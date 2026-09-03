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
    assert 'fetch("/chat/stream"' in body


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


def test_chat_stream_endpoint_returns_sse_chunks(tmp_path) -> None:
    server, thread = _start_test_server(tmp_path)
    try:
        status, body, content_type = _request_text(
            server,
            "POST",
            "/chat/stream",
            {"message": "hello stream", "session": "stream-test"},
        )
    finally:
        _stop_test_server(server, thread)

    assert status == 200
    assert "text/event-stream" in content_type
    assert '"type": "delta"' in body
    assert _join_sse_deltas(body) == "Echo: hello stream"
    assert '"type": "done"' in body


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


def test_jobs_endpoint_lists_automation_jobs(tmp_path) -> None:
    server, thread = _start_test_server(tmp_path)
    try:
        _request_json(
            server,
            "POST",
            "/chat",
            {"message": "/remind 5m check gateway", "session": "api-jobs"},
        )
        status, body = _request_json(server, "GET", "/jobs")
    finally:
        _stop_test_server(server, thread)

    assert status == 200
    assert body["jobs"][0]["session"] == "api-jobs"
    assert body["jobs"][0]["prompt"] == "check gateway"


def test_webhook_endpoint_returns_agent_response(tmp_path) -> None:
    server, thread = _start_test_server(tmp_path)
    try:
        status, body = _request_json(
            server,
            "POST",
            "/webhooks/default",
            {"message": "hello webhook api", "session": "webhook-user"},
        )
    finally:
        _stop_test_server(server, thread)

    assert status == 200
    assert body["message"] == "Echo: hello webhook api"
    assert body["session"] == "webhook-user"
    assert body["channel"] == "default"


def test_webhook_endpoint_rejects_invalid_token(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LGH_AGENT_WEBHOOK_TOKEN", "secret")
    server, thread = _start_test_server(tmp_path)
    try:
        status, body = _request_json(
            server,
            "POST",
            "/webhooks/default",
            {"message": "hello"},
            headers={"Authorization": "Bearer wrong"},
        )
    finally:
        _stop_test_server(server, thread)

    assert status == 401
    assert body["error"] == "Invalid webhook token."


def test_channels_endpoint_lists_configured_channels(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_path = workspace / "channels.json"
    config_path.write_text(
        json.dumps(
            {
                "channels": [
                    {"name": "ops", "kind": "webhook", "token": "ops-token"},
                    {"name": "telegram-dev", "kind": "telegram"},
                    {"name": "discord-dev", "kind": "discord"},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LGH_AGENT_CHANNELS_CONFIG", str(config_path))
    server, thread = _start_test_server(tmp_path)
    try:
        status, body = _request_json(server, "GET", "/channels")
    finally:
        _stop_test_server(server, thread)

    assert status == 200
    assert [channel["name"] for channel in body["channels"]] == [
        "ops",
        "telegram-dev",
        "discord-dev",
    ]


def test_configured_webhook_endpoint_uses_channel_token(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_path = workspace / "channels.json"
    config_path.write_text(
        json.dumps(
            {
                "channels": [
                    {
                        "name": "ops",
                        "kind": "webhook",
                        "token": "ops-token",
                        "default_session": "ops-default",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LGH_AGENT_CHANNELS_CONFIG", str(config_path))
    server, thread = _start_test_server(tmp_path)
    try:
        status, body = _request_json(
            server,
            "POST",
            "/webhooks/ops",
            {"message": "hello ops"},
            headers={"Authorization": "Bearer ops-token"},
        )
    finally:
        _stop_test_server(server, thread)

    assert status == 200
    assert body["message"] == "Echo: hello ops"
    assert body["session"] == "ops-default"


def test_configured_telegram_mock_endpoint(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config_path = workspace / "channels.json"
    config_path.write_text(
        json.dumps({"channels": [{"name": "tg", "kind": "telegram"}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("LGH_AGENT_CHANNELS_CONFIG", str(config_path))
    server, thread = _start_test_server(tmp_path)
    try:
        status, body = _request_json(
            server,
            "POST",
            "/webhooks/tg",
            {"message": {"text": "hello tg", "chat": {"id": 7}}},
        )
    finally:
        _stop_test_server(server, thread)

    assert status == 200
    assert body["message"] == "Echo: hello tg"
    assert body["session"] == "telegram-7"


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


def _request_json(
    server,
    method: str,
    path: str,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
):
    host, port = server.server_address
    conn = HTTPConnection(host, port, timeout=5)
    try:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request_headers = dict(headers or {})
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        conn.request(method, path, body=body, headers=request_headers)
        response = conn.getresponse()
        raw = response.read().decode("utf-8")
        return response.status, json.loads(raw)
    finally:
        conn.close()


def _request_text(server, method: str, path: str, payload: dict | None = None):
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
        return response.status, raw, response.getheader("Content-Type") or ""
    finally:
        conn.close()


def _join_sse_deltas(body: str) -> str:
    chunks = []
    for event in body.split("\n\n"):
        if not event.startswith("data: "):
            continue
        payload = json.loads(event.removeprefix("data: "))
        if payload.get("type") == "delta":
            chunks.append(payload.get("delta", ""))
    return "".join(chunks)
