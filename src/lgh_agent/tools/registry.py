from __future__ import annotations

import shlex #安全解析命令字符串

from lgh_agent.errors import ToolError
from lgh_agent.tools.base import Tool, ToolResult


class ToolRegistry:
    """Stores tools and dispatches `/tool ...` commands."""

    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ToolError(f"Tool '{tool.name}' is already registered.")
        self._tools[tool.name] = tool

    def describe_tools(self) -> str:
        if not self._tools:
            return "No tools are available."
        lines = ["Available tools:"]
        for name in sorted(self._tools):
            tool = self._tools[name]
            lines.append(f"- {tool.name}: {tool.description}")
        return "\n".join(lines)

    async def run_command(self, text: str) -> ToolResult:
        """Parse and run a command like `/tool read_file pyproject.toml`."""

        try:
            parts = shlex.split(text)
        except ValueError as exc:
            raise ToolError(f"Invalid tool command: {exc}") from exc

        if not parts:
            raise ToolError("Empty tool command.")
        if parts[0] == "/tools":
            return ToolResult(self.describe_tools())
        if parts[0] != "/tool":
            raise ToolError("Tool commands must start with /tool.")
        if len(parts) < 2:
            raise ToolError("Usage: /tool <tool_name> [args...]")

        tool_name = parts[1]
        tool = self._tools.get(tool_name)
        if tool is None:
            raise ToolError(f"Unknown tool '{tool_name}'.\n{self.describe_tools()}")
        return await tool.run(parts[2:])
