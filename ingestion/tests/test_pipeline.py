"""
Unit tests for the S-2 scrape-to-ingest pipeline.

Tests cover:
- RealestateReader.from_data  — in-memory normalisation path
- DomainReader.from_data      — in-memory normalisation path
- Ingester.ingest_listings_data — integration of in-memory ingestion
- Pipeline class wiring        — scraper callable → ingester (mocked Scrapfly)

No Supabase or Scrapfly credentials are required.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Path wiring — mirrors ingestion/ingest.py pattern
_repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(_repo_root / "models" / "src"))

from ingestion.readers import RealestateReader, DomainReader
from ingestion.ingester import Ingester
from ingestion.pipeline import Pipeline


# ---------------------------------------------------------------------------
# Minimal test fixtures — realistic structures, not full scraper output
# ---------------------------------------------------------------------------

REALESTATE_ITEM: Dict[str, Any] = {
    "id": "149785064",
    "propertyType": "House",
    "description": "Great family home with pool.",
    "propertyLink": "https://www.realestate.com.au/property-house-vic-dandenong+north-149785064",
    "address": {
        "display": {
            "shortAddress": "31 Aberdeen Drive",
            "fullAddress": "31 Aberdeen Drive, Dandenong North, Vic 3175",
        },
        "suburb": "Dandenong North",
        "state": "Vic",
        "postcode": "3175",
    },
    "propertySizes": {
        "land": {"displayValue": "554"},
        "building": None,
    },
    "generalFeatures": {
        "bedrooms": {"value": 6},
        "bathrooms": {"value": 2},
    },
    "auction": None,
}

REALESTATE_ITEM_2: Dict[str, Any] = {
    "id": "999000001",
    "propertyType": "Townhouse",
    "description": "Modern townhouse. Price Guide $760,000.",
    "propertyLink": "https://www.realestate.com.au/property-townhouse-vic-glenroy-999000001",
    "address": {
        "display": {
            "shortAddress": "5 Example St",
            "fullAddress": "5 Example St, Glenroy, Vic 3046",
        },
        "suburb": "Glenroy",
        "state": "Vic",
        "postcode": "3046",
    },
    "propertySizes": {},
    "generalFeatures": {
        "bedrooms": {"value": 3},
        "bathrooms": {"value": 2},
    },
    "auction": None,
}

DOMAIN_ITEM: Dict[str, Any] = {
    "listingId": 2018835548,
    "listingUrl": "https://www.domain.com.au/610-399-bourke-street-melbourne-vic-3000-2018835548",
    "unitNumber": "610",
    "streetNumber": "399",
    "street": "Bourke Street",
    "suburb": "Melbourne",
    "postcode": "3000",
    "propertyType": "Apartment",
    "beds": 2,
    "description": ["Stunning apartment in the heart of Melbourne CBD."],
}

DOMAIN_ITEM_WITH_BAD_ID: Dict[str, Any] = {
    # Missing listingId — normaliser should handle gracefully
    "listingUrl": "https://www.domain.com.au/some-property",
    "suburb": "Richmond",
    "postcode": "3121",
    "propertyType": "Unit",
    "beds": 1,
}


# ---------------------------------------------------------------------------
# RealestateReader.from_data tests
# ---------------------------------------------------------------------------


class TestRealestateReaderFromData:
    def test_yields_listing_for_valid_item(self) -> None:
        listings = list(RealestateReader.from_data([REALESTATE_ITEM]))
        assert len(listings) == 1
        listing = listings[0]
        assert listing.listing_id == "149785064"
        assert listing.suburb == "Dandenong North"
        assert listing.bedrooms == 6
        assert listing.bathrooms == 2
        assert listing.land_size == Decimal("554")
        assert listing.source == "realestate.com.au"

    def test_yields_multiple_listings(self) -> None:
        listings = list(RealestateReader.from_data([REALESTATE_ITEM, REALESTATE_ITEM_2]))
        assert len(listings) == 2
        ids = {l.listing_id for l in listings}
        assert ids == {"149785064", "999000001"}

    def test_skips_unparseable_items_and_continues(self) -> None:
        bad_item: Dict[str, Any] = {}  # missing required fields like 'id' and 'address'
        # Should not raise — bad item is skipped, good item is yielded
        listings = list(RealestateReader.from_data([bad_item, REALESTATE_ITEM]))
        # At minimum the valid item should come through
        assert any(l.listing_id == "149785064" for l in listings)

    def test_empty_list_yields_nothing(self) -> None:
        listings = list(RealestateReader.from_data([]))
        assert listings == []

    def test_price_extracted_from_description(self) -> None:
        listings = list(RealestateReader.from_data([REALESTATE_ITEM_2]))
        assert len(listings) == 1
        # Description contains "Price Guide $760,000" — should be extracted
        assert listings[0].current_price == Decimal("760000")


# ---------------------------------------------------------------------------
# DomainReader.from_data tests
# ---------------------------------------------------------------------------


class TestDomainReaderFromData:
    def test_yields_listing_for_valid_item(self) -> None:
        listings = list(DomainReader.from_data([DOMAIN_ITEM]))
        assert len(listings) == 1
        listing = listings[0]
        assert listing.listing_id == "2018835548"
        assert listing.suburb == "Melbourne"
        assert listing.bedrooms == 2
        assert listing.source == "domain.com.au"

    def test_yields_multiple_listings(self) -> None:
        listings = list(DomainReader.from_data([DOMAIN_ITEM, DOMAIN_ITEM_WITH_BAD_ID]))
        # Both items should be processed; bad ID item gets empty string listing_id
        assert len(listings) >= 1
        assert any(l.listing_id == "2018835548" for l in listings)

    def test_empty_list_yields_nothing(self) -> None:
        listings = list(DomainReader.from_data([]))
        assert listings == []

    def test_description_joined_from_list(self) -> None:
        listings = list(DomainReader.from_data([DOMAIN_ITEM]))
        assert listings[0].description == "Stunning apartment in the heart of Melbourne CBD."


# ---------------------------------------------------------------------------
# Ingester.ingest_listings_data tests (mocked repository)
# ---------------------------------------------------------------------------


def _make_mock_repository() -> MagicMock:
    """Create a MagicMock SupabaseRepository that simulates a new listing."""
    repo = MagicMock()
    repo.get_listing.return_value = None  # listing does not exist yet → create path
    repo.upsert_listing.return_value = {}
    repo.get_listing_events.return_value = []
    repo.add_event.return_value = {}
    return repo


class TestIngesterIngestListingsData:
    def test_realestate_data_processed(self) -> None:
        repo = _make_mock_repository()
        ingester = Ingester(repo)
        ingester.ingest_listings_data([REALESTATE_ITEM, REALESTATE_ITEM_2], source_type="realestate")
        stats = ingester.get_stats()
        assert stats["processed"] == 2
        assert stats["created"] == 2
        assert stats["errors"] == 0

    def test_domain_data_processed(self) -> None:
        repo = _make_mock_repository()
        ingester = Ingester(repo)
        ingester.ingest_listings_data([DOMAIN_ITEM], source_type="domain")
        stats = ingester.get_stats()
        assert stats["processed"] == 1
        assert stats["created"] == 1
        assert stats["errors"] == 0

    def test_upsert_called_for_each_listing(self) -> None:
        repo = _make_mock_repository()
        ingester = Ingester(repo)
        ingester.ingest_listings_data([REALESTATE_ITEM, REALESTATE_ITEM_2], source_type="realestate")
        # Each listing is upserted at least once on the create path; listings
        # with a price get a second upsert when the opportunity score is persisted.
        assert repo.upsert_listing.call_count >= 2
        upserted_ids = {call.args[0].listing_id for call in repo.upsert_listing.call_args_list}
        assert upserted_ids == {"149785064", "999000001"}

    def test_invalid_source_type_raises(self) -> None:
        repo = _make_mock_repository()
        ingester = Ingester(repo)
        with pytest.raises(ValueError, match="Unknown source_type"):
            ingester.ingest_listings_data([REALESTATE_ITEM], source_type="unknown")

    def test_empty_data_no_calls(self) -> None:
        repo = _make_mock_repository()
        ingester = Ingester(repo)
        ingester.ingest_listings_data([], source_type="realestate")
        stats = ingester.get_stats()
        assert stats["processed"] == 0
        repo.upsert_listing.assert_not_called()

    def test_update_path_when_existing_listing(self) -> None:
        """When the listing already exists, updated count increments."""
        repo = _make_mock_repository()
        # Simulate an existing listing with same price — no events expected
        repo.get_listing.return_value = {
            "listing_id": "149785064",
            "current_price": None,
            "status": "unknown",
            "auction_datetime": None,
        }
        ingester = Ingester(repo)
        ingester.ingest_listings_data([REALESTATE_ITEM], source_type="realestate")
        stats = ingester.get_stats()
        assert stats["updated"] == 1
        assert stats["created"] == 0


# ---------------------------------------------------------------------------
# Pipeline class tests (scraper functions mocked)
# ---------------------------------------------------------------------------


class TestPipeline:
    @pytest.mark.asyncio
    async def test_run_realestate_calls_scraper_and_ingests(self) -> None:
        repo = _make_mock_repository()
        pipeline = Pipeline(repo)

        mock_scrape_search = AsyncMock(return_value=[REALESTATE_ITEM])

        with patch.dict(
            sys.modules,
            {"realestate": MagicMock(scrape_search=mock_scrape_search)},
        ):
            stats = await pipeline.run_realestate(
                search_url="https://www.realestate.com.au/buy/in-melbourne",
                max_scrape_pages=1,
            )

        mock_scrape_search.assert_awaited_once_with(
            url="https://www.realestate.com.au/buy/in-melbourne",
            max_scrape_pages=1,
        )
        assert stats["processed"] == 1
        assert stats["errors"] == 0

    @pytest.mark.asyncio
    async def test_run_domain_calls_scraper_and_ingests(self) -> None:
        repo = _make_mock_repository()
        pipeline = Pipeline(repo)

        mock_scrape_search = AsyncMock(return_value=[DOMAIN_ITEM])

        with patch.dict(
            sys.modules,
            {"domaincom": MagicMock(scrape_search=mock_scrape_search)},
        ):
            stats = await pipeline.run_domain(
                search_url="https://www.domain.com.au/sale/melbourne-vic-3000/",
                max_scrape_pages=1,
            )

        mock_scrape_search.assert_awaited_once_with(
            url="https://www.domain.com.au/sale/melbourne-vic-3000/",
            max_scrape_pages=1,
        )
        assert stats["processed"] == 1
        assert stats["errors"] == 0

    @pytest.mark.asyncio
    async def test_run_realestate_raises_on_missing_scraper(self) -> None:
        """ImportError raised when realestate module is not importable."""
        repo = _make_mock_repository()
        pipeline = Pipeline(repo)

        # Remove realestate from sys.modules if present, simulate import failure
        with patch.dict(sys.modules, {"realestate": None}):  # type: ignore[dict-item]
            with pytest.raises((ImportError, TypeError)):
                await pipeline.run_realestate(
                    search_url="https://www.realestate.com.au/buy/",
                    max_scrape_pages=1,
                )

    @pytest.mark.asyncio
    async def test_stats_reset_between_runs(self) -> None:
        """Each pipeline.run_* call resets stats so they don't accumulate."""
        repo = _make_mock_repository()
        pipeline = Pipeline(repo)

        mock_scrape = AsyncMock(return_value=[REALESTATE_ITEM])
        with patch.dict(sys.modules, {"realestate": MagicMock(scrape_search=mock_scrape)}):
            stats1 = await pipeline.run_realestate("https://example.com", max_scrape_pages=1)
            stats2 = await pipeline.run_realestate("https://example.com", max_scrape_pages=1)

        # Each run should report 1 processed, not 2
        assert stats1["processed"] == 1
        assert stats2["processed"] == 1
