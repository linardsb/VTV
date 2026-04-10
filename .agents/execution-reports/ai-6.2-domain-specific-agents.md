# Execution Report: AI-6.2 Domain-Specific Agents

**Plan:** [.agents/plans/ai-6.2-domain-specific-agents.md](../plans/ai-6.2-domain-specific-agents.md)
**Implemented:** 2026-04-10
**Status:** Done — ready to commit

## Summary

Three `BaseAgentService` subclasses added under `app/core/agents/agents/` with a per-request `agent` selector on `ChatCompletionRequest`. The existing `AgentService` is preserved as the `unified` fallback so default behavior is bit-identical to pre-AI-6.2. 48 new tests green. No migrations.

## Files

**Created (8):**
- `app/core/agents/agents/__init__.py` — package marker
- `app/core/agents/agents/transit.py` — `TransitAgent` + `transit_agent` singleton + `TRANSIT_SYSTEM_PROMPT`
- `app/core/agents/agents/knowledge.py` — `KnowledgeAgent` + `knowledge_agent` singleton + `KNOWLEDGE_SYSTEM_PROMPT`
- `app/core/agents/agents/vault.py` — `VaultAgent` + `vault_agent` singleton + `VAULT_SYSTEM_PROMPT`
- `app/core/agents/agents/registry.py` — `get_agent_by_name()` + `close_all_agents()`
- `app/core/agents/tests/test_transit_agent.py` — 16 tests
- `app/core/agents/tests/test_knowledge_agent.py` — 15 tests
- `app/core/agents/tests/test_vault_agent.py` — 15 tests

**Modified (5):**
- `app/core/agents/schemas.py` — added `AgentName = Literal[...]` + `agent: AgentName = "unified"` on `ChatCompletionRequest`
- `app/core/agents/routes.py` — resolves service via `get_agent_by_name(body.agent)`, logs `agent.chat.selected`
- `app/core/agents/tests/test_routes.py` — 3 selector regression tests + `_bypass_quota_tracker` autouse fixture
- `app/main.py` — imports and calls `close_all_agents()` after `close_agent_service()` in lifespan shutdown
- `app/core/agents/CLAUDE.md` — marked AI-6.2 done in Planned Improvements

## Validation Results

| Check | Result | Notes |
|---|---|---|
| `ruff format` | pass | 325 files unchanged |
| `ruff check` | pass | 0 errors |
| `ruff check --select=S` (Bandit) | pass | 0 errors |
| `mypy app/` | 3 errors (baseline) | Pre-existing in `pipeline.py:136`, `static_store.py:149-150` — unchanged |
| `pyright app/` | 5 errors (baseline) | Pre-existing in `pipeline.py:47,49,136(×2)`, `tools/transit/client.py:193` — unchanged |
| `pytest -m "not integration"` | **1288 passed** | +48 from AI-6.2 |
| `pytest app/core/agents/` | **388 passed** | 340 baseline + 48 new |
| `pytest app/tests/test_security.py` | **106 passed** | All endpoints still require auth |
| Integration tests | skipped | Docker not running (same as task start) |

## What Went Well

- The `BaseAgentService` hook-point contract from AI-6.1 held up. Each subclass only overrides what it specifically needs (`_execute`, `_apply_rag_routing`, `_recall_memories_block`, `build_system_prompt`, `_run_qa`, optionally `_preload_validation_cache`). The base pipeline handled prompt injection, tier classification, logging, and exception wrapping identically across all four agents with zero changes.
- The plan's "mirror `service.py` structure verbatim" directive for `TransitAgent` paid off immediately — the test harness pattern from `test_service.py` transplanted 1:1.
- Pydantic `Literal` validation gave us CTX-INPUT security for free: a POST with `"agent": "bogus"` returns 422 before the request ever reaches the service layer. Verified by `test_chat_completions_unknown_agent_returns_422`.
- The per-agent `agent_name` tag (`transit_agent_v2`, `knowledge_agent`, `vault_agent`) kept memory-store lanes clean; `AgentService` still writes with `"transit_agent"` so the unified fallback's episodic memory doesn't get contaminated by the v2 subclass.

## Challenges

| Challenge | Resolution |
|---|---|
| Full `chat()` pipeline tests for `TransitAgent` were accidentally hitting a real Jina embedding API + Postgres via the memory-recall hook (default `memory_enabled=True` from cached settings). | Added `get_settings` patches to every test that drives `chat()` so `memory_enabled=False` + `agent_self_correction_enabled=False` + test LLM metadata are in scope. |
| `caplog` didn't capture `structlog`-routed events, so `test_chat_logs_chat_started_and_completed` couldn't assert on message text. | Switched to patching `app.core.agents.base.logger` and asserting on `mock_logger.info.call_args_list` event names — matches the pattern used in `test_service.py`. |
| mypy flagged `svc._deps.transit_http_client.aclose = AsyncMock(...)` with `method-assign` because `AsyncMock(spec=httpx.AsyncClient)` exposes typed methods. | Replaced the full http client with a fresh `AsyncMock()` pre-configured with `aclose.side_effect = RuntimeError("closed")` and assigned to the dataclass field instead of monkey-patching the method. |
| Pyright flagged `get_agent_service`/`AgentService` as unused after removing the `Depends(get_agent_service)` injection. The plan said to keep them for legacy test patching, but `grep` confirmed nothing patches them via the `routes` namespace. | Dropped both imports from `routes.py` rather than adding ignore comments — cleaner than a `# noqa`. Documented as a deviation from the plan below. |

