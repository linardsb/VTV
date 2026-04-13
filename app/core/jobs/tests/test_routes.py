"""Tests for the admin job status endpoint."""

# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.core.jobs.routes import router
from app.core.rate_limit import limiter


@pytest.fixture
def admin_user() -> MagicMock:
    user = MagicMock()
    user.id = 1
    user.role = "admin"
    user.email = "admin@test.com"
    return user


@pytest.fixture
def dispatcher_user() -> MagicMock:
    user = MagicMock()
    user.id = 2
    user.role = "dispatcher"
    user.email = "dispatcher@test.com"
    return user


@pytest.fixture
def app_with_admin(admin_user: MagicMock) -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.state.limiter = limiter
    limiter.enabled = False
    test_app.dependency_overrides[get_current_user] = lambda: admin_user
    return test_app


@pytest.fixture
def client_admin(app_with_admin: FastAPI) -> TestClient:
    return TestClient(app_with_admin)


@pytest.fixture
def app_with_dispatcher(dispatcher_user: MagicMock) -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.state.limiter = limiter
    limiter.enabled = False
    test_app.dependency_overrides[get_current_user] = lambda: dispatcher_user
    return test_app


@pytest.fixture
def client_dispatcher(app_with_dispatcher: FastAPI) -> TestClient:
    return TestClient(app_with_dispatcher)


def test_admin_status_returns_queue_disabled(client_admin: TestClient) -> None:
    with patch("app.core.jobs.routes.get_settings") as mock_gs:
        mock_gs.return_value.background_queue_enabled = False
        resp = client_admin.get("/admin/jobs/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["queue_enabled"] is False
    assert data["jobs"] == []


def test_admin_status_returns_job_info_when_enabled(client_admin: TestClient) -> None:
    mock_pool = MagicMock()
    mock_pool.all_job_results = AsyncMock(return_value=[])

    with (
        patch("app.core.jobs.routes.get_settings") as mock_gs,
        patch("app.core.jobs.queue.get_arq_pool", new_callable=AsyncMock, return_value=mock_pool),
    ):
        mock_gs.return_value.background_queue_enabled = True
        resp = client_admin.get("/admin/jobs/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["queue_enabled"] is True
    assert len(data["jobs"]) == 3
    assert data["jobs"][0]["name"] == "run_compaction"
    assert data["jobs"][1]["name"] == "run_promotion"
    assert data["jobs"][2]["name"] == "run_daily_adherence"


def test_admin_status_requires_admin_role(client_dispatcher: TestClient) -> None:
    resp = client_dispatcher.get("/admin/jobs/status")
    assert resp.status_code == 403
