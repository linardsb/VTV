"""Agent-specific configuration for LLM model selection.

This module provides functions to build model strings and resolve
the appropriate Pydantic AI model instance based on application settings.
"""

from typing import Literal

from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.providers.ollama import OllamaProvider

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def build_model_string(settings: Settings) -> str:
    """Build a provider:model string from settings.

    Args:
        settings: Application settings containing LLM provider and model.

    Returns:
        Model string in "provider:model" format (e.g., "anthropic:claude-sonnet-4-5").
    """
    return f"{settings.llm_provider}:{settings.llm_model}"


def get_agent_model(settings: Settings | None = None) -> str | Model:
    """Resolve the Pydantic AI model to use for the agent.

    When the provider is "test", returns a TestModel instance directly
    (pydantic-ai does not recognize "test" as a valid provider string).
    When a fallback provider is configured, returns a FallbackModel.
    Otherwise returns the provider:model string for real LLM providers.

    Args:
        settings: Optional settings instance. If None, uses get_settings().

    Returns:
        Either a model string (e.g., "anthropic:claude-sonnet-4-5"),
        a TestModel instance, or a FallbackModel instance.
    """
    if settings is None:
        settings = get_settings()

    provider = settings.llm_provider
    model = settings.llm_model
    has_fallback = settings.llm_fallback_provider is not None

    logger.info(
        "agent.config.model_configured",
        provider=provider,
        model=model,
        has_fallback=has_fallback,
    )

    # TestModel for testing — pydantic-ai rejects "test:test-model" as unknown provider
    if provider == "test":
        return TestModel()

    # Anthropic needs explicit api_key since env var may not be set at import time
    if provider == "anthropic":
        if not settings.anthropic_api_key:
            logger.warning("agent.config.anthropic_api_key_missing")
            return TestModel()
        anthropic_provider = AnthropicProvider(api_key=settings.anthropic_api_key)
        return AnthropicModel(model, provider=anthropic_provider)

    # Google Gemini needs explicit api_key
    if provider == "google":
        if not settings.google_api_key:
            logger.warning("agent.config.google_api_key_missing")
            return TestModel()
        google_provider = GoogleProvider(api_key=settings.google_api_key)
        return GoogleModel(model, provider=google_provider)

    # Groq needs explicit api_key
    if provider == "groq":
        if not settings.groq_api_key:
            logger.warning("agent.config.groq_api_key_missing")
            return TestModel()
        groq_provider = GroqProvider(api_key=settings.groq_api_key)
        return GroqModel(model, provider=groq_provider)

    # Ollama needs explicit base_url since env var may not be set at import time
    if provider == "ollama":
        ollama_provider = OllamaProvider(base_url=settings.ollama_base_url)
        return OpenAIChatModel(model, provider=ollama_provider)

    primary = build_model_string(settings)

    if has_fallback and settings.llm_fallback_model is not None:
        fallback = f"{settings.llm_fallback_provider}:{settings.llm_fallback_model}"
        return FallbackModel(primary, fallback)

    return primary


ModelTier = Literal["fast", "standard", "complex"]


def resolve_tier_model(tier: ModelTier, settings: Settings | None = None) -> str | Model | None:
    """Resolve a model for a specific routing tier.

    Returns the tier-specific model if configured, or None to use the agent's
    default model (set at creation time via get_agent_model).

    Args:
        tier: The routing tier - "fast", "standard", or "complex".
        settings: Optional settings. If None, uses get_settings().

    Returns:
        A Pydantic AI model instance/string for the tier, or None if the tier
        has no override configured (meaning: use the agent's default model).
    """
    if settings is None:
        settings = get_settings()

    tier_map: dict[ModelTier, tuple[str | None, str | None]] = {
        "fast": (settings.llm_fast_provider, settings.llm_fast_model),
        "standard": (settings.llm_standard_provider, settings.llm_standard_model),
        "complex": (settings.llm_complex_provider, settings.llm_complex_model),
    }

    provider, model = tier_map[tier]

    # No tier override configured — caller should use agent default
    if provider is None or model is None:
        return None

    # Test provider
    if provider == "test":
        return TestModel()

    # Anthropic
    if provider == "anthropic":
        if not settings.anthropic_api_key:
            logger.warning("agent.config.tier_api_key_missing", tier=tier, provider=provider)
            return None
        return AnthropicModel(model, provider=AnthropicProvider(api_key=settings.anthropic_api_key))

    # Google
    if provider == "google":
        if not settings.google_api_key:
            logger.warning("agent.config.tier_api_key_missing", tier=tier, provider=provider)
            return None
        return GoogleModel(model, provider=GoogleProvider(api_key=settings.google_api_key))

    # Groq
    if provider == "groq":
        if not settings.groq_api_key:
            logger.warning("agent.config.tier_api_key_missing", tier=tier, provider=provider)
            return None
        return GroqModel(model, provider=GroqProvider(api_key=settings.groq_api_key))

    # Ollama
    if provider == "ollama":
        return OpenAIChatModel(model, provider=OllamaProvider(base_url=settings.ollama_base_url))

    # Generic provider:model string
    return f"{provider}:{model}"
