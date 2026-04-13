# Plan: OPS-4.2 Dispatcher-Scoped Query Filters (RBAC Scoping)

## Context

Auth has 4 roles (admin, dispatcher, editor, viewer) but queries are role-checked at the route level only. A dispatcher with scope "routes 1-10" can still read data for routes 11-50 by calling the same endpoint with a different query parameter. This is the biggest authorization gap in the platform.

**Goal:** Add a `RequestScope` dependency that resolves "what routes/vehicles this user may see" from their role + assignments, and inject it into every repository query for data-scoped models.

## Security Context Assessment

| Context | Active | Rationale |
|---------|--------|-----------|
| CTX-AUTH | Yes | New auth dependency (`get_request_scope`), fail-closed semantics |
| CTX-RBAC | Yes | All scoped endpoints get new authorization layer |
| CTX-INPUT | Yes | New assignment CRUD endpoints accept user input |
| CTX-FILE | No | No file handling |
| CTX-AGENT | No | No agent tools |
| CTX-INFRA | No | No Docker/nginx changes |

## Design Decisions

### Scoped entities (3 repositories)

| Entity | Scope mechanism | Notes |
|--------|----------------|-------|
| **Routes** | Direct `Route.id IN (scope.route_ids)` | Cleanest — Route is the scope anchor |
| **Vehicles** | New junction table `vehicle_route_qualifications(vehicle_id, route_id)` | Replaces CSV `qualified_route_ids` for queryable FK |
| **Alerts** | `source_entity_type` + `source_entity_id` resolution | Filter by source route/vehicle membership |

### Deferred (not in this PR)

| Entity | Why deferred |
|--------|-------------|
| **Geofences** | Infrastructure data (depots, terminals, restricted zones) — all dispatchers need visibility regardless of route. No route FK exists. |
| **depot_id** | No `Depot` model exists. Column reserved in migration comment for Phase 2. |
| **Driver-role scoping** | No `User → Driver` FK mapping exists. Document gap, address when driver-role users are onboarded. |

### Scope behavior by role

| Role | `route_ids` | Behavior |
|------|-------------|----------|
| admin | `None` | Unrestricted — all data visible |
| dispatcher | `frozenset({1,2,...})` from assignments | Filtered to assigned routes |
| editor | `None` | Unrestricted (content editors, not ops-scoped) |
| viewer | `None` | Unrestricted read-only (dashboard users) |

### Fail-closed semantics

- If `scope` parameter is missing from a repository read method → `RBACConfigurationError` (HTTP 500)
- Dispatcher with zero assignments → empty result (200), not 403
- `GET /vehicles/{id}` with ID outside scope → 404 (not 403, to avoid info leak)

## Research Summary

### Current auth pattern (`app/auth/dependencies.py:45-144`)
- `get_current_user()` decodes JWT, checks revocation, caches User in TTLCache
- `require_role(*roles)` factory returns dependency checking `user.role in roles`
- User model has `role: String(20)` — no scope fields

### Repository pattern (all features)
- `__init__(self, db: AsyncSession)` → `self.db = db`
- List methods: `async def list(self, *, offset, limit, **filters) -> list[Model]`
- Count methods: mirror list filters, return `int`
- No scope parameter exists on any method

### Service pattern
- `__init__(self, db: AsyncSession)` → creates repo instances
- Service methods call `self.vehicle_repo.list(offset=..., limit=..., **filters)`
- Routes inject `service: Service = Depends(get_service)` + `_current_user: User = Depends(get_current_user)`
- `_current_user` is captured but NOT passed to service/repo

### Key files
- Vehicle model: `app/vehicles/models.py:16-53` — `qualified_route_ids: String(500)` CSV field
- Route model: `app/schedules/models.py:38-56` — `Route.id` is the scope anchor
- Alert model: `app/alerts/models.py:39-81` — `source_entity_type` + `source_entity_id` for polymorphic refs
- Latest migration: `n7o8p9q0r1s2` (head)

## Test Landscape

### Existing fixtures
| Feature | Factory | Location |
|---------|---------|----------|
| Vehicles | `make_vehicle(**overrides)` | `app/vehicles/tests/conftest.py` |
| Schedules | `make_route(**overrides)` | `app/schedules/tests/conftest.py` |
| Alerts | `make_alert_instance(**overrides)` | `app/alerts/tests/conftest.py` |

