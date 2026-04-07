"""
Unit tests for the S-1 APScheduler-based scheduler.

Tests cover:
- Scheduler construction and job registration
- configure() registers both job IDs
- add_daily_listings_job / add_auction_results_job register correct triggers
- start() / stop() lifecycle
- Job functions call Pipeline methods correctly (mocked)
- Errors within a job are logged and do not propagate (resilience)

No Supabase or Scrapfly credentials are required.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest

# Path wiring
_repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(_repo_root / "models" / "src"))

from ingestion.scheduler import Scheduler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_repository() -> MagicMock:
    repo = MagicMock()
    repo.get_listing.return_value = None
    repo.upsert_listing.return_value = {}
    repo.get_listing_events.return_value = []
    repo.add_event.return_value = {}
    return repo


def _make_scheduler(
    realestate_url: str = "https://www.realestate.com.au/buy/in-melbourne",
    domain_url: str = "https://www.domain.com.au/sale/melbourne-vic-3000/",
    max_scrape_pages: int = 2,
    timezone: str = "Australia/Melbourne",
) -> Scheduler:
    repo = _make_mock_repository()
    return Scheduler(
        repository=repo,
        realestate_search_url=realestate_url,
        domain_search_url=domain_url,
        max_scrape_pages=max_scrape_pages,
        timezone=timezone,
    )


# ---------------------------------------------------------------------------
# Construction and configuration tests
# ---------------------------------------------------------------------------


class TestSchedulerConstruction:
    def test_scheduler_created_not_running(self) -> None:
        sched = _make_scheduler()
        assert not sched.running

    def test_no_jobs_before_configure(self) -> None:
        sched = _make_scheduler()
        assert sched.get_job_ids() == []

    def test_configure_registers_both_jobs(self) -> None:
        sched = _make_scheduler()
        sched.configure()
        job_ids = sched.get_job_ids()
        assert Scheduler.JOB_DAILY_LISTINGS in job_ids
        assert Scheduler.JOB_AUCTION_RESULTS in job_ids

    def test_add_daily_listings_job_registers_job(self) -> None:
        sched = _make_scheduler()
        sched.add_daily_listings_job(hour=7, minute=30)
        assert Scheduler.JOB_DAILY_LISTINGS in sched.get_job_ids()

    def test_add_auction_results_job_registers_job(self) -> None:
        sched = _make_scheduler()
        sched.add_auction_results_job(hour=20, minute=0)
        assert Scheduler.JOB_AUCTION_RESULTS in sched.get_job_ids()

    def test_configure_replaces_existing_jobs(self) -> None:
        """Calling configure() twice should not duplicate jobs."""
        sched = _make_scheduler()
        sched.configure()
        sched.configure(daily_hour=8, auction_hour=22)
        job_ids = sched.get_job_ids()
        # Should have exactly 2 jobs, not 4
        assert len(job_ids) == 2

    def test_daily_job_trigger_is_cron(self) -> None:
        """Daily job trigger must be a CronTrigger."""
        from apscheduler.triggers.cron import CronTrigger
        sched = _make_scheduler()
        sched.add_daily_listings_job(hour=6, minute=0)
        apscheduler_jobs = sched._scheduler.get_jobs()
        daily_job = next(j for j in apscheduler_jobs if j.id == Scheduler.JOB_DAILY_LISTINGS)
        assert isinstance(daily_job.trigger, CronTrigger)

    def test_auction_job_trigger_is_saturday(self) -> None:
        """Auction results job must fire on Saturday only."""
        from apscheduler.triggers.cron import CronTrigger
        sched = _make_scheduler()
        sched.add_auction_results_job(hour=21, minute=0)
        apscheduler_jobs = sched._scheduler.get_jobs()
        auction_job = next(j for j in apscheduler_jobs if j.id == Scheduler.JOB_AUCTION_RESULTS)
        assert isinstance(auction_job.trigger, CronTrigger)
        # Inspect the trigger fields — day_of_week should restrict to Saturday (5 or 'sat')
        trigger_fields = {f.name: str(f) for f in auction_job.trigger.fields}
        assert trigger_fields.get("day_of_week") == "sat"


# ---------------------------------------------------------------------------
# Lifecycle tests
# ---------------------------------------------------------------------------


class TestSchedulerLifecycle:
    @pytest.mark.asyncio
    async def test_start_sets_running_true(self) -> None:
        """start() must make the scheduler report running=True."""
        sched = _make_scheduler()
        sched.configure()
        try:
            sched.start()
            assert sched.running
        finally:
            sched.stop(wait=False)

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self) -> None:
        """stop() must make the scheduler report running=False."""
        sched = _make_scheduler()
        sched.configure()
        sched.start()
        sched.stop(wait=True)
        # APScheduler AsyncIOScheduler updates its internal state asynchronously;
        # a brief event-loop yield is required before .running reflects False.
        await asyncio.sleep(0.1)
        assert not sched.running


# ---------------------------------------------------------------------------
# Job function tests (pipeline mocked)
# ---------------------------------------------------------------------------


class TestSchedulerJobFunctions:
    @pytest.mark.asyncio
    async def test_run_daily_listings_calls_both_pipelines(self) -> None:
        """_run_daily_listings must call run_realestate and run_domain."""
        sched = _make_scheduler()

        mock_re = AsyncMock(return_value={"processed": 5, "created": 5, "updated": 0,
                                          "events_generated": 0, "errors": 0})
        mock_domain = AsyncMock(return_value={"processed": 3, "created": 3, "updated": 0,
                                              "events_generated": 0, "errors": 0})

        with patch.object(sched._pipeline, "run_realestate", mock_re), \
             patch.object(sched._pipeline, "run_domain", mock_domain):
            await sched._run_daily_listings()

        mock_re.assert_awaited_once_with(
            search_url="https://www.realestate.com.au/buy/in-melbourne",
            max_scrape_pages=2,
        )
        mock_domain.assert_awaited_once_with(
            search_url="https://www.domain.com.au/sale/melbourne-vic-3000/",
            max_scrape_pages=2,
        )

    @pytest.mark.asyncio
    async def test_run_auction_results_calls_both_pipelines(self) -> None:
        """_run_auction_results must call run_realestate and run_domain."""
        sched = _make_scheduler()

        mock_re = AsyncMock(return_value={"processed": 2, "created": 2, "updated": 0,
                                          "events_generated": 0, "errors": 0})
        mock_domain = AsyncMock(return_value={"processed": 1, "created": 1, "updated": 0,
                                              "events_generated": 0, "errors": 0})

        with patch.object(sched._pipeline, "run_realestate", mock_re), \
             patch.object(sched._pipeline, "run_domain", mock_domain):
            await sched._run_auction_results()

        mock_re.assert_awaited_once()
        mock_domain.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_daily_realestate_failure_does_not_abort_domain(self) -> None:
        """If the realestate scrape fails, domain scrape must still run."""
        sched = _make_scheduler()

        mock_re = AsyncMock(side_effect=RuntimeError("realestate down"))
        mock_domain = AsyncMock(return_value={"processed": 3, "created": 3, "updated": 0,
                                              "events_generated": 0, "errors": 0})

        with patch.object(sched._pipeline, "run_realestate", mock_re), \
             patch.object(sched._pipeline, "run_domain", mock_domain):
            # Must not raise
            await sched._run_daily_listings()

        mock_domain.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_daily_domain_failure_does_not_propagate(self) -> None:
        """If the domain scrape fails, the job function must not raise."""
        sched = _make_scheduler()

        mock_re = AsyncMock(return_value={"processed": 1, "created": 1, "updated": 0,
                                          "events_generated": 0, "errors": 0})
        mock_domain = AsyncMock(side_effect=ConnectionError("domain unreachable"))

        with patch.object(sched._pipeline, "run_realestate", mock_re), \
             patch.object(sched._pipeline, "run_domain", mock_domain):
            await sched._run_daily_listings()  # must not raise

    @pytest.mark.asyncio
    async def test_auction_realestate_failure_does_not_abort_domain(self) -> None:
        """Auction results job: realestate failure must not prevent domain run."""
        sched = _make_scheduler()

        mock_re = AsyncMock(side_effect=Exception("realestate timeout"))
        mock_domain = AsyncMock(return_value={"processed": 2, "created": 2, "updated": 0,
                                              "events_generated": 0, "errors": 0})

        with patch.object(sched._pipeline, "run_realestate", mock_re), \
             patch.object(sched._pipeline, "run_domain", mock_domain):
            await sched._run_auction_results()

        mock_domain.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_daily_listings_uses_configured_url(self) -> None:
        """Job must use the URL supplied at construction time."""
        custom_url = "https://www.realestate.com.au/buy/custom-search"
        repo = _make_mock_repository()
        sched = Scheduler(
            repository=repo,
            realestate_search_url=custom_url,
            domain_search_url="https://www.domain.com.au/sale/",
            max_scrape_pages=1,
        )

        mock_re = AsyncMock(return_value={})
        mock_domain = AsyncMock(return_value={})

        with patch.object(sched._pipeline, "run_realestate", mock_re), \
             patch.object(sched._pipeline, "run_domain", mock_domain):
            await sched._run_daily_listings()

        mock_re.assert_awaited_once_with(search_url=custom_url, max_scrape_pages=1)
