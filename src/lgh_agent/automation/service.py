from __future__ import annotations

import asyncio
from threading import Event

from lgh_agent.automation.store import AutomationStore
from lgh_agent.bus import InboundMessage, MessageBus


class AutomationService:
    """Runs due automation jobs through the normal message bus."""

    def __init__(
        self,
        *,
        store: AutomationStore,
        bus: MessageBus,
        poll_seconds: float = 1.0,
    ) -> None:
        self.store = store
        self.bus = bus
        self.poll_seconds = poll_seconds

    async def run_due_once(self, *, now: float | None = None) -> int:
        handled = 0
        for job in self.store.due_jobs(now=now):
            try:
                await self.bus.submit(InboundMessage(content=job.prompt, session=job.session))
            except Exception as exc:  # pragma: no cover - defensive boundary for background work
                self.store.mark_failed(job.id, str(exc))
            else:
                self.store.mark_done(job.id)
            handled += 1
        return handled

    async def run_forever(self, stop_event: Event) -> None:
        while not stop_event.is_set():
            await self.run_due_once()
            await asyncio.sleep(self.poll_seconds)
