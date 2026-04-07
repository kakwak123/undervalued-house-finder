"""In-memory event bus with ring buffer for the activity dashboard."""

from __future__ import annotations

import asyncio
import uuid
from collections import deque
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Deque, Dict, List, Optional, Union

from pydantic import BaseModel


class EventCategory(str, Enum):
    SCRAPING = "SCRAPING"
    INGESTING = "INGESTING"
    VALUATION = "VALUATION"
    EVENT = "EVENT"
    DB_WRITE = "DB_WRITE"
    RETRY = "RETRY"
    ERROR = "ERROR"
    SYSTEM = "SYSTEM"


class ActivityEvent(BaseModel):
    id: str
    timestamp: str
    category: EventCategory
    message: str
    detail: Optional[Dict[str, Any]] = None


# Subscribers are async callables that receive a serialised event dict.
_Subscriber = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]

_RING_BUFFER_SIZE = 500

_buffer: Deque[ActivityEvent] = deque(maxlen=_RING_BUFFER_SIZE)
_subscribers: List[_Subscriber] = []


def _make_event(category: EventCategory, message: str, detail: Optional[Dict[str, Any]]) -> ActivityEvent:
    return ActivityEvent(
        id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        category=category,
        message=message,
        detail=detail,
    )


async def publish(category: Union[EventCategory, str], message: str, detail: Optional[Dict[str, Any]] = None) -> None:
    """Broadcast an event to all WebSocket subscribers and append to ring buffer."""
    if isinstance(category, str):
        category = EventCategory(category)
    event = _make_event(category, message, detail)
    _buffer.append(event)
    payload = event.model_dump()
    dead: List[_Subscriber] = []
    for sub in list(_subscribers):
        try:
            await sub(payload)
        except Exception:
            dead.append(sub)
    for sub in dead:
        _subscribers.remove(sub)


def publish_sync(category: Union[EventCategory, str], message: str, detail: Optional[Dict[str, Any]] = None) -> None:
    """Fire-and-forget wrapper usable from synchronous code.

    Uses asyncio.get_event_loop() — only call from within a running event loop context
    (e.g. a background thread spawned by a FastAPI endpoint).
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(publish(category, message, detail))
        else:
            loop.run_until_complete(publish(category, message, detail))
    except RuntimeError:
        # No event loop available — buffer only (no broadcast).
        if isinstance(category, str):
            category = EventCategory(category)
        event = _make_event(category, message, detail)
        _buffer.append(event)


def subscribe(callback: _Subscriber) -> None:
    """Register an async subscriber."""
    _subscribers.append(callback)


def unsubscribe(callback: _Subscriber) -> None:
    """Remove a subscriber."""
    try:
        _subscribers.remove(callback)
    except ValueError:
        pass


def get_buffered_events() -> List[Dict[str, Any]]:
    """Return a copy of the ring buffer as plain dicts (for WebSocket replay)."""
    return [e.model_dump() for e in _buffer]


def clear_buffer() -> None:
    """Clear the in-memory ring buffer (used by reset-events endpoint)."""
    _buffer.clear()
