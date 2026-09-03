from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from lgh_agent.automation.store import AutomationStore
from lgh_agent.bus import InboundMessage, MessageBus, OutboundMessage
from lgh_agent.channels import ChannelManager, WebhookAuthError
from lgh_agent.config import load_app_config
from lgh_agent.errors import LghAgentError
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
    server = make_server(host=host, port=port, settings=settings)
    print(f"lgh_agent API server listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


def make_server(
    *,
    host: str,
    port: int,
    settings: ApiSettings,
) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), create_handler(settings))


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
            if self.path == "/jobs":
                self._send_json({"jobs": _jobs_json(settings)})
                return
            if self.path == "/channels":
                self._send_json({"channels": _channels_json(settings)})
                return
            self._send_json({"error": "not found"}, status=404)

        def do_POST(self) -> None:
            try:
                body = self._read_json()
                if self.path == "/chat":
                    self._handle_chat(body)
                    return
                if self.path == "/chat/stream":
                    self._handle_chat_stream(body)
                    return
                if self.path == "/v1/chat/completions":
                    self._handle_chat_completions(body)
                    return
                if self.path.startswith("/webhooks/"):
                    self._handle_webhook(body)
                    return
                self._send_json({"error": "not found"}, status=404)
            except WebhookAuthError as exc:
                self._send_json({"error": str(exc)}, status=401)
            except LghAgentError as exc:
                self._send_json({"error": str(exc)}, status=400)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)

        def _handle_chat(self, body: dict[str, Any]) -> None:
            message = body.get("message")
            if not isinstance(message, str) or not message:
                raise ValueError("Request body must include a non-empty 'message'.")
            session = str(body.get("session") or "api")
            outbound = _run_bus_turn(
                InboundMessage(
                    content=message,
                    session=session,
                    use_real_provider=bool(body.get("real", settings.use_real_provider)),
                ),
                settings=settings,
            )
            self._send_json(
                {
                    "message": outbound.content,
                    "session": outbound.session,
                    "tool_events": [_tool_event_json(event) for event in outbound.tool_events],
                }
            )

        def _handle_chat_stream(self, body: dict[str, Any]) -> None:
            message = body.get("message")
            if not isinstance(message, str) or not message:
                raise ValueError("Request body must include a non-empty 'message'.")
            session = str(body.get("session") or "api")
            self._send_sse_headers()
            try:
                for item in _collect_bus_stream(
                    InboundMessage(
                        content=message,
                        session=session,
                        use_real_provider=bool(body.get("real", settings.use_real_provider)),
                    ),
                    settings=settings,
                ):
                    if isinstance(item, str):
                        self._write_sse({"type": "delta", "delta": item})
                    else:
                        self._write_sse(
                            {
                                "type": "done",
                                "session": item.session,
                                "tool_events": [
                                    _tool_event_json(event) for event in item.tool_events
                                ],
                            }
                        )
            except LghAgentError as exc:
                self._write_sse({"type": "error", "error": str(exc)})
            finally:
                self.close_connection = True

        def _handle_chat_completions(self, body: dict[str, Any]) -> None:
            messages = body.get("messages")
            if not isinstance(messages, list):
                raise ValueError("Request body must include 'messages' list.")
            text = _last_user_text(messages)
            session = str(body.get("session_id") or body.get("user") or "openai-api")
            outbound = _run_bus_turn(
                InboundMessage(
                    content=text,
                    session=session,
                    use_real_provider=settings.use_real_provider,
                ),
                settings=settings,
            )
            self._send_json(_chat_completion_response(outbound.content, outbound.tool_events))

        def _handle_webhook(self, body: dict[str, Any]) -> None:
            channel_name = self.path.removeprefix("/webhooks/").strip("/")
            if not channel_name:
                raise ValueError("Webhook path must include a channel name.")
            outbound = _run_webhook_turn(
                channel_name,
                body,
                authorization_header=self.headers.get("Authorization"),
                settings=settings,
            )
            self._send_json(
                {
                    "message": outbound.content,
                    "session": outbound.session,
                    "channel": channel_name,
                    "tool_events": [_tool_event_json(event) for event in outbound.tool_events],
                }
            )

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

        def _send_sse_headers(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()

        def _write_sse(self, payload: dict[str, Any]) -> None:
            raw = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
            self.wfile.write(raw)
            self.wfile.flush()

        def log_message(self, format: str, *args: Any) -> None:
            return

    return LghAgentHandler


def _build_bus(settings: ApiSettings) -> MessageBus:
    return MessageBus(
        default_use_real_provider=settings.use_real_provider,
        workspace=settings.workspace,
        tool_root=settings.tool_root,
    )


def _build_channel_manager(settings: ApiSettings) -> ChannelManager:
    app_config = load_app_config(settings.workspace)
    return ChannelManager(bus=_build_bus(settings), app_config=app_config)


def _channels_json(settings: ApiSettings) -> list[dict[str, object]]:
    return _build_channel_manager(settings).describe()


def _jobs_json(settings: ApiSettings) -> list[dict[str, object]]:
    app_config = load_app_config(settings.workspace)
    return [job.to_dict() for job in AutomationStore(app_config.workspace).list_jobs()]


def _run_bus_turn(message: InboundMessage, *, settings: ApiSettings) -> OutboundMessage:
    return asyncio.run(_build_bus(settings).submit(message))


def _run_webhook_turn(
    channel_name: str,
    body: dict[str, Any],
    *,
    authorization_header: str | None,
    settings: ApiSettings,
) -> OutboundMessage:
    async def run() -> OutboundMessage:
        channel = _build_channel_manager(settings).get(channel_name)
        return await channel.handle(
            body,
            authorization_header=authorization_header,
            use_real_provider=settings.use_real_provider,
        )

    return asyncio.run(run())


def _collect_bus_stream(
    message: InboundMessage,
    *,
    settings: ApiSettings,
) -> list[str | OutboundMessage]:
    async def collect() -> list[str | OutboundMessage]:
        return [item async for item in _build_bus(settings).submit_stream(message)]

    return asyncio.run(collect())


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
