"""Tests for agent configuration module."""

import os
from unittest.mock import patch

from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.models.test import TestModel

from app.core.agents.config import build_model_string, get_agent_model, resolve_tier_model
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


def test_resolve_tier_model_no_override() -> None:
    """Returns None when no tier-specific model is configured."""
    settings = create_settings(LLM_PROVIDER="anthropic", LLM_MODEL="claude-sonnet-4-5")
    result = resolve_tier_model("fast", settings)
    assert result is None


def test_resolve_tier_model_fast_anthropic() -> None:
    """Resolves fast tier to Anthropic model when configured."""
    settings = create_settings(
        LLM_PROVIDER="anthropic",
        LLM_MODEL="claude-sonnet-4-5",
        LLM_FAST_PROVIDER="anthropic",
        LLM_FAST_MODEL="claude-haiku-4-5",
        ANTHROPIC_API_KEY="sk-test-key",
    )
    result = resolve_tier_model("fast", settings)
    assert isinstance(result, AnthropicModel)


def test_resolve_tier_model_complex_anthropic() -> None:
    """Resolves complex tier to Anthropic model when configured."""
    settings = create_settings(
        LLM_PROVIDER="anthropic",
        LLM_MODEL="claude-sonnet-4-5",
        LLM_COMPLEX_PROVIDER="anthropic",
        LLM_COMPLEX_MODEL="claude-opus-4-5",
        ANTHROPIC_API_KEY="sk-test-key",
    )
    result = resolve_tier_model("complex", settings)
    assert isinstance(result, AnthropicModel)


def test_resolve_tier_model_standard_no_override() -> None:
    """Standard tier returns None when not explicitly configured."""
    settings = create_settings(
        LLM_PROVIDER="anthropic",
        LLM_MODEL="claude-sonnet-4-5",
        LLM_FAST_PROVIDER="anthropic",
        LLM_FAST_MODEL="claude-haiku-4-5",
        ANTHROPIC_API_KEY="sk-test-key",
    )
    result = resolve_tier_model("standard", settings)
    assert result is None


def test_resolve_tier_model_missing_api_key() -> None:
    """Returns None when tier provider API key is missing."""
    settings = create_settings(
        LLM_PROVIDER="google",
        LLM_MODEL="gemini-2.0-flash",
        LLM_FAST_PROVIDER="anthropic",
        LLM_FAST_MODEL="claude-haiku-4-5",
        GOOGLE_API_KEY="test-google-key",
    )
    result = resolve_tier_model("fast", settings)
    assert result is None


def test_resolve_tier_model_test_provider() -> None:
    """Test provider returns TestModel for tier."""
    settings = create_settings(
        LLM_PROVIDER="anthropic",
        LLM_MODEL="claude-sonnet-4-5",
        LLM_FAST_PROVIDER="test",
        LLM_FAST_MODEL="test-model",
        ANTHROPIC_API_KEY="sk-test-key",
    )
    result = resolve_tier_model("fast", settings)
    assert isinstance(result, TestModel)


def test_resolve_tier_model_google() -> None:
    """Resolves tier to Google model."""
    settings = create_settings(
        LLM_PROVIDER="anthropic",
        LLM_MODEL="claude-sonnet-4-5",
        LLM_FAST_PROVIDER="google",
        LLM_FAST_MODEL="gemini-2.0-flash",
        ANTHROPIC_API_KEY="sk-test-key",
        GOOGLE_API_KEY="test-google-key",
    )
    result = resolve_tier_model("fast", settings)
    assert isinstance(result, GoogleModel)


def test_resolve_tier_model_generic_string() -> None:
    """Returns provider:model string for unknown providers."""
    settings = create_settings(
        LLM_PROVIDER="anthropic",
        LLM_MODEL="claude-sonnet-4-5",
        LLM_FAST_PROVIDER="openrouter",
        LLM_FAST_MODEL="meta-llama/llama-3.1-8b",
        ANTHROPIC_API_KEY="sk-test-key",
    )
    result = resolve_tier_model("fast", settings)
    assert result == "openrouter:meta-llama/llama-3.1-8b"
