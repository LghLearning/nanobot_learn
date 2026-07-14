from __future__ import annotations

from dataclasses import dataclass#用于快速创建数据类
from typing import Protocol


Message = dict[str, str]


@dataclass(slots=True) #slots=True可以节省内存，禁止动态添加属性
class LLMResponse:#统一格式，
    """A normalized response returned by any model provider."""

    content: str


class LLMProvider(Protocol):#接口
    """Common interface for model providers.

    AgentRunner depends on this interface, not on a concrete model vendor.
    """

    async def complete(self, messages: list[Message]) -> LLMResponse:#规定所有模型必须提供complete方法，返回LLMResponse对象
        ...
