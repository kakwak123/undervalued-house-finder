"""
This is an example web scraper for realestate.com.au

To run this scraper set env variable $SCRAPFLY_KEY with your scrapfly API key:
$ export $SCRAPFLY_KEY="your key from https://scrapfly.io/dashboard"
"""
import os
import re
import json
import jmespath
from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse
from typing import Dict, List
from pathlib import Path
from loguru import logger as log

from scraper_utils import RateLimiter, retry_on_failure

SCRAPFLY = ScrapflyClient(key=os.environ["SCRAPFLY_KEY"])

BASE_CONFIG = {
    # bypass realesta.com.au scraping blocking
    "asp": True,
    # set the proxy country location
    "country": "US",
    "render_js": True,
}

# Module-level rate limiter: enforces minimum 2s between sequential requests
_rate_limiter = RateLimiter(min_delay_seconds=2.0)


output = Path(__file__).parent / "results"
output.mkdir(exist_ok=True)


def parse_property_data(data: Dict) -> Dict:
    """refine property data from JSON"""
    if not data:
        return
    result = jmespath.search(
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
        listingCompany: listingCompany.{name: name, id: id, companyLink: _links.canonical.href, phoneNumber: businessPhone, address: address.display.fullAddress, ratingsReviews: ratingsReviews, description: description},
        listers: listers,
        auction: auction
        }
        """,
        data,
    )
    return result


def parse_hidden_data(response: ScrapeApiResponse) -> Dict:
    """parse JSON data from script tag"""
    selector = response.selector
    script = selector.xpath(
        "//script[contains(text(),'window.ArgonautExchange')]/text()"
    ).get()
    # data needs to be parsed mutiple times
    data = json.loads(re.findall(r"window.ArgonautExchange=(\{.+\});", script)[0])
    data = json.loads(data["resi-property_listing-experience-web"]["urqlClientCache"])
    data = json.loads(list(data.values())[0]["data"])
    return data


def parse_search_data(data: List[Dict]) -> List[Dict]:
    """refine search data"""
    search_data = []
    data = list(data.values())[0]
    for listing in data["results"]["exact"]["items"]:
        # refine each property listing in the search results
        search_data.append(parse_property_data(listing["listing"]))
    max_search_pages = data["results"]["pagination"]["maxPageNumberAvailable"]
    return {"search_data": search_data, "max_search_pages": max_search_pages}


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
    data = parse_hidden_data(response)["details"]["listing"]
    return parse_property_data(data)


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
    data = parse_search_data(data)
    search_data = data["search_data"]
    # get the number of maximum search pages
    max_search_pages = data["max_search_pages"]
    # scrape all available pages if not max_scrape_pages or max_scrape_pages > max_search_pages
    if max_scrape_pages and max_scrape_pages < max_search_pages:
        max_scrape_pages = max_scrape_pages
    else:
        max_scrape_pages = max_search_pages
    log.info(f"scraping search pagination, remaining ({max_scrape_pages - 1} more pages)")
    # scrape remaining pages sequentially — rate limiter is enforced inside _fetch_search_page
    for page in range(2, max_scrape_pages + 1):
        page_url = str(first_page.context["url"]).split("/list")[0] + f"/list-{page}"
        try:
            response = await _fetch_search_page(page_url)
            page_data = parse_hidden_data(response)
            search_data.extend(parse_search_data(page_data)["search_data"])
        except Exception as e:
            log.error(f"Failed to scrape search page {page_url!r}: {type(e).__name__}: {e}")
    log.success(f"scraped ({len(search_data)}) from {url}")
    return search_data
