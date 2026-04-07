# DECISION_LOG.md

Managed by the **Architect Agent**. All agents must read this before implementing.
`Accepted` decisions are binding. To override one, log a new decision with `Supersedes: DEC-NNN`.

---

## Decision Template

```
### DEC-NNN — Title
- **Date:** YYYY-MM-DD
- **Status:** Proposed | Accepted | Rejected | Superseded by DEC-NNN
- **Agent:** Architect | Dev
- **Context:** Why this decision was needed.
- **Decision:** What was decided.
- **Consequences:** Trade-offs, what this rules out, what it enables.
```

---

## Accepted Decisions

### DEC-001 — Monorepo with independent Poetry packages

- **Date:** 2026-04-07
- **Status:** Accepted
- **Agent:** Architect
- **Context:** Project spans scraping, data models, ingestion, API, and frontend. Need isolation between layers without a complex build system.
- **Decision:** Each package (`models/`, `ingestion/`, future `api/`) has its own `pyproject.toml` and Poetry environment. Root `pyproject.toml` is for dev tooling only (black, ruff).
- **Consequences:** Each package installs independently. Cross-package imports are resolved via `sys.path` manipulation at runtime (acceptable for now). No shared lockfile — versions may drift between packages over time.

---

### DEC-002 — Pydantic v2 for all data models

- **Date:** 2026-04-07
- **Status:** Accepted
- **Agent:** Architect
- **Context:** Need validated, serialisable models that can round-trip to JSON and Supabase.
- **Decision:** All data models use Pydantic v2 (`BaseModel`). No dataclasses or plain dicts for domain objects.
- **Consequences:** Strong validation and JSON serialisation out of the box. `model_dump_json()` used for serialisation. Pydantic v1 syntax (`.dict()`, `.json()`) must not be used.

---

### DEC-003 — Supabase (PostgreSQL) as the database

- **Date:** 2026-04-07
- **Status:** Accepted
- **Agent:** Architect
- **Context:** Need a hosted PostgreSQL database with a REST API that works without standing up infrastructure.
- **Decision:** Supabase is the database layer. Schema defined in `ingestion/supabase_schema.sql`. Two tables: `listings` (upsert by `listing_id`) and `events` (append-only, UUID PK).
- **Consequences:** No local DB setup required. Supabase anon key must never be hardcoded — always via `SUPABASE_URL` / `SUPABASE_KEY` env vars. Migration workflow is manual (run SQL in Supabase dashboard or CLI).

---

### DEC-004 — EventTimeline is in-memory; persistence is the Ingester's job

- **Date:** 2026-04-07
- **Status:** Accepted
- **Agent:** Architect
- **Context:** `models/` must have no knowledge of the database. Events need to be usable in tests without any DB dependency.
- **Decision:** `EventTimeline` is a pure in-memory structure in `models/`. The `Ingester` in `ingestion/` is responsible for persisting events to Supabase via `_save_events()`.
- **Consequences:** `models/` stays dependency-free (only pydantic). Any code that needs durable events must go through `ingestion/`. Tests for event logic do not need a DB.

---

### DEC-005 — Idempotent ingestion via upsert

- **Date:** 2026-04-07
- **Status:** Accepted
- **Agent:** Architect
- **Context:** Scrapers will be re-run on a schedule. The same listing will appear in multiple scrape runs.
- **Decision:** Listings are upserted by `listing_id`. Events are deduplicated by checking for an existing event with the same `listing_id`, `event_type`, and `timestamp` before inserting.
- **Consequences:** Re-running ingestion on the same data is safe. Event deduplication is timestamp-based — events with identical timestamps and types are considered duplicates.

---

### DEC-006 — Scraper credentials (Scrapfly) via environment variables

