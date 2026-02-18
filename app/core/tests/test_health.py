# pyright: reportArgumentType=false
"""Unit tests for health check endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, status

from app.core.health import (
    database_health_check,
    health_check,
    readiness_check,
)
from app.core.rate_limit import limiter

# Disable rate limiting during tests
limiter.enabled = False


@pytest.fixture(autouse=True)
def _clear_db_health_cache() -> None:
    """Clear the DB health cache before each test."""
    import app.core.health as health_mod

    health_mod._db_health_cache = None
    health_mod._db_health_cache_time = 0.0


@pytest.mark.asyncio
async def test_health_check_returns_healthy():
    """Test that basic health check returns healthy status."""
    response = await health_check(request=None)
    assert response["status"] == "healthy"
    assert response["service"] == "api"


@pytest.mark.asyncio
async def test_database_health_check_success():
    """Test database health check with successful connection."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()

    response = await database_health_check(request=None, db=mock_db)
    mock_db.execute.assert_called_once()
    call_args = mock_db.execute.call_args[0][0]
    assert str(call_args) == "SELECT 1"

    assert response["status"] == "healthy"
    assert response["service"] == "database"
    assert response["provider"] == "postgresql"


@pytest.mark.asyncio
async def test_database_health_check_failure():
    """Test database health check with failed connection."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("Database connection failed"))

    with patch("app.core.health.logger.error"):
        with pytest.raises(HTTPException) as exc_info:
            await database_health_check(request=None, db=mock_db)
    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "Database is not accessible" in exc_info.value.detail


@pytest.mark.asyncio
async def test_readiness_check_success():
    """Test readiness check with all dependencies healthy."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()

    with patch("app.core.health.get_settings") as mock_get_settings:
        mock_settings = AsyncMock()
        mock_settings.environment = "test"
        mock_get_settings.return_value = mock_settings

        response = await readiness_check(request=None, db=mock_db)
    mock_db.execute.assert_called_once()

    assert response["status"] == "ready"
    assert response["environment"] == "test"
    assert response["database"] == "connected"


@pytest.mark.asyncio
async def test_readiness_check_failure():
    """Test readiness check with failed dependencies."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("Database not ready"))

    with patch("app.core.health.get_settings") as mock_get_settings:
        mock_settings = AsyncMock()
        mock_settings.environment = "test"
        mock_get_settings.return_value = mock_settings

        with patch("app.core.health.logger.error"):
            with pytest.raises(HTTPException) as exc_info:
                await readiness_check(request=None, db=mock_db)
    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "Application is not ready" in exc_info.value.detail


@pytest.mark.asyncio
async def test_database_health_check_logs_error():
    """Test that database health check logs errors properly."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("Connection error"))

    with patch("app.core.health.logger.error") as mock_logger:
        with pytest.raises(HTTPException):
            await database_health_check(request=None, db=mock_db)
        mock_logger.assert_called_once()
        assert "database.health_check_failed" in str(mock_logger.call_args)


@pytest.mark.asyncio
async def test_readiness_check_logs_error():
    """Test that readiness check logs errors properly."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("Not ready"))

    with patch("app.core.health.get_settings"):
        with patch("app.core.health.logger.error") as mock_logger:
            with pytest.raises(HTTPException):
                await readiness_check(request=None, db=mock_db)
            mock_logger.assert_called_once()
            assert "health.readiness_check_failed" in str(mock_logger.call_args)
