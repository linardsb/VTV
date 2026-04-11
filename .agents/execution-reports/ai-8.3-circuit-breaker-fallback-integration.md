# Execution Report — AI-8.3 Circuit Breaker Integration with FallbackModel

**Plan:** `.agents/plans/ai-8-3-circuit-breaker-fallback-integration.md`
**Date:** 2026-04-11
**Status:** ✅ Shipped — ready to commit

## Summary

Closes the AI-8 loop by wiring the AI-8.1 circuit breaker primitive into the LLM hot path via a per-provider registry and a `invoke_provider_chain` async helper. Service-level execution catches `AllProvidersUnavailableError` and degrades gracefully to a static, user-safe response. Pre-AI-8 behavior is preserved byte-for-byte when `circuit_breaker_enabled=False`. The AI-8.2 admin endpoint now reflects live breaker state (was previously hard-coded to `CLOSED`).

## Files Changed

| Action | File | Notes |
|---|---|---|
| CREATE | `app/core/agents/llm.py` | Per-provider breaker registry (`get_breaker`, `get_breaker_state`, `reset_provider_breakers`) + `invoke_provider_chain[T](call, *, settings)` async helper. PEP 695 generic syntax (Ruff UP047). Always-through-`breaker.call` design preserves OPEN→HALF_OPEN recovery transitions. |
| CREATE | `app/core/agents/tests/test_llm.py` | 5 unit tests: lazy registry init, unregistered → CLOSED, disabled passthrough (zero registry writes), primary-OPEN skip-to-fallback, all-exhausted raises `AllProvidersUnavailableError(providers_tried)`. |
| UPDATE | `app/core/agents/exceptions.py` | New `AllProvidersUnavailableError(AgentError)` with `providers_tried: list[str]` constructor. Wired into `agent_exception_handler` → HTTP 503 alongside `CircuitBreakerOpenError`. Module docstring + handler `isinstance` ladder + `setup_agent_exception_handlers()` registration all updated. |
| UPDATE | `app/core/agents/service.py` | Refactored `_execute()` into a 3-helper dispatch (`_execute_complex_tier`, `_execute_correction_tier`, `_execute_fallback_tier`); each helper wraps its LLM call in a closure run through `invoke_provider_chain`. Per-iteration observability via `track_provider_call(None, provider_name)` so the chain provider name keys both registries. `_execute()` catches `AllProvidersUnavailableError` and returns a static, user-safe degraded `_PipelineOutcome` (`confidence=None` skips AI-6.5 re-route gate; `warnings=[]` skips QA + footnote rendering). |
| UPDATE | `app/core/agents/provider_health.py` | `track_provider_call` now does a deferred `from app.core.agents.llm import get_breaker_state` (avoids module-load circular import) and forwards live `CircuitState` to `record_call(state=...)` on both branches. Stale AI-8.2-followup TODO removed; module + dataclass docstrings refreshed. |
| UPDATE | `app/core/agents/tests/conftest.py` | New `_reset_provider_breakers` autouse fixture clears the registry around every agent test (mirrors `_reset_skill_cache`). |
| UPDATE | `app/core/agents/tests/test_service.py` | Renamed `test_chat_failure_raises_agent_execution_error` → `test_chat_failure_with_breaker_disabled_raises_agent_execution_error` and gated it on `circuit_breaker_enabled=False` (the canonical regression test for byte-for-byte preserved kill-switch behavior). Added `TestCircuitBreakerIntegration` class with 8 tests covering trip→fallback routing, both-fail-degraded, both-open-degraded, fast-fail under 200ms, two-consecutive-fast-fail, recovery via HALF_OPEN→CLOSED, kill-switch-no-registry-writes, kill-switch-raw-exception-propagation. Added `_state(breaker)` indirection helper to defeat mypy literal narrowing. |
| UPDATE | `docs/TODO.md` | AI-8.3 marked ✅ Done with full implementation summary; Agent Intelligence progress bar bumped 88% → 90%. |
| UPDATE | `app/core/agents/CLAUDE.md` | New `llm.py` entry in directory tree; AI-8.3 amendments to `service.py`, `circuit_breaker.py`, `provider_health.py`, `exceptions.py` lines; tests count bumped to 388; "Provider resilience" narrative bullet (#7) extended with the AI-8.3 paragraph. |

## Validation Results

| Check | Result | Delta vs Baseline |
|---|---|---|
| `ruff format .` | ✅ clean (386 files) | — |
| `ruff check .` | ✅ All checks passed | — |
| `mypy app/` | 3 errors | unchanged baseline (`tools/transit/static_store.py:149,150` + `pipeline.py:136`) |
| `pyright app/core/agents/` | 5 errors | unchanged baseline (`pipeline.py` x4 + `tools/transit/client.py:193`) |
| `pyright` on new files (`llm.py`, `test_llm.py`) | 0 / 0 | clean |
| `pytest app/core/agents/tests/test_llm.py` | 5 passed | new |
| `pytest test_service.py::TestCircuitBreakerIntegration` | 8 passed | new |
| `pytest app/core/agents/tests/` | 388 passed | baseline 375 (AI-8.2) + 13 new (5 + 8) |
| `pytest -m "not integration"` (full unit suite) | 1482 passed, 1 pre-existing flake | `test_fetch_feed_http_error` flake **confirmed pre-existing on clean main** (verified by `git stash --include-untracked` then re-running; failure reproduces without any AI-8.3 code). Caused by the unrelated `_feed_breaker` module-level singleton in `app/core/resilience.py`. |
| `pytest app/tests/test_security.py` | 106 passed | unchanged |
| Integration / SDK sync / server | SKIPPED | Docker not running |

## Divergences from Plan

| # | Divergence | Why | Classification |
|---|---|---|---|
| 1 | `invoke_provider_chain` does NOT short-circuit on `breaker.state is OPEN` before calling — always goes through `breaker.call(...)` and catches `CircuitBreakerOpenError` instead | The plan's draft Step 2 implementation had an upfront `state is OPEN` check that `continue`d the loop. This would have prevented OPEN→HALF_OPEN recovery transitions forever, because `_before_call` is the only place where the elapsed-time check fires. With the plan's design, after a single failure trips the breaker, no subsequent call would ever recover until process restart. The corrected design routes everything through `breaker.call(...)`, and uses `CircuitBreakerOpenError` as the unified preempt-or-race signal — same fast-fail behavior on the hot path, plus correct recovery semantics. The recovery test (`test_recovery_after_timeout_probes_and_closes`) directly exercises this. | **Bug in plan, fixed during execution** |
| 2 | PEP 695 generic syntax `async def invoke_provider_chain[T](...)` instead of `T = TypeVar("T")` | Ruff `UP047` (auto-enabled in this repo) flags `TypeVar`-based generics on functions when PEP 695 syntax is available. Switched to `[T]` after the lint error. | **Style enforcement** |
| 3 | `service.py::_execute_correction_tier` uses an `if correction_loop is None: raise RuntimeError(...)` guard rather than `assert correction_loop is not None` | python-anti-patterns.md #1: no `assert` in production code (Ruff S101). The branch is unreachable in practice (caller checks `self._correction_loop is not None` first) but the explicit guard satisfies both the linter and pyright's narrowing. | **Plan anticipated; anti-pattern enforcement** |
| 4 | Closures inside the 3 per-tier helpers pass `track_provider_call(None, provider_name)` instead of `track_provider_call(tier_model, get_settings().llm_provider)` | The plan's "simpler approach" recommendation in Step 4 keeps `tier_model` constant across chain iterations and only swaps the breaker key. The chain provider name (the breaker registry key) is what we want both the breaker AND the health tracker to be keyed on for consistency, so we pass `None` as `tier_model` and the chain provider as `default_provider`. `_extract_provider_name` then returns the chain provider verbatim. | **Plan-aligned simplification** |
| 5 | `_state(breaker: CircuitBreaker) -> CircuitState` indirection helper added to `test_service.py` | Mypy literal-narrows `breaker.state` after `assert ... is CircuitState.OPEN`, then complains "Non-overlapping identity check" when later asserting `is CircuitState.CLOSED`. The helper returns `CircuitState` un-narrowed. Same pattern is already used in `test_circuit_breaker.py`. | **Pattern reuse** |

## Open Questions Carried Forward

| # | Question | Decision | Defer To |
|---|---|---|---|
| 1 (plan §Open Questions #1) | Wire all 3 LLM call sites or only the fallback `agent.run`? | **All 3** via the shared 3-helper dispatch — the breaker is authoritative for every LLM invocation. | Done |
| 2 (plan §Open Questions #2) | Breaker key when tier override specifies a different provider than `settings.llm_provider`? | **Use the settings provider** — matches AI-8.2's current extraction. Future refinement can make breakers tier-aware. | Future enhancement |
| 3 (plan §Open Questions #3) | Bypass `FallbackModel` and pass a single-provider Model to `agent.run()` per chain attempt? | **No** — per the simpler-approach recommendation in Step 4, the closures pass `tier_model` unchanged. Practical implication: with `FallbackModel(primary, fallback)` configured at the agent level, the secondary's internal cascade still runs even when our chain has skipped the primary. The fast-fail benefit primarily kicks in for single-provider tier overrides. A future PR can resolve a single-provider Model per chain attempt to make the chain authoritative end-to-end. | Future enhancement |

## Security Checklist (CTX-AGENT)

- [x] Breaker logs never include raw API keys, connection strings, or endpoints (already enforced in `circuit_breaker.py`).
- [x] `invoke_provider_chain` log fields restricted to provider name, error_type class name, and providers_tried — no raw exception `repr()`.
- [x] `AllProvidersUnavailableError.providers_tried` is logged at error level but **never** returned to HTTP clients — the service layer catches it and substitutes a static degraded response.
- [x] Degraded response is a static string (`"All LLM providers are temporarily unavailable. Please retry in 30 seconds."`) with no provider names, no error class names, no internal state.
- [x] `AllProvidersUnavailableError` mapped to HTTP 503 in the global handler, but in practice never reaches HTTP because `_execute()` swallows it.
- [x] No new endpoints, no RBAC changes — `TestAllEndpointsRequireAuth` convention test still passes (106/106).
- [x] `circuit_breaker_enabled` kill switch preserves pre-AI-8 behavior byte-for-byte — verified by `test_breaker_disabled_does_not_register_breakers` (no registry writes) and `test_breaker_disabled_propagates_original_exception` (raw `RuntimeError` still wraps as `AgentExecutionError`).

## Manual Verification Recipe (deferred — Docker not running)

The plan §Step 9 manual verification was deferred because the local environment did not have Docker up at execution time. To run it before flipping the kill switch in production:

1. `make docker` to bring up the full stack with `CIRCUIT_BREAKER_ENABLED=true` (default).
2. Set `LLM_PROVIDER=ollama` with `OLLAMA_BASE_URL=http://127.0.0.1:9` (unreachable port → 30s timeout) and `LLM_FALLBACK_PROVIDER=test`.
3. Send 5 chat requests via `curl -X POST localhost:8123/v1/chat/completions ...` — each will accumulate a failure on the `ollama` breaker.
4. Send the 6th request — should fail-fast in <100ms via the `test` provider.
5. `curl -H "Authorization: Bearer <admin-jwt>" localhost:8123/v1/chat/provider-health` — confirm the `ollama` snapshot reports `state: "open"`.
6. Set `CIRCUIT_BREAKER_ENABLED=false`, restart, repeat steps 3–4 — confirm each request still takes 30s (pre-AI-8 behavior preserved).

## Bugs Found During Implementation

| Bug | Root Cause | Fix Applied |
|---|---|---|
| Initial `invoke_provider_chain` design would trap breakers in OPEN forever | The plan's draft had an upfront `breaker.state is OPEN` skip-and-`continue`, but `OPEN→HALF_OPEN` recovery transitions only fire inside `_before_call`. Skipping the call meant `recovery_timeout_s` could elapse without any state transition. | Removed the upfront state check; always go through `breaker.call(...)` and catch `CircuitBreakerOpenError`. The `test_recovery_after_timeout_probes_and_closes` integration test directly exercises the corrected behavior. |
| `from app.core.agents.circuit_breaker import CircuitBreakerOpenError` failed mypy `attr-defined` | `circuit_breaker.py` imports `CircuitBreakerOpenError` *from* `exceptions.py` (so it's only in `exceptions.py`'s namespace), but my initial import in `llm.py` reached for it via `circuit_breaker.py`. | Updated `llm.py` to import `CircuitBreakerOpenError` from `app.core.agents.exceptions` directly. |
| `Settings(...)` constructor in `test_llm.py` failed pyright with "Argument missing for parameter `database_url`" | Pydantic-settings requires `database_url` (no default in the production schema). | Added `database_url="postgresql+asyncpg://test:test@localhost/test"` to the `_make_settings` test factory. |
| Mypy "Non-overlapping identity check" on `primary_breaker.state is CircuitState.CLOSED` after a prior `assert ... is CircuitState.OPEN` | Mypy literal-narrows `state` based on the prior assertion. | Added `_state(breaker)` indirection helper that returns `CircuitState` un-narrowed; same pattern already used in `test_circuit_breaker.py`. |
| E402 module-level imports out of order in `test_service.py` after first edit | First Edit placed the `_state` helper between two import groups, breaking the import-block invariant. | Moved the helper definition below all module-level imports. |

## Suggested Next Step

`/commit` — single conventional commit:

```
feat(agent): wire circuit breaker into provider chain with degraded fallback (AI-8.3)
```

Push deferred until manual verification (above) is run against a real environment.
