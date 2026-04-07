"""
Undervalued House Finder — Public REST API (M4-1).

Run with:
    uvicorn api.main:app --reload --port 8001

Endpoints:
    GET /api/opportunities        — ranked list of undervalued listings (M4-2)
    GET /api/listings/{id}        — full listing + event timeline (M4-3)
    GET /api/listings             — filterable listing search (M4-4)
"""

from __future__ import annotations

import logging
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# sys.path: make models/ importable (DEC-001 — independent packages via sys.path)
# __file__ = api/src/api/main.py → parents[3] = project root
# ---------------------------------------------------------------------------
_project_root = Path(__file__).resolve().parents[3]
_models_src = _project_root / "models" / "src"
if str(_models_src) not in sys.path:
    sys.path.insert(0, str(_models_src))

from models.enums import EventType, PropertyType  # noqa: E402
from models.listing import Listing  # noqa: E402
from models.address import Address  # noqa: E402
from models.valuation import PriceModel, compute_undervalue_score  # noqa: E402
from models.scoring import OpportunityScorer, OpportunityScore  # noqa: E402
from models.events import Event  # noqa: E402

from api.database import ListingRepository, get_supabase_client  # noqa: E402

load_dotenv()

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Undervalued House Finder API",
    version="0.1.0",
    description="Opportunity scoring and listing search for Melbourne properties.",
)

