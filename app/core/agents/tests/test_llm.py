"""Unit tests for the LLM provider chain registry + invoker (AI-8.3)."""

from __future__ import annotations

import pytest

from app.core.agents.circuit_breaker import CircuitState
from app.core.agents.exceptions import AllProvidersUnavailableError
from app.core.agents.llm import (
    get_breaker,
    get_breaker_state,
    invoke_provider_chain,
    reset_provider_breakers,
)
from app.core.config import Settings


def _make_settings(
    *,
    primary: str = "primary",
    fallback: str | None = None,
    enabled: bool = True,
    failure_threshold: int = 3,
) -> Settings:
    """Build a ``Settings`` instance with deterministic chain config."""
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        llm_provider=primary,
        llm_fallback_provider=fallback,
        circuit_breaker_enabled=enabled,
        circuit_breaker_failure_threshold=failure_threshold,
        circuit_breaker_recovery_timeout_s=10.0,
        circuit_breaker_success_threshold=2,
        circuit_breaker_failure_rate_threshold=0.5,
    )


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    """Reset the breaker registry before every test."""
    reset_provider_breakers()


def test_get_breaker_lazy_init() -> None:
    """First ``get_breaker`` call constructs; second returns the same instance."""
    settings = _make_settings()
    first = get_breaker("primary", settings)
    second = get_breaker("primary", settings)
    assert first is second
    assert first.state is CircuitState.CLOSED


def test_get_breaker_state_unregistered_returns_closed() -> None:
    """Unknown provider names report CLOSED without registering anything."""
    assert get_breaker_state("never-seen") is CircuitState.CLOSED


@pytest.mark.asyncio
async def test_invoke_provider_chain_disabled_passes_through() -> None:
    """When the breaker is disabled, no registry entries are created."""
    settings = _make_settings(enabled=False, primary="primary", fallback="fallback")
    seen: list[str] = []

    async def _call(provider: str) -> str:
        seen.append(provider)
        return f"result-{provider}"

    result = await invoke_provider_chain(_call, settings=settings)

    assert result == "result-primary"
    assert seen == ["primary"]
    # Disabled path must NOT mutate the registry — preserves pre-AI-8 behavior.
    assert get_breaker_state("primary") is CircuitState.CLOSED
    assert get_breaker_state("fallback") is CircuitState.CLOSED


@pytest.mark.asyncio
async def test_invoke_provider_chain_primary_open_skips_to_fallback() -> None:
    """An OPEN primary breaker fast-fails to the fallback without calling primary."""
    settings = _make_settings(primary="primary", fallback="fallback", failure_threshold=1)

    # Trip the primary breaker by injecting a single failure.
    primary = get_breaker("primary", settings)

    async def _boom(_: str) -> str:
        raise RuntimeError("primary down")

    with pytest.raises(RuntimeError, match="primary down"):
        await primary.call(_boom, "primary")
    assert primary.state is CircuitState.OPEN

    # Now invoke the chain — primary should be skipped and fallback called.
    seen: list[str] = []

    async def _ok(provider: str) -> str:
        seen.append(provider)
        return f"result-{provider}"

    result = await invoke_provider_chain(_ok, settings=settings)

    assert result == "result-fallback"
    assert seen == ["fallback"]  # primary was preempted, never called


@pytest.mark.asyncio
async def test_invoke_provider_chain_all_exhausted_raises() -> None:
    """When every provider in the chain raises, AllProvidersUnavailableError is raised."""
    settings = _make_settings(primary="primary", fallback="fallback", failure_threshold=10)
    seen: list[str] = []

    async def _always_fail(provider: str) -> str:
        seen.append(provider)
        raise RuntimeError(f"{provider} unreachable")

    with pytest.raises(AllProvidersUnavailableError) as exc_info:
        await invoke_provider_chain(_always_fail, settings=settings)

    assert exc_info.value.providers_tried == ["primary", "fallback"]
    assert seen == ["primary", "fallback"]
