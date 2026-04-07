"""
APScheduler-based scheduler for automated scraping.

Provides two recurring job types:
- Daily listings scrape  — runs every day at a configurable time (default 06:00 AEST)
- Saturday auction results — runs every Saturday night at a configurable time (default 21:00 AEST)

Usage (programmatic)::

    import asyncio
    from ingestion.scheduler import Scheduler
    from ingestion.database import SupabaseRepository

    repo = SupabaseRepository(supabase_url, supabase_key)
    scheduler = Scheduler(
        repository=repo,
        realestate_search_url="https://www.realestate.com.au/buy/...",
        domain_search_url="https://www.domain.com.au/sale/...",
    )
    scheduler.configure()

    loop = asyncio.get_event_loop()
    scheduler.start()
    try:
        loop.run_forever()
    finally:
        scheduler.stop()

The standalone ``scheduler.py`` script at the ingestion root provides a CLI interface.
"""

import asyncio
import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .database import SupabaseRepository
from .pipeline import Pipeline

log = logging.getLogger(__name__)


class Scheduler:
    """
    Wraps APScheduler's AsyncIOScheduler to run the scrape-to-ingest pipeline
    on a configurable recurring schedule.

    Two job types are registered:
    - ``daily_listings``:   runs every day, scraping active listings from both sources.
    - ``auction_results``:  runs every Saturday night, capturing auction outcomes.

    Both jobs use the same Pipeline internally.  Jobs run sequentially within a
    single scheduler instance (no parallel scrape jobs) to respect rate limiting.
    """

    # APScheduler job IDs — used for start/stop/status checks
    JOB_DAILY_LISTINGS = "daily_listings"
    JOB_AUCTION_RESULTS = "auction_results"

    def __init__(
        self,
        repository: SupabaseRepository,
        realestate_search_url: str,
        domain_search_url: str,
        max_scrape_pages: int = 3,
        timezone: str = "Australia/Melbourne",
    ) -> None:
        """
        Initialise the scheduler.

        Args:
            repository:             Configured SupabaseRepository instance.
            realestate_search_url:  Search URL for the realestate.com.au scraper.
            domain_search_url:      Search URL for the domain.com.au scraper.
            max_scrape_pages:       Maximum search result pages per scrape run.
            timezone:               Timezone for cron expressions (IANA name).
                                    Defaults to 'Australia/Melbourne' (AEST/AEDT).
        """
        self._pipeline = Pipeline(repository)
        self._realestate_url = realestate_search_url
        self._domain_url = domain_search_url
        self._max_pages = max_scrape_pages
        self._timezone = timezone
        self._scheduler = AsyncIOScheduler(timezone=timezone)

    # ------------------------------------------------------------------
    # Job functions — called by APScheduler in the asyncio event loop
    # ------------------------------------------------------------------

    async def _run_daily_listings(self) -> None:
        """
        Job: scrape both sources for active listings and ingest immediately.

        Runs realestate first, then domain.  Errors from one source are logged
        and do not abort the other source.
        """
        log.info("Scheduler: starting daily listings scrape")
        try:
            re_stats = await self._pipeline.run_realestate(
                search_url=self._realestate_url,
                max_scrape_pages=self._max_pages,
            )
            log.info("Scheduler: realestate daily complete — %s", re_stats)
        except Exception as exc:
            log.error("Scheduler: realestate daily scrape failed — %s: %s", type(exc).__name__, exc)

        try:
            domain_stats = await self._pipeline.run_domain(
                search_url=self._domain_url,
                max_scrape_pages=self._max_pages,
            )
            log.info("Scheduler: domain daily complete — %s", domain_stats)
        except Exception as exc:
            log.error("Scheduler: domain daily scrape failed — %s: %s", type(exc).__name__, exc)

    async def _run_auction_results(self) -> None:
        """
        Job: scrape both sources for Saturday night auction results.

        Same pipeline as the daily job but run specifically on Saturday evenings
        to capture clearance rates and passed-in results before they're updated.
        """
        log.info("Scheduler: starting Saturday auction results scrape")
        try:
            re_stats = await self._pipeline.run_realestate(
                search_url=self._realestate_url,
                max_scrape_pages=self._max_pages,
            )
            log.info("Scheduler: realestate auction results complete — %s", re_stats)
        except Exception as exc:
            log.error("Scheduler: realestate auction scrape failed — %s: %s", type(exc).__name__, exc)

        try:
            domain_stats = await self._pipeline.run_domain(
                search_url=self._domain_url,
                max_scrape_pages=self._max_pages,
            )
            log.info("Scheduler: domain auction results complete — %s", domain_stats)
        except Exception as exc:
            log.error("Scheduler: domain auction scrape failed — %s: %s", type(exc).__name__, exc)

    # ------------------------------------------------------------------
    # Job registration
    # ------------------------------------------------------------------

    def add_daily_listings_job(self, hour: int = 6, minute: int = 0) -> None:
        """
        Register the daily listings scrape job.

        If a job with the same ID already exists it is removed first, so
        calling this method twice reconfigures the schedule rather than
        duplicating the job.

        Args:
            hour:   Hour of day (0–23) in the scheduler's configured timezone.
                    Defaults to 6 (06:00 AEST — before peak-hour traffic).
            minute: Minute of the hour. Defaults to 0.
        """
        # Remove existing job with this ID before (re)adding to avoid duplicates
        if self._scheduler.get_job(self.JOB_DAILY_LISTINGS):
            self._scheduler.remove_job(self.JOB_DAILY_LISTINGS)

        self._scheduler.add_job(
            self._run_daily_listings,
            trigger=CronTrigger(hour=hour, minute=minute, timezone=self._timezone),
            id=self.JOB_DAILY_LISTINGS,
            name="Daily listings scrape (realestate + domain)",
            misfire_grace_time=600,  # tolerate up to 10-minute delay before skipping
        )
        log.info(
            "Scheduler: daily listings job registered — %02d:%02d %s",
            hour,
            minute,
            self._timezone,
        )

    def add_auction_results_job(self, hour: int = 21, minute: int = 0) -> None:
        """
        Register the Saturday night auction results scrape job.

        If a job with the same ID already exists it is removed first.

        Args:
            hour:   Hour of day (0–23) in the scheduler's configured timezone.
                    Defaults to 21 (21:00 AEST — after most Melbourne auctions
                    have completed and results are published online).
            minute: Minute of the hour. Defaults to 0.
        """
        # Remove existing job with this ID before (re)adding to avoid duplicates
        if self._scheduler.get_job(self.JOB_AUCTION_RESULTS):
            self._scheduler.remove_job(self.JOB_AUCTION_RESULTS)

        self._scheduler.add_job(
            self._run_auction_results,
            trigger=CronTrigger(
                day_of_week="sat",  # Saturday only
                hour=hour,
                minute=minute,
                timezone=self._timezone,
            ),
            id=self.JOB_AUCTION_RESULTS,
            name="Saturday auction results scrape (realestate + domain)",
            misfire_grace_time=3600,  # tolerate up to 1-hour delay for auction results
        )
        log.info(
            "Scheduler: auction results job registered — Saturday %02d:%02d %s",
            hour,
            minute,
            self._timezone,
        )

    def configure(
        self,
        daily_hour: int = 6,
        daily_minute: int = 0,
        auction_hour: int = 21,
        auction_minute: int = 0,
    ) -> None:
        """
        Register both standard jobs with a single call.

        Args:
            daily_hour:    Hour for the daily listings job (default 6).
            daily_minute:  Minute for the daily listings job (default 0).
            auction_hour:  Hour for the Saturday auction job (default 21).
            auction_minute: Minute for the Saturday auction job (default 0).
        """
        self.add_daily_listings_job(hour=daily_hour, minute=daily_minute)
        self.add_auction_results_job(hour=auction_hour, minute=auction_minute)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the scheduler. Must be called from within a running asyncio event loop."""
        self._scheduler.start()
        log.info("Scheduler: started — %d job(s) scheduled", len(self._scheduler.get_jobs()))

    def stop(self, wait: bool = True) -> None:
        """
        Shut down the scheduler.

        Args:
            wait: If True, wait for currently-running jobs to complete before stopping.
        """
        self._scheduler.shutdown(wait=wait)
        log.info("Scheduler: stopped")

    @property
    def running(self) -> bool:
        """Return True if the scheduler is currently running."""
        return self._scheduler.running

    def get_job_ids(self) -> list[str]:
        """Return the IDs of all registered jobs."""
        return [job.id for job in self._scheduler.get_jobs()]