_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Module-level singletons (created once on first request to avoid cold-start
# errors when Supabase env vars are missing in unit tests)
# ---------------------------------------------------------------------------

_price_model: Optional[PriceModel] = None
_scorer = OpportunityScorer()


def _get_price_model() -> PriceModel:
    global _price_model
    if _price_model is None:
        _price_model = PriceModel()
    return _price_model


def _get_repo() -> ListingRepository:
    return ListingRepository(get_supabase_client())


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class OpportunityItem(BaseModel):
    """Per-listing response for GET /api/opportunities."""

    listing_id: str
    address: str
    suburb: str
    bedrooms: Optional[int]
    property_type: str
    listed_price: Optional[str]
    estimated_price: Optional[str]
    undervalue_score: Optional[float]
    classification: Optional[str]
    total_score: float
    score_breakdown: Dict[str, float]
    active_signals: List[str]


class ListingDetail(BaseModel):
    """Full listing + events for GET /api/listings/{listing_id}."""

    listing_id: str
    address: Optional[Dict[str, Any]]
    suburb: str
    property_type: str
    bedrooms: Optional[int]
    bathrooms: Optional[int]
    status: str
    current_price: Optional[str]
    previous_price: Optional[str]
    auction_datetime: Optional[str]
    estimated_price: Optional[str]
    undervalue_score: Optional[float]
    valuation_classification: Optional[str]
    distress_signal: bool
    opportunity_score: Optional[float]
    property_link: Optional[str]
    description: Optional[str]
    source: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    events: List[Dict[str, Any]]


class ListingSummary(BaseModel):
    """Compact listing row for GET /api/listings."""

    listing_id: str
    suburb: str
    property_type: str
    bedrooms: Optional[int]
    status: str
    current_price: Optional[str]
    estimated_price: Optional[str]
    undervalue_score: Optional[float]
    distress_signal: bool
    property_link: Optional[str]
    address: Optional[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _address_string(row: Dict[str, Any]) -> str:
    """Best-effort single-line address from a listing row."""
    addr = row.get("address")
    if isinstance(addr, dict):
        return addr.get("full_address") or addr.get("suburb") or row.get("suburb", "")
    return row.get("suburb", "")


def _score_listing_row(row: Dict[str, Any], events_raw: List[Dict[str, Any]]) -> OpportunityScore:
    """
    Run valuation + scoring for a raw DB listing row and its events.

    Returns an OpportunityScore.  Never raises — returns zero score on error.
    """
    listing_id: str = row.get("listing_id", "")

    # Build a minimal Listing for the scorer
    try:
        suburb = row.get("suburb", "")
        pt_raw = row.get("property_type", "house")
        try:
            pt = PropertyType(pt_raw)
        except ValueError:
            pt = PropertyType.OTHER

        bedrooms_raw = row.get("bedrooms")
        bedrooms = int(bedrooms_raw) if bedrooms_raw is not None else None

        price_raw = row.get("current_price")
        current_price = Decimal(str(price_raw)) if price_raw else None

        distress = bool(row.get("distress_signal", False))

        created_at_raw = row.get("created_at")
        from datetime import datetime, timezone

        created_at = None
        if created_at_raw:
            try:
                created_at = datetime.fromisoformat(str(created_at_raw).replace("Z", "+00:00"))
            except ValueError:
                pass

        addr_raw = row.get("address") or {}
        address = Address(
            street_number=addr_raw.get("street_number", ""),
            street_name=addr_raw.get("street_name", ""),
            suburb=suburb,
            state=addr_raw.get("state", "VIC"),
            postcode=addr_raw.get("postcode", ""),
            full_address=addr_raw.get("full_address", suburb),
        )

        listing = Listing(
            listing_id=listing_id,
            address=address,
            suburb=suburb,
            property_type=pt,
            bedrooms=bedrooms,
            current_price=current_price,
            distress_signal=distress,
            created_at=created_at,
        )
    except Exception as exc:
        log.warning("_score_listing_row: could not build Listing for %s: %s", listing_id, exc)
        return OpportunityScore(listing_id=listing_id, total_score=0.0, breakdown={})

    # Valuation
    vr = None
    if current_price and current_price > 0:
        try:
            pm = _get_price_model()
            estimated = pm.estimate(suburb, pt, bedrooms)
            vr = compute_undervalue_score(listing_id, current_price, estimated)
        except Exception as exc:
            log.warning("_score_listing_row: valuation failed for %s: %s", listing_id, exc)

    # Convert raw event dicts to Event objects (best-effort)
    events: List[Event] = []
    for e in events_raw:
        try:
            from datetime import timezone as _tz

            ts_raw = e.get("timestamp")
            from datetime import datetime as _dt

            ts = _dt.fromisoformat(str(ts_raw).replace("Z", "+00:00")) if ts_raw else _dt.now(tz=_tz.utc)
            events.append(
                Event(
                    event_type=EventType(e["event_type"]),
                    listing_id=listing_id,
                    timestamp=ts,
                    metadata=e.get("metadata") or {},
                )
            )
        except Exception:
            pass

    return _scorer.score(listing, vr, events)


def _active_signals(events_raw: List[Dict[str, Any]], distress: bool) -> List[str]:
    """Return list of human-readable active signal names."""
    signals: List[str] = []
    seen_types = {e.get("event_type") for e in events_raw}
    if distress:
        signals.append("DISTRESS_SIGNAL")
    if EventType.AUCTION_CANCELLED.value in seen_types:
        signals.append("AUCTION_CANCELLED")
    if EventType.AUCTION_VOIDED.value in seen_types:
        signals.append("AUCTION_VOIDED")
    if EventType.AUCTION_RESCHEDULED.value in seen_types:
        signals.append("AUCTION_RESCHEDULED")
    if EventType.PRICE_DROPPED.value in seen_types:
        signals.append("PRICE_DROPPED")
    if EventType.UNDERVALUED_THRESHOLD_CROSSED.value in seen_types:
        signals.append("UNDERVALUED_THRESHOLD_CROSSED")
    return signals


# ---------------------------------------------------------------------------
# M4-2: GET /api/opportunities
# ---------------------------------------------------------------------------


@app.get("/api/opportunities", response_model=List[OpportunityItem])
def get_opportunities(
    limit: int = Query(default=20, ge=1, le=200, description="Max listings to return"),
    min_score: float = Query(default=0.0, ge=0, le=100, description="Minimum opportunity score"),
) -> List[OpportunityItem]:
    """
    Return listings ranked by composite opportunity score (highest first).

    Fetches listings from Supabase, runs valuation + scoring, filters by
    ``min_score``, and returns sorted by ``total_score`` descending.
    """
    repo = _get_repo()

    # Fetch more than limit so we have room to filter by min_score
    fetch_limit = min(limit * 5, 500)
    rows = repo.get_all_listings(limit=fetch_limit)

    results: List[OpportunityItem] = []
    for row in rows:
        listing_id = row.get("listing_id", "")
        events_raw = repo.get_events_for_listing(listing_id)
        opp_score = _score_listing_row(row, events_raw)

        if opp_score.total_score < min_score:
            continue

        # Compute valuation fields for response
        estimated_str: Optional[str] = row.get("estimated_price")
        undervalue_score: Optional[float] = None
        classification: Optional[str] = row.get("valuation_classification")

        price_raw = row.get("current_price")
        if price_raw:
            try:
                current_price = Decimal(str(price_raw))
                pm = _get_price_model()
                suburb = row.get("suburb", "")
                pt = PropertyType(row.get("property_type", "house"))
                bedrooms_raw = row.get("bedrooms")
                beds = int(bedrooms_raw) if bedrooms_raw is not None else None
                estimated = pm.estimate(suburb, pt, beds)
                estimated_str = str(estimated)
                from models.valuation import compute_undervalue_score as _cuv

                vr = _cuv(listing_id, current_price, estimated)
                undervalue_score = vr.undervalue_score
                classification = vr.classification.value
            except Exception:
                pass

        results.append(
            OpportunityItem(
                listing_id=listing_id,
                address=_address_string(row),
                suburb=row.get("suburb", ""),
                bedrooms=row.get("bedrooms"),
                property_type=row.get("property_type", ""),
                listed_price=str(price_raw) if price_raw else None,
                estimated_price=estimated_str,
                undervalue_score=undervalue_score,
                classification=classification,
                total_score=opp_score.total_score,
                score_breakdown=opp_score.breakdown,
                active_signals=_active_signals(events_raw, bool(row.get("distress_signal", False))),
            )
        )

    results.sort(key=lambda x: x.total_score, reverse=True)
    return results[:limit]


# ---------------------------------------------------------------------------
# M4-3: GET /api/listings/{listing_id}
# ---------------------------------------------------------------------------


@app.get("/api/listings/{listing_id}", response_model=ListingDetail)
def get_listing(listing_id: str) -> ListingDetail:
    """
    Return full listing details plus a chronological event timeline.
    """
    repo = _get_repo()
    row = repo.get_listing_by_id(listing_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Listing {listing_id!r} not found")

    events = repo.get_events_for_listing(listing_id)

    return ListingDetail(
        listing_id=listing_id,
        address=row.get("address"),
        suburb=row.get("suburb", ""),
        property_type=row.get("property_type", ""),
        bedrooms=row.get("bedrooms"),
        bathrooms=row.get("bathrooms"),
        status=row.get("status", "unknown"),
        current_price=str(row["current_price"]) if row.get("current_price") else None,
        previous_price=str(row["previous_price"]) if row.get("previous_price") else None,
        auction_datetime=row.get("auction_datetime"),
        estimated_price=str(row["estimated_price"]) if row.get("estimated_price") else None,
        undervalue_score=row.get("undervalue_score"),
        valuation_classification=row.get("valuation_classification"),
        distress_signal=bool(row.get("distress_signal", False)),
        opportunity_score=row.get("opportunity_score"),
        property_link=row.get("property_link"),
        description=row.get("description"),
        source=row.get("source"),
        created_at=str(row["created_at"]) if row.get("created_at") else None,
        updated_at=str(row["updated_at"]) if row.get("updated_at") else None,
        events=events,
    )


# ---------------------------------------------------------------------------
# M4-4: GET /api/listings
# ---------------------------------------------------------------------------


@app.get("/api/listings", response_model=List[ListingSummary])
def list_listings(
    suburb: Optional[str] = Query(default=None, description="Filter by suburb name"),
    property_type: Optional[str] = Query(default=None, description="Filter by property type"),
    min_price: Optional[float] = Query(default=None, ge=0, description="Minimum listed price (AUD)"),
    max_price: Optional[float] = Query(default=None, ge=0, description="Maximum listed price (AUD)"),
    min_undervalue_score: Optional[float] = Query(
        default=None, description="Minimum undervalue score (e.g. 10.0 for ≥10 % undervalued)"
    ),
    has_distress_signal: Optional[bool] = Query(default=None, description="Filter to distress-flagged listings"),
    limit: int = Query(default=50, ge=1, le=500, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> List[ListingSummary]:
    """
    Filterable listing search.

    Supports suburb, property_type, price range, undervalue score threshold,
    distress signal flag, and pagination.
    """
    repo = _get_repo()
    rows = repo.get_all_listings(
        limit=limit,
        offset=offset,
        suburb=suburb,
        property_type=property_type,
        min_price=min_price,
        max_price=max_price,
        min_undervalue_score=min_undervalue_score,
        has_distress_signal=has_distress_signal,
    )

    return [
        ListingSummary(
            listing_id=row.get("listing_id", ""),
            suburb=row.get("suburb", ""),
            property_type=row.get("property_type", ""),
            bedrooms=row.get("bedrooms"),
            status=row.get("status", "unknown"),
            current_price=str(row["current_price"]) if row.get("current_price") else None,
            estimated_price=str(row["estimated_price"]) if row.get("estimated_price") else None,
            undervalue_score=row.get("undervalue_score"),
            distress_signal=bool(row.get("distress_signal", False)),
            property_link=row.get("property_link"),
            address=row.get("address"),
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "undervalued-house-finder-api"}
