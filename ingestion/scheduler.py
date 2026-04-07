#!/usr/bin/env python3
"""
APScheduler-based automated scraping daemon.

Runs two recurring jobs:
  1. Daily listings scrape   — every day at DAILY_HOUR:DAILY_MINUTE (default 06:00 AEST)
  2. Auction results scrape  — every Saturday at AUCTION_HOUR:AUCTION_MINUTE (default 21:00 AEST)

Both jobs scrape realestate.com.au and domain.com.au in sequence and ingest
results directly into Supabase — no intermediate JSON file is written.

Usage::

    python3 scheduler.py

Environment variables (set in shell or ingestion/.env):

    Required:
        SCRAPFLY_KEY            Scrapfly API key
        SUPABASE_URL            Supabase project URL
        SUPABASE_KEY            Supabase API key

    Search URLs (at least one pair required):
        REALESTATE_SEARCH_URL   realestate.com.au search URL to scrape
        DOMAIN_SEARCH_URL       domain.com.au search URL to scrape

    Optional timing (integers, Melbourne local time):
        DAILY_HOUR              Hour for daily listings job       (default: 6)
        DAILY_MINUTE            Minute for daily listings job     (default: 0)
        AUCTION_HOUR            Hour for Saturday auction job     (default: 21)
        AUCTION_MINUTE          Minute for Saturday auction job   (default: 0)
        MAX_SCRAPE_PAGES        Max search result pages per run   (default: 3)
        SCHEDULER_TIMEZONE      IANA timezone name                (default: Australia/Melbourne)
"""

import asyncio
import logging
import os
import signal
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

# scraper packages
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
from ingestion.scheduler import Scheduler  # noqa: E402

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
        sys.exit(1)
    return value


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        return int(raw)
    except ValueError:
        print(f"Error: {name} must be an integer, got {raw!r}")
        sys.exit(1)


async def main() -> None:
    # Credentials — env vars only (DEC-003, DEC-006)
    supabase_url = _require_env("SUPABASE_URL")
    supabase_key = _require_env("SUPABASE_KEY")
    _require_env("SCRAPFLY_KEY")  # validated early; consumed by scraper module at import time

    realestate_url = _require_env("REALESTATE_SEARCH_URL")
    domain_url = _require_env("DOMAIN_SEARCH_URL")

    daily_hour = _int_env("DAILY_HOUR", 6)
    daily_minute = _int_env("DAILY_MINUTE", 0)
    auction_hour = _int_env("AUCTION_HOUR", 21)
    auction_minute = _int_env("AUCTION_MINUTE", 0)
    max_pages = _int_env("MAX_SCRAPE_PAGES", 3)
    timezone = os.getenv("SCHEDULER_TIMEZONE", "Australia/Melbourne")

    log.info("=== Undervalued House Finder Scheduler ===")
    log.info("Timezone          : %s", timezone)
    log.info("Daily listings    : %02d:%02d", daily_hour, daily_minute)
    log.info("Auction results   : Saturday %02d:%02d", auction_hour, auction_minute)
    log.info("Max pages/run     : %d", max_pages)
    log.info("realestate URL    : %s", realestate_url)
    log.info("domain URL        : %s", domain_url)

    repository = SupabaseRepository(supabase_url, supabase_key)

    scheduler = Scheduler(
        repository=repository,
        realestate_search_url=realestate_url,
        domain_search_url=domain_url,
        max_scrape_pages=max_pages,
        timezone=timezone,
    )
    scheduler.configure(
        daily_hour=daily_hour,
        daily_minute=daily_minute,
        auction_hour=auction_hour,
        auction_minute=auction_minute,
    )
    scheduler.start()

    log.info("Scheduler running. Press Ctrl+C to stop.")

    # Graceful shutdown on SIGTERM (e.g. systemd, Docker)
    loop = asyncio.get_running_loop()

    def _handle_signal() -> None:
        log.info("Scheduler: shutdown signal received")
        scheduler.stop(wait=True)
        loop.stop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal)

    # Keep the event loop alive until a signal stops it
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        if scheduler.running:
            scheduler.stop(wait=True)


if __name__ == "__main__":
    asyncio.run(main())
