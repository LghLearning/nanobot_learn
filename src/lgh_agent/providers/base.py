from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


Message = dict[str, Any]


@dataclass(slots=True)
class ToolCall:
    """A normalized request from the model to run one tool."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class LLMResponse:
    """A normalized response returned by any model provider."""

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMProvider(Protocol):
    """Common interface for model providers.

    Providers may receive tool schemas. If the model wants a tool, the provider
    returns normalized ToolCall objects instead of hiding vendor-specific JSON.
    """

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        ...
