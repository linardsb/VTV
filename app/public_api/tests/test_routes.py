# pyright: reportCallIssue=false
"""Unit tests for public API route handlers."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.main import app
from app.public_api.auth import get_api_key
from app.public_api.tests.conftest import make_api_key

limiter.enabled = False


def _make_auth_header() -> dict[str, str]:
    """Create a mock JWT Authorization header value (unused — we override deps)."""
    return {"Authorization": "Bearer mock-token"}


@pytest.fixture(autouse=True)
def _override_deps() -> Generator[None, None, None]:
    """Override auth + DB dependencies for route tests."""
    mock_user = MagicMock()
    mock_user.id = 10
    mock_user.role = "admin"
    mock_user.email = "admin@test.com"

    mock_db = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db
    yield
    app.dependency_overrides.clear()


class TestKeyManagement:
    """Tests for key management endpoints (/api/v1/public-api/keys)."""

    def test_create_key_success(self, client: TestClient) -> None:
        """POST /api/v1/public-api/keys returns 201 with raw key."""
        key = make_api_key()
        with patch(
            "app.public_api.routes.PublicAPIService.generate_key",
            new_callable=AsyncMock,
            return_value=("vtv_pk_" + "a" * 32, key),
        ):
            resp = client.post(
                "/api/v1/public-api/keys/",
                json={"name": "Test Key"},
                headers=_make_auth_header(),
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["key"].startswith("vtv_pk_")
        assert data["name"] == "Test Key"

    def test_create_key_requires_editor_role(self, client: TestClient) -> None:
        """Viewer role gets 403 on key creation."""
        mock_viewer = MagicMock()
        mock_viewer.id = 20
        mock_viewer.role = "viewer"
        app.dependency_overrides[get_current_user] = lambda: mock_viewer

        resp = client.post(
            "/api/v1/public-api/keys/",
            json={"name": "Test"},
            headers=_make_auth_header(),
        )
        assert resp.status_code == 403

    def test_list_keys_success(self, client: TestClient) -> None:
        """GET /api/v1/public-api/keys returns paginated list."""
        keys = [make_api_key(id=i) for i in range(3)]
        with patch(
            "app.public_api.routes.PublicAPIService.list_keys",
            new_callable=AsyncMock,
            return_value=(keys, 3),
        ):
            resp = client.get(
                "/api/v1/public-api/keys/",
                headers=_make_auth_header(),
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_revoke_key_success(self, client: TestClient) -> None:
        """DELETE /api/v1/public-api/keys/{id} returns revoked key."""
        revoked = make_api_key(is_active=False)
        with patch(
            "app.public_api.routes.PublicAPIService.revoke_key",
            new_callable=AsyncMock,
            return_value=revoked,
        ):
            resp = client.delete(
                "/api/v1/public-api/keys/1",
                headers=_make_auth_header(),
            )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False


class TestPublicEndpoints:
    """Tests for public data endpoints (/public/v1)."""

    @pytest.fixture(autouse=True)
    def _override_api_key(self) -> Generator[None, None, None]:
        """Override API key dependency for public endpoint tests."""
        key = make_api_key()
        app.dependency_overrides[get_api_key] = lambda: key
        yield
        # Don't clear — outer fixture handles cleanup

    def test_get_vehicles_with_api_key(self, client: TestClient) -> None:
        """GET /public/v1/vehicles with valid key returns 200."""
        mock_positions = MagicMock()
        mock_positions.vehicles = []
        with (
            patch(
                "app.public_api.routes.PublicAPIService.check_rate_limit",
                new_callable=AsyncMock,
                return_value=(60, 59),
            ),
            patch(
                "app.public_api.routes.get_transit_service",
            ) as mock_ts,
        ):
            mock_ts.return_value.get_vehicle_positions = AsyncMock(return_value=mock_positions)
            resp = client.get("/public/v1/vehicles", headers={"X-API-Key": "vtv_pk_test"})
        assert resp.status_code == 200

    def test_get_vehicles_without_key(self, client: TestClient) -> None:
        """GET /public/v1/vehicles without API key returns 401."""
        # Remove the API key override
        app.dependency_overrides.pop(get_api_key, None)
        resp = client.get("/public/v1/vehicles")
        assert resp.status_code == 401

    def test_get_routes_with_api_key(self, client: TestClient) -> None:
        """GET /public/v1/routes with valid key returns 200."""
        with (
            patch(
                "app.public_api.routes.PublicAPIService.check_rate_limit",
                new_callable=AsyncMock,
                return_value=(60, 59),
            ),
            patch(
                "app.public_api.routes.ScheduleRepository.list_routes",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.public_api.routes.ScheduleRepository.count_routes",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "app.public_api.routes.PublicAPIService.record_usage_async",
            ),
        ):
            resp = client.get("/public/v1/routes", headers={"X-API-Key": "vtv_pk_test"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_get_stops_with_api_key(self, client: TestClient) -> None:
        """GET /public/v1/stops with valid key returns 200."""
        with (
            patch(
                "app.public_api.routes.PublicAPIService.check_rate_limit",
                new_callable=AsyncMock,
                return_value=(60, 59),
            ),
            patch(
                "app.public_api.routes.StopRepository.list",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.public_api.routes.StopRepository.count",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "app.public_api.routes.PublicAPIService.record_usage_async",
            ),
        ):
            resp = client.get("/public/v1/stops", headers={"X-API-Key": "vtv_pk_test"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_public_endpoint_cache_control_header(self, client: TestClient) -> None:
        """Public endpoints return Cache-Control header."""
        mock_positions = MagicMock()
        mock_positions.vehicles = []
        with (
            patch(
                "app.public_api.routes.PublicAPIService.check_rate_limit",
                new_callable=AsyncMock,
                return_value=(60, 59),
            ),
            patch(
                "app.public_api.routes.get_transit_service",
            ) as mock_ts,
        ):
            mock_ts.return_value.get_vehicle_positions = AsyncMock(return_value=mock_positions)
            resp = client.get("/public/v1/vehicles", headers={"X-API-Key": "vtv_pk_test"})
        assert "Cache-Control" in resp.headers
        assert "max-age=" in resp.headers["Cache-Control"]

    def test_public_endpoint_rate_limit_headers(self, client: TestClient) -> None:
        """Public endpoints return X-RateLimit-* headers."""
        mock_positions = MagicMock()
        mock_positions.vehicles = []
        with (
            patch(
                "app.public_api.routes.PublicAPIService.check_rate_limit",
                new_callable=AsyncMock,
                return_value=(60, 59),
            ),
            patch(
                "app.public_api.routes.get_transit_service",
            ) as mock_ts,
        ):
            mock_ts.return_value.get_vehicle_positions = AsyncMock(return_value=mock_positions)
            resp = client.get("/public/v1/vehicles", headers={"X-API-Key": "vtv_pk_test"})
        assert resp.headers.get("X-RateLimit-Limit") == "60"
        assert resp.headers.get("X-RateLimit-Remaining") == "59"

    def test_public_endpoint_cors_header(self, client: TestClient) -> None:
        """Public endpoints return Access-Control-Allow-Origin: *."""
        mock_positions = MagicMock()
        mock_positions.vehicles = []
        with (
            patch(
                "app.public_api.routes.PublicAPIService.check_rate_limit",
                new_callable=AsyncMock,
                return_value=(60, 59),
            ),
            patch(
                "app.public_api.routes.get_transit_service",
            ) as mock_ts,
        ):
            mock_ts.return_value.get_vehicle_positions = AsyncMock(return_value=mock_positions)
            resp = client.get("/public/v1/vehicles", headers={"X-API-Key": "vtv_pk_test"})
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"
