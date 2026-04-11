# Execution Report: AI-7.3 LLM Judge + AI-7.4 Regression Baselines

**Plan:** [.agents/plans/ai-7.3-7.4-judge-regression.md](../plans/ai-7.3-7.4-judge-regression.md)
**Date:** 2026-04-11
**Status:** Implemented + validated, pending commit

## Summary

Both modules built per the plan with the schemas, CLI surface, and security
posture (path sandboxing, fail-open per case, no raw prompt logging,
`<<<BEGIN>>>`/`<<<END>>>` delimiters) intact. 35 new unit tests pass (15 judge
+ 20 regression). Wider agent-module pyright/mypy baselines preserved
(5 pre-existing pyright errors in `pipeline.py` + `tools/transit/client.py`,
3 pre-existing mypy errors in `pipeline.py` + `tools/transit/static_store.py`).
1431 unit tests + 106 security tests green.

## Files Created

| Path | Purpose |
|------|---------|
| `app/core/agents/evals/judge.py` | `LLMJudge` class, prompt builder, JSONL writer, CLI |
| `app/core/agents/evals/regression.py` | `generate_baseline` + `check_regression`, JSON I/O, two-subcommand CLI |
| `app/core/agents/tests/test_eval_judge.py` | 15 unit tests |
| `app/core/agents/tests/test_eval_regression.py` | 20 unit tests |

## Files Modified

| Path | Change |
|------|--------|
| `app/core/agents/evals/schemas.py` | +6 frozen dataclasses (`JudgeVerdict`, `SuiteJudgement`, `CriterionBaseline`, `BaselineReport`, `RegressionFinding`, `RegressionReport`) with `__post_init__` validation |
| `app/core/agents/evals/__init__.py` | Re-export new public symbols |
| `app/core/config.py` | `eval_judge_enabled: bool = True`, `eval_baseline_tolerance_pct: float = 3.0` |
| `Makefile` | `eval-judge`, `eval-baseline`, `eval-check` targets |
| `.gitignore` | Ignore `evals/verdicts/`; carve-out comment to keep `evals/baselines/` committed |
| `app/core/agents/CLAUDE.md` | Extended evals bullet with AI-7.3/7.4 status |

## Validation Results

| Gate | Result |
|------|--------|
| `ruff format .` | Clean |
| `ruff check --fix .` | Clean |
| `mypy app/` | 3 errors — all pre-existing baseline (`pipeline.py:136`, `tools/transit/static_store.py:149-150`) |
| `pyright app/` | 5 errors — all pre-existing baseline (`pipeline.py:47/49/136`, `tools/transit/client.py:193`) |
| `pyright app/core/agents/evals/` | 0 errors |
| `pytest -m "not integration"` | 1431 passed (1 known-flaky pre-existing test in `tools/transit/test_client.py::test_fetch_feed_http_error` — passes in isolation, unrelated to AI-7.3/7.4) |
| `pytest test_eval_judge.py + test_eval_regression.py` | 35 passed |
| `pytest app/core/agents/tests/` | 337 passed |
| `ruff check --select=S` (Bandit) | Clean |
| `pytest app/tests/test_security.py` | 106 passed |
| `make -n eval-judge eval-baseline eval-check` | All targets parse |

## Divergences from Plan

| # | Plan said | Actual | Reason |
|---|-----------|--------|--------|
| 1 | `# pyright: reportUnknownMemberType=false` at top of `judge.py` (mirroring `runner.py:17`) | Extended to also include `reportUnknownVariableType` and `reportUnknownArgumentType` at file level | `json.loads()` returns `Any` and the unknown types propagate through `trace.get(...)` calls in `_build_user_prompt`. Matches the existing pattern in `loader.py:16`, which uses the identical 3-suppression set for the same JSON-parsing reason. No inline `# type: ignore` comments — file-level directives are the project convention for untyped boundary code (anti-pattern #14). |
| 2 | Same file-level pyright suppression on `regression.py` (plan implied only the standard `reportUnknownMemberType=false`) | Same 3-suppression block as `judge.py` (`reportUnknownMemberType`, `reportUnknownVariableType`, `reportUnknownArgumentType`) | `_baseline_from_json()` parses `dict[str, Any]` from `json.load()` and the unknown types propagate through `entry.get(...)` calls. Same justification as #1 — matches `loader.py` precedent. |
| 3 | Plan listed transit/knowledge/vault criteria names in the AI-7.3 implementation section | `judge.py` is criteria-agnostic — it grades whatever 5 `QualityCriterion` entries each `EvalCase` carries (loaded from YAML by AI-7.1) | Hardcoding criteria names in the judge would have created two sources of truth. The YAML cases own the criterion catalog; the judge consumes whatever is there. This stays consistent with the AI-7.1 design where `EvalCase.quality_criteria` is the canonical schema. |

## Bugs Found During Implementation

| Bug | Root Cause | Fix Applied |
|-----|------------|-------------|
| Initial `judge.py` failed pyright with 4 `reportUnknownArgumentType` errors on `tools_used` / `tool_returns` extracted from JSON-decoded trace dicts | `dict[str, Any].get()` returns `Any`, but isinstance narrowing on a `list \| tuple` yields `list[Unknown]` / `tuple[Unknown, ...]` under pyright strict mode | Replaced inline `# pyright: ignore[...]` (which would have violated the project's "no inline ignores" rule) with the file-level 3-suppression block matching `loader.py:16`. Documented as Divergence #1 above. |
| `test_eval_judge.py::test_cli_returns_exit_code_1_on_failure` failed pyright `reportUnknownArgumentType` on `monkeypatch.setattr(..., lambda _suite: ...)` | Anonymous lambda passed to `setattr` had inferred-`Unknown` parameter; pyright cannot narrow lambda arg types from `setattr`'s string-key form | Replaced lambda with a named inner `def _fake_cases_by_id(_suite: str) -> dict[str, EvalCase]:`. Added explicit annotation, fixed in one edit. |
| `test_eval_regression.py` had 10 pyright `reportUnknownMemberType` errors on `pytest.approx(...)` calls | `pytest.approx`'s return type is generic and pyright resolves it as partially unknown | Added file-level `reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false` (mirrors what `test_eval_loader.py` and other test files do). No inline ignores. |

All three were caught during the per-step validation loop and fixed before
moving to the next step — no rework after Phase 4 final validation.

## Pre-existing Flaky Test

`app/core/agents/tools/transit/tests/test_client.py::test_fetch_feed_http_error`
fails intermittently in the full unit-test run but passes in isolation. It is
unrelated to the AI-7.3/7.4 changes (different module, no shared fixtures or
mocks). Reproduced in both pre- and post-implementation runs. Should be
investigated separately as part of test-isolation cleanup.

## Manual Verification (Pending — post-merge)

These items from the plan's Verification section require running the actual
LLM stack and are deferred until after merge:

- [ ] `make eval-judge SUITE=transit` on a fresh trace — emits verdict JSONL
- [ ] `make eval-baseline SUITE=transit` writes `evals/baselines/transit_baseline.json`
- [ ] `make eval-check SUITE=transit` exits 0 right after baseline generation
- [ ] Manual calibration: human agrees with judge on ≥8/10 verdicts (AI-7.3 acceptance)
- [ ] Deliberately degrade a transit prompt → `make eval-check` exits 1 with a `RegressionFinding`

Code-level acceptance (35 unit tests + clean validation) is met.
