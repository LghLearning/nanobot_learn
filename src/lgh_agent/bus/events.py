from __future__ import annotations

from dataclasses import dataclass, field

from lgh_agent.tools.base import ToolEvent


@dataclass(frozen=True, slots=True)
class InboundMessage:
    """A normalized user message from any future channel."""

    content: str
    session: str = "default"
    use_real_provider: bool = False


@dataclass(frozen=True, slots=True)
class OutboundMessage:
    """A normalized assistant response returned to a channel."""

    content: str
    session: str
    tool_events: list[ToolEvent] = field(default_factory=list)
