# Review: `app/analytics/`

**Summary:** Clean implementation of a read-only aggregation layer. All 8 quality standards are largely met with a few minor issues: one unused type alias, one field that should use `Literal` instead of bare `str`, and two `pyright: ignore` suppressions that are justified but noted.

| File:Line | Issue | Suggestion | Priority |
|-----------|-------|------------|----------|
| `schemas.py:17` | `AdherenceStatus` Literal type is defined but never used in any schema or service | Remove unused type alias to avoid dead code | Medium |
| `schemas.py:100` | `service_type: str` is a bare `str` — upstream `classify_service_type()` returns only `"weekday"`, `"saturday"`, `"sunday"`. Plus the fallback `"unknown"` in routes.py | Define `ServiceType = Literal["weekday", "saturday", "sunday", "unknown"]` and use it. Matches VTV convention for constrained string fields | High |
| `service.py:91` | `# pyright: ignore[reportArgumentType]` suppression for DB string → Literal assignment | Justified — DB values are untyped strings. Document with brief comment explaining why (e.g., `# DB returns str, validated by Pydantic at runtime`) | Low |
| `service.py:214` | Same `# pyright: ignore[reportArgumentType]` for shift field | Same as above — justified, add brief comment | Low |
| `service.py:28` | Imports private function `_compute_route_adherence` from agent tool module | Acceptable per three-feature rule (2 consumers). Add `# NOTE: 2nd consumer — extract to shared on 3rd use` comment for traceability | Low |
| `routes.py:120` | `except Exception as e:` in on-time endpoint catches all exceptions including programming errors (AttributeError, TypeError) and maps them to 503 | Consider catching a narrower set (httpx errors, RuntimeError) or at least logging at `error` level not `warning` for unexpected exception types | Medium |
| `routes.py:161` | Overview `except Exception as e:` for on-time degradation — same broad catch | Same concern but more acceptable here since it's a graceful degradation path and the goal is to never fail the overview. Current behavior is correct | Low |
| `test_service.py:19-40` | `_mock_db_empty()` uses `call_count` state tracking which is fragile — adding a new query to the service will silently break mock ordering | Consider using `db.execute.side_effect` with a list of return values, or assert call count in test body | Medium |
| `test_routes.py:43` | `app.dependency_overrides[get_db] = lambda: AsyncMock()` — creates a new AsyncMock per call, meaning service gets a fresh mock each time | This works because the routes patch `AnalyticsService` anyway, so db is never actually used. But the pattern is misleading — consider documenting with a comment | Low |

**Priority Guide:**
- **Critical**: Type safety violations, security issues, data corruption risks
- **High**: Missing logging, broken patterns, no tests
- **Medium**: Inconsistent naming, missing docstrings, suboptimal patterns
- **Low**: Style nits, minor improvements

**Stats:**
- Files reviewed: 7
- Issues: 9 total — 0 Critical, 1 High, 3 Medium, 5 Low

**Next step:** To fix issues: `/code-review-fix .agents/code-reviews/analytics-review.md`
