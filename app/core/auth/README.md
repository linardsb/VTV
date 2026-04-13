# RBAC Scoping (OPS-4.2) & Authorization Audit Log (OPS-4.3)

Dispatcher-scoped query filters that restrict data visibility based on user role and route assignments. Dispatchers only see data for their assigned routes; admin/editor/viewer roles see everything.

## Key Flows

### Scope Resolution

1. `get_request_scope` FastAPI dependency chains through `get_current_user` (JWT auth)
2. Non-dispatcher roles (admin, editor, viewer) get `RequestScope(route_ids=None)` (unrestricted)
3. Dispatchers: query `dispatcher_assignments` table for assigned route IDs
4. Returns `RequestScope(route_ids=frozenset({1, 2, ...}))` for dispatchers

### Scope Injection

1. Route handler declares `scope: RequestScope = Depends(get_request_scope)`
2. Service method receives scope, passes to repository
3. Repository applies scope filter: `WHERE route_id IN (scope.route_ids)` or subquery via junction table
4. Dispatcher with 0 assignments gets empty result (200), not 403

### Assignment Management (Admin-only)

1. Admin creates/deletes assignments via `/api/v1/admin/assignments`
2. Bulk replace: `PUT /{user_id}` replaces all assignments atomically
3. Assignments cascade on user/route deletion

## Database Schema

Table: `dispatcher_assignments`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `user_id` | Integer | FK users.id CASCADE, indexed | Dispatcher user |
| `route_id` | Integer | FK routes.id CASCADE | Assigned route |
| `assigned_by` | Integer | FK users.id SET NULL, nullable | Admin who created |
| `created_at` | DateTime | Not null | Auto-set on create |
| `updated_at` | DateTime | Not null | Auto-set on update |

Unique constraint: `(user_id, route_id)`

Table: `vehicle_route_qualifications`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `vehicle_id` | Integer | FK vehicles.id CASCADE, indexed | Vehicle |
| `route_id` | Integer | FK routes.id CASCADE, indexed | Qualified route |
| `created_at` | DateTime | Not null | Auto-set on create |
| `updated_at` | DateTime | Not null | Auto-set on update |

Unique constraint: `(vehicle_id, route_id)`

## Business Rules

1. **Fail-closed**: Missing scope on `list()`/`count()` raises `RBACConfigurationError` (500)
2. **404 not 403**: Out-of-scope `get()` returns None (404) to avoid info leak
3. **Empty result**: Dispatcher with 0 assignments gets 200 with empty list
4. **Read-only scoping**: Only read operations (`get`, `list`, `count`) are scoped; mutations (`create`, `update`, `delete`) use `require_role` only
5. **Scope by role**: admin=unrestricted, dispatcher=assigned routes, editor=unrestricted, viewer=unrestricted

## Integration Points

