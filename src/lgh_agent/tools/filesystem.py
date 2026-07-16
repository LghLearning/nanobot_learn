from __future__ import annotations

from pathlib import Path

from lgh_agent.errors import ToolError
from lgh_agent.tools.base import Tool, ToolResult


class ReadFileTool:
    name = "read_file"
    description = "Read a UTF-8 text file inside the tool root."

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()#统一绝对路径

    async def run(self, args: list[str]) -> ToolResult:#所有tool接口保持一致
        if len(args) != 1:
            raise ToolError("Usage: /tool read_file <path>")

        path = _resolve_inside_root(self.root, args[0])
        if not path.exists():
            raise ToolError(f"File does not exist: {args[0]}")
        if not path.is_file():
            raise ToolError(f"Path is not a file: {args[0]}")

        content = path.read_text(encoding="utf-8")#只读取文本 .py .md .txt
        return ToolResult(content=content)


class ListFilesTool:
    name = "list_files"
    description = "List files and directories inside the tool root."

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    async def run(self, args: list[str]) -> ToolResult:
        target_arg = args[0] if args else "."#默认根目录
        path = _resolve_inside_root(self.root, target_arg)
        if not path.exists():
            raise ToolError(f"Directory does not exist: {target_arg}")
        if not path.is_dir():
            raise ToolError(f"Path is not a directory: {target_arg}")

        items = sorted(path.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
        lines = []
        for item in items:
            suffix = "/" if item.is_dir() else ""
            lines.append(f"{item.name}{suffix}")
        return ToolResult(content="\n".join(lines) if lines else "(empty)")


def create_filesystem_tools(root: Path) -> list[Tool]:
    return [
        ListFilesTool(root),
        ReadFileTool(root),
    ]


def _resolve_inside_root(root: Path, user_path: str) -> Path:#把用户输入的路径转换成真实路径，并检查它是否仍然在 root 里面。
    path = (root / user_path).resolve()
    if path != root and root not in path.parents:
        raise ToolError("Path is outside the tool root.")
    return path
