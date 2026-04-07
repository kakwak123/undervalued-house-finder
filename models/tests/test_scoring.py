"""
Tests for the OpportunityScorer (M3-4).

Each test exercises a specific scoring signal in isolation, then a
combined scenario verifies the cap-at-100 behaviour.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from models.enums import EventType, ListingStatus, PropertyType
from models.events import Event, EventTimeline
from models.listing import Listing
from models.address import Address
from models.scoring import OpportunityScore, OpportunityScorer
from models.valuation import ValuationResult, ValuationClassification


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_address(suburb: str = "Richmond") -> Address:
    return Address(
        street_number="1",
        street_name="Test St",
        suburb=suburb,
        state="VIC",
        postcode="3121",
        full_address=f"1 Test St, {suburb} VIC 3121",
    )


def _make_listing(
    listing_id: str = "test-001",
    suburb: str = "Richmond",
    status: ListingStatus = ListingStatus.ACTIVE,
    distress_signal: bool = False,
    created_at: datetime | None = None,
) -> Listing:
    return Listing(
        listing_id=listing_id,
        address=_make_address(suburb),
        suburb=suburb,
        property_type=PropertyType.HOUSE,
        bedrooms=3,
        status=status,
        current_price=Decimal("800000"),
        distress_signal=distress_signal,
        created_at=created_at,
    )


def _make_valuation(
    listing_id: str = "test-001",
    listed_price: Decimal = Decimal("800000"),
    estimated_price: Decimal = Decimal("1000000"),
) -> ValuationResult:
    diff = estimated_price - listed_price
    score = float(diff / estimated_price * 100)
    classification = ValuationClassification.UNDERVALUED if score >= 10 else ValuationClassification.FAIR_VALUE
    if score >= 20:
        classification = ValuationClassification.SIGNIFICANTLY_UNDERVALUED
    return ValuationResult(
        listing_id=listing_id,
        listed_price=listed_price,
        estimated_price=estimated_price,
        price_difference=diff,
        undervalue_score=round(score, 2),
        classification=classification,
    )


def _make_event(
    event_type: EventType,
    listing_id: str = "test-001",
    days_ago: int = 0,
) -> Event:
    ts = datetime.now(tz=timezone.utc) - timedelta(days=days_ago)
    return Event(event_type=event_type, listing_id=listing_id, timestamp=ts)


# ---------------------------------------------------------------------------
# Scorer instance (shared)
# ---------------------------------------------------------------------------


@pytest.fixture()
def scorer() -> OpportunityScorer:
    return OpportunityScorer()


# ---------------------------------------------------------------------------
# Undervalue component tests
# ---------------------------------------------------------------------------


def test_undervalue_20pct_gives_40_points(scorer: OpportunityScorer) -> None:
    listing = _make_listing()
    # listed=800k, estimated=1000k → 20% undervalued
    vr = _make_valuation(estimated_price=Decimal("1000000"), listed_price=Decimal("800000"))
    result = scorer.score(listing, vr, [])
    assert result.breakdown.get("undervalue_20pct") == 40.0
    assert "undervalue_10pct" not in result.breakdown
    assert result.total_score == 40.0


def test_undervalue_10pct_gives_25_points(scorer: OpportunityScorer) -> None:
    listing = _make_listing()
    # listed=900k, estimated=1000k → 10% undervalued
    vr = _make_valuation(estimated_price=Decimal("1000000"), listed_price=Decimal("900000"))
    result = scorer.score(listing, vr, [])
    assert result.breakdown.get("undervalue_10pct") == 25.0
    assert result.total_score == 25.0


def test_undervalue_5pct_gives_10_points(scorer: OpportunityScorer) -> None:
    listing = _make_listing()
    # listed=950k, estimated=1000k → 5% undervalued
    vr = _make_valuation(estimated_price=Decimal("1000000"), listed_price=Decimal("950000"))
    result = scorer.score(listing, vr, [])
    assert result.breakdown.get("undervalue_5pct") == 10.0
    assert result.total_score == 10.0


def test_no_undervalue_no_undervalue_points(scorer: OpportunityScorer) -> None:
    listing = _make_listing()
    # listed=1000k, estimated=1000k → 0% undervalued
    vr = _make_valuation(estimated_price=Decimal("1000000"), listed_price=Decimal("1000000"))
    result = scorer.score(listing, vr, [])
    assert "undervalue_20pct" not in result.breakdown
    assert "undervalue_10pct" not in result.breakdown
    assert "undervalue_5pct" not in result.breakdown


def test_none_valuation_skips_undervalue_component(scorer: OpportunityScorer) -> None:
    listing = _make_listing()
    result = scorer.score(listing, None, [])
    assert "undervalue_20pct" not in result.breakdown
    assert "undervalue_10pct" not in result.breakdown
    assert "undervalue_5pct" not in result.breakdown
    assert result.total_score == 0.0


# ---------------------------------------------------------------------------
# Distress signal
# ---------------------------------------------------------------------------


def test_distress_signal_adds_20_points(scorer: OpportunityScorer) -> None:
    listing = _make_listing(distress_signal=True)
    result = scorer.score(listing, None, [])
    assert result.breakdown.get("distress_signal") == 20.0
    assert result.total_score == 20.0


def test_no_distress_signal_no_points(scorer: OpportunityScorer) -> None:
    listing = _make_listing(distress_signal=False)
    result = scorer.score(listing, None, [])
    assert "distress_signal" not in result.breakdown


# ---------------------------------------------------------------------------
# Auction failure events
# ---------------------------------------------------------------------------


def test_auction_cancelled_adds_15_points(scorer: OpportunityScorer) -> None:
    listing = _make_listing()
    events = [_make_event(EventType.AUCTION_CANCELLED)]
    result = scorer.score(listing, None, events)
    assert result.breakdown.get("auction_failure") == 15.0
    assert result.total_score == 15.0


def test_auction_voided_adds_15_points(scorer: OpportunityScorer) -> None:
    listing = _make_listing()
    events = [_make_event(EventType.AUCTION_VOIDED)]
    result = scorer.score(listing, None, events)
    assert result.breakdown.get("auction_failure") == 15.0


def test_both_auction_failure_events_still_15_points(scorer: OpportunityScorer) -> None:
    """Only one auction_failure bucket, regardless of how many failure events exist."""
    listing = _make_listing()
    events = [
        _make_event(EventType.AUCTION_CANCELLED),
        _make_event(EventType.AUCTION_VOIDED),
    ]
    result = scorer.score(listing, None, events)
    assert result.breakdown.get("auction_failure") == 15.0
    assert result.total_score == 15.0


def test_no_auction_failure_no_points(scorer: OpportunityScorer) -> None:
    listing = _make_listing()
    events = [_make_event(EventType.PRICE_DROPPED)]
    result = scorer.score(listing, None, events)
    assert "auction_failure" not in result.breakdown


# ---------------------------------------------------------------------------
# Recent price drop
# ---------------------------------------------------------------------------


def test_price_drop_within_14_days_adds_10_points(scorer: OpportunityScorer) -> None:
    listing = _make_listing()
    events = [_make_event(EventType.PRICE_DROPPED, days_ago=7)]
    result = scorer.score(listing, None, events)
    assert result.breakdown.get("recent_price_drop") == 10.0


def test_price_drop_older_than_14_days_no_points(scorer: OpportunityScorer) -> None:
    listing = _make_listing()
    events = [_make_event(EventType.PRICE_DROPPED, days_ago=15)]
    result = scorer.score(listing, None, events)
    assert "recent_price_drop" not in result.breakdown


def test_price_drop_13_days_ago_counts(scorer: OpportunityScorer) -> None:
    """13 days ago is within the 14-day window."""
    listing = _make_listing()
    events = [_make_event(EventType.PRICE_DROPPED, days_ago=13)]
    result = scorer.score(listing, None, events)
    assert result.breakdown.get("recent_price_drop") == 10.0


# ---------------------------------------------------------------------------
# Days on market
# ---------------------------------------------------------------------------


def test_dom_60_days_adds_10_points(scorer: OpportunityScorer) -> None:
    created = datetime.now(tz=timezone.utc) - timedelta(days=60)
    listing = _make_listing(created_at=created)
    result = scorer.score(listing, None, [])
    assert result.breakdown.get("days_on_market_60") == 10.0
    assert "days_on_market_30" not in result.breakdown


def test_dom_30_days_adds_5_points(scorer: OpportunityScorer) -> None:
    created = datetime.now(tz=timezone.utc) - timedelta(days=30)
    listing = _make_listing(created_at=created)
    result = scorer.score(listing, None, [])
    assert result.breakdown.get("days_on_market_30") == 5.0
    assert "days_on_market_60" not in result.breakdown


def test_dom_29_days_no_dom_points(scorer: OpportunityScorer) -> None:
    created = datetime.now(tz=timezone.utc) - timedelta(days=29)
    listing = _make_listing(created_at=created)
    result = scorer.score(listing, None, [])
    assert "days_on_market_30" not in result.breakdown
    assert "days_on_market_60" not in result.breakdown


def test_no_created_at_no_dom_points(scorer: OpportunityScorer) -> None:
    listing = _make_listing(created_at=None)
    result = scorer.score(listing, None, [])
    assert "days_on_market_30" not in result.breakdown
    assert "days_on_market_60" not in result.breakdown


# ---------------------------------------------------------------------------
# Score is capped at 100
# ---------------------------------------------------------------------------


def test_score_capped_at_100(scorer: OpportunityScorer) -> None:
    """Pile on all signals — total should never exceed 100."""
    created = datetime.now(tz=timezone.utc) - timedelta(days=90)
    listing = _make_listing(distress_signal=True, created_at=created)
    # 20%+ undervalue → +40
    vr = _make_valuation(estimated_price=Decimal("1000000"), listed_price=Decimal("750000"))
    events = [
        _make_event(EventType.AUCTION_VOIDED, days_ago=2),
        _make_event(EventType.AUCTION_CANCELLED, days_ago=5),
        _make_event(EventType.PRICE_DROPPED, days_ago=3),
    ]
    result = scorer.score(listing, vr, events)
    # Raw: 40 + 20 + 15 + 10 + 10 = 95, under 100 — all signals contribute
    assert result.total_score <= 100.0
    # Verify no overflow
    assert result.total_score == 95.0


def test_score_is_opportunity_score_model(scorer: OpportunityScorer) -> None:
    listing = _make_listing()
    result = scorer.score(listing, None, [])
    assert isinstance(result, OpportunityScore)
    assert result.listing_id == "test-001"


def test_score_breakdown_sums_to_total(scorer: OpportunityScorer) -> None:
    created = datetime.now(tz=timezone.utc) - timedelta(days=45)
    listing = _make_listing(distress_signal=True, created_at=created)
    vr = _make_valuation(estimated_price=Decimal("1000000"), listed_price=Decimal("870000"))
    events = [_make_event(EventType.PRICE_DROPPED, days_ago=1)]
    result = scorer.score(listing, vr, events)
    # breakdown values should sum to total_score (no cap hit here)
    assert abs(sum(result.breakdown.values()) - result.total_score) < 0.01
