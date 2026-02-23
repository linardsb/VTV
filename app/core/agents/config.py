"""Agent-specific configuration for LLM model selection.

This module provides functions to build model strings and resolve
the appropriate Pydantic AI model instance based on application settings.
"""

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
