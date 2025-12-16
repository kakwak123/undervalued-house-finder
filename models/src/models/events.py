"""
Event timeline system for tracking listing changes.

This module provides event logging functionality that stores events with
timestamps and metadata, and allows querying events per listing.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from .enums import EventType


class Event(BaseModel):
    """
    An event that occurred for a listing.

    Events are stored with timestamp and metadata as required by acceptance criteria.
    """

    event_type: EventType = Field(..., description="Type of event")
    timestamp: datetime = Field(..., description="When the event occurred")
    listing_id: str = Field(..., description="ID of the listing this event relates to")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the event",
    )

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    def __repr__(self) -> str:
        return f"Event(type={self.event_type}, listing_id={self.listing_id}, timestamp={self.timestamp})"


class EventTimeline:
    """
    Timeline system for storing and querying events per listing.

    This class provides the event logging functionality required by Issue 3.
    Events are stored with timestamp + metadata and are queryable per listing.
    """

    def __init__(self):
        """Initialize an empty event timeline."""
        self._events: List[Event] = []
        self._events_by_listing: Dict[str, List[Event]] = {}

    def add_event(
        self,
        event_type: EventType,
        listing_id: str,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Event:
        """
        Add an event to the timeline.

        Args:
            event_type: Type of event
            listing_id: ID of the listing
            timestamp: When the event occurred (defaults to now)
            metadata: Additional metadata about the event

        Returns:
            The created Event instance
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        if metadata is None:
            metadata = {}

        event = Event(
            event_type=event_type,
            timestamp=timestamp,
            listing_id=listing_id,
            metadata=metadata,
        )

        # Add to events list
        self._events.append(event)

        # Add to listing-specific index
        if listing_id not in self._events_by_listing:
            self._events_by_listing[listing_id] = []
        self._events_by_listing[listing_id].append(event)

        # Sort events by timestamp (most recent first)
        self._events.sort(key=lambda e: e.timestamp, reverse=True)
        self._events_by_listing[listing_id].sort(
            key=lambda e: e.timestamp, reverse=True
        )

        return event

    def get_events_for_listing(
        self,
        listing_id: str,
        event_type: Optional[EventType] = None,
        limit: Optional[int] = None,
    ) -> List[Event]:
        """
        Query events for a specific listing.

        Args:
            listing_id: ID of the listing
            event_type: Optional filter by event type
            limit: Optional limit on number of events to return

        Returns:
            List of events for the listing, sorted by timestamp (most recent first)
        """
        events = self._events_by_listing.get(listing_id, [])

        # Filter by event type if specified
        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]

        # Apply limit if specified
        if limit is not None:
            events = events[:limit]

        return events

    def get_all_events(
        self,
        event_type: Optional[EventType] = None,
        limit: Optional[int] = None,
    ) -> List[Event]:
        """
        Get all events, optionally filtered by type.

        Args:
            event_type: Optional filter by event type
            limit: Optional limit on number of events to return

        Returns:
            List of events, sorted by timestamp (most recent first)
        """
        events = self._events.copy()

        # Filter by event type if specified
        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]

        # Apply limit if specified
        if limit is not None:
            events = events[:limit]

        return events

    def get_latest_event(
        self,
        listing_id: str,
        event_type: Optional[EventType] = None,
    ) -> Optional[Event]:
        """
        Get the most recent event for a listing.

        Args:
            listing_id: ID of the listing
            event_type: Optional filter by event type

        Returns:
            Most recent event, or None if no events exist
        """
        events = self.get_events_for_listing(listing_id, event_type, limit=1)
        return events[0] if events else None

    def has_event_type(
        self,
        listing_id: str,
        event_type: EventType,
    ) -> bool:
        """
        Check if a listing has any events of a specific type.

        Args:
            listing_id: ID of the listing
            event_type: Event type to check for

        Returns:
            True if listing has at least one event of this type
        """
        events = self.get_events_for_listing(listing_id, event_type)
        return len(events) > 0

    def count_events(
        self,
        listing_id: Optional[str] = None,
        event_type: Optional[EventType] = None,
    ) -> int:
        """
        Count events, optionally filtered by listing and/or event type.

        Args:
            listing_id: Optional filter by listing ID
            event_type: Optional filter by event type

        Returns:
            Number of events matching the criteria
        """
        if listing_id is not None:
            events = self.get_events_for_listing(listing_id, event_type)
            return len(events)
        else:
            events = self.get_all_events(event_type)
            return len(events)

    def clear(self) -> None:
        """Clear all events from the timeline."""
        self._events.clear()
        self._events_by_listing.clear()

    def __len__(self) -> int:
        """Return the total number of events."""
        return len(self._events)

    def __repr__(self) -> str:
        return f"EventTimeline(events={len(self._events)}, listings={len(self._events_by_listing)})"

