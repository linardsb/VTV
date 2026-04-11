# Execution Report — AI-8.2 Per-Provider Health Metrics + Admin Endpoint

**Plan:** `.agents/plans/ai-8.2-provider-health-metrics.md`
**Date:** 2026-04-11
**Status:** ✅ Shipped — ready to commit

## Files Changed

| Action | File | Notes |
|---|---|---|
| CREATE | `app/core/agents/provider_health.py` | `ProviderHealth` dataclass + `ProviderHealthTracker` singleton + `track_provider_call()` async context manager + `_extract_provider_name()` helper. Lazy 00:00 UTC daily reset mirrors `metrics.py` (AI-5.3). |
| CREATE | `app/core/agents/tests/test_provider_health.py` | 19 unit tests: tracker primitives (9), provider name extraction (4), singleton lifecycle (2), endpoint 200/403 + state field (4). |
| UPDATE | `app/core/agents/schemas.py` | Added `ProviderHealthSnapshot` + `ProviderHealthResponse` Pydantic models with `ConfigDict(strict=True)`. |
| UPDATE | `app/core/agents/routes.py` | Added admin-only `GET /v1/chat/provider-health` (`require_role("admin")`, `60/minute`) returning deep-copied sorted snapshots. |
| UPDATE | `app/core/agents/service.py` | Wrapped the 3 LLM call sites (complex pipeline, correction loop, fallback `agent.run`) in `async with track_provider_call(tier_model, get_settings().llm_provider)`. |
| UPDATE | `app/core/agents/CLAUDE.md` | New `provider_health.py` entry in directory tree; AI-8.2 bullet added to "Provider resilience" point 7; tests line updated. |
| UPDATE | `docs/TODO.md` | AI-8.2 marked ✅ with shipped details; Agent Intelligence progress bar bumped 86% → 88%. |

## Validation Results

| Check | Result | Delta vs Baseline |
|---|---|---|
| `ruff format .` | ✅ clean | — |
| `ruff check app/core/agents/` (AI-8.2 files) | ✅ clean | — |
| `ruff check --select=S app/` | ✅ clean | — |
| `mypy app/` | 3 errors | unchanged baseline (`static_store.py:149,150` + `pipeline.py:136`) |
| `pyright app/` | 5 errors | unchanged baseline (`pipeline.py` x3 + `tools/transit/client.py`) |
| `pyright` on new files | 0 / 0 / 0 | clean |
| `pytest app/core/agents/tests/` | 375 passed | baseline 356 + 19 new |
| `pytest -m "not integration"` | 1469 passed, 1 flake | `test_fetch_feed_http_error` flake **confirmed pre-existing on clean main** (1 failed, 1450 passed with AI-8.2 stashed); caused by `_feed_breaker` module-level singleton contamination in `app/core/resilience.py`, unrelated to AI-8.2 |
| `pytest app/tests/test_security.py` | 106 passed | `TestAllEndpointsRequireAuth` auto-detected the new admin endpoint |
| Integration / SDK sync / server | SKIPPED | Docker not running |

## Divergences from Plan

| # | Divergence | Why | Classification |
|---|---|---|---|
| 1 | Rate limit set to `60/minute` (matches `/v1/models` + other health endpoints) instead of plan's `30/minute` hint in TODO.md | Plan file (`.agents/plans/ai-8.2-provider-health-metrics.md`) explicitly specifies `60/minute` to match `/v1/models`; TODO.md predates the plan and was stale. | **Plan staleness in TODO.md, not the plan itself** |
| 2 | Test `test_p50_p95_quantile_correctness` uses `range(1, 101)` with `±1.0` tolerance instead of exact asserts | `statistics.quantiles(method="inclusive")` interpolates linearly, so exact integer asserts on a 1..100 ramp are not guaranteed across Python versions. Plan warned about this in the preflight section. | **Plan anticipated** |
| 3 | `deque` type hint uses `deque[float](maxlen=_LATENCY_WINDOW)` constructor (typed lambda factory) | python-anti-patterns.md #24 mandates typed lambda factory for `field(default_factory=...)` to satisfy pyright invariance. | **Plan anticipated** |
| 4 | `_execute()` wiring to a per-provider `BreakerRegistry` deferred to AI-8.3 follow-up | Plan explicitly says this is out of scope — tracker's `state` field always reports `"closed"` until the registry lands. Documented in `_extract_provider_name` docstring + CLAUDE.md + TODO.md. | **Planned scope** |

No divergences represent ignored plan constraints. All are either anticipated by the plan or stale references in older docs.

## Bugs Found During Implementation

None. The plan's reference pattern (`app/core/agents/metrics.py`) was close enough that the tracker landed clean on first pass. The `track_provider_call` async context manager was added on the advisor's recommendation to avoid triplicating the try/except block across 3 service.py call sites.

## Security Checklist (CTX-AGENT + CTX-RBAC)

- [x] `Depends(require_role("admin"))` on `GET /v1/chat/provider-health` — not bare `get_current_user`
- [x] `@limiter.limit("60/minute")` — matches `/v1/models` and other health endpoints
- [x] No query/path parameters — no input validation surface
- [x] Response uses typed Pydantic `ProviderHealthResponse` — no `Any`, no raw dict leakage
- [x] No credentials / API keys / connection strings in response body or log fields
- [x] No raw exception `repr()` in response body — fail-open logs only `agent.provider_health.record_failed` with `exc_info=True` (goes to GlitchTip/stdlib, not the HTTP response)
- [x] `TestAllEndpointsRequireAuth` in `app/tests/test_security.py` auto-discovered and enforced `require_role` — 106/106 green
- [x] Admin-200 test (`test_provider_health_endpoint_returns_recorded_providers`) and dispatcher-403 test (`test_provider_health_endpoint_rejects_non_admin`) both included
- [x] `_latencies_ms` private field is not exposed in `ProviderHealthSnapshot` — only the p50/p95 summary statistics
- [x] `get_all()` deep-copies via fresh `ProviderHealth` construction + new `deque(...)` — callers cannot mutate tracker state
- [x] `record_call` failures wrapped in `try/except Exception` with `# noqa: BLE001` and inline comment — fail-open so instrumentation never blocks LLM results
- [x] No `verify=False`, no new network calls, no file I/O

## Out of Scope (AI-8.3 Follow-up)

The tracker + `track_provider_call` wrapper + admin endpoint ship in this PR. The actual per-provider `CircuitBreaker` registry keyed by provider name (wired into `_execute()` via the `circuit_breaker_enabled` kill switch) is deferred to AI-8.3 so it can be reviewed and rolled out independently. Until then:

- `ProviderHealth.state` always reports `CircuitState.CLOSED`
- `track_provider_call` records outcomes but never short-circuits a call
- Ops readers of `GET /v1/chat/provider-health` get accurate latency + success/failure counts, but the `state` column is a placeholder

A `TODO(AI-8.2-followup)` comment in `_extract_provider_name` points at the follow-up so the next agent knows where to wire the registry.
