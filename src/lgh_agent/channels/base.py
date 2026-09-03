from __future__ import annotations

from typing import Protocol


class Channel(Protocol):
    """A user-facing entrypoint connected to MessageBus."""

    async def run(self) -> None:
        ...
