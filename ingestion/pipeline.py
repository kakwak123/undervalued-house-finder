#!/usr/bin/env python3
"""
Scrape-to-ingest pipeline CLI.

Runs a scraper and feeds results directly into the ingester without writing
any intermediate JSON file.

Usage::

    # realestate.com.au
    python3 pipeline.py realestate "https://www.realestate.com.au/buy/..." --pages 3

    # domain.com.au
    python3 pipeline.py domain "https://www.domain.com.au/sale/..." --pages 2

Environment variables required:
    SCRAPFLY_KEY    — Scrapfly API key
    SUPABASE_URL    — Supabase project URL
    SUPABASE_KEY    — Supabase API key (anon or service-role)
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path wiring — must happen before any local imports
# ---------------------------------------------------------------------------

_repo_root = Path(__file__).parent.parent

# ingestion package
sys.path.insert(0, str(Path(__file__).parent / "src"))

# models package (cross-package import per DEC-001 / ingester.py:12 pattern)
_models_src = _repo_root / "models" / "src"
if _models_src.exists():
    sys.path.insert(0, str(_models_src))

# scraper packages — each scraper dir contains its module directly
_re_scraper_dir = _repo_root / "scaper" / "realestatecom-scraper"
_domain_scraper_dir = _repo_root / "scaper" / "domaincom-scraper"
if _re_scraper_dir.exists():
    sys.path.insert(0, str(_re_scraper_dir))
if _domain_scraper_dir.exists():
    sys.path.insert(0, str(_domain_scraper_dir))

# ---------------------------------------------------------------------------
# Application imports (after path wiring)
# ---------------------------------------------------------------------------

from dotenv import load_dotenv  # noqa: E402

from ingestion.database import SupabaseRepository  # noqa: E402
from ingestion.pipeline import Pipeline  # noqa: E402

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger(__name__)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Error: {name} environment variable is not set.")
        print("Set it in your shell or add it to ingestion/.env")
        sys.exit(1)
    return value


async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Scrape property listings and ingest them directly — no JSON file step.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "source",
        choices=["realestate", "domain"],
        help="Scraper to use",
    )
    parser.add_argument(
        "url",
        type=str,
        help="Search page URL to scrape",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=3,
        metavar="N",
        help="Maximum number of search result pages to scrape (default: 3)",
    )

    args = parser.parse_args()

    # Credentials — env vars only (DEC-003, DEC-006)
    supabase_url = _require_env("SUPABASE_URL")
    supabase_key = _require_env("SUPABASE_KEY")
    _require_env("SCRAPFLY_KEY")  # validated early; consumed by scraper module

    repository = SupabaseRepository(supabase_url, supabase_key)
    pipeline = Pipeline(repository)

    print(f"Source  : {args.source}")
    print(f"URL     : {args.url}")
    print(f"Pages   : {args.pages}")
    print()

    if args.source == "realestate":
        stats = await pipeline.run_realestate(
            search_url=args.url,
            max_scrape_pages=args.pages,
        )
    else:
        stats = await pipeline.run_domain(
            search_url=args.url,
            max_scrape_pages=args.pages,
        )

    print("\n=== Pipeline Complete ===")
    print(f"Processed        : {stats['processed']}")
    print(f"Created          : {stats['created']}")
    print(f"Updated          : {stats['updated']}")
    print(f"Events Generated : {stats['events_generated']}")
    print(f"Errors           : {stats['errors']}")


if __name__ == "__main__":
    asyncio.run(main())
