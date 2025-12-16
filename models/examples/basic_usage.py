"""
Basic usage example for property listing models.
"""

from datetime import datetime
from decimal import Decimal

from models import Listing, ListingStatus, PropertyType, Address


def main():
    """Demonstrate basic usage of the listing models."""
    
    # Create an address
    address = Address(
        street_number="31",
        street_name="Aberdeen Drive",
        suburb="Dandenong North",
        state="Vic",
        postcode="3175",
        full_address="31 Aberdeen Drive, Dandenong North, Vic 3175",
        short_address="31 Aberdeen Drive",
    )

    # Create a listing
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
        auction_datetime=datetime(2024, 12, 20, 10, 0, 0),
        property_link="https://www.realestate.com.au/property-house-vic-dandenong+north-149785064",
        source="realestate.com.au",
    )

    print("Created listing:")
    print(f"  ID: {listing.listing_id}")
    print(f"  Address: {listing.address.full_address}")
    print(f"  Type: {listing.property_type}")
    print(f"  Status: {listing.status}")
    print(f"  Current Price: ${listing.current_price:,.0f}")
    print(f"  Auction: {listing.auction_datetime}")

    # Add price history
    print("\nAdding price history...")
    listing.add_price_record(Decimal("800000"), datetime(2024, 11, 1))
    listing.add_price_record(Decimal("750000"), datetime(2024, 12, 1))

    print(f"  Current Price: ${listing.current_price:,.0f}")
    print(f"  Previous Price: ${listing.previous_price:,.0f}")
    print(f"  Price History Entries: {len(listing.price_history)}")

    # Add auction history
    print("\nAdding auction history...")
    listing.add_auction_record(
        auction_datetime=datetime(2024, 12, 20, 10, 0, 0),
        status=ListingStatus.SCHEDULED,
        notes="Initial auction scheduled",
    )

    print(f"  Status: {listing.status}")
    print(f"  Auction History Entries: {len(listing.auction_history)}")

    # Demonstrate status change
    print("\nCancelling auction...")
    listing.add_auction_record(
        auction_datetime=datetime(2024, 12, 20, 10, 0, 0),
        status=ListingStatus.CANCELLED,
        notes="Auction cancelled by seller",
    )

    print(f"  Status: {listing.status}")
    print(f"  Latest Auction Note: {listing.auction_history[0].notes}")

    # Export to JSON
    print("\nExporting to JSON...")
    json_data = listing.model_dump_json(indent=2)
    print("  JSON export successful (first 200 chars):")
    print(json_data[:200] + "...")


if __name__ == "__main__":
    main()

