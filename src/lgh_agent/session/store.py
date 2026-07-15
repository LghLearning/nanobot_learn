from __future__ import annotations

import json
import re
from pathlib import Path

from lgh_agent.errors import ConfigError
from lgh_agent.providers.base import Message


_SESSION_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


class SessionStore:
    """Persist one chat session as JSONL."""

    def __init__(self, workspace: Path, session_name: str = "default") -> None:
        if not _SESSION_NAME_PATTERN.fullmatch(session_name):
            raise ConfigError("Session name may only contain letters, numbers, '.', '_' and '-'.")
        self.workspace = workspace
        self.session_name = session_name
        self.path = workspace / "sessions" / f"{session_name}.jsonl"

    def load_history(self) -> list[Message]:#从磁盘恢复会话
        if not self.path.exists():
            return []

        history: list[Message] = []
        for line_number, raw_line in enumerate(#记录行数，方便报错
            self.path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not raw_line.strip():
                continue
            try:
                item = json.loads(raw_line)#处理成字典格式
            except json.JSONDecodeError as exc:
                raise ConfigError(
                    f"Session file {self.path} has invalid JSON on line {line_number}."
                ) from exc
            if isinstance(item, dict) and isinstance(item.get("role"), str):#检查是否是字典格式，并且role是否是字符串
                history.append({"role": str(item["role"]), "content": str(item.get("content", ""))})
        return history

    def append_message(self, message: Message) -> None:#将新消息追加到会话文件
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(message, ensure_ascii=False) + "\n")
