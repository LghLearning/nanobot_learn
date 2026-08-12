from __future__ import annotations

import argparse
import asyncio

from lgh_agent.api.server import serve
from lgh_agent.errors import LghAgentError
from lgh_agent.runtime import build_agent
from lgh_agent.tools.base import ToolEvent


EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit"}


def _print_tool_event(event: ToolEvent) -> None:
    status = "ok" if event.ok else "error"
    detail = event.content_preview if event.ok else event.error
    print(f"[tool:{status}] {event.name} {event.arguments} -> {detail}")


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
        on_tool_event=_print_tool_event,
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
    parser.add_argument("--serve", action="store_true", help="Run the HTTP API server.")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP server host.")
    parser.add_argument("--port", type=int, default=8900, help="HTTP server port.")
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
        if args.serve:
            serve(
                host=args.host,
                port=args.port,
                use_real_provider=args.real,
                workspace=args.workspace,
                tool_root=args.tool_root,
            )
        else:
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
