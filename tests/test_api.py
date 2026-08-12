from __future__ import annotations

import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread

from lgh_agent.api.server import ApiSettings, create_handler


def test_health_endpoint(tmp_path) -> None:
    server, thread = _start_test_server(tmp_path)
    try:
        status, body = _request_json(server, "GET", "/health")
    finally:
        _stop_test_server(server, thread)

    assert status == 200
    assert body == {"status": "ok"}


def test_webui_root_serves_html(tmp_path) -> None:
    server, thread = _start_test_server(tmp_path)
    try:
        status, body, content_type = _request_text(server, "GET", "/")
    finally:
        _stop_test_server(server, thread)

    assert status == 200
    assert "text/html" in content_type
    assert "lgh_agent" in body
    assert 'fetch("/chat"' in body


def test_chat_endpoint_returns_agent_response_and_tool_events(tmp_path) -> None:
    (tmp_path / "note.txt").write_text("hello api", encoding="utf-8")
    server, thread = _start_test_server(tmp_path)
    try:
        status, body = _request_json(
            server,
            "POST",
            "/chat",
            {"message": "/tool read_file note.txt", "session": "api-test"},
        )
    finally:
        _stop_test_server(server, thread)

    assert status == 200
    assert body["message"] == "hello api"
    assert body["session"] == "api-test"
    assert body["tool_events"][0]["name"] == "manual"


def test_openai_compatible_chat_completions_endpoint(tmp_path) -> None:
    server, thread = _start_test_server(tmp_path)
    try:
        status, body = _request_json(
            server,
            "POST",
            "/v1/chat/completions",
            {
                "messages": [
                    {"role": "user", "content": "hello"},
                ],
                "session_id": "openai-test",
            },
        )
    finally:
        _stop_test_server(server, thread)

    assert status == 200
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["content"] == "Echo: hello"


def _start_test_server(tmp_path):
    settings = ApiSettings(use_real_provider=False, workspace=str(tmp_path / "workspace"), tool_root=str(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(settings))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _stop_test_server(server, thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def _request_json(server, method: str, path: str, payload: dict | None = None):
    host, port = server.server_address
    conn = HTTPConnection(host, port, timeout=5)
    try:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {}
        if body is not None:
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        raw = response.read().decode("utf-8")
        return response.status, json.loads(raw)
    finally:
        conn.close()


def _request_text(server, method: str, path: str):
    host, port = server.server_address
    conn = HTTPConnection(host, port, timeout=5)
    try:
        conn.request(method, path)
        response = conn.getresponse()
        raw = response.read().decode("utf-8")
        return response.status, raw, response.getheader("Content-Type") or ""
    finally:
        conn.close()
