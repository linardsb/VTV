# Review: `app/vehicles/`

**Summary:** Solid implementation following established VTV patterns closely. The vertical slice is complete with proper RBAC, rate limiting, structured logging, and comprehensive tests. A few architectural and correctness issues warrant attention — most notably a double-commit in maintenance creation and missing `_failed` logging in one path.

| # | File:Line | Issue | Suggestion | Priority |
|---|-----------|-------|------------|----------|
| 1 | `service.py:275-285` | **Double commit** — `maintenance_repo.create()` commits the record, then service commits again for vehicle side-effects. If the second commit fails, the maintenance record is persisted but vehicle mileage/date is not updated, leaving inconsistent state. | Remove `commit()` from `maintenance_repo.create()` — change it to just `add()` + return, then let the service do a single `commit()` after all mutations. Or move the vehicle side-effects into the repo's `create()`. | High |
| 2 | `service.py:310-314` | **Missing `_failed` log** — `get_maintenance_history` raises `VehicleNotFoundError` without a `logger.warning("vehicles.maintenance_list_failed", ...)` log. Every other not-found path in the service has a warning log before the raise. | Add `logger.warning("vehicles.maintenance_list_failed", vehicle_id=vehicle_id, reason="vehicle_not_found")` before the raise on line 314. | Medium |
| 3 | `service.py:188-190` | **Driver validation via PATCH bypasses unassign** — When `current_driver_id` is explicitly set to `0` or another falsy-but-non-None value via VehicleUpdate, the `isinstance(new_driver_id, int)` check passes but `0` is not a valid driver ID. | Add `ge=1` constraint to `VehicleUpdate.current_driver_id` field in schemas.py, or validate `new_driver_id > 0` in the service. The schema-level fix is cleaner. | Medium |
| 4 | `repository.py:133-146` | **Repository commits directly** — The `create()`, `update()`, and `delete()` methods all commit within the repository. This prevents the service layer from composing multiple repo operations in a single transaction (e.g., create vehicle + assign driver atomically). | Consider a "unit of work" pattern where the service controls commits. For now this matches the existing drivers/stops pattern, so it's consistent but worth noting for future refactoring. | Low |
| 5 | `schemas.py:108` | **Response inherits from Create** — `MaintenanceRecordResponse` inherits from `MaintenanceRecordCreate`. This means all Create validators (e.g., future `@field_validator`) would also apply to responses, which may cause issues with legacy data. | Create a separate `MaintenanceRecordBase` with shared fields, then have both `Create` and `Response` inherit from it. Matches the `VehicleBase` → `VehicleCreate` / `VehicleResponse` pattern used for vehicles. | Medium |
| 6 | `routes.py:37` | **Query param `status` uses bare `str`** — The `vehicle_status` query param accepts any string, but the model column only accepts `active`, `inactive`, `maintenance`. Invalid values silently return empty results. | Use `Query(None, pattern="^(active\|inactive\|maintenance)$")` or define it as `VehicleStatus \| None` to get Pydantic validation at the API boundary. Same for `vehicle_type`. | Medium |
| 7 | `models.py:33` | **No check constraint on `status`** — The database accepts any string up to 20 chars for `vehicle_type` and `status` columns. A malformed API bypass (or direct DB insert) could insert invalid values. | Add `CheckConstraint("status IN ('active', 'inactive', 'maintenance')")` and similar for `vehicle_type`. Defense in depth. | Low |
| 8 | `test_routes.py:37-42` | **Auth override in autouse fixture doesn't save/restore** — The fixture overrides `get_current_user` but individual tests also override `get_service` with manual try/finally. The `get_current_user` override in the autouse fixture could leak if a test adds `require_role` overrides. | This matches the existing drivers test pattern, so it's consistent. But the `_setup_auth_override` fixture should also save and restore any pre-existing `get_current_user` override. Minor risk since tests run in isolation. | Low |
| 9 | `test_service.py:153-170` | **MonkeyPatch for DriverRepository** — Tests patch `app.vehicles.service.DriverRepository` with a lambda factory. This is fragile — renaming the import breaks the test silently (returns a mock that doesn't raise). | Consider injecting DriverRepository as a service dependency or using `unittest.mock.patch` with `autospec=True` for stronger type safety. | Low |
| 10 | `service.py:278` | **Mileage comparison trusts input** — `data.mileage_at_service > vehicle.mileage_km` doesn't guard against rollback scenarios (e.g., correcting a wrong entry with a lower mileage). The vehicle's mileage can only increase, never decrease. | This is a reasonable business rule (mileage only goes up). Just ensure it's documented. If correction is needed, it requires a direct vehicle update via PATCH. | Low |

## Standards Compliance

### 1. Type Safety — PASS
All functions have complete type annotations. `Any` usage in `reject_empty_body` is justified with `# noqa: ANN401` (matches existing pattern). Pyright directive at file level for schemas is consistent with events feature.

### 2. Pydantic Schemas — PASS (with note)
Schemas are complete. `VehicleUpdate` has `reject_empty_body` validator. `Literal` types used for constrained strings. One structural issue: `MaintenanceRecordResponse` inherits from `MaintenanceRecordCreate` rather than a shared base (issue #5).

### 3. Structured Logging — PASS (with note)
All actions have `_started` and `_completed`/`_failed` pairs except `get_maintenance_history` (issue #2). Logger uses `get_logger(__name__)`. Events follow `vehicles.action_state` pattern.

### 4. Database Patterns — PASS
Async/await used consistently. `select()` style throughout. Models inherit `Base` and `TimestampMixin`. `get_db()` dependency in routes. `escape_like()` used for ILIKE patterns.

### 5. Architecture — PASS
Vertical slice boundaries respected. Cross-feature read (DriverRepository) follows guidelines. Router registered in `app/main.py`. Complete feature structure.

### 6. Docstrings — PASS
All functions have Google-style docstrings with Args, Returns, and Raises sections.

### 7. Testing — PASS
30 tests (16 service + 14 routes) all passing. Edge cases covered: not found, duplicates, driver assignment conflicts, unassign, maintenance with mileage side-effects. Missing: empty body PATCH rejection test, RBAC permission tests (e.g., viewer can't create).

### 8. Security — PASS
- `escape_like()` used for ILIKE queries
- All endpoints have auth dependencies (verified by `TestAllEndpointsRequireAuth`)
- Query params have `max_length` constraints
- Rate limiting on all endpoints
- No hardcoded secrets

**Stats:**
- Files reviewed: 9 (schemas, models, exceptions, repository, service, routes, conftest, test_service, test_routes)
- Issues: 10 total — 0 Critical, 1 High, 4 Medium, 5 Low
