"""
Tests for event timeline system.
"""

import pytest
from datetime import datetime
from decimal import Decimal

from models import (
    EventTimeline,
    EventType,
    Listing,
    ListingStatus,
    PropertyType,
    Address,
)


def test_event_creation():
    """Test creating an event."""
    timeline = EventTimeline()
    event = timeline.add_event(
        event_type=EventType.PRICE_DROPPED,
        listing_id="123",
        metadata={"old_price": "800000", "new_price": "750000"},
    )

    assert event.event_type == EventType.PRICE_DROPPED
    assert event.listing_id == "123"
    assert event.metadata["old_price"] == "800000"
    assert isinstance(event.timestamp, datetime)


def test_events_stored_with_timestamp():
    """Test that events are stored with timestamps."""
    timeline = EventTimeline()
    timestamp = datetime(2024, 12, 1, 10, 0, 0)

    event = timeline.add_event(
        event_type=EventType.AUCTION_CANCELLED,
        listing_id="123",
        timestamp=timestamp,
    )

    assert event.timestamp == timestamp


def test_events_queryable_per_listing():
    """Test that events are queryable per listing."""
    timeline = EventTimeline()

    # Add events for different listings
    timeline.add_event(EventType.PRICE_DROPPED, "listing1")
    timeline.add_event(EventType.AUCTION_CANCELLED, "listing1")
    timeline.add_event(EventType.PRICE_DROPPED, "listing2")
    timeline.add_event(EventType.AUCTION_VOIDED, "listing1")

    # Query events for listing1
    listing1_events = timeline.get_events_for_listing("listing1")
    assert len(listing1_events) == 3

    # Query events for listing2
    listing2_events = timeline.get_events_for_listing("listing2")
    assert len(listing2_events) == 1
    assert listing2_events[0].event_type == EventType.PRICE_DROPPED


def test_events_filtered_by_type():
    """Test filtering events by type."""
    timeline = EventTimeline()

    timeline.add_event(EventType.PRICE_DROPPED, "listing1")
    timeline.add_event(EventType.AUCTION_CANCELLED, "listing1")
    timeline.add_event(EventType.PRICE_DROPPED, "listing1")
    timeline.add_event(EventType.AUCTION_VOIDED, "listing1")

    # Get only price drop events
    price_events = timeline.get_events_for_listing("listing1", event_type=EventType.PRICE_DROPPED)
    assert len(price_events) == 2
    assert all(e.event_type == EventType.PRICE_DROPPED for e in price_events)

    # Get only auction cancelled events
    cancelled_events = timeline.get_events_for_listing(
        "listing1", event_type=EventType.AUCTION_CANCELLED
    )
    assert len(cancelled_events) == 1
    assert cancelled_events[0].event_type == EventType.AUCTION_CANCELLED


def test_events_sorted_by_timestamp():
    """Test that events are sorted by timestamp (most recent first)."""
    timeline = EventTimeline()

    timeline.add_event(
        EventType.PRICE_DROPPED, "listing1", timestamp=datetime(2024, 11, 1)
    )
    timeline.add_event(
        EventType.AUCTION_CANCELLED, "listing1", timestamp=datetime(2024, 12, 1)
    )
    timeline.add_event(
        EventType.PRICE_DROPPED, "listing1", timestamp=datetime(2024, 10, 1)
    )

    events = timeline.get_events_for_listing("listing1")
    assert len(events) == 3
    # Most recent first
    assert events[0].timestamp == datetime(2024, 12, 1)
    assert events[1].timestamp == datetime(2024, 11, 1)
    assert events[2].timestamp == datetime(2024, 10, 1)


def test_get_latest_event():
    """Test getting the latest event for a listing."""
    timeline = EventTimeline()

    timeline.add_event(
        EventType.PRICE_DROPPED, "listing1", timestamp=datetime(2024, 11, 1)
    )
    timeline.add_event(
        EventType.AUCTION_CANCELLED, "listing1", timestamp=datetime(2024, 12, 1)
    )

    latest = timeline.get_latest_event("listing1")
    assert latest is not None
    assert latest.event_type == EventType.AUCTION_CANCELLED
    assert latest.timestamp == datetime(2024, 12, 1)

    # Test with type filter
    latest_price = timeline.get_latest_event("listing1", EventType.PRICE_DROPPED)
    assert latest_price is not None
    assert latest_price.event_type == EventType.PRICE_DROPPED


