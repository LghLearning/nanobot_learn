from __future__ import annotations

from collections.abc import AsyncIterator, Callable
import json

from lgh_agent.errors import ToolError
from lgh_agent.providers.base import LLMProvider, Message, ToolCall
from lgh_agent.tools import ToolRegistry
from lgh_agent.tools.base import ToolEvent


class AgentRunner:
    """Runs the model-facing part of the agent.

    Runner owns the model-tool-model loop. It also emits ToolEvent records so
    the CLI/API/WebUI layers can show what the agent actually did.
    """

    def __init__(self, provider: LLMProvider, *, max_tool_iterations: int = 5) -> None:
        self.provider = provider
        self.max_tool_iterations = max_tool_iterations

    async def run(
        self,
        messages: list[Message],
        tools: ToolRegistry | None = None,
        on_tool_event: Callable[[ToolEvent], None] | None = None,
    ) -> str:
        working_messages = [dict(message) for message in messages]
        tool_schemas = tools.openai_tool_schemas() if tools is not None else None

        for _iteration in range(self.max_tool_iterations + 1):
            response = await self.provider.complete(working_messages, tools=tool_schemas)
            if not response.tool_calls:
                return response.content
            if tools is None:
                raise ToolError("The model requested a tool, but no tools are configured.")

            working_messages.append(_assistant_tool_call_message(response.tool_calls))
            for tool_call in response.tool_calls:
                try:
                    tool_result = await tools.run_tool_call(tool_call.name, tool_call.arguments)
                except ToolError as exc:
                    _emit_tool_event(
                        on_tool_event,
                        ToolEvent(
                            name=tool_call.name,
                            arguments=tool_call.arguments,
                            content_preview="",
                            ok=False,
                            error=str(exc),
                        ),
                    )
                    raise

                _emit_tool_event(
                    on_tool_event,
                    ToolEvent(
                        name=tool_call.name,
                        arguments=tool_call.arguments,
                        content_preview=_preview(tool_result.content),
                    ),
                )
                working_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.name,
                        "content": tool_result.content,
                    }
                )

        raise ToolError("Tool calling did not finish before the iteration limit.")

    async def run_stream(
        self,
        messages: list[Message],
        tools: ToolRegistry | None = None,
        on_tool_event: Callable[[ToolEvent], None] | None = None,
    ) -> AsyncIterator[str]:
        """Stream a final answer when the provider can do native streaming.

        If tools are available, the first pass still uses complete() so the
        model can request tools. Once tool calls are resolved, the final answer
        is streamed with provider.stream().
        """

        working_messages = [dict(message) for message in messages]
        tool_schemas = tools.openai_tool_schemas() if tools is not None else None

        for _iteration in range(self.max_tool_iterations + 1):
            response = await self.provider.complete(working_messages, tools=tool_schemas)
            if not response.tool_calls:
                async for chunk in self.provider.stream(working_messages, tools=tool_schemas):
                    yield chunk
                return
            if tools is None:
                raise ToolError("The model requested a tool, but no tools are configured.")

            working_messages.append(_assistant_tool_call_message(response.tool_calls))
            for tool_call in response.tool_calls:
                tool_result = await tools.run_tool_call(tool_call.name, tool_call.arguments)
                _emit_tool_event(
                    on_tool_event,
                    ToolEvent(
                        name=tool_call.name,
                        arguments=tool_call.arguments,
                        content_preview=_preview(tool_result.content),
                    ),
                )
                working_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.name,
                        "content": tool_result.content,
                    }
                )

        raise ToolError("Tool calling did not finish before the iteration limit.")


def _assistant_tool_call_message(tool_calls: list[ToolCall]) -> Message:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.name,
                    "arguments": json.dumps(tool_call.arguments, ensure_ascii=False),
                },
            }
            for tool_call in tool_calls
        ],
    }


def _preview(content: str, limit: int = 180) -> str:
    content = content.replace("\r", "").strip()
    if len(content) <= limit:
        return content
    return content[:limit] + "...[truncated]"


def _emit_tool_event(callback: Callable[[ToolEvent], None] | None, event: ToolEvent) -> None:
    if callback is not None:
        callback(event)