### Auth mock pattern
```python
app.dependency_overrides[get_current_user] = lambda: _mock_user("admin")
# cleanup in fixture:
app.dependency_overrides.pop(get_current_user, None)
```

### Security convention tests
`app/tests/test_security.py` (1,536 lines, 110 tests) — auto-discovers all endpoints, validates auth.

## Type Check Baseline

| Directory | Pyright | MyPy |
|-----------|---------|------|
| `app/auth/` | 0 | 0 |
| `app/vehicles/` | 0 | 0 |
| `app/schedules/` | 0 | 0 |
| `app/alerts/` | 0 | 0 |
| `app/core/` | 0 | 0 |

**Baseline: 0 errors across all affected directories.**

## Files to Create/Modify

| # | Action | File | Purpose |
|---|--------|------|---------|
| 1 | CREATE | `alembic/versions/o8p9q0r1s2t3_add_dispatcher_assignments.py` | Migration: `dispatcher_assignments` + `vehicle_route_qualifications` tables |
| 2 | CREATE | `app/core/auth/__init__.py` | Package init |
| 3 | CREATE | `app/core/auth/models.py` | `DispatcherAssignment` SQLAlchemy model |
| 4 | CREATE | `app/core/auth/scope.py` | `RequestScope` dataclass + `get_request_scope` dependency |
| 5 | CREATE | `app/core/auth/repository.py` | `AssignmentRepository` for CRUD on assignments |
| 6 | CREATE | `app/core/auth/schemas.py` | Pydantic schemas for assignment CRUD |
| 7 | CREATE | `app/core/auth/routes.py` | Admin endpoints for managing assignments |
| 8 | UPDATE | `app/core/exceptions.py` | Add `RBACConfigurationError` |
| 9 | UPDATE | `app/vehicles/models.py` | Add `VehicleRouteQualification` model |
| 10 | UPDATE | `app/vehicles/repository.py` | Add `scope` param to `get`, `list`, `count` |
| 11 | UPDATE | `app/vehicles/service.py` | Pass `scope` to repo methods |
| 12 | UPDATE | `app/vehicles/routes.py` | Inject `scope: RequestScope` dependency |
| 13 | UPDATE | `app/schedules/repository.py` | Add `scope` param to `list_routes`, `count_routes`, `get_route` |
| 14 | UPDATE | `app/schedules/service.py` | Pass `scope` to repo methods |
| 15 | UPDATE | `app/schedules/routes.py` | Inject `scope: RequestScope` dependency on route-related endpoints |
| 16 | UPDATE | `app/alerts/repository.py` | Add `scope` param to `AlertInstanceRepository.list`, `count` |
| 17 | UPDATE | `app/alerts/service.py` | Pass `scope` to repo methods |
| 18 | UPDATE | `app/alerts/routes.py` | Inject `scope: RequestScope` dependency |
| 19 | UPDATE | `app/main.py` | Register assignments router |
| 20 | CREATE | `app/core/auth/tests/__init__.py` | Test package init |
| 21 | CREATE | `app/core/auth/tests/conftest.py` | Test fixtures: `make_assignment`, `make_scope` |
| 22 | CREATE | `app/core/auth/tests/test_scope.py` | Unit tests for `RequestScope` + `get_request_scope` |
| 23 | CREATE | `app/core/auth/tests/test_routes.py` | Tests for assignment CRUD endpoints |
| 24 | UPDATE | `app/vehicles/tests/test_service.py` | Add scope filtering tests |
| 25 | UPDATE | `app/schedules/tests/test_service.py` | Add scope filtering tests |
| 26 | UPDATE | `app/alerts/tests/test_service.py` | Add scope filtering tests |

## Implementation Steps

### Step 1: Migration — `dispatcher_assignments` + `vehicle_route_qualifications`

**File:** `alembic/versions/o8p9q0r1s2t3_add_dispatcher_assignments.py`
**Action:** CREATE

```python
revision = "o8p9q0r1s2t3"
down_revision = "n7o8p9q0r1s2"
```

Tables to create:

