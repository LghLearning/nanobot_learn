from __future__ import annotations

import asyncio

import httpx

from lgh_agent.agent.loop import AgentLoop
from lgh_agent.agent.runner import AgentRunner
from lgh_agent.config import OpenAICompatibleConfig
from lgh_agent.providers.fake import FakeProvider
from lgh_agent.providers.openai_compat import OpenAICompatibleProvider


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
