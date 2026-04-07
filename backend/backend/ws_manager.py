"""WebSocket connection manager — handles connect, disconnect, and broadcast."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from fastapi import WebSocket

from backend.event_bus import get_buffered_events, subscribe, unsubscribe


class ConnectionManager:
    def __init__(self) -> None:
        self._active: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept the connection, replay buffered events, then start listening."""
        await websocket.accept()
        self._active.append(websocket)

        # Register a subscriber so future publishes reach this socket.
        async def _send(payload: Dict[str, Any]) -> None:
            await websocket.send_text(json.dumps(payload))

        # Stash the callable on the websocket so we can unsubscribe it later.
        websocket.state.bus_subscriber = _send  # type: ignore[attr-defined]
        subscribe(_send)

        # Replay the last 500 events so the frontend has history on connect.
        for event in get_buffered_events():
            await websocket.send_text(json.dumps(event))

    def disconnect(self, websocket: WebSocket) -> None:
        """Unsubscribe and remove from active connections."""
        sub = getattr(getattr(websocket, "state", None), "bus_subscriber", None)
        if sub is not None:
            unsubscribe(sub)
        try:
            self._active.remove(websocket)
        except ValueError:
            pass

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        """Send a payload to all active connections directly (bypasses event bus)."""
        dead: List[WebSocket] = []
        for ws in list(self._active):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()
