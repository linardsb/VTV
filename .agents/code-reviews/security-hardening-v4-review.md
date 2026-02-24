# Review: Security Hardening v4

**Summary:** Solid security hardening implementation across 8 workstreams. Container hardening, GDPR deletion, dependency scanning, backup infrastructure, and 19 new convention tests all follow VTV patterns well. A few minor inconsistencies in logging and a double-query in the deletion flow, but no critical or security issues found.

| File:Line | Issue | Suggestion | Priority |
|-----------|-------|------------|----------|
| `app/auth/service.py:32` | `_check_redis_brute_force` except block has no logging, while sibling functions `_record_failed_attempt_redis` and `_clear_redis_brute_force` both log at `warning` level | Add `logger.warning("auth.redis_lockout_check_unavailable", email=email)` for consistency | Medium |
| `app/auth/service.py:217-224` | `delete_user_data` calls `find_by_id(user_id)` to get email, then `delete_user(user_id)` which internally does another `select(User).where(User.id == user_id)` — redundant DB query | Refactor `delete_user` to accept the User object directly, or have `delete_user_data` call `db.delete(user)` after the initial find | Medium |
| `app/auth/service.py:52` | `_record_failed_attempt_redis` except block logs warning but missing `exc_info=True` — harder to debug Redis connection issues | Add `exc_info=True` to `logger.warning("auth.redis_brute_force_unavailable", email=email, exc_info=True)` | Low |
| `app/auth/service.py:67` | `_clear_redis_brute_force` except block same issue — missing `exc_info=True` | Add `exc_info=True` to the warning log | Low |
| `docker-compose.prod.yml:11` | `POSTGRES_USER: postgres` hardcoded while base compose uses `${POSTGRES_USER:-postgres}` interpolation | Use `${POSTGRES_USER:-postgres}` for consistency with security standard | Low |
| `docker-compose.prod.yml:31` | migrate service `DATABASE_URL` hardcodes username `postgres:${POSTGRES_PASSWORD}` instead of `${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD}` | Use interpolated username for consistency | Low |
| `app/auth/routes.py:119` | `status_code=404` uses integer literal; other status codes in the file use `status.HTTP_*` constants | Use `status.HTTP_404_NOT_FOUND` for consistency | Low |
| `scripts/db-backup.sh` | Backup files are unencrypted `.sql.gz` containing potentially sensitive PII (user emails, names) | Consider adding `gpg --symmetric` encryption or document this as an accepted risk for local-only backups | Low |

**Priority Guide:**
- **Critical**: Type safety violations, security issues, data corruption risks
- **High**: Missing logging, broken patterns, no tests
- **Medium**: Inconsistent patterns, suboptimal performance
- **Low**: Style nits, minor improvements

**Stats:**
- Files reviewed: 8
- Issues: 8 total — 0 Critical, 0 High, 2 Medium, 6 Low
