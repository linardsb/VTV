# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Tests for auth routes."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.exceptions import AccountLockedError, InvalidCredentialsError
from app.auth.schemas import LoginResponse
from app.core.rate_limit import limiter
from app.main import app

limiter.enabled = False


@pytest.fixture
def client():
    return TestClient(app)


class TestLoginEndpoint:
    def test_successful_login(self, client):
        mock_response = LoginResponse(id=1, email="admin@vtv.lv", name="VTV Admin", role="admin")
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


class TestSeedEndpoint:
    def test_seed_creates_users(self, client):
        with patch(
            "app.auth.routes.AuthService.seed_demo_users",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = client.post("/api/v1/auth/seed")
        assert response.status_code == 200
