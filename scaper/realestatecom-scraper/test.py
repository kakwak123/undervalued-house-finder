"""
Tests for realestate.com.au Playwright scraper.

These are integration tests that hit the live realestate.com.au website.
Requires Playwright Chromium to be installed:
    playwright install chromium

Tests are marked flaky with 3 retries to handle transient Cloudflare blocks.
"""

import pytest
from cerberus import Validator
import pprint

import realestate

pp = pprint.PrettyPrinter(indent=4)


def validate_or_fail(item, validator):
    if not validator.validate(item):
        pp.pformat(item)
        pytest.fail(
            f"Validation failed for item: {pp.pformat(item)}\nErrors: {validator.errors}"
        )


property_schema = {
    "schema": {
        "type": "dict",
        "schema": {
            "id": {"type": "string", "nullable": True},
            "propertyType": {"type": "string", "nullable": True},
            "description": {"nullable": True},
            "propertyLink": {"type": "string", "nullable": True},
            "address": {
                "type": "dict",
                "nullable": True,
                "schema": {
                    "suburb": {"type": "string", "nullable": True},
                    "state": {"type": "string", "nullable": True},
                    "postcode": {"type": "string", "nullable": True},
                    "display": {
                        "type": "dict",
                        "nullable": True,
                        "schema": {
                            "shortAddress": {"type": "string", "nullable": True},
                            "fullAddress": {"type": "string", "nullable": True},
                        },
                    },
                },
            },
            "generalFeatures": {
                "type": "dict",
                "nullable": True,
                "schema": {
                    "bedrooms": {
                        "type": "dict",
                        "nullable": True,
                        "schema": {"value": {"type": "integer", "nullable": True}},
                    },
                    "bathrooms": {
                        "type": "dict",
                        "nullable": True,
                        "schema": {"value": {"type": "integer", "nullable": True}},
                    },
                    "parkingSpaces": {
                        "type": "dict",
                        "nullable": True,
                        "schema": {"value": {"type": "integer", "nullable": True}},
                    },
                },
            },
            "images": {"type": "list", "nullable": True, "schema": {"type": "string"}},
            "listingCompany": {
                "type": "dict",
                "nullable": True,
                "schema": {
                    "name": {"type": "string", "nullable": True},
                    "id": {"type": "string", "nullable": True},
                },
            },
        },
    }
}


@pytest.mark.asyncio
@pytest.mark.flaky(reruns=3, reruns_delay=30)
async def test_properties_scraping():
    """Scrape individual property pages and validate output shape."""
    properties_data = await realestate.scrape_properties(
        urls=[
            "https://www.realestate.com.au/property-house-vic-tarneit-143160680",
            "https://www.realestate.com.au/property-house-vic-bundoora-141557712",
            "https://www.realestate.com.au/property-townhouse-vic-glenroy-143556608",
        ]
    )
    validator = Validator(property_schema, allow_unknown=True)
    for item in properties_data:
        validate_or_fail(item, validator)
    assert len(properties_data) >= 1


@pytest.mark.asyncio
@pytest.mark.flaky(reruns=3, reruns_delay=30)
async def test_search_scraping():
    """Scrape one page of search results and validate output shape."""
    search_data = await realestate.scrape_search(
        url="https://www.realestate.com.au/buy/in-melbourne+-+northern+region,+vic/list-1",
        max_scrape_pages=1,
    )
    validator = Validator(property_schema, allow_unknown=True)
    for item in search_data:
        validate_or_fail(item, validator)
    assert len(search_data) >= 1
