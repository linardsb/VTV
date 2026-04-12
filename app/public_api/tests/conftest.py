# pyright: reportCallIssue=false
"""Test fixtures for public API feature tests."""

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.public_api.models import APIKey, APIKeyUsage


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock AsyncSession for unit tests."""
    return AsyncMock()


def make_api_key(**overrides: object) -> MagicMock:
    """Factory for APIKey model instances.

    Args:
        **overrides: Fields to override on the default APIKey.

    Returns:
        MagicMock spec'd to APIKey with sensible defaults.
    """
    defaults: dict[str, object] = {
        "id": 1,
        "name": "Test Key",
        "key_hash": "a" * 64,
        "key_preview": "vtv_pk_...abcd",
        "owner_user_id": 10,
        "tier": "free",
        "is_active": True,
        "last_used_at": None,
        "revoked_at": None,
        "expires_at": None,
        "created_at": datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        "updated_at": datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
    }
    defaults.update(overrides)
    key = MagicMock(spec=APIKey)
    for k, v in defaults.items():
        setattr(key, k, v)
    return key


def make_api_key_usage(**overrides: object) -> MagicMock:
    """Factory for APIKeyUsage model instances.

    Args:
        **overrides: Fields to override on the default APIKeyUsage.

    Returns:
        MagicMock spec'd to APIKeyUsage with sensible defaults.
    """
    defaults: dict[str, object] = {
        "id": 1,
        "api_key_id": 1,
        "recorded_at": datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        "endpoint": "/public/v1/routes",
        "method": "GET",
        "status_code": 200,
        "response_time_ms": 50,
    }
    defaults.update(overrides)
    usage = MagicMock(spec=APIKeyUsage)
    for k, v in defaults.items():
        setattr(usage, k, v)
    return usage
