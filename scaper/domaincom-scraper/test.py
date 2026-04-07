"""
Tests for Domain.com.au API scraper.

These are integration tests that hit the live Domain API.
Set DOMAIN_API_KEY in your environment before running.
Set SAVE_TEST_RESULTS=true to persist results to ./results/.
"""

import json
import os
from pathlib import Path

import pytest
from cerberus import Validator
import pprint

import domaincom

pp = pprint.PrettyPrinter(indent=4)


def validate_or_fail(item, validator):
    if not validator.validate(item):
        pp.pformat(item)
        pytest.fail(
            f"Validation failed for item: {pp.pformat(item)}\nErrors: {validator.errors}"
        )


# Cerberus schema for a parsed listing detail (scrape_properties output)
property_schema = {
    "schema": {
        "type": "dict",
        "schema": {
            "listingId": {"type": "integer", "nullable": True},
            "listingUrl": {"type": "string"},
            "unitNumber": {"type": "string", "nullable": True},
            "street": {"type": "string", "nullable": True},
            "suburb": {"type": "string", "nullable": True},
            "postcode": {"type": "string", "nullable": True},
            "createdOn": {"type": "string", "nullable": True},
            "propertyType": {"type": "string", "nullable": True},
            "beds": {"type": "integer", "nullable": True},
            "phone": {"type": "string", "nullable": True},
            "agencyName": {"type": "string", "nullable": True},
            "propertyDeveloperName": {"nullable": True},
            "agencyProfileUrl": {"nullable": True},
            "propertyDeveloperUrl": {"nullable": True},
            "description": {
                "type": "list",
                "schema": {"type": "string"},
            },
            "listingSummary": {
                "type": "dict",
                "schema": {
                    "beds": {"type": "integer", "nullable": True},
                    "baths": {"type": "integer", "nullable": True},
                    "parking": {"type": "integer", "nullable": True},
                    "title": {"type": "string", "nullable": True},
                    "address": {"type": "string", "nullable": True},
                    "listingType": {"type": "string"},
                    "propertyType": {"type": "string", "nullable": True},
                    "status": {"type": "string", "nullable": True},
                    "mode": {"nullable": True},
                },
            },
            "agents": {
                "type": "list",
                "schema": {
                    "type": "dict",
                    "schema": {
                        "name": {"type": "string", "nullable": True},
                        "photo": {"nullable": True},
                        "phone": {"type": "string", "nullable": True},
                        "mobile": {"nullable": True},
                        "agentProfileUrl": {"nullable": True},
                    },
                },
            },
        },
    }
}


# Cerberus schema for a search result item (scrape_search output)
search_schema = {
    "schema": {
        "type": "dict",
        "schema": {
            "id": {"type": "string"},
            "listingType": {"type": "string"},
            "listingModel": {
                "type": "dict",
                "schema": {
                    "listingId": {"nullable": True},
                    "listingUrl": {"type": "string", "nullable": True},
                    "suburb": {"type": "string", "nullable": True},
                    "postcode": {"type": "string", "nullable": True},
                },
            },
        },
    }
}


@pytest.mark.asyncio
async def test_properties_scraping():
    """Fetch listing detail for known Domain listing IDs."""
    properties_data = await domaincom.scrape_properties(
        listing_ids=[2018835548, 17773317]
    )
    validator = Validator(property_schema, allow_unknown=True)
    assert len(properties_data) >= 1
    validate_or_fail(properties_data[0], validator)
    if os.getenv("SAVE_TEST_RESULTS") == "true":
        (Path(__file__).parent / "results/properties.json").write_text(
            json.dumps(properties_data, indent=2, ensure_ascii=False)
        )


@pytest.mark.asyncio
async def test_search_scraping():
    """Search a single suburb and validate shape of results."""
    search_data = await domaincom.scrape_search(
        suburbs=["Melbourne"],
        property_types=["house", "unit apartment"],
    )
    validator = Validator(search_schema, allow_unknown=True)
    for item in search_data:
        validate_or_fail(item, validator)
    assert len(search_data) >= 1
    if os.getenv("SAVE_TEST_RESULTS") == "true":
        (Path(__file__).parent / "results/search.json").write_text(
            json.dumps(search_data, indent=2, ensure_ascii=False)
        )
