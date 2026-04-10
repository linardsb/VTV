"""Tests for agent API routes."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.agents.agent import agent
from app.core.agents.base import BaseAgentService
from app.core.agents.schemas import (
    ChatCompletionChoice,
    ChatCompletionResponse,
    ChatMessage,
)
from app.core.config import get_settings
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


@pytest.fixture(autouse=True)
def _bypass_quota_tracker() -> Generator[None, None, None]:
    """Bypass the daily quota tracker for route tests.

    Without this, tests that hit ``/v1/chat/completions`` leak into a shared
    Redis-backed quota counter (or the in-memory fallback) and eventually
    exhaust the 50-query daily budget, causing cascading 429s across the
    suite. Patching ``get_quota_tracker`` on the routes module returns a
    stub that always allows.
    """
    fake_tracker = MagicMock()
    fake_tracker.check_and_increment = AsyncMock(return_value=True)
    fake_tracker.get_remaining = AsyncMock(return_value=50)
    with patch("app.core.agents.routes.get_quota_tracker", return_value=fake_tracker):
        yield


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


# --- AI-6.2: agent selector regressions -----------------------------------


def _fake_chat_response() -> ChatCompletionResponse:
    """Build a minimal ChatCompletionResponse for patching service.chat()."""
    return ChatCompletionResponse(
        model="test:test-model",
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content="ok"),
                finish_reason="stop",
            )
        ],
    )


def test_chat_completions_unknown_agent_returns_422() -> None:
    """Pydantic Literal validation rejects unknown selector values."""
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "agent": "bogus",
            },
        )
    assert response.status_code == 422


def test_chat_completions_default_agent_is_unified() -> None:
    """Omitting ``agent`` resolves to the unified ``AgentService``."""
    fake_service = MagicMock()
    fake_service.chat = AsyncMock(return_value=_fake_chat_response())

    with patch(
        "app.core.agents.routes.get_agent_by_name", return_value=fake_service
    ) as mock_resolver:
        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Hello"}]},
            )

    assert response.status_code == 200
    mock_resolver.assert_called_once_with("unified")
    fake_service.chat.assert_awaited_once()


def test_chat_completions_routes_to_transit_agent() -> None:
    """Explicit ``agent: 'transit'`` is forwarded to ``get_agent_by_name``."""
    fake_service = MagicMock()
    fake_service.chat = AsyncMock(return_value=_fake_chat_response())

    with patch(
        "app.core.agents.routes.get_agent_by_name", return_value=fake_service
    ) as mock_resolver:
        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": "Kuri marsruti kavejas?"}],
                    "agent": "transit",
                },
            )

    assert response.status_code == 200
    mock_resolver.assert_called_once_with("transit")
    fake_service.chat.assert_awaited_once()


# --- AI-6.3: server-side AgentRouter auto-routing -------------------------


class TestChatCompletionsAutoRouting:
    """AI-6.3: server-side AgentRouter wires into chat_completions."""

    def test_flag_disabled_no_auto_routing(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When AGENT_MULTI_AGENT_ENABLED is False, body.agent is honored verbatim."""
        monkeypatch.setenv("AGENT_MULTI_AGENT_ENABLED", "false")
        get_settings.cache_clear()
        try:
            fake_service = MagicMock(spec=BaseAgentService)
            fake_service.chat = AsyncMock(return_value=_fake_chat_response())
            with patch(
                "app.core.agents.routes.get_agent_by_name",
                return_value=fake_service,
            ) as resolver:
                with TestClient(app) as client:
                    response = client.post(
                        "/v1/chat/completions",
                        json={"messages": [{"role": "user", "content": "Kuri maršruti kavējas?"}]},
                    )
            assert response.status_code == 200
            resolver.assert_called_once_with("unified")
        finally:
            get_settings.cache_clear()

    def test_flag_enabled_routes_transit_prompt(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When flag is on and prompt is transit-y, request reaches transit agent."""
        monkeypatch.setenv("AGENT_MULTI_AGENT_ENABLED", "true")
        get_settings.cache_clear()
        try:
            fake_service = MagicMock(spec=BaseAgentService)
            fake_service.chat = AsyncMock(return_value=_fake_chat_response())
            with patch(
                "app.core.agents.routes.get_agent_by_name",
                return_value=fake_service,
            ) as resolver:
                with TestClient(app) as client:
                    response = client.post(
                        "/v1/chat/completions",
                        json={
                            "messages": [{"role": "user", "content": "Which routes are delayed?"}]
                        },
                    )
            assert response.status_code == 200
            resolver.assert_called_once_with("transit")
        finally:
            get_settings.cache_clear()

    def test_flag_enabled_cross_domain_falls_back_to_unified(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Tied scores -> unified."""
        monkeypatch.setenv("AGENT_MULTI_AGENT_ENABLED", "true")
        get_settings.cache_clear()
        try:
            fake_service = MagicMock(spec=BaseAgentService)
            fake_service.chat = AsyncMock(return_value=_fake_chat_response())
            with patch(
                "app.core.agents.routes.get_agent_by_name",
                return_value=fake_service,
            ) as resolver:
                with TestClient(app) as client:
                    response = client.post(
                        "/v1/chat/completions",
                        json={
                            "messages": [
                                {
                                    "role": "user",
                                    "content": (
                                        "What routes serve the hospitals mentioned in the SOP?"
                                    ),
                                }
                            ]
                        },
                    )
            assert response.status_code == 200
            resolver.assert_called_once_with("unified")
        finally:
            get_settings.cache_clear()
