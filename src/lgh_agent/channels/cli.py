from __future__ import annotations

from lgh_agent.bus import InboundMessage, MessageBus, OutboundMessage
from lgh_agent.errors import LghAgentError
from lgh_agent.tools.base import ToolEvent


EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit"}


class CLIChannel:
    """Terminal channel.

    The channel handles terminal input/output and submits normalized messages
    to MessageBus. It does not know how AgentLoop, tools, memory, or providers
    are built.
    """

    def __init__(
        self,
        bus: MessageBus,
        *,
        session_name: str = "default",
        use_real_provider: bool = False,
        stream: bool = False,
    ) -> None:
        self.bus = bus
        self.session_name = session_name
        self.use_real_provider = use_real_provider
        self.stream = stream

    async def run(self) -> None:
        provider_name = "real provider" if self.use_real_provider else "fake provider"
        print(
            f"lgh_agent is ready using {provider_name} "
            f"in session '{self.session_name}'. Type 'exit' to quit."
        )
        print("Try '/tools' or '/tool list_files .' to inspect the tool layer.")

        while True:
            try:
                text = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not text:
                continue
            if text.lower() in EXIT_COMMANDS:
                break

            try:
                inbound = InboundMessage(
                    content=text,
                    session=self.session_name,
                    use_real_provider=self.use_real_provider,
                )
                if self.stream:
                    await self._handle_stream(inbound)
                else:
                    outbound = await self.bus.submit(inbound)
                    self._print_outbound(outbound)
            except LghAgentError as exc:
                print(f"Error: {exc}")

    async def _handle_stream(self, inbound: InboundMessage) -> None:
        print("Agent: ", end="", flush=True)
        final: OutboundMessage | None = None
        async for item in self.bus.submit_stream(inbound):
            if isinstance(item, str):
                print(item, end="", flush=True)
            else:
                final = item
        print()
        if final is not None:
            for event in final.tool_events:
                self._print_tool_event(event)

    def _print_outbound(self, outbound: OutboundMessage) -> None:
        print(f"Agent: {outbound.content}")
        for event in outbound.tool_events:
            self._print_tool_event(event)

    def _print_tool_event(self, event: ToolEvent) -> None:
        status = "ok" if event.ok else "error"
        detail = event.content_preview if event.ok else event.error
        print(f"[tool:{status}] {event.name} {event.arguments} -> {detail}")
