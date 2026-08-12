from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ToolResult:
    """The normalized result returned by any tool."""

    content: str


@dataclass(frozen=True, slots=True)
class ToolEvent:
    """A small trace record for one tool execution."""

    name: str
    arguments: dict[str, Any]
    content_preview: str
    ok: bool = True
    error: str | None = None


class Tool(Protocol):
    """Common interface for tools.

    A tool now supports two paths:
    - command path: user types `/tool read_file pyproject.toml`
    - model path: model sends structured JSON arguments
    """

    name: str
    description: str
    parameters: dict[str, Any]

    def parse_command_args(self, args: list[str]) -> dict[str, Any]:
        ...

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        ...
