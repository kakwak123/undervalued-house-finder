"""FastAPI application entry point for the Live Agent Activity Dashboard.

Run with:
    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import os

import sys
from decimal import Decimal
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.event_bus import EventCategory, publish
from backend.health import get_health
from backend.triggers import reset_events, run_ingestion, run_scraper, run_valuation, _price_model
from backend.ws_manager import manager

# Allow importing models/ (DEC-001)
# __file__ = backend/backend/main.py → parents[2] = project root
_models_src = Path(__file__).resolve().parents[2] / "models" / "src"
if str(_models_src) not in sys.path:
    sys.path.insert(0, str(_models_src))

from models.enums import PropertyType  # noqa: E402
from models.valuation import compute_undervalue_score  # noqa: E402

load_dotenv()

app = FastAPI(title="Undervalued House Finder — Activity Dashboard", version="0.1.0")

# ---------------------------------------------------------------------------
# CORS — allow the Vite dev server to reach this API.
# ---------------------------------------------------------------------------
_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def _startup() -> None:
    await publish(EventCategory.SYSTEM, "Dashboard backend started")


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@app.websocket("/ws/activity")
async def ws_activity(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive; we only push from the server side.
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health() -> dict:  # type: ignore[type-arg]
    return get_health().model_dump()


@app.post("/api/scrape")
async def scrape() -> dict:  # type: ignore[type-arg]
    result = await run_scraper()
    return result


@app.post("/api/ingest")
async def ingest() -> dict:  # type: ignore[type-arg]
    result = await run_ingestion()
    return result


@app.post("/api/valuation")
async def valuation() -> dict:  # type: ignore[type-arg]
    result = await run_valuation()
    return result


@app.post("/api/reset-events")
async def reset() -> dict:  # type: ignore[type-arg]
    result = await reset_events()
    return result


@app.get("/api/valuation/estimate")
async def estimate(
    suburb: str = Query(..., description="Melbourne suburb name"),
    property_type: str = Query("house", description="house | unit | townhouse | apartment"),
    bedrooms: Optional[int] = Query(None, description="Number of bedrooms"),
    listed_price: Optional[float] = Query(None, description="Listed asking price in AUD"),
) -> dict:  # type: ignore[type-arg]
    """Return an estimated price and optional undervalue score for a property."""
    try:
        pt = PropertyType(property_type.lower())
    except ValueError:
        return {"error": f"Unknown property_type '{property_type}'. Use: house, unit, townhouse, apartment"}

    estimated = _price_model.estimate(suburb, pt, bedrooms)
    response: dict = {
        "suburb": suburb,
        "property_type": pt.value,
        "bedrooms": bedrooms,
        "estimated_price": str(estimated),
        "known_suburb": suburb.strip().title() in _price_model.known_suburbs(),
    }

    if listed_price is not None:
        result = compute_undervalue_score("adhoc", Decimal(str(listed_price)), estimated)
        response["listed_price"] = str(listed_price)
        response["price_difference"] = str(result.price_difference)
        response["undervalue_score"] = result.undervalue_score
        response["classification"] = result.classification.value

    return response


@app.get("/api/valuation/suburbs")
async def suburbs() -> dict:  # type: ignore[type-arg]
    """Return all suburbs with known median data."""
    return {"suburbs": sorted(_price_model.known_suburbs())}
