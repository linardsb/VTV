# pyright: reportUnknownParameterType=false, reportMissingParameterType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
"""Unit tests for journey planner service and endpoint (LV-3.3)."""

import datetime
import json
from collections.abc import Generator
from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.agents.exceptions import TransitDataError
from app.core.rate_limit import limiter
from app.main import app
from app.transit.journey_planner import (
    JourneyPlannerService,
    _cache_key,
    _map_itinerary,
)
from app.transit.otp_client import OTPClient
from app.transit.schemas import JourneyPlanResponse

limiter.enabled = False


def _mock_admin_user() -> User:
    """Return a mock admin user for testing."""
    user = MagicMock(spec=User)
    user.id = 1
    user.email = "admin@vtv.lv"
    user.name = "Admin"
    user.role = "admin"
    user.is_active = True
    return user


@pytest.fixture(autouse=True)
def _setup_auth_override() -> Generator[None, None, None]:
    """Ensure auth override is set before each test and restored after."""
    app.dependency_overrides[get_current_user] = _mock_admin_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _make_settings() -> MagicMock:
    """Create a mock Settings with OTP + transit feed config."""
    s = MagicMock()
    s.otp_enabled = True
    s.otp_base_url = "http://otp:8080"
    s.otp_router_id = "default"
    s.otp_timeout_seconds = 10.0
    s.otp_cache_ttl_seconds = 300
    s.otp_max_itineraries = 5
    s.otp_max_walk_distance_m = 2000
    feed = MagicMock()
    feed.feed_id = "riga"
    feed.enabled = True
    s.transit_feeds = [feed]
    return s


def _make_otp_plan_response() -> dict[str, object]:
    """OTP /plan response with 2 itineraries."""
    now_ms = int(datetime.datetime.now(tz=UTC).timestamp() * 1000)
    return {
        "plan": {
            "from": {"name": "Origin", "lat": 56.95, "lon": 24.10},
            "to": {"name": "Destination", "lat": 56.85, "lon": 24.05},
            "itineraries": [
                {
                    "startTime": now_ms,
                    "endTime": now_ms + 1800000,
                    "duration": 1800,
                    "walkDistance": 500.0,
                    "transitTime": 1200,
                    "waitingTime": 100,
                    "transfers": 1,
                    "legs": [
                        {
                            "mode": "WALK",
                            "from": {"name": "Start", "lat": 56.95, "lon": 24.10},
                            "to": {"name": "Stop A", "lat": 56.94, "lon": 24.11},
                            "startTime": now_ms,
                            "endTime": now_ms + 300000,
                            "duration": 300,
                            "distance": 400.0,
                        },
                        {
                            "mode": "BUS",
                            "from": {"name": "Stop A", "lat": 56.94, "lon": 24.11},
                            "to": {"name": "Stop B", "lat": 56.88, "lon": 24.08},
                            "startTime": now_ms + 300000,
                            "endTime": now_ms + 1500000,
                            "duration": 1200,
                            "distance": 5000.0,
                            "routeId": "22",
                            "routeShortName": "22",
                            "route": "Riga Bus 22",
                            "tripId": "trip_001",
                            "agencyName": "Rigas Satiksme",
                            "numIntermediateStops": 8,
                            "legGeometry": {"points": "encoded_polyline"},
                        },
                    ],
                },
                {
                    "startTime": now_ms + 60000,
                    "endTime": now_ms + 2400000,
                    "duration": 2340,
                    "walkDistance": 800.0,
                    "transitTime": 1500,
                    "waitingTime": 40,
                    "transfers": 0,
                    "legs": [
                        {
                            "mode": "TRAM",
                            "from": {"name": "Start", "lat": 56.95, "lon": 24.10},
                            "to": {"name": "End", "lat": 56.85, "lon": 24.05},
                            "startTime": now_ms + 60000,
                            "endTime": now_ms + 1560000,
                            "duration": 1500,
                            "distance": 6000.0,
                            "routeId": "1",
                            "routeShortName": "1",
                            "route": "Tram 1",
                            "tripId": "trip_002",
                            "agencyName": "Rigas Satiksme",
                            "numIntermediateStops": 12,
                        },
                    ],
                },
            ],
        }
    }


