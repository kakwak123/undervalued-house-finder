"""
This is an example web scraper for domain.com.au

To run this scraper set env variable $SCRAPFLY_KEY with your scrapfly API key:
$ export $SCRAPFLY_KEY="your key from https://scrapfly.io/dashboard"
"""

import os
import json
import jmespath
from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse
from typing import Dict, List
from pathlib import Path
from loguru import logger as log

from scraper_utils import RateLimiter, retry_on_failure

SCRAPFLY = ScrapflyClient(key=os.environ["SCRAPFLY_KEY"])


BASE_CONFIG = {
    # bypass domain.com.au scraping blocking
    "asp": True,
    # set the proxy country to australia
    "country": "AU",
}

# Module-level rate limiter: enforces minimum 2s between sequential requests
_rate_limiter = RateLimiter(min_delay_seconds=2.0)


output = Path(__file__).parent / "results"
output.mkdir(exist_ok=True)


def parse_hidden_data(response: ScrapeApiResponse):
    """parse json data from script tags"""
    selector = response.selector
    script = selector.xpath("//script[@id='__NEXT_DATA__']/text()").get()
    data = json.loads(script)
    return data["props"]["pageProps"]["componentProps"]


def parse_repoerty_data(response: ScrapeApiResponse):
    """parse json data from script tags"""
    selector = response.selector
    script = selector.xpath("//script[@id='__NEXT_DATA__']/text()").get()
    json_data = json.loads(script)
    # property pages data are found in different structures
    try:  # listed property
        data = json_data["props"]["pageProps"]["componentProps"]
        data = parse_component_props(data)
        return data
    except Exception:  # usually sold property has different data structure
        data = json_data["props"]["pageProps"]
        data = parse_page_props(data)
        return data


def parse_page_props(data: Dict) -> Dict:
    """refine property pages data"""
    if not data:
        return
    data = data["__APOLLO_STATE__"]
    key = next(k for k in data if k.startswith("Property:"))
    data = data[key]
    result = jmespath.search(
        """{
        propertyId: propertyId,
        unitNumber: address.unitNumber,
        streetNumber: address.streetNumber,
        suburb: address.suburb,
        postcode: address.postcode
    }""",
        data,
    )
    # parse the photo data
    image_key = next(k for k in data if k.startswith("media("))
    result["gallery"] = []
    for image in data[image_key]:
        result["gallery"].append(image["url"])
    return result


def parse_component_props(data: Dict) -> Dict:
    """refine property pages data"""
    if not data:
        return
    result = jmespath.search(
        """{
    listingId: listingId,
    listingUrl: listingUrl,
    unitNumber: unitNumber,
    streetNumber: streetNumber,
    street: street,
    suburb: suburb,
    postcode: postcode,
    createdOn: createdOn,
    propertyType: propertyType,
    beds: beds,
    phone: phone,
    agencyName: agencyName,
    propertyDeveloperName: propertyDeveloperName,
    agencyProfileUrl: agencyProfileUrl,
    propertyDeveloperUrl: propertyDeveloperUrl,
    description: description,
    loanfinder: loanfinder,
    schools: schoolCatchment.schools,
    suburbInsights: suburbInsights,
    gallery: gallery,
    listingSummary: listingSummary,
    agents: agents,
    features: features,
    structuredFeatures: structuredFeatures,
    faqs: faqs
    }""",
        data,
    )
    return result


def parse_search_page(data):
    """refine search pages data"""
    if not data:
        return
    data = data["listingsMap"]
    result = []
    # iterate over card items in the search data
    for key in data.keys():
        item = data[key]
        parsed_data = jmespath.search(
            """{
        id: id,
        listingType: listingType,
        listingModel: listingModel
      }""",
            item,
        )
        # execulde the skeletonImages key from the data
        parsed_data["listingModel"].pop("skeletonImages")
        result.append(parsed_data)
    return result


@retry_on_failure(max_attempts=3, base_delay_seconds=2.0, backoff_factor=2.0)
async def _fetch_property_page(url: str) -> Dict:
    """
    Fetch and parse a single property page.

    Rate-limited (2s minimum inter-request delay) and retried with
    exponential backoff (2s → 4s) on failure.

    Args:
        url: Property page URL

    Returns:
        Parsed property data dict
    """
    await _rate_limiter.wait()
    config = ScrapeConfig(url, **BASE_CONFIG)
    response = await SCRAPFLY.async_scrape(config)
    data = parse_repoerty_data(response)
    data["url"] = response.context["url"]
    return data


async def scrape_properties(urls: List[str]) -> List[Dict]:
    """Scrape listing data from property pages with rate limiting and retry."""
    properties = []
    for url in urls:
        try:
            data = await _fetch_property_page(url)
            properties.append(data)
        except Exception as e:
            log.error(f"Failed to scrape property page {url!r}: {type(e).__name__}: {e}")
    log.success(f"scraped {len(properties)} property listings")
    return properties


@retry_on_failure(max_attempts=3, base_delay_seconds=2.0, backoff_factor=2.0)
async def _fetch_search_page(url: str) -> ScrapeApiResponse:
    """
    Fetch a single search page with rate limiting and retry.

    Args:
        url: Search page URL

    Returns:
        ScrapeApiResponse for the page
    """
    await _rate_limiter.wait()
    return await SCRAPFLY.async_scrape(ScrapeConfig(url, **BASE_CONFIG))


async def scrape_search(url: str, max_scrape_pages: int = None) -> List[Dict]:
    """Scrape property listings from search pages with rate limiting and retry."""
    log.info("scraping search page {}", url)
    first_page = await _fetch_search_page(url)
    data = parse_hidden_data(first_page)
    search_data = parse_search_page(data)
    # get the number of maximum search pages
    max_search_pages = data["totalPages"]
    # scrape all available pages if not max_scrape_pages or max_scrape_pages >= max_search_pages
    if max_scrape_pages and max_scrape_pages < max_search_pages:
        max_scrape_pages = max_scrape_pages
    else:
        max_scrape_pages = max_search_pages
    log.info(f"scraping search pagination, remaining ({max_scrape_pages - 1} more pages)")
    # scrape remaining pages sequentially — rate limiter is enforced inside _fetch_search_page
    for page in range(2, max_scrape_pages + 1):
        page_url = str(first_page.context["url"]) + f"?page={page}"
        try:
            response = await _fetch_search_page(page_url)
            page_data = parse_hidden_data(response)
            search_data.extend(parse_search_page(page_data))
        except Exception as e:
            log.error(f"Failed to scrape search page {page_url!r}: {type(e).__name__}: {e}")
    log.success(f"scraped ({len(search_data)}) from {url}")
    return search_data
