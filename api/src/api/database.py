"""
Supabase client setup for the API package (M4-1).

Credentials are loaded exclusively from environment variables:
    SUPABASE_URL  — project URL (e.g. https://xxxx.supabase.co)
    SUPABASE_KEY  — anon/service-role key

A .env file in the project root is loaded automatically via python-dotenv
if the variables are not already set in the environment.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from supabase import Client, create_client

log = logging.getLogger(__name__)

load_dotenv()


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """
    Return a singleton Supabase client.

    Raises:
        RuntimeError: If SUPABASE_URL or SUPABASE_KEY are not set.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set as environment variables. "
            "See .env.example for required variables."
        )
    log.info("API: connecting to Supabase at %s", url)
    return create_client(url, key)


class ListingRepository:
    """
    Thin wrapper around the Supabase client for listing and event queries.

    All methods return plain dicts / lists of dicts — serialisation to
    Pydantic response models is done at the endpoint layer.
    """

    def __init__(self, client: Client) -> None:
        self._client = client

    # ------------------------------------------------------------------
    # Listings
    # ------------------------------------------------------------------

    def get_all_listings(
        self,
        limit: int = 50,
        offset: int = 0,
        suburb: Optional[str] = None,
        property_type: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_undervalue_score: Optional[float] = None,
        has_distress_signal: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch listings from Supabase with optional filters.

        Args:
            limit:                Maximum rows to return.
            offset:               Number of rows to skip (pagination).
            suburb:               Filter by exact suburb name (case-sensitive).
            property_type:        Filter by property_type value.
            min_price:            Minimum current_price (stored as TEXT, compared via cast).
            max_price:            Maximum current_price.
            min_undervalue_score: Minimum undervalue_score (FLOAT column).
            has_distress_signal:  Filter by distress_signal flag.

        Returns:
            List of listing dicts.
        """
        query = self._client.table("listings").select("*")

        if suburb:
            query = query.eq("suburb", suburb)
        if property_type:
            query = query.eq("property_type", property_type)
        if min_price is not None:
            # current_price is stored as TEXT in existing schema; filter via gte on cast
            # Supabase PostgREST supports this via filter on the column directly for numeric strings.
            query = query.gte("current_price", str(int(min_price)))
        if max_price is not None:
            query = query.lte("current_price", str(int(max_price)))
        if min_undervalue_score is not None:
            query = query.gte("undervalue_score", min_undervalue_score)
        if has_distress_signal is not None:
            query = query.eq("distress_signal", has_distress_signal)

        response = query.range(offset, offset + limit - 1).execute()
        return response.data or []

    def get_listing_by_id(self, listing_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a single listing by its primary key.

        Returns:
            Listing dict, or None if not found.
        """
        response = self._client.table("listings").select("*").eq("listing_id", listing_id).execute()
        rows = response.data or []
        return rows[0] if rows else None

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def get_events_for_listing(self, listing_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all events for a listing, ordered chronologically (asc).

        Returns:
            List of event dicts.
        """
        response = (
            self._client.table("events")
            .select("*")
            .eq("listing_id", listing_id)
            .order("timestamp", desc=False)
            .execute()
        )
        return response.data or []
