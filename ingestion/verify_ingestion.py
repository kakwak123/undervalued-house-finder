#!/usr/bin/env python3
"""
Verification script to check if listings were successfully ingested into Supabase.
"""

import sys
import os
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Add models package path
models_path = Path(__file__).parent.parent / "models" / "src"
if models_path.exists():
    sys.path.insert(0, str(models_path))

try:
    from ingestion.database import SupabaseRepository
except ImportError as e:
    print(f"Error importing: {e}")
    print("Make sure dependencies are installed: pip3 install -r requirements.txt")
    import traceback
    traceback.print_exc()
    sys.exit(1)

DEFAULT_SUPABASE_URL = os.getenv("SUPABASE_URL", "")
DEFAULT_SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")


def verify_ingestion(supabase_url: str, supabase_key: str):
    """Verify that listings were ingested successfully."""
    print("Connecting to Supabase...")
    try:
        repository = SupabaseRepository(supabase_url, supabase_key)
    except Exception as e:
        print(f"❌ Error connecting to Supabase: {e}")
        return False

    print("✅ Connected to Supabase\n")

    # Get all listings
    print("Fetching listings from database...")
    try:
        listings = repository.get_all_listings()
        total_count = len(listings)
        print(f"✅ Found {total_count} listings in database\n")
    except Exception as e:
        print(f"❌ Error fetching listings: {e}")
        print("\nPossible issues:")
        print("  1. Tables don't exist - run the SQL schema in Supabase dashboard")
        print("  2. Connection issue - check your Supabase URL and API key")
        return False

    if total_count == 0:
        print("⚠️  No listings found in database.")
        print("   This could mean:")
        print("   - Ingestion hasn't been run yet")
        print("   - Ingestion failed silently")
        print("   - Tables exist but are empty")
        return False

    # Show sample listings
    print("=" * 60)
    print("Sample Listings (first 5):")
    print("=" * 60)
    for i, listing in enumerate(listings[:5], 1):
        print(f"\n{i}. Listing ID: {listing.get('listing_id')}")
        print(f"   Suburb: {listing.get('suburb')}")
        print(f"   Property Type: {listing.get('property_type')}")
        print(f"   Status: {listing.get('status')}")
        print(f"   Current Price: {listing.get('current_price')}")
        print(f"   Source: {listing.get('source')}")
        print(f"   Created: {listing.get('created_at')}")

    # Get events count
    print("\n" + "=" * 60)
    print("Checking Events...")
    print("=" * 60)
    try:
        # Try to get events count (this might fail if events table doesn't exist)
        # We'll query a sample listing for events
        if listings:
            sample_listing_id = listings[0].get('listing_id')
            events = repository.get_listing_events(sample_listing_id)
            print(f"✅ Events table accessible")
            print(f"   Sample listing '{sample_listing_id}' has {len(events)} events")
        else:
            print("⚠️  No listings to check events for")
    except Exception as e:
        print(f"⚠️  Could not check events: {e}")
        print("   Events table may not exist or may be empty")

    # Statistics
    print("\n" + "=" * 60)
    print("Statistics:")
    print("=" * 60)

    # Count by source
    sources = {}
    statuses = {}
    for listing in listings:
        source = listing.get('source', 'unknown')
        status = listing.get('status', 'unknown')
        sources[source] = sources.get(source, 0) + 1
        statuses[status] = statuses.get(status, 0) + 1

    print(f"\nTotal Listings: {total_count}")
    print(f"\nBy Source:")
    for source, count in sources.items():
        print(f"  {source}: {count}")

    print(f"\nBy Status:")
    for status, count in sorted(statuses.items()):
        print(f"  {status}: {count}")

    # Check for listings with prices
    listings_with_price = [l for l in listings if l.get('current_price')]
    print(f"\nListings with Price: {len(listings_with_price)}/{total_count}")

    # Check for listings with auction dates
    listings_with_auction = [l for l in listings if l.get('auction_datetime')]
    print(f"Listings with Auction Date: {len(listings_with_auction)}/{total_count}")

    print("\n" + "=" * 60)
    print("✅ Verification Complete!")
    print("=" * 60)
    print("\nTo view data in Supabase dashboard:")
    print("  1. Go to https://supabase.com/dashboard")
    print("  2. Select your project")
    print("  3. Go to 'Table Editor'")
    print("  4. View 'listings' and 'events' tables")

    return True


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Verify ingestion into Supabase")
    parser.add_argument(
        "--supabase-url",
        type=str,
        default=os.getenv("SUPABASE_URL", DEFAULT_SUPABASE_URL),
        help="Supabase project URL",
    )
    parser.add_argument(
        "--supabase-key",
        type=str,
        default=os.getenv("SUPABASE_KEY", DEFAULT_SUPABASE_KEY),
        help="Supabase API key",
    )

    args = parser.parse_args()

    try:
        success = verify_ingestion(args.supabase_url, args.supabase_key)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

