from __future__ import annotations

import asyncio
from threading import Event, Thread

from lgh_agent.api.server import ApiSettings, make_server
from lgh_agent.automation.service import AutomationService
from lgh_agent.automation.store import AutomationStore
from lgh_agent.bus import MessageBus
from lgh_agent.config import load_app_config


def serve_gateway(
    *,
    host: str = "127.0.0.1",
    port: int = 8900,
    use_real_provider: bool = False,
    workspace: str | None = None,
    tool_root: str | None = None,
) -> None:
    """Run the HTTP API plus local background automation."""

    app_config = load_app_config(workspace)
    bus = MessageBus(
        default_use_real_provider=use_real_provider,
        workspace=str(app_config.workspace),
        tool_root=tool_root,
    )
    automation = AutomationService(
        store=AutomationStore(app_config.workspace),
        bus=bus,
    )
    stop_event = Event()
    worker = Thread(
        target=lambda: asyncio.run(automation.run_forever(stop_event)),
        daemon=True,
    )
    settings = ApiSettings(
        use_real_provider=use_real_provider,
        workspace=str(app_config.workspace),
        tool_root=tool_root,
    )
    server = make_server(host=host, port=port, settings=settings)

    print(f"lgh_agent gateway listening on http://{host}:{port}")
    worker.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        stop_event.set()
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
