from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ToolResult:
    """The normalized result returned by any tool."""

    content: str


class Tool(Protocol):
    """Common interface for tools.

    Every tool has a stable name and receives command arguments as strings.
    Later, model tool-calling can reuse the same idea with structured args.
    """

    name: str
    description: str

    async def run(self, args: list[str]) -> ToolResult:
        ...
