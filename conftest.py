"""Root pytest configuration and shared fixtures.

This conftest.py sits at the project root (next to pyproject.toml) and provides
fixtures available to ALL test modules across the application. Feature-specific
fixtures should remain in their respective tests/ directories.

Shared fixtures provided:
- client: FastAPI TestClient for endpoint testing
- mock_settings: Patched Settings for unit tests without .env dependency
"""

import os
from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


@pytest.fixture(scope="function")
def client() -> Generator[TestClient, None, None]:
    """Create a FastAPI TestClient for endpoint testing.

    Yields:
        TestClient instance configured with the VTV FastAPI app.
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def mock_settings() -> Generator[None, None, None]:
    """Patch environment variables for unit tests.

    Sets safe test defaults so unit tests don't depend on a .env file.
    Clears the settings cache before and after to ensure isolation.

    Yields:
        None — settings are patched via environment variables.
    """
    get_settings.cache_clear()
    with patch.dict(
        os.environ,
        {
            "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test_db",
            "ENVIRONMENT": "test",
            "LOG_LEVEL": "DEBUG",
            "LLM_PROVIDER": "test",
            "LLM_MODEL": "test-model",
        },
    ):
        yield
    get_settings.cache_clear()
