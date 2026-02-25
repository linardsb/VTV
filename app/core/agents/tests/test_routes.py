"""Tests for agent API routes."""

from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.agents.agent import agent
from app.core.rate_limit import limiter
from app.main import app

# Prevent accidental real LLM API calls during testing
models.ALLOW_MODEL_REQUESTS = False

# Disable rate limiting during tests
limiter.enabled = False


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


def test_chat_completions_endpoint():
    with agent.override(model=TestModel()):
        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Hello"}]},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "chat.completion"
    assert "choices" in data
    assert "model" in data


def test_chat_completions_empty_messages():
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={"messages": []},
        )

    assert response.status_code == 422


def test_models_endpoint():
    with TestClient(app) as client:
        response = client.get("/v1/models")

    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert isinstance(data["data"], list)
    assert len(data["data"]) >= 1
    assert data["data"][0]["object"] == "model"


def test_chat_completions_returns_assistant_message():
    with agent.override(model=TestModel()):
        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "What is VTV?"}]},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["choices"][0]["finish_reason"] == "stop"
