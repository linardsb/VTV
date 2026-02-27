# Code Review: PostGIS Migration

**Reviewed:** 2026-02-27
**Scope:** All files created/modified in the PostGIS migration

## Summary

Clean migration with solid architecture. PostGIS integration follows established patterns (pgvector precedent), proper trigger-based sync, and clean separation of concerns. Two medium issues (missing schema validator, stale docstring in CLAUDE.md) and a few low-priority items.

## Findings

| File:Line | Issue | Suggestion | Priority |
|-----------|-------|------------|----------|
| `app/stops/schemas.py:31` | `StopUpdate` missing `reject_empty_body` model_validator | Add `@model_validator(mode="before")` classmethod per VTV convention — rejects empty PATCH/PUT bodies | Medium |
| `CLAUDE.md:77` | Stops feature still described as "Haversine proximity" | Update to "PostGIS spatial queries" to reflect the migration | Low |
| `app/stops/models.py:8` | `pyright: ignore[reportMissingTypeStubs]` on geoalchemy2 import | Acceptable — GeoAlchemy2 lacks py.typed. File-level directive in repository.py is cleaner pattern | Low |
| `alembic/versions/b039c337be87:41` | Comment says "# 5." after "# 3." — numbering skip from removed step | Renumber comments to sequential (4, 5) | Low |
| `app/stops/tests/conftest.py:22` | `make_stop` defaults missing `geom` key | Add `"geom": None` to defaults dict for explicitness — prevents surprise if Stop model validates geom presence in future | Low |
| `app/shared/geo.py:4` | Docstring says "used by both the stops REST API and the transit agent tools" | Stops REST API no longer uses Haversine (now uses PostGIS). Update to "Used by the transit agent tools for in-memory proximity filtering" | Low |

## Standards Checklist

| Standard | Status | Notes |
|----------|--------|-------|
| 1. Type Safety | PASS | All functions annotated, pyright ignore only for untyped GeoAlchemy2 |
| 2. Pydantic Schemas | WARN | StopUpdate missing reject_empty_body (pre-existing, not introduced by migration) |
| 3. Structured Logging | PASS | `stops.nearby_started`/`stops.nearby_completed` pairs present |
| 4. Database Patterns | PASS | async/await, select() style, TimestampMixin, proper session usage |
| 5. Architecture | PASS | VSA respected, shared geo extracted correctly (used by 2 features: stops tests + agent tool) |
| 6. Docstrings | PASS | Google-style throughout, agent tool has full 5-principle format |
| 7. Testing | PASS | 56 feature tests + 4 shared geo tests, mocks updated for PostGIS delegation |
| 8. Security | PASS | No new security concerns, ILIKE uses escape_like(), trigger uses parameterized values |

## Stats

- Files reviewed: 12 (4 created, 5 modified, 3 test files)
- Issues: 6 total — 0 Critical, 0 High, 1 Medium, 5 Low