- **Date:** 2026-04-07
- **Status:** Accepted
- **Agent:** Architect
- **Context:** Scrapers use Scrapfly API for anti-bot bypass. API keys must not be committed.
- **Decision:** All external API keys (Scrapfly, Supabase) are read from environment variables. `.env.example` files document required variables. `.env` is gitignored.
- **Consequences:** Any new secret must get an entry in the relevant `.env.example`. CI/CD must inject secrets via environment.

---

## Proposed Decisions

_Architect Agent reviews these and moves them to Accepted or Rejected._

| ID      | Title                                                        | Raised by | Date       |
| ------- | ------------------------------------------------------------ | --------- | ---------- |
| DEC-007 | scraper_utils.py duplicated per package                      | Dev       | 2026-04-07 |
| DEC-008 | Sequential page fetching replaces concurrent                 | Dev       | 2026-04-07 |
| DEC-009 | Scheduler lives in ingestion/ package                        | Dev       | 2026-04-07 |
| DEC-010 | Valuation logic lives in models/ package                     | Dev       | 2026-04-07 |
| DEC-011 | Suburb medians in JSON seed file, not Python dicts           | Dev       | 2026-04-07 |
| DEC-012 | Distress signal merges in-memory + persisted events          | Dev       | 2026-04-07 |
| DEC-013 | API package on port 8001 (8000 = debug dashboard)            | Dev       | 2026-04-07 |
| DEC-014 | Opportunity score computed on-the-fly in API, not pre-cached | Dev       | 2026-04-07 |

---

### DEC-007 — scraper_utils.py duplicated per independent scraper package

- **Date:** 2026-04-07
- **Status:** Proposed
- **Agent:** Dev
- **Context:** S-3 required shared rate-limiting and retry logic for both scrapers. No shared `scaper/` package exists; DEC-001 mandates each package is independently installable with its own `pyproject.toml`. A third shared package would require adding it as a dependency in both scrapers, which adds coordination overhead and goes beyond S-3 scope.
- **Decision:** `scraper_utils.py` is duplicated verbatim into `scaper/realestatecom-scraper/` and `scaper/domaincom-scraper/`. Both copies are identical and tested identically.
- **Consequences:** Changes to rate limiting or retry logic must be applied to both copies. The duplication is intentional and acceptable given independent package model. If a future item introduces a third scraper, revisiting a shared package becomes worthwhile.

---

### DEC-008 — Sequential page fetching replaces concurrent_scrape for pagination

- **Date:** 2026-04-07
- **Status:** Proposed
- **Agent:** Dev
- **Context:** The original scrapers used `SCRAPFLY.concurrent_scrape()` for both property pages and pagination, which fires all requests in parallel and bypasses any per-request rate limiting. Applying a rate limiter to concurrent requests requires a semaphore-based approach that significantly increases complexity.
- **Decision:** Pagination loops now fetch pages sequentially (one `await _fetch_search_page()` per iteration). Each fetch goes through the module-level `RateLimiter`, guaranteeing at least 2s between requests. Property pages in `scrape_properties` are also fetched sequentially for the same reason.
- **Consequences:** Scrape throughput is lower than the original concurrent approach. This is an explicit trade-off required by the 2s minimum delay policy. If throughput becomes a bottleneck, a semaphore-gated concurrent approach can be introduced as a future optimisation.

---

### DEC-009 — Scheduler lives in the ingestion/ package

- **Date:** 2026-04-07
- **Status:** Proposed
- **Agent:** Dev
- **Context:** S-1 required an APScheduler-based daemon. The scheduler orchestrates the full scrape-to-ingest pipeline, which is already in `ingestion/`. Alternatives were a top-level `scheduler/` package or embedding it in a scraper package.
- **Decision:** `Scheduler` class added to `ingestion/src/ingestion/scheduler.py`. Standalone entry point at `ingestion/scheduler.py` (mirrors `ingestion/pipeline.py` and `ingestion/ingest.py` conventions). APScheduler added as a dependency to `ingestion/pyproject.toml`.
- **Consequences:** Running the scheduler requires the ingestion package to be installed with its full dependencies including APScheduler. Scraper packages remain unchanged. The scheduler imports scrapers at job-call time (not module-import time) so scraper package dependencies are only needed at runtime.

