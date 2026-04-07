#!/usr/bin/env python3
"""
run_scrapers.py — one command to scrape → ingest → score

Usage:
    python3 run_scrapers.py                        # both scrapers, default suburbs
    python3 run_scrapers.py --source domain        # domain only
    python3 run_scrapers.py --source realestate    # realestate only
    python3 run_scrapers.py --suburbs "Richmond,Fitzroy,Collingwood"

Env vars:
    DOMAIN_API_KEY          — required for domain scraper
    SUPABASE_URL            — required for ingestion
    SUPABASE_KEY            — required for ingestion
    REALESTATE_SEARCH_URL   — override default search URL
    REALESTATE_MAX_PAGES    — max pages per run (default 3)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger as log

load_dotenv()

# Fix import paths for models and ingestion packages (DEC-001)
_root = Path(__file__).resolve().parent
sys.path.insert(0, str(_root / "models" / "src"))
sys.path.insert(0, str(_root / "ingestion" / "src"))
sys.path.insert(0, str(_root / "scaper" / "domaincom-scraper"))
sys.path.insert(0, str(_root / "scaper" / "realestatecom-scraper"))

# ---------------------------------------------------------------------------
# Configure logging — human-readable with timing
# ---------------------------------------------------------------------------
log.remove()
log.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
    level="INFO",
    colorize=True,
)


# ---------------------------------------------------------------------------
# Scraper runners
# ---------------------------------------------------------------------------


async def run_domain_scraper(suburbs: list[str]) -> list[dict]:
    """Run the domain.com.au API scraper and return raw listing dicts."""
    from domaincom import scrape_domain

    log.info("=" * 60)
    log.info("DOMAIN.COM.AU — starting scrape for {} suburbs", len(suburbs))
    log.info("Suburbs: {}", ", ".join(suburbs))
    log.info("=" * 60)

    t0 = time.monotonic()
    try:
        listings = await scrape_domain(suburbs=suburbs)
        elapsed = time.monotonic() - t0
        log.success("Domain scrape complete — {} listings in {:.1f}s", len(listings), elapsed)
        return listings
    except EnvironmentError as e:
        log.error("Domain scraper config error: {}", e)
        log.warning("Skipping domain scraper. Set DOMAIN_API_KEY in .env to enable it.")
        return []
    except Exception as e:
        log.error("Domain scraper failed: {}", e)
        return []


async def run_realestate_scraper(suburbs: list[str]) -> list[dict]:
    """Run the realestate.com.au Playwright scraper and return raw listing dicts."""
    from realestate import scrape_search, scrape_properties, parse_property_data

    log.info("=" * 60)
    log.info("REALESTATE.COM.AU — starting Playwright scrape")
    log.info("Suburbs: {}", ", ".join(suburbs))
    log.info("=" * 60)

    t0 = time.monotonic()
    try:
        search_results = await scrape_search()
        elapsed = time.monotonic() - t0
        log.info("Search pages scraped — {} raw results in {:.1f}s", len(search_results), elapsed)

        # Extract property URLs/IDs from search results
        property_urls = [r.get("propertyLink") for r in search_results if r.get("propertyLink")]
        log.info("Fetching {} property detail pages...", len(property_urls))

        t1 = time.monotonic()
        listings = await scrape_properties(urls=property_urls)
        elapsed2 = time.monotonic() - t1
        log.success("REA scrape complete — {} listings in {:.1f}s", len(listings), elapsed2)
        return listings
    except Exception as e:
        log.error("REA scraper failed: {}", e)
        log.exception(e)
        return []


# ---------------------------------------------------------------------------
# Save to testdata/
# ---------------------------------------------------------------------------


def save_results(listings: list[dict], source: str) -> Path:
    """Save scraped listings to testdata/ with a timestamp."""
    testdata = _root / "testdata"
    testdata.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = testdata / f"{source}_{timestamp}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(listings, f, indent=2, default=str)
    log.info("Saved {} listings → {}", len(listings), out_path)
    return out_path


# ---------------------------------------------------------------------------
# Ingest into Supabase
# ---------------------------------------------------------------------------


def ingest(listings: list[dict], source: str) -> None:
    """Pipe listings directly into the ingester — no file step."""
    try:
        from ingestion.ingester import Ingester
        from ingestion.readers import RealestateReader, DomainReader

        log.info("=" * 60)
        log.info("INGESTING {} {} listings into Supabase...", len(listings), source)
        log.info("=" * 60)

        reader_cls = DomainReader if source == "domain" else RealestateReader
        reader = reader_cls.from_data(listings)
        normalized = reader.read()

        ingester = Ingester()
        result = ingester.ingest(normalized)
        log.success(
            "Ingestion complete — {} inserted, {} updated, {} unchanged",
            result.inserted,
            result.updated,
            result.unchanged,
        )
    except Exception as e:
        log.error("Ingestion failed: {}", e)
        log.warning("Listings saved to testdata/ — run ingest.py manually to retry")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Melbourne property listings")
    parser.add_argument("--source", choices=["domain", "realestate", "both"], default="both")
    parser.add_argument(
        "--suburbs",
        default="Richmond,Fitzroy,Collingwood,Brunswick,Northcote,St Kilda,South Yarra,Hawthorn",
        help="Comma-separated list of Melbourne suburbs",
    )
    parser.add_argument("--no-ingest", action="store_true", help="Skip ingestion, just save JSON")
    args = parser.parse_args()

    suburbs = [s.strip() for s in args.suburbs.split(",") if s.strip()]

    total_start = time.monotonic()
    all_results: dict[str, list[dict]] = {}

    if args.source in ("domain", "both"):
        listings = await run_domain_scraper(suburbs)
        if listings:
            save_results(listings, "domain")
            all_results["domain"] = listings

    if args.source in ("realestate", "both"):
        listings = await run_realestate_scraper(suburbs)
        if listings:
            save_results(listings, "realestate")
            all_results["realestate"] = listings

    total_elapsed = time.monotonic() - total_start
    total_listings = sum(len(v) for v in all_results.values())
    log.info("=" * 60)
    log.success("ALL SCRAPERS DONE — {} total listings in {:.1f}s", total_listings, total_elapsed)
    log.info("=" * 60)

    if not args.no_ingest and all_results:
        for source, listings in all_results.items():
            ingest(listings, source)
    elif args.no_ingest:
        log.info("Skipping ingestion (--no-ingest flag set)")
    else:
        log.warning("No listings scraped — nothing to ingest")


if __name__ == "__main__":
    asyncio.run(main())