def test_automatic_price_drop_event():
    """Test that price drops automatically generate events."""
    timeline = EventTimeline()
    address = Address(suburb="Test", state="Vic", postcode="3000")
    listing = Listing(
        listing_id="123",
        address=address,
        suburb="Test",
        property_type=PropertyType.HOUSE,
        current_price=Decimal("800000"),
    )

    # Add lower price - should trigger PRICE_DROPPED event
    listing.add_price_record(Decimal("750000"), event_timeline=timeline)

    events = timeline.get_events_for_listing("123")
    assert len(events) == 1
    assert events[0].event_type == EventType.PRICE_DROPPED
    assert events[0].metadata["old_price"] == "800000"
    assert events[0].metadata["new_price"] == "750000"


def test_automatic_auction_cancelled_event():
    """Test that auction cancellations automatically generate events."""
    timeline = EventTimeline()
    address = Address(suburb="Test", state="Vic", postcode="3000")
    listing = Listing(
        listing_id="123",
        address=address,
        suburb="Test",
        property_type=PropertyType.HOUSE,
        status=ListingStatus.SCHEDULED,
        auction_datetime=datetime(2024, 12, 20, 10, 0, 0),
    )

    # Cancel auction - should trigger AUCTION_CANCELLED event
    listing.add_auction_record(
        auction_datetime=datetime(2024, 12, 20, 10, 0, 0),
        status=ListingStatus.CANCELLED,
        event_timeline=timeline,
    )

    events = timeline.get_events_for_listing("123")
    assert len(events) == 1
    assert events[0].event_type == EventType.AUCTION_CANCELLED


def test_automatic_auction_voided_event():
    """Test that auction voiding automatically generates events."""
    timeline = EventTimeline()
    address = Address(suburb="Test", state="Vic", postcode="3000")
    listing = Listing(
        listing_id="123",
        address=address,
        suburb="Test",
        property_type=PropertyType.HOUSE,
        status=ListingStatus.SCHEDULED,
    )

    listing.add_auction_record(
        auction_datetime=datetime(2024, 12, 20, 10, 0, 0),
        status=ListingStatus.VOIDED,
        event_timeline=timeline,
    )

    events = timeline.get_events_for_listing("123")
    assert len(events) == 1
    assert events[0].event_type == EventType.AUCTION_VOIDED


def test_automatic_auction_rescheduled_event():
    """Test that auction rescheduling automatically generates events."""
    timeline = EventTimeline()
    address = Address(suburb="Test", state="Vic", postcode="3000")
    listing = Listing(
        listing_id="123",
        address=address,
        suburb="Test",
        property_type=PropertyType.HOUSE,
        status=ListingStatus.SCHEDULED,
        auction_datetime=datetime(2024, 12, 20, 10, 0, 0),
    )

    # Reschedule auction - should trigger AUCTION_RESCHEDULED event
    listing.add_auction_record(
        auction_datetime=datetime(2024, 12, 27, 14, 0, 0),
        status=ListingStatus.SCHEDULED,
        event_timeline=timeline,
    )

    events = timeline.get_events_for_listing("123")
    assert len(events) == 1
    assert events[0].event_type == EventType.AUCTION_RESCHEDULED
    assert "old_auction_datetime" in events[0].metadata
    assert "new_auction_datetime" in events[0].metadata


def test_count_events():
    """Test counting events."""
    timeline = EventTimeline()

    timeline.add_event(EventType.PRICE_DROPPED, "listing1")
    timeline.add_event(EventType.AUCTION_CANCELLED, "listing1")
    timeline.add_event(EventType.PRICE_DROPPED, "listing2")

    assert timeline.count_events() == 3
    assert timeline.count_events(listing_id="listing1") == 2
    assert timeline.count_events(event_type=EventType.PRICE_DROPPED) == 2
    assert timeline.count_events(listing_id="listing1", event_type=EventType.PRICE_DROPPED) == 1


def test_has_event_type():
    """Test checking if listing has specific event type."""
    timeline = EventTimeline()

    timeline.add_event(EventType.PRICE_DROPPED, "listing1")
    timeline.add_event(EventType.AUCTION_CANCELLED, "listing1")

    assert timeline.has_event_type("listing1", EventType.PRICE_DROPPED) is True
    assert timeline.has_event_type("listing1", EventType.AUCTION_VOIDED) is False
    assert timeline.has_event_type("listing2", EventType.PRICE_DROPPED) is False

