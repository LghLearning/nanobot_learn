from __future__ import annotations

import asyncio

from lgh_agent.agent.loop import AgentLoop
from lgh_agent.agent.runner import AgentRunner
from lgh_agent.memory import MemoryStore
from lgh_agent.providers.fake import FakeProvider
from lgh_agent.runtime import build_agent


def test_memory_store_add_read_and_clear(tmp_path) -> None:
    store = MemoryStore(tmp_path)
    assert store.read() == ""

    store.add("User likes concise explanations.")

    assert store.read() == "- User likes concise explanations."

    store.clear()
    assert store.read() == ""


def test_agent_loop_memory_commands(tmp_path) -> None:
    memory = MemoryStore(tmp_path)
    agent = AgentLoop(AgentRunner(FakeProvider()), memory=memory)

    async def run_case() -> tuple[str, str, str]:
        saved = await agent.ask("/memory add User is learning agents.")
        shown = await agent.ask("/memory show")
        cleared = await agent.ask("/memory clear")
        return saved, shown, cleared

    saved, shown, cleared = asyncio.run(run_case())

    assert saved == "Memory saved."
    assert "- User is learning agents." in shown
    assert cleared == "Memory cleared."


def test_runtime_injects_memory_as_system_message(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    MemoryStore(workspace).add("User is building lgh_agent.")

    agent = build_agent(workspace=str(workspace))

    assert agent.history[0]["role"] == "system"
    assert "User is building lgh_agent." in agent.history[0]["content"]
