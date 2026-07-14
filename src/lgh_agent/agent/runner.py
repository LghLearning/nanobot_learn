from __future__ import annotations

from lgh_agent.providers.base import LLMProvider, Message


class AgentRunner:
    """Runs the model-facing part of the agent.

    Today it makes one provider call. Later this is where tool-calling loops
    will live.
    """

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    async def run(self, messages: list[Message]) -> str:
        response = await self.provider.complete(messages)
        return response.content
