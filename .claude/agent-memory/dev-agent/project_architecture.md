---
name: Project Architecture & Package Boundaries
description: Key architectural constraints and package boundaries for the Undervalued House Finder monorepo
type: project
---

Each package is independently installable with its own pyproject.toml and Poetry env (DEC-001). Cross-package imports use sys.path manipulation — see ingestion/src/ingestion/ingester.py:12 as canonical example.

Package roles:

- `models/` — Pydantic v2 only, no DB deps. Contains Listing, EventTimeline, normalizers.
- `ingestion/` — reads from models/, writes to Supabase. Ingester.\_save_events() persists events.
- `scaper/realestatecom-scraper/` — standalone, uses Scrapfly SDK. Credentials via SCRAPFLY_KEY env var.
- `scaper/domaincom-scraper/` — standalone, uses Scrapfly SDK. Credentials via SCRAPFLY_KEY env var.

**Why:** DEC-001 mandates isolation. No shared lockfile. Changes to shared logic must be duplicated across independent packages (e.g., scraper_utils.py is intentionally duplicated in both scrapers).

**How to apply:** Never add cross-package imports except via sys.path. Never add ingestion/DB deps to models/. When adding shared scraper logic, duplicate it into each scraper package.
