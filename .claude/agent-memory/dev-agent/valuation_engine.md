---
name: Valuation Engine (M2-1/M2-2/M2-3)
description: Where valuation logic lives, how the price model works, JSON seed file pattern, and threshold boundary rules
type: project
---

All valuation logic lives in `models/src/models/valuation.py` (DEC-010). No DB deps — pure models/ package.

Key classes:

- `PriceModel` — loads `models/src/models/data/suburb_medians.json`, computes `suburb_median × bedroom_weight × property_type_multiplier`. Path overridable via `SUBURB_MEDIANS_PATH` env var.
- `compute_undervalue_score(listing_id, listed_price, estimated_price)` → `ValuationResult`
- `UndervaluationDetector(threshold_pct=10.0)` — in-memory state tracker, emits `UNDERVALUED_THRESHOLD_CROSSED` on state change only.

Enum additions in `enums.py`:

- `EventType.UNDERVALUED_THRESHOLD_CROSSED`
- `ValuationClassification` (SIGNIFICANTLY_UNDERVALUED ≥20%, UNDERVALUED ≥10%, FAIR_VALUE ≥-10%, OVERPRICED <-10%)

Boundary rule: threshold values belong to the _higher_ (more undervalued) band (uses `>=`).

`Listing` model gets three new Optional fields: `estimated_price`, `undervalue_score`, `valuation_classification`.

**Why:** DEC-004 keeps models/ DB-free. DEC-011 keeps suburb data updateable without code changes.
**How to apply:** When adding new valuation signals, add to valuation.py in models/. Never import DB clients from models/.
