"""
Domain.com.au API client — uses the official Domain Developer API (api.domain.com.au).

Authentication: set env var DOMAIN_API_KEY with your key from https://developer.domain.com.au/
Configuration:
  DOMAIN_SUBURBS          — comma-separated suburb names (default: Melbourne defaults)
  DOMAIN_PROPERTY_TYPES   — comma-separated property types (default: house,unit,apartment,townhouse)
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger as log

from scraper_utils import RateLimiter, retry_on_failure

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_API_KEY: str = os.environ.get("DOMAIN_API_KEY", "")
_BASE_URL: str = "https://api.domain.com.au/v1"

_DEFAULT_SUBURBS: List[str] = [
    "Melbourne",
    "South Yarra",
    "Richmond",
    "Fitzroy",
    "Collingwood",
    "St Kilda",
    "Prahran",
    "Hawthorn",
    "Toorak",
    "Northcote",
]

_DEFAULT_PROPERTY_TYPES: List[str] = ["house", "unit apartment", "townhouse"]

# Module-level rate limiter: enforces minimum 2s between sequential requests
_rate_limiter = RateLimiter(min_delay_seconds=2.0)

output = Path(__file__).parent / "results"
output.mkdir(exist_ok=True)


def _get_suburbs() -> List[str]:
    """Read suburb list from DOMAIN_SUBURBS env var, or fall back to defaults."""
    raw = os.environ.get("DOMAIN_SUBURBS", "")
    if raw.strip():
        return [s.strip() for s in raw.split(",") if s.strip()]
    return _DEFAULT_SUBURBS


def _get_property_types() -> List[str]:
    """Read property types from DOMAIN_PROPERTY_TYPES env var, or fall back to defaults."""
    raw = os.environ.get("DOMAIN_PROPERTY_TYPES", "")
    if raw.strip():
        return [t.strip() for t in raw.split(",") if t.strip()]
    return _DEFAULT_PROPERTY_TYPES


def _build_headers() -> Dict[str, str]:
    """Build HTTP headers for Domain API requests."""
    if not _API_KEY:
        raise EnvironmentError("DOMAIN_API_KEY environment variable is not set")
    return {
        "X-Api-Key": _API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# ---------------------------------------------------------------------------
# Response parsers
# ---------------------------------------------------------------------------


def parse_listing_summary(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map a Domain API search-result listing object to the output shape
    expected by the ingestion pipeline (same keys as the old scraper).

    The Domain /v1/listings/residential/_search endpoint returns a list of
    listing objects; each has a top-level ``listing`` sub-object.
    """
    listing = item.get("listing", item)  # some responses embed under "listing"

    price_details = listing.get("priceDetails") or {}
    address = listing.get("addressParts") or {}
    property_details = listing.get("propertyDetails") or {}
    media = listing.get("media") or []

    gallery_slides = []
    for m in media:
        if m.get("category") in ("image", None):
            gallery_slides.append(
                {
                    "thumbnail": m.get("url", ""),
                    "images": {
                        "original": {"url": m.get("url", ""), "width": None, "height": None},
                        "tablet": {"url": m.get("url", ""), "width": None, "height": None},
                        "mobile": {"url": m.get("url", ""), "width": None, "height": None},
                    },
                    "embedUrl": m.get("url") if m.get("category") == "video" else None,
                    "mediaType": m.get("category", "image"),
                }
            )

    agents_raw = listing.get("advertiserIdentifiers", {})
    agents: List[Dict[str, Any]] = []
    if agents_raw.get("advertiserType") == "Agency":
        agents.append(
            {
                "name": agents_raw.get("contactName", ""),
                "photo": None,
                "phone": agents_raw.get("contactPhone", ""),
                "mobile": None,
                "agentProfileUrl": None,
                "email": None,
            }
        )

    return {
        "id": str(listing.get("id", "")),
        "listingType": item.get("type", "Sale"),
        "listingModel": {
            "listingId": listing.get("id"),
            "listingUrl": listing.get("listingSlug", ""),
            "unitNumber": address.get("unitNumber", ""),
            "streetNumber": address.get("streetNumber", ""),
            "street": address.get("street", ""),
            "suburb": address.get("suburb", ""),
            "postcode": address.get("postcode", ""),
            "state": address.get("state", ""),
            "createdOn": listing.get("dateUpdated", ""),
            "propertyType": property_details.get("propertyType", ""),
            "beds": property_details.get("bedrooms"),
            "baths": property_details.get("bathrooms"),
            "parking": property_details.get("carspaces"),
            "landSize": property_details.get("landArea"),
            "buildingSize": property_details.get("buildingArea"),
            "phone": agents_raw.get("contactPhone", ""),
            "agencyName": agents_raw.get("developerName", "") or agents_raw.get("contactName", ""),
            "propertyDeveloperName": None,
            "agencyProfileUrl": None,
            "propertyDeveloperUrl": None,
            "description": listing.get("headline", ""),
            "loanfinder": None,
            "schools": None,
            "suburbInsights": None,
            "gallery": {"slides": gallery_slides},
            "listingSummary": {
                "address": address.get("displayAddress", ""),
                "baths": property_details.get("bathrooms"),
                "beds": property_details.get("bedrooms"),
                "parking": property_details.get("carspaces"),
                "propertyType": property_details.get("propertyType", ""),
                "title": price_details.get("displayPrice", ""),
                "status": listing.get("status", ""),
                "listingType": "sale",
            },
            "agents": agents,
            "features": property_details.get("features", []),
            "structuredFeatures": [],
            "faqs": [],
            "url": f"https://www.domain.com.au/{listing.get('listingSlug', '')}",
            "priceDisplay": price_details.get("displayPrice", ""),
            "priceFrom": price_details.get("price"),
            "priceTo": price_details.get("priceTo"),
            "latitude": property_details.get("latitude"),
            "longitude": property_details.get("longitude"),
        },
    }


