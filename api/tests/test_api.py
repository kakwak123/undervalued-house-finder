"""
Tests for the API endpoints (M4-2, M4-3, M4-4).

Supabase is mocked — no network calls are made.  The TestClient from httpx
drives the FastAPI app in-process.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure models/ is importable before importing the app
# ---------------------------------------------------------------------------
_project_root = Path(__file__).resolve().parents[3]
_models_src = _project_root / "models" / "src"
if str(_models_src) not in sys.path:
    sys.path.insert(0, str(_models_src))

from fastapi.testclient import TestClient  # noqa: E402

# We must patch Supabase BEFORE the app module is imported so that
# get_supabase_client() never actually calls create_client().
_mock_supabase_client = MagicMock()

with patch("api.database.create_client", return_value=_mock_supabase_client):
    from api.main import app  # noqa: E402

client = TestClient(app)


# ---------------------------------------------------------------------------
# Sample fixture data
# ---------------------------------------------------------------------------

_LISTING_ROW: Dict[str, Any] = {
    "listing_id": "prop-001",
    "suburb": "Richmond",
    "property_type": "house",
    "bedrooms": 3,
    "bathrooms": 2,
    "status": "active",
    "current_price": "800000",
    "previous_price": "850000",
    "auction_datetime": None,
    "estimated_price": None,
    "undervalue_score": None,
    "valuation_classification": None,
    "distress_signal": False,
    "opportunity_score": None,
    "property_link": "https://example.com/prop-001",
    "description": "Nice house",
    "source": "realestate",
    "created_at": "2026-01-01T00:00:00+00:00",
    "updated_at": "2026-03-01T00:00:00+00:00",
    "address": {
        "street_number": "1",
        "street_name": "Test St",
        "suburb": "Richmond",
        "state": "VIC",
        "postcode": "3121",
        "full_address": "1 Test St, Richmond VIC 3121",
    },
}

_LISTING_ROW_DISTRESS: Dict[str, Any] = {
    **_LISTING_ROW,
    "listing_id": "prop-002",
    "suburb": "Fitzroy",
    "current_price": "700000",
    "distress_signal": True,
    "address": {
        "street_number": "2",
        "street_name": "Signal St",
        "suburb": "Fitzroy",
        "state": "VIC",
        "postcode": "3065",
        "full_address": "2 Signal St, Fitzroy VIC 3065",
    },
}

_EVENTS_EMPTY: List[Dict[str, Any]] = []

_EVENTS_WITH_SIGNALS: List[Dict[str, Any]] = [
    {
        "id": "evt-001",
        "event_type": "auction_voided",
        "listing_id": "prop-002",
        "timestamp": "2026-03-15T10:00:00+00:00",
        "metadata": {},
    },
    {
        "id": "evt-002",
        "event_type": "price_dropped",
        "listing_id": "prop-002",
        "timestamp": "2026-03-20T10:00:00+00:00",
        "metadata": {"old_price": "800000", "new_price": "700000"},
    },
]


# ---------------------------------------------------------------------------
# Helper: build a mock ListingRepository
# ---------------------------------------------------------------------------


def _make_mock_repo(
    all_listings: Optional[List[Dict[str, Any]]] = None,
    single_listing: Optional[Dict[str, Any]] = None,
    events: Optional[List[Dict[str, Any]]] = None,
) -> MagicMock:
    repo = MagicMock()
    repo.get_all_listings.return_value = all_listings or []
    repo.get_listing_by_id.return_value = single_listing
    repo.get_events_for_listing.return_value = events or []
    return repo


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def test_health_returns_ok() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "api" in data["service"].lower()


# ---------------------------------------------------------------------------
# GET /api/opportunities  (M4-2)
# ---------------------------------------------------------------------------


def test_opportunities_returns_list_sorted_by_score() -> None:
    """Two listings — the one with distress_signal should score higher."""
    mock_repo = _make_mock_repo(
        all_listings=[_LISTING_ROW, _LISTING_ROW_DISTRESS],
        events=_EVENTS_WITH_SIGNALS,
    )
    # events differ by listing, so side_effect maps listing_id → events
    mock_repo.get_events_for_listing.side_effect = lambda lid: _EVENTS_WITH_SIGNALS if lid == "prop-002" else []

    with patch("api.main._get_repo", return_value=mock_repo):
        response = client.get("/api/opportunities")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    # Distress listing (prop-002) should rank first
    assert data[0]["listing_id"] == "prop-002"
    assert data[0]["total_score"] >= data[1]["total_score"]


def test_opportunities_min_score_filter() -> None:
    """Listings below min_score should be excluded."""
    mock_repo = _make_mock_repo(all_listings=[_LISTING_ROW])
    with patch("api.main._get_repo", return_value=mock_repo):
        response = client.get("/api/opportunities?min_score=50")

    assert response.status_code == 200
    data = response.json()
    # prop-001 without distress or undervalue should score < 50
    assert all(item["total_score"] >= 50 for item in data)


def test_opportunities_respects_limit() -> None:
    """Limit parameter caps result count."""
    many_listings = [
        {**_LISTING_ROW, "listing_id": f"prop-{i:03d}", "distress_signal": False} for i in range(30)
    ]
    mock_repo = _make_mock_repo(all_listings=many_listings)
    with patch("api.main._get_repo", return_value=mock_repo):
        response = client.get("/api/opportunities?limit=5")

    assert response.status_code == 200
    assert len(response.json()) <= 5


def test_opportunities_response_fields() -> None:
    """Every item has all required response fields."""
    mock_repo = _make_mock_repo(all_listings=[_LISTING_ROW])
    with patch("api.main._get_repo", return_value=mock_repo):
        response = client.get("/api/opportunities")

    assert response.status_code == 200
    item = response.json()[0]
    required_fields = {
        "listing_id", "address", "suburb", "bedrooms", "property_type",
        "listed_price", "estimated_price", "undervalue_score", "classification",
        "total_score", "score_breakdown", "active_signals",
    }
    assert required_fields.issubset(item.keys())


def test_opportunities_empty_db_returns_empty_list() -> None:
    mock_repo = _make_mock_repo(all_listings=[])
    with patch("api.main._get_repo", return_value=mock_repo):
        response = client.get("/api/opportunities")

    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# GET /api/listings/{listing_id}  (M4-3)
# ---------------------------------------------------------------------------


def test_listing_detail_returns_full_data() -> None:
    mock_repo = _make_mock_repo(single_listing=_LISTING_ROW, events=_EVENTS_EMPTY)
    with patch("api.main._get_repo", return_value=mock_repo):
        response = client.get("/api/listings/prop-001")

    assert response.status_code == 200
    data = response.json()
    assert data["listing_id"] == "prop-001"
    assert data["suburb"] == "Richmond"
    assert data["property_type"] == "house"
    assert data["bedrooms"] == 3
    assert isinstance(data["events"], list)


def test_listing_detail_events_are_chronological() -> None:
    """Events should be returned in timestamp-ascending order (as returned by DB)."""
    mock_repo = _make_mock_repo(single_listing=_LISTING_ROW_DISTRESS, events=_EVENTS_WITH_SIGNALS)
    with patch("api.main._get_repo", return_value=mock_repo):
        response = client.get("/api/listings/prop-002")

    assert response.status_code == 200
    events = response.json()["events"]
    assert len(events) == 2
    # First event should be auction_voided (earlier timestamp)
    assert events[0]["event_type"] == "auction_voided"
    assert events[1]["event_type"] == "price_dropped"


def test_listing_detail_404_when_not_found() -> None:
    mock_repo = _make_mock_repo(single_listing=None)
    with patch("api.main._get_repo", return_value=mock_repo):
        response = client.get("/api/listings/does-not-exist")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_listing_detail_distress_flag_present() -> None:
    mock_repo = _make_mock_repo(single_listing=_LISTING_ROW_DISTRESS, events=_EVENTS_WITH_SIGNALS)
    with patch("api.main._get_repo", return_value=mock_repo):
        response = client.get("/api/listings/prop-002")

    assert response.status_code == 200
    assert response.json()["distress_signal"] is True


# ---------------------------------------------------------------------------
# GET /api/listings  (M4-4)
# ---------------------------------------------------------------------------


def test_list_listings_returns_all_by_default() -> None:
    mock_repo = _make_mock_repo(all_listings=[_LISTING_ROW, _LISTING_ROW_DISTRESS])
    with patch("api.main._get_repo", return_value=mock_repo):
        response = client.get("/api/listings")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_listings_suburb_filter_passed_to_repo() -> None:
    mock_repo = _make_mock_repo(all_listings=[_LISTING_ROW])
    with patch("api.main._get_repo", return_value=mock_repo):
        response = client.get("/api/listings?suburb=Richmond")

    assert response.status_code == 200
    mock_repo.get_all_listings.assert_called_once()
    call_kwargs = mock_repo.get_all_listings.call_args.kwargs
    assert call_kwargs.get("suburb") == "Richmond"


def test_list_listings_property_type_filter() -> None:
    mock_repo = _make_mock_repo(all_listings=[_LISTING_ROW])
    with patch("api.main._get_repo", return_value=mock_repo):
        response = client.get("/api/listings?property_type=house")

    assert response.status_code == 200
    call_kwargs = mock_repo.get_all_listings.call_args.kwargs
    assert call_kwargs.get("property_type") == "house"


def test_list_listings_price_range_filter() -> None:
    mock_repo = _make_mock_repo(all_listings=[_LISTING_ROW])
    with patch("api.main._get_repo", return_value=mock_repo):
        response = client.get("/api/listings?min_price=500000&max_price=1000000")

    assert response.status_code == 200
    call_kwargs = mock_repo.get_all_listings.call_args.kwargs
    assert call_kwargs.get("min_price") == 500000.0
    assert call_kwargs.get("max_price") == 1000000.0


def test_list_listings_distress_filter() -> None:
    mock_repo = _make_mock_repo(all_listings=[_LISTING_ROW_DISTRESS])
    with patch("api.main._get_repo", return_value=mock_repo):
        response = client.get("/api/listings?has_distress_signal=true")

    assert response.status_code == 200
    call_kwargs = mock_repo.get_all_listings.call_args.kwargs
    assert call_kwargs.get("has_distress_signal") is True


def test_list_listings_pagination_params_passed() -> None:
    mock_repo = _make_mock_repo(all_listings=[])
    with patch("api.main._get_repo", return_value=mock_repo):
        response = client.get("/api/listings?limit=10&offset=20")

    assert response.status_code == 200
    call_kwargs = mock_repo.get_all_listings.call_args.kwargs
    assert call_kwargs.get("limit") == 10
    assert call_kwargs.get("offset") == 20


def test_list_listings_response_fields() -> None:
    mock_repo = _make_mock_repo(all_listings=[_LISTING_ROW])
    with patch("api.main._get_repo", return_value=mock_repo):
        response = client.get("/api/listings")

    assert response.status_code == 200
    item = response.json()[0]
    required = {"listing_id", "suburb", "property_type", "bedrooms", "status",
                "current_price", "distress_signal"}
    assert required.issubset(item.keys())


def test_list_listings_empty_returns_empty_list() -> None:
    mock_repo = _make_mock_repo(all_listings=[])
    with patch("api.main._get_repo", return_value=mock_repo):
        response = client.get("/api/listings")

    assert response.status_code == 200
    assert response.json() == []
