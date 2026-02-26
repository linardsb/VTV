---
paths:
  - "app/auth/**/*.py"
  - "cms/**/auth*"
  - "cms/**/middleware*"
  - "scripts/**"
  - "nginx/**"
---

# Security Rules

## Pre-commit Hook

`scripts/pre-commit` — fast (<5s) shell script that blocks commits with:
- Bandit security violations
- Staged sensitive files (`.env`, `*.pem`, `*.key`)
- Hardcoded postgres credentials
- Leaked secrets (AWS keys, private keys, JWT tokens)
Install via `make install-hooks`.

## Auth Patterns

- FastAPI `HTTPBearer(auto_error=False)` + manual 401 (not default 403)
- `app.dependency_overrides` is global — test fixtures must save/clear/restore
- Never expose role names in error messages — generic "Insufficient permissions"
- JWT claims need runtime validation — `Array.includes()` + fallback, never bare `as` cast
- Auth tokens in httpOnly cookies only (never localStorage)

## Security Convention Tests

105 convention tests in `app/tests/test_security.py` auto-discover all endpoints and enforce:
- Auth requirements on every endpoint
- JWT safety, bcrypt rounds, container hardening
- CORS, GDPR, and 15+ other security properties
