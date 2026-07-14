from __future__ import annotations

import os

from lgh_agent.config import load_dotenv


def test_load_dotenv_reads_key_value_pairs(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "LGH_AGENT_API_KEY=test-key",
                "LGH_AGENT_BASE_URL=https://example.test/v1",
                "LGH_AGENT_MODEL=test-model",
            ]
        ),
        encoding="utf-8",
    )

    load_dotenv(env_file)

    assert os.getenv("LGH_AGENT_API_KEY") == "test-key"
    assert os.getenv("LGH_AGENT_BASE_URL") == "https://example.test/v1"
    assert os.getenv("LGH_AGENT_MODEL") == "test-model"


def test_load_dotenv_does_not_override_existing_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LGH_AGENT_API_KEY", "already-set")
    env_file = tmp_path / ".env"
    env_file.write_text("LGH_AGENT_API_KEY=from-file", encoding="utf-8")

    load_dotenv(env_file)

    assert os.getenv("LGH_AGENT_API_KEY") == "already-set"
