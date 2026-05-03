"""
End-to-end tests for the valuation + opportunity scoring integration in
``Ingester``.

These cover the wiring added for issues #1, #2, #3, and #7:

- ``estimated_price``, ``undervalue_score``, ``valuation_classification``
  are populated on the listing before it is upserted.
- ``UNDERVALUED_THRESHOLD_CROSSED`` is emitted on the first crossing only.
- ``opportunity_score`` is computed using events from this run + the DB
  and is persisted via a follow-up upsert.
- ``_listing_to_dict`` serialises all four valuation/distress/opportunity
  columns so they actually reach Supabase.

No real Supabase / scraper credentials needed — uses MagicMock for the
repository, ``RealestateReader.from_data`` for normalisation, and a
seed-backed PriceModel.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

# Path wiring — mirrors test_pipeline.py
_repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(_repo_root / "models" / "src"))

from ingestion.database import SupabaseRepository
from ingestion.ingester import Ingester
from models.address import Address
from models.enums import EventType, ListingStatus, PropertyType, ValuationClassification
from models.listing import Listing
from models.scoring import OpportunityScorer
from models.valuation import PriceModel, UndervaluationDetector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_repository() -> MagicMock:
    """Mock SupabaseRepository that simulates a brand-new listing."""
    repo = MagicMock()
    repo.get_listing.return_value = None
    repo.upsert_listing.return_value = {}
    repo.get_listing_events.return_value = []
    repo.add_event.return_value = {}
    return repo


def _make_listing(
    listing_id: str = "TEST-1",
    suburb: str = "Hawthorn",  # has a real seed median
    property_type: PropertyType = PropertyType.HOUSE,
    bedrooms: int = 3,
    current_price: Decimal | None = Decimal("1000000"),
) -> Listing:
    return Listing(
        listing_id=listing_id,
        address=Address(
            street_number="1",
            street_name="Test St",
            suburb=suburb,
            state="VIC",
            postcode="3000",
            full_address=f"1 Test St, {suburb} VIC",
        ),
        suburb=suburb,
        property_type=property_type,
        bedrooms=bedrooms,
        current_price=current_price,
    )


def _captured_listing(repo: MagicMock, call_index: int = -1) -> Listing:
    """Return the Listing argument from the upsert call at *call_index*."""
    return repo.upsert_listing.call_args_list[call_index].args[0]


# ---------------------------------------------------------------------------
# Valuation wiring
# ---------------------------------------------------------------------------


class TestValuationWiring:
    def test_valuation_fields_populated_for_priced_listing(self) -> None:
        repo = _make_mock_repository()
        ingester = Ingester(repo)

        listing = _make_listing(current_price=Decimal("500000"))
        ingester._ingest_listing(listing)

        # The Listing object passed to upsert should have all valuation fields set
        captured = _captured_listing(repo, call_index=0)
        assert captured.estimated_price is not None
        assert captured.estimated_price > 0
        assert captured.undervalue_score is not None
        assert captured.valuation_classification is not None
        assert isinstance(captured.valuation_classification, ValuationClassification)

    def test_valuation_skipped_when_no_current_price(self) -> None:
        repo = _make_mock_repository()
        ingester = Ingester(repo)

        listing = _make_listing(current_price=None)
        ingester._ingest_listing(listing)

        captured = _captured_listing(repo, call_index=0)
        assert captured.estimated_price is None
        assert captured.undervalue_score is None
        assert captured.valuation_classification is None

    def test_significantly_undervalued_classification(self) -> None:
        """A very low listed price relative to suburb median should classify as significantly undervalued."""
        repo = _make_mock_repository()
        ingester = Ingester(repo)

        # Hawthorn 3-bed house — list at very low price → highly undervalued
        listing = _make_listing(suburb="Hawthorn", bedrooms=3, current_price=Decimal("100000"))
        ingester._ingest_listing(listing)

        captured = _captured_listing(repo, call_index=0)
        assert captured.undervalue_score is not None
        assert captured.undervalue_score >= 20.0
        assert captured.valuation_classification == ValuationClassification.SIGNIFICANTLY_UNDERVALUED

    def test_undervalued_threshold_crossed_emitted_once(self) -> None:
        """UNDERVALUED_THRESHOLD_CROSSED fires on first cross only."""
        repo = _make_mock_repository()
        ingester = Ingester(repo)

        # First ingest crosses the threshold (very undervalued)
        listing1 = _make_listing(listing_id="X1", current_price=Decimal("100000"))
        ingester._ingest_listing(listing1)

        events_after_first = ingester.event_timeline.get_events_for_listing("X1")
        threshold_events = [
            e for e in events_after_first if e.event_type == EventType.UNDERVALUED_THRESHOLD_CROSSED
        ]
        assert len(threshold_events) == 1

        # Second ingest with same data — no new event
        listing2 = _make_listing(listing_id="X1", current_price=Decimal("100000"))
        # Simulate "existing" so the update path is taken
        repo.get_listing.return_value = {
            "listing_id": "X1",
            "current_price": "100000",
            "status": "unknown",
            "auction_datetime": None,
        }
        ingester._ingest_listing(listing2)

        threshold_events_after_second = [
            e
            for e in ingester.event_timeline.get_events_for_listing("X1")
            if e.event_type == EventType.UNDERVALUED_THRESHOLD_CROSSED
        ]
        # Detector holds in-memory state — still exactly one
        assert len(threshold_events_after_second) == 1


# ---------------------------------------------------------------------------
# Opportunity score persistence
# ---------------------------------------------------------------------------


class TestOpportunityScorePersistence:
    def test_opportunity_score_persisted_for_priced_listing(self) -> None:
        repo = _make_mock_repository()
        ingester = Ingester(repo)

        # Highly undervalued listing → should get a non-zero score
        listing = _make_listing(suburb="Hawthorn", current_price=Decimal("100000"))
        ingester._ingest_listing(listing)

        # Last upsert call should have opportunity_score populated
        last = _captured_listing(repo, call_index=-1)
        assert last.opportunity_score is not None
        assert last.opportunity_score > 0
        assert last.opportunity_score <= 100

    def test_opportunity_score_includes_distress_bonus(self) -> None:
        """Distress signal contributes 20 points to the opportunity score."""
        repo = _make_mock_repository()
        ingester = Ingester(repo)

        listing = _make_listing(current_price=Decimal("500000"))
        listing.distress_signal = True
        ingester._ingest_listing(listing)

        last = _captured_listing(repo, call_index=-1)
        # The breakdown should include the distress bonus when distress=True
        assert last.opportunity_score is not None
        assert last.opportunity_score >= 20.0  # at minimum the distress 20 pts

    def test_opportunity_score_uses_db_events(self) -> None:
        """Score should reward an existing AUCTION_VOIDED event in the DB."""
        repo = _make_mock_repository()
        # Existing AUCTION_VOIDED event in db (from a prior run)
        repo.get_listing_events.return_value = [
            {
                "event_type": EventType.AUCTION_VOIDED.value,
                "timestamp": datetime.utcnow().isoformat(),
                "listing_id": "X2",
                "metadata": {},
            }
        ]
        ingester = Ingester(repo)

        listing = _make_listing(listing_id="X2", current_price=Decimal("500000"))
        ingester._ingest_listing(listing)

        last = _captured_listing(repo, call_index=-1)
        # Auction failure adds 15 pts
        assert last.opportunity_score is not None
        assert last.opportunity_score >= 15.0

    def test_no_score_when_no_signals_and_no_price(self) -> None:
        """Listing with no price and no events: opportunity_score stays None."""
        repo = _make_mock_repository()
        ingester = Ingester(repo)

        listing = _make_listing(current_price=None)
        ingester._ingest_listing(listing)

        last = _captured_listing(repo, call_index=-1)
        assert last.opportunity_score is None


# ---------------------------------------------------------------------------
# _listing_to_dict serialization
# ---------------------------------------------------------------------------


class TestListingToDictSerialization:
    """The serializer must include the M2/M3 columns or the DB write is silent-no-op."""

    def _serialize(self, listing: Listing) -> Dict[str, Any]:
        # Construct a SupabaseRepository without hitting Supabase
        repo = SupabaseRepository.__new__(SupabaseRepository)  # bypass __init__
        return repo._listing_to_dict(listing)

    def test_estimated_price_serialized(self) -> None:
        listing = _make_listing()
        listing.estimated_price = Decimal("750000")
        assert self._serialize(listing)["estimated_price"] == "750000"

    def test_undervalue_score_serialized(self) -> None:
        listing = _make_listing()
        listing.undervalue_score = 12.5
        assert self._serialize(listing)["undervalue_score"] == 12.5

    def test_valuation_classification_serialized_as_string(self) -> None:
        listing = _make_listing()
        listing.valuation_classification = ValuationClassification.UNDERVALUED
        assert self._serialize(listing)["valuation_classification"] == "undervalued"

    def test_distress_signal_serialized(self) -> None:
        listing = _make_listing()
        listing.distress_signal = True
        assert self._serialize(listing)["distress_signal"] is True

    def test_opportunity_score_serialized(self) -> None:
        listing = _make_listing()
        listing.opportunity_score = 55.0
        assert self._serialize(listing)["opportunity_score"] == 55.0

    def test_none_valuation_fields_serialized_as_none(self) -> None:
        listing = _make_listing()
        d = self._serialize(listing)
        assert d["estimated_price"] is None
        assert d["undervalue_score"] is None
        assert d["valuation_classification"] is None
        assert d["distress_signal"] is False
        assert d["opportunity_score"] is None


# ---------------------------------------------------------------------------
# Dependency injection
# ---------------------------------------------------------------------------


class TestDependencyInjection:
    """Ingester should accept injected price model / detector / scorer for testing."""

    def test_custom_price_model_is_used(self) -> None:
        repo = _make_mock_repository()

        class StubPriceModel:
            def estimate(self, suburb, property_type, bedrooms):
                return Decimal("999999")

        ingester = Ingester(repo, price_model=StubPriceModel())  # type: ignore[arg-type]

        listing = _make_listing(current_price=Decimal("500000"))
        ingester._ingest_listing(listing)

        captured = _captured_listing(repo, call_index=0)
        assert captured.estimated_price == Decimal("999999")

    def test_custom_detector_is_used(self) -> None:
        repo = _make_mock_repository()
        # Detector with very high threshold — should NOT emit even on big undervalue
        detector = UndervaluationDetector(threshold_pct=99.0)
        ingester = Ingester(repo, undervaluation_detector=detector)

        listing = _make_listing(current_price=Decimal("100000"))  # very undervalued
        ingester._ingest_listing(listing)

        threshold_events = [
            e
            for e in ingester.event_timeline.get_events_for_listing(listing.listing_id)
            if e.event_type == EventType.UNDERVALUED_THRESHOLD_CROSSED
        ]
        assert threshold_events == []

    def test_custom_scorer_is_used(self) -> None:
        repo = _make_mock_repository()

        class StubScorer:
            def score(self, listing, valuation_result, events):
                # Always return a fixed score
                from models.scoring import OpportunityScore
                return OpportunityScore(
                    listing_id=listing.listing_id,
                    total_score=42.0,
                    breakdown={"stub": 42.0},
                )

        ingester = Ingester(repo, opportunity_scorer=StubScorer())  # type: ignore[arg-type]

        listing = _make_listing(current_price=Decimal("500000"))
        ingester._ingest_listing(listing)

        last = _captured_listing(repo, call_index=-1)
        assert last.opportunity_score == 42.0
