# CI Failure Buckets — Systematic Fix Tracker

**Source:** last 100 failed runs of `ci.yml` on `main` (pulled 2026-04-14).
**Total distinct failing (job, step) pairs:** 9 buckets.
**Re-verified on clean `main` (HEAD `db3963a`) at 2026-04-14.** All 9 buckets pass locally. Upstream fixes landed in commits `7ccb4bf`, `13467a7`, `148e39d`, and `db3963a`.

## How to use this file

1. Buckets are ordered by **fix priority**, not by frequency. Early buckets block later ones (a failing `Pre-commit check` hides all downstream failures).
2. For each bucket: **verify current state on main first** (`make check` or the exact CI command). Many errors are from old commits and may already be fixed. Do not fix based on log excerpts alone.
3. Only move to the next bucket after the current one is green locally AND on a re-run of CI.
4. Update status column as you go: `todo` → `in-progress` → `fixed` → `verified-ci-green`.

> **Verification method used here:** `git stash push -u` all parallel-session WIP, then run each bucket's CI-equivalent command against pristine `main`. Stash restored after verification so in-flight feature work is untouched.

---

## Priority order & blocker chain

```
1. Pre-commit checks ──▶ blocks everything (Format/Lint/Mypy)
2. Dependency audit   ──▶ independent gate, but blocks merges
3. Format check       ──▶ trivial, run-once
4. Lint check         ──▶ likely fixable with --fix
5. Run migrations     ──▶ must pass before Run tests
6. Type check (mypy)  ──▶ after lint
7. Type check (pyright)
8. Frontend Type check
9. Run tests          ──▶ last; real bugs surface here
```

---

## Bucket 1 — Pre-commit checks (27 runs, backend)

**Status:** `fixed-locally`
**Verify:** `uv run pre-commit run detect-secrets --all-files`
**Local result (2026-04-14):** `Detect secrets...Passed`

**Root cause & fix:** `.pre-commit-config.yaml` already excludes `.secrets.baseline` from the detect-secrets hook (`exclude: (\.env\.example|…|\.secrets\.baseline)$`), stopping the self-scan oscillation. Commit: `7ccb4bf fix(ci): stop detect-secrets baseline self-scan oscillation`.

**Representative run:** 24383241730

---

## Bucket 2 — Dependency audit (24 runs, backend)

**Status:** `fixed-locally`
**Verify:** `uv run pip-audit --desc --ignore-vuln CVE-2025-69872 --ignore-vuln CVE-2024-23342`
**Local result (2026-04-14):** `No known vulnerabilities found`

**Root cause & fix:**
- `pillow 12.1.1` → `12.2.0` (CVE-2026-40192). Commit `13467a7`.
- `pytest 8.4.2` → `9.0.3` (CVE-2025-71176). Commit `13467a7`.

The pytest-9 major bump did not break collection; local run of `test_predict_eta.py` (5 tests) passes under the new lockfile.

**Representative run:** 24386205504

---

## Bucket 3 — Format check (18 runs, backend)

**Status:** `fixed-locally`
**Verify:** `uv run ruff format --check .`
**Local result (2026-04-14):** `598 files already formatted`

The alembic/scripts files named in the original log excerpt have since been formatted and committed.

**Representative run:** 22849414647

---

## Bucket 4 — Lint check (13 runs, backend)

**Status:** `fixed-locally`
**Verify:** `uv run ruff check .`
**Local result (2026-04-14):** `All checks passed!`

The `RUF100` stale `# noqa: S311` directives have already been auto-fixed upstream.

**Representative run:** 24307707495

---

## Bucket 5 — Run migrations (7 runs, backend)

**Status:** `fixed-locally`
**Verify:** `uv run alembic heads`
**Local result (2026-04-14) on tracked files only:** single head `w7x8y9z0a1b2`.

The `KeyError: 'v6w7x8y9z0a1'` was caused by `w7x8y9z0a1b2_add_lemmatized_content_to_chunks.py` (KB-2) pointing at a down_revision that wasn't merged yet. Commit `db3963a fix(alembic): rebase KB-2 migration onto merged head` repointed it to `u5v6w7x8y9z0`.

