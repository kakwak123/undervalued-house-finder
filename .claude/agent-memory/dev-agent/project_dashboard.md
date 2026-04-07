---
name: Dashboard package structure and integration points
description: Key facts about the backend/ and frontend/ packages added in M6-1 — ports, entry points, and wiring TODOs
type: project
---

`backend/` FastAPI app runs on port 8000 (`uvicorn backend.main:app --reload --port 8000`).
`frontend/` Vite app runs on port 5173 (`npm run dev`). Vite proxies `/api` and `/ws` to `localhost:8000`.

Dashboard route is `/debug` in the frontend.

**Why:** These packages were added for M6-1 (Live Agent Activity Dashboard) as standalone dev-time tooling, not part of the main data pipeline.

**How to apply:** When working on backend/ or frontend/ packages, remember they are independent of models/, ingestion/, and scaper/. Do not import from models/ inside backend/ — the backend is a separate service.

Trigger stubs in `backend/backend/triggers.py` are all marked `# TODO: wire to real scraper`. These are the integration points when real API keys become available.

DECISION_LOG.md was created as part of M6-1 — it did not exist before this milestone.
