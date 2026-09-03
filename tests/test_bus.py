from __future__ import annotations

import asyncio

from lgh_agent.bus import InboundMessage, MessageBus, OutboundMessage


def test_message_bus_submits_inbound_message(tmp_path) -> None:
    bus = MessageBus(workspace=str(tmp_path / "workspace"), tool_root=str(tmp_path))

    async def run_case() -> OutboundMessage:
        return await bus.submit(InboundMessage(content="hello", session="bus-test"))

    outbound = asyncio.run(run_case())

    assert outbound.content == "Echo: hello"
    assert outbound.session == "bus-test"
    assert outbound.tool_events == []


def test_message_bus_streams_inbound_message(tmp_path) -> None:
    bus = MessageBus(workspace=str(tmp_path / "workspace"), tool_root=str(tmp_path))

    async def run_case() -> list[str | OutboundMessage]:
        return [
            item
            async for item in bus.submit_stream(
                InboundMessage(content="hello stream", session="bus-stream")
            )
        ]

    items = asyncio.run(run_case())

    assert "".join(item for item in items if isinstance(item, str)) == "Echo: hello stream"
    assert isinstance(items[-1], OutboundMessage)
    assert items[-1].session == "bus-stream"
