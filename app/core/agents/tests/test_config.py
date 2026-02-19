"""Tests for agent configuration module."""

import os
from unittest.mock import patch

from pydantic_ai.models.anthropic import AnthropicModel
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
        return Settings()  # pyright: ignore[reportCallIssue]


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
    assert isinstance(result, AnthropicModel)


def test_get_agent_model_with_fallback():
    """Test that fallback config with anthropic primary still returns AnthropicModel.

    When the primary provider is anthropic, it returns an AnthropicModel directly
    (with explicit api_key), regardless of fallback configuration.
    Fallback is only used for generic string-based providers.
    """
    settings = create_settings(
        LLM_PROVIDER="anthropic",
        LLM_MODEL="claude-sonnet-4-5",
        LLM_FALLBACK_PROVIDER="ollama",
        LLM_FALLBACK_MODEL="llama3.1:70b",
    )
    result = get_agent_model(settings)
    # Anthropic provider takes priority — returns AnthropicModel directly
    assert isinstance(result, AnthropicModel)