# ── Service tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch("app.transit.journey_planner.get_redis")
async def test_plan_journey_success(mock_get_redis: MagicMock) -> None:
    """plan_journey returns a valid JourneyPlanResponse."""
    # Mock Redis (cache miss, empty feeds)
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.set = AsyncMock()
    mock_redis.smembers.return_value = set()
    mock_get_redis.return_value = mock_redis

    mock_otp = AsyncMock(spec=OTPClient)
    mock_otp.plan.return_value = _make_otp_plan_response()

    service = JourneyPlannerService(otp_client=mock_otp, settings=_make_settings())
    result = await service.plan_journey(56.95, 24.10, 56.85, 24.05)

    assert isinstance(result, JourneyPlanResponse)
    assert len(result.itineraries) == 2
    assert result.itineraries[0].legs[0].mode == "WALK"
    assert result.itineraries[0].legs[1].mode == "BUS"
    assert result.itineraries[0].legs[1].trip_id == "trip_001"
    assert result.itineraries[0].legs[1].route_short_name == "22"
    assert result.itineraries[0].legs[1].polyline == "encoded_polyline"


@pytest.mark.asyncio
@patch("app.transit.journey_planner.get_redis")
async def test_plan_journey_cache_hit(mock_get_redis: MagicMock) -> None:
    """Cached result is returned without calling OTP."""
    cached_plan = JourneyPlanResponse(
        from_name="A",
        from_lat=56.95,
        from_lon=24.10,
        to_name="B",
        to_lat=56.85,
        to_lon=24.05,
        itineraries=[],
        requested_at=datetime.datetime.now(tz=UTC),
    )
    mock_redis = AsyncMock()
    mock_redis.get.return_value = cached_plan.model_dump_json()
    mock_get_redis.return_value = mock_redis

    mock_otp = AsyncMock(spec=OTPClient)
    service = JourneyPlannerService(otp_client=mock_otp, settings=_make_settings())
    result = await service.plan_journey(56.95, 24.10, 56.85, 24.05)

    assert isinstance(result, JourneyPlanResponse)
    mock_otp.plan.assert_not_awaited()


@pytest.mark.asyncio
@patch("app.transit.journey_planner.get_redis")
async def test_delay_enrichment(mock_get_redis: MagicMock) -> None:
    """Transit legs are enriched with real-time delay data from Redis."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None  # Cache miss
    mock_redis.set = AsyncMock()
    # Vehicle data with delay
    vehicle_json = json.dumps({"trip_id": "trip_001", "delay_seconds": 120})
    mock_redis.smembers.return_value = {"v1"}
    mock_redis.mget.return_value = [vehicle_json]
    mock_get_redis.return_value = mock_redis

    mock_otp = AsyncMock(spec=OTPClient)
    mock_otp.plan.return_value = _make_otp_plan_response()

    service = JourneyPlannerService(otp_client=mock_otp, settings=_make_settings())
    result = await service.plan_journey(56.95, 24.10, 56.85, 24.05)

    bus_leg = result.itineraries[0].legs[1]
    assert bus_leg.realtime_delay_seconds == 120
    assert bus_leg.scheduled_start_time is not None
    assert result.otp_enriched is True


@pytest.mark.asyncio
@patch("app.transit.journey_planner.get_redis")
async def test_delay_enrichment_redis_down(mock_get_redis: MagicMock) -> None:
    """Plan is returned without enrichment when Redis fails."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None  # Cache miss
    mock_redis.set = AsyncMock()
    mock_redis.smembers.side_effect = ConnectionError("Redis down")
    mock_get_redis.return_value = mock_redis

    mock_otp = AsyncMock(spec=OTPClient)
    mock_otp.plan.return_value = _make_otp_plan_response()

    service = JourneyPlannerService(otp_client=mock_otp, settings=_make_settings())
    result = await service.plan_journey(56.95, 24.10, 56.85, 24.05)

    assert result.otp_enriched is False
    assert result.itineraries[0].legs[1].realtime_delay_seconds is None


