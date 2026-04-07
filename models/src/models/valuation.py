"""
Baseline price estimation and undervaluation scoring.

Implements three backlog items:

M2-1  PriceModel          — estimates property value from suburb median,
                            bedroom weighting, and property-type multiplier.
M2-2  ValuationResult     — compares estimated vs listed price and produces
                            an undervalue score and classification.
M2-3  UndervaluationDetector — detects when a listing crosses an undervaluation
                               threshold and emits UNDERVALUED_THRESHOLD_CROSSED
                               events (state-change only, not on every call).

All logic is pure Python / Pydantic v2.  No database dependencies.

Suburb median data is loaded from a JSON seed file whose path can be overridden
via the SUBURB_MEDIANS_PATH environment variable, allowing the data to be updated
without modifying source code.
"""

from __future__ import annotations

import json
import logging
import os
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .enums import EventType, PropertyType, ValuationClassification
from .events import EventTimeline

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default path for the suburb median seed file
# ---------------------------------------------------------------------------

_DEFAULT_DATA_PATH = Path(__file__).parent / "data" / "suburb_medians.json"


def _load_medians_data(path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load suburb median configuration from a JSON file.

    The file path is resolved in this order:
    1. ``path`` argument (if supplied)
    2. ``SUBURB_MEDIANS_PATH`` environment variable
    3. Default bundled seed file (``models/src/models/data/suburb_medians.json``)

    Args:
        path: Optional explicit path to a suburb medians JSON file.

    Returns:
        Parsed JSON dict.

    Raises:
        FileNotFoundError: If the resolved path does not exist.
        ValueError: If the JSON is missing required top-level keys.
    """
    resolved: Path
    if path is not None:
        resolved = Path(path)
    elif env_path := os.getenv("SUBURB_MEDIANS_PATH"):
        resolved = Path(env_path)
    else:
        resolved = _DEFAULT_DATA_PATH

    if not resolved.exists():
        raise FileNotFoundError(
            f"Suburb medians file not found: {resolved}. "
            "Set SUBURB_MEDIANS_PATH to an existing JSON file."
        )

    with open(resolved, encoding="utf-8") as fh:
        data: Dict[str, Any] = json.load(fh)

    required_keys = {"suburb_medians", "bedroom_weights", "property_type_multipliers", "fallback_median"}
    missing = required_keys - set(data.keys())
    if missing:
        raise ValueError(f"Suburb medians file is missing required keys: {missing}")

    return data


# ---------------------------------------------------------------------------
# M2-1  PriceModel
# ---------------------------------------------------------------------------


class PriceModel:
    """
    Estimates a property's market value using three factors:

    1. **Suburb median** — the baseline 3-bedroom house price for the suburb.
       Falls back to a Melbourne-wide median when the suburb is unknown.
    2. **Bedroom weight** — scales the median up/down based on bedroom count
       relative to the reference 3-bedroom house.
    3. **Property-type multiplier** — discounts or premiums vs a standalone house.

    ``estimated_price = suburb_median × bedroom_weight × property_type_multiplier``

    All configuration is loaded from the suburb medians JSON file.  To use a
    custom file, pass its path to the constructor or set ``SUBURB_MEDIANS_PATH``.

    [RESEARCH NEEDED] Bedroom weights and property-type multipliers in the seed
    file are conservative approximations.  They should be validated against
    actual Melbourne transaction data (e.g. CoreLogic RP Data) once available.
    """

    def __init__(self, medians_path: Optional[Path] = None) -> None:
        """
        Initialise the price model, loading suburb median data.

        Args:
            medians_path: Optional path to a suburb medians JSON file.
                          Defaults to the bundled seed file.
        """
        data = _load_medians_data(medians_path)
        self._suburb_medians: Dict[str, int] = {
            k: v for k, v in data["suburb_medians"].items() if not k.startswith("_")
        }
        raw_bw: Dict[str, Any] = data["bedroom_weights"]
        self._bedroom_weights: Dict[str, float] = {
            k: float(v) for k, v in raw_bw.items() if not k.startswith("_")
        }
        raw_pt: Dict[str, Any] = data["property_type_multipliers"]
        self._property_type_multipliers: Dict[str, float] = {
            k: float(v) for k, v in raw_pt.items() if not k.startswith("_")
        }
        self._fallback_median: int = int(data["fallback_median"])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def estimate(
        self,
        suburb: str,
        property_type: PropertyType,
        bedrooms: Optional[int],
    ) -> Decimal:
        """
        Estimate market value for a property.

        Args:
            suburb:        Suburb name (case-insensitive lookup).
            property_type: ``PropertyType`` enum value.
            bedrooms:      Number of bedrooms.  ``None`` uses the default weight (1.0).

        Returns:
            Estimated price rounded to the nearest dollar.
        """
        suburb_median = self._get_suburb_median(suburb)
        bedroom_weight = self._get_bedroom_weight(bedrooms)
        pt_multiplier = self._get_property_type_multiplier(property_type)

        raw = Decimal(str(suburb_median)) * Decimal(str(bedroom_weight)) * Decimal(str(pt_multiplier))
        return raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    def known_suburbs(self) -> list[str]:
        """Return all suburb names present in the seed data."""
        return list(self._suburb_medians.keys())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_suburb_median(self, suburb: str) -> int:
        """Look up suburb median, falling back gracefully on unknown suburbs."""
        # Exact match first, then title-case, then case-insensitive scan
        if suburb in self._suburb_medians:
            return self._suburb_medians[suburb]
        title = suburb.strip().title()
        if title in self._suburb_medians:
            return self._suburb_medians[title]
        lower = suburb.strip().lower()
        for key, val in self._suburb_medians.items():
            if key.lower() == lower:
                return val
        log.warning("PriceModel: suburb %r not found in seed data — using fallback median", suburb)
        return self._fallback_median

    def _get_bedroom_weight(self, bedrooms: Optional[int]) -> float:
        """Return bedroom weight for the given count."""
        if bedrooms is None:
            return self._bedroom_weights.get("default", 1.0)
        key = str(max(1, min(bedrooms, 6)))  # clamp to range present in seed data
        return self._bedroom_weights.get(key, self._bedroom_weights.get("default", 1.0))

    def _get_property_type_multiplier(self, property_type: PropertyType) -> float:
        """Return property-type multiplier for the given type."""
        key = property_type.value  # e.g. "house", "unit"
        return self._property_type_multipliers.get(
            key, self._property_type_multipliers.get("default", 1.0)
        )


# ---------------------------------------------------------------------------
# M2-2  ValuationResult + classify/score helpers
# ---------------------------------------------------------------------------

# Classification thresholds (percentage, positive = undervalued)
_SIGNIFICANTLY_UNDERVALUED_THRESHOLD = 20.0  # > 20 % below estimated
_UNDERVALUED_THRESHOLD = 10.0               # 10–20 % below estimated
_OVERPRICED_THRESHOLD = -10.0               # > 10 % above estimated


class ValuationResult(BaseModel):
    """
    Outcome of comparing a listing's asking price to its estimated value.

    ``undervalue_score = (estimated_price - listed_price) / estimated_price × 100``

    A positive score means the listing is priced *below* the estimate (undervalued).
    A negative score means it is priced *above* the estimate (overpriced).
    """

    listing_id: str = Field(..., description="Listing identifier")
    listed_price: Decimal = Field(..., description="Current asking price")
    estimated_price: Decimal = Field(..., description="Model-estimated value")
    price_difference: Decimal = Field(
        ..., description="estimated_price - listed_price (positive = undervalued)"
    )
    undervalue_score: float = Field(
        ...,
        description="(estimated - listed) / estimated × 100. Positive = undervalued.",
    )
    classification: ValuationClassification = Field(
        ..., description="Human-readable valuation band"
    )

    class Config:
        json_encoders = {Decimal: str}


def compute_undervalue_score(
    listing_id: str,
    listed_price: Decimal,
    estimated_price: Decimal,
) -> ValuationResult:
    """
    Compute the undervalue score and classification for a single listing.

    Args:
        listing_id:      Listing identifier (for the result record).
        listed_price:    Current asking price.
        estimated_price: Model-estimated value (from ``PriceModel.estimate``).

    Returns:
        A ``ValuationResult`` with score, difference, and classification.

    Raises:
        ValueError: If ``estimated_price`` is zero or negative.
    """
    if estimated_price <= 0:
        raise ValueError(f"estimated_price must be positive, got {estimated_price}")

    diff = estimated_price - listed_price
    score = float(diff / estimated_price * 100)
    classification = _classify(score)

    return ValuationResult(
        listing_id=listing_id,
        listed_price=listed_price,
        estimated_price=estimated_price,
        price_difference=diff,
        undervalue_score=round(score, 2),
        classification=classification,
    )


def _classify(undervalue_score: float) -> ValuationClassification:
    """
    Map an undervalue score to a classification band.

    Boundary values belong to the higher (more undervalued) band:
    - score >= 20  → SIGNIFICANTLY_UNDERVALUED
    - score >= 10  → UNDERVALUED
    - score >= -10 → FAIR_VALUE
    - score < -10  → OVERPRICED
    """
    if undervalue_score >= _SIGNIFICANTLY_UNDERVALUED_THRESHOLD:
        return ValuationClassification.SIGNIFICANTLY_UNDERVALUED
    elif undervalue_score >= _UNDERVALUED_THRESHOLD:
        return ValuationClassification.UNDERVALUED
    elif undervalue_score >= _OVERPRICED_THRESHOLD:
        return ValuationClassification.FAIR_VALUE
    else:
        return ValuationClassification.OVERPRICED


# ---------------------------------------------------------------------------
# M2-3  UndervaluationDetector
# ---------------------------------------------------------------------------


class UndervaluationDetector:
    """
    Detects when a listing crosses the undervaluation threshold and emits
    an ``UNDERVALUED_THRESHOLD_CROSSED`` event — but only on a *state change*.

    "State change" means:
    - The listing was NOT classified as undervalued on the previous call and
      IS classified as undervalued now (new crossing → emit event).
    - If it was already undervalued and remains undervalued on subsequent
      calls, no duplicate event is emitted.
    - If it moves from undervalued back to fair-value or overpriced, the
      state resets, allowing a future re-crossing to fire again.

    The detector maintains an in-memory set of listing IDs that are currently
    in an undervalued state.  This state is **not** persisted; each new
    process starts with a clean slate.  For persistent deduplication, the
    ``Ingester._save_events()`` timestamp-dedup mechanism in ``ingestion/``
    provides a second layer of protection.

    The threshold for triggering the event is configurable at construction
    time (default: 10 % — i.e. the ``UNDERVALUED`` band or higher).
    """

    def __init__(self, threshold_pct: float = 10.0) -> None:
        """
        Initialise the detector.

        Args:
            threshold_pct: Minimum undervalue score (%) that counts as
                           "undervalued" for event emission purposes.
                           Default is 10.0 (matches ``UNDERVALUED`` band).
        """
        if threshold_pct <= 0:
            raise ValueError("threshold_pct must be positive")
        self._threshold = threshold_pct
        # listing_id → bool: True if the listing was undervalued on the last check
        self._undervalued_state: Dict[str, bool] = {}

    def check(
        self,
        result: ValuationResult,
        event_timeline: EventTimeline,
    ) -> bool:
        """
        Check a valuation result and emit an event if the threshold is newly crossed.

        Args:
            result:         ``ValuationResult`` from ``compute_undervalue_score``.
            event_timeline: ``EventTimeline`` to append events to.

        Returns:
            ``True`` if an ``UNDERVALUED_THRESHOLD_CROSSED`` event was emitted,
            ``False`` otherwise.
        """
        listing_id = result.listing_id
        is_undervalued_now = result.undervalue_score >= self._threshold
        was_undervalued = self._undervalued_state.get(listing_id, False)

        # Update state regardless of whether we fire
        self._undervalued_state[listing_id] = is_undervalued_now

        if is_undervalued_now and not was_undervalued:
            # State change: not undervalued → undervalued — emit event
            event_timeline.add_event(
                event_type=EventType.UNDERVALUED_THRESHOLD_CROSSED,
                listing_id=listing_id,
                metadata={
                    "undervalue_score": result.undervalue_score,
                    "listed_price": str(result.listed_price),
                    "estimated_price": str(result.estimated_price),
                    "price_difference": str(result.price_difference),
                    "classification": result.classification.value,
                    "threshold_pct": self._threshold,
                },
            )
            log.info(
                "UndervaluationDetector: %s crossed threshold (score=%.1f%%, "
                "listed=%s, estimated=%s)",
                listing_id,
                result.undervalue_score,
                result.listed_price,
                result.estimated_price,
            )
            return True

        return False

    def reset(self, listing_id: str) -> None:
        """
        Clear the undervalued state for a single listing.

        Useful in tests or when a listing is removed from tracking.
        """
        self._undervalued_state.pop(listing_id, None)

    def is_undervalued(self, listing_id: str) -> bool:
        """Return the current undervalued state for a listing (default False)."""
        return self._undervalued_state.get(listing_id, False)
