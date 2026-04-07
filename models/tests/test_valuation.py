"""
Tests for M2-1, M2-2, and M2-3: price model, undervalue scoring, and threshold detection.

All tests are offline (no DB, no Scrapfly, no network).
"""

from decimal import Decimal
from pathlib import Path
import json
import tempfile
import pytest

from models import (
    EventTimeline,
    EventType,
    PropertyType,
    ValuationClassification,
)
from models.valuation import (
    PriceModel,
    ValuationResult,
    UndervaluationDetector,
    compute_undervalue_score,
    _classify,
    _SIGNIFICANTLY_UNDERVALUED_THRESHOLD,
    _UNDERVALUED_THRESHOLD,
    _OVERPRICED_THRESHOLD,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SEED_PATH = Path(__file__).parent.parent / "src" / "models" / "data" / "suburb_medians.json"


def _make_minimal_medians_file(tmp_path: Path) -> Path:
    """Write a minimal valid medians JSON to a temp file."""
    data = {
        "suburb_medians": {
            "Testville": 1000000,
            "Cheapville": 500000,
        },
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
        "fallback_median": 850000,
    }
    p = tmp_path / "medians.json"
    p.write_text(json.dumps(data))
    return p


# ---------------------------------------------------------------------------
# M2-1  PriceModel tests
# ---------------------------------------------------------------------------


class TestPriceModel:
    def test_loads_bundled_seed_file(self) -> None:
        """Default constructor must load the bundled suburb_medians.json."""
        model = PriceModel()
        assert len(model.known_suburbs()) > 50  # seed file has many suburbs

    def test_known_suburb_house_3bed(self, tmp_path: Path) -> None:
        """Known suburb, 3-bed house → exactly the median (weights = 1.0 × 1.0)."""
        path = _make_minimal_medians_file(tmp_path)
        model = PriceModel(medians_path=path)
        price = model.estimate("Testville", PropertyType.HOUSE, bedrooms=3)
        assert price == Decimal("1000000")

    def test_bedroom_weight_applied(self, tmp_path: Path) -> None:
        """4-bed house should be > 3-bed house for same suburb."""
        path = _make_minimal_medians_file(tmp_path)
        model = PriceModel(medians_path=path)
        price_3 = model.estimate("Testville", PropertyType.HOUSE, bedrooms=3)
        price_4 = model.estimate("Testville", PropertyType.HOUSE, bedrooms=4)
        assert price_4 > price_3

    def test_bedroom_weight_2bed_less_than_3bed(self, tmp_path: Path) -> None:
        path = _make_minimal_medians_file(tmp_path)
        model = PriceModel(medians_path=path)
        price_2 = model.estimate("Testville", PropertyType.HOUSE, bedrooms=2)
        price_3 = model.estimate("Testville", PropertyType.HOUSE, bedrooms=3)
        assert price_2 < price_3

    def test_property_type_multiplier_applied(self, tmp_path: Path) -> None:
        """Unit should be priced below house for same suburb and bedroom count."""
        path = _make_minimal_medians_file(tmp_path)
        model = PriceModel(medians_path=path)
        house = model.estimate("Testville", PropertyType.HOUSE, bedrooms=3)
        unit = model.estimate("Testville", PropertyType.UNIT, bedrooms=3)
        assert unit < house

    def test_unit_multiplier_exact(self, tmp_path: Path) -> None:
        """Unit with 3-bed: median × 1.0 (bedrooms) × 0.72 (unit) = 720 000."""
        path = _make_minimal_medians_file(tmp_path)
        model = PriceModel(medians_path=path)
        price = model.estimate("Testville", PropertyType.UNIT, bedrooms=3)
        assert price == Decimal("720000")

    def test_unknown_suburb_uses_fallback(self, tmp_path: Path) -> None:
        """Suburb not in seed → fallback median, no exception."""
        path = _make_minimal_medians_file(tmp_path)
        model = PriceModel(medians_path=path)
        price = model.estimate("NoSuchSuburb", PropertyType.HOUSE, bedrooms=3)
        assert price == Decimal("850000")  # fallback_median

    def test_none_bedrooms_uses_default_weight(self, tmp_path: Path) -> None:
        """None bedrooms → default weight 1.0 → same as 3-bed house."""
        path = _make_minimal_medians_file(tmp_path)
        model = PriceModel(medians_path=path)
        price_none = model.estimate("Testville", PropertyType.HOUSE, bedrooms=None)
        price_3 = model.estimate("Testville", PropertyType.HOUSE, bedrooms=3)
        assert price_none == price_3

    def test_case_insensitive_suburb_lookup(self, tmp_path: Path) -> None:
        """Suburb lookup is case-insensitive."""
        path = _make_minimal_medians_file(tmp_path)
        model = PriceModel(medians_path=path)
        price_exact = model.estimate("Testville", PropertyType.HOUSE, bedrooms=3)
        price_lower = model.estimate("testville", PropertyType.HOUSE, bedrooms=3)
        price_upper = model.estimate("TESTVILLE", PropertyType.HOUSE, bedrooms=3)
        assert price_exact == price_lower == price_upper

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        """Non-existent path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            PriceModel(medians_path=tmp_path / "nonexistent.json")

    def test_missing_keys_raises(self, tmp_path: Path) -> None:
        """JSON missing required keys raises ValueError."""
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"suburb_medians": {}}))
        with pytest.raises(ValueError, match="missing required keys"):
            PriceModel(medians_path=bad)

    def test_env_var_overrides_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """SUBURB_MEDIANS_PATH env var is respected when no explicit path given."""
        path = _make_minimal_medians_file(tmp_path)
        monkeypatch.setenv("SUBURB_MEDIANS_PATH", str(path))
        model = PriceModel()  # no explicit path
        price = model.estimate("Testville", PropertyType.HOUSE, bedrooms=3)
        assert price == Decimal("1000000")

    def test_returns_decimal(self, tmp_path: Path) -> None:
        path = _make_minimal_medians_file(tmp_path)
        model = PriceModel(medians_path=path)
        price = model.estimate("Testville", PropertyType.HOUSE, bedrooms=3)
        assert isinstance(price, Decimal)

    def test_real_melbourne_suburb_present(self) -> None:
        """Dandenong North should be in the bundled seed data."""
        model = PriceModel()
        # Should not fall back (the suburb is in the seed file)
        price = model.estimate("Dandenong North", PropertyType.HOUSE, bedrooms=3)
        assert price > Decimal("500000")

    def test_bedroom_clamp_high(self, tmp_path: Path) -> None:
        """Bedrooms > 6 is clamped to 6 — no KeyError."""
        path = _make_minimal_medians_file(tmp_path)
        model = PriceModel(medians_path=path)
        price_6 = model.estimate("Testville", PropertyType.HOUSE, bedrooms=6)
        price_10 = model.estimate("Testville", PropertyType.HOUSE, bedrooms=10)
        assert price_6 == price_10

    def test_bedroom_clamp_low(self, tmp_path: Path) -> None:
        """Bedrooms <= 0 is clamped to 1 — no KeyError."""
        path = _make_minimal_medians_file(tmp_path)
        model = PriceModel(medians_path=path)
        price_1 = model.estimate("Testville", PropertyType.HOUSE, bedrooms=1)
        price_0 = model.estimate("Testville", PropertyType.HOUSE, bedrooms=0)
        assert price_1 == price_0


# ---------------------------------------------------------------------------
# M2-2  compute_undervalue_score / ValuationResult tests
# ---------------------------------------------------------------------------


class TestComputeUndervalueScore:
    def test_undervalued_listing(self) -> None:
        """Listed below estimated → positive score, undervalued classification."""
        result = compute_undervalue_score(
            listing_id="test-001",
            listed_price=Decimal("700000"),
            estimated_price=Decimal("800000"),
        )
        assert result.listing_id == "test-001"
        assert result.undervalue_score == pytest.approx(12.5, abs=0.01)
        assert result.price_difference == Decimal("100000")
        assert result.classification == ValuationClassification.UNDERVALUED

    def test_significantly_undervalued(self) -> None:
        """More than 20% below estimated → SIGNIFICANTLY_UNDERVALUED."""
        result = compute_undervalue_score(
            listing_id="test-002",
            listed_price=Decimal("600000"),
            estimated_price=Decimal("800000"),
        )
        assert result.undervalue_score == pytest.approx(25.0, abs=0.01)
        assert result.classification == ValuationClassification.SIGNIFICANTLY_UNDERVALUED

    def test_fair_value(self) -> None:
        """Within 10% of estimated → FAIR_VALUE."""
        result = compute_undervalue_score(
            listing_id="test-003",
            listed_price=Decimal("780000"),
            estimated_price=Decimal("800000"),
        )
        assert result.undervalue_score == pytest.approx(2.5, abs=0.01)
        assert result.classification == ValuationClassification.FAIR_VALUE

    def test_overpriced(self) -> None:
        """Listed above estimated by > 10% → OVERPRICED, negative score."""
        result = compute_undervalue_score(
            listing_id="test-004",
            listed_price=Decimal("920000"),
            estimated_price=Decimal("800000"),
        )
        assert result.undervalue_score == pytest.approx(-15.0, abs=0.01)
        assert result.classification == ValuationClassification.OVERPRICED

    def test_exact_at_estimated(self) -> None:
        """Listed price == estimated → score 0.0, FAIR_VALUE."""
        result = compute_undervalue_score(
            listing_id="test-005",
            listed_price=Decimal("800000"),
            estimated_price=Decimal("800000"),
        )
        assert result.undervalue_score == pytest.approx(0.0, abs=0.01)
        assert result.classification == ValuationClassification.FAIR_VALUE

    def test_exactly_at_undervalued_boundary(self) -> None:
        """Exactly 10% below → UNDERVALUED (not FAIR_VALUE)."""
        result = compute_undervalue_score(
            listing_id="test-006",
            listed_price=Decimal("720000"),
            estimated_price=Decimal("800000"),
        )
        assert result.undervalue_score == pytest.approx(10.0, abs=0.01)
        assert result.classification == ValuationClassification.UNDERVALUED

    def test_exactly_at_significant_boundary(self) -> None:
        """Exactly 20% below → SIGNIFICANTLY_UNDERVALUED (not UNDERVALUED)."""
        result = compute_undervalue_score(
            listing_id="test-007",
            listed_price=Decimal("640000"),
            estimated_price=Decimal("800000"),
        )
        assert result.undervalue_score == pytest.approx(20.0, abs=0.01)
        assert result.classification == ValuationClassification.SIGNIFICANTLY_UNDERVALUED

    def test_zero_estimated_raises(self) -> None:
        """Zero estimated_price raises ValueError."""
        with pytest.raises(ValueError):
            compute_undervalue_score(
                listing_id="test-bad",
                listed_price=Decimal("500000"),
                estimated_price=Decimal("0"),
            )

    def test_negative_estimated_raises(self) -> None:
        with pytest.raises(ValueError):
            compute_undervalue_score(
                listing_id="test-bad",
                listed_price=Decimal("500000"),
                estimated_price=Decimal("-100"),
            )

    def test_result_is_valuation_result_instance(self) -> None:
        result = compute_undervalue_score(
            listing_id="test-008",
            listed_price=Decimal("750000"),
            estimated_price=Decimal("800000"),
        )
        assert isinstance(result, ValuationResult)

    def test_price_difference_sign(self) -> None:
        """price_difference is positive when listed < estimated."""
        result = compute_undervalue_score(
            listing_id="test-009",
            listed_price=Decimal("600000"),
            estimated_price=Decimal("800000"),
        )
        assert result.price_difference > 0

    def test_price_difference_negative_when_overpriced(self) -> None:
        result = compute_undervalue_score(
            listing_id="test-010",
            listed_price=Decimal("900000"),
            estimated_price=Decimal("800000"),
        )
        assert result.price_difference < 0


# ---------------------------------------------------------------------------
# classify helper
# ---------------------------------------------------------------------------


class TestClassify:
    def test_significantly_undervalued(self) -> None:
        assert _classify(25.0) == ValuationClassification.SIGNIFICANTLY_UNDERVALUED
        assert _classify(20.1) == ValuationClassification.SIGNIFICANTLY_UNDERVALUED

    def test_undervalued(self) -> None:
        assert _classify(10.0) == ValuationClassification.UNDERVALUED
        assert _classify(15.0) == ValuationClassification.UNDERVALUED
        assert _classify(20.0) == ValuationClassification.SIGNIFICANTLY_UNDERVALUED  # boundary

    def test_fair_value(self) -> None:
        assert _classify(0.0) == ValuationClassification.FAIR_VALUE
        assert _classify(9.9) == ValuationClassification.FAIR_VALUE
        assert _classify(-9.9) == ValuationClassification.FAIR_VALUE
        assert _classify(-10.0) == ValuationClassification.FAIR_VALUE  # boundary inclusive

    def test_overpriced(self) -> None:
        assert _classify(-10.1) == ValuationClassification.OVERPRICED
        assert _classify(-25.0) == ValuationClassification.OVERPRICED


# ---------------------------------------------------------------------------
# M2-3  UndervaluationDetector tests
# ---------------------------------------------------------------------------


class TestUndervaluationDetector:
    def _make_result(
        self,
        listing_id: str,
        listed: int,
        estimated: int,
    ) -> ValuationResult:
        return compute_undervalue_score(
            listing_id=listing_id,
            listed_price=Decimal(str(listed)),
            estimated_price=Decimal(str(estimated)),
        )

    def test_fires_on_first_undervalued_check(self) -> None:
        """First time a listing is undervalued → event emitted."""
        detector = UndervaluationDetector(threshold_pct=10.0)
        timeline = EventTimeline()
        result = self._make_result("L1", listed=700000, estimated=800000)  # 12.5%
        fired = detector.check(result, timeline)
        assert fired is True
        events = timeline.get_events_for_listing("L1")
        assert len(events) == 1
        assert events[0].event_type == EventType.UNDERVALUED_THRESHOLD_CROSSED

    def test_does_not_fire_on_second_consecutive_undervalued_check(self) -> None:
        """Second call with same listing still undervalued → no duplicate event."""
        detector = UndervaluationDetector(threshold_pct=10.0)
        timeline = EventTimeline()
        result = self._make_result("L1", listed=700000, estimated=800000)
        detector.check(result, timeline)        # fires
        fired2 = detector.check(result, timeline)  # must NOT fire
        assert fired2 is False
        assert len(timeline.get_events_for_listing("L1")) == 1

    def test_does_not_fire_when_not_undervalued(self) -> None:
        """Fair-value listing → no event."""
        detector = UndervaluationDetector(threshold_pct=10.0)
        timeline = EventTimeline()
        result = self._make_result("L1", listed=780000, estimated=800000)  # 2.5%
        fired = detector.check(result, timeline)
        assert fired is False
        assert len(timeline.get_events_for_listing("L1")) == 0

    def test_fires_again_after_state_resets(self) -> None:
        """If listing goes fair→undervalued→fair→undervalued, fires twice total."""
        detector = UndervaluationDetector(threshold_pct=10.0)
        timeline = EventTimeline()

        under = self._make_result("L1", listed=700000, estimated=800000)   # 12.5%
        fair = self._make_result("L1", listed=790000, estimated=800000)    # 1.25%

        detector.check(under, timeline)   # fires (1)
        detector.check(fair, timeline)    # resets state
        fired3 = detector.check(under, timeline)  # fires again (2)

        assert fired3 is True
        assert len(timeline.get_events_for_listing("L1")) == 2

    def test_event_metadata_contains_score_and_prices(self) -> None:
        """Event metadata must include score, listed_price, estimated_price."""
        detector = UndervaluationDetector(threshold_pct=10.0)
        timeline = EventTimeline()
        result = self._make_result("L1", listed=700000, estimated=800000)
        detector.check(result, timeline)

        event = timeline.get_latest_event("L1", EventType.UNDERVALUED_THRESHOLD_CROSSED)
        assert event is not None
        assert "undervalue_score" in event.metadata
        assert "listed_price" in event.metadata
        assert "estimated_price" in event.metadata
        assert "classification" in event.metadata
        assert "threshold_pct" in event.metadata
        assert event.metadata["undervalue_score"] == pytest.approx(12.5, abs=0.01)

    def test_custom_threshold(self) -> None:
        """A 5% threshold fires for a 7% undervalued listing."""
        detector = UndervaluationDetector(threshold_pct=5.0)
        timeline = EventTimeline()
        result = self._make_result("L1", listed=744000, estimated=800000)  # 7%
        fired = detector.check(result, timeline)
        assert fired is True

    def test_custom_threshold_does_not_fire_below(self) -> None:
        """A 15% threshold does NOT fire for a 12% undervalued listing."""
        detector = UndervaluationDetector(threshold_pct=15.0)
        timeline = EventTimeline()
        result = self._make_result("L1", listed=704000, estimated=800000)  # 12%
        fired = detector.check(result, timeline)
        assert fired is False

    def test_invalid_threshold_raises(self) -> None:
        with pytest.raises(ValueError):
            UndervaluationDetector(threshold_pct=0.0)
        with pytest.raises(ValueError):
            UndervaluationDetector(threshold_pct=-5.0)

    def test_is_undervalued_reflects_state(self) -> None:
        detector = UndervaluationDetector(threshold_pct=10.0)
        timeline = EventTimeline()
        result = self._make_result("L1", listed=700000, estimated=800000)
        assert detector.is_undervalued("L1") is False
        detector.check(result, timeline)
        assert detector.is_undervalued("L1") is True

    def test_reset_clears_state(self) -> None:
        detector = UndervaluationDetector(threshold_pct=10.0)
        timeline = EventTimeline()
        result = self._make_result("L1", listed=700000, estimated=800000)
        detector.check(result, timeline)
        detector.reset("L1")
        assert detector.is_undervalued("L1") is False
        # Should fire again after reset
        fired = detector.check(result, timeline)
        assert fired is True

    def test_independent_listings_tracked_separately(self) -> None:
        """Two different listings have independent undervalued states."""
        detector = UndervaluationDetector(threshold_pct=10.0)
        timeline = EventTimeline()

        under_l1 = self._make_result("L1", listed=700000, estimated=800000)
        fair_l2 = self._make_result("L2", listed=790000, estimated=800000)

        detector.check(under_l1, timeline)
        detector.check(fair_l2, timeline)

        assert detector.is_undervalued("L1") is True
        assert detector.is_undervalued("L2") is False
        assert len(timeline.get_events_for_listing("L1")) == 1
        assert len(timeline.get_events_for_listing("L2")) == 0

    def test_significantly_undervalued_triggers_event(self) -> None:
        """25% undervalued (> significantly_undervalued threshold) still fires."""
        detector = UndervaluationDetector(threshold_pct=10.0)
        timeline = EventTimeline()
        result = self._make_result("L1", listed=600000, estimated=800000)  # 25%
        fired = detector.check(result, timeline)
        assert fired is True
        event = timeline.get_latest_event("L1", EventType.UNDERVALUED_THRESHOLD_CROSSED)
        assert event is not None
        assert event.metadata["classification"] == ValuationClassification.SIGNIFICANTLY_UNDERVALUED.value
