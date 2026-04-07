"""
Entry point for the realestate.com.au Playwright scraper.

Uses Playwright + playwright-stealth to bypass Cloudflare protection.
No paid proxy service or API key required.

NOTE: After installing dependencies, run once to download the browser:
    playwright install chromium

Optional env vars:
    REALESTATE_SEARCH_URL   — full search URL (default: Melbourne buy listings)
    REALESTATE_MAX_PAGES    — maximum pages to scrape (default: 3)

Usage:
    poetry install
    playwright install chromium
    poetry run python run.py
"""

import asyncio
import json
from pathlib import Path

from realestate import scrape_search, _get_search_url, _get_max_pages

output = Path(__file__).parent / "results"
output.mkdir(exist_ok=True)

SEARCH_URL = _get_search_url()
MAX_PAGES = _get_max_pages()


if __name__ == "__main__":
    print(f"Running realestate.com.au Playwright scrape")
    print(f"Search URL: {SEARCH_URL}")
    print(f"Max pages: {MAX_PAGES}")
    print("Saving results to ./results/search.json")

    search_data = asyncio.run(scrape_search(url=SEARCH_URL, max_scrape_pages=MAX_PAGES))

    out_path = output / "search.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(search_data, fh, indent=2, ensure_ascii=False)
    print(f"Written {len(search_data)} listings to {out_path}")
