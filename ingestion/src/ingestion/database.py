"""
Supabase database repository for listings and events.
"""

import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal

from supabase import create_client, Client
from pydantic import BaseModel

# Add models package to path
models_path = Path(__file__).parent.parent.parent.parent.parent / "models" / "src"
sys.path.insert(0, str(models_path))

from models import Listing, ListingStatus, PropertyType, Event, EventType, EventTimeline


class SupabaseRepository:
    """
    Repository for storing and retrieving listings and events from Supabase.
    """

    def __init__(self, supabase_url: str, supabase_key: str):
        """
        Initialize Supabase client.

        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase API key
        """
        self.client: Client = create_client(supabase_url, supabase_key)
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """
        Ensure required tables exist in Supabase.
        Creates tables if they don't exist via SQL migration.
        """
        # Note: In production, you'd run migrations separately
        # For now, we'll assume tables are created via Supabase dashboard
        # or migration scripts
        pass

    def get_listing(self, listing_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a listing by ID.

        Args:
            listing_id: Listing identifier

        Returns:
            Listing data as dict, or None if not found
        """
        try:
            response = (
                self.client.table("listings")
                .select("*")
                .eq("listing_id", listing_id)
                .execute()
            )
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            print(f"Error fetching listing {listing_id}: {e}")
            return None

    def upsert_listing(self, listing: Listing) -> Dict[str, Any]:
        """
        Insert or update a listing (idempotent).

        Args:
            listing: Listing model instance

        Returns:
            Upserted listing data
        """
        # Convert listing to dict for Supabase
        listing_data = self._listing_to_dict(listing)

        try:
            response = (
                self.client.table("listings")
                .upsert(listing_data, on_conflict="listing_id")
                .execute()
            )
            return response.data[0] if response.data else listing_data
        except Exception as e:
            print(f"Error upserting listing {listing.listing_id}: {e}")
            raise

    def _listing_to_dict(self, listing: Listing) -> Dict[str, Any]:
        """
        Convert Listing model to dictionary for Supabase.

        Args:
            listing: Listing model instance

        Returns:
            Dictionary representation
        """
        # Convert Decimal to string for JSON serialization
        def decimal_to_str(value):
            return str(value) if value is not None else None

        # Convert datetime to ISO string
        def datetime_to_str(value):
            return value.isoformat() if value else None

        return {
            "listing_id": listing.listing_id,
            "suburb": listing.suburb,
            "property_type": listing.property_type.value,
            "bedrooms": listing.bedrooms,
            "bathrooms": listing.bathrooms,
            "land_size": decimal_to_str(listing.land_size),
            "building_size": decimal_to_str(listing.building_size),
            "status": listing.status.value,
            "current_price": decimal_to_str(listing.current_price),
            "previous_price": decimal_to_str(listing.previous_price),
            "auction_datetime": datetime_to_str(listing.auction_datetime),
            "property_link": listing.property_link,
            "description": listing.description,
            "source": listing.source,
            "address": listing.address.model_dump_json(),
            "price_history": [
                {
                    "price": str(ph.price),
                    "timestamp": ph.timestamp.isoformat(),
                    "source": ph.source,
                }
                for ph in listing.price_history
            ],
            "auction_history": [
                {
                    "auction_datetime": ah.auction_datetime.isoformat(),
                    "status": ah.status.value,
                    "timestamp": ah.timestamp.isoformat(),
                    "notes": ah.notes,
                }
                for ah in listing.auction_history
            ],
            "created_at": datetime_to_str(listing.created_at) or datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

    def add_event(self, event: Event) -> Dict[str, Any]:
        """
        Add an event to the database.

        Args:
            event: Event model instance

        Returns:
            Inserted event data
        """
        event_data = {
            "event_type": event.event_type.value,
            "timestamp": event.timestamp.isoformat(),
            "listing_id": event.listing_id,
            "metadata": event.metadata,
        }

        try:
            response = self.client.table("events").insert(event_data).execute()
            return response.data[0] if response.data else event_data
        except Exception as e:
            print(f"Error adding event: {e}")
            raise

    def get_listing_events(
        self, listing_id: str, event_type: Optional[EventType] = None
    ) -> List[Dict[str, Any]]:
        """
        Get events for a listing.

        Args:
            listing_id: Listing identifier
            event_type: Optional event type filter

        Returns:
            List of event data
        """
        query = self.client.table("events").select("*").eq("listing_id", listing_id)

        if event_type:
            query = query.eq("event_type", event_type.value)

        try:
            response = query.order("timestamp", desc=True).execute()
            return response.data or []
        except Exception as e:
            print(f"Error fetching events for listing {listing_id}: {e}")
            return []

    def get_all_listings(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all listings.

        Args:
            limit: Optional limit on number of results

        Returns:
            List of listing data
        """
        query = self.client.table("listings").select("*")

        if limit:
            query = query.limit(limit)

        try:
            response = query.execute()
            return response.data or []
        except Exception as e:
            print(f"Error fetching listings: {e}")
            return []

