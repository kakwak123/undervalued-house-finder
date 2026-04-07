"""System health state tracking for the dashboard health bar."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel


class ServiceStatus(BaseModel):
    name: str
    status: str  # "ok" | "degraded" | "error" | "unknown"
    detail: Optional[str] = None


class SchedulerInfo(BaseModel):
    next_run: str  # ISO 8601
    interval_minutes: int


class HealthState(BaseModel):
    scraper: ServiceStatus
    supabase: ServiceStatus
    scrapfly_credits: int
    scheduler: SchedulerInfo


def _default_next_run() -> str:
    """Return tomorrow at 06:00 UTC as the mocked next run timestamp."""
    now = datetime.now(timezone.utc)
    tomorrow_6am = (now + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
    return tomorrow_6am.isoformat()


# Mutable singleton — updated by trigger handlers and startup checks.
_state: Dict[str, Any] = {
    "scraper": ServiceStatus(name="scraper", status="unknown"),
    "supabase": ServiceStatus(name="supabase", status="unknown"),
    "scrapfly_credits": 1240,  # Mocked — replace with real Scrapfly API call when available.
    "scheduler": SchedulerInfo(next_run=_default_next_run(), interval_minutes=1440),
}


def get_health() -> HealthState:
    return HealthState(**_state)


def set_scraper_status(status: str, detail: str | None = None) -> None:
    _state["scraper"] = ServiceStatus(name="scraper", status=status, detail=detail)


def set_supabase_status(status: str, detail: str | None = None) -> None:
    _state["supabase"] = ServiceStatus(name="supabase", status=status, detail=detail)


def set_scrapfly_credits(credits: int) -> None:
    _state["scrapfly_credits"] = credits


def set_next_run(next_run_iso: str, interval_minutes: int = 1440) -> None:
    _state["scheduler"] = SchedulerInfo(next_run=next_run_iso, interval_minutes=interval_minutes)