**`dispatcher_assignments`:**
- `id` INTEGER PK AUTOINCREMENT
- `user_id` INTEGER FK → `users.id` ON DELETE CASCADE, NOT NULL
- `route_id` INTEGER FK → `routes.id` ON DELETE CASCADE, NOT NULL
- `assigned_at` TIMESTAMP WITH TZ, NOT NULL, DEFAULT now()
- `assigned_by` INTEGER FK → `users.id` ON DELETE SET NULL, NULLABLE
- UNIQUE(`user_id`, `route_id`) — prevent duplicate assignments
- INDEX on `user_id` — fast scope resolution
- `-- TODO: depot_id INTEGER FK → future depots table (Phase 2)`

**`vehicle_route_qualifications`:**
- `id` INTEGER PK AUTOINCREMENT
- `vehicle_id` INTEGER FK → `vehicles.id` ON DELETE CASCADE, NOT NULL
- `route_id` INTEGER FK → `routes.id` ON DELETE CASCADE, NOT NULL
- UNIQUE(`vehicle_id`, `route_id`)
- INDEX on `vehicle_id`, INDEX on `route_id`

**Validation:** `uv run alembic upgrade head` (requires Docker DB running)

### Step 2: `RBACConfigurationError` exception

**File:** `app/core/exceptions.py`
**Action:** UPDATE — add after `DomainValidationError` (line 29)

```python
class RBACConfigurationError(AppError):
    """Raised when a repository query is executed without required RBAC scope.

    This indicates a programming error — a route handler forgot to inject and
    pass RequestScope to a scoped repository method. Maps to HTTP 500.
    """
    pass
```

No handler registration needed — the base `AppError` handler already maps to 500.

**Validation:** `uv run ruff check app/core/exceptions.py && uv run pyright app/core/exceptions.py`

### Step 3: `RequestScope` dataclass + `get_request_scope` dependency

**File:** `app/core/auth/__init__.py` — empty `__init__.py`
**File:** `app/core/auth/scope.py`
**Action:** CREATE

```python
from __future__ import annotations
from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.database import get_db
from app.core.logging import get_logger

logger = get_logger(__name__)

@dataclass(frozen=True)
class RequestScope:
    user_id: int
    role: str
    route_ids: frozenset[int] | None  # None = unrestricted (admin/editor/viewer)

    @property
    def is_unrestricted(self) -> bool:
        return self.route_ids is None

async def get_request_scope(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RequestScope:
    """Resolve RBAC scope from user role + dispatcher assignments."""
    if current_user.role != "dispatcher":
        # admin, editor, viewer → unrestricted
        logger.info("rbac.scope.resolved", user_id=current_user.id, role=current_user.role, scope="unrestricted")
        return RequestScope(user_id=current_user.id, role=current_user.role, route_ids=None)

    # Dispatcher → load assignments
    from app.core.auth.models import DispatcherAssignment
    result = await db.execute(
        select(DispatcherAssignment.route_id).where(
            DispatcherAssignment.user_id == current_user.id
        )
    )
    route_ids = frozenset(row[0] for row in result.all())
    logger.info("rbac.scope.resolved", user_id=current_user.id, role="dispatcher", route_count=len(route_ids))
    return RequestScope(user_id=current_user.id, role=current_user.role, route_ids=route_ids)
```

**Validation:** `uv run ruff format app/core/auth/ && uv run ruff check app/core/auth/ && uv run pyright app/core/auth/`

### Step 4: `DispatcherAssignment` model

**File:** `app/core/auth/models.py`
**Action:** CREATE

```python
from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.shared.models import TimestampMixin

class DispatcherAssignment(Base, TimestampMixin):
    """Maps a dispatcher user to an assigned route for RBAC scoping."""
    __tablename__ = "dispatcher_assignments"
    __table_args__ = (
        UniqueConstraint("user_id", "route_id", name="uq_dispatcher_assignment"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    route_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("routes.id", ondelete="CASCADE"), nullable=False
    )
    assigned_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
```

**Validation:** `uv run pyright app/core/auth/models.py`

### Step 5: `VehicleRouteQualification` model

**File:** `app/vehicles/models.py`
**Action:** UPDATE — add after `MaintenanceRecord` class (after line 81)