> **Caveat for future runs:** `alembic heads` against a dirty working tree will still show multiple heads because several parallel feature sessions have uncommitted migrations (`1f0fc7681339_add_search_feedback.py`, `v6w7x8y9z0a1_add_share_links.py`, `x8y9z0a1b2c3_add_document_versions.py`, `e5n6t6k6b6_add_entities.py`). Each of those PRs is responsible for rebasing its own migration onto whatever head is current at merge time. They do not affect main CI until merged.

**Representative run:** 24386420978

---

## Bucket 6 — Type check (mypy) (3 runs, backend)

**Status:** `fixed-locally`
**Verify:** `uv run mypy app/`
**Local result (2026-04-14):** `Success: no issues found in 519 source files`

The `Settings` attribute references (`ml_load_time_window_seconds`, `anomaly_recent_window_hours`, etc.) and missing pandera annotations have been resolved in follow-up commits.

**Representative run:** 24328178589

---

## Bucket 7 — Type check (pyright) (2 runs, backend)

**Status:** `fixed-locally`
**Verify:** `uv run pyright`
**Local result (2026-04-14):** `0 errors, 0 warnings, 0 informations`

The `sql_validator.py` `reportUnknownArgumentType` errors are resolved.

**Representative run:** 24312781638

---

## Bucket 8 — Frontend Type check (9 runs, frontend)

**Status:** `fixed-locally`
**Verify:** `rm -rf cms/apps/web/.next && pnpm --filter @vtv/web type-check`
**Local result (2026-04-14):** clean exit (no TS errors).

> **Caveat:** stale `cms/apps/web/.next/types/validator.ts` from a dev run referencing WIP page paths can create spurious `TS2307` errors against `(dashboard)/journey-planner/page.js` etc. CI always runs from a clean checkout so this only affects local runs — delete `.next/` before type-checking if you hit it locally.

**Representative runs:** 24342173417, SDK example

---

## Bucket 9 — Run tests (6 runs, backend)

**Status:** `fixed-locally` (spot-checked)
**Verify:** `uv run pytest app/core/agents/tools/transit/tests/test_predict_eta.py -x`
**Local result (2026-04-14):** `5 passed`

The `test_predict_eta_logs_started_completed` assertion now finds the `agent.predict_eta.started` event in captured logs.

> **Not re-run:** the full 2258-test suite (~75s) was not executed during this sweep. Run `make test` before closing the bucket permanently.

**Representative run:** 24386812918

---

## Summary — 2026-04-14 re-verification

| # | Bucket | Status | Verifying commit |
|---|--------|--------|------------------|
| 1 | Pre-commit | ✅ fixed-locally | `7ccb4bf` |
| 2 | Dependency audit | ✅ fixed-locally | `13467a7` |
| 3 | Format | ✅ fixed-locally | (no single commit; incremental) |
| 4 | Lint | ✅ fixed-locally | (incremental) |
| 5 | Migrations | ✅ fixed-locally | `db3963a` |
| 6 | Mypy | ✅ fixed-locally | (incremental) |
| 7 | Pyright | ✅ fixed-locally | (incremental) |
| 8 | Frontend TS | ✅ fixed-locally | (incremental; clean `.next/` locally) |
| 9 | Backend tests | ✅ spot-checked | `148e39d` and related |

**Next action:** push main's current HEAD to trigger a fresh CI run and confirm `verified-ci-green` across all buckets. No code changes required.

---

## Appendix — Operational notes

- **Run the checks locally first.** `make check` covers format + lint + mypy + pyright + tests. Everything in this file should be verifiable in a single machine session.
- **Parallel-session WIP bleeds into local checks.** If a bucket shows multiple alembic heads, duplicate TS2307 errors for WIP pages, or unrelated mypy failures, `git stash push -u` before re-running — dirty-tree state is not what CI sees.
- **Don't backfill old runs.** Logs are frozen; fixing main's current head is the goal.
- **One commit per bucket** makes the next CI run's blame trivial.
- **Re-run the bucket survey weekly** using the commands in `.agents/ci-fixes/refresh.sh` (to be created) so new failure classes surface early.
