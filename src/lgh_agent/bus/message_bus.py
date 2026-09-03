from __future__ import annotations

from collections.abc import AsyncIterator

from lgh_agent.bus.events import InboundMessage, OutboundMessage
from lgh_agent.runtime import build_agent
from lgh_agent.tools.base import ToolEvent


class MessageBus:
    """Routes normalized messages into AgentLoop.

    Today the bus is a thin adapter. Later it can own queues, channel routing,
    retries, cancellation, and background workers without changing API/CLI code.
    """

    def __init__(
        self,
        *,
        default_use_real_provider: bool = False,
        workspace: str | None = None,
        tool_root: str | None = None,
    ) -> None:
        self.default_use_real_provider = default_use_real_provider
        self.workspace = workspace
        self.tool_root = tool_root

    async def submit(self, message: InboundMessage) -> OutboundMessage:
        events: list[ToolEvent] = []
        agent = build_agent(
            use_real_provider=message.use_real_provider or self.default_use_real_provider,
            session_name=message.session,
            workspace=self.workspace,
            tool_root=self.tool_root,
            on_tool_event=events.append,
        )
        content = await agent.ask(message.content)
        return OutboundMessage(
            content=content,
            session=message.session,
            tool_events=events,
        )

    async def submit_stream(self, message: InboundMessage) -> AsyncIterator[str | OutboundMessage]:
        events: list[ToolEvent] = []
        agent = build_agent(
            use_real_provider=message.use_real_provider or self.default_use_real_provider,
            session_name=message.session,
            workspace=self.workspace,
            tool_root=self.tool_root,
            on_tool_event=events.append,
        )
        async for chunk in agent.ask_stream(message.content):
            yield chunk
        yield OutboundMessage(content="", session=message.session, tool_events=events)
