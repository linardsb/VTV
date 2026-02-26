# Review: Dashboard Goals Model (Session 2)

**Date:** 2026-02-26
**Scope:** `app/events/` (schemas, models, tests) + `alembic/versions/37de45842dd3_*`
**Plan:** `.agents/plans/be-dashboard-goals-model.md`

## Summary

Clean implementation that adds JSONB goals to events with zero changes to service/repository/routes layers. All 8 quality standards pass with only minor suggestions. The approach correctly leverages Pydantic's `model_dump()`/`model_validate()` pipeline for transparent JSONB handling — no manual serialization needed.

## Findings

| File:Line | Issue | Suggestion | Priority |
|-----------|-------|------------|----------|
| `schemas.py:29` | `items: list[GoalItem]` has no upper bound constraint | Add `max_length=100` to Field to prevent oversized payloads beyond what BodySizeLimitMiddleware catches (100KB still allows ~200 items) | Low |
| `schemas.py:9-10` | `VALID_PRIORITIES` and `VALID_CATEGORIES` tuples are unused after `Literal` types were added (pre-existing) | Not a regression — pre-existing dead code. Could be cleaned up in a future pass but not part of this change | Low |
| `test_service.py:1` | `reportArgumentType=false` pyright directive added | Justified — intentional invalid literal in `test_goal_item_invalid_type` to verify Pydantic rejects it. No alternative without suppression | Low |
| `test_service.py` | Missing edge case: GoalItem `text` exceeding `max_length=500` | Add `test_goal_item_text_too_long` — Pydantic covers it natively but explicit test documents the contract | Low |
| `test_routes.py` | Missing edge case: POST with invalid `transport_type` returns 422 | Add route-level validation error test (HTTP 422 on bad enum value). Currently only tested at schema level in `test_service.py` | Low |

## Standard-by-Standard Assessment

### 1. Type Safety — PASS
- All new functions fully annotated (params + return types)
- `TransportType` and `GoalItemType` use `Literal[...]` — correct
- `Mapped[dict[str, Any] | None]` for JSONB column — `Any` justified by JSONB nature
- No `# type: ignore` in production code
- Single pyright suppression in test file is justified (intentional invalid literal)

### 2. Pydantic Schemas — PASS
- `GoalItem`: required `text` (1-500), default `completed=False`, required `item_type` Literal
- `EventGoals`: `default_factory=list` for items, all optional fields use `None` default
- `EventBase.goals`: nullable field with `Field(None, ...)`
- `EventUpdate.goals`: properly optional for PATCH semantics
- `reject_empty_body` validator correctly handles goals (verified: `{"goals": null}` alone is rejected, `{"goals": {...}}` passes)

### 3. Structured Logging — PASS (N/A)
- No new logging events needed — existing `events.create_started`/`_completed` pattern covers goals transparently
- Correct decision not to add goals-specific logging (would be noisy without value)

### 4. Database Patterns — PASS
- `OperationalEvent` inherits `Base, TimestampMixin`
- `mapped_column(JSONB, nullable=True, default=None)` — correct PostgreSQL dialect
- Migration uses `sa.Column("goals", postgresql.JSONB(), nullable=True)` — clean
- `model_dump()` serializes nested `EventGoals` to dict for JSONB storage automatically
- `exclude_unset=True` preserves PATCH semantics — not sending `goals` doesn't touch it

### 5. Architecture — PASS
- All changes within `app/events/` vertical slice
- No cross-feature imports introduced
- No router registration changes needed (existing events router)
- Migration in `alembic/versions/` with correct `down_revision` chain

### 6. Docstrings — PASS
- `GoalItem`, `EventGoals` have class-level docstrings
- `make_goals_dict()` factory has docstring
- Migration functions have descriptive docstrings
- No tool/agent functions — no agent-optimized docstrings needed

### 7. Testing — PASS
- 13 new tests (8 service + 5 route) covering: create/update/clear goals, backward compat, schema validation, invalid types
- Edge cases: empty `EventGoals()`, invalid transport/item_type, null goals backward compat
- All tests pass (31/31 feature, 706/706 full suite)

### 8. Security — PASS
- No new endpoints — existing auth + rate limiting covers all paths
- JSONB input validated through Pydantic schema (rejects invalid types, enforces max_length)
- `BodySizeLimitMiddleware` (100KB) bounds maximum payload size
- No SQL injection risk (parameterized via SQLAlchemy)
- No hardcoded secrets or credentials
- Security convention tests pass (105/105)

## Stats

- Files reviewed: 8 (2 production, 1 migration, 3 test, 2 unchanged reference)
- Issues: 5 total — 0 Critical, 0 High, 0 Medium, 5 Low
- Verdict: **Ready to commit**

## Notes

- The zero-touch approach to service/repository/routes is the strongest aspect — leveraging Pydantic + SQLAlchemy JSONB pipeline eliminates an entire class of serialization bugs
- All Low findings are optional improvements, not blocking issues
- SDK regeneration needed post-commit: `cd cms && pnpm --filter @vtv/sdk refresh`