def parse_listing_detail(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map a Domain API GET /v1/listings/{id} response to the detailed property shape
    expected by the ingestion pipeline.
    """
    price_details = data.get("priceDetails") or {}
    address = data.get("addressParts") or {}
    property_details = data.get("propertyDetails") or {}
    media = data.get("media") or []

    gallery_slides = []
    for m in media:
        gallery_slides.append(
            {
                "thumbnail": m.get("url", ""),
                "images": {
                    "original": {"url": m.get("url", ""), "width": None, "height": None},
                    "tablet": {"url": m.get("url", ""), "width": None, "height": None},
                    "mobile": {"url": m.get("url", ""), "width": None, "height": None},
                },
                "embedUrl": m.get("url") if m.get("category") == "video" else None,
                "mediaType": m.get("category", "image"),
            }
        )

    advertiser = data.get("advertiserIdentifiers") or {}
    agents: List[Dict[str, Any]] = []
    if advertiser.get("advertiserType") == "Agency":
        agents.append(
            {
                "name": advertiser.get("contactName", ""),
                "photo": None,
                "phone": advertiser.get("contactPhone", ""),
                "mobile": None,
                "agentProfileUrl": None,
                "email": None,
            }
        )

    result = {
        "listingId": data.get("id"),
        "listingUrl": f"https://www.domain.com.au/{data.get('listingSlug', '')}",
        "unitNumber": address.get("unitNumber", ""),
        "streetNumber": address.get("streetNumber", ""),
        "street": address.get("street", ""),
        "suburb": address.get("suburb", ""),
        "postcode": address.get("postcode", ""),
        "state": address.get("state", ""),
        "createdOn": data.get("dateUpdated", ""),
        "propertyType": property_details.get("propertyType", ""),
        "beds": property_details.get("bedrooms"),
        "phone": advertiser.get("contactPhone", ""),
        "agencyName": advertiser.get("developerName", "") or advertiser.get("contactName", ""),
        "propertyDeveloperName": None,
        "agencyProfileUrl": None,
        "propertyDeveloperUrl": None,
        "description": [data.get("description", "")] if data.get("description") else [],
        "loanfinder": None,
        "schools": None,
        "suburbInsights": None,
        "gallery": {"slides": gallery_slides},
        "listingSummary": {
            "address": address.get("displayAddress", ""),
            "baths": property_details.get("bathrooms"),
            "beds": property_details.get("bedrooms"),
            "parking": property_details.get("carspaces"),
            "propertyType": property_details.get("propertyType", ""),
            "title": price_details.get("displayPrice", ""),
            "status": data.get("status", ""),
            "listingType": "sale",
            "mode": None,
            "isRural": property_details.get("isRural", False),
            "promoType": None,
            "showDefaultFeatures": True,
            "showDomainInsight": True,
            "stats": [],
            "houses": None,
        },
        "agents": agents,
        "features": property_details.get("features", []),
        "structuredFeatures": [],
        "faqs": [],
        "url": f"https://www.domain.com.au/{data.get('listingSlug', '')}",
        "priceDisplay": price_details.get("displayPrice", ""),
        "priceFrom": price_details.get("price"),
        "priceTo": price_details.get("priceTo"),
        "latitude": property_details.get("latitude"),
        "longitude": property_details.get("longitude"),
    }
    return result


# ---------------------------------------------------------------------------
# API fetch helpers
# ---------------------------------------------------------------------------


@retry_on_failure(max_attempts=3, base_delay_seconds=2.0, backoff_factor=2.0)
async def _search_suburb(
    client: httpx.AsyncClient,
    suburb: str,
    state: str,
    property_types: List[str],
    page: int = 1,
    page_size: int = 200,
) -> Dict[str, Any]:
    """
    POST /v1/listings/residential/_search for a single suburb + page.

    Rate-limited (2s minimum inter-request delay) and retried with
    exponential backoff on failure.

    Args:
        client:         Shared httpx.AsyncClient
        suburb:         Suburb name (e.g. "Melbourne")
        state:          State code (e.g. "VIC")
        property_types: List of Domain property type strings
        page:           1-based page number
        page_size:      Results per page (max 200)

    Returns:
        Raw API response dict
    """
    await _rate_limiter.wait()
    payload: Dict[str, Any] = {
        "listingType": "Sale",
        "locations": [{"state": state, "suburb": suburb, "includeNearbyCities": False}],
        "propertyTypes": property_types,
        "pageSize": page_size,
        "page": page,
    }
    url = f"{_BASE_URL}/listings/residential/_search"
    log.debug(f"POST {url} suburb={suburb!r} page={page}")
    response = await client.post(url, json=payload)
    response.raise_for_status()
    return response.json()


@retry_on_failure(max_attempts=3, base_delay_seconds=2.0, backoff_factor=2.0)
async def _get_listing_detail(client: httpx.AsyncClient, listing_id: int) -> Dict[str, Any]:
    """
    GET /v1/listings/{id} for a single listing.

    Rate-limited and retried with exponential backoff on failure.

    Args:
        client:     Shared httpx.AsyncClient
        listing_id: Domain listing ID

    Returns:
        Raw API response dict
    """
    await _rate_limiter.wait()
    url = f"{_BASE_URL}/listings/{listing_id}"
    log.debug(f"GET {url}")
    response = await client.get(url)
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Public scraping functions (entry points)
# ---------------------------------------------------------------------------


async def scrape_search(
    suburbs: Optional[List[str]] = None,
    state: str = "VIC",
    property_types: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Search for residential sale listings across a list of Melbourne suburbs.

    Paginates through all available pages for each suburb and returns a flat
    list of normalised listing objects matching the existing output shape.

    Args:
        suburbs:        Suburb names to search. Defaults to DOMAIN_SUBURBS env var
                        or the built-in Melbourne defaults.
        state:          State code (default "VIC").
        property_types: Domain property type strings. Defaults to
                        DOMAIN_PROPERTY_TYPES env var or built-in defaults.

    Returns:
        List of parsed listing dicts.
    """
    if suburbs is None:
        suburbs = _get_suburbs()
    if property_types is None:
        property_types = _get_property_types()

    headers = _build_headers()
    all_results: List[Dict[str, Any]] = []

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        for suburb in suburbs:
            log.info(f"Searching suburb: {suburb!r}")
            page = 1
            while True:
                try:
                    raw = await _search_suburb(client, suburb, state, property_types, page=page)
                except Exception as exc:
                    log.error(
                        f"Search failed for suburb={suburb!r} page={page}: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    break

                if not raw:
                    log.debug(f"No results for suburb={suburb!r} page={page}, stopping pagination")
                    break

                page_results = [parse_listing_summary(item) for item in raw]
                all_results.extend(page_results)
                log.info(f"suburb={suburb!r} page={page}: got {len(page_results)} listings")

                # Domain API returns fewer results than page_size on the last page
                if len(raw) < 200:
                    break
                page += 1

    log.success(f"scrape_search: total {len(all_results)} listings across {len(suburbs)} suburbs")
    return all_results


async def scrape_properties(listing_ids: List[int]) -> List[Dict[str, Any]]:
    """
    Fetch full listing detail for a list of Domain listing IDs.

    Rate-limited and retried per request; errors are logged and skipped.

    Args:
        listing_ids: List of integer Domain listing IDs.

    Returns:
        List of parsed property detail dicts.
    """
    headers = _build_headers()
    properties: List[Dict[str, Any]] = []

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        for listing_id in listing_ids:
            try:
                raw = await _get_listing_detail(client, listing_id)
                properties.append(parse_listing_detail(raw))
            except Exception as exc:
                log.error(
                    f"Failed to fetch listing detail id={listing_id}: "
                    f"{type(exc).__name__}: {exc}"
                )

    log.success(f"scrape_properties: fetched {len(properties)} of {len(listing_ids)} listings")
    return properties


async def scrape_domain(
    suburbs: Optional[List[str]] = None,
    property_types: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Top-level entry point: search all configured suburbs and return results.

    Writes output to results/search.json.

    Args:
        suburbs:        Override suburb list (default: env var / built-in defaults).
        property_types: Override property types (default: env var / built-in defaults).

    Returns:
        List of listing dicts written to results/search.json.
    """
    results = await scrape_search(suburbs=suburbs, property_types=property_types)

    out_path = output / "search.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    log.success(f"Written {len(results)} listings to {out_path}")
    return results
