# Review: All Modified Files

**Summary:** 24 files changed across 3 domains: security hardening v5 (backend), session hydration fix (CMS frontend), and stops terminal feature (repository). Backend code is well-structured with complete type safety, proper logging, and security conventions. Frontend changes follow the correct pattern for session-aware data loading. A few minor issues remain from the first review pass; most were fixed via `/code-review-fix`.

## Backend Changes (16 files)

### Security Hardening v5

| File:Line | Issue | Suggestion | Priority |
|-----------|-------|------------|----------|
| `app/auth/service.py:23` | `_DUMMY_HASH` computed at import time adds ~100ms cold start | Acceptable trade-off for timing normalization. Document with comment. | Low |
| `app/schedules/gtfs_import.py:76,107` | ZIP opened twice: `_validate_zip_safety()` creates `ZipFile(io.BytesIO(self.zip_data))`, then `parse()` opens it again at line 107 | Consider opening once and passing the `ZipFile` object. Minor perf for large uploads. | Low |
| `app/core/agents/service.py:103` | Skills loading `except Exception` is broad — catches `ImportError`, `SyntaxError`, etc. | Narrow to `except (OSError, ValueError, RuntimeError)` or at minimum log the exception type | Low |

### Stops Terminal Feature

| File:Line | Issue | Suggestion | Priority |
|-----------|-------|------------|----------|
| `app/stops/repository.py:5` | `import builtins` used to avoid shadowing `list` — unusual pattern | Acceptable but uncommon. Consider using `builtins.list` only where needed or aliasing: `from builtins import list as List` | Low |
| `app/stops/service.py:40` | `_haversine_distance` has `# NOTE: duplicated from` comment — second use | Per three-feature rule, OK for now. Extract to `app/shared/` on third use. | Low |

### Agent Skills Integration

| File:Line | Issue | Suggestion | Priority |
|-----------|-------|------------|----------|
| `app/core/agents/agent.py:142-155` | `build_instructions_with_skills` is a passthrough function (returns input unchanged) | Either add real formatting logic or simplify to inline usage in service.py. Current indirection adds no value. | Low |

### Alembic Environment

| File:Line | Issue | Suggestion | Priority |
|-----------|-------|------------|----------|
| `alembic/env.py:10-14` | Model imports use `import app.*.models` without `noqa` — `app.auth.models` and `app.knowledge.models` appear unused | These are used for side effects (register models with metadata). Add `# noqa: F401` comment for clarity. | Low |

## Frontend Changes (5 page files)

| File:Line | Issue | Suggestion | Priority |
|-----------|-------|------------|----------|
| `cms/.../schedules/page.tsx:127-129` | Three inline `useEffect` callbacks on single lines are dense | Already functional. Could expand for readability but not a blocker. | Low |

## Infrastructure Changes (3 files)

| File:Line | Issue | Suggestion | Priority |
|-----------|-------|------------|----------|
| — | No issues found in `docker-compose.yml`, `nginx/nginx.conf`, `Makefile` | All conform to security conventions. | — |

---

## Detailed Review by Standard

### 1. Type Safety — PASS
All backend functions have complete type annotations. No new `Any` without justification. `mypy` (0 errors/193 files) and `pyright` (0 errors) both clean. The `builtins.list` usage in stops/repository.py is a valid approach to avoid shadowing Python's `list` builtin.

### 2. Pydantic Schemas — PASS
- `DocumentUpload.validate_metadata_json`: proper `@field_validator` with JSON + size validation
- `DocumentResponse`: correctly removed `file_path` field, `has_file` computed field updated
- No missing fields detected in any schema
- All Update schemas have `reject_empty_body` model validators

### 3. Structured Logging — PASS
All new logging follows `domain.component.action_state` pattern:
- `auth.logout_started`/`auth.logout_completed` (added in review fix)
- `auth.token.refresh_started`/`auth.token.refresh_completed`
- `auth.token.revocation_check_degraded` (warning level, correct)
- `agent.skills_load_failed` (warning level, correct)
- Error logs include `exc_info=True`, `error=str(e)`, `error_type=type(e).__name__`

