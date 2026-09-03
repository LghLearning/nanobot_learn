from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lgh_agent.bus import MessageBus
from lgh_agent.channels.discord import DiscordMockChannel
from lgh_agent.channels.registry import ChannelRegistry
from lgh_agent.channels.telegram import TelegramMockChannel
from lgh_agent.channels.webhook import WebhookChannel
from lgh_agent.config import AppConfig
from lgh_agent.errors import LghAgentError


@dataclass(frozen=True, slots=True)
class ChannelConfig:
    name: str
    kind: str = "webhook"
    enabled: bool = True
    token: str | None = None
    default_session: str | None = None


class ChannelManager:
    """Builds channel adapters from configuration and exposes one registry."""

    def __init__(self, *, bus: MessageBus, app_config: AppConfig) -> None:
        self.bus = bus
        self.app_config = app_config
        self.registry = ChannelRegistry()
        self.configs = load_channel_configs(app_config)
        self._register_channels()

    def get(self, name: str):
        return self.registry.get(name)

    def names(self) -> list[str]:
        return self.registry.names()

    def describe(self) -> list[dict[str, object]]:
        return [
            {
                "name": config.name,
                "kind": config.kind,
                "enabled": config.enabled,
                "has_token": bool(config.token),
                "default_session": config.default_session,
            }
            for config in self.configs
        ]

    def _register_channels(self) -> None:
        for config in self.configs:
            if config.kind == "webhook":
                self.registry.register(
                    WebhookChannel(
                        self.bus,
                        name=config.name,
                        token=config.token,
                        default_session=config.default_session or "webhook",
                        enabled=config.enabled,
                    )
                )
            elif config.kind == "telegram":
                self.registry.register(
                    TelegramMockChannel(
                        self.bus,
                        name=config.name,
                        token=config.token,
                        default_session=config.default_session,
                        enabled=config.enabled,
                    )
                )
            elif config.kind == "discord":
                self.registry.register(
                    DiscordMockChannel(
                        self.bus,
                        name=config.name,
                        token=config.token,
                        default_session=config.default_session,
                        enabled=config.enabled,
                    )
                )
            else:
                raise LghAgentError(f"Unsupported channel kind: {config.kind}")


def load_channel_configs(app_config: AppConfig) -> list[ChannelConfig]:
    path = app_config.channels_config_path
    if path is None:
        return [
            ChannelConfig(
                name="default",
                kind="webhook",
                token=app_config.webhook_token,
                default_session="webhook",
            )
        ]
    return _read_channel_config_file(path)


def _read_channel_config_file(path: Path) -> list[ChannelConfig]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    channels = raw.get("channels") if isinstance(raw, dict) else None
    if not isinstance(channels, list):
        raise LghAgentError("channels.json must contain a 'channels' list.")
    configs: list[ChannelConfig] = []
    for item in channels:
        if not isinstance(item, dict):
            raise LghAgentError("Each channel config must be an object.")
        configs.append(_parse_channel_config(item))
    return configs


def _parse_channel_config(item: dict[str, Any]) -> ChannelConfig:
    name = item.get("name")
    if not isinstance(name, str) or not name.strip():
        raise LghAgentError("Channel config must include a non-empty name.")
    kind = item.get("kind", "webhook")
    if not isinstance(kind, str) or not kind.strip():
        raise LghAgentError("Channel config kind must be a string.")
    enabled = item.get("enabled", True)
    if not isinstance(enabled, bool):
        raise LghAgentError("Channel config enabled must be true or false.")
    token = item.get("token")
    if token is not None and not isinstance(token, str):
        raise LghAgentError("Channel config token must be a string.")
    default_session = item.get("default_session")
    if default_session is not None and not isinstance(default_session, str):
        raise LghAgentError("Channel config default_session must be a string.")
    return ChannelConfig(
        name=name.strip(),
        kind=kind.strip(),
        enabled=enabled,
        token=token,
        default_session=default_session,
    )
