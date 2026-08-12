from __future__ import annotations

import asyncio

from lgh_agent.agent.loop import AgentLoop
from lgh_agent.agent.runner import AgentRunner
from lgh_agent.errors import ToolError
from lgh_agent.providers.fake import FakeProvider
from lgh_agent.tools import ToolRegistry, create_filesystem_tools


def test_tool_registry_lists_tools(tmp_path) -> None:
    registry = ToolRegistry(create_filesystem_tools(tmp_path))

    async def run_case() -> str:
        result = await registry.run_command("/tools")
        return result.content

    output = asyncio.run(run_case())

    assert "read_file" in output
    assert "list_files" in output


def test_filesystem_tools_list_and_read_files(tmp_path) -> None:
    (tmp_path / "note.txt").write_text("hello tools", encoding="utf-8")
    registry = ToolRegistry(create_filesystem_tools(tmp_path))

    async def run_case() -> tuple[str, str]:
        listing = await registry.run_command("/tool list_files .")
        content = await registry.run_command("/tool read_file note.txt")
        return listing.content, content.content

    listing, content = asyncio.run(run_case())

    assert "note.txt" in listing
    assert content == "hello tools"


def test_filesystem_tools_block_paths_outside_root(tmp_path) -> None:
    registry = ToolRegistry(create_filesystem_tools(tmp_path))

    async def run_case() -> None:
        await registry.run_command("/tool read_file ../secret.txt")

    try:
        asyncio.run(run_case())
    except ToolError as exc:
        assert "outside the workspace" in str(exc)
    else:
        raise AssertionError("Expected ToolError")


def test_agent_loop_routes_tool_commands_to_registry(tmp_path) -> None:
    (tmp_path / "note.txt").write_text("hello from agent tool", encoding="utf-8")
    registry = ToolRegistry(create_filesystem_tools(tmp_path))
    agent = AgentLoop(AgentRunner(FakeProvider()), tools=registry)

    async def run_case() -> str:
        return await agent.ask("/tool read_file note.txt")

    assert asyncio.run(run_case()) == "hello from agent tool"
    assert agent.history == [
        {"role": "user", "content": "/tool read_file note.txt"},
        {"role": "assistant", "content": "hello from agent tool"},
    ]


def test_filesystem_tools_write_append_and_search(tmp_path) -> None:
    registry = ToolRegistry(create_filesystem_tools(tmp_path))

    async def run_case() -> tuple[str, str]:
        await registry.run_command("/tool write_file notes/todo.txt hello")
        await registry.run_command("/tool append_file notes/todo.txt \" world\"")
        search = await registry.run_command("/tool search_files world notes")
        content = await registry.run_command("/tool read_file notes/todo.txt")
        return search.content, content.content

    search, content = asyncio.run(run_case())

    assert content == "hello world"
    assert "notes\\todo.txt:1: hello world" in search or "notes/todo.txt:1: hello world" in search
