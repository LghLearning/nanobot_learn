from __future__ import annotations

from lgh_agent.agent.runner import AgentRunner

#
# 依赖注入（Dependency Injection）
# AgentLoop 不知道怎么调用模型。
# 它只知道：
# "需要回复的时候，我找 Runner。"
#
from lgh_agent.providers.base import Message


class AgentLoop:#管理一场聊天,而不是管理整个 Agent
    """Handles one conversation session.

    This layer owns conversation history and calls AgentRunner for each turn.
    """

    def __init__(self, runner: AgentRunner) -> None:#初始化
        self.runner = runner
        self.history: list[Message] = []#记录整场聊天内容

    async def ask(self, text: str) -> str:
        user_message: Message = {"role": "user", "content": text}#把输入定义成message的形式
        self.history.append(user_message)#把历史（上下文）载入

        answer = await self.runner.run(self.history)#调用 Runner，Runner 每次都拿到整场聊天的历史，返回一个回答

        assistant_message: Message = {"role": "assistant", "content": answer} #包装回答成message的形式
        self.history.append(assistant_message)#把回答加入历史
        return answer

# 为什么要把 history 放在 AgentLoop，而不是 AgentRunner？
# 职责分离（Single Responsibility Principle）：
# AgentLoop：负责维护会话状态（聊天历史、未来也可能包括会话 ID、上下文裁剪等）。它知道“一场对话”是什么。
# AgentRunner：负责执行一次推理。它接收一组消息，调用模型，返回答案，不关心这些消息是不是来自同一场聊天。
# 因此，同一个 AgentRunner 可以被多个 AgentLoop 复用，每个 AgentLoop 都拥有各自独立的 history。会话状态和模型执行逻辑解耦。