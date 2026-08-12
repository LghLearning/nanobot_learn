from __future__ import annotations

from pathlib import Path
from typing import Any

from lgh_agent.errors import ToolError
from lgh_agent.tools.base import Tool, ToolResult


MAX_READ_CHARS = 20_000
MAX_WRITE_CHARS = 50_000


class ReadFileTool:
    name = "read_file"
    description = "Read a UTF-8 text file inside the workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to read, relative to workspace."},
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def parse_command_args(self, args: list[str]) -> dict[str, Any]:
        if len(args) != 1:
            raise ToolError("Usage: /tool read_file <path>")
        return {"path": args[0]}

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        path = _resolve_file_for_read(self.root, _string_arg(arguments, "path"))
        content = path.read_text(encoding="utf-8")
        if len(content) > MAX_READ_CHARS:
            content = content[:MAX_READ_CHARS] + "\n...[truncated]"
        return ToolResult(content=content)


class ListFilesTool:
    name = "list_files"
    description = "List files and directories inside the workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory to list, relative to workspace.",
                "default": ".",
            },
        },
        "additionalProperties": False,
    }

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def parse_command_args(self, args: list[str]) -> dict[str, Any]:
        return {"path": args[0] if args else "."}

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        target_arg = str(arguments.get("path") or ".")
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


class WriteFileTool:
    name = "write_file"
    description = "Create or replace a UTF-8 text file inside the workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to write, relative to workspace."},
            "content": {"type": "string", "description": "Full file content to write."},
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    }

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def parse_command_args(self, args: list[str]) -> dict[str, Any]:
        if len(args) < 2:
            raise ToolError("Usage: /tool write_file <path> <content>")
        return {"path": args[0], "content": " ".join(args[1:])}

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        path = _resolve_file_for_write(self.root, _string_arg(arguments, "path"))
        content = _string_arg(arguments, "content")
        _validate_write_content(content)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ToolResult(content=f"Wrote {len(content)} characters to {path.relative_to(self.root)}")


class AppendFileTool:
    name = "append_file"
    description = "Append UTF-8 text to a file inside the workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to append to, relative to workspace."},
            "content": {"type": "string", "description": "Text to append."},
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    }

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def parse_command_args(self, args: list[str]) -> dict[str, Any]:
        if len(args) < 2:
            raise ToolError("Usage: /tool append_file <path> <content>")
        return {"path": args[0], "content": " ".join(args[1:])}

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        path = _resolve_file_for_write(self.root, _string_arg(arguments, "path"))
        content = _string_arg(arguments, "content")
        _validate_write_content(content)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(content)
        return ToolResult(content=f"Appended {len(content)} characters to {path.relative_to(self.root)}")


class SearchFilesTool:
    name = "search_files"
    description = "Search UTF-8 text files inside the workspace for a substring."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Text to search for."},
            "path": {
                "type": "string",
                "description": "Directory to search, relative to workspace.",
                "default": ".",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def parse_command_args(self, args: list[str]) -> dict[str, Any]:
        if not args:
            raise ToolError("Usage: /tool search_files <query> [path]")
        return {"query": args[0], "path": args[1] if len(args) > 1 else "."}

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        query = _string_arg(arguments, "query")
        start = _resolve_inside_root(self.root, str(arguments.get("path") or "."))
        if not start.exists():
            raise ToolError(f"Search path does not exist: {arguments.get('path') or '.'}")
        if start.is_file():
            files = [start]
        else:
            files = [path for path in start.rglob("*") if path.is_file()]

        matches: list[str] = []
        for path in files[:500]:
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for line_number, line in enumerate(lines, start=1):
                if query in line:
                    relative = path.relative_to(self.root)
                    matches.append(f"{relative}:{line_number}: {line}")
                    if len(matches) >= 50:
                        return ToolResult(content="\n".join(matches))
        return ToolResult(content="\n".join(matches) if matches else "No matches.")


def create_filesystem_tools(root: Path) -> list[Tool]:
    return [
        AppendFileTool(root),
        ListFilesTool(root),
        ReadFileTool(root),
        SearchFilesTool(root),
        WriteFileTool(root),
    ]


def _string_arg(arguments: dict[str, Any], name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or value == "":
        raise ToolError(f"Missing or invalid '{name}' argument.")
    return value


def _validate_write_content(content: str) -> None:
    if len(content) > MAX_WRITE_CHARS:
        raise ToolError(f"Content is too large. Limit is {MAX_WRITE_CHARS} characters.")


def _resolve_file_for_read(root: Path, user_path: str) -> Path:
    path = _resolve_inside_root(root, user_path)
    if not path.exists():
        raise ToolError(f"File does not exist: {user_path}")
    if not path.is_file():
        raise ToolError(f"Path is not a file: {user_path}")
    return path


def _resolve_file_for_write(root: Path, user_path: str) -> Path:
    path = _resolve_inside_root(root, user_path)
    if path.exists() and not path.is_file():
        raise ToolError(f"Path is not a file: {user_path}")
    return path


def _resolve_inside_root(root: Path, user_path: str) -> Path:
    path = (root / user_path).resolve()
    if path != root and root not in path.parents:
        raise ToolError("Path is outside the workspace.")
    return path
