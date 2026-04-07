"""
Scrape-to-ingest pipeline: runs a scraper and feeds results directly into the
Ingester without any intermediate JSON file step.

Usage (programmatic)::

    from ingestion.pipeline import Pipeline
    from ingestion.database import SupabaseRepository
    import realestate  # from scaper/realestatecom-scraper/

    repo = SupabaseRepository(supabase_url, supabase_key)
    pipeline = Pipeline(repo)
    await pipeline.run_realestate(search_url="https://www.realestate.com.au/...")

The standalone ``pipeline.py`` script at the ingestion package root provides a
CLI interface over this class.
"""

import sys
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from .database import SupabaseRepository
from .ingester import Ingester

log = logging.getLogger(__name__)


class Pipeline:
    """
    Orchestrates scraping + ingestion in a single in-process call.

    Scrapers are imported at call time (not module import time) to avoid
    requiring their dependencies in every process.  The scraper packages must
    be on sys.path before calling any ``run_*`` method — the standalone
    ``pipeline.py`` script handles this via sys.path manipulation.
    """

    def __init__(self, repository: SupabaseRepository) -> None:
        """
        Initialise the pipeline.

        Args:
            repository: Configured SupabaseRepository instance.
        """
        self.repository = repository
        self.ingester = Ingester(repository)

    async def run_realestate(
        self,
        search_url: str,
        max_scrape_pages: int = 3,
    ) -> Dict[str, int]:
        """
        Scrape realestate.com.au search results and ingest them immediately.

        Args:
            search_url:       Full search URL for realestate.com.au.
            max_scrape_pages: Maximum number of search result pages to scrape.

        Returns:
            Ingestion statistics dict (processed, created, updated, events_generated, errors).
        """
        try:
            import realestate as re_scraper  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "realestate scraper not importable. "
                "Ensure scaper/realestatecom-scraper/ is on sys.path."
            ) from exc

        log.info("Pipeline: starting realestate.com.au scrape — %s", search_url)
        raw_data: List[Dict[str, Any]] = await re_scraper.scrape_search(
            url=search_url,
            max_scrape_pages=max_scrape_pages,
        )
        log.info("Pipeline: scraped %d listings, ingesting…", len(raw_data))

        self.ingester.reset_stats()
        self.ingester.ingest_listings_data(raw_data, source_type="realestate")

        stats = self.ingester.get_stats()
        log.info("Pipeline: ingestion complete — %s", stats)
        return stats

    async def run_domain(
        self,
        search_url: str,
        max_scrape_pages: int = 3,
    ) -> Dict[str, int]:
        """
        Scrape domain.com.au search results and ingest them immediately.

        Args:
            search_url:       Full search URL for domain.com.au.
            max_scrape_pages: Maximum number of search result pages to scrape.

        Returns:
            Ingestion statistics dict (processed, created, updated, events_generated, errors).
        """
        try:
            import domaincom as domain_scraper  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "domaincom scraper not importable. "
                "Ensure scaper/domaincom-scraper/ is on sys.path."
            ) from exc

        log.info("Pipeline: starting domain.com.au scrape — %s", search_url)
        raw_data: List[Dict[str, Any]] = await domain_scraper.scrape_search(
            url=search_url,
            max_scrape_pages=max_scrape_pages,
        )
        log.info("Pipeline: scraped %d listings, ingesting…", len(raw_data))

        self.ingester.reset_stats()
        self.ingester.ingest_listings_data(raw_data, source_type="domain")

        stats = self.ingester.get_stats()
        log.info("Pipeline: ingestion complete — %s", stats)
        return stats
