from __future__ import annotations

from collections.abc import Callable #类型注解

from lgh_agent.agent.runner import AgentRunner
from lgh_agent.providers.base import Message


class AgentLoop:
    """Handles one conversation session.

    This layer owns conversation history and calls AgentRunner for each turn.
    """

    def __init__(
        self,
        runner: AgentRunner,
        *,
        history: list[Message] | None = None,
        on_message: Callable[[Message], None] | None = None,
    ) -> None:
        self.runner = runner
        self.history: list[Message] = list(history or [])
        self._on_message = on_message

    async def ask(self, text: str) -> str:
        user_message: Message = {"role": "user", "content": text}
        self._append_message(user_message)

        answer = await self.runner.run(self.history)

        assistant_message: Message = {"role": "assistant", "content": answer}
        self._append_message(assistant_message)
        return answer

    def _append_message(self, message: Message) -> None:
        self.history.append(message)
        if self._on_message is not None:
            self._on_message(message)
