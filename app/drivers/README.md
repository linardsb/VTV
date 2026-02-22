# Driver Management

Manage driver profiles, shift assignments, licensing, and qualifications for transit operations. Replaces the hardcoded mock data in the agent tool with real database-backed CRUD.

## Key Flows

### Create Driver

1. Validate input (required: `first_name`, `last_name`, `employee_number`)
2. Check `employee_number` uniqueness — reject with 422 if duplicate
3. Persist to `drivers` table with defaults (`status="available"`, `default_shift="morning"`, `is_active=True`)
4. Return `DriverResponse` (201)

### List Drivers (with Filters)

1. Parse query params: `search`, `status`, `shift`, `active_only`, pagination
2. Search matches against `first_name`, `last_name`, `employee_number` (case-insensitive `ILIKE`)
3. Filter by `status`, `shift`, `is_active`
4. Order by `last_name, first_name`
5. Return `PaginatedResponse[DriverResponse]` with total count

### Agent Availability Query

1. Agent tool calls `get_drivers_for_availability(shift, route_id)`
2. Service queries `DriverRepository.list_for_agent()` — active drivers only
3. Optional filters: `shift` (exact match), `route_id` (substring in comma-separated `qualified_route_ids`)
4. Returns list formatted for agent tool consumption
5. Falls back to mock data if DB unavailable

## Database Schema

Table: `drivers`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `employee_number` | String(20) | Unique, not null, indexed | HR identifier (e.g., "DRV-001") |
| `first_name` | String(100) | Not null, indexed | Given name |
| `last_name` | String(100) | Not null, indexed | Family name |
| `date_of_birth` | Date | Nullable | Date of birth |
| `phone` | String(30) | Nullable | Contact phone |
| `email` | String(200) | Nullable | Contact email |
| `address` | Text | Nullable | Home address |
| `emergency_contact_name` | String(200) | Nullable | Emergency contact |
| `emergency_contact_phone` | String(30) | Nullable | Emergency phone |
| `photo_url` | String(500) | Nullable | Profile photo URL |
| `hire_date` | Date | Nullable | Employment start date |
| `license_categories` | String(50) | Nullable | Comma-separated: "D,D1,DE" |
| `license_expiry_date` | Date | Nullable | License validity |
| `medical_cert_expiry` | Date | Nullable | Medical certificate validity |
| `qualified_route_ids` | Text | Nullable | Comma-separated GTFS route IDs |
| `default_shift` | String(20) | Not null, default="morning" | morning/afternoon/evening/night |
| `status` | String(20) | Not null, default="available" | available/on_duty/on_leave/sick |
| `notes` | Text | Nullable | Free-text notes |
| `training_records` | Text | Nullable | Training history |
| `is_active` | Boolean | Not null, default=True | Soft delete flag |
| `created_at` | DateTime | Not null | Auto-set on create |
| `updated_at` | DateTime | Not null | Auto-set on update |

## Business Rules

1. `employee_number` must be unique across all drivers
2. `first_name` and `last_name` are required (min 1, max 100 chars)
3. `default_shift` must be one of: morning, afternoon, evening, night
4. `status` must be one of: available, on_duty, on_leave, sick
5. Deletion is hard delete (not soft delete via `is_active`)
6. `license_categories` and `qualified_route_ids` stored as comma-separated strings
7. Agent tool queries only return active drivers (`is_active=True`)

## Integration Points

- **Agent Tool (`check_driver_availability`)**: Queries drivers from DB via `get_db_context()` standalone session. Falls back to mock data when DB is unavailable
- **CMS Frontend**: Full CRUD page at `/[locale]/drivers` with table, filters, forms, and detail view
- **RBAC**: All roles can view drivers; write operations restricted to admin/editor in frontend

## API Endpoints

| Method | Path | Description | Rate Limit |
|--------|------|-------------|------------|
| GET | `/api/v1/drivers/` | List drivers (paginated, filterable) | 30/min |
| GET | `/api/v1/drivers/{driver_id}` | Get driver by ID | 30/min |
| POST | `/api/v1/drivers/` | Create a new driver | 10/min |
| PATCH | `/api/v1/drivers/{driver_id}` | Update driver fields | 10/min |
| DELETE | `/api/v1/drivers/{driver_id}` | Delete a driver | 10/min |