---

### DEC-010 — Valuation logic (M2-1, M2-2, M2-3) lives in models/ package

- **Date:** 2026-04-07
- **Status:** Proposed
- **Agent:** Dev
- **Context:** M2-1/M2-2/M2-3 required a price model, undervalue scorer, and threshold detector. These are pure domain-logic computations with no DB dependency. The project note said "not inside backend/".
- **Decision:** All valuation code lives in `models/src/models/valuation.py`. `ValuationClassification` enum added to `models/src/models/enums.py`. `UNDERVALUED_THRESHOLD_CROSSED` added to `EventType`. Three new `Optional` fields (`estimated_price`, `undervalue_score`, `valuation_classification`) added to the `Listing` model.
- **Consequences:** `models/` remains the single source of truth for domain objects and logic. The ingestion layer or a future `api/` package can import and call these directly. No new package was needed.

---

### DEC-011 — Suburb medians in a JSON seed file, configurable via env var

- **Date:** 2026-04-07
- **Status:** Proposed
- **Agent:** Dev
- **Context:** M2-1 requires suburb median prices. No live ABS/Domain API is available yet. Hardcoding dicts in Python source makes data updates require code changes and deploys.
- **Decision:** Median data, bedroom weights, and property-type multipliers are stored in `models/src/models/data/suburb_medians.json`. The `PriceModel` loads this file at construction time. The path can be overridden via the `SUBURB_MEDIANS_PATH` environment variable, allowing updated data to be injected without changing source code.
- **Consequences:** Data updates (e.g. fresh CoreLogic suburb report) only require replacing the JSON file — no Python changes. The bundled seed data is approximate 2024-2025 Melbourne figures and should be validated against actual transaction data when available. [RESEARCH NEEDED]: Validate bedroom weights and property-type multipliers against CoreLogic RP Data transaction records.

---

### DEC-012 — Distress signal detection merges in-memory + persisted events

- **Date:** 2026-04-07
- **Status:** Proposed
- **Agent:** Dev
- **Context:** M3-3 requires detecting AUCTION_VOIDED + PRICE_DROPPED within N days. Either signal may have occurred in a prior run (persisted in Supabase) or in the current run (in-memory EventTimeline only).
- **Decision:** `Ingester._check_distress_signal()` merges events from both `EventTimeline` (current run) and `repository.get_listing_events()` (DB) before evaluating the compound condition.
- **Consequences:** One extra DB read per listing update. Correct across multi-run scenarios. If throughput is a concern, events can be pre-fetched in bulk per ingestion batch.

---

### DEC-013 — API package runs on port 8001

- **Date:** 2026-04-07
- **Status:** Proposed
- **Agent:** Dev
- **Context:** `backend/` debug dashboard already occupies port 8000. The new `api/` production API must not conflict with it during local development.
- **Decision:** `api/src/api/main.py` is documented to run on port 8001 via `uvicorn api.main:app --port 8001`. Port is a CLI argument, not hardcoded in source.
- **Consequences:** Two separate processes required for full local stack. CORS_ORIGINS env var must list the frontend dev server.

---

### DEC-014 — Opportunity score computed on-the-fly in the API

- **Date:** 2026-04-07
- **Status:** Proposed
- **Agent:** Dev
- **Context:** `GET /api/opportunities` must return scored listings. Pre-computing during ingestion would require the ingester to depend on the scoring engine and add a DB write per listing.
- **Decision:** Scores are computed on-the-fly in the API handler using `OpportunityScorer`. The `opportunity_score` DB column is defined in the schema but is not written by the current API (reserved for future pre-computation).
- **Consequences:** Latency on `GET /api/opportunities` is O(n) in listing count. Acceptable for current data volumes. Pre-computing scores during ingestion is the natural next optimisation.

---

## Rejected / Superseded

_None yet._
