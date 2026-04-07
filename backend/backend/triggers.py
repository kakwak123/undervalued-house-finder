"""Manual trigger handlers called by the REST API endpoints.

Scraper and ingestion triggers are simulated (no API keys in dev).
Valuation trigger uses the real PriceModel + compute_undervalue_score.
"""

from __future__ import annotations

import asyncio
import random
import sys
from decimal import Decimal
from pathlib import Path
from typing import Dict, List

# Allow importing models/ without a shared lockfile (DEC-001)
# __file__ = backend/backend/triggers.py → parents[2] = project root
_models_src = Path(__file__).resolve().parents[2] / "models" / "src"
if str(_models_src) not in sys.path:
    sys.path.insert(0, str(_models_src))

from models.enums import PropertyType  # noqa: E402
from models.valuation import PriceModel, compute_undervalue_score  # noqa: E402

from backend.event_bus import EventCategory, clear_buffer, publish
from backend.health import set_scraper_status, set_supabase_status

_price_model = PriceModel()


async def run_scraper() -> Dict[str, str]:
    """Simulate a scraper run by emitting a series of SCRAPING events.

    # TODO: wire to real scraper (scaper/realestatecom-scraper or scaper/domaincom-scraper)
    """
    set_scraper_status("ok", "Scraper triggered manually")
    await publish(EventCategory.SYSTEM, "Scraper triggered manually")

    suburbs = ["Richmond", "Fitzroy", "Collingwood", "Brunswick", "Northcote"]
    base_url = "https://www.realestate.com.au/buy/in-{suburb},+vic/"

    for suburb in suburbs:
        url = base_url.format(suburb=suburb.lower())
        await asyncio.sleep(0.05)  # Simulate async I/O — not a real HTTP delay.
        listings_found = random.randint(8, 35)
        response_ms = random.randint(340, 1800)
        await publish(
            EventCategory.SCRAPING,
            f"Fetched {suburb}: {listings_found} listings in {response_ms}ms",
            detail={
                "url": url,
                "status": 200,
                "ms": response_ms,
                "count": listings_found,
            },
        )

    await publish(EventCategory.SYSTEM, "Scraper run complete")
    set_scraper_status("ok", "Last run completed successfully")
    return {"status": "ok", "message": "Scraper simulation complete"}


async def run_ingestion() -> Dict[str, str]:
    """Simulate an ingestion run by emitting INGESTING and DB_WRITE events.

    # TODO: wire to real ingestion pipeline (ingestion/ingest.py)
    """
    set_supabase_status("ok", "Ingestion triggered manually")
    await publish(EventCategory.SYSTEM, "Ingestion triggered manually")

    listing_ids = [f"prop-{random.randint(10000, 99999)}" for _ in range(6)]

    for listing_id in listing_ids:
        await asyncio.sleep(0.03)
        action = random.choice(["inserted", "updated", "no change"])
        await publish(
            EventCategory.INGESTING,
            f"Listing {listing_id}: {action}",
            detail={"listing_id": listing_id, "action": action},
        )
        if action != "no change":
            await asyncio.sleep(0.02)
            await publish(
                EventCategory.DB_WRITE,
                f"DB upsert: listings/{listing_id}",
                detail={"listing_id": listing_id, "table": "listings"},
            )

    # Simulate a price drop event.
    dropped_id = random.choice(listing_ids)
    await publish(
        EventCategory.EVENT,
        f"PRICE_DROPPED detected for {dropped_id}",
        detail={"listing_id": dropped_id, "event_type": "PRICE_DROPPED"},
    )
    await publish(
        EventCategory.DB_WRITE,
        f"DB insert: events/{dropped_id}/PRICE_DROPPED",
        detail={"listing_id": dropped_id, "table": "events"},
    )

    await publish(EventCategory.SYSTEM, "Ingestion run complete")
    set_supabase_status("ok", "Last ingestion completed successfully")
    return {"status": "ok", "message": "Ingestion simulation complete"}


async def run_valuation() -> Dict[str, str]:
    """Run the real valuation engine across a sample of Melbourne listings."""
    await publish(EventCategory.SYSTEM, "Valuation run triggered manually")

    # Sample listings: (suburb, property_type, bedrooms, listed_price)
    sample_listings: List[tuple] = [
        ("Richmond", PropertyType.HOUSE, 3, Decimal("1_350_000")),
        ("Richmond", PropertyType.UNIT, 2, Decimal("620_000")),
        ("Fitzroy", PropertyType.HOUSE, 4, Decimal("1_800_000")),
        ("Fitzroy", PropertyType.TOWNHOUSE, 3, Decimal("1_050_000")),
        ("Collingwood", PropertyType.UNIT, 1, Decimal("490_000")),
        ("Collingwood", PropertyType.HOUSE, 3, Decimal("1_150_000")),
        ("Brunswick", PropertyType.HOUSE, 3, Decimal("980_000")),
        ("Brunswick", PropertyType.UNIT, 2, Decimal("560_000")),
        ("Northcote", PropertyType.HOUSE, 4, Decimal("1_600_000")),
        ("St Kilda", PropertyType.UNIT, 2, Decimal("750_000")),
        ("Hawthorn", PropertyType.HOUSE, 4, Decimal("2_600_000")),
        ("Preston", PropertyType.HOUSE, 3, Decimal("820_000")),
    ]

    results = []
    for suburb, prop_type, beds, listed in sample_listings:
        await asyncio.sleep(0.02)
        listing_id = f"{suburb.lower().replace(' ', '-')}-{prop_type.value}-{beds}br"
        estimated = _price_model.estimate(suburb, prop_type, beds)
        result = compute_undervalue_score(listing_id, listed, estimated)
        results.append(result)
        await publish(
            EventCategory.VALUATION,
            f"{suburb} {beds}br {prop_type.value}: listed ${listed:,} | estimated ${estimated:,} | score {result.undervalue_score:+.1f}% → {result.classification.value}",
            detail={
                "listing_id": listing_id,
                "suburb": suburb,
                "property_type": prop_type.value,
                "bedrooms": beds,
                "listed_price": str(listed),
                "estimated_price": str(estimated),
                "undervalue_score": result.undervalue_score,
                "classification": result.classification.value,
            },
        )

    undervalued_count = sum(1 for r in results if r.undervalue_score >= 10.0)
    avg_score = sum(r.undervalue_score for r in results) / len(results)
    await publish(
        EventCategory.SYSTEM,
        f"Valuation complete: {len(results)} listings scored, {undervalued_count} undervalued, avg score {avg_score:+.1f}%",
    )
    return {"status": "ok", "message": f"Scored {len(results)} listings, {undervalued_count} undervalued"}


async def reset_events() -> Dict[str, str]:
    """Clear the in-memory ring buffer and notify subscribers."""
    clear_buffer()
    await publish(EventCategory.SYSTEM, "Event buffer reset by user")
    return {"status": "ok", "message": "Event buffer cleared"}
