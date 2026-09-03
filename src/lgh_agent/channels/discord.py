from __future__ import annotations

from typing import Any

from lgh_agent.bus import InboundMessage, MessageBus, OutboundMessage
from lgh_agent.channels.webhook import WebhookAuthError
from lgh_agent.errors import LghAgentError


class DiscordMockChannel:
    """Parses Discord-like message JSON without connecting to Discord."""

    def __init__(
        self,
        bus: MessageBus,
        *,
        name: str = "discord",
        token: str | None = None,
        default_session: str | None = None,
        enabled: bool = True,
    ) -> None:
        self.bus = bus
        self.name = name
        self.token = token
        self.default_session = default_session
        self.enabled = enabled

    def authenticate(self, authorization_header: str | None) -> None:
        if not self.token:
            return
        if authorization_header != f"Bearer {self.token}":
            raise WebhookAuthError("Invalid webhook token.")

    def to_inbound(
        self,
        payload: dict[str, Any],
        *,
        use_real_provider: bool = False,
    ) -> InboundMessage:
        content = payload.get("content")
        if not isinstance(content, str) or not content.strip():
            raise LghAgentError("Discord mock payload must include non-empty content.")
        channel_id = payload.get("channel_id")
        session = self.default_session or f"discord-{channel_id or 'unknown'}"
        return InboundMessage(
            content=content.strip(),
            session=session,
            use_real_provider=use_real_provider,
        )

    async def handle(
        self,
        payload: dict[str, Any],
        *,
        authorization_header: str | None,
        use_real_provider: bool = False,
    ) -> OutboundMessage:
        self.authenticate(authorization_header)
        if not self.enabled:
            raise LghAgentError(f"Channel is disabled: {self.name}")
        return await self.bus.submit(self.to_inbound(payload, use_real_provider=use_real_provider))
