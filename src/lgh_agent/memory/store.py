from __future__ import annotations

from pathlib import Path


class MemoryStore:
    """Stores long-term memory for the whole workspace.

    Session history answers "what happened in this chat?"
    Memory answers "what should the agent remember across chats?"
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.path = workspace / "memory" / "MEMORY.md"

    def read(self) -> str:
        if not self.path.exists():
            return ""
        return self.path.read_text(encoding="utf-8").strip()

    def add(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        prefix = "\n" if self.path.exists() and self.path.read_text(encoding="utf-8").strip() else ""
        with self.path.open("a", encoding="utf-8") as file:
            file.write(f"{prefix}- {text}\n")

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
