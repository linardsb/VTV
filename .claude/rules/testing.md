---
paths:
  - "app/**/tests/**"
  - "cms/**/e2e/**"
  - "cms/**/*.spec.ts"
  - ".github/**"
---

# Testing Rules

## CI Pipeline

GitHub Actions (`.github/workflows/ci.yml`) runs on push/PR to `main`. Three jobs:
- `backend-checks`: ruff + security audit via `ruff --select=S` + mypy + pyright + pytest (with PostgreSQL + Redis services)
- `frontend-checks`: TypeScript + ESLint + build
- `e2e-tests`: docker-compose full stack + Playwright (depends on first two jobs). Report uploaded as artifact (14-day retention).

## Pytest Conventions

- Tests in `tests/` subdirectory of each feature
- `@pytest.mark.integration` for DB tests
- Fast unit tests preferred
- Test helpers need return type annotations (`-> ReturnType`)
- No `type: ignore` in test files — use pyright file-level directives

## E2E Patterns (Playwright)

- Auto-detection script maps changed components to test files
- Three projects: setup (auth), chromium (authenticated), no-auth (login page)
- Shared code changes trigger ALL tests
- CRUD tests conditionally skip when prerequisites missing
