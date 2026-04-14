# CI Fixes — Session Progress (2026-04-14)

Continuation-friendly record of the CI-failure sweep driven from `.agents/ci-fixes/BUCKETS.md`.

## Scope

BUCKETS.md enumerated 9 distinct failing (job, step) pairs across the last 100 failed `ci.yml` runs on `main`. This session cross-verified the taxonomy against the last 140 failed runs — the same 9 pairs cover every failure on the GitHub Actions history pages 1–7. Full mapping proven empirically via `gh run view --json jobs --jq '.jobs[].steps[] | select(.conclusion=="failure")'`.

## Final bucket status (end of session)

| # | Bucket | Status | Notes |
|---|--------|--------|-------|
| 1 | Backend \| Pre-commit checks | ⚠ **still intermittent** | See *Remaining work* below |
| 2 | Backend \| Dependency audit | ✅ green | `13467a7` pillow/pytest bump |
| 3 | Backend \| Format check | ✅ green | incremental upstream fixes |
| 4 | Backend \| Lint check | ✅ green | incremental upstream fixes |
| 5 | Backend \| Run migrations | ✅ green | `db3963a` KB-2 rebase |
| 6 | Backend \| Type check (mypy) | ✅ green | incremental upstream fixes |
| 7 | Backend \| Type check (pyright) | ✅ green | incremental upstream fixes |
| 8 | Frontend \| Type check | ✅ green | incremental upstream fixes |
| 9 | Backend \| Run tests | ✅ green (predict_eta) / ✅ green (test_config) | **Fixed this session** — see below |

## Commits landed on `main` this session

| SHA | Subject | Effect |
|-----|---------|--------|
| `ddbde20` | `fix(logging): disable structlog logger cache so capture_logs works in suite` | Production fix. Eliminates the entire class of `capture_logs()`-bypass bugs. |
| `76cd253` | `fix(tests): set JWT_SECRET_KEY in production env test` | Test fix. Satisfies the production-env JWT validator that was added after the test. |
| `8379ae0` | `fix(tests): mark JWT test literal as allowlisted for detect-secrets` | Test fix. `# pragma: allowlist secret` on the test fixture literal. |

Origin `main` HEAD at end of session: `8379ae0`.

## Deep-dive: Bucket 9 root cause (the only real production bug)

### Symptom

CI failed at test #825 of the suite:

```
FAILED app/core/agents/tools/transit/tests/test_predict_eta.py::TestPredictEta::test_predict_eta_logs_started_completed
AssertionError: assert 'agent.predict_eta.started' in []
```

…while captured stdout clearly showed the events being emitted.

### Root cause

`app/core/logging.py::setup_logging()` configured structlog with `cache_logger_on_first_use=True`. When any earlier test caused the module-level `logger = get_logger(__name__)` in `predict_eta.py:19` to be resolved, structlog permanently bound its processor chain to the production config. Later `structlog.testing.capture_logs()` swapped the *global* config, but the already-bound module logger kept its stale chain and wrote to stdout via `PrintLoggerFactory` instead of through `LogCapture` — `cap_logs` stayed empty.

Invisible in single-file local runs (why I initially mis-reported the bucket as green).

### Fix

`app/core/logging.py` — `cache_logger_on_first_use=False`. Trade-off: structlog rebinds per call, overhead is microseconds, dominated by any realistic log sink. Fix eliminates the class of bug for any module using the standard `logger = get_logger(__name__)` pattern.

## Cascade after the predict_eta fix

With `-x` stop-on-first-failure, each CI run revealed the next latent bug previously masked:

1. Pre-`ddbde20`: fails at test #825 (predict_eta).
2. Post-`ddbde20`: fails at test #987 (`test_settings_from_environment` — production validator rejects default JWT secret). Fixed in `76cd253`.
3. Post-`76cd253`: fails at pre-commit / detect-secrets (the new JWT test literal flagged). Fixed in `8379ae0`.
4. **Post-`8379ae0`: fails at pre-commit / detect-secrets again — this time with baseline drift oscillation.** See below.

