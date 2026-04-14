# pyright: reportUnknownParameterType=false, reportMissingParameterType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
"""Unit tests for share link endpoints (LV-3.4)."""

import datetime
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.main import app
from app.transit.models import ShareLink
from app.transit.schemas import VehiclePosition

limiter.enabled = False


def _mock_admin_user() -> User:
    user = MagicMock(spec=User)
    user.id = 1
    user.email = "admin@vtv.lv"
    user.name = "Admin"
    user.role = "admin"
    user.is_active = True
    return user


def _mock_dispatcher_user() -> User:
    user = MagicMock(spec=User)
    user.id = 2
    user.email = "dispatcher@vtv.lv"
    user.name = "Dispatcher"
    user.role = "dispatcher"
    user.is_active = True
    return user


def _mock_viewer_user() -> User:
    user = MagicMock(spec=User)
    user.id = 3
    user.email = "viewer@vtv.lv"
    user.name = "Viewer"
    user.role = "viewer"
    user.is_active = True
    return user


def _make_share_link_obj(
    *,
    link_id: int = 1,
    token_hash: str = "a" * 64,
    vehicle_id: str = "4521",
    route_id: str | None = "22",
    feed_id: str = "riga",
    created_by: int = 1,
    expires_at: datetime.datetime | None = None,
    view_count: int = 0,
    is_active: bool = True,
) -> MagicMock:
    """Create a mock ShareLink ORM object."""
    obj = MagicMock(spec=ShareLink)
    obj.id = link_id
    obj.token_hash = token_hash
    obj.vehicle_id = vehicle_id
    obj.route_id = route_id
    obj.feed_id = feed_id
    obj.created_by = created_by
    obj.expires_at = expires_at or (
        datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1)
    )
    obj.view_count = view_count
    obj.is_active = is_active
    obj.created_at = datetime.datetime(2026, 4, 13, tzinfo=datetime.UTC)
    obj.updated_at = datetime.datetime(2026, 4, 13, tzinfo=datetime.UTC)
    return obj


def _make_vehicle_position(vehicle_id: str = "4521") -> VehiclePosition:
    return VehiclePosition(
        vehicle_id=vehicle_id,
        route_id="22",
        route_short_name="22",
        route_type=3,
        latitude=56.9496,
        longitude=24.1052,
        bearing=180.0,
        speed_kmh=30.0,
        delay_seconds=0,
        current_status="IN_TRANSIT_TO",
        timestamp="2026-04-13T12:00:00Z",
        feed_id="riga",
    )


class _FakeDBSession:
    """Minimal async DB session stub for share link route tests."""

    def __init__(
        self,
        *,
        existing_link: MagicMock | None = None,
    ) -> None:
        self._existing = existing_link
        self._added: list[object] = []

    async def execute(self, stmt: object) -> MagicMock:  # noqa: ARG002
        result = MagicMock()
        result.scalar_one_or_none.return_value = self._existing
        return result

    def add(self, obj: object) -> None:
        self._added.append(obj)

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    async def refresh(self, obj: object) -> None:
        from typing import Any

        o: Any = obj
        if hasattr(o, "id") and not isinstance(o.id, int):
            o.id = 1
        now = datetime.datetime(2026, 4, 13, tzinfo=datetime.UTC)
        if not getattr(o, "created_at", None):
            o.created_at = now
        if not getattr(o, "updated_at", None):
            o.updated_at = now


@pytest.fixture(autouse=True)
def _setup_auth() -> Generator[None, None, None]:
    app.dependency_overrides[get_current_user] = _mock_admin_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


# ── CREATE ──────────────────────────────────────────────────────────


