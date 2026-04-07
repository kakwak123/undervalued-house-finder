"""
Main ingestion logic with change detection and event generation.

Handles M3-1 (auction cancellation), M3-2 (auction rescheduling), and
M3-3 (distress signal: AUCTION_VOIDED + PRICE_DROPPED compound signal).
"""

import logging
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal

# Add models package to path
models_path = Path(__file__).parent.parent.parent.parent.parent / "models" / "src"
sys.path.insert(0, str(models_path))

from models import Listing, ListingStatus, EventTimeline, EventType

from .database import SupabaseRepository
from .readers import RealestateReader, DomainReader, detect_reader_type

log = logging.getLogger(__name__)

# Number of days within which both AUCTION_VOIDED and PRICE_DROPPED must have
# occurred to trigger a DISTRESS_SIGNAL (M3-3).  Configurable at construction.
_DEFAULT_DISTRESS_WINDOW_DAYS = 14


class Ingester:
    """
    Main ingestion class that handles listing ingestion with change detection.

    Provides idempotent ingestion, change detection, and automatic event generation.

    Detects and emits the following events:
    - PRICE_DROPPED       — price decreased between runs
    - AUCTION_CANCELLED   — status changed to CANCELLED, or auction_datetime cleared
    - AUCTION_VOIDED      — status changed to VOIDED
    - AUCTION_RESCHEDULED — auction_datetime changed to a new future date
    - DISTRESS_SIGNAL     — AUCTION_VOIDED + PRICE_DROPPED within ``distress_window_days``
    """

    def __init__(
        self,
        repository: SupabaseRepository,
        distress_window_days: int = _DEFAULT_DISTRESS_WINDOW_DAYS,
    ) -> None:
        """
        Initialize ingester with database repository.

        Args:
            repository: SupabaseRepository instance
            distress_window_days: Window (days) for DISTRESS_SIGNAL compound detection (M3-3).
        """
        self.repository = repository
        self.event_timeline = EventTimeline()
        self.distress_window_days = distress_window_days
        self.stats = {
            "processed": 0,
            "created": 0,
            "updated": 0,
            "events_generated": 0,
            "errors": 0,
        }

    def ingest_listings_data(
        self,
        data: List[Dict[str, Any]],
        source_type: str,
    ) -> None:
        """
        Ingest listings from an in-memory list of raw scraper dicts.

        This is the no-file-step entry point used by the scrape-to-ingest
        pipeline (S-2).  It accepts the same raw JSON structures that the
        scraper functions return and normalises them using the appropriate
        reader without writing anything to disk.

        Args:
            data:        List of raw property dicts from a scraper.
            source_type: Scraper origin — 'realestate' or 'domain'.
        """
        from .readers import RealestateReader, DomainReader

        if source_type == "realestate":
            listings_iter = RealestateReader.from_data(data)
        elif source_type == "domain":
            listings_iter = DomainReader.from_data(data)
        else:
            raise ValueError(f"Unknown source_type {source_type!r}. Must be 'realestate' or 'domain'.")

        for listing in listings_iter:
            try:
                self._ingest_listing(listing)
                self.stats["processed"] += 1
            except Exception as e:
                print(f"Error ingesting listing {listing.listing_id}: {e}")
                self.stats["errors"] += 1

    def ingest_file(
        self,
        file_path: Path,
        source_type: Optional[str] = None,
    ) -> None:
        """
        Ingest listings from a JSON file.

        Args:
            file_path: Path to JSON file
            source_type: Optional source type ('realestate' or 'domain')
        """
        file_path = Path(file_path)

        # Auto-detect source type if not provided
        if source_type is None:
            source_type = detect_reader_type(file_path)

        # Create appropriate reader
        if source_type == "realestate":
            reader = RealestateReader(file_path)
        elif source_type == "domain":
            reader = DomainReader(file_path)
        else:
            # Try realestate first (most common)
            reader = RealestateReader(file_path)

        # Process each listing
        for listing in reader.read_listings():
            try:
                self._ingest_listing(listing)
                self.stats["processed"] += 1
            except Exception as e:
                print(f"Error ingesting listing {listing.listing_id}: {e}")
                self.stats["errors"] += 1

    def _ingest_listing(self, listing: Listing) -> None:
        """
        Ingest a single listing with change detection.

        Args:
            listing: Listing model instance
        """
        # Set timestamps if not set
        if listing.created_at is None:
            listing.created_at = datetime.utcnow()
        listing.updated_at = datetime.utcnow()

        # Get existing listing from database
        existing = self.repository.get_listing(listing.listing_id)

        if existing:
            # Update existing listing with change detection
            self._update_listing(listing, existing)
            self.stats["updated"] += 1
        else:
            # Create new listing
            self.repository.upsert_listing(listing)
            self.stats["created"] += 1

        # Save events to database
        self._save_events(listing.listing_id)

    def _update_listing(self, new_listing: Listing, existing: Dict) -> None:
        """
        Update existing listing with change detection.

        Args:
            new_listing: New listing data
            existing: Existing listing data from database
        """
        # Detect price changes
        existing_price = (
            Decimal(str(existing.get("current_price")))
            if existing.get("current_price")
            else None
        )
        new_price = new_listing.current_price

        if existing_price and new_price and new_price < existing_price:
            # Price dropped - generate event
            price_drop_amount = existing_price - new_price
            price_drop_percent = (price_drop_amount / existing_price) * 100

            self.event_timeline.add_event(
                event_type=EventType.PRICE_DROPPED,
                listing_id=new_listing.listing_id,
                metadata={
                    "old_price": str(existing_price),
                    "new_price": str(new_price),
                    "drop_amount": str(price_drop_amount),
                    "drop_percent": float(price_drop_percent),
                },
            )
            self.stats["events_generated"] += 1

        # Detect auction rescheduling and cancellation via auction_datetime change
        existing_auction = existing.get("auction_datetime")
        new_auction = (
            new_listing.auction_datetime.isoformat()
            if new_listing.auction_datetime
            else None
        )

        # M3-1: auction_datetime was set and is now None/removed → AUCTION_CANCELLED
        # (Covers the case where the status field alone does not change but the
        # scheduled datetime disappears, signalling the auction was pulled.)
        if existing_auction and not new_auction:
            self.event_timeline.add_event(
                event_type=EventType.AUCTION_CANCELLED,
                listing_id=new_listing.listing_id,
                metadata={
                    "previous_auction_datetime": existing_auction,
                    "reason": "auction_datetime cleared",
                },
            )
            # Reflect cancellation in the listing's status if it is still SCHEDULED
            if new_listing.status == ListingStatus.SCHEDULED:
                new_listing.status = ListingStatus.CANCELLED
            log.info(
                "Ingester: %s auction cancelled — auction_datetime cleared (was %s)",
                new_listing.listing_id,
                existing_auction,
            )
            self.stats["events_generated"] += 1

        # M3-2: auction_datetime changed to a new future date → AUCTION_RESCHEDULED
        # (Covered also by status-change path below, but the datetime change is the
        # authoritative signal when the status stays SCHEDULED.)
        elif (
            existing_auction
            and new_auction
            and existing_auction != new_auction
            and new_listing.status == ListingStatus.SCHEDULED
        ):
            self.event_timeline.add_event(
                event_type=EventType.AUCTION_RESCHEDULED,
                listing_id=new_listing.listing_id,
                metadata={
                    "old_auction_datetime": existing_auction,
                    "new_auction_datetime": new_auction,
                },
            )
            log.info(
                "Ingester: %s auction rescheduled from %s to %s",
                new_listing.listing_id,
                existing_auction,
                new_auction,
            )
            self.stats["events_generated"] += 1

        # Detect status changes (covers CANCELLED/VOIDED transitions not caught above)
        existing_status = ListingStatus(existing.get("status", "unknown"))
        new_status = new_listing.status

        if existing_status != new_status:
            if new_status == ListingStatus.CANCELLED:
                # Only emit if not already emitted by the auction_datetime-cleared path
                already_emitted = any(
                    e.event_type == EventType.AUCTION_CANCELLED
                    for e in self.event_timeline.get_events_for_listing(new_listing.listing_id)
                )
                if not already_emitted:
                    self.event_timeline.add_event(
                        event_type=EventType.AUCTION_CANCELLED,
                        listing_id=new_listing.listing_id,
                        metadata={
                            "previous_status": existing_status.value,
                            "new_status": new_status.value,
                        },
                    )
                    log.info(
                        "Ingester: %s status changed to CANCELLED (was %s)",
                        new_listing.listing_id,
                        existing_status.value,
                    )
                    self.stats["events_generated"] += 1
            elif new_status == ListingStatus.VOIDED:
                self.event_timeline.add_event(
                    event_type=EventType.AUCTION_VOIDED,
                    listing_id=new_listing.listing_id,
                    metadata={
                        "previous_status": existing_status.value,
                        "new_status": new_status.value,
                    },
                )
                log.info(
                    "Ingester: %s status changed to VOIDED (was %s)",
                    new_listing.listing_id,
                    existing_status.value,
                )
                self.stats["events_generated"] += 1

        # Update listing in database
        self.repository.upsert_listing(new_listing)

        # M3-3: check for DISTRESS_SIGNAL compound condition after persisting
        self._check_distress_signal(new_listing)

    def _check_distress_signal(self, listing: Listing) -> None:
        """
        M3-3: Detect and emit a DISTRESS_SIGNAL when a listing has both an
        AUCTION_VOIDED event and a PRICE_DROPPED event within the configured
        distress window.

        If the signal is newly detected:
        - Sets ``listing.distress_signal = True``
        - Emits a DISTRESS_SIGNAL event into the timeline
        - Re-upserts the listing to persist the ``distress_signal`` flag

        The check uses persisted events from the database so that signals
        from previous ingestion runs are honoured, not just in-memory events
        from the current run.

        Args:
            listing: The newly upserted Listing instance.
        """
        if listing.distress_signal:
            # Already flagged — nothing to do.
            return

        cutoff = datetime.utcnow() - timedelta(days=self.distress_window_days)

        db_events = self.repository.get_listing_events(listing.listing_id)
        in_memory_events = self.event_timeline.get_events_for_listing(listing.listing_id)

        # Merge: db_events is a list of dicts; in_memory_events is a list of Event objects.
        def _event_matches(event_type: str, source: Any) -> bool:
            """Return True if *source* (dict or Event) has the given type and is recent."""
            if isinstance(source, dict):
                ts_raw = source.get("timestamp")
                if ts_raw is None:
                    return False
                if isinstance(ts_raw, str):
                    ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).replace(tzinfo=None)
                else:
                    ts = ts_raw
                return source.get("event_type") == event_type and ts >= cutoff
            else:
                # Event object
                ts = source.timestamp.replace(tzinfo=None) if source.timestamp.tzinfo else source.timestamp
                return source.event_type.value == event_type and ts >= cutoff

        has_voided = any(_event_matches(EventType.AUCTION_VOIDED.value, e) for e in db_events) or any(
            _event_matches(EventType.AUCTION_VOIDED.value, e) for e in in_memory_events
        )
        has_price_dropped = any(_event_matches(EventType.PRICE_DROPPED.value, e) for e in db_events) or any(
            _event_matches(EventType.PRICE_DROPPED.value, e) for e in in_memory_events
        )

        if not (has_voided and has_price_dropped):
            return

        # New distress signal detected
        listing.distress_signal = True
        self.event_timeline.add_event(
            event_type=EventType.DISTRESS_SIGNAL,
            listing_id=listing.listing_id,
            metadata={
                "distress_window_days": self.distress_window_days,
                "reason": "AUCTION_VOIDED + PRICE_DROPPED within window",
            },
        )
        log.info(
            "Ingester: %s DISTRESS_SIGNAL detected (AUCTION_VOIDED + PRICE_DROPPED within %d days)",
            listing.listing_id,
            self.distress_window_days,
        )
        self.stats["events_generated"] += 1

        # Persist the updated distress_signal flag
        self.repository.upsert_listing(listing)

    def _save_events(self, listing_id: str) -> None:
        """
        Save events for a listing to database.

        Args:
            listing_id: Listing identifier
        """
        events = self.event_timeline.get_events_for_listing(listing_id)

        for event in events:
            # Check if event already exists (idempotency)
            existing_events = self.repository.get_listing_events(
                listing_id, event.event_type
            )

            # Simple check: if event with same type and timestamp exists, skip
            event_exists = any(
                e.get("timestamp") == event.timestamp.isoformat()
                for e in existing_events
            )

            if not event_exists:
                self.repository.add_event(event)

    def get_stats(self) -> dict:
        """
        Get ingestion statistics.

        Returns:
            Dictionary with statistics
        """
        return self.stats.copy()

    def reset_stats(self) -> None:
        """Reset ingestion statistics."""
        self.stats = {
            "processed": 0,
            "created": 0,
            "updated": 0,
            "events_generated": 0,
            "errors": 0,
        }

