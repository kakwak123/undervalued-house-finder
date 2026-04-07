"""
Entry point for the Domain.com.au scraper.

Uses the official Domain Developer API (api.domain.com.au) — no Scrapfly required.

Required env vars:
    DOMAIN_API_KEY          — API key from https://developer.domain.com.au/

Optional env vars:
    DOMAIN_SUBURBS          — comma-separated suburb names (default: Melbourne CBD + inner suburbs)
    DOMAIN_PROPERTY_TYPES   — comma-separated property types (default: house,unit apartment,townhouse)

Usage:
    export DOMAIN_API_KEY=your-key
    poetry run python run.py
"""

import asyncio

from domaincom import scrape_domain, _get_suburbs, _get_property_types


SUBURBS = _get_suburbs()
PROPERTY_TYPES = _get_property_types()


if __name__ == "__main__":
    print(f"Running Domain.com.au API scrape for {len(SUBURBS)} suburbs")
    print(f"Suburbs: {SUBURBS}")
    print(f"Property types: {PROPERTY_TYPES}")
    print("Saving results to ./results/search.json")
    asyncio.run(scrape_domain(suburbs=SUBURBS, property_types=PROPERTY_TYPES))
