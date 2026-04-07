# BACKLOG.md

Managed by the **PM Agent**. Dev Agent picks `Ready` items. QA Agent moves items to `Done`.
See `AGENTS.md` for status/priority definitions and workflow protocol.

---

## Milestone 1 — MVP Foundations

| ID   | Title                                        | Status | Priority | Notes                          |
| ---- | -------------------------------------------- | ------ | -------- | ------------------------------ |
| M1-1 | Initialize repo & project structure          | Done   | P0       |                                |
| M1-2 | Core listing data model (Pydantic)           | Done   | P0       | `models/src/models/listing.py` |
| M1-3 | Event timeline system                        | Done   | P0       | `models/src/models/events.py`  |
| M1-4 | Listing ingestion pipeline (JSON → Supabase) | Done   | P0       | `ingestion/`                   |

---

## Milestone 2 — Valuation & Undervaluation Engine

| ID   | Title                              | Status    | Priority | Notes                                                        |
| ---- | ---------------------------------- | --------- | -------- | ------------------------------------------------------------ |
| M2-1 | Baseline estimated price model     | In Review | P1       | Suburb median + bedroom weighting + property type multiplier |
| M2-2 | Compare estimated vs listing price | In Review | P1       | Depends on M2-1                                              |
| M2-3 | Undervaluation threshold detection | In Review | P1       | Emits `UNDERVALUED_THRESHOLD_CROSSED` event; depends on M2-2 |

---

## Milestone 3 — Auction & Price Signal Intelligence

| ID   | Title                                       | Status      | Priority | Notes                                                                   |
| ---- | ------------------------------------------- | ----------- | -------- | ----------------------------------------------------------------------- |
| M3-1 | Auction cancellation signal handling        | In Progress | P1       | Countdown stops, listing flagged for re-auction                         |
| M3-2 | Re-auction & timing extension detection     | In Progress | P1       | Detect rescheduling, restart countdown                                  |
| M3-3 | Voided auction + price drop compound signal | In Progress | P2       | `DISTRESS_SIGNAL` tag + ranking boost; depends on M3-1, M3-2            |
| M3-4 | Opportunity scoring engine                  | In Progress | P1       | Inputs: undervaluation %, auction failures, price drops, days-on-market |

---

## Milestone 4 — Backend API

| ID   | Title                        | Status      | Priority | Notes                                                           |
| ---- | ---------------------------- | ----------- | -------- | --------------------------------------------------------------- |
| M4-1 | FastAPI project setup        | In Progress | P1       | Depends on M2 + M3 being complete                               |
| M4-2 | Opportunity summary endpoint | In Progress | P1       | Ranked listings, score breakdown, active signals                |
| M4-3 | Listing detail endpoint      | In Progress | P1       | Full listing + chronological event timeline                     |
| M4-4 | Filters & search endpoint    | In Progress | P2       | Suburb, type, price range, undervaluation threshold, pagination |

---

## Milestone 5 — React Web Application

| ID   | Title                                        | Status  | Priority | Notes                                       |
| ---- | -------------------------------------------- | ------- | -------- | ------------------------------------------- |
| M5-1 | React app setup (Vite + TypeScript + Router) | Backlog | P2       | Depends on M4 API being available           |
| M5-2 | Opportunity listing page                     | Backlog | P2       | Property cards, sortable, quick filters     |
| M5-3 | Property detail page                         | Backlog | P2       | Timeline chart, price vs estimated, signals |
| M5-4 | Filter & search UI                           | Backlog | P2       | Sidebar, URL-persisted state                |
| M5-5 | Dashboard & analytics view                   | Backlog | P2       | Suburb trends, signal distribution charts   |
| M5-6 | Responsive design & polish                   | Backlog | P2       | Mobile-first, WCAG, loading states          |

---

## Scraper Infrastructure

| ID  | Title                                               | Status    | Priority | Notes                                                                   |
| --- | --------------------------------------------------- | --------- | -------- | ----------------------------------------------------------------------- |
| S-1 | Scheduler for automated scraping                    | In Review | P1       | APScheduler; daily listings, Saturday night auctions                    |
| S-2 | Scrape-to-ingest pipeline (remove manual JSON step) | In Review | P1       | Chain scraper output directly into ingester                             |
| S-3 | Rate limiting + retry logic in scrapers             | In Review | P1       | Min 2s delay, exponential backoff on failure                            |
| S-4 | Persistent process management                       | Backlog   | P2       | Docker + systemd or Railway/Fly.io deployment; depends on S-1, S-2, S-3 |

---

## Milestone 6 — Debug Dashboard

| ID   | Title                         | Status    | Priority | Notes                                                              |
| ---- | ----------------------------- | --------- | -------- | ------------------------------------------------------------------ |
| M6-1 | Live Agent Activity Dashboard | In Review | P1       | `backend/` FastAPI + WebSocket + `frontend/` React; `/debug` route |

---

## Open Bugs

_Cross-referenced with `QA_LOG.md`. QA Agent maintains this section._

| Bug ID | Linked Item | Summary            | Status |
| ------ | ----------- | ------------------ | ------ |
| —      | —           | No bugs logged yet | —      |
