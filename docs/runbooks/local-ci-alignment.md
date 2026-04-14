# Local CI Alignment

How the local dev environment is kept in sync with what CI enforces. Goal: every push that passes locally also passes CI.

Three layers, in order of speed:

## 1. Pre-commit hooks (≈5s, run on `git commit`)

Defined in `.pre-commit-config.yaml`, install via `make install-hooks`.

| Hook | Catches |
|------|---------|
| `ruff-format`, `ruff` | Format + lint regressions |
| `trailing-whitespace`, `end-of-file-fixer`, `check-yaml` | Trivial file hygiene |
| `check-added-large-files` (1MB) | Accidental binary commits |
| `detect-secrets --baseline .secrets.baseline` | New secrets not in baseline |
| `vtv-security` (`scripts/pre-commit`) | Bandit + sensitive files + hardcoded creds + secret regex |

## 2. Pre-push hooks (≈90s, run on `git push`)

Same config, `stages: [pre-push]`. These mirror the CI gates that historically caused the most CI failures.

| Hook | Catches | Class of bug |
|------|---------|--------------|
| `mypy` | Type errors on tracked files | Static type drift |
| `app-import-smoke` | `from app.main import app` failure | Wiring gaps (e.g. router defined but not registered in `main.py`) |
| `audit-log-taxonomy` | `logger.*()` events not in `docs/logging-standard.md` | Undocumented log events from new features |
| `pytest -x -q` (full suite, ≈75s) | Test regressions in the whole suite | Tests that pass in isolation but fail in the full run (e.g. structlog cache pollution, prod-env tests missing JWT_SECRET_KEY) |

**Pytest hook needs DB+Redis running** — `make db` first. If pre-push fails on pytest with connection errors, that's the cause.

To skip pre-push hooks once for a known-safe reason: `git push --no-verify`. Use sparingly — every cascade of CI failures this project has seen started with one `--no-verify`.

## 3. Local docker stack (≈3-5min, run when touching infra)

The pre-push hooks don't catch docker-only bugs (libgomp1 missing in runtime, `NEXT_PUBLIC_*` build args, `AUTH_URL` redirect derivation, container healthcheck failures, GTFS auto-import behavior).

**When to run `make docker && make e2e` before pushing:**

- Any change to `Dockerfile`, `docker-compose.yml`, `nginx/`, or `cms/apps/web/Dockerfile`
- Any change to `app/main.py` (lifespan, startup, router registration)
- Any change to `scripts/docker-migrate.py` or the migrate flow
- Any change to `auth.ts`, `middleware.ts`, or `next.config.ts`
- Any new `NEXT_PUBLIC_*` env var or backend service env var read from container

Skip the docker step for backend-only or frontend-only changes that don't touch the boundary — pre-push is enough.

```bash
make docker        # full stack: db, redis, migrate, app, cms, nginx
make e2e           # auto-detects changed features and runs only those tests
make docker-down   # teardown
```

## When CI does fail

The E2E job has a `Dump container logs on failure` step in `.github/workflows/ci.yml` that prints the last 1000 lines of every service (`db`, `redis`, `migrate`, `app`, `cms`, `nginx`) before teardown. This collapses what used to be 5 push iterations of "container unhealthy → guess what's wrong → push → repeat" into a single run with the actual app error visible.

Use the dumped logs to diagnose; don't push speculative fixes.

## Why each layer exists (decision history)

- **Pre-commit**: cheap formatting + secrets prevent the easy stuff from polluting `main`.
- **Pre-push**: 4 of 9 CI-failure classes in the April 2026 cascade (anomaly router unregistered, JWT in prod test, undocumented log events, wiring gaps) would have been blocked locally if the full suite + import smoke + taxonomy audit ran on push. They didn't, so they shipped.
- **Local docker**: the remaining 5 classes (docker missing libgomp1, build-time env baking, AUTH_URL redirect, migrate tz mismatch, asyncpg encoding) were docker-only. Pre-push can't catch these — the only way to surface them locally is to run the actual stack.
- **Log-dump**: when CI fails despite all the above, the dump cuts the diagnose-fix-push iteration count from 4-5 to 1.
