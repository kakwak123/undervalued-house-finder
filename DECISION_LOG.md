# DECISION_LOG.md

Architectural and design decisions made during implementation. Managed by the Dev Agent.
QA Agent and PM Agent may review and promote `Proposed` decisions to `Accepted`.

---

## [2026-04-07] In-memory event bus with async subscriber list (no external broker)

- **Status**: Proposed
- **Context**: The dashboard needs to broadcast pipeline events to WebSocket clients in real time. Options included Redis pub/sub, an external message broker, or a simple in-process async subscriber list.
- **Decision**: Implemented a pure in-memory event bus (`backend/event_bus.py`) with an async subscriber list and a 500-event ring buffer (Python `collections.deque`). No external broker dependency.
- **Consequences**: Simple to run locally with zero infrastructure. Not suitable for multi-process or multi-worker deployments — if `uvicorn` is scaled to multiple workers the bus state is not shared. Acceptable for the single-process dashboard use case. Must revisit if the backend is ever deployed with `--workers > 1`.
- **Backlog Item**: M6-1 — Live Agent Activity Dashboard

---

## [2026-04-07] WebSocket replay on connect (last 500 events)

- **Status**: Proposed
- **Context**: When the browser connects or reconnects, the activity feed would otherwise be empty even if the backend has been running for some time.
- **Decision**: On WebSocket `connect`, the `ConnectionManager` immediately flushes the ring buffer to the new client before subscribing it to future events. This gives the frontend full history up to 500 events without a separate REST endpoint.
- **Consequences**: Adds a brief burst of messages on connect. With 500 events this is negligible. If the buffer is ever increased significantly, the connect handshake may need to be made incremental.
- **Backlog Item**: M6-1 — Live Agent Activity Dashboard

---

## [2026-04-07] Trigger stubs with simulated events (no real scraper calls)

- **Status**: Proposed
- **Context**: Real scrapers require Scrapfly API keys and network access. The dashboard must be usable without credentials during development.
- **Decision**: `backend/triggers.py` implements all four trigger handlers as async stubs that emit realistic fake events via the event bus. Each function is annotated with `# TODO: wire to real scraper` to make the integration point explicit.
- **Consequences**: The dashboard is fully functional for UI development and demo purposes without any API keys. Wiring real scrapers is a drop-in replacement — callers only need to call `await publish(...)` from the real pipeline code.
- **Backlog Item**: M6-1 — Live Agent Activity Dashboard

---

## [2026-04-07] Frontend event state lifted to DebugPage (prop drilling over context)

- **Status**: Proposed
- **Context**: Multiple panels (DbView, BrowserPreview) need to read the same stream of ActivityEvents that originate from the ActivityFeed WebSocket connection. Options included React Context, a state management library (Zustand/Redux), or simple prop drilling via a shared parent.
- **Decision**: State is lifted to `DebugPage` via an `onEvent` callback prop on `ActivityFeed`. `DebugPage` accumulates all events in a `useState` array and passes slices down to `DbView` and `BrowserPreview` as `recentEvents` props.
- **Consequences**: Simple and transparent — no additional dependencies. Works well for a single-page dashboard. If the event volume grows very large (thousands of events), the accumulated array in React state will cause re-renders; a windowed or time-bounded slice should be introduced at that point.
- **Backlog Item**: M6-1 — Live Agent Activity Dashboard

---

## [2026-04-07] Distress signal detection merges in-memory + persisted events

- **Status**: Proposed
- **Context**: M3-3 requires detecting a compound condition (AUCTION_VOIDED + PRICE_DROPPED within N days). Either signal may have occurred in a prior ingestion run and be stored in Supabase, or it may have been generated in the current in-memory run.
- **Decision**: `Ingester._check_distress_signal()` merges events from both the in-memory `EventTimeline` and the DB (`repository.get_listing_events()`) before checking the compound condition. This ensures that a voided auction from yesterday + a price drop today triggers the signal correctly.
- **Consequences**: One extra DB read per listing update (get_listing_events). Acceptable at current scale. If ingestion throughput becomes a bottleneck, events could be pre-fetched in bulk.
- **Backlog Item**: M3-3 — Voided auction + price drop compound signal

---

## [2026-04-07] API package on port 8001 (port 8000 reserved for debug dashboard)

- **Status**: Proposed
- **Context**: The `backend/` debug dashboard already occupies port 8000. The new `api/` production API must not conflict.
- **Decision**: `api/src/api/main.py` is documented to run on port 8001 via `uvicorn api.main:app --port 8001`. The port is not hardcoded in code — it is a uvicorn CLI argument.
- **Consequences**: Running both services locally requires two terminal processes. CORS_ORIGINS env var must include the frontend dev server port.
- **Backlog Item**: M4-1 — FastAPI project setup

---

## [2026-04-07] Opportunity scoring is computed on-the-fly in the API (not cached in DB)

- **Status**: Proposed
- **Context**: `GET /api/opportunities` must return scored listings. Options were: (a) pre-compute scores during ingestion and store in the `opportunity_score` column, or (b) compute on every API request.
- **Decision**: Scores are computed on-the-fly in the API handler. The `opportunity_score` column in the DB schema is reserved for future pre-computation but is not written to by the current API.
- **Consequences**: Latency on `GET /api/opportunities` grows linearly with listing count. For the current dataset size (hundreds of listings) this is acceptable. Pre-computation during ingestion should be added as a future optimisation once DB write patterns are established.
- **Backlog Item**: M4-2 — Opportunity summary endpoint

---

## [2026-04-07] Vite proxy for /api and /ws (no hardcoded backend URL in frontend)

- **Status**: Proposed
- **Context**: The frontend must reach the FastAPI backend without embedding `localhost:8000` in component code, which would break in any non-local environment.
- **Decision**: `vite.config.ts` proxies `/api` (HTTP) and `/ws` (WebSocket upgrade) to `http://localhost:8000`. All fetch calls and the WebSocket URL use relative paths (`/api/...`, `ws://<host>/ws/activity`).
- **Consequences**: Zero hardcoded backend addresses in frontend source. Changing the backend port only requires updating `vite.config.ts`. Works transparently in production if a reverse proxy (nginx, Caddy) handles the same path prefixes.
- **Backlog Item**: M6-1 — Live Agent Activity Dashboard