- **auth**: `get_request_scope` depends on `get_current_user` from `app.auth.dependencies`
- **vehicles**: `VehicleRepository.get/list/count` accept `scope` param; scope filters via `vehicle_route_qualifications` junction table
- **schedules**: `ScheduleRepository.get_route/list_routes/count_routes` accept `scope` param; direct `Route.id IN scope.route_ids`
- **alerts**: `AlertInstanceRepository.list/count` accept `scope` param; filters by `source_entity_type` (route direct, vehicle via junction, other passthrough)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/admin/assignments?user_id=N` | List assignments for a user |
| POST | `/api/v1/admin/assignments` | Create single assignment |
| PUT | `/api/v1/admin/assignments/{user_id}` | Bulk replace all assignments |
| DELETE | `/api/v1/admin/assignments/{assignment_id}` | Delete single assignment |

All endpoints require `admin` role. Rate limited: 30/min (list), 10/min (mutations).

---

## Authorization Audit Log (OPS-4.3)

Persists authorization denial events (401, 403, 429) to a TimescaleDB hypertable for compliance audit trails and breach investigation. Every auth denial emits a structured `auth.audit.denied` log event and a fire-and-forget DB write.

### Key Flows

#### Denial Capture

1. Auth dependency (`get_current_user`, `require_role`) or rate limit handler detects denial
2. Calls `emit_auth_denial()` with request context, reason, enforcement layer
3. Structured log event emitted immediately (always, regardless of feature flag)
4. If `auth_audit_enabled=True`: background `asyncio.create_task` persists to DB via standalone session
5. DB write failures are logged at DEBUG, never propagated (fire-and-forget)

#### Admin Query

1. Admin calls `GET /api/v1/admin/audit/auth` with optional filters
2. `AuthAuditRepository` builds filtered query (user_id, date range, enforcement_layer)
3. Returns paginated results via `PaginatedResponse[AuthAuditEventResponse]`

### Database Schema

Table: `auth_audit_events` (TimescaleDB hypertable, daily chunks)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | BigInteger | PK, autoincrement | Primary key |
| `recorded_at` | DateTime(tz) | Not null, indexed, server_default=now() | Event timestamp (hypertable time column) |
| `request_id` | String(64) | Not null | Correlation ID |
| `user_id` | Integer | Nullable, indexed | User who was denied (null for missing credentials) |
| `path` | String(512) | Not null | Request path |
| `method` | String(10) | Not null | HTTP method |
| `status_code` | SmallInteger | Not null | 401, 403, or 429 |
| `reason` | String(255) | Not null | Machine-readable reason (e.g., `token_revoked`, `role_required:admin`) |
| `enforcement_layer` | String(50) | Not null | `jwt`, `role`, `scope`, or `rate_limit` |
| `client_ip` | String(45) | Nullable | Client IP address |
| `user_role` | String(20) | Nullable | User's role at time of denial |
| `extra` | JSONB | Nullable | Additional context (PII-sanitized) |

Composite index: `(user_id, recorded_at DESC)`

TimescaleDB policies: 7-day compression, 90-day retention.

No `TimestampMixin` — immutable append-only table uses `recorded_at` as time column.

### Denial Hook Points

| Hook | File | Status Code | Reason | Layer |
|------|------|-------------|--------|-------|
| Missing credentials | `app/auth/dependencies.py` | 401 | `missing_credentials` | `jwt` |
| Invalid/expired JWT | `app/auth/dependencies.py` | 401 | `token_invalid_or_expired` | `jwt` |
| Token revoked | `app/auth/dependencies.py` | 401 | `token_revoked` | `jwt` |
| User not found | `app/auth/dependencies.py` | 401 | `user_not_found` | `jwt` |
| Inactive account | `app/auth/dependencies.py` | 403 | `account_inactive` | `jwt` |
| Role check failure | `app/auth/dependencies.py` | 403 | `role_required:{roles}` | `role` |
| Rate limit exceeded | `app/core/rate_limit.py` | 429 | `rate_limit_exceeded:{detail}` | `rate_limit` |

### Business Rules

1. **Always log**: Structured log emitted even when `auth_audit_enabled=False`
2. **Fire-and-forget**: DB write never blocks or fails the request
3. **PII sanitized**: `password`, `token`, `authorization`, `cookie`, `secret`, `api_key` stripped from `extra` dict
4. **Standalone session**: Audit writes use `get_db_context()`, not the request's transaction
5. **Feature-flagged**: DB persistence controlled by `auth_audit_enabled` (default `True`)

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `auth_audit_enabled` | `True` | Enable DB persistence of audit events |
| `auth_audit_retention_days` | `90` | TimescaleDB retention policy (days) |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/admin/audit/auth` | Query audit events (paginated, filtered) |

Query parameters: `from` (datetime), `to` (datetime), `user_id` (int), `enforcement_layer` (Literal: jwt, role, scope, rate_limit), `page` (int), `page_size` (int).

Requires `admin` role. Rate limited: 30/min.