@patch("app.transit.routes.generate_qr_code_base64", return_value="AAAA")
@patch(
    "app.transit.routes.create_share_token",
    return_value=("fake.jwt.token", "a" * 64),
)
def test_create_share_link_admin(
    _mock_create: MagicMock,
    _mock_qr: MagicMock,
    client: TestClient,
) -> None:
    """Admin can create a share link."""
    db = _FakeDBSession()
    app.dependency_overrides[get_db] = lambda: db

    resp = client.post(
        "/api/v1/transit/share",
        json={"vehicle_id": "4521", "route_id": "22", "feed_id": "riga", "expiry_hours": 1},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["vehicle_id"] == "4521"
    assert data["token"] == "fake.jwt.token"
    assert data["share_url"] == "/share/fake.jwt.token"
    assert data["qr_code_base64"] == "AAAA"


@patch("app.transit.routes.generate_qr_code_base64", return_value="AAAA")
@patch(
    "app.transit.routes.create_share_token",
    return_value=("fake.jwt.token", "a" * 64),
)
def test_create_share_link_dispatcher(
    _mock_create: MagicMock,
    _mock_qr: MagicMock,
    client: TestClient,
) -> None:
    """Dispatcher can create a share link."""
    app.dependency_overrides[get_current_user] = _mock_dispatcher_user
    db = _FakeDBSession()
    app.dependency_overrides[get_db] = lambda: db

    resp = client.post(
        "/api/v1/transit/share",
        json={"vehicle_id": "4521"},
    )
    assert resp.status_code == 201


def test_create_share_link_viewer_forbidden(client: TestClient) -> None:
    """Viewer role cannot create share links."""
    app.dependency_overrides[get_current_user] = _mock_viewer_user

    resp = client.post(
        "/api/v1/transit/share",
        json={"vehicle_id": "4521"},
    )
    assert resp.status_code == 403


def test_create_share_link_unauthenticated(client: TestClient) -> None:
    """No auth token returns 401."""
    app.dependency_overrides.pop(get_current_user, None)

    resp = client.post(
        "/api/v1/transit/share",
        json={"vehicle_id": "4521"},
    )
    assert resp.status_code in (401, 403)


# ── RESOLVE ─────────────────────────────────────────────────────────


@patch("app.transit.routes.get_transit_service")
@patch("app.transit.routes.hash_token", return_value="a" * 64)
@patch("app.transit.routes.decode_share_token")
def test_resolve_share_link_success(
    mock_decode: MagicMock,
    _mock_hash: MagicMock,
    mock_service: MagicMock,
    client: TestClient,
) -> None:
    """Valid token resolves to vehicle position data."""
    from app.transit.locshare import ShareTokenPayload

    mock_decode.return_value = ShareTokenPayload(
        sub="4521",
        route_id="22",
        feed_id="riga",
        exp=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
        type="share",
        jti="abc123",
    )

    link = _make_share_link_obj()
    db = _FakeDBSession(existing_link=link)
    app.dependency_overrides[get_db] = lambda: db

    svc = AsyncMock()
    positions_resp = MagicMock()
    positions_resp.vehicles = [_make_vehicle_position()]
    svc.get_vehicle_positions.return_value = positions_resp
    mock_service.return_value = svc

    resp = client.get("/api/v1/transit/share/some-token")
    assert resp.status_code == 200
    data = resp.json()
    assert data["vehicle_id"] == "4521"
    assert data["position"] is not None
    assert data["position"]["latitude"] == 56.9496


@patch("app.transit.routes.decode_share_token", return_value=None)
def test_resolve_share_link_invalid_token(
    _mock_decode: MagicMock,
    client: TestClient,
) -> None:
    """Garbage token returns 404."""
    resp = client.get("/api/v1/transit/share/garbage-token")
    assert resp.status_code == 404


@patch("app.transit.routes.get_transit_service")
@patch("app.transit.routes.hash_token", return_value="a" * 64)
@patch("app.transit.routes.decode_share_token")
def test_resolve_share_link_expired_in_db(
    mock_decode: MagicMock,
    _mock_hash: MagicMock,
    _mock_service: MagicMock,
    client: TestClient,
) -> None:
    """Valid JWT but DB says expired returns 410."""
    from app.transit.locshare import ShareTokenPayload

    mock_decode.return_value = ShareTokenPayload(
        sub="4521",
        route_id="22",
        feed_id="riga",
        exp=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
        type="share",
        jti="abc123",
    )

    link = _make_share_link_obj(
        expires_at=datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC),
    )
    db = _FakeDBSession(existing_link=link)
    app.dependency_overrides[get_db] = lambda: db

    resp = client.get("/api/v1/transit/share/some-token")
    assert resp.status_code == 410


@patch("app.transit.routes.hash_token", return_value="a" * 64)
@patch("app.transit.routes.decode_share_token")
def test_resolve_share_link_deactivated(
    mock_decode: MagicMock,
    _mock_hash: MagicMock,
    client: TestClient,
) -> None:
    """Deactivated link returns 404."""
    from app.transit.locshare import ShareTokenPayload

    mock_decode.return_value = ShareTokenPayload(
        sub="4521",
        route_id="22",
        feed_id="riga",
        exp=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
        type="share",
        jti="abc123",
    )

    # _FakeDBSession returns None when no existing link (is_active filter fails)
    db = _FakeDBSession(existing_link=None)
    app.dependency_overrides[get_db] = lambda: db

    resp = client.get("/api/v1/transit/share/some-token")
    assert resp.status_code == 404


@patch("app.transit.routes.get_transit_service")
@patch("app.transit.routes.hash_token", return_value="a" * 64)
@patch("app.transit.routes.decode_share_token")
def test_resolve_share_link_vehicle_not_found(
    mock_decode: MagicMock,
    _mock_hash: MagicMock,
    mock_service: MagicMock,
    client: TestClient,
) -> None:
    """Valid link but no vehicle position returns position: null."""
    from app.transit.locshare import ShareTokenPayload

    mock_decode.return_value = ShareTokenPayload(
        sub="9999",
        route_id="22",
        feed_id="riga",
        exp=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
        type="share",
        jti="abc123",
    )

    link = _make_share_link_obj(vehicle_id="9999")
    db = _FakeDBSession(existing_link=link)
    app.dependency_overrides[get_db] = lambda: db

    svc = AsyncMock()
    positions_resp = MagicMock()
    positions_resp.vehicles = [_make_vehicle_position("4521")]
    svc.get_vehicle_positions.return_value = positions_resp
    mock_service.return_value = svc

    resp = client.get("/api/v1/transit/share/some-token")
    assert resp.status_code == 200
    data = resp.json()
    assert data["position"] is None


@patch("app.transit.routes.get_transit_service")
@patch("app.transit.routes.hash_token", return_value="a" * 64)
@patch("app.transit.routes.decode_share_token")
def test_resolve_share_link_increments_view_count(
    mock_decode: MagicMock,
    _mock_hash: MagicMock,
    mock_service: MagicMock,
    client: TestClient,
) -> None:
    """Resolving a share link increments the view count."""
    from app.transit.locshare import ShareTokenPayload

    mock_decode.return_value = ShareTokenPayload(
        sub="4521",
        route_id="22",
        feed_id="riga",
        exp=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
        type="share",
        jti="abc123",
    )

    link = _make_share_link_obj(view_count=5)
    db = _FakeDBSession(existing_link=link)
    app.dependency_overrides[get_db] = lambda: db

    svc = AsyncMock()
    positions_resp = MagicMock()
    positions_resp.vehicles = [_make_vehicle_position()]
    svc.get_vehicle_positions.return_value = positions_resp
    mock_service.return_value = svc

    resp = client.get("/api/v1/transit/share/some-token")
    assert resp.status_code == 200
    assert link.view_count == 6
