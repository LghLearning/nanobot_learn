from __future__ import annotations

import asyncio

import pytest

from lgh_agent.bus import MessageBus
from lgh_agent.channels import ChannelRegistry, WebhookAuthError, WebhookChannel
from lgh_agent.errors import LghAgentError


def test_webhook_channel_converts_payload_to_inbound_message(tmp_path) -> None:
    channel = WebhookChannel(
        MessageBus(workspace=str(tmp_path / "workspace")),
        default_session="fallback",
    )

    inbound = channel.to_inbound({"message": "hello", "session": "webhook-user"})

    assert inbound.content == "hello"
    assert inbound.session == "webhook-user"

    fallback = channel.to_inbound({"message": "hello again"})
    assert fallback.session == "fallback"


def test_webhook_channel_rejects_missing_message(tmp_path) -> None:
    channel = WebhookChannel(MessageBus(workspace=str(tmp_path / "workspace")))

    with pytest.raises(LghAgentError):
        channel.to_inbound({"session": "webhook-user"})


def test_webhook_channel_checks_bearer_token(tmp_path) -> None:
    channel = WebhookChannel(MessageBus(workspace=str(tmp_path / "workspace")), token="secret")

    channel.authenticate("Bearer secret")
    with pytest.raises(WebhookAuthError):
        channel.authenticate("Bearer wrong")


def test_webhook_channel_submits_to_message_bus(tmp_path) -> None:
    channel = WebhookChannel(MessageBus(workspace=str(tmp_path / "workspace")))

    async def run_case():
        return await channel.handle(
            {"message": "hello webhook", "session": "hook"},
            authorization_header=None,
        )

    outbound = asyncio.run(run_case())

    assert outbound.content == "Echo: hello webhook"
    assert outbound.session == "hook"


def test_channel_registry_registers_and_finds_channels(tmp_path) -> None:
    registry = ChannelRegistry()
    channel = WebhookChannel(MessageBus(workspace=str(tmp_path / "workspace")))

    registry.register(channel)

    assert registry.names() == ["default"]
    assert registry.get("default") is channel