```python
class VehicleRouteQualification(Base, TimestampMixin):
    """Junction table mapping vehicles to qualified routes (replaces CSV field)."""
    __tablename__ = "vehicle_route_qualifications"
    __table_args__ = (
        UniqueConstraint("vehicle_id", "route_id", name="uq_vehicle_route_qual"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    vehicle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    route_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True
    )
```

Add import for `UniqueConstraint` if not already present.

**Validation:** `uv run pyright app/vehicles/models.py`

### Step 6: Assignment CRUD — schemas, repository, routes

**File:** `app/core/auth/schemas.py`
**Action:** CREATE

Schemas:
- `AssignmentCreate(user_id: int, route_id: int)`
- `AssignmentResponse(id, user_id, route_id, assigned_by, assigned_at: datetime, created_at: datetime)`
- `AssignmentBulkCreate(user_id: int, route_ids: list[int])`

**File:** `app/core/auth/repository.py`
**Action:** CREATE

Methods:
- `list_by_user(user_id) -> list[DispatcherAssignment]`
- `create(user_id, route_id, assigned_by) -> DispatcherAssignment`
- `delete(assignment_id) -> None`
- `bulk_replace(user_id, route_ids, assigned_by) -> list[DispatcherAssignment]` — delete all for user, insert new set
- `get_assigned_route_ids(user_id) -> frozenset[int]`

**File:** `app/core/auth/routes.py`
**Action:** CREATE

Endpoints (admin-only, rate-limited):
- `GET /api/v1/admin/assignments?user_id=N` — list assignments for a user
- `POST /api/v1/admin/assignments` — create single assignment
- `PUT /api/v1/admin/assignments/{user_id}` — bulk replace all assignments for a user
- `DELETE /api/v1/admin/assignments/{assignment_id}` — remove single assignment

All require `require_role("admin")`. Rate limit: `10/minute`.

**File:** `app/main.py`
**Action:** UPDATE — register `assignments_router`

**Validation:** `uv run ruff format app/core/auth/ && uv run ruff check app/core/auth/ && uv run pyright app/core/auth/`

### Step 7: Scope injection — Vehicles

**File:** `app/vehicles/repository.py`
**Action:** UPDATE

Add import: `from app.core.auth.scope import RequestScope` and `from app.core.exceptions import RBACConfigurationError`

Add helper method:
```python
def _apply_scope(self, query, scope: RequestScope | None):
    if scope is None:
        raise RBACConfigurationError("RequestScope required for vehicle queries")
    if scope.is_unrestricted:
        return query
    # Filter via junction table
    from app.vehicles.models import VehicleRouteQualification
    subq = select(VehicleRouteQualification.vehicle_id).where(
        VehicleRouteQualification.route_id.in_(scope.route_ids)
    ).scalar_subquery()
    return query.where(Vehicle.id.in_(subq))
```

Update method signatures:
- `get(self, vehicle_id, *, scope: RequestScope | None = None)` — if scope provided and vehicle not in scope, return None
- `list(self, *, scope: RequestScope | None = None, ...)` — apply scope filter
- `count(self, *, scope: RequestScope | None = None, ...)` — apply scope filter

Note: `create`, `update`, `delete` do NOT take scope — they are already role-gated (admin/editor). Only read operations are scoped.

**File:** `app/vehicles/service.py`
**Action:** UPDATE

Add `scope: RequestScope` parameter to:
- `get_vehicle(self, vehicle_id, scope: RequestScope)`
- `list_vehicles(self, pagination, *, scope: RequestScope, ...)`
- `get_maintenance_history(self, vehicle_id, pagination, scope: RequestScope)` — uses `get` to verify access

Pass `scope=scope` to all repo `get`, `list`, `count` calls.

**File:** `app/vehicles/routes.py`
**Action:** UPDATE

Add import: `from app.core.auth.scope import RequestScope, get_request_scope`

On read endpoints (`list_vehicles`, `get_vehicle`, `get_maintenance_history`):
- Change `_current_user: User = Depends(get_current_user)` to `scope: RequestScope = Depends(get_request_scope)`
- Pass `scope=scope` to service methods

Mutation endpoints (`create_vehicle`, `update_vehicle`, `delete_vehicle`, `assign_driver`, `create_maintenance_record`) keep `require_role()` — no scope needed.

