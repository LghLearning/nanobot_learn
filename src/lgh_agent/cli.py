from __future__ import annotations

import argparse
import asyncio

from lgh_agent.api.server import serve
from lgh_agent.bus import MessageBus
from lgh_agent.channels import CLIChannel
from lgh_agent.errors import LghAgentError
from lgh_agent.gateway import serve_gateway


async def main(
    use_real_provider: bool = False,
    *,
    session_name: str = "default",
    workspace: str | None = None,
    tool_root: str | None = None,
    stream: bool = False,
) -> None:
    bus = MessageBus(
        default_use_real_provider=use_real_provider,
        workspace=workspace,
        tool_root=tool_root,
    )
    channel = CLIChannel(
        bus,
        session_name=session_name,
        use_real_provider=use_real_provider,
        stream=stream,
    )
    await channel.run()


def run() -> None:
    parser = argparse.ArgumentParser(description="Run lgh_agent.")
    parser.add_argument("--serve", action="store_true", help="Run the HTTP API server.")
    parser.add_argument(
        "--gateway",
        action="store_true",
        help="Run the HTTP API server plus background automation.",
    )
    parser.add_argument("--stream", action="store_true", help="Stream CLI responses in chunks.")
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
        if args.gateway:
            serve_gateway(
                host=args.host,
                port=args.port,
                use_real_provider=args.real,
                workspace=args.workspace,
                tool_root=args.tool_root,
            )
        elif args.serve:
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
                    stream=args.stream,
                )
            )
    except LghAgentError as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    run()
