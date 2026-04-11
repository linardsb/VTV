"""LLM provider chain invoker with per-provider circuit breaker preemption (AI-8.3).

Wraps the AI-8.1 :class:`CircuitBreaker` primitive in a process-wide registry
and exposes :func:`invoke_provider_chain`, the helper used by ``service.py``
at every LLM call site to:

* Skip providers whose breaker is OPEN *before* incurring a call-time
  timeout (the verification target: <100ms fast-fail after trip).
* Cascade through ``settings.llm_provider`` → ``settings.llm_fallback_provider``
  on either preemption or runtime failure.
* Raise :class:`AllProvidersUnavailableError` once the chain is exhausted so
  the service layer can return a degraded :class:`AgentResult`.

Kill switch: when ``settings.circuit_breaker_enabled`` is ``False`` the helper
flattens to a single direct call against ``settings.llm_provider`` with no
breaker wrapping and no registry writes — preserves pre-AI-8 behavior
byte-for-byte. Pydantic AI's :class:`FallbackModel` remains the belt-and-braces
layer for that path.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.core.agents.circuit_breaker import (
    BreakerConfig,
    CircuitBreaker,
    CircuitState,
)
from app.core.agents.exceptions import (
    AllProvidersUnavailableError,
    CircuitBreakerOpenError,
)
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Module-level breaker registry. Lazy-init on first :func:`get_breaker` call.
# The dict mutation is racy under asyncio but idempotent — concurrent first
# registrations of the same provider just overwrite each other with an
# equivalent ``CircuitBreaker``. The ``CircuitBreaker`` itself owns an
# ``asyncio.Lock`` for state transitions.
_breakers: dict[str, CircuitBreaker] = {}


def _build_config(settings: Settings) -> BreakerConfig:
    """Construct a :class:`BreakerConfig` from the application settings."""
    return BreakerConfig(
        failure_threshold=settings.circuit_breaker_failure_threshold,
        recovery_timeout_s=settings.circuit_breaker_recovery_timeout_s,
        success_threshold=settings.circuit_breaker_success_threshold,
        failure_rate_threshold=settings.circuit_breaker_failure_rate_threshold,
    )


def get_breaker(provider_name: str, settings: Settings | None = None) -> CircuitBreaker:
    """Return (or lazily create) the breaker for ``provider_name``.

    Args:
        provider_name: Short provider identifier (e.g. ``anthropic``).
        settings: Optional :class:`Settings` override (used in tests). When
            ``None``, ``get_settings()`` is consulted.

    Returns:
        The registry-resident :class:`CircuitBreaker` for this provider.
    """
    breaker = _breakers.get(provider_name)
    if breaker is None:
        breaker = CircuitBreaker(
            name=provider_name,
            config=_build_config(settings or get_settings()),
        )
        _breakers[provider_name] = breaker
    return breaker


def get_breaker_state(provider_name: str) -> CircuitState:
    """Return the current state of ``provider_name``'s breaker.

    Read-only lookup that does *not* mutate the registry. Used by
    :mod:`app.core.agents.provider_health` to surface live breaker state in
    the admin endpoint without coupling the tracker to breaker construction.

    Returns:
        The breaker's current :class:`CircuitState`, or
        :attr:`CircuitState.CLOSED` when the provider has not been registered
        yet (no calls have flowed through this provider in this process).
    """
    breaker = _breakers.get(provider_name)
    return breaker.state if breaker is not None else CircuitState.CLOSED


def reset_provider_breakers() -> None:
    """Test-only helper: clear the registry between tests."""
    _breakers.clear()


def _provider_chain(settings: Settings) -> list[str]:
    """Return the ordered fallback chain for the current settings."""
    chain = [settings.llm_provider]
    fallback = settings.llm_fallback_provider
    if fallback and fallback != settings.llm_provider:
        chain.append(fallback)
    return chain


async def invoke_provider_chain[T](
    call: Callable[[str], Awaitable[T]],
    *,
    settings: Settings | None = None,
) -> T:
    """Invoke ``call(provider_name)`` across the fallback chain with breaker preemption.

    For each provider in the chain (primary, then optional fallback):

    * If the provider's breaker is OPEN, log ``agent.provider_chain.preempted``
      and skip to the next provider — no call is made and no timeout is
      incurred.
    * Otherwise the call is dispatched through ``breaker.call(...)`` so the
      breaker records success or failure.
    * On exception (either :class:`CircuitBreakerOpenError` from a race or any
      other exception), log ``agent.provider_chain.fallback`` and continue
      with the next provider.

    When ``settings.circuit_breaker_enabled`` is ``False`` the chain is
    flattened to the single primary provider with no breaker wrapping — this
    is the byte-for-byte preserved pre-AI-8 path.

    Args:
        call: An async callable that accepts a provider name and performs the
            actual LLM invocation. The caller is responsible for resolving
            the right :class:`pydantic_ai.models.Model` for that provider
            inside the closure.
        settings: Optional :class:`Settings` override (tests).

    Returns:
        Whatever the first successful ``call`` returns.

    Raises:
        AllProvidersUnavailableError: When every provider in the chain has
            been preempted or has raised.
    """
    s = settings or get_settings()

    if not s.circuit_breaker_enabled:
        return await call(s.llm_provider)

    chain = _provider_chain(s)
    tried: list[str] = []
    last_error: Exception | None = None

    for provider in chain:
        breaker = get_breaker(provider, s)
        # Always go through ``breaker.call`` so the OPEN→HALF_OPEN recovery
        # transition (driven by ``_before_call``) gets a chance to fire when
        # ``recovery_timeout_s`` has elapsed. ``CircuitBreakerOpenError`` is
        # raised both for the no-recovery-yet case and for the rare race
        # where the breaker re-opens between state check and call.
        try:
            return await breaker.call(call, provider)
        except CircuitBreakerOpenError:
            tried.append(provider)
            logger.info(
                "agent.provider_chain.preempted",
                provider=provider,
                reason="breaker_open",
            )
            continue
        except Exception as exc:
            tried.append(provider)
            last_error = exc
            logger.warning(
                "agent.provider_chain.fallback",
                provider=provider,
                error_type=type(exc).__name__,
            )
            continue

    logger.error(
        "agent.provider_chain.exhausted",
        providers_tried=tried,
        last_error_type=type(last_error).__name__ if last_error is not None else None,
    )
    raise AllProvidersUnavailableError(providers_tried=tried)


__all__ = [
    "get_breaker",
    "get_breaker_state",
    "invoke_provider_chain",
    "reset_provider_breakers",
]
