"""Tests for agent configuration module."""

import os
from unittest.mock import patch

from pydantic_ai.models.test import TestModel

from app.core.agents.config import build_model_string, get_agent_model
from app.core.config import Settings, get_settings


def create_settings(**overrides: str) -> Settings:
    """Create Settings instance with test defaults and optional overrides."""
    env = {
        "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test_db",
        **overrides,
    }
    with patch.dict(os.environ, env):
        get_settings.cache_clear()
        return Settings()  # type: ignore[call-arg]


def test_build_model_string():
    settings = create_settings(LLM_PROVIDER="anthropic", LLM_MODEL="claude-sonnet-4-5")
    result = build_model_string(settings)
    assert result == "anthropic:claude-sonnet-4-5"


def test_build_model_string_ollama():
    settings = create_settings(LLM_PROVIDER="ollama", LLM_MODEL="llama3.1:70b")
    result = build_model_string(settings)
    assert result == "ollama:llama3.1:70b"


def test_get_agent_model_test_provider():
    settings = create_settings(LLM_PROVIDER="test", LLM_MODEL="test-model")
    result = get_agent_model(settings)
    assert isinstance(result, TestModel)


def test_get_agent_model_no_fallback():
    settings = create_settings(LLM_PROVIDER="anthropic", LLM_MODEL="claude-sonnet-4-5")
    result = get_agent_model(settings)
    assert isinstance(result, str)
    assert result == "anthropic:claude-sonnet-4-5"


def test_get_agent_model_with_fallback():
    """Test that fallback config triggers FallbackModel creation.

    We mock FallbackModel because it eagerly validates provider API keys
    at construction time, which requires real credentials.
    """
    settings = create_settings(
        LLM_PROVIDER="anthropic",
        LLM_MODEL="claude-sonnet-4-5",
        LLM_FALLBACK_PROVIDER="ollama",
        LLM_FALLBACK_MODEL="llama3.1:70b",
    )
    with patch("app.core.agents.config.FallbackModel") as mock_fallback:
        mock_fallback.return_value = mock_fallback
        result = get_agent_model(settings)

    mock_fallback.assert_called_once_with(
        "anthropic:claude-sonnet-4-5",
        "ollama:llama3.1:70b",
    )
    assert result is mock_fallback
