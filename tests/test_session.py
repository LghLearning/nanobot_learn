from __future__ import annotations

from lgh_agent.errors import ConfigError
from lgh_agent.session import SessionStore


def test_session_store_appends_and_loads_messages(tmp_path) -> None:
    store = SessionStore(tmp_path, session_name="study")
    store.append_message({"role": "user", "content": "hello"})
    store.append_message({"role": "assistant", "content": "Echo: hello"})

    reloaded = SessionStore(tmp_path, session_name="study")

    assert reloaded.load_history() == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "Echo: hello"},
    ]


def test_session_store_rejects_unsafe_session_names(tmp_path) -> None:
    try:
        SessionStore(tmp_path, session_name="../secret")
    except ConfigError as exc:
        assert "Session name" in str(exc)
    else:
        raise AssertionError("Expected ConfigError")
