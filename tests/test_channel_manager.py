from __future__ import annotations

import asyncio
import json

from lgh_agent.bus import MessageBus
from lgh_agent.channels import ChannelManager
from lgh_agent.channels.discord import DiscordMockChannel
from lgh_agent.channels.telegram import TelegramMockChannel
from lgh_agent.config import load_app_config


def test_channel_manager_uses_default_webhook_channel(tmp_path) -> None:
    app_config = load_app_config(str(tmp_path / "workspace"))
    manager = ChannelManager(
        bus=MessageBus(workspace=str(tmp_path / "workspace")),
        app_config=app_config,
    )

    assert manager.names() == ["default"]
    assert manager.describe()[0]["kind"] == "webhook"


def test_channel_manager_loads_channels_json(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_path = workspace / "channels.json"
    config_path.write_text(
        json.dumps(
            {
                "channels": [
                    {
                        "name": "ops",
                        "kind": "webhook",
                        "token": "ops-token",
                        "default_session": "ops-session",
                    },
                    {"name": "tg", "kind": "telegram"},
                    {"name": "dc", "kind": "discord", "enabled": False},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LGH_AGENT_CHANNELS_CONFIG", str(config_path))
    app_config = load_app_config(str(workspace))
    manager = ChannelManager(bus=MessageBus(workspace=str(workspace)), app_config=app_config)

    assert manager.names() == ["dc", "ops", "tg"]
    assert manager.describe()[0]["name"] == "ops"


def test_telegram_mock_channel_converts_update(tmp_path) -> None:
    channel = TelegramMockChannel(MessageBus(workspace=str(tmp_path / "workspace")))

    inbound = channel.to_inbound(
        {
            "message": {
                "text": "hello telegram",
                "chat": {"id": 123},
            }
        }
    )

    assert inbound.content == "hello telegram"
    assert inbound.session == "telegram-123"


def test_discord_mock_channel_converts_event(tmp_path) -> None:
    channel = DiscordMockChannel(MessageBus(workspace=str(tmp_path / "workspace")))

    inbound = channel.to_inbound({"content": "hello discord", "channel_id": "room"})

    assert inbound.content == "hello discord"
    assert inbound.session == "discord-room"


def test_configured_mock_channels_submit_to_bus(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_path = workspace / "channels.json"
    config_path.write_text(
        json.dumps(
            {
                "channels": [
                    {"name": "tg", "kind": "telegram"},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LGH_AGENT_CHANNELS_CONFIG", str(config_path))
    manager = ChannelManager(
        bus=MessageBus(workspace=str(workspace)),
        app_config=load_app_config(str(workspace)),
    )

    async def run_case():
        return await manager.get("tg").handle(
            {"message": {"text": "from tg", "chat": {"id": 9}}},
            authorization_header=None,
        )

    outbound = asyncio.run(run_case())

    assert outbound.content == "Echo: from tg"
    assert outbound.session == "telegram-9"
