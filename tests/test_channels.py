from __future__ import annotations

from lgh_agent.bus import MessageBus, OutboundMessage
from lgh_agent.channels import CLIChannel
from lgh_agent.tools.base import ToolEvent


def test_cli_channel_prints_outbound_message(capsys, tmp_path) -> None:
    bus = MessageBus(workspace=str(tmp_path / "workspace"), tool_root=str(tmp_path))
    channel = CLIChannel(bus, session_name="cli-test")

    channel._print_outbound(
        OutboundMessage(
            content="hello",
            session="cli-test",
            tool_events=[
                ToolEvent(
                    name="read_file",
                    arguments={"path": "note.txt"},
                    content_preview="note content",
                )
            ],
        )
    )

    captured = capsys.readouterr()

    assert "Agent: hello" in captured.out
    assert "[tool:ok] read_file" in captured.out
