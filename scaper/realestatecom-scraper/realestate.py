"""
realestate.com.au Playwright scraper — replaces Scrapfly dependency.

Uses Playwright (async API) + playwright-stealth to bypass Cloudflare protection.
Listing data is embedded in a <script id="__NEXT_DATA__"> JSON tag — no UI interaction needed.

NOTE: After installing dependencies, run:
    playwright install chromium

Required env vars:
    (none — public site, no auth required)

Optional env vars:
    REALESTATE_SEARCH_URL   — full search URL to scrape (default: Melbourne buy listings)
    REALESTATE_MAX_PAGES    — maximum pages to scrape per run (default: 3)
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import jmespath
from loguru import logger as log
from playwright.async_api import Page, async_playwright
from playwright_stealth import Stealth

async def stealth_async(page):
    """Compatibility shim for playwright-stealth v2."""
    await Stealth().apply_stealth_async(page)

from scraper_utils import RateLimiter, retry_on_failure

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_SEARCH_URL: str = (
    "https://www.realestate.com.au/buy/in-melbourne,+vic/list-1"
)
_DEFAULT_MAX_PAGES: int = 3

# Module-level rate limiter: enforces minimum 2s between sequential requests
_rate_limiter = RateLimiter(min_delay_seconds=2.0)

output = Path(__file__).parent / "results"
output.mkdir(exist_ok=True)


def _get_search_url() -> str:
    """Read search URL from REALESTATE_SEARCH_URL env var, or fall back to default."""
    return os.environ.get("REALESTATE_SEARCH_URL", _DEFAULT_SEARCH_URL)


def _get_max_pages() -> int:
    """Read max pages from REALESTATE_MAX_PAGES env var, or fall back to default."""
    raw = os.environ.get("REALESTATE_MAX_PAGES", "")
    if raw.strip().isdigit():
        return int(raw.strip())
    return _DEFAULT_MAX_PAGES


def _get_headless() -> bool:
    """Return False if REALESTATE_HEADLESS=false, so browser is visible."""
    return os.environ.get("REALESTATE_HEADLESS", "true").lower() not in ("false", "0", "no")


# ---------------------------------------------------------------------------
# Page data extraction
# ---------------------------------------------------------------------------


def _extract_next_data(page_content: str) -> Optional[Dict[str, Any]]:
    """
    Extract and parse the JSON payload embedded in <script id="__NEXT_DATA__">.

    Args:
        page_content: Raw HTML of the page.

    Returns:
        Parsed JSON dict, or None if the script tag is not found.
    """
    match = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        page_content,
        re.DOTALL,
    )
    if not match:
        log.warning("__NEXT_DATA__ script tag not found in page")
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        log.error(f"Failed to parse __NEXT_DATA__ JSON: {exc}")
        return None


def _extract_argonaut_data(page_content: str) -> Optional[Dict[str, Any]]:
    """
    Extract and parse the window.ArgonautExchange JSON payload used by
    realestate.com.au for listing data on search and detail pages.

    Args:
        page_content: Raw HTML of the page.

    Returns:
        Parsed innermost JSON dict, or None on any failure.
    """
    match = re.search(r"window\.ArgonautExchange\s*=\s*(\{.+?\});", page_content, re.DOTALL)
    if not match:
        log.warning("window.ArgonautExchange not found in page")
        return None
    try:
        data = json.loads(match.group(1))
        data = json.loads(data["resi-property_listing-experience-web"]["urqlClientCache"])
        data = json.loads(list(data.values())[0]["data"])
        return data
    except (KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
        log.error(f"Failed to parse ArgonautExchange data: {type(exc).__name__}: {exc}")
        return None


def parse_property_data(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Refine a single property listing dict using jmespath projection.

    Preserves the exact output shape expected by the ingestion pipeline.

    Args:
        data: Raw listing object from the JSON payload.

    Returns:
        Projected dict, or None if data is empty/None.
    """
    if not data:
        return None
    result: Optional[Dict[str, Any]] = jmespath.search(
        """{
        id: id,
        propertyType: propertyType.display,
        description: description,
        propertyLink: _links.canonical.href,
        address: address,
        propertySizes: propertySizes,
        generalFeatures: generalFeatures,
        propertyFeatures: propertyFeatures[].{featureName: displayLabel, value: value},
        images: media.images[].templatedUrl,
        videos: videos,
        floorplans: floorplans,
        listingCompany: listingCompany.{
            name: name,
            id: id,
            companyLink: _links.canonical.href,
            phoneNumber: businessPhone,
            address: address.display.fullAddress,
            ratingsReviews: ratingsReviews,
            description: description
        },
        listers: listers,
        auction: auction
        }""",
        data,
    )
    return result