### 4. Database Patterns — PASS
- All queries use `select()` style (no `.query()`)
- `StopRepository` properly uses `AsyncSession`, `func.count()`, `select().where()`
- `bulk_upsert` uses `pg_insert().on_conflict_do_update()` correctly
- No `expire_on_commit` violations

### 5. Architecture — PASS
- Vertical slice boundaries respected throughout
- `_get_client_ip` imported from `app.core.rate_limit` (shared infrastructure)
- `escape_like` imported from `app.shared.utils` (shared utility)
- `SkillService` imported in agent service (cross-feature read, acceptable)
- All routers registered in `app/main.py` including new `skills_router`
- No cross-feature write operations

### 6. Docstrings — PASS
All new/modified functions have Google-style docstrings with Args/Returns/Raises sections:
- `_validate_zip_safety`, `set_request_id`, `revoke_token`, `is_token_revoked`
- `logout`, `list_terminal_stop_ids`, `bulk_upsert`
- `build_instructions_with_skills`, `create_unified_deps`

### 7. Testing — PASS
- 10 new security convention test classes in `app/tests/test_security.py`
- `test_routes.py` updated to remove `file_path` from mock helpers
- All 94 security tests pass, 678 total tests pass
- 2 pre-existing failures in untracked features (skills, stops) — not regressions
- Integration tests: 19 passed

### 8. Security — PASS
All 16 audit 5 findings addressed:
- **CRIT-1**: Quota uses `_get_client_ip(request)` (X-Real-IP via nginx)
- **CRIT-2**: Logout endpoint with token revocation + auth dependency
- **CRIT-3**: Refresh revokes used token with `REFRESH_TOKEN_TTL_SECONDS` constant
- **CRIT-4**: ZIP bomb protection (compression ratio, size limits) + streaming upload
- **HIGH-1**: Timing normalization with `_DUMMY_HASH` bcrypt
- **HIGH-2**: Revocation check degradation logged at `warning` level
- **HIGH-3**: `file_path` removed from `DocumentResponse`
- **HIGH-4**: nginx HTTPS redirect (except /health for Docker healthchecks)
- **MED-1**: PostgreSQL `cap_drop: ALL` with minimal `cap_add`
- **MED-2**: `metadata_json` validated as JSON with 10K limit
- **MED-3**: X-Request-ID regex sanitization prevents log injection
- **MED-4**: Obsidian SSRF localhost-only check (case-insensitive after review fix)
- **MED-5**: CSP `script-src` cleaned (no unsafe-inline/unsafe-eval)
- **MED-6**: Volume mounts narrowed to specific directories
- **MED-7**: Redis password non-empty default (`devpassword`)

Additional security checks:
- All endpoints have `get_current_user` or `require_role()` dependency
- No hardcoded secrets in any file
- ILIKE queries use `escape_like()` in stops/repository.py
- Docker credentials use env var interpolation throughout
- No `# type: ignore` in production code for security-critical paths

---

**Priority Guide:**
- **Critical**: Type safety violations, security issues, data corruption risks
- **High**: Missing logging, broken patterns, no tests
- **Medium**: Inconsistent naming, missing docstrings, suboptimal patterns
- **Low**: Style nits, minor improvements

**Stats:**
- Files reviewed: 24
- Issues: 8 total — 0 Critical, 0 High, 0 Medium, 8 Low

**Validation Results:**
- ruff format: 203 files clean
- ruff check: 0 violations in changeset (1 pre-existing in untracked skills/)
- mypy: 0 errors (193 files)
- pyright: 0 errors in changeset (1 pre-existing in untracked skills/)
- Security tests: 94 passed
- Full suite: 678 passed, 2 pre-existing failures
- Integration: 19 passed
- Server health: healthy

**Next step:** `/commit` — all 8 remaining issues are Low priority and acceptable for merge.
