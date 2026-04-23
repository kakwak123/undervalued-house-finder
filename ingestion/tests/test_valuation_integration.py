"""
Integration tests for the valuation engine wiring inside the Ingester.

Covers backlog items #1, #2, #3:
- #1 Baseline estimated price model — estimated_price is computed and persisted
- #2 Compare estimated price vs listing price — undervalue_score + classification
     are computed and persisted
- #3 Undervaluation threshold detection — UNDERVALUED_THRESHOLD_CROSSED event
     is emitted once on state change, not on every ingest

All tests use an in-memory mock repository — no Supabase credentials required.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

# Path wiring — mirrors test_pipeline.py
_repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(_repo_root / "models" / "src"))

from ingestion.ingester import Ingester  # noqa: E402
from models import EventType, ListingStatus, PropertyType  # noqa: E402
from models.address import Address  # noqa: E402
from models.listing import Listing  # noqa: E402
from models.valuation import PriceModel, UndervaluationDetector  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_repo(existing: Dict[str, Any] | None = None) -> MagicMock:
    repo = MagicMock()
    repo.get_listing.return_value = existing
    repo.upsert_listing.return_value = {}
    repo.get_listing_events.return_value = []
    repo.add_event.return_value = {}
    return repo


def _make_listing(
    listing_id: str = "L1",
    suburb: str = "Testville",
    property_type: PropertyType = PropertyType.HOUSE,
    bedrooms: int = 3,
    current_price: Decimal | None = Decimal("700000"),
) -> Listing:
    return Listing(
        listing_id=listing_id,
        address=Address(
            street_number="1",
            street_name="Example St",
            suburb=suburb,
            state="Vic",
            postcode="3000",
            full_address=f"1 Example St, {suburb}, Vic 3000",
        ),
        suburb=suburb,
        property_type=property_type,
        bedrooms=bedrooms,
        status=ListingStatus.UNKNOWN,
        current_price=current_price,
    )


def _tiny_price_model(tmp_path: Path, median: int = 1_000_000) -> PriceModel:
    """Build a PriceModel from a minimal seed file with a controllable median."""
    import json

    data = {
        "suburb_medians": {"Testville": median},
        "bedroom_weights": {
            "1": 0.65,
            "2": 0.82,
            "3": 1.00,
            "4": 1.18,
            "5": 1.34,
            "6": 1.48,
            "default": 1.00,
        },
        "property_type_multipliers": {
            "house": 1.00,
            "unit": 0.72,
            "apartment": 0.72,
            "townhouse": 0.88,
            "villa": 0.85,
            "studio": 0.55,
            "land": 0.60,
            "other": 0.90,
            "default": 1.00,
        },
        "fallback_median": 800_000,
    }
    p = tmp_path / "medians.json"
    p.write_text(json.dumps(data))
    return PriceModel(medians_path=p)


def _captured_upsert_payloads(repo: MagicMock) -> List[Listing]:
    """Return the Listing objects passed to repo.upsert_listing, in call order."""
    return [call.args[0] for call in repo.upsert_listing.call_args_list]


# ---------------------------------------------------------------------------
# #1: estimated_price computed and populated
# ---------------------------------------------------------------------------


class TestEstimatedPricePopulated:
    def test_new_listing_has_estimated_price(self, tmp_path: Path) -> None:
        repo = _make_mock_repo(existing=None)
        ingester = Ingester(
            repo,
            price_model=_tiny_price_model(tmp_path, median=1_000_000),
        )
        listing = _make_listing(current_price=Decimal("700000"))
        ingester._ingest_listing(listing)

        # 3-bed house in Testville → median × 1.0 × 1.0 = 1 000 000
        assert listing.estimated_price == Decimal("1000000")

        payloads = _captured_upsert_payloads(repo)
        assert payloads, "upsert_listing must be called"
        assert payloads[0].estimated_price == Decimal("1000000")

    def test_unit_applies_property_type_multiplier(self, tmp_path: Path) -> None:
        repo = _make_mock_repo(existing=None)
        ingester = Ingester(
            repo,
            price_model=_tiny_price_model(tmp_path, median=1_000_000),
        )
        listing = _make_listing(property_type=PropertyType.UNIT, current_price=Decimal("600000"))
        ingester._ingest_listing(listing)
        # 1 000 000 × 1.0 × 0.72 = 720 000
        assert listing.estimated_price == Decimal("720000")

    def test_recomputed_on_update(self, tmp_path: Path) -> None:
        """When a listing is updated, estimated_price is recomputed (data-change AC)."""
        repo = _make_mock_repo(
            existing={
                "listing_id": "L1",
                "current_price": "900000",
                "status": "unknown",
                "auction_datetime": None,
            }
        )
        ingester = Ingester(
            repo,
            price_model=_tiny_price_model(tmp_path, median=1_000_000),
        )
        listing = _make_listing(current_price=Decimal("700000"))
        # Stale estimate on the incoming listing — must be overwritten
        listing.estimated_price = Decimal("1")
        ingester._ingest_listing(listing)
        assert listing.estimated_price == Decimal("1000000")


# ---------------------------------------------------------------------------
# #2: undervalue score + classification populated
# ---------------------------------------------------------------------------


class TestUndervalueScorePopulated:
    def test_score_and_classification_set(self, tmp_path: Path) -> None:
        repo = _make_mock_repo(existing=None)
        ingester = Ingester(
            repo,
            price_model=_tiny_price_model(tmp_path, median=1_000_000),
        )
        # Listed 700k vs estimated 1M → 30% below → significantly undervalued
        listing = _make_listing(current_price=Decimal("700000"))
        ingester._ingest_listing(listing)

        assert listing.undervalue_score == pytest.approx(30.0, abs=0.01)
        assert listing.valuation_classification is not None
        assert listing.valuation_classification.value == "significantly_undervalued"

    def test_fair_value_when_close_to_estimate(self, tmp_path: Path) -> None:
        repo = _make_mock_repo(existing=None)
        ingester = Ingester(
            repo,
            price_model=_tiny_price_model(tmp_path, median=1_000_000),
        )
        listing = _make_listing(current_price=Decimal("980000"))  # 2% below
        ingester._ingest_listing(listing)
        assert listing.valuation_classification.value == "fair_value"

    def test_overpriced_produces_negative_score(self, tmp_path: Path) -> None:
        repo = _make_mock_repo(existing=None)
        ingester = Ingester(
            repo,
            price_model=_tiny_price_model(tmp_path, median=1_000_000),
        )
        listing = _make_listing(current_price=Decimal("1200000"))  # 20% above
        ingester._ingest_listing(listing)
        assert listing.undervalue_score < 0
        assert listing.valuation_classification.value == "overpriced"

    def test_no_current_price_yields_no_score(self, tmp_path: Path) -> None:
        """estimated_price is still set, but score is undefined without a listed price."""
        repo = _make_mock_repo(existing=None)
        ingester = Ingester(
            repo,
            price_model=_tiny_price_model(tmp_path, median=1_000_000),
        )
        listing = _make_listing(current_price=None)
        ingester._ingest_listing(listing)

        assert listing.estimated_price == Decimal("1000000")
        assert listing.undervalue_score is None
        assert listing.valuation_classification is None


# ---------------------------------------------------------------------------
# #3: UNDERVALUED_THRESHOLD_CROSSED event emitted on state change only
# ---------------------------------------------------------------------------


class TestUndervaluedThresholdEvent:
    def test_event_emitted_when_newly_undervalued(self, tmp_path: Path) -> None:
        repo = _make_mock_repo(existing=None)
        ingester = Ingester(
            repo,
            price_model=_tiny_price_model(tmp_path, median=1_000_000),
            undervaluation_detector=UndervaluationDetector(threshold_pct=10.0),
        )
        listing = _make_listing(current_price=Decimal("700000"))  # 30% undervalued
        ingester._ingest_listing(listing)

        events = ingester.event_timeline.get_events_for_listing("L1")
        assert any(e.event_type == EventType.UNDERVALUED_THRESHOLD_CROSSED for e in events)

    def test_no_event_for_fair_value_listing(self, tmp_path: Path) -> None:
        repo = _make_mock_repo(existing=None)
        ingester = Ingester(
            repo,
            price_model=_tiny_price_model(tmp_path, median=1_000_000),
        )
        listing = _make_listing(current_price=Decimal("980000"))  # 2% below
        ingester._ingest_listing(listing)

        events = ingester.event_timeline.get_events_for_listing("L1")
        assert not any(e.event_type == EventType.UNDERVALUED_THRESHOLD_CROSSED for e in events)

    def test_event_not_duplicated_on_second_ingest(self, tmp_path: Path) -> None:
        """Second ingest of an already-undervalued listing must not re-emit the event."""
        repo = _make_mock_repo(existing=None)
        ingester = Ingester(
            repo,
            price_model=_tiny_price_model(tmp_path, median=1_000_000),
        )
        listing1 = _make_listing(current_price=Decimal("700000"))
        ingester._ingest_listing(listing1)

        # Simulate second ingestion round (detector keeps in-memory state)
        repo.get_listing.return_value = {
            "listing_id": "L1",
            "current_price": "700000",
            "status": "unknown",
            "auction_datetime": None,
        }
        listing2 = _make_listing(current_price=Decimal("700000"))
        ingester._ingest_listing(listing2)

        events = ingester.event_timeline.get_events_for_listing("L1")
        crossed = [e for e in events if e.event_type == EventType.UNDERVALUED_THRESHOLD_CROSSED]
        assert len(crossed) == 1


# ---------------------------------------------------------------------------
# Persistence: valuation fields are included in the upsert payload
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_valuation_fields_serialised_via_database_helper(self, tmp_path: Path) -> None:
        """The _listing_to_dict helper must include the valuation fields for DB write."""
        from ingestion.database import SupabaseRepository

        # Build a listing with valuation fields populated — no network calls needed
        # because _listing_to_dict is a pure serialiser.
        listing = _make_listing(current_price=Decimal("700000"))
        listing.estimated_price = Decimal("1000000")
        listing.undervalue_score = 30.0
        from models.enums import ValuationClassification

        listing.valuation_classification = ValuationClassification.SIGNIFICANTLY_UNDERVALUED

        # Bypass __init__ (which creates a real Supabase client) — we only need
        # the unbound method behaviour.
        data = SupabaseRepository._listing_to_dict(SupabaseRepository.__new__(SupabaseRepository), listing)

        assert data["estimated_price"] == "1000000"
        assert data["undervalue_score"] == 30.0
        assert data["valuation_classification"] == "significantly_undervalued"
        assert data["distress_signal"] is False
