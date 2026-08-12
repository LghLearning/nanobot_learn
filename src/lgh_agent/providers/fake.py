from __future__ import annotations

from typing import Any

from lgh_agent.providers.base import LLMResponse, Message


class FakeProvider:
    """A tiny provider used to prove the project wiring works."""

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        last_user_message = ""
        for message in reversed(messages):
            if message.get("role") == "user":
                last_user_message = str(message.get("content", ""))
                break
        return LLMResponse(content=f"Echo: {last_user_message}")
