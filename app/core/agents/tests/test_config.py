"""Tests for agent configuration module."""

import os
from unittest.mock import patch

from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.groq import GroqModel
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
    settings = create_settings(
        LLM_PROVIDER="anthropic",
        LLM_MODEL="claude-sonnet-4-5",
        ANTHROPIC_API_KEY="sk-test-key",
    )
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
        ANTHROPIC_API_KEY="sk-test-key",
    )
    result = get_agent_model(settings)
    # Anthropic provider takes priority — returns AnthropicModel directly
    assert isinstance(result, AnthropicModel)


def test_get_agent_model_anthropic_missing_key():
    """Falls back to TestModel when Anthropic API key is not set."""
    settings = create_settings(LLM_PROVIDER="anthropic", LLM_MODEL="claude-sonnet-4-5")
    result = get_agent_model(settings)
    assert isinstance(result, TestModel)


def test_get_agent_model_google():
    settings = create_settings(
        LLM_PROVIDER="google",
        LLM_MODEL="gemini-2.0-flash",
        GOOGLE_API_KEY="test-google-key",
    )
    result = get_agent_model(settings)
    assert isinstance(result, GoogleModel)


def test_get_agent_model_google_missing_key():
    """Falls back to TestModel when Google API key is not set."""
    settings = create_settings(LLM_PROVIDER="google", LLM_MODEL="gemini-2.0-flash")
    result = get_agent_model(settings)
    assert isinstance(result, TestModel)


def test_get_agent_model_groq():
    settings = create_settings(
        LLM_PROVIDER="groq",
        LLM_MODEL="llama-3.3-70b-versatile",
        GROQ_API_KEY="test-groq-key",
    )
    result = get_agent_model(settings)
    assert isinstance(result, GroqModel)


def test_get_agent_model_groq_missing_key():
    """Falls back to TestModel when Groq API key is not set."""
    settings = create_settings(
        LLM_PROVIDER="groq", LLM_MODEL="llama-3.3-70b-versatile", GROQ_API_KEY=""
    )
    result = get_agent_model(settings)
    assert isinstance(result, TestModel)
