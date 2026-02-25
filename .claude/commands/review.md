---
description: Review code against all 8 VTV quality standards
argument-hint: [file-or-directory] e.g. app/core/ or app/core/health.py
allowed-tools: Read, Glob, Grep, Write
---

Review code against VTV's 8 quality standards and produce a findings table with fix suggestions.

@CLAUDE.md

# Review — Code Review Against VTV Standards

## INPUT

**Target:** $ARGUMENTS

## PROCESS

Read all files in the target path. For each file, check against VTV's standards in this order:

### 1. Type Safety (CRITICAL)

- All functions have complete type annotations (params + return)
- No `Any` types without justification
- No `# type: ignore` or `# pyright: ignore` suppressions
- Pydantic models use proper field types

### 2. Pydantic Schemas

- Request/response schemas are complete (no missing fields)
- Validators use `@field_validator` or `@model_validator` patterns
- Schemas inherit appropriately (Create, Update, Response variants)

### 3. Structured Logging

- Events follow `domain.component.action_state` pattern
- Actions have `_started` and `_completed`/`_failed` pairs
- Error logs include `exc_info=True`, `error=str(e)`, `error_type=type(e).__name__`
- Logger created with `get_logger(__name__)`
- No generic events like "processing" or "handling"

### 4. Database Patterns

- Async/await used consistently with SQLAlchemy
- `select()` style (not `.query()`)
- Models inherit from `Base` and `TimestampMixin`
- `get_db()` dependency used for sessions
- `expire_on_commit=False` respected

### 5. Architecture

- Vertical slice boundaries respected (no cross-feature imports)
- Shared utilities only in `app/shared/` when used by 3+ features
- Router registered in `app/main.py`
- Feature structure: models.py, schemas.py, routes.py, service.py, tests/

### 6. Docstrings

- Functions have Google-style docstrings
- Tool/agent functions have agent-optimized docstrings covering all 5 principles:
  1. **Guide Selection** — When to use this tool (and when NOT to)
  2. **Prevent Token Waste** — Parameter efficiency tips, concise response formats
  3. **Enable Composition** — What tools to chain before/after
  4. **Set Expectations** — Output format, size, performance characteristics
  5. **Provide Examples** — Concrete usage with realistic data

### 7. Testing

- Tests exist in feature's `tests/` subdirectory
- Integration tests marked with `@pytest.mark.integration`
- Async tests use proper patterns
- Edge cases covered

### 8. Security

**Application code (Python):**
- No hardcoded secrets, demo passwords, or credentials in source code
- ILIKE/LIKE queries use `escape_like()` from `app.shared.utils` (not raw f-strings)
- File uploads enforce size limits via streaming chunks (not just middleware `Content-Length`)
- Filenames regex-sanitized with `re.sub(r"[^\w\-.]", "_", ...)` and paths validated with `is_relative_to()`
- URLs redacted before logging — no credentials in log output (use `_redact_url()`)
- Rate limiter uses `X-Real-IP` header, not client-spoofable `X-Forwarded-For`
- Query params validated with `max_length` and `pattern` constraints
- Docker credentials use env var interpolation (`${VAR:-default}`), not hardcoded values
- Input validation on all API boundaries (Query, Form, Path params)
- SQL injection prevention (parameterized queries via SQLAlchemy)
- GTFS time fields validated for range (minutes < 60, seconds < 60), not just format
- Composite natural keys have UniqueConstraint (trip+stop_sequence, calendar+date)
- Unknown file types rejected with 415, never silently processed as "text"
- Error-path DB calls wrapped in try/except to avoid masking original errors
- Content-Length header parsed with try/except ValueError
- PATCH/PUT schemas reject empty bodies via model_validator
- Stored files cleaned up when processing fails (no orphaned uploads)
- **All route endpoints protected** — every endpoint has `get_current_user` or `require_role()` dependency (enforced by `TestAllEndpointsRequireAuth` convention test)
- **Security logging at warning+** — no `logger.debug` in `except` blocks in auth paths (enforced by `TestNoDebugSecurityLogging` convention test)
- **JWT algorithm safety** — must use HS256, not `none` (enforced by `TestJwtAlgorithmNotNone` convention test)
- **Bcrypt rounds >= 12** — no weakened hash rounds (enforced by `TestBcryptRoundsSufficient` convention test)

**Shell scripts (`scripts/`):**
- No `eval` — use `bash -c "$cmd"` or direct function calls
- All shell variables that hold file lists must be quoted or piped through `xargs` to prevent word splitting on filenames with spaces
- `set -euo pipefail` at top of every script (fail on undefined vars, pipe errors)
- CVE ignore flags (`--ignore-vuln`) must have inline comments explaining why and when to re-evaluate
- Error output must not be swallowed — capture and display stderr on failure

**GitHub Actions workflows (`.github/workflows/`):**
- `${{ }}` expressions in `run:` blocks must use intermediate `env:` variables to prevent expression injection (even for `choice` inputs — defense in depth)
- CI-only credentials (ephemeral DB) must have a comment noting they are CI-only
- `continue-on-error: true` should only be on steps that upload artifacts (not on the check itself, unless results are captured)

**YAML/Docker config:**
- `yaml.safe_load()` (never `yaml.load()`) and null-check the result before accessing keys
- Python scripts parsing YAML/config files must handle malformed input gracefully (try/except or None checks)

## OUTPUT

Present findings in this format:

### Review: `[target path]`

**Summary:** [1-2 sentence overall assessment]

| File:Line | Issue | Suggestion | Priority |
|-----------|-------|------------|----------|
| `path:42` | [what's wrong] | [how to fix] | Critical |
| `path:15` | [what's wrong] | [how to fix] | High |
| `path:88` | [what's wrong] | [how to fix] | Medium |
| `path:3`  | [what's wrong] | [how to fix] | Low |

**Priority Guide:**
- **Critical**: Type safety violations, security issues, data corruption risks
- **High**: Missing logging, broken patterns, no tests
- **Medium**: Inconsistent naming, missing docstrings, suboptimal patterns
- **Low**: Style nits, minor improvements

**Stats:**
- Files reviewed: [X]
- Issues: [N] total — [A] Critical, [B] High, [C] Medium, [D] Low

Save the review to `.agents/code-reviews/[target-name]-review.md`.

**Next step:** To fix issues: `/code-review-fix .agents/code-reviews/[target-name]-review.md`