## Remaining work for the next session

### R1 — detect-secrets baseline oscillation (CRITICAL, blocks all CI)

CI run `24388924745` (on `8379ae0`) fails:

```
Detect secrets...........................................................Failed
- hook id: detect-secrets
Probably to keep line numbers of secrets up-to-date.
Please `git add .secrets.baseline`, thank you.
```

The hook detects that the baseline's recorded line numbers drift from what it just re-scanned (my pragma line shifted the hashes in `app/core/tests/test_config.py`), auto-updates `.secrets.baseline`, and then fails because the modified baseline isn't in git.

Commit `7ccb4bf` addressed a *different* oscillation (self-scan of the baseline file). This one is legitimate baseline drift.

**Suggested fix paths** (pick one):

1. **Re-generate and commit the baseline:**
   ```bash
   uv run detect-secrets scan --baseline .secrets.baseline
   git add .secrets.baseline
   git commit -m "chore(security): refresh detect-secrets baseline line numbers"
   ```
   Low-risk — just accepts the new line numbers as canonical.

2. **CI auto-stage on drift** (similar to the pattern in commit `c480ff8 fix(ci): auto-update secrets baseline line numbers before pre-commit check`) — if that logic exists but isn't firing here, debug why. The CI workflow may need a pre-hook step that runs `detect-secrets scan --baseline .secrets.baseline` before `pre-commit run`.

3. **Drop line numbers from the baseline** via `--exclude-lines` or equivalent — more invasive, risks masking real regressions.

Option 1 is fastest. Option 2 is more durable.

### R2 — Potential further latent failures beyond R1

Because CI uses `pytest -x`, any test that would have failed after the current blocker hasn't been observed yet. When R1 is fixed, the next CI run may reveal more test failures that were invisible up to now. Plan to loop:

```
fix → push → watch CI → inspect next failure → fix → ...
```

until a clean green run lands.

## Stashes present (inspect with `git stash list`)

Several stashes were created to isolate fixes from parallel-session WIP. Inspect and drop/apply as appropriate for the kb-5 / kb-4 / lv-3-3 / lv-3-4 branches they belong to — none of them belong on `main`.

## Watch-outs for continuation

- **Parallel sessions are active on `main`.** A merge commit `95f6aae Merge branch 'kb-5-entity-graph'` appeared in my local `main` during this session and was NOT pushed — I cherry-picked my clean fix onto `origin/main` instead. If you see unexpected commits on `main` locally, compare against `origin/main` before pushing.
- **Dirty working tree distorts local CI equivalents.** `uv run mypy app/` on a dirty tree reports parallel-session errors that are not on main. `uv run alembic heads` shows multiple heads for the same reason. Stash before verifying.
- **Cross-check before fixing from log excerpts.** BUCKETS.md warned about this and it bit me on Bucket 9 — the test passed in isolation locally while failing in the full suite on CI. Always run with something approximating the full suite (`uv run pytest -x -q` with real DB/Redis) before declaring green.

## Fast re-verify commands

```bash
# Stash all in-flight work so you see what CI sees
git stash push -u -m "verify-main"

# Run each gate (mirrors ci.yml)
uv run pre-commit run --all-files
uv run pip-audit --desc --ignore-vuln CVE-2025-69872 --ignore-vuln CVE-2024-23342
uv run alembic heads
uv run mypy app/
uv run pyright
(cd cms && rm -rf apps/web/.next && pnpm --filter @vtv/web type-check)
DATABASE_URL=... REDIS_URL=... uv run pytest -x -q

# Restore
git stash pop
```

## References

- BUCKETS.md: `.agents/ci-fixes/BUCKETS.md`
- CI workflow: `.github/workflows/ci.yml`
- Failing run IDs inspected this session: 24386812918 (predict_eta), 24387731575 (predict_eta), 24388507319 (test_config), 24388756206 (detect-secrets pragma), 24388924745 (detect-secrets baseline drift — **next to fix**).
