# CI Fixes — Session Progress (2026-04-14)

Continuation-friendly record of the CI-failure sweep driven from `.agents/ci-fixes/BUCKETS.md`.

## Scope

BUCKETS.md enumerated 9 distinct failing (job, step) pairs across the last 100 failed `ci.yml` runs on `main`. Goal: verify each bucket on the current `main` HEAD, fix whatever's actually still broken, leave a clear record.

## Starting state

- `main` HEAD when the sweep began: `db3963a fix(alembic): rebase KB-2 migration onto merged head`
- `main` HEAD after a parallel KB-3 merge during the sweep: `725c03f feat(knowledge): add document versioning with diff-aware search (KB-3)`
- Working tree had extensive uncommitted work from parallel feature sessions (KB-3/4/5, LV-3.3/3.4, etc.) — stashed before running any CI-equivalent check so local observations matched what CI sees.

## Bucket-by-bucket verification

| # | Bucket | Local cmd | Result on clean `main` | Resolution |
|---|--------|-----------|------------------------|------------|
| 1 | Pre-commit / detect-secrets | `uv run pre-commit run detect-secrets --all-files` | Passed | Already fixed by commit `7ccb4bf` (exclude `.secrets.baseline` from self-scan) |
| 2 | Dependency audit | `uv run pip-audit --desc --ignore-vuln CVE-2025-69872 --ignore-vuln CVE-2024-23342` | No vulnerabilities | Already fixed by commit `13467a7` (pillow 12.2.0, pytest 9.0.3) |
| 3 | Format | `uv run ruff format --check .` | 598 files already formatted | Previously landed incrementally |
| 4 | Lint | `uv run ruff check .` | All checks passed | Previously landed incrementally (RUF100 auto-fix) |
| 5 | Migrations | `uv run alembic heads` (clean tree) | Single head `w7x8y9z0a1b2` | Already fixed by commit `db3963a` |
| 6 | mypy | `uv run mypy app/` | 0 errors on tracked files (clean tree) | Incremental fixes already landed |
| 7 | pyright | `uv run pyright` | 0 errors, 0 warnings | Incremental fixes already landed |
| 8 | Frontend TS | `rm -rf cms/apps/web/.next && pnpm --filter @vtv/web type-check` | Clean | Incremental — local stale `.next/` is a false positive, CI runs from clean checkout |
| 9 | Run tests | `uv run pytest -x -q` | **Still failing on CI: `test_predict_eta_logs_started_completed`** | **Fixed this session in `app/core/logging.py`** |

## Bucket 9 — the only real remaining failure

### Symptom

CI (HEAD `725c03f`) still fails at test #825 of the suite:

```
FAILED app/core/agents/tools/transit/tests/test_predict_eta.py::TestPredictEta::test_predict_eta_logs_started_completed
AssertionError: assert 'agent.predict_eta.started' in []
```

…yet captured stdout clearly shows the events being emitted:

```json
{"event": "agent.predict_eta.started", "level": "info", ...}
{"event": "agent.predict_eta.completed", "level": "info", ...}
```

### Root cause

`app/core/logging.py::setup_logging()` configured structlog with `cache_logger_on_first_use=True`. When any earlier test in the suite caused the module-level `logger = get_logger(__name__)` in `predict_eta.py:19` to be resolved, structlog permanently bound its processor chain to the production config. Later, when `structlog.testing.capture_logs()` swapped the *global* config, the already-bound module logger kept its stale chain and kept writing to stdout via `PrintLoggerFactory` instead of through the test's `LogCapture` processor — so `cap_logs` stayed empty.

This was invisible when running the test in isolation (which is why my first local verification mis-reported the bucket as green) because a single-file run hit `capture_logs()` *before* anything else triggered the cache bind.

### Why this is a class of bug, not a one-off

Any module using the project's standard `logger = get_logger(__name__)` pattern is subject to the same silent capture bypass whenever asserted from a later test in the suite. Patching individual tests (`structlog.reset_defaults()` + re-bind before each `capture_logs()`) would work but leaves the trap set for the next author.

### Fix

`app/core/logging.py` — one-line config change:

```diff
-        cache_logger_on_first_use=True,
+        # False so structlog.testing.capture_logs() can intercept events
+        # emitted through module-level `logger = get_logger(__name__)`
+        # proxies. ...
+        cache_logger_on_first_use=False,
```

Perf trade-off: structlog rebinds the processor chain on each log call. Overhead is microseconds and is dominated by any realistic sink (JSON render + stdout write). No measurable impact on a FastAPI service with async I/O in the hot path.

### Verification

1. `uv run pytest "app/core/agents/tools/transit/tests/test_predict_eta.py::TestPredictEta::test_predict_eta_logs_started_completed" app/core/agents/tests/ app/core/agents/tools/transit/tests/ -q` → **666 passed**, no test-side hack.
2. `uv run ruff format --check app/core/logging.py` → clean.
3. `uv run ruff check app/core/logging.py` → clean.
4. `uv run mypy app/core/logging.py` → clean.

## Untracked-on-main caveats to know when continuing

Running `uv run mypy app/` on a dirty tree will report extra errors from parallel-session files that are not on main (`app/transit/tests/test_share_routes.py`, `app/knowledge/feedback.py`, etc.). They will land with their respective PRs; they are not main-CI blockers. Verify by stashing before re-running.

`uv run alembic heads` shows multiple heads in a dirty tree because the parallel-session migrations (`1f0fc7681339`, `v6w7x8y9z0a1`, `x8y9z0a1b2c3`, `e5n6t6k6b6`) exist on the filesystem. Each owning PR is responsible for rebasing onto whatever head is current at merge time.

## Stashes present at handoff

Several stashes were created during this session to isolate the fix from parallel-session WIP. Inspect with `git stash list` and `git stash show -p stash@{N}` before dropping — some hold kb-5 branch state, others hold intermediate test-side bandaids that the production fix supersedes.

## What to do in the next tab

1. Verify the new CI run on `main` after the logging.py fix lands — all 9 buckets should go green.
2. If any un-enumerated failure surfaces, add it as Bucket 10 in `BUCKETS.md` with the same structure.
3. Review the stashes — keep anything that represents real parallel-session work, drop intermediate test-side bandaids.
4. Parallel-session WIP in the stashes belongs to those feature branches, not main.

## Commands for a fast re-verify

```bash
# Stash all in-flight work so you see what CI sees
git stash push -u -m "verify-main"

# Run each gate (mirrors ci.yml)
uv run ruff format --check .
uv run ruff check .
uv run pip-audit --desc --ignore-vuln CVE-2025-69872 --ignore-vuln CVE-2024-23342
uv run alembic heads
uv run mypy app/
uv run pyright
(cd cms && rm -rf apps/web/.next && pnpm --filter @vtv/web type-check)
DATABASE_URL=... REDIS_URL=... uv run pytest -x -q

# Restore
git stash pop
```