**Validation:** `uv run ruff format app/vehicles/ && uv run ruff check app/vehicles/ && uv run pyright app/vehicles/`

### Step 8: Scope injection — Schedules (routes only)

**File:** `app/schedules/repository.py`
**Action:** UPDATE

Add `scope: RequestScope | None = None` to:
- `get_route(self, route_id, *, scope: RequestScope | None = None)` — if scope, verify route_id in scope
- `list_routes(self, *, scope: RequestScope | None = None, ...)` — add `.where(Route.id.in_(scope.route_ids))`
- `count_routes(self, *, scope: RequestScope | None = None, ...)` — same filter

Agency, Calendar, Trip, StopTime methods: NOT scoped (they are sub-entities accessed via route).

**File:** `app/schedules/service.py`
**Action:** UPDATE — add `scope` param to `list_routes`, `get_route`, pass to repo.

**File:** `app/schedules/routes.py`
**Action:** UPDATE — inject `scope: RequestScope` on `list_routes`, `get_route` endpoints. Other schedule endpoints (agencies, trips, calendars) keep `get_current_user` as-is.

**Validation:** `uv run ruff format app/schedules/ && uv run ruff check app/schedules/ && uv run pyright app/schedules/`

### Step 9: Scope injection — Alerts

**File:** `app/alerts/repository.py`
**Action:** UPDATE

Add `scope: RequestScope | None = None` to `AlertInstanceRepository.list` and `AlertInstanceRepository.count`.

Scope filter logic:
```python
if scope is not None and not scope.is_unrestricted:
    # Filter alerts to those whose source entity is within scope
    # Route-sourced alerts: source_entity_type='route' AND source_entity_id IN scope.route_ids
    # Vehicle-sourced alerts: source_entity_type='vehicle' AND vehicle maps to a scoped route
    from app.vehicles.models import VehicleRouteQualification
    vehicle_subq = select(VehicleRouteQualification.vehicle_id).where(
        VehicleRouteQualification.route_id.in_(scope.route_ids)
    ).scalar_subquery()
    query = query.where(
        or_(
            # Route alerts in scope
            sa.and_(
                AlertInstance.source_entity_type == "route",
                sa.cast(AlertInstance.source_entity_id, sa.Integer).in_(scope.route_ids),
            ),
            # Vehicle alerts where vehicle is on a scoped route
            sa.and_(
                AlertInstance.source_entity_type == "vehicle",
                AlertInstance.source_entity_id.in_(
                    select(sa.cast(VehicleRouteQualification.vehicle_id, sa.String)).where(
                        VehicleRouteQualification.route_id.in_(scope.route_ids)
                    ).scalar_subquery()
                ),
            ),
            # Other source types (geofence, feed, etc.) — pass through
            AlertInstance.source_entity_type.not_in(["route", "vehicle"]),
            AlertInstance.source_entity_type.is_(None),
        )
    )
```

**File:** `app/alerts/service.py` — add `scope` param to `list_alerts`, `get_summary`.
**File:** `app/alerts/routes.py` — inject `scope: RequestScope` on `list_alerts`, `get_alert`, `get_summary`, `acknowledge_alert`, `resolve_alert`.

Note: `AlertRule` endpoints remain admin-only, no scope needed.

**Validation:** `uv run ruff format app/alerts/ && uv run ruff check app/alerts/ && uv run pyright app/alerts/`

### Step 10: Audit logging

Already handled in `get_request_scope` (Step 3): `rbac.scope.resolved` emitted on every scope resolution.

Add `rbac.scope.denied` in repository `_apply_scope` when a specific entity is filtered out:
```python
logger.info("rbac.scope.denied", user_id=scope.user_id, entity_type="vehicle", entity_id=vehicle_id)
```

This goes in `VehicleRepository.get` when scope check fails (vehicle not in scope → return None).

### Step 11: Tests

**File:** `app/core/auth/tests/conftest.py`
**Action:** CREATE

```python
def make_scope(*, role: str = "admin", route_ids: frozenset[int] | None = None) -> RequestScope:
    return RequestScope(user_id=1, role=role, route_ids=route_ids)
```

**File:** `app/core/auth/tests/test_scope.py`
**Action:** CREATE — 11 tests

