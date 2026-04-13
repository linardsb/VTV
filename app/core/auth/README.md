# RBAC Scoping (OPS-4.2)

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
