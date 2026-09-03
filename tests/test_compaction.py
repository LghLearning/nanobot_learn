from __future__ import annotations

from lgh_agent.runtime import build_agent
from lgh_agent.session import SessionStore
from lgh_agent.session.compaction import compact_history


def test_compact_history_adds_summary_and_keeps_recent_messages() -> None:
    history = [
        {"role": "user", "content": f"user {index}"}
        for index in range(6)
    ]

    result = compact_history(history, keep_recent=2, summary_message_limit=2)

    assert result.compacted is True
    assert result.messages[0]["role"] == "system"
    assert "Summary of earlier conversation" in result.messages[0]["content"]
    assert result.messages[-2:] == [
        {"role": "user", "content": "user 4"},
        {"role": "user", "content": "user 5"},
    ]


def test_runtime_compacts_loaded_session_history(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    store = SessionStore(workspace, session_name="long")
    for index in range(8):
        store.append_message({"role": "user", "content": f"message {index}"})

    monkeypatch.setenv("LGH_AGENT_MAX_HISTORY_MESSAGES", "3")
    monkeypatch.setenv("LGH_AGENT_SUMMARY_MESSAGE_LIMIT", "2")

    agent = build_agent(workspace=str(workspace), session_name="long")

    assert agent.history[0]["role"] == "system"
    assert "Summary of earlier conversation" in agent.history[0]["content"]
    assert [message["content"] for message in agent.history[-3:]] == [
        "message 5",
        "message 6",
        "message 7",
    ]