1. `test_admin_scope_is_unrestricted` — admin → `route_ids=None`, `is_unrestricted=True`
2. `test_editor_scope_is_unrestricted` — editor → unrestricted
3. `test_viewer_scope_is_unrestricted` — viewer → unrestricted
4. `test_dispatcher_scope_loads_assignments` — dispatcher with 3 assignments → `route_ids={1,2,3}`
5. `test_dispatcher_empty_assignments` — dispatcher with 0 assignments → `route_ids=frozenset()`
6. `test_scope_is_frozen` — verify dataclass is immutable
7. `test_scope_caching_in_request` — same request gets same scope object (if implemented)
8. `test_rbac_audit_log_fields` — verify `rbac.scope.resolved` includes user_id, role
9. `test_rbac_audit_log_dispatcher` — verify route_count in log for dispatcher
10. `test_scope_depends_on_current_user` — verify dependency chain
11. `test_fail_closed_no_scope_raises` — repo call without scope → `RBACConfigurationError`

**File:** `app/core/auth/tests/test_routes.py`
**Action:** CREATE — 5 tests

1. `test_list_assignments_requires_admin`
2. `test_create_assignment`
3. `test_bulk_replace_assignments`
4. `test_delete_assignment`
5. `test_non_admin_cannot_manage_assignments`

**File:** `app/vehicles/tests/test_service.py`
**Action:** UPDATE — 4 new tests

1. `test_list_vehicles_admin_sees_all` — admin scope → no route filter applied
2. `test_list_vehicles_dispatcher_sees_scoped` — dispatcher scope routes 1-3 → only matching vehicles
3. `test_get_vehicle_outside_scope_returns_not_found` — dispatcher scope → vehicle on route 5 → 404
4. `test_list_vehicles_dispatcher_empty_scope` — empty route_ids → empty result

**File:** `app/schedules/tests/test_service.py`
**Action:** UPDATE — 2 new tests

1. `test_list_routes_dispatcher_sees_scoped` — dispatcher scope → only assigned routes returned
2. `test_get_route_outside_scope_returns_not_found` — route not in scope → 404

**File:** `app/alerts/tests/test_service.py`
**Action:** UPDATE — 2 new tests

1. `test_list_alerts_dispatcher_sees_scoped` — only alerts for scoped routes/vehicles
2. `test_list_alerts_non_route_alerts_pass_through` — geofence/feed alerts visible to all

**Validation:** `uv run pytest app/core/auth/tests/ app/vehicles/tests/ app/schedules/tests/ app/alerts/tests/ -v --tb=short`

## Preflight Warnings

- `app/vehicles/tests/test_routes.py` uses `app.dependency_overrides[get_current_user]` — will need `get_request_scope` override too after Step 7
- `app/alerts/tests/test_routes.py` uses `_mock_user("dispatcher")` for alert access — scope override needed
- `app/tests/test_security.py` auto-discovers all endpoints — new `/api/v1/admin/assignments` endpoints will be auto-tested for auth
- `app/schedules/tests/test_service.py` has 671 lines — add new tests at the end, don't refactor

## Security Checklist

For every new/modified endpoint:
- [ ] `require_role("admin")` on all assignment CRUD endpoints
- [ ] `@limiter.limit("10/minute")` on mutation endpoints
- [ ] Input validation via Pydantic schemas (user_id, route_id as int)
- [ ] Error responses use `AppError` (no internal type leakage)
- [ ] `escape_like()` not needed (no ILIKE queries in assignments)
- [ ] Fail-closed: missing scope → 500, not silent pass
- [ ] No role names in error messages (generic "Insufficient permissions")
- [ ] 200 with empty result for out-of-scope queries (not 403)

## Verification

- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] New assignment endpoints have auth + rate limiting
- [ ] Pyright errors ≤ baseline (0 errors before)
- [ ] Security convention tests pass: `uv run pytest app/tests/test_security.py -v`
- [ ] Dispatcher A (scope routes 1-10) → `GET /v1/vehicles` returns only vehicles on routes 1-10
- [ ] Dispatcher A → `GET /v1/schedules/routes` returns only routes 1-10
- [ ] Admin sees everything (unrestricted scope)
- [ ] Missing `scope` on a new repo method → `RBACConfigurationError` in test
