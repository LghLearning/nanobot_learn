from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from lgh_agent.agent.loop import AgentLoop
from lgh_agent.agent.runner import AgentRunner
from lgh_agent.config import load_app_config, load_openai_compatible_config
from lgh_agent.providers.fake import FakeProvider
from lgh_agent.providers.openai_compat import OpenAICompatibleProvider
from lgh_agent.session import SessionStore
from lgh_agent.tools import ToolRegistry, create_filesystem_tools
from lgh_agent.tools.base import ToolEvent


def build_agent(
    *,
    use_real_provider: bool = False,
    session_name: str = "default",
    workspace: str | None = None,
    tool_root: str | None = None,
    on_tool_event: Callable[[ToolEvent], None] | None = None,
) -> AgentLoop:
    """Create a fully wired AgentLoop for CLI, API, or tests."""

    if use_real_provider:
        provider = OpenAICompatibleProvider(load_openai_compatible_config())
    else:
        provider = FakeProvider()

    app_config = load_app_config(workspace)
    session_store = SessionStore(app_config.workspace, session_name=session_name)

    tool_root_path = Path(tool_root).expanduser() if tool_root else Path.cwd()
    tool_registry = ToolRegistry(create_filesystem_tools(tool_root_path))

    return AgentLoop(
        AgentRunner(provider),
        history=session_store.load_history(),
        on_message=session_store.append_message,
        on_tool_event=on_tool_event,
        tools=tool_registry,
    )
