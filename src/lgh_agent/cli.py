from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from lgh_agent.agent.loop import AgentLoop
from lgh_agent.agent.runner import AgentRunner
from lgh_agent.config import load_app_config, load_openai_compatible_config
from lgh_agent.errors import LghAgentError
from lgh_agent.providers.fake import FakeProvider
from lgh_agent.providers.openai_compat import OpenAICompatibleProvider
from lgh_agent.session import SessionStore
from lgh_agent.tools import ToolRegistry, create_filesystem_tools


EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit"}


def build_agent(
    *,
    use_real_provider: bool = False,
    session_name: str = "default",
    workspace: str | None = None,
    tool_root: str | None = None,
) -> AgentLoop:
    if use_real_provider:
        provider = OpenAICompatibleProvider(load_openai_compatible_config())
    else:
        provider = FakeProvider()

    app_config = load_app_config(workspace)
    session_store = SessionStore(app_config.workspace, session_name=session_name)


    tool_root_path = Path(tool_root).expanduser() if tool_root else Path.cwd()#工具目录
    tool_registry = ToolRegistry(create_filesystem_tools(tool_root_path))#创建工具

    return AgentLoop(
        AgentRunner(provider),
        history=session_store.load_history(),
        on_message=session_store.append_message,
        tools=tool_registry,
    )


async def main(
    use_real_provider: bool = False,
    *,
    session_name: str = "default",
    workspace: str | None = None,
    tool_root: str | None = None,
) -> None:
    agent = build_agent(
        use_real_provider=use_real_provider,
        session_name=session_name,
        workspace=workspace,
        tool_root=tool_root,
    )
    provider_name = "real provider" if use_real_provider else "fake provider"
    print(
        f"lgh_agent is ready using {provider_name} "
        f"in session '{session_name}'. Type 'exit' to quit."
    )
    print("Try '/tools' or '/tool list_files .' to inspect the tool layer.")

    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not text:
            continue
        if text.lower() in EXIT_COMMANDS:
            break

        try:
            answer = await agent.ask(text)
        except LghAgentError as exc:
            print(f"Error: {exc}")
            continue
        print(f"Agent: {answer}")


def run() -> None:
    parser = argparse.ArgumentParser(description="Run lgh_agent.")
    parser.add_argument(
        "--real",
        action="store_true",
        help="Use an OpenAI-compatible real model provider.",
    )
    parser.add_argument(
        "--session",
        default="default",
        help="Conversation session name. Defaults to 'default'.",
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Directory used to store sessions. Defaults to .lgh_agent in the project root.",
    )
    parser.add_argument(
        "--tool-root",
        default=None,
        help="Directory filesystem tools can access. Defaults to the current directory.",
    )
    args = parser.parse_args()
    try:
        asyncio.run(
            main(
                use_real_provider=args.real,
                session_name=args.session,
                workspace=args.workspace,
                tool_root=args.tool_root,
            )
        )
    except LghAgentError as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    run()
