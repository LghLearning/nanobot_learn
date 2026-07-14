from __future__ import annotations

import argparse#命令行参数解析库
import asyncio

from lgh_agent.agent.loop import AgentLoop
from lgh_agent.agent.runner import AgentRunner
from lgh_agent.config import load_openai_compatible_config#配置层
from lgh_agent.providers.fake import FakeProvider
from lgh_agent.providers.openai_compat import OpenAICompatibleProvider


EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit"}


def build_agent(*, use_real_provider: bool = False) -> AgentLoop:# *后面的参数必须使用关键字,
    if use_real_provider:
        provider = OpenAICompatibleProvider(load_openai_compatible_config())
    else:
        provider = FakeProvider()
    return AgentLoop(AgentRunner(provider))


async def main(use_real_provider: bool = False) -> None:
    agent = build_agent(use_real_provider=use_real_provider)
    provider_name = "real provider" if use_real_provider else "fake provider"
    print(f"lgh_agent is ready using {provider_name}. Type 'exit' to quit.")

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

        answer = await agent.ask(text)
        print(f"Agent: {answer}")


def run() -> None:
    parser = argparse.ArgumentParser(description="Run lgh_agent.")#命令解析
    parser.add_argument(
        "--real",
        action="store_true",
        help="Use an OpenAI-compatible real model provider.",
    )
    args = parser.parse_args()
    asyncio.run(main(use_real_provider=args.real))


if __name__ == "__main__":
    run()
