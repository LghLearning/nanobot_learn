from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from lgh_agent.errors import ConfigError


@dataclass(frozen=True, slots=True)
class AppConfig:
    workspace: Path


@dataclass(frozen=True, slots=True)
class OpenAICompatibleConfig:
    api_key: str
    base_url: str
    model: str
    timeout_s: float = 60.0


def load_app_config(workspace: str | None = None) -> AppConfig:
    """Load non-secret app settings."""

    load_dotenv()
    raw_workspace = workspace or os.getenv("LGH_AGENT_WORKSPACE")
    if raw_workspace:
        workspace_path = Path(raw_workspace).expanduser()
    else:
        workspace_path = _project_root() / ".lgh_agent"
    return AppConfig(workspace=workspace_path)


def load_openai_compatible_config() -> OpenAICompatibleConfig:
    """Load real model settings from environment variables."""

    load_dotenv()

    api_key = os.getenv("LGH_AGENT_API_KEY")
    if not api_key:
        raise ConfigError("Missing LGH_AGENT_API_KEY. Add it to .env or your shell environment.")

    base_url = os.getenv("LGH_AGENT_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("LGH_AGENT_MODEL", "gpt-4.1-mini")
    try:
        timeout_s = float(os.getenv("LGH_AGENT_TIMEOUT_S", "60"))
    except ValueError as exc:
        raise ConfigError("LGH_AGENT_TIMEOUT_S must be a number, such as 60.") from exc

    return OpenAICompatibleConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_s=timeout_s,
    )


def load_dotenv(path: Path | None = None) -> None:
    """Load KEY=VALUE pairs from a local .env file.

    Existing environment variables win over .env values.
    """

    env_path = path or _default_env_path()
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def _default_env_path() -> Path:
    return _project_root() / ".env"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]
