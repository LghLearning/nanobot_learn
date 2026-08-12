from __future__ import annotations

import asyncio
import json
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from lgh_agent.errors import LghAgentError
from lgh_agent.runtime import build_agent
from lgh_agent.tools.base import ToolEvent
from lgh_agent.webui import WEBUI_HTML


class ApiSettings:
    def __init__(
        self,
        *,
        use_real_provider: bool,
        workspace: str | None,
        tool_root: str | None,
    ) -> None:
        self.use_real_provider = use_real_provider
        self.workspace = workspace
        self.tool_root = tool_root


def serve(
    *,
    host: str = "127.0.0.1",
    port: int = 8900,
    use_real_provider: bool = False,
    workspace: str | None = None,
    tool_root: str | None = None,
) -> None:
    settings = ApiSettings(
        use_real_provider=use_real_provider,
        workspace=workspace,
        tool_root=tool_root,
    )
    server = ThreadingHTTPServer((host, port), create_handler(settings))
    print(f"lgh_agent API server listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


def create_handler(settings: ApiSettings) -> type[BaseHTTPRequestHandler]:
    class LghAgentHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path in {"/", "/index.html"}:
                self._send_html(WEBUI_HTML)
                return
            if self.path == "/health":
                self._send_json({"status": "ok"})
                return
            if self.path == "/v1/models":
                self._send_json(
                    {
                        "object": "list",
                        "data": [
                            {
                                "id": "lgh-agent",
                                "object": "model",
                                "created": int(time.time()),
                                "owned_by": "lgh_agent",
                            }
                        ],
                    }
                )
                return
            self._send_json({"error": "not found"}, status=404)

        def do_POST(self) -> None:
            try:
                body = self._read_json()
                if self.path == "/chat":
                    self._handle_chat(body)
                    return
                if self.path == "/v1/chat/completions":
                    self._handle_chat_completions(body)
                    return
                self._send_json({"error": "not found"}, status=404)
            except LghAgentError as exc:
                self._send_json({"error": str(exc)}, status=400)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)

        def _handle_chat(self, body: dict[str, Any]) -> None:
            message = body.get("message")
            if not isinstance(message, str) or not message:
                raise ValueError("Request body must include a non-empty 'message'.")
            session = str(body.get("session") or "api")
            answer, events = _run_agent_turn(
                message,
                session=session,
                settings=settings,
                use_real_provider=bool(body.get("real", settings.use_real_provider)),
            )
            self._send_json(
                {
                    "message": answer,
                    "session": session,
                    "tool_events": [_tool_event_json(event) for event in events],
                }
            )

        def _handle_chat_completions(self, body: dict[str, Any]) -> None:
            messages = body.get("messages")
            if not isinstance(messages, list):
                raise ValueError("Request body must include 'messages' list.")
            text = _last_user_text(messages)
            session = str(body.get("session_id") or body.get("user") or "openai-api")
            answer, events = _run_agent_turn(
                text,
                session=session,
                settings=settings,
                use_real_provider=settings.use_real_provider,
            )
            self._send_json(_chat_completion_response(answer, events))

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            if not raw:
                return {}
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("JSON body must be an object.")
            return data

        def _send_json(self, payload: dict[str, Any], *, status: int = 200) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _send_html(self, html: str, *, status: int = 200) -> None:
            raw = html.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return LghAgentHandler


def _run_agent_turn(
    message: str,
    *,
    session: str,
    settings: ApiSettings,
    use_real_provider: bool,
) -> tuple[str, list[ToolEvent]]:
    events: list[ToolEvent] = []
    agent = build_agent(
        use_real_provider=use_real_provider,
        session_name=session,
        workspace=settings.workspace,
        tool_root=settings.tool_root,
        on_tool_event=events.append,
    )
    answer = asyncio.run(agent.ask(message))
    return answer, events


def _last_user_text(messages: list[Any]) -> str:
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, str) and content:
                return content
    raise ValueError("messages must contain at least one user text message.")


def _chat_completion_response(content: str, events: list[ToolEvent]) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "lgh-agent",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        "lgh_agent": {
            "tool_events": [_tool_event_json(event) for event in events],
        },
    }


def _tool_event_json(event: ToolEvent) -> dict[str, Any]:
    return {
        "name": event.name,
        "arguments": event.arguments,
        "content_preview": event.content_preview,
        "ok": event.ok,
        "error": event.error,
    }
