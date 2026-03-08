"""Tests for compliance export REST API routes.

Uses httpx AsyncClient with ASGI transport for lightweight endpoint tests.
Service layer is mocked to avoid DB/Redis dependencies.
"""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.compliance.schemas import ExportMetadata
from app.core.rate_limit import limiter
from app.main import app

# Disable rate limiting during tests
limiter.enabled = False

SAMPLE_XML = b'<?xml version="1.0" encoding="UTF-8"?>\n<root/>'


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


@pytest.mark.asyncio
@patch("app.compliance.service.ComplianceService.export_netex", new_callable=AsyncMock)
async def test_netex_export_returns_xml(mock_export: AsyncMock) -> None:
    """GET /api/v1/compliance/netex returns XML with correct content type."""
    mock_export.return_value = SAMPLE_XML

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/compliance/netex")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/xml"
    assert "attachment" in response.headers["content-disposition"]


@pytest.mark.asyncio
@patch("app.compliance.service.ComplianceService.get_siri_vm", new_callable=AsyncMock)
async def test_siri_vm_returns_xml(mock_siri_vm: AsyncMock) -> None:
    """GET /api/v1/compliance/siri/vm returns XML."""
    mock_siri_vm.return_value = SAMPLE_XML

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/compliance/siri/vm")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/xml"


@pytest.mark.asyncio
async def test_siri_sm_requires_stop_name() -> None:
    """GET /api/v1/compliance/siri/sm without stop_name returns 422."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/compliance/siri/sm")

    assert response.status_code == 422


@pytest.mark.asyncio
@patch("app.compliance.service.ComplianceService.get_export_status", new_callable=AsyncMock)
async def test_status_returns_json(mock_status: AsyncMock) -> None:
    """GET /api/v1/compliance/status returns JSON with entity counts."""
    mock_status.return_value = ExportMetadata(
        format="NeTEx",
        version="1.2",
        codespace="TEST",
        generated_at="2026-03-03T12:00:00Z",
        entity_counts={"agencies": 1, "routes": 5, "trips": 50, "stops": 200},
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/compliance/status")

    assert response.status_code == 200
    data = response.json()
    assert data["format"] == "NeTEx"
    assert data["entity_counts"]["routes"] == 5


@pytest.mark.asyncio
async def test_compliance_endpoints_in_openapi_spec() -> None:
    """All 4 compliance endpoints appear in the OpenAPI schema."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    spec = response.json()
    paths = spec["paths"]

    expected_paths = [
        "/api/v1/compliance/netex",
        "/api/v1/compliance/siri/vm",
        "/api/v1/compliance/siri/sm",
        "/api/v1/compliance/status",
    ]
    for path in expected_paths:
        assert path in paths, f"{path} missing from OpenAPI spec"

    # XML endpoints should document application/xml response
    for xml_path in expected_paths[:3]:
        responses = paths[xml_path]["get"]["responses"]
        assert "200" in responses
        content = responses["200"].get("content", {})
        assert "application/xml" in content, f"{xml_path} missing application/xml content type"

    # Status endpoint should document application/json response
    status_responses = paths[expected_paths[3]]["get"]["responses"]
    assert "200" in status_responses
    status_content = status_responses["200"].get("content", {})
    assert "application/json" in status_content


@pytest.mark.asyncio
async def test_endpoints_require_authentication() -> None:
    """All compliance endpoints return 401 without auth."""
    # Remove the auth override
    app.dependency_overrides.pop(get_current_user, None)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        endpoints = [
            "/api/v1/compliance/netex",
            "/api/v1/compliance/siri/vm",
            "/api/v1/compliance/siri/sm?stop_name=Test",
            "/api/v1/compliance/status",
        ]
        for endpoint in endpoints:
            response = await client.get(endpoint)
            assert response.status_code == 401, (
                f"{endpoint} returned {response.status_code}, expected 401"
            )
