---
name: Scraper Implementation Patterns
description: Conventions and decisions for scraper rate limiting, retry, and page fetching
type: project
---

Both scrapers (realestatecom-scraper, domaincom-scraper) now share the same pattern via `scraper_utils.py` (duplicated per DEC-007):

- `RateLimiter(min_delay_seconds=2.0)` — module-level singleton, \_last_call_time initialised to float('-inf') so first call is always free
- `@retry_on_failure(max_attempts=3, base_delay_seconds=2.0, backoff_factor=2.0)` — exponential backoff decorator for async functions
- Pagination loops are sequential (not concurrent_scrape) — rate limiter enforced inside each fetch helper (DEC-008)
- Property pages are also fetched sequentially for the same reason

Test files: `test_rate_limiting.py` in each scraper dir. Run with pytest — does NOT require SCRAPFLY*KEY.
pytest config: `python_files = "test.py test*\*.py"`and`asyncio_mode = "auto"` in each scraper's pyproject.toml.

**Why:** concurrent_scrape bypasses per-request delays; sequential fetching is the only clean way to enforce 2s minimum.
