from __future__ import annotations

from collections.abc import Callable

from lgh_agent.agent.runner import AgentRunner
from lgh_agent.providers.base import Message
from lgh_agent.tools import ToolRegistry
from lgh_agent.tools.base import ToolEvent


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
    ) -> None:
        self.runner = runner
        self.history: list[Message] = list(history or [])
        self._on_message = on_message
        self._on_tool_event = on_tool_event
        self.tools = tools
        self.last_tool_events: list[ToolEvent] = []

    async def ask(self, text: str) -> str:
        self.last_tool_events = []
        user_message: Message = {"role": "user", "content": text}
        self._append_message(user_message)

        if self._is_tool_command(text):
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

    def _append_message(self, message: Message) -> None:
        self.history.append(message)
        if self._on_message is not None:
            self._on_message(message)

    def _is_tool_command(self, text: str) -> bool:
        return text.startswith("/tool ") or text == "/tools"

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