def parse_search_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract listing cards and pagination info from a search-page ArgonautExchange payload.

    Args:
        data: Parsed ArgonautExchange dict for a search page.

    Returns:
        Dict with keys ``search_data`` (list of property dicts) and
        ``max_search_pages`` (int).
    """
    inner = list(data.values())[0] if data else {}
    results = inner.get("results", {})
    items = results.get("exact", {}).get("items", [])
    max_pages: int = results.get("pagination", {}).get("maxPageNumberAvailable", 1)

    search_data: List[Optional[Dict[str, Any]]] = []
    for item in items:
        listing = item.get("listing")
        if listing:
            search_data.append(parse_property_data(listing))

    return {"search_data": [d for d in search_data if d], "max_search_pages": max_pages}


# ---------------------------------------------------------------------------
# Playwright fetch helpers
# ---------------------------------------------------------------------------


async def _navigate_with_rate_limit(page: Page, url: str) -> str:
    """
    Navigate to a URL with rate limiting applied before the request.

    Args:
        page: Playwright Page instance.
        url:  URL to navigate to.

    Returns:
        Full HTML content of the loaded page.
    """
    await _rate_limiter.wait()
    log.debug(f"Navigating to {url!r}")
    await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    return await page.content()


@retry_on_failure(max_attempts=3, base_delay_seconds=2.0, backoff_factor=2.0)
async def _fetch_search_page(page: Page, url: str) -> Dict[str, Any]:
    """
    Fetch a search page and return parsed search data + pagination info.

    Rate-limited (2s minimum inter-request delay) and retried with
    exponential backoff on failure.

    Args:
        page: Shared Playwright Page instance (stealth already applied).
        url:  Search page URL.

    Returns:
        Dict with ``search_data`` and ``max_search_pages`` keys.
    """
    html = await _navigate_with_rate_limit(page, url)
    data = _extract_argonaut_data(html)
    if data is None:
        # Fall back to __NEXT_DATA__ for pages that don't use ArgonautExchange
        next_data = _extract_next_data(html)
        if next_data is None:
            raise ValueError(f"No usable JSON data found on search page: {url!r}")
        data = next_data
    return parse_search_data(data)


@retry_on_failure(max_attempts=3, base_delay_seconds=2.0, backoff_factor=2.0)
async def _fetch_property_page(page: Page, url: str) -> Optional[Dict[str, Any]]:
    """
    Fetch a property detail page and return parsed property data.

    Rate-limited (2s minimum inter-request delay) and retried with
    exponential backoff on failure.

    Args:
        page: Shared Playwright Page instance (stealth already applied).
        url:  Property detail page URL.

    Returns:
        Parsed property dict, or None if data could not be extracted.
    """
    html = await _navigate_with_rate_limit(page, url)
    data = _extract_argonaut_data(html)
    if data is None:
        log.warning(f"ArgonautExchange not found on property page {url!r}; skipping")
        return None
    details = data.get("details", {}).get("listing")
    if details is None:
        log.warning(f"No 'details.listing' key in ArgonautExchange data for {url!r}; skipping")
        return None
    return parse_property_data(details)


# ---------------------------------------------------------------------------
# Public scraping functions (entry points)
# ---------------------------------------------------------------------------


async def scrape_search(
    url: Optional[str] = None,
    max_scrape_pages: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Scrape property listings from realestate.com.au search pages.

    Uses Playwright + playwright-stealth for Cloudflare bypass. Extracts data
    from the embedded __NEXT_DATA__ / ArgonautExchange JSON tags — no UI
    interaction required.

    Args:
        url:             Search URL (default: REALESTATE_SEARCH_URL env var or built-in default).
        max_scrape_pages: Maximum pages to scrape (default: REALESTATE_MAX_PAGES env var or 3).

    Returns:
        Flat list of parsed listing dicts.
    """
    if url is None:
        url = _get_search_url()
    if max_scrape_pages is None:
        max_scrape_pages = _get_max_pages()

    log.info(f"scrape_search: url={url!r} max_pages={max_scrape_pages}")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=_get_headless())
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-AU",
        )
        page = await context.new_page()
        await stealth_async(page)

        try:
            # --- First page ---
            try:
                first_result = await _fetch_search_page(page, url)
            except Exception as exc:
                log.error(f"Failed to fetch first search page {url!r}: {type(exc).__name__}: {exc}")
                return []

            search_data: List[Dict[str, Any]] = first_result["search_data"]
            max_available: int = first_result["max_search_pages"]
            effective_max = min(max_scrape_pages, max_available)

            log.info(
                f"First page returned {len(search_data)} listings; "
                f"max_available={max_available}, will scrape up to {effective_max} pages"
            )

            # --- Remaining pages ---
            # Build page URLs by replacing the trailing list-N segment
            base_url = re.sub(r"/list-\d+", "", url.rstrip("/"))

            for page_num in range(2, effective_max + 1):
                page_url = f"{base_url}/list-{page_num}"
                try:
                    result = await _fetch_search_page(page, page_url)
                    search_data.extend(result["search_data"])
                    log.info(f"Page {page_num}: +{len(result['search_data'])} listings")
                except Exception as exc:
                    log.error(
                        f"Failed to scrape search page {page_url!r}: "
                        f"{type(exc).__name__}: {exc}"
                    )

        finally:
            await browser.close()

    log.success(f"scrape_search: total {len(search_data)} listings from {url!r}")
    return search_data


async def scrape_properties(urls: List[str]) -> List[Dict[str, Any]]:
    """
    Fetch full listing detail for a list of realestate.com.au property page URLs.

    Rate-limited and retried per request; errors are logged and skipped.

    Args:
        urls: List of property detail page URLs.

    Returns:
        List of parsed property detail dicts (failed pages are omitted).
    """
    properties: List[Dict[str, Any]] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=_get_headless())
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-AU",
        )
        page = await context.new_page()
        await stealth_async(page)

        try:
            for url in urls:
                try:
                    data = await _fetch_property_page(page, url)
                    if data:
                        properties.append(data)
                except Exception as exc:
                    log.error(
                        f"Failed to scrape property page {url!r}: "
                        f"{type(exc).__name__}: {exc}"
                    )
        finally:
            await browser.close()

    log.success(f"scrape_properties: scraped {len(properties)} of {len(urls)} listings")
    return properties
