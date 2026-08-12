from __future__ import annotations

import asyncio

import httpx

from lgh_agent.agent.loop import AgentLoop
from lgh_agent.agent.runner import AgentRunner
from lgh_agent.config import OpenAICompatibleConfig
from lgh_agent.errors import ProviderConnectionError, ProviderHTTPError, ProviderResponseError
from lgh_agent.providers.base import LLMResponse, Message, ToolCall
from lgh_agent.providers.fake import FakeProvider
from lgh_agent.providers.openai_compat import OpenAICompatibleProvider
from lgh_agent.tools import ToolRegistry, create_filesystem_tools


def test_agent_loop_returns_fake_provider_response() -> None:
    async def run_case() -> str:
        agent = AgentLoop(AgentRunner(FakeProvider()))
        return await agent.ask("hello")

    assert asyncio.run(run_case()) == "Echo: hello"


def test_agent_loop_stores_history() -> None:
    async def run_case() -> list[dict[str, str]]:
        agent = AgentLoop(AgentRunner(FakeProvider()))
        await agent.ask("hello")
        return agent.history

    history = asyncio.run(run_case())

    assert history == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "Echo: hello"},
    ]


def test_openai_compatible_provider_uses_chat_completions() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["payload"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "real response",
                        }
                    }
                ]
            },
        )

    async def run_case() -> str:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            provider = OpenAICompatibleProvider(
                OpenAICompatibleConfig(
                    api_key="test-key",
                    base_url="https://example.test/v1",
                    model="test-model",
                ),
                client=client,
            )
            response = await provider.complete([{"role": "user", "content": "hello"}])
            return response.content

    assert asyncio.run(run_case()) == "real response"
    assert captured["url"] == "https://example.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-key"
    assert '"model":"test-model"' in str(captured["payload"]).replace(" ", "")


def test_openai_compatible_provider_sends_tools_and_parses_tool_calls() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "read_file",
                                        "arguments": "{\"path\":\"note.txt\"}",
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    async def run_case() -> LLMResponse:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            provider = OpenAICompatibleProvider(
                OpenAICompatibleConfig(
                    api_key="test-key",
                    base_url="https://example.test/v1",
                    model="test-model",
                ),
                client=client,
            )
            return await provider.complete(
                [{"role": "user", "content": "read note"}],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "description": "Read file",
                            "parameters": {"type": "object"},
                        },
                    }
                ],
            )

    response = asyncio.run(run_case())

    assert '"tools"' in str(captured["payload"])
    assert response.tool_calls == [
        ToolCall(id="call_1", name="read_file", arguments={"path": "note.txt"})
    ]


def test_openai_compatible_provider_wraps_http_errors() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad key")

    async def run_case() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            provider = OpenAICompatibleProvider(
                OpenAICompatibleConfig(
                    api_key="test-key",
                    base_url="https://example.test/v1",
                    model="test-model",
                ),
                client=client,
            )
            await provider.complete([{"role": "user", "content": "hello"}])

    try:
        asyncio.run(run_case())
    except ProviderHTTPError as exc:
        assert "HTTP 401" in str(exc)
    else:
        raise AssertionError("Expected ProviderHTTPError")


def test_openai_compatible_provider_wraps_connection_errors() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down")

    async def run_case() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            provider = OpenAICompatibleProvider(
                OpenAICompatibleConfig(
                    api_key="test-key",
                    base_url="https://example.test/v1",
                    model="test-model",
                ),
                client=client,
            )
            await provider.complete([{"role": "user", "content": "hello"}])

    try:
        asyncio.run(run_case())
    except ProviderConnectionError as exc:
        assert "Could not connect" in str(exc)
    else:
        raise AssertionError("Expected ProviderConnectionError")


def test_openai_compatible_provider_wraps_invalid_response_shape() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    async def run_case() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            provider = OpenAICompatibleProvider(
                OpenAICompatibleConfig(
                    api_key="test-key",
                    base_url="https://example.test/v1",
                    model="test-model",
                ),
                client=client,
            )
            await provider.complete([{"role": "user", "content": "hello"}])

    try:
        asyncio.run(run_case())
    except ProviderResponseError as exc:
        assert "Invalid chat completions response" in str(exc)
    else:
        raise AssertionError("Expected ProviderResponseError")


def test_agent_runner_executes_model_tool_calls(tmp_path) -> None:
    (tmp_path / "note.txt").write_text("tool result text", encoding="utf-8")

    class ScriptedToolProvider:
        def __init__(self) -> None:
            self.calls = 0

        async def complete(
            self,
            messages: list[Message],
            tools: list[dict] | None = None,
        ) -> LLMResponse:
            self.calls += 1
            if self.calls == 1:
                assert tools
                return LLMResponse(
                    tool_calls=[
                        ToolCall(
                            id="call_1",
                            name="read_file",
                            arguments={"path": "note.txt"},
                        )
                    ]
                )
            assert messages[-1]["role"] == "tool"
            assert messages[-1]["content"] == "tool result text"
            return LLMResponse(content="I read: tool result text")

    provider = ScriptedToolProvider()
    runner = AgentRunner(provider)
    registry = ToolRegistry(create_filesystem_tools(tmp_path))
    events = []

    async def run_case() -> str:
        return await runner.run(
            [{"role": "user", "content": "read note.txt"}],
            tools=registry,
            on_tool_event=events.append,
        )

    assert asyncio.run(run_case()) == "I read: tool result text"
    assert provider.calls == 2
    assert len(events) == 1
    assert events[0].name == "read_file"
    assert events[0].arguments == {"path": "note.txt"}
