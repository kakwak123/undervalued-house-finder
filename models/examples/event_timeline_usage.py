"""
Example usage of the event timeline system.
"""

from datetime import datetime
from decimal import Decimal

from models import (
    Listing,
    ListingStatus,
    PropertyType,
    Address,
    EventTimeline,
    EventType,
)


def main():
    """Demonstrate event timeline functionality."""
    
    # Create an event timeline
    timeline = EventTimeline()
    
    # Create a listing
    address = Address(
        suburb="Dandenong North",
        state="Vic",
        postcode="3175",
        full_address="31 Aberdeen Drive, Dandenong North, Vic 3175",
    )
    
    listing = Listing(
        listing_id="149785064",
        address=address,
        suburb="Dandenong North",
        property_type=PropertyType.HOUSE,
        bedrooms=6,
        bathrooms=2,
        status=ListingStatus.SCHEDULED,
        current_price=Decimal("800000"),
        auction_datetime=datetime(2024, 12, 20, 10, 0, 0),
    )

    print("=== Initial Listing ===")
    print(f"Status: {listing.status}")
    print(f"Price: ${listing.current_price:,.0f}")
    print(f"Auction: {listing.auction_datetime}")

    # Price drop - automatically generates PRICE_DROPPED event
    print("\n=== Price Drop ===")
    listing.add_price_record(Decimal("750000"), event_timeline=timeline)
    print(f"New Price: ${listing.current_price:,.0f}")
    print(f"Previous Price: ${listing.previous_price:,.0f}")
    
    price_events = timeline.get_events_for_listing(listing.listing_id, EventType.PRICE_DROPPED)
    print(f"Price drop events: {len(price_events)}")
    if price_events:
        event = price_events[0]
        print(f"  Event: {event.event_type}")
        print(f"  Drop: ${event.metadata['drop_amount']} ({event.metadata['drop_percent']:.1f}%)")

    # Auction cancelled - automatically generates AUCTION_CANCELLED event
    print("\n=== Auction Cancelled ===")
    listing.add_auction_record(
        auction_datetime=datetime(2024, 12, 20, 10, 0, 0),
        status=ListingStatus.CANCELLED,
        notes="Cancelled by seller",
        event_timeline=timeline,
    )
    print(f"Status: {listing.status}")
    
    cancelled_events = timeline.get_events_for_listing(
        listing.listing_id, EventType.AUCTION_CANCELLED
    )
    print(f"Cancelled events: {len(cancelled_events)}")
    if cancelled_events:
        print(f"  Note: {cancelled_events[0].metadata.get('notes')}")

    # Reschedule auction - automatically generates AUCTION_RESCHEDULED event
    print("\n=== Auction Rescheduled ===")
    listing.add_auction_record(
        auction_datetime=datetime(2024, 12, 27, 14, 0, 0),
        status=ListingStatus.SCHEDULED,
        notes="Rescheduled to next week",
        event_timeline=timeline,
    )
    print(f"New Auction Date: {listing.auction_datetime}")
    
    rescheduled_events = timeline.get_events_for_listing(
        listing.listing_id, EventType.AUCTION_RESCHEDULED
    )
    print(f"Rescheduled events: {len(rescheduled_events)}")
    if rescheduled_events:
        event = rescheduled_events[0]
        print(f"  Old: {event.metadata['old_auction_datetime']}")
        print(f"  New: {event.metadata['new_auction_datetime']}")

    # Query all events for this listing
    print("\n=== All Events for Listing ===")
    all_events = timeline.get_events_for_listing(listing.listing_id)
    print(f"Total events: {len(all_events)}")
    for event in all_events:
        print(f"  {event.event_type} at {event.timestamp}")

    # Query latest event
    print("\n=== Latest Event ===")
    latest = timeline.get_latest_event(listing.listing_id)
    if latest:
        print(f"Latest: {latest.event_type} at {latest.timestamp}")

    # Count events by type
    print("\n=== Event Counts ===")
    print(f"Price drops: {timeline.count_events(listing.listing_id, EventType.PRICE_DROPPED)}")
    print(f"Auction cancelled: {timeline.count_events(listing.listing_id, EventType.AUCTION_CANCELLED)}")
    print(f"Auction rescheduled: {timeline.count_events(listing.listing_id, EventType.AUCTION_RESCHEDULED)}")


if __name__ == "__main__":
    main()

