from __future__ import annotations

from lgh_agent.providers.base import LLMResponse, Message


class FakeProvider:
    """A tiny provider used to prove the project wiring works.

    It lets us build and test the agent loop before using a real API key.
    """

    async def complete(self, messages: list[Message]) -> LLMResponse:
        last_user_message = ""
        for message in reversed(messages):
            if message.get("role") == "user":
                last_user_message = message.get("content", "")
                break
        return LLMResponse(content=f"Echo: {last_user_message}")
