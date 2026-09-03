from __future__ import annotations

from dataclasses import dataclass

from lgh_agent.providers.base import Message


@dataclass(frozen=True, slots=True)
class CompactionResult:
    messages: list[Message]
    compacted: bool


def compact_history(
    history: list[Message],
    *,
    keep_recent: int = 20,
    summary_message_limit: int = 12,
) -> CompactionResult:
    """Return model-facing history with old turns summarized.

    This is deterministic compaction: it does not call an LLM yet. The session
    JSONL remains complete on disk; only the prompt context is shortened.
    """

    if keep_recent <= 0 or len(history) <= keep_recent:
        return CompactionResult(messages=list(history), compacted=False)

    old_messages = history[:-keep_recent]
    recent_messages = history[-keep_recent:]
    summary = _summarize_messages(old_messages, limit=summary_message_limit)
    summary_message: Message = {
        "role": "system",
        "content": (
            "Summary of earlier conversation, compressed to save context:\n"
            f"{summary}"
        ),
    }
    return CompactionResult(messages=[summary_message, *recent_messages], compacted=True)


def _summarize_messages(messages: list[Message], *, limit: int) -> str:
    selected = messages[-limit:] if limit > 0 else []
    if not selected:
        return "(Earlier messages were omitted.)"

    lines: list[str] = []
    omitted = len(messages) - len(selected)
    if omitted > 0:
        lines.append(f"- {omitted} older message(s) omitted.")
    for message in selected:
        role = str(message.get("role", "unknown"))
        content = str(message.get("content", "")).replace("\r", "").replace("\n", " ")
        if len(content) > 160:
            content = content[:160] + "...[truncated]"
        lines.append(f"- {role}: {content}")
    return "\n".join(lines)
