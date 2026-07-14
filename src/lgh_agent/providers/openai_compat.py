from __future__ import annotations

from typing import Any

import httpx

from lgh_agent.config import OpenAICompatibleConfig
from lgh_agent.providers.base import LLMResponse, Message


class OpenAICompatibleProvider:
    """Provider for APIs that implement OpenAI's chat completions format."""

    def __init__(
        self,
        config: OpenAICompatibleConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self._client = client
        self._owns_client = client is None

    async def complete(self, messages: list[Message]) -> LLMResponse:
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout_s)
        try:
            response = await client.post(
                f"{self.config.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.config.model,
                    "messages": messages,
                },
            )
            response.raise_for_status()
            data = response.json()
            return LLMResponse(content=_extract_content(data))
        finally:
            if self._owns_client:
                await client.aclose()


def _extract_content(data: dict[str, Any]) -> str:
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Invalid chat completions response.") from exc
    return "" if content is None else str(content)
