from __future__ import annotations

import asyncio

import pytest

from lgh_agent.automation.service import AutomationService
from lgh_agent.automation.store import AutomationStore, parse_delay_seconds
from lgh_agent.bus import MessageBus
from lgh_agent.errors import LghAgentError
from lgh_agent.runtime import build_agent


def test_parse_delay_seconds() -> None:
    assert parse_delay_seconds("10s") == 10
    assert parse_delay_seconds("5m") == 300
    assert parse_delay_seconds("2h") == 7200
    assert parse_delay_seconds("1d") == 86400


def test_parse_delay_seconds_rejects_invalid_value() -> None:
    with pytest.raises(LghAgentError):
        parse_delay_seconds("tomorrow")


def test_automation_store_add_due_cancel_and_mark_done(tmp_path) -> None:
    store = AutomationStore(tmp_path)

    job = store.add_reminder(session="default", prompt="stand up", delay_seconds=60)

    assert store.list_jobs()[0].id == job.id
    assert store.due_jobs(now=job.run_at - 1) == []
    assert store.due_jobs(now=job.run_at + 1)[0].id == job.id

    cancelled = store.cancel(job.id)
    assert cancelled is not None
    assert store.due_jobs(now=job.run_at + 1) == []

    done_job = store.add_reminder(session="default", prompt="drink water", delay_seconds=1)
    store.mark_done(done_job.id)
    assert store.list_jobs()[-1].status == "done"


def test_agent_loop_remind_and_jobs_commands(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    agent = build_agent(workspace=str(workspace), session_name="learn")

    async def run_case() -> tuple[str, str, str]:
        scheduled = await agent.ask("/remind 5m review notes")
        jobs = await agent.ask("/jobs")
        job_id = AutomationStore(workspace).list_jobs()[0].id
        cancelled = await agent.ask(f"/job cancel {job_id}")
        return scheduled, jobs, cancelled

    scheduled, jobs, cancelled = asyncio.run(run_case())

    assert scheduled.startswith("Reminder scheduled:")
    assert "review notes" in jobs
    assert cancelled.startswith("Cancelled job:")


def test_automation_service_runs_due_jobs(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    store = AutomationStore(workspace)
    job = store.add_reminder(session="auto", prompt="background hello", delay_seconds=1)
    bus = MessageBus(workspace=str(workspace), tool_root=str(tmp_path))
    service = AutomationService(store=store, bus=bus)

    async def run_case() -> int:
        return await service.run_due_once(now=job.run_at - 1)

    handled = asyncio.run(run_case())

    assert handled == 0

    async def run_due_case() -> int:
        return await service.run_due_once(now=job.run_at + 1)

    handled = asyncio.run(run_due_case())

    assert handled == 1
    assert store.list_jobs()[0].status == "done"
