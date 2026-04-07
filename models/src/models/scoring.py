"""
Opportunity scoring engine (M3-4).

``OpportunityScorer`` produces a 0–100 composite score for a listing by
combining signals from the valuation engine, the event timeline, and basic
listing metadata (days on market).

Scoring formula (additive, capped at 100):
    +40  undervalue_score >= 20 %
    +25  undervalue_score >= 10 %
    +10  undervalue_score >= 5 %
    +20  listing has a DISTRESS_SIGNAL event
    +15  listing has AUCTION_CANCELLED or AUCTION_VOIDED event
    +10  listing has a PRICE_DROPPED event in the last 14 days
    +10  days_on_market >= 60
    +5   days_on_market >= 30

Only the highest applicable undervalue bracket contributes (they are mutually
exclusive in the additive formula); similarly, only the highest DOM bracket
contributes.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .enums import EventType
from .events import Event
from .listing import Listing
from .valuation import ValuationResult

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Days within which a PRICE_DROPPED event counts toward the score.
_RECENT_PRICE_DROP_DAYS = 14


# ---------------------------------------------------------------------------
# OpportunityScore model
# ---------------------------------------------------------------------------


class OpportunityScore(BaseModel):
    """
    Composite opportunity score for a property listing.

    ``total_score`` is in the range [0, 100].
    ``breakdown`` maps each signal name to the points it contributed.
    """

    listing_id: str = Field(..., description="Listing identifier")
    total_score: float = Field(..., ge=0, le=100, description="Composite score 0–100")
    breakdown: Dict[str, float] = Field(
        default_factory=dict,
        description="Per-signal point contributions that sum to total_score",
    )


# ---------------------------------------------------------------------------
# OpportunityScorer
# ---------------------------------------------------------------------------


class OpportunityScorer:
    """
    Scores a property listing on a 0–100 scale using:

    - Valuation undervalue percentage
    - Distress signal flag
    - Auction failure events (AUCTION_CANCELLED, AUCTION_VOIDED)
    - Recent price drops
    - Days on market
    """

    def score(
        self,
        listing: Listing,
        valuation_result: Optional[ValuationResult],
        events: List[Event],
    ) -> OpportunityScore:
        """
        Compute an OpportunityScore for *listing*.

        Args:
            listing:          The property listing to score.
            valuation_result: Valuation result from ``compute_undervalue_score``.
                              If ``None``, the undervalue component is skipped.
            events:           All events associated with this listing (typically
                              fetched from the DB or an EventTimeline).

        Returns:
            An ``OpportunityScore`` with ``total_score`` and ``breakdown``.
        """
        breakdown: Dict[str, float] = {}

        # ------------------------------------------------------------------
        # 1. Undervalue score component
        # ------------------------------------------------------------------
        if valuation_result is not None:
            uv = valuation_result.undervalue_score
            if uv >= 20.0:
                breakdown["undervalue_20pct"] = 40.0
            elif uv >= 10.0:
                breakdown["undervalue_10pct"] = 25.0
            elif uv >= 5.0:
                breakdown["undervalue_5pct"] = 10.0

        # ------------------------------------------------------------------
        # 2. Distress signal
        # ------------------------------------------------------------------
        if listing.distress_signal:
            breakdown["distress_signal"] = 20.0

        # ------------------------------------------------------------------
        # 3. Auction failure events (AUCTION_CANCELLED or AUCTION_VOIDED)
        # ------------------------------------------------------------------
        auction_failure_types = {EventType.AUCTION_CANCELLED, EventType.AUCTION_VOIDED}
        has_auction_failure = any(e.event_type in auction_failure_types for e in events)
        if has_auction_failure:
            breakdown["auction_failure"] = 15.0

        # ------------------------------------------------------------------
        # 4. Recent price drop (within _RECENT_PRICE_DROP_DAYS days)
        # ------------------------------------------------------------------
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=_RECENT_PRICE_DROP_DAYS)
        has_recent_price_drop = any(
            e.event_type == EventType.PRICE_DROPPED and _event_is_after(e, cutoff)
            for e in events
        )
        if has_recent_price_drop:
            breakdown["recent_price_drop"] = 10.0

        # ------------------------------------------------------------------
        # 5. Days on market
        # ------------------------------------------------------------------
        dom = _days_on_market(listing)
        if dom is not None:
            if dom >= 60:
                breakdown["days_on_market_60"] = 10.0
            elif dom >= 30:
                breakdown["days_on_market_30"] = 5.0

        # ------------------------------------------------------------------
        # Sum and cap at 100
        # ------------------------------------------------------------------
        raw_total = sum(breakdown.values())
        total = min(raw_total, 100.0)

        log.debug(
            "OpportunityScorer: %s total=%.1f breakdown=%s",
            listing.listing_id,
            total,
            breakdown,
        )

        return OpportunityScore(
            listing_id=listing.listing_id,
            total_score=round(total, 2),
            breakdown=breakdown,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event_is_after(event: Event, cutoff: datetime) -> bool:
    """Return True if the event's timestamp is on or after *cutoff*."""
    ts = event.timestamp
    # Normalise to offset-aware for comparison
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts >= cutoff


def _days_on_market(listing: Listing) -> Optional[int]:
    """
    Calculate days on market from ``listing.created_at`` to now.

    Returns ``None`` if ``created_at`` is not set.
    """
    if listing.created_at is None:
        return None
    now = datetime.now(tz=timezone.utc)
    created = listing.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    delta = now - created
    return max(0, delta.days)
