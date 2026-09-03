from __future__ import annotations

from collections.abc import AsyncIterator
import json
from typing import Any

import httpx

from lgh_agent.config import OpenAICompatibleConfig
from lgh_agent.errors import (
    ProviderConnectionError,
    ProviderHTTPError,
    ProviderResponseError,
)
from lgh_agent.providers.base import LLMResponse, Message, ToolCall


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

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout_s)
        try:
            payload: dict[str, Any] = {
                "model": self.config.model,
                "messages": messages,
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            response = await client.post(
                f"{self.config.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return _extract_response(data)
        except httpx.ConnectError as exc:
            raise ProviderConnectionError(
                "Could not connect to the model provider. Check LGH_AGENT_BASE_URL and your proxy/network."
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderConnectionError(
                f"The model provider did not respond within {self.config.timeout_s} seconds."
            ) from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            body = exc.response.text[:300]
            raise ProviderHTTPError(
                f"Model provider returned HTTP {status}. Response: {body}"
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderConnectionError(f"Model provider request failed: {exc}") from exc
        finally:
            if self._owns_client:
                await client.aclose()

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout_s)
        try:
            payload: dict[str, Any] = {
                "model": self.config.model,
                "messages": messages,
                "stream": True,
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            async with client.stream(
                "POST",
                f"{self.config.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    chunk = _parse_stream_line(line)
                    if chunk is not None:
                        yield chunk
        except httpx.ConnectError as exc:
            raise ProviderConnectionError(
                "Could not connect to the model provider. Check LGH_AGENT_BASE_URL and your proxy/network."
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderConnectionError(
                f"The model provider did not respond within {self.config.timeout_s} seconds."
            ) from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            body = exc.response.text[:300]
            raise ProviderHTTPError(
                f"Model provider returned HTTP {status}. Response: {body}"
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderConnectionError(f"Model provider request failed: {exc}") from exc
        finally:
            if self._owns_client:
                await client.aclose()


def _extract_response(data: dict[str, Any]) -> LLMResponse:
    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderResponseError("Invalid chat completions response.") from exc

    content = message.get("content") or ""
    tool_calls = [_parse_tool_call(item) for item in message.get("tool_calls") or []]
    return LLMResponse(content=str(content), tool_calls=tool_calls)


def _parse_tool_call(item: dict[str, Any]) -> ToolCall:
    try:
        function = item["function"]
        raw_arguments = function.get("arguments") or "{}"
        arguments = json.loads(raw_arguments)
        if not isinstance(arguments, dict):
            raise TypeError("tool arguments must be an object")
        return ToolCall(
            id=str(item["id"]),
            name=str(function["name"]),
            arguments=arguments,
        )
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ProviderResponseError("Invalid tool call in provider response.") from exc


def _parse_stream_line(line: str) -> str | None:
    if not line.startswith("data: "):
        return None
    payload = line.removeprefix("data: ").strip()
    if payload == "[DONE]":
        return None
    try:
        data = json.loads(payload)
        delta = data["choices"][0].get("delta") or {}
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise ProviderResponseError("Invalid streaming chat completions response.") from exc
    content = delta.get("content")
    if content is None:
        return None
    return str(content)
