# Execution Report: AI-6.3 Agent Router (Heuristic Domain Auto-Selection)

**Plan:** [.agents/plans/ai-6.3-agent-router.md](../plans/ai-6.3-agent-router.md)
**Date:** 2026-04-10
**Status:** ✅ Shipped

## Summary

Added a server-side heuristic router (`app/core/agents/router.py`) that scores incoming prompts against transit/knowledge/vault keyword signal sets and auto-upgrades `agent="unified"` requests to a domain-specific agent. Wired into `chat_completions` behind a default-off `AGENT_MULTI_AGENT_ENABLED` config flag for safe rollout.

## Files Changed

| Action | File | Purpose |
|---|---|---|
| CREATE | `app/core/agents/router.py` | `AgentRouter` class, `RoutingDecision` NamedTuple, regex signal sets, `get_agent_router()` singleton |
| CREATE | `app/core/agents/tests/test_router.py` | 24 unit tests across 6 test classes |
| UPDATE | `app/core/config.py` | Added `agent_multi_agent_enabled: bool = False` flag |
| UPDATE | `app/core/agents/routes.py` | Wired router into `chat_completions`; expanded `agent.chat.selected` log with `requested_agent` + `auto_routed` |
| UPDATE | `app/core/agents/tests/test_routes.py` | Added `TestChatCompletionsAutoRouting` class with 3 endpoint integration tests |

## Validation Results

| Check | Result |
|---|---|
| `ruff format .` | PASS |
| `ruff check .` | PASS |
| `mypy app/` | 3 baseline errors (pre-existing in `pipeline.py`/`static_store.py`); zero new |
| `pyright app/` | 5 baseline errors (pre-existing in `pipeline.py`/`tools/transit/client.py`); zero new |
| `pytest -m "not integration"` | 1315 passed; 1 pre-existing flaky `test_fetch_feed_http_error` (passes in isolation, unrelated to AI-6.3) |
| `ruff check --select=S` (security lint) | PASS |
| `pytest app/tests/test_security.py` | 106 / 106 PASS |
| `pytest app/core/agents/tests/test_router.py` | 24 / 24 PASS in 0.08s |
| `pytest app/core/agents/tests/test_routes.py::TestChatCompletionsAutoRouting` | 3 / 3 PASS |

## Pattern Compliance

- ✅ Type Safety — full annotations, zero `Any`, zero `# type: ignore`
- ✅ Structured Logging — `agent.router.decision` follows `domain.component.action_state`
- ✅ Anti-pattern #44 — never logs raw prompt; uses 12-char SHA-256 prefix `prompt_hash`
- ✅ Anti-pattern #54 — reuses existing `AgentName` Literal alias instead of new enum
- ✅ Reuses fragile-pattern guidance from plan: `MagicMock(spec=BaseAgentService)`, `get_settings.cache_clear()` in try/finally to prevent env-var leakage between tests
- ✅ Default-off feature flag for safe rollout

## Divergences from Plan

| Planned | Actual | Reason |
|---|---|---|
| `winners = [name for name, score in scores.items() if score == top_score]` | Added explicit `winners: list[AgentName]` annotation | Pyright widens dict iteration key types; explicit annotation satisfies type checker without `cast()` |

Single-line type-hint addition; behavior is identical.

## Bugs Found During Implementation

None. The plan was followed exactly.

## What Went Well

- Plan's "Fragile patterns to avoid" section accurately predicted the issues to watch for (`MagicMock(spec=...)`, `get_settings.cache_clear()` leakage, security-test grep on `_get_client_ip`).
- Anti-pattern #44 (`prompt_hash` instead of raw prompt) was followed on first pass — sentinel-leak test confirms no prompt content escapes via logs.
- Type-check baseline preserved exactly: 5 pyright + 3 mypy errors, all pre-existing in unrelated files.
- All 27 new tests passed on first run after a single one-line pyright fix.

## Challenges

- One pre-existing flaky test (`tools/transit/tests/test_client.py::test_fetch_feed_http_error`) failed under full-suite ordering but passed in isolation — unrelated to AI-6.3, recommend separate cleanup ticket.

## Next Steps

- Run `/commit` to save the implementation.
- After rollout, monitor `agent.router.decision` log events to gather data for tuning the keyword signal sets.
- Foundation laid for AI-6.4 (L3 progressive skills) and AI-6.5 (`AgentResult` protocol).