@pytest.mark.asyncio
async def test_coordinates_outside_latvia() -> None:
    """Coordinates outside Latvia bounds raise TransitDataError."""
    mock_otp = AsyncMock(spec=OTPClient)
    service = JourneyPlannerService(otp_client=mock_otp, settings=_make_settings())

    with pytest.raises(TransitDataError, match="outside Latvia"):
        await service.plan_journey(40.0, 24.10, 56.85, 24.05)


def test_cache_key_rounding() -> None:
    """Coordinates differing by <11m produce the same cache key."""
    key1 = _cache_key(56.94960, 24.10520, 56.85, 24.05, None, None, "TRANSIT,WALK")
    key2 = _cache_key(56.94961, 24.10521, 56.85, 24.05, None, None, "TRANSIT,WALK")
    assert key1 == key2


def test_map_itinerary_basic() -> None:
    """_map_itinerary correctly maps OTP response to schema."""
    now_ms = int(datetime.datetime.now(tz=UTC).timestamp() * 1000)
    itin = {
        "startTime": now_ms,
        "endTime": now_ms + 600000,
        "duration": 600,
        "walkDistance": 200.0,
        "transitTime": 400,
        "waitingTime": 0,
        "transfers": 0,
        "legs": [
            {
                "mode": "WALK",
                "from": {"name": "A", "lat": 56.9, "lon": 24.1},
                "to": {"name": "B", "lat": 56.8, "lon": 24.0},
                "startTime": now_ms,
                "endTime": now_ms + 600000,
                "duration": 600,
                "distance": 500.0,
            }
        ],
    }
    result = _map_itinerary(itin, None)
    assert result.duration_seconds == 600
    assert len(result.legs) == 1
    assert result.legs[0].mode == "WALK"


# ── Route tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch("app.transit.routes.get_journey_planner")
async def test_plan_endpoint_200(mock_get_planner: MagicMock) -> None:
    """GET /api/v1/transit/plan returns 200 with valid params."""
    mock_planner = AsyncMock()
    mock_planner.plan_journey.return_value = JourneyPlanResponse(
        from_name="Origin",
        from_lat=56.95,
        from_lon=24.10,
        to_name="Destination",
        to_lat=56.85,
        to_lon=24.05,
        itineraries=[],
        requested_at=datetime.datetime.now(tz=UTC),
    )
    mock_get_planner.return_value = mock_planner

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/transit/plan",
            params={
                "from_lat": 56.95,
                "from_lon": 24.10,
                "to_lat": 56.85,
                "to_lon": 24.05,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "itineraries" in data


@pytest.mark.asyncio
async def test_plan_endpoint_422_both_times() -> None:
    """GET /api/v1/transit/plan rejects both depart_at and arrive_by."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/transit/plan",
            params={
                "from_lat": 56.95,
                "from_lon": 24.10,
                "to_lat": 56.85,
                "to_lon": 24.05,
                "depart_at": "2026-04-13T10:00:00",
                "arrive_by": "2026-04-13T11:00:00",
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_plan_endpoint_422_invalid_coords() -> None:
    """GET /api/v1/transit/plan rejects coordinates outside Latvia."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/transit/plan",
            params={
                "from_lat": 40.0,
                "from_lon": 24.10,
                "to_lat": 56.85,
                "to_lon": 24.05,
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
@patch("app.transit.routes.get_journey_planner")
async def test_plan_endpoint_503_otp_down(mock_get_planner: MagicMock) -> None:
    """GET /api/v1/transit/plan returns 503 when OTP is unavailable."""
    mock_planner = AsyncMock()
    mock_planner.plan_journey.side_effect = TransitDataError("OTP down")
    mock_get_planner.return_value = mock_planner

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/transit/plan",
            params={
                "from_lat": 56.95,
                "from_lon": 24.10,
                "to_lat": 56.85,
                "to_lon": 24.05,
            },
        )

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_plan_endpoint_requires_auth() -> None:
    """GET /api/v1/transit/plan returns 401/403 without auth."""
    app.dependency_overrides.pop(get_current_user, None)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/transit/plan",
                params={
                    "from_lat": 56.95,
                    "from_lon": 24.10,
                    "to_lat": 56.85,
                    "to_lon": 24.05,
                },
            )

        assert response.status_code in (401, 403)
    finally:
        app.dependency_overrides[get_current_user] = _mock_admin_user
