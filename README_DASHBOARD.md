# Live Agent Activity Dashboard — Local Dev Setup

## Overview

The dashboard has two independent processes:

| Process  | Directory   | Port |
| -------- | ----------- | ---- |
| Backend  | `backend/`  | 8000 |
| Frontend | `frontend/` | 5173 |

The Vite dev server proxies `/api` and `/ws` to the FastAPI backend, so the
frontend never hard-codes the backend address.

---

## Prerequisites

- Python 3.9+ (tested on 3.9.6 — `X | None` union syntax patched to use `Optional`)
- `pip3 install fastapi "uvicorn[standard]" python-dotenv`
- Node.js 16+ and npm

---

## 1. Environment variables

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

The backend loads `.env` automatically via `python-dotenv`. The Supabase
variables are only required if you enable the optional `db` extra in
`backend/pyproject.toml`. Stubs work without any credentials set.

---

## 2. Start the backend

```bash
# Run from repo root (NOT from inside backend/)
pip3 install fastapi "uvicorn[standard]" python-dotenv   # once
python3 -m uvicorn backend.main:app --reload --port 8000
```

The API is now available at `http://localhost:8000`.

WebSocket endpoint: `ws://localhost:8000/ws/activity`

REST endpoints:

| Method | Path              | Action                             |
| ------ | ----------------- | ---------------------------------- |
| GET    | /api/health       | System health state (JSON)         |
| POST   | /api/scrape       | Trigger a simulated scraper run    |
| POST   | /api/ingest       | Trigger a simulated ingestion run  |
| POST   | /api/valuation    | Trigger a simulated valuation pass |
| POST   | /api/reset-events | Clear the in-memory event buffer   |

---

## 3. Start the frontend

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173/debug` in your browser.

---

## 4. How to trigger a pipeline run

Use the **Manual Triggers** bar at the bottom of the `/debug` page:

1. **Run Scraper Now** — simulates fetching listings from realestate.com.au.
   Emits `SCRAPING` events with URL, status code, response time, and listing
   count. These populate the Browser Preview table at the bottom.

2. **Run Ingestion Now** — simulates upsert logic. Emits `INGESTING`,
   `DB_WRITE`, and `EVENT` (e.g. `PRICE_DROPPED`) events. These populate the
   DB Live View counters on the right.

3. **Run Valuation Now** — simulates the undervaluation scoring pass. Emits
   `VALUATION` events with suburb-level counts. Updates the "Undervalued"
   counter in DB Live View.

4. **Reset Events** — clears the in-memory ring buffer on the backend and
   emits a `SYSTEM` confirmation event. The frontend feed is not cleared
   (refresh the page to reset the frontend state).

Buttons disable while their request is in-flight and re-enable when the
backend responds.

---

## 5. Wiring to real scrapers

Each trigger in `backend/backend/triggers.py` contains a
`# TODO: wire to real scraper` comment. Replace the simulated loop with a
call to the appropriate scraper or ingestion module once API keys are
available. The event bus API (`publish(category, message, detail)`) is the
integration point — call it from anywhere in the pipeline.

---

## 6. Run order for a full local session

```
# From repo root:
Terminal 1: python3 -m uvicorn backend.main:app --reload --port 8000
Terminal 2: cd frontend && npm run dev
Browser:    http://localhost:5173/debug
```
