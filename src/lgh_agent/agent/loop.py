from __future__ import annotations

from collections.abc import Callable
from collections.abc import AsyncIterator

from lgh_agent.agent.runner import AgentRunner
from lgh_agent.automation.store import AutomationStore, parse_delay_seconds
from lgh_agent.providers.base import Message
from lgh_agent.tools import ToolRegistry
from lgh_agent.tools.base import ToolEvent
from lgh_agent.memory import MemoryStore


class AgentLoop:
    """Handles one conversation session.

    AgentLoop owns conversation history. It also collects tool events for the
    latest turn, which gives us a simple observability layer.
    """

    def __init__(
        self,
        runner: AgentRunner,
        *,
        history: list[Message] | None = None,
        on_message: Callable[[Message], None] | None = None,
        on_tool_event: Callable[[ToolEvent], None] | None = None,
        tools: ToolRegistry | None = None,
        memory: MemoryStore | None = None,
        automation: AutomationStore | None = None,
        session_name: str = "default",
    ) -> None:
        self.runner = runner
        self.history: list[Message] = list(history or [])
        self._on_message = on_message
        self._on_tool_event = on_tool_event
        self.tools = tools
        self.memory = memory
        self.automation = automation
        self.session_name = session_name
        self.last_tool_events: list[ToolEvent] = []

    async def ask(self, text: str) -> str:
        self.last_tool_events = []
        user_message: Message = {"role": "user", "content": text}
        self._append_message(user_message)

        if self._is_memory_command(text):
            answer = self._run_memory_command(text)
        elif self._is_automation_command(text):
            answer = self._run_automation_command(text)
        elif self._is_tool_command(text):
            answer = await self._run_tool_command(text)
        else:
            answer = await self.runner.run(
                self.history,
                tools=self.tools,
                on_tool_event=self._record_tool_event,
            )

        assistant_message: Message = {"role": "assistant", "content": answer}
        self._append_message(assistant_message)
        return answer

    async def ask_stream(self, text: str) -> AsyncIterator[str]:
        """Run one turn and yield answer chunks."""

        self.last_tool_events = []
        user_message: Message = {"role": "user", "content": text}
        self._append_message(user_message)

        if self._is_memory_command(text):
            answer = self._run_memory_command(text)
            self._append_message({"role": "assistant", "content": answer})
            for chunk in _chunk_text(answer):
                yield chunk
            return

        if self._is_automation_command(text):
            answer = self._run_automation_command(text)
            self._append_message({"role": "assistant", "content": answer})
            for chunk in _chunk_text(answer):
                yield chunk
            return

        if self._is_tool_command(text):
            answer = await self._run_tool_command(text)
            self._append_message({"role": "assistant", "content": answer})
            for chunk in _chunk_text(answer):
                yield chunk
            return

        chunks: list[str] = []
        async for chunk in self.runner.run_stream(
            self.history,
            tools=self.tools,
            on_tool_event=self._record_tool_event,
        ):
            chunks.append(chunk)
            yield chunk
        self._append_message({"role": "assistant", "content": "".join(chunks)})

    def _append_message(self, message: Message) -> None:
        self.history.append(message)
        if self._on_message is not None:
            self._on_message(message)

    def _is_tool_command(self, text: str) -> bool:
        return text.startswith("/tool ") or text == "/tools"

    def _is_memory_command(self, text: str) -> bool:
        return text == "/memory" or text.startswith("/memory ")

    def _is_automation_command(self, text: str) -> bool:
        return text == "/jobs" or text.startswith("/job ") or text.startswith("/remind ")

    def _run_memory_command(self, text: str) -> str:
        if self.memory is None:
            return "No memory store is configured."

        parts = text.split(" ", 2)
        action = parts[1] if len(parts) > 1 else "show"
        if action == "show":
            content = self.memory.read()
            return content if content else "Memory is empty."
        if action == "add":
            if len(parts) < 3 or not parts[2].strip():
                return "Usage: /memory add <text>"
            self.memory.add(parts[2])
            return "Memory saved."
        if action == "clear":
            self.memory.clear()
            return "Memory cleared."
        return "Usage: /memory show | /memory add <text> | /memory clear"

    def _run_automation_command(self, text: str) -> str:
        if self.automation is None:
            return "No automation store is configured."

        if text == "/jobs" or text == "/job list":
            jobs = [job for job in self.automation.list_jobs() if job.status == "pending"]
            if not jobs:
                return "No pending jobs."
            lines = ["Pending jobs:"]
            for job in jobs:
                lines.append(f"- {job.id} | session={job.session} | run_at={job.run_at:.0f} | {job.prompt}")
            return "\n".join(lines)

        if text.startswith("/job cancel "):
            job_id = text.removeprefix("/job cancel ").strip()
            if not job_id:
                return "Usage: /job cancel <job_id>"
            cancelled = self.automation.cancel(job_id)
            if cancelled is None:
                return f"No pending job found for id: {job_id}"
            return f"Cancelled job: {cancelled.id}"

        if text.startswith("/remind "):
            parts = text.split(" ", 2)
            if len(parts) < 3 or not parts[2].strip():
                return "Usage: /remind <10s|5m|2h|1d> <message>"
            delay_seconds = parse_delay_seconds(parts[1])
            job = self.automation.add_reminder(
                session=self.session_name,
                prompt=parts[2].strip(),
                delay_seconds=delay_seconds,
            )
            return f"Reminder scheduled: {job.id}"

        return "Usage: /remind <10s|5m|2h|1d> <message> | /jobs | /job cancel <job_id>"

    async def _run_tool_command(self, text: str) -> str:
        if self.tools is None:
            return "No tools are configured."
        result = await self.tools.run_command(text)
        self._record_tool_event(
            ToolEvent(
                name="manual",
                arguments={"command": text},
                content_preview=result.content[:180],
            )
        )
        return result.content

    def _record_tool_event(self, event: ToolEvent) -> None:
        self.last_tool_events.append(event)
        if self._on_tool_event is not None:
            self._on_tool_event(event)


def _chunk_text(text: str, chunk_size: int = 24) -> list[str]:
    if not text:
        return [""]
    return [text[index : index + chunk_size] for index in range(0, len(text), chunk_size)]
