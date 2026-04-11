# Execution Report — AI-7.1 Synthetic Eval Cases + Loader

**Plan:** [.agents/plans/ai-7.1-synthetic-test-cases.md](../plans/ai-7.1-synthetic-test-cases.md) (if present)
**Commit:** `06e0a1b feat(agent): add progressive L3 skills, AgentResult, and synthetic eval cases (AI-6.4/6.5/7.1)`
**Date:** 2026-04-10
**Status:** ✅ Complete
**Reconstructed retrospectively on:** 2026-04-11 (report was not written when the feature landed)

## Scope

Foundation of the agent eval framework: frozen `EvalCase` + `QualityCriterion` dataclasses, fail-open path-sandboxed YAML loader mirroring `skill_loader.py`, and 30 hand-authored synthetic test cases across the three domains (transit/knowledge/vault). No runner yet — AI-7.2 built that on top.

## Files Created (per `06e0a1b`)

| File | Purpose |
|---|---|
| `app/core/agents/evals/__init__.py` | Package docstring (later extended by AI-7.2) |
| `app/core/agents/evals/schemas.py` | Frozen `EvalCase` + `QualityCriterion` dataclasses with `__post_init__` validation. Defines `VALID_DOMAINS`, `VALID_LANGUAGES`, `KNOWN_TOOLS` (frozenset of all 10 unique tool function names), `REQUIRED_CRITERIA_COUNT = 5`. |
| `app/core/agents/evals/loader.py` | Fail-open YAML loader. `yaml.safe_load` only, path-sandboxed via `Path.is_relative_to` after `.resolve()` on both sides. Logs `agent.evals.loader.<reason>` on every error path; never raises into callers. Returns `None`/`[]` on failure. |
| `app/core/agents/evals/cases/transit.yaml` | 15 cases: LV baseline, EN mirror, diacriticless variant, specific-route, name + proximity stop search, cross-tool composition, schedule by date/direction, adherence report, multi-route comparison, driver headcount, cross-tool driver+schedule, non-existent route handling, mixed LV/EN code-switching |
| `app/core/agents/evals/cases/knowledge.yaml` | 10 cases: SOP retrieval, EU regulation, out-of-domain "no relevant docs" honesty, cross-lingual LV↔EN retrieval, temporal SOP relevance, multi-doc synthesis, diacriticless query, EN policy lookup, citation format compliance |
| `app/core/agents/evals/cases/vault.yaml` | 5 cases: tag search, note creation with frontmatter, safe deletion requiring `confirm: true`, bulk operation with `dry_run` preview, folder organisation |
| `app/core/agents/tests/test_eval_loader.py` | 30 tests — schema validation (valid + rejects empty/unknown/wrong-count), frozen invariant, parser edges (missing/malformed/top-level-not-dict/missing-cases-key/cases-not-list), partial-skip-keeps-valid, missing-file, path-traversal blocked, three-domain load, duplicate-ID detection, production-suite integrity |

## Files Modified (per `06e0a1b`)

| File | Change |
|---|---|
| `app/core/agents/tests/conftest.py` | Added `make_eval_case` + `make_quality_criterion` factories + `tmp_eval_dir` fixture |
| `app/core/agents/CLAUDE.md` | Added `evals/` bullet to the directory tree |
| `docs/TODO.md` | Marked AI-7.1 done with Status line and Completed section entry |

## Validation Results (at commit time)

- pyright + mypy baseline preserved (5 / 3 pre-existing errors, all unrelated files)
- 286 agent tests + 1376 unit tests + 106 security convention tests green
- No new endpoints, no models, no migrations, no auth surface — zero HTTP behavior change

## Security Posture

Mirrors `skill_loader.py` exactly:
- `yaml.safe_load` only (no `yaml.load`)
- Path sandbox: `_CASES_ROOT.resolve()` + `file_path.resolve()` + `Path.is_relative_to()`
- Fail-open: every error path logs structured event and returns empty; never raises into callers
- No raw prompt content in INFO logs — only file paths and counts

CTX-AGENT + CTX-INPUT contexts satisfied; no CTX-AUTH/RBAC/FILE/INFRA triggered.

## Out of Scope (deferred)

- Eval runner that actually executes cases → **AI-7.2 (done 2026-04-11)**
- LLM judges + TPR/TNR calibration → AI-7.3
- Regression baselines + CI gating → AI-7.4

## Retrospective Notes

- `KNOWN_TOOLS` frozenset prevents typos in `expected_tools`; `__post_init__` rejects unknown tool names at load time.
- Test suite assertion that every one of the 10 known tool names appears in at least one case keeps the eval suite honest as tools are added/renamed.
- 5-criterion count enforced by `REQUIRED_CRITERIA_COUNT` constant — changing it is a breaking change to every YAML case.
- Duplicate-ID detection is suite-wide (across all three files), not per-file — guards against cross-file collisions.
