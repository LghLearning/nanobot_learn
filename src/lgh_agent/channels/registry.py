from __future__ import annotations

from lgh_agent.bus import OutboundMessage
from typing import Any, Protocol

from lgh_agent.errors import LghAgentError


class MessageAdapter(Protocol):
    """Converts one external channel payload into an InboundMessage."""

    name: str

    def to_inbound(self, payload: dict[str, Any], *, use_real_provider: bool = False):
        ...

    async def handle(
        self,
        payload: dict[str, Any],
        *,
        authorization_header: str | None,
        use_real_provider: bool = False,
    ) -> OutboundMessage:
        ...


class ChannelRegistry:
    """Central lookup table for HTTP/webhook style channel adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, MessageAdapter] = {}

    def register(self, adapter: MessageAdapter) -> None:
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> MessageAdapter:
        try:
            return self._adapters[name]
        except KeyError as exc:
            raise LghAgentError(f"Unknown channel: {name}") from exc

    def names(self) -> list[str]:
        return sorted(self._adapters)
