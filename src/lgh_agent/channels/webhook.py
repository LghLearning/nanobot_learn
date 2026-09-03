from __future__ import annotations

from typing import Any

from lgh_agent.bus import InboundMessage, MessageBus, OutboundMessage
from lgh_agent.errors import LghAgentError


class WebhookAuthError(LghAgentError):
    """Raised when a webhook request does not provide the expected token."""


class WebhookChannel:
    """Generic HTTP webhook channel.

    It accepts a small neutral JSON shape and converts it into InboundMessage,
    the same internal message type used by CLI and future bot channels.
    """

    def __init__(
        self,
        bus: MessageBus,
        *,
        name: str = "default",
        token: str | None = None,
        default_session: str = "webhook",
        enabled: bool = True,
    ) -> None:
        self.name = name
        self.bus = bus
        self.token = token
        self.default_session = default_session
        self.enabled = enabled

    def authenticate(self, authorization_header: str | None) -> None:
        if not self.token:
            return
        expected = f"Bearer {self.token}"
        if authorization_header != expected:
            raise WebhookAuthError("Invalid webhook token.")

    def to_inbound(
        self,
        payload: dict[str, Any],
        *,
        use_real_provider: bool = False,
    ) -> InboundMessage:
        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            raise LghAgentError("Webhook body must include a non-empty 'message'.")
        session = str(payload.get("session") or self.default_session)
        return InboundMessage(
            content=message.strip(),
            session=session,
            use_real_provider=bool(payload.get("real", use_real_provider)),
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
        inbound = self.to_inbound(payload, use_real_provider=use_real_provider)
        return await self.bus.submit(inbound)
