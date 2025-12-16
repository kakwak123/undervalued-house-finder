"""
Tests for property listing models.
"""

import pytest
from datetime import datetime
from decimal import Decimal

from models import (
    Listing,
    ListingStatus,
    PropertyType,
    Address,
    PriceHistory,
    AuctionHistory,
)


def test_listing_creation():
    """Test creating a basic listing."""
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
        land_size=Decimal("554"),
        status=ListingStatus.SCHEDULED,
        current_price=Decimal("750000"),
    )

    assert listing.listing_id == "149785064"
    assert listing.suburb == "Dandenong North"
    assert listing.property_type == PropertyType.HOUSE
    assert listing.bedrooms == 6
    assert listing.bathrooms == 2
    assert listing.status == ListingStatus.SCHEDULED
    assert listing.current_price == Decimal("750000")


def test_price_history_tracking():
    """Test that price history is tracked correctly."""
    address = Address(suburb="Test", state="Vic", postcode="3000")
    listing = Listing(
        listing_id="123",
        address=address,
        suburb="Test",
        property_type=PropertyType.HOUSE,
    )

    # Add initial price
    listing.add_price_record(Decimal("800000"), datetime(2024, 11, 1))
    assert listing.current_price == Decimal("800000")
    assert listing.previous_price is None
    assert len(listing.price_history) == 1

    # Add new price
    listing.add_price_record(Decimal("750000"), datetime(2024, 12, 1))
    assert listing.current_price == Decimal("750000")
    assert listing.previous_price == Decimal("800000")
    assert len(listing.price_history) == 2

    # Verify history is sorted (most recent first)
    assert listing.price_history[0].price == Decimal("750000")
    assert listing.price_history[1].price == Decimal("800000")


def test_auction_history_tracking():
    """Test that auction history is tracked correctly."""
    address = Address(suburb="Test", state="Vic", postcode="3000")
    listing = Listing(
        listing_id="123",
        address=address,
        suburb="Test",
        property_type=PropertyType.HOUSE,
    )

    # Add scheduled auction
    auction_dt = datetime(2024, 12, 20, 10, 0, 0)
    listing.add_auction_record(
        auction_datetime=auction_dt,
        status=ListingStatus.SCHEDULED,
        notes="Initial auction",
    )

    assert listing.auction_datetime == auction_dt
    assert listing.status == ListingStatus.SCHEDULED
    assert len(listing.auction_history) == 1
    assert listing.auction_history[0].notes == "Initial auction"

    # Add cancelled auction
    listing.add_auction_record(
        auction_datetime=auction_dt,
        status=ListingStatus.CANCELLED,
        notes="Auction cancelled",
    )

    assert listing.status == ListingStatus.CANCELLED
    assert len(listing.auction_history) == 2


def test_listing_status_enum():
    """Test that all required status values exist."""
    required_statuses = [
        "scheduled",
        "cancelled",
        "voided",
        "sold",
        "withdrawn",
        "active",
        "under_offer",
        "unknown",
    ]

    for status in required_statuses:
        assert hasattr(ListingStatus, status.upper().replace("_", ""))
        assert ListingStatus(status) is not None


def test_property_type_from_string():
    """Test PropertyType.from_string handles variations."""
    assert PropertyType.from_string("House") == PropertyType.HOUSE
    assert PropertyType.from_string("Apartment / Unit / Flat") == PropertyType.UNIT
    assert PropertyType.from_string("Townhouse") == PropertyType.TOWNHOUSE
    assert PropertyType.from_string("Unknown Type") == PropertyType.OTHER
    assert PropertyType.from_string("") == PropertyType.OTHER


def test_listing_json_serialization():
    """Test that listing can be serialized to JSON."""
    address = Address(suburb="Test", state="Vic", postcode="3000")
    listing = Listing(
        listing_id="123",
        address=address,
        suburb="Test",
        property_type=PropertyType.HOUSE,
        current_price=Decimal("750000"),
    )

    # Should not raise
    json_data = listing.model_dump_json()
    assert json_data is not None
    assert "123" in json_data
    assert "750000" in json_data

