# Execution Report — AI-8.1 Circuit Breaker State Machine

**Plan:** `.agents/plans/ai-8.1-circuit-breaker.md`
**Date:** 2026-04-11
**Status:** ✅ Shipped — ready to commit

## Files Changed

| Action | File | Notes |
|---|---|---|
| CREATE | `app/core/agents/circuit_breaker.py` | 3-state async breaker (CLOSED/OPEN/HALF_OPEN), `BreakerConfig`, `CircuitBreaker.call()`, `asyncio.Lock` never held across `fn` await |
| CREATE | `app/core/agents/tests/test_circuit_breaker.py` | 19 unit tests: transitions + concurrency + invariants + structlog assertion + full spec scenario |
| UPDATE | `app/core/agents/exceptions.py` | `CircuitBreakerOpenError(AgentError)` + 503 mapping + `setup_agent_exception_handlers` registration |
| UPDATE | `app/core/config.py` | 5 new `circuit_breaker_*` pydantic-settings fields (env-var-backed) |
| UPDATE | `app/core/agents/tests/conftest.py` | `ManualClock`, `make_breaker_config`, `make_breaker` factories |
| UPDATE | `docs/logging-standard.md` | 7 new `agent.circuit_breaker.*` event rows in agent taxonomy |
| UPDATE | `docs/TODO.md` | AI-8.1 marked `✅ Done` with status line; Agent Intelligence progress bar bumped 85% → 86% |
| UPDATE | `app/core/agents/CLAUDE.md` | `circuit_breaker.py` added to directory structure; "Provider resilience" bullet added to Planned Improvements; agent test count 256 → 356 |

## Validation Results

| Check | Result | Delta vs Baseline |
|---|---|---|
| `ruff format app/` | ✅ clean | — |
| `ruff check app/` | ✅ clean | — |
| `ruff check --select=S app/` | ✅ clean | — |
| `mypy app/` | 3 errors | unchanged baseline (all in `static_store.py` + `pipeline.py`, unrelated) |
| `pyright app/core/agents/` | 5 errors | unchanged baseline (all in `pipeline.py` + `tools/transit/client.py` + `tools/transit/static_store.py`, unrelated) |
| `pyright` on new files | 0 / 0 / 0 | clean |
| `pytest app/core/agents/tests/` | 356 passed | baseline 337 + 19 new |
| `pytest -m "not integration"` | 1450 passed, 1 flake | `test_fetch_feed_http_error` flake is **pre-existing** state pollution in `_feed_breaker` module-level singleton in `app/core/agents/tools/transit/client.py`; reproduced with `--ignore=app/core/agents/tests/test_circuit_breaker.py` — unrelated to AI-8.1 |
| `pytest app/tests/test_security.py` | 106 passed | all security convention tests green |
| Integration / SDK sync / server | SKIPPED | Docker not running |

## Divergences from Plan

| # | Divergence | Why | Classification |
|---|---|---|---|
| 1 | `test_concurrent_calls_share_state_atomically` rewritten as two-phase (sequential trip → concurrent fast-fail) | Plan's original 10-way concurrent-fail design had a race: all 10 tasks pass `_before_call` with state=CLOSED before any records a failure (fn awaits yield the event loop between each task's state check and its failure record), so no call ever sees OPEN. Two-phase test still exercises the atomicity claim. | **Plan gap** — fixed in test |
| 2 | `test_log_events_emitted` switched from `caplog` to `structlog.testing.capture_logs` | This repo's structlog pipeline isn't routed through stdlib logging, so `caplog.records` is always empty for agent logs. `capture_logs` returns structured event dicts — stronger assertion than string-contains. | **Plan gap** — better pattern |
| 3 | Added private `_state(breaker) -> CircuitState` helper in test file | mypy narrows `breaker.state is CircuitState.X` across an entire function scope when `state` is a `@property` (literal narrowing). Multi-transition tests broke. The helper returns a fresh value mypy can't narrow across calls. Plan was silent; no production change. | **Plan gap** — type-check workaround |
| 4 | `make_breaker_config(**overrides: Any)` instead of plan's `**overrides: object` + `# type: ignore[arg-type]` | Matches the existing `make_agent_result` / `make_skill_meta` factory convention in the same `conftest.py`. Cleaner + consistent. | **Better approach** |
| 5 | 5 new config settings placed after `eval_baseline_tolerance_pct` (not after line 293) | AI-7.3/7.4 landed in between; line 293 no longer holds `agent_confidence_reroute_threshold`. Placed at end of agent block before `@model_validator`. | **Plan staleness** |
| 6 | Documented 7 log events in `logging-standard.md` (plan said 6) | Plan's prose listed 6 but the code actually emits `probe_success` + `probe_failure` as distinct events. Documented both so the taxonomy matches reality. | **Plan gap** — now consistent |

All divergences are justified (better approach, plan staleness, or type-check workaround). None ignore plan constraints.

## Bugs Found During Implementation

| Bug | Root Cause | Fix Applied |
|---|---|---|
| Concurrent-fail test hung with zero `CircuitBreakerOpenError` rejections | Plan's test launched 10 concurrent failing calls via `asyncio.gather`. Every task passed `_before_call` observing state=CLOSED before any task's `fn` completed + recorded its failure, so the trip happened *after* all 10 had already entered the provider call. | Re-designed as a two-phase test: (1) 3 sequential failures trip the breaker, (2) 10 concurrent calls after-trip must *all* fast-fail with `CircuitBreakerOpenError`. Preserves the atomicity claim. |
| `test_log_events_emitted` asserted on an empty `caplog.records` | structlog events aren't routed through stdlib `logging` in this repo, so `caplog` never sees them. | Switched to `structlog.testing.capture_logs` context manager and assert directly on the structured event dict (`event`, `provider`, `trigger` fields). |
| mypy non-overlapping-identity errors on multi-transition asserts | mypy narrows `breaker.state is CircuitState.X` to `Literal[CircuitState.X]` for the *entire* remainder of the function (property narrowing), so the second `assert breaker.state is CircuitState.HALF_OPEN` after a prior `assert ... is CircuitState.OPEN` fails comparison-overlap. | Introduced private `_state(breaker) -> CircuitState` helper; function-call return values aren't narrowed across subsequent calls. |
| Unused `# type: ignore[attr-defined]` on `breaker._failure_rate()` | `_failure_rate` exists as a regular method — no attribute error to suppress. | Removed the suppression. |

## Security Checklist (CTX-AGENT + CTX-INFRA)

- [x] No provider credentials in log fields — only `provider` (name string), `state`, counters, `elapsed_s`, `trigger`
- [x] `CircuitBreakerOpenError` messages are generic — no upstream exception `repr()` leaked to HTTP response
- [x] Kill switch: `circuit_breaker_enabled=False` disables the feature via env var, no redeploy needed (wiring honours this when AI-8.2 lands)
- [x] New settings are pydantic-settings (env-var-backed) — no hardcoded secrets
- [x] No new endpoints, no RBAC surface — `app/tests/test_security.py` unaffected (still 106/106 green)
- [x] No `except: pass`, no `# type: ignore` / `# noqa` in production code

## Out of Scope (AI-8.2 Follow-up)

The breaker primitive + config + exception + tests landed here. The actual wiring into `AgentService._execute()` around each `agent.run()` call, plus the per-provider registry keyed by `llm_primary_provider` / `llm_fallback_provider`, is intentionally deferred to AI-8.2 so it can be reviewed + gated by the kill switch independently.
