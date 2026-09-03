from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from lgh_agent.errors import LghAgentError


@dataclass(frozen=True, slots=True)
class AutomationJob:
    id: str
    session: str
    prompt: str
    run_at: float
    created_at: float
    status: str = "pending"
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class AutomationStore:
    """Stores local automation jobs in the agent workspace."""

    def __init__(self, workspace: Path) -> None:
        self.path = workspace / "automation" / "jobs.json"

    def list_jobs(self) -> list[AutomationJob]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise LghAgentError("Automation jobs file is not a JSON list.")
        return [AutomationJob(**item) for item in raw if isinstance(item, dict)]

    def add_reminder(self, *, session: str, prompt: str, delay_seconds: int) -> AutomationJob:
        now = time.time()
        job = AutomationJob(
            id=uuid.uuid4().hex[:12],
            session=session,
            prompt=prompt,
            run_at=now + delay_seconds,
            created_at=now,
        )
        self._save([*self.list_jobs(), job])
        return job

    def cancel(self, job_id: str) -> AutomationJob | None:
        jobs = self.list_jobs()
        updated: list[AutomationJob] = []
        found: AutomationJob | None = None
        for job in jobs:
            if job.id == job_id and job.status == "pending":
                found = _replace_job(job, status="cancelled")
                updated.append(found)
            else:
                updated.append(job)
        if found is not None:
            self._save(updated)
        return found

    def due_jobs(self, *, now: float | None = None) -> list[AutomationJob]:
        current_time = time.time() if now is None else now
        return [
            job
            for job in self.list_jobs()
            if job.status == "pending" and job.run_at <= current_time
        ]

    def mark_done(self, job_id: str) -> None:
        self._update_status(job_id, status="done")

    def mark_failed(self, job_id: str, error: str) -> None:
        self._update_status(job_id, status="failed", error=error)

    def _update_status(self, job_id: str, *, status: str, error: str | None = None) -> None:
        self._save(
            [
                _replace_job(job, status=status, error=error) if job.id == job_id else job
                for job in self.list_jobs()
            ]
        )

    def _save(self, jobs: list[AutomationJob]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [job.to_dict() for job in jobs]
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_delay_seconds(value: str) -> int:
    """Parse a compact delay such as 10s, 5m, 2h, or 1d."""

    match = re.fullmatch(r"(\d+)([smhd])", value.strip().lower())
    if match is None:
        raise LghAgentError("Delay must look like 10s, 5m, 2h, or 1d.")
    amount = int(match.group(1))
    unit = match.group(2)
    multiplier = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    seconds = amount * multiplier
    if seconds <= 0:
        raise LghAgentError("Delay must be greater than zero.")
    return seconds


def _replace_job(
    job: AutomationJob,
    *,
    status: str,
    error: str | None = None,
) -> AutomationJob:
    return AutomationJob(
        id=job.id,
        session=job.session,
        prompt=job.prompt,
        run_at=job.run_at,
        created_at=job.created_at,
        status=status,
        error=error,
    )