## Divergences from Plan

| Plan Item | Actual | Reason |
|---|---|---|
| Step 7 said "Keep the existing `from app.core.agents.service import AgentService, get_agent_service` import — the metrics endpoint still references types from there, and existing tests may patch it." | Dropped both imports. | `grep` for `routes.AgentService` / `routes.get_agent_service` across the codebase found zero patch sites. The metrics endpoint uses `get_metrics_tracker`, not the agent service singleton. Keeping unused imports would require a `# noqa: F401` or `# pyright: ignore` — neither is warranted when the symbols are genuinely unused. |
| Step 9 said "15 tests" for `test_transit_agent.py`. | 16 tests. | Added a supplementary `test_chat_rag_routing_disables_rag_unconditionally` that drives the full `chat()` pipeline to verify the RAG flag flip survives end-to-end (not just the unit-level `_apply_rag_routing` hook). Cheap coverage win. |
| `_close_swallows_runtime_error_on_closed_loop` plan implied monkey-patching `.aclose` on the spec'd client. | Replaces the whole client with a fresh `AsyncMock` whose `aclose` is pre-configured. | mypy `method-assign` error on the spec'd client — the anti-pattern catalog warns against this pattern. |

## Bugs Found During Implementation

| Bug | Root Cause | Fix Applied |
|---|---|---|
| `test_routes.py::test_chat_completions_default_agent_is_unified` failed pyright with `reportArgumentType` on a dict-literal in `_fake_chat_response()`. | I had constructed the `ChatCompletionResponse.choices` list as `list[dict]`, but the field is typed `list[ChatCompletionChoice]`. Pydantic would coerce at runtime but pyright flags the call-site type mismatch. | Imported `ChatCompletionChoice` + `ChatMessage` and built the response with real Pydantic instances instead of dict literals. |
| `test_routes.py` tests that hit `/v1/chat/completions` were cascading 429s on the second full-suite run — `test_chat_completions_endpoint`, `test_chat_completions_returns_assistant_message`, and my two new selector regressions all hit quota exceeded with `current_count=57`. | The quota tracker's singleton in `app/core/agents/quota.py` falls back to an in-memory counter per-process, but the local dev environment has an SSH tunnel to a real Redis on `:6379`, so the Redis-backed path was persistent across pytest invocations. The 50-query daily budget leaked across CI runs and finally overflowed. This was a **latent** bug that existed before AI-6.2 — it only surfaced today because repeated validation runs crossed the threshold. | Added an `_bypass_quota_tracker` autouse fixture to `test_routes.py` that patches `app.core.agents.routes.get_quota_tracker` to return a stub whose `check_and_increment` always returns `True`. This fixes both my new tests AND the pre-existing ones that were about to break in CI. |

## Acceptance Criteria

- [x] `make lint` clean
- [x] `make types` ≤ baseline (pyright 5, mypy 3, all pre-existing)
- [x] `uv run pytest app/core/agents/` — 388 tests pass (340 baseline + 48 new)
- [x] `uv run pytest app/tests/test_security.py` — 106 passed
- [x] `ruff check --select=S` clean (Bandit)
- [x] `agent_router` registered exactly once in `app/main.py`
- [x] Both `close_agent_service()` AND `close_all_agents()` fire on shutdown
- [x] Domain agents do NOT receive `manage_agent_skills` (CTX-AGENT)
- [x] `agent` selector typed `Literal[...]` — 422 fires before service dispatch (CTX-INPUT)
- [x] `get_current_user` + `@limiter.limit("10/minute")` + daily quota preserved on `/v1/chat/completions` (CTX-RBAC)
- [x] `VaultAgent` system prompt requires user confirmation before destructive ops (CTX-AGENT)
- [ ] Manual smoke: `curl -X POST .../v1/chat/completions -d '{"messages":[...], "agent":"transit"}'` → 200 — **deferred, requires running server**
- [ ] Memory store contains episodes tagged `transit_agent_v2`, `knowledge_agent`, `vault_agent` after smoke tests — **deferred, requires running server**

## Follow-ups

- **AI-6.2.1** — Extract `_recall_memories_block` + skills loader to `app/core/agents/hooks_shared.py`. The three-feature rule threshold is now reached (4 copies across `AgentService` + `TransitAgent` + `KnowledgeAgent` + `VaultAgent`). Each duplicate carries `# NOTE: duplicated from AgentService; extract on AI-6.2.1`.
- **AI-6.3** — Auto-routing. Today the selector is explicit; AI-6.3 will use keyword signals (like the existing tier classifier) to default to the right domain agent without client configuration, with `unified` as the fallback for cross-domain queries.
- **Pre-existing flake** — `app/core/agents/tools/transit/tests/test_client.py::test_fetch_feed_http_error` is a test-ordering-dependent failure that passes in isolation and also fails without any AI-6.2 files present. Not blocking AI-6.2 but should be tracked separately.
