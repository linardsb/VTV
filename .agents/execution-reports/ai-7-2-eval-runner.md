# Execution Report — AI-7.2 Eval Runner + Trace Collection

**Plan:** [.agents/plans/ai-7-2-eval-runner.md](../plans/ai-7-2-eval-runner.md)
**Date:** 2026-04-11
**Status:** ✅ Complete

## Scope

Build the CLI runner that executes AI-7.1 synthetic `EvalCase` fixtures against the live per-domain agents and writes JSONL trace files to `evals/traces/`. Traces are the input artifact for the future AI-7.3 LLM judges, so schema stability and grep-friendliness were primary constraints.

## Files Created

| File | Purpose |
|---|---|
| `app/core/agents/evals/runner.py` | `EvalTrace` dataclass, `EvalRunner` class, `_coerce_tool_return`, `_collect_tool_returns`, `_trace_to_jsonl_line`, `_as_agent_name`, CLI entrypoint |
| `app/core/agents/tests/test_eval_runner.py` | 14 unit tests — helpers (3), runner happy path (7), CLI (2), sandbox (1), trace roundtrip (1) |
| `.agents/execution-reports/ai-7-2-eval-runner.md` | This report |

## Files Modified

| File | Change |
|---|---|
| `app/core/agents/base.py` | Added `chat_with_trace() -> (ChatCompletionResponse, AgentResult, tuple[ToolReturnRecord, ...])`. `chat()` delegates. Tracked `final_outcome` across the retry path so tool returns come from the winning pipeline hop. |
| `app/core/agents/tests/test_base.py` | 2 new tests asserting `chat_with_trace` contract + `chat()` shim semantics |
| `app/core/agents/evals/__init__.py` | Re-export `EvalRunner` + `EvalTrace` |
| `app/core/agents/CLAUDE.md` | One-line mention of `runner.py` in the `evals/` directory bullet + Eval framework status update |
| `docs/TODO.md` | Progress bar, AI-7.2 Status line, Completed section entry |
| `Makefile` | `eval` / `eval-all` targets |
| `.gitignore` | `evals/traces/*.jsonl` |

## Validation Results

| Check | Result | Notes |
|---|---|---|
| `ruff format app/` | PASS | 341 files unchanged |
| `ruff check app/` | PASS | |
| `mypy app/` | PASS (baseline) | 3 pre-existing errors in `static_store.py:149-150` + `pipeline.py:136`, unrelated to AI-7.2 |
| `mypy app/core/agents/evals/` | PASS | 0 errors |
| `pyright app/` | PASS (baseline) | 5 pre-existing errors, same files as above + `client.py:193` |
| `pyright app/core/agents/evals/` | PASS | 0 errors, 0 warnings |
| `pytest app/core/agents/tests/` | PASS | 302 tests (11 new runner + 2 new base) |
| `pytest -m "not integration"` | PASS* | 1396 passed, 1 pre-existing flake (`test_fetch_feed_http_error` — circuit-breaker state bleed, verified identical on `git stash`) |
| `ruff check app/ --select=S` | PASS | Security lint clean |
| `pytest app/tests/test_security.py` | PASS | 106/106 |

## Divergences from Plan

| Planned | Actual | Reason |
|---|---|---|
| `chat_with_trace` returns 2-tuple `(response, AgentResult)` | Returns 3-tuple `(response, AgentResult, tuple[ToolReturnRecord, ...])` | Plan Step 4 identified that `AgentResult` does not carry message history, so tool returns must be extracted in `chat_with_trace` before the outcome is discarded. The 3-tuple "Option A" was explicitly chosen in the plan itself — this is not a last-minute deviation, it was the plan's refined signature. |
| 11 numbered runner tests per plan | 14 tests total (includes 3 helper unit tests for `_coerce_tool_return` / `_collect_tool_returns` / `_trace_to_jsonl_line`) | Helper functions deserve direct coverage; plan folded them into the larger integration tests. Non-JSON-serializable payload test from the plan list was dropped because `json.dumps(..., default=str)` makes the coercion fallback unreachable — the roundtrip test covers the same contract. |
| Symlink-based sandbox escape test | `../escape/x` suite-name path traversal | Symlink escape setup was unnecessarily complex. Passing a `..`-containing suite name to `_write_traces` directly exercises `is_relative_to()` with a simpler shape. |

## Bugs Found During Implementation

| Bug | Root Cause | Fix Applied |
|---|---|---|
| mypy `[unused-ignore]` on `chat_with_trace  # type: ignore[override]` in the test fake agent | The test double overrides `chat_with_trace` with the exact same signature as the base class, so `[override]` was not needed. Anti-pattern #14/#32: never guess ignore codes. | Removed the comment. Test file still pyright-clean. |
| Redundant `from app.core.agents.agent_result import AgentResult` import in `runner.py` (F401) | Early draft imported `AgentResult` for type marker use, then removed the usage but left the import. | Removed the import; `AgentResult` flows through from `BaseAgentService.chat_with_trace` at runtime without a direct import. |
| Test file used relative `from .conftest import make_eval_case` | Drift from peer test files' absolute-import style (`from app.core.agents.tests.conftest import ...`) | Changed to absolute import to match `test_eval_loader.py` convention. |
| `_CaseExecution` dataclass + `field(default_factory=list)` inside `__init__` | Leftover scaffolding from an earlier draft where `_SuiteSummary` was going to be instance state. `field()` only works inside dataclass bodies, not inside `__init__`. | Removed the unused dataclass. Used plain `self._summaries: list[_SuiteSummary] = []` assignment. |

## What Went Well

- Plan's preflight warnings (tuple unpacking fragility, `ToolReturnRecord` import, `extract_tool_returns` already exported) were all accurate and saved time.
- `_FakeBudgetAgent` test pattern from `test_agent_result.py` transplanted cleanly to `_FakeEvalAgent`.
- Fail-open philosophy made the per-case exception path trivially testable (one `_FakeEvalAgent(raise_exc=RuntimeError(...))` covers all infra failures).
- `chat_with_trace` refactor with retry-path-aware `final_outcome` tracking turned out to be a 3-line diff once the approach was clear — no behavior change for existing HTTP callers.

## Challenges

- The plan's initial `chat_with_trace` signature (2-tuple) would not have carried tool return records, which are in `_PipelineOutcome.messages`, not `AgentResult`. Caught during planning via "Option A vs B" refinement.
- mypy `[unused-ignore]` is only raised on full-directory runs, not per-file runs — `uv run mypy app/core/agents/evals/runner.py` passed but `uv run mypy app/` flagged the test-file comment. Catch came from the Phase 1 validation in `/be-ship`, not from Step 4 of `/be-execute`.

## Out of Scope (per plan, deferred to AI-7.3+)

- LLM judges / binary pass-fail scoring per case
- Regression baselines + CI gating
- Any changes to `AgentResult` public surface
- Fixing pre-existing pyright/mypy errors in `tools/transit/client.py`, `tools/transit/static_store.py`, `pipeline.py`

## Next Steps

- `/commit` the AI-7.2 changes
- Begin AI-7.3 LLM judge planning — traces emitted by this runner are the direct input artifact
