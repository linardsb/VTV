# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Tests for auth routes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import clear_user_cache
from app.auth.exceptions import AccountLockedError, InvalidCredentialsError
from app.auth.models import User
from app.auth.schemas import LoginResponse
from app.auth.token import create_access_token, create_refresh_token
from app.core.rate_limit import limiter
from app.main import app

limiter.enabled = False


@pytest.fixture
def client():
    """Test client that clears dependency overrides for auth-specific tests.

    Other test modules set app.dependency_overrides at module level (to bypass auth).
    Since `app` is a shared global, those overrides leak into this module.
    We clear them here so auth enforcement tests work correctly.

    Mocks is_token_revoked to return False (Redis unavailable in unit tests,
    and fail-closed behavior would reject all tokens).
    """
    saved_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    clear_user_cache()
    with patch(
        "app.auth.dependencies.is_token_revoked", new_callable=AsyncMock, return_value=False
    ):
        yield TestClient(app)
    clear_user_cache()
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved_overrides)


def _make_auth_header(user_id: int = 1, role: str = "admin") -> dict[str, str]:
    """Create an Authorization header with a valid JWT token."""
    token = create_access_token(user_id=user_id, role=role)
    return {"Authorization": f"Bearer {token}"}


class TestLoginEndpoint:
    def test_successful_login(self, client):
        mock_response = LoginResponse(
            id=1,
            email="admin@vtv.lv",
            name="VTV Admin",
            role="admin",
            access_token="test-access-token",
            refresh_token="test-refresh-token",
        )
        with patch(
            "app.auth.routes.AuthService.authenticate",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "admin@vtv.lv", "password": "admin"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@vtv.lv"
        assert data["role"] == "admin"
        assert "access_token" in data
        assert "refresh_token" in data

    def test_invalid_credentials(self, client):
        with patch(
            "app.auth.routes.AuthService.authenticate",
            new_callable=AsyncMock,
            side_effect=InvalidCredentialsError("Invalid"),
        ):
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "bad@vtv.lv", "password": "wrong"},
            )
        assert response.status_code == 401

    def test_locked_account(self, client):
        with patch(
            "app.auth.routes.AuthService.authenticate",
            new_callable=AsyncMock,
            side_effect=AccountLockedError("Locked"),
        ):
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "locked@vtv.lv", "password": "pass"},
            )
        assert response.status_code == 423


class TestRefreshEndpoint:
    def test_valid_refresh_token(self, client):
        refresh_token = create_refresh_token(user_id=1)
        with patch(
            "app.auth.routes.AuthService.refresh_access_token",
            new_callable=AsyncMock,
            return_value="new-access-token",
        ):
            response = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": refresh_token},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "new-access-token"

    def test_invalid_refresh_token(self, client):
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert response.status_code == 401

    def test_access_token_as_refresh_rejected(self, client):
        access_token = create_access_token(user_id=1, role="admin")
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )
        assert response.status_code == 401


class TestSeedEndpoint:
    def test_seed_requires_auth(self, client):
        """Seed endpoint should return 401 without auth token."""
        response = client.post("/api/v1/auth/seed")
        assert response.status_code == 401

    def test_seed_requires_admin_role(self, client):
        """Non-admin users should get 403."""
        headers = _make_auth_header(user_id=1, role="viewer")
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.role = "viewer"
        mock_user.is_active = True

        # Pre-populate auth cache to avoid db.expunge on mock objects
        from app.auth.dependencies import _user_cache

        _user_cache[1] = mock_user
        try:
            response = client.post("/api/v1/auth/seed", headers=headers)
            assert response.status_code == 403
        finally:
            _user_cache.pop(1, None)

    def test_seed_works_for_admin(self, client):
        """Admin users should be able to seed."""
        headers = _make_auth_header(user_id=1, role="admin")
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.role = "admin"
        mock_user.is_active = True

        # Pre-populate auth cache to avoid db.expunge on mock objects
        from app.auth.dependencies import _user_cache

        _user_cache[1] = mock_user
        try:
            with patch(
                "app.auth.routes.AuthService.seed_demo_users",
                new_callable=AsyncMock,
                return_value=[],
            ):
                response = client.post("/api/v1/auth/seed", headers=headers)
            assert response.status_code == 200
        finally:
            _user_cache.pop(1, None)


class TestProtectedEndpoints:
    def test_stops_requires_auth(self, client):
        """Stops endpoint should return 401 without auth token."""
        response = client.get("/api/v1/stops/")
        assert response.status_code == 401

    def test_transit_requires_auth(self, client):
        """Transit endpoint should return 401 without auth token."""
        response = client.get("/api/v1/transit/vehicles")
        assert response.status_code == 401

    def test_health_is_public(self, client):
        """Health endpoint should remain public."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_root_is_public(self, client):
        """Root endpoint should remain public."""
        response = client.get("/")
        assert response.status_code == 200

    def test_login_is_public(self, client):
        """Login endpoint should be accessible without auth.

        Uses a weak password to also verify that LoginRequest does NOT
        enforce password complexity — that belongs on PasswordResetRequest only.
        """
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "test@test.com", "password": "test"},
        )
        # Should get 401 from invalid credentials, NOT 422 from schema validation
        assert response.status_code == 401
