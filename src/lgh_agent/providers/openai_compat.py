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
            response = await client.post(#发送http请求：请求地址，请求头，请求体
                f"{self.config.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",#身份验证
                    "Content-Type": "application/json",#声明数据格式是 JSON
                },
                json={
                    "model": self.config.model,
                    "messages": messages,
                },
            )
            response.raise_for_status()
            data = response.json()
            return LLMResponse(content=_extract_content(data))#转换成统一格式
        finally:
            if self._owns_client:#清理资源
                await client.aclose()


def _extract_content(data: dict[str, Any]) -> str:#解析函数，
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Invalid chat completions response.") from exc
    return "" if content is None else str(content)
