# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Root-level (linting/formatting)

```bash
make format          # Format all Python code with black (line-length 120)
make lint            # Lint code with ruff
make install         # Install root-level dev dependencies via poetry
make clean           # Remove __pycache__, .pyc, .egg-info
```

### Models package

```bash
cd models
poetry install
poetry run pytest tests/                     # Run all model tests
poetry run pytest tests/test_models.py::test_listing_creation  # Run single test
```

### Ingestion package

```bash
cd ingestion
poetry install
# OR: pip3 install -r requirements.txt

python3 ingest.py ../testdata/search.json
python3 ingest.py ../scaper/realestatecom-scraper/results/search.json --source realestate
python3 ingest.py ../scaper/domaincom-scraper/results/search.json --source domain
```

### Scrapers

```bash
cd scaper/realestatecom-scraper && poetry install && poetry run python run.py
cd scaper/domaincom-scraper && poetry install && poetry run python run.py
```

## Architecture

This is a Python monorepo with independently-installable packages, each with its own `pyproject.toml` and Poetry environment.

### Data flow

```
Scrapers → JSON files → Ingestion → Supabase DB
              ↑                         ↑
         testdata/search.json      listings + events tables
```

### Package responsibilities

**`models/`** — Core Pydantic v2 data models (no external dependencies except pydantic):

- `Listing` — central model with price/auction history tracking methods (`add_price_record`, `add_auction_record`)
- `EventTimeline` — in-memory event store, queryable by listing ID and event type
- `normalizers.py` — converts raw scraper JSON → `Listing` objects (`normalize_realestate_data`, `normalize_domain_data`)
- `enums.py` — `ListingStatus`, `PropertyType`, `EventType`

**`ingestion/`** — Reads JSON files and persists to Supabase:

- `Ingester` — orchestrates idempotent upserts with change detection; generates `PRICE_DROPPED`, `AUCTION_CANCELLED`, `AUCTION_VOIDED`, `AUCTION_RESCHEDULED` events when data changes between runs
- `SupabaseRepository` (`database.py`) — wraps Supabase client for listings/events CRUD
- `RealestateReader` / `DomainReader` (`readers.py`) — parse scraper JSON into `Listing` models via `normalizers.py`
- `ingest.py` — standalone script entry point (sets `PYTHONPATH` internally to find `models`)

**`scaper/`** — Two independent scrapers (realestate.com.au and domain.com.au). Output is JSON written to `results/` (gitignored).

### Key design decisions

- `EventTimeline` is in-memory; events are persisted to Supabase `events` table by `Ingester._save_events()`
- Ingestion is idempotent: listings use upsert by `listing_id`; events check timestamp+type before inserting
- `models/` has no dependency on `ingestion/`; `ingestion/` imports from `models/` by manipulating `sys.path` at runtime (`ingester.py:12`)
- Database schema is defined in `ingestion/supabase_schema.sql`. Two tables: `listings` (upserted by `listing_id`) and `events` (append-only, UUID PK)
- Credentials via `SUPABASE_URL` / `SUPABASE_KEY` env vars or `.env` file

## Domain Knowledge

**Undervalue score:**

```
(Predicted Price - Listed Price) / Predicted Price × 100
```

- > 10% = potentially undervalued; > 20% = significantly undervalued; < 0% = overpriced

**Melbourne auction context:**

- Auctions are the dominant sales method (60–80% of Melbourne sales)
- "Passed in" = property did not sell; highest bid was below vendor reserve — properties that pass in often re-list lower, which is a key signal
- School zones and distance to Melbourne CBD (Flinders St Station) are strong price predictors
- Clearance rates and days-on-market are key suburb-level signals

**Data freshness targets:**

- Listings: daily
- Auction results: Saturday night + Sunday morning
- Price drops: every 2–3 days
- Suburb median trends: weekly

## Planned Tech Stack

When building out `api/`, `webapp/`, and `model/` packages (not yet implemented):

- **ML**: scikit-learn → XGBoost / LightGBM (do not simplify to linear regression)
- **Scraping**: httpx + BeautifulSoup; Playwright for JS-heavy pages; minimum 2s delay between requests
- **Backend**: FastAPI with `async/await` throughout
- **Frontend**: React 18 + Tailwind CSS + Recharts; functional components only
- **Scheduling**: APScheduler for recurring scrape jobs

## Code Style

- Python: PEP8, type hints, line-length 120 (enforced by black + ruff)
- File naming: `snake_case` for Python, `camelCase` for React components
- Scrapers must handle failures gracefully and log errors — never crash silently
- Do not hardcode suburb lists — make them dynamic/configurable
