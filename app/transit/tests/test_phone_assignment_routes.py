# pyright: reportUnknownParameterType=false, reportMissingParameterType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
"""Unit tests for phone assignment admin endpoints (LV-3.1)."""

import datetime
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.main import app
from app.transit.models import VehiclePhoneAssignment

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


def _make_assignment_obj(
    assignment_id: int = 1,
    phone_identifier: str = "user1_phone",
    vehicle_id: int = 42,
    route_id: int | None = 101,
    driver_id: int | None = None,
    active: bool = True,
) -> MagicMock:
    """Create a mock VehiclePhoneAssignment ORM object."""
    obj = MagicMock(spec=VehiclePhoneAssignment)
    obj.id = assignment_id
    obj.phone_identifier = phone_identifier
    obj.vehicle_id = vehicle_id
    obj.route_id = route_id
    obj.driver_id = driver_id
    obj.assigned_by = "admin@vtv.lv"
    obj.active = active
    obj.created_at = datetime.datetime(2026, 4, 13, tzinfo=datetime.UTC)
    obj.updated_at = datetime.datetime(2026, 4, 13, tzinfo=datetime.UTC)
    return obj


class _FakeDBSession:
    """Minimal async DB session stub for route tests.

    Mirrors the production duplicate-check semantics: only an *active* existing
    row participates in the ``scalar_one_or_none`` lookup. Deactivated rows are
    excluded — matching ``VehiclePhoneAssignment.active.is_(True)`` filtering
    in ``app/transit/routes.py:301-306``.
    """

    def __init__(self, *, existing_assignment: MagicMock | None = None) -> None:
        self._existing = existing_assignment
        self._added: list[object] = []
        self._refreshed: list[object] = []

    async def execute(self, stmt: object) -> MagicMock:  # noqa: ARG002
        result = MagicMock()
        # Duplicate check filters by active=True — simulate that here so the
        # mock matches real DB behaviour after the partial-unique-index migration
        # (alembic ``y9z0a1b2c3d4``). Inactive rows must NOT block re-creation.
        active_existing = (
            self._existing
            if self._existing is not None and bool(getattr(self._existing, "active", False))
            else None
        )
        result.scalar_one_or_none.return_value = active_existing
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [self._existing] if self._existing else []
        result.scalars.return_value = mock_scalars
        return result

    def add(self, obj: object) -> None:
        self._added.append(obj)

    async def commit(self) -> None:
        pass

    async def refresh(self, obj: object) -> None:
        # Simulate ORM refresh — use Any to allow dynamic attribute setting
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


def test_create_assignment_admin(client: TestClient) -> None:
    """Admin can create a phone assignment."""
    db = _FakeDBSession(existing_assignment=None)
    app.dependency_overrides[get_db] = lambda: db

    resp = client.post(
        "/api/v1/transit/phone-assignments",
        json={"phone_identifier": "user1_phone", "vehicle_id": 42, "route_id": 101},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["phone_identifier"] == "user1_phone"
    assert data["vehicle_id"] == 42


def test_create_assignment_dispatcher(client: TestClient) -> None:
    """Dispatcher can create a phone assignment."""
    app.dependency_overrides[get_current_user] = _mock_dispatcher_user
    db = _FakeDBSession(existing_assignment=None)
    app.dependency_overrides[get_db] = lambda: db

    resp = client.post(
        "/api/v1/transit/phone-assignments",
        json={"phone_identifier": "user2_phone", "vehicle_id": 43},
    )
    assert resp.status_code == 201


def test_create_assignment_viewer_forbidden(client: TestClient) -> None:
    """Viewer role cannot create phone assignments."""
    app.dependency_overrides[get_current_user] = _mock_viewer_user

    resp = client.post(
        "/api/v1/transit/phone-assignments",
        json={"phone_identifier": "user3_phone", "vehicle_id": 44},
    )
    assert resp.status_code == 403


def test_create_duplicate_phone_rejected(client: TestClient) -> None:
    """Duplicate phone_identifier returns 409."""
    existing = _make_assignment_obj()
    db = _FakeDBSession(existing_assignment=existing)
    app.dependency_overrides[get_db] = lambda: db

    resp = client.post(
        "/api/v1/transit/phone-assignments",
        json={"phone_identifier": "user1_phone", "vehicle_id": 42},
    )
    assert resp.status_code == 409


def test_create_after_deactivate_allows_reuse(client: TestClient) -> None:
    # Regression for T-002: the application soft-deletes by toggling ``active=False``,
    # so the duplicate check must NOT count deactivated rows. The DB-level partial
    # unique index (alembic ``y9z0a1b2c3d4``) provides the matching guarantee.
    deactivated = _make_assignment_obj(active=False)
    db = _FakeDBSession(existing_assignment=deactivated)
    app.dependency_overrides[get_db] = lambda: db

    resp = client.post(
        "/api/v1/transit/phone-assignments",
        json={"phone_identifier": "user1_phone", "vehicle_id": 99},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["phone_identifier"] == "user1_phone"
    assert data["vehicle_id"] == 99


# ── LIST ────────────────────────────────────────────────────────────


def test_list_assignments(client: TestClient) -> None:
    """List returns active assignments."""
    existing = _make_assignment_obj()
    db = _FakeDBSession(existing_assignment=existing)
    app.dependency_overrides[get_db] = lambda: db

    resp = client.get("/api/v1/transit/phone-assignments")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["phone_identifier"] == "user1_phone"


# ── DELETE ──────────────────────────────────────────────────────────


def test_delete_assignment_admin(client: TestClient) -> None:
    """Admin can deactivate an assignment."""
    existing = _make_assignment_obj()
    db = _FakeDBSession(existing_assignment=existing)
    app.dependency_overrides[get_db] = lambda: db

    resp = client.delete("/api/v1/transit/phone-assignments/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["active"] is False


def test_delete_assignment_dispatcher_forbidden(client: TestClient) -> None:
    """Dispatcher cannot delete phone assignments (admin only)."""
    app.dependency_overrides[get_current_user] = _mock_dispatcher_user

    resp = client.delete("/api/v1/transit/phone-assignments/1")
    assert resp.status_code == 403
