# Operational Events

Manages time-bounded operational events (maintenance windows, route changes, driver shifts, service alerts) displayed on the dashboard calendar. Events can include structured goals (route assignment, transport type, vehicle number, performance notes, checklist items) stored as JSONB with frontend completion tracking.

## Key Flows

### Create Event

1. Validate input (title required, max 200 chars, start/end datetimes required)
2. Set default priority ("medium") and category ("maintenance") if not provided
3. Persist to `operational_events` table
4. Return event with generated ID and timestamps

### List Events (with date range filter)

1. Parse optional `start_date` and `end_date` query parameters
2. Filter events overlapping the requested date range
3. Return paginated results with total count

### Update Event

1. Look up event by ID — 404 if not found
2. Apply partial update (only provided fields)
3. Return updated event

### Delete Event

1. Look up event by ID — 404 if not found
2. Hard delete from database
3. Return 204 No Content

## Database Schema

Table: `operational_events`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `title` | String(200) | Not null | Event title |
| `description` | Text | Nullable | Event description |
| `start_datetime` | DateTime(tz) | Not null, indexed | Event start (UTC) |
| `end_datetime` | DateTime(tz) | Not null | Event end (UTC) |
| `priority` | String(20) | Not null, default "medium" | high/medium/low |
| `category` | String(30) | Not null, default "maintenance" | maintenance/route-change/driver-shift/service-alert |
| `created_at` | DateTime(tz) | Not null | Auto-set via TimestampMixin |
| `goals` | JSONB | Nullable | Structured goals (EventGoals schema) |
| `updated_at` | DateTime(tz) | Not null | Auto-set via TimestampMixin |

## Goals Schema (JSONB)

The `goals` column stores structured goal data as validated JSONB:

| Field | Type | Description |
|-------|------|-------------|
| `items` | List[GoalItem] | Checklist items (max 100), each with `text` (max 500), `completed` (bool), `item_type` ("custom"/"checklist") |
| `route_id` | int? | Assigned route from driver's qualified routes |
| `transport_type` | string? | "bus", "trolleybus", or "tram" |
| `vehicle_id` | string? | Vehicle number (max 50 chars) |
| `notes` | string? | Performance notes (max 1000 chars) |

Existing events without goals return `goals: null`. The column is nullable with NULL default for backward compatibility.

## Business Rules

1. Title must be 1-200 characters
2. Priority values: "high", "medium", "low" (default: "medium")
3. Category values: "maintenance", "route-change", "driver-shift", "service-alert" (default: "maintenance")
4. Date range filter uses overlap logic — events are included if they overlap with the requested range
5. Hard delete (no soft delete) — operational events are ephemeral by nature
6. Read endpoints (list/get) are public — dashboard calendar fetches from client-side hooks
7. Create/update/delete require admin or editor role
8. PATCH rejects empty bodies — `model_validator(mode="before")` raises if all fields are None
9. Goal items limited to 100 per event, text limited to 500 characters
10. Goals are updated via PATCH — frontend toggles individual goal completion and saves the full goals object

## Integration Points

- **Dashboard (frontend)**: `CalendarPanel` component fetches events via `useCalendarEvents` hook (60s polling, 6-month window)
- **Goal progress badges**: `GoalProgressBadge` component shows completion fraction on calendar event cards (month/three-month views)
- **Goal completion panel**: `EventGoalPanel` dialog allows toggling goal checkboxes, saves via PATCH
- **Driver drop dialog**: Two-step flow for "Assign Shift" and "Schedule Training" — step 2 collects goals via `GoalsForm`
- **Driver roster**: Shows qualified route count, license/medical expiry badges — informs goal setting
- **No cross-feature backend dependencies**: standalone feature with no imports from other `app/{feature}/` directories

## API Endpoints

| Method | Path | Description | Rate Limit |
|--------|------|-------------|------------|
| GET | `/api/v1/events/` | List events (paginated, date range filter) | 30/min |
| GET | `/api/v1/events/{id}` | Get event by ID | 30/min |
| POST | `/api/v1/events/` | Create event (admin/editor) | 10/min |
| PATCH | `/api/v1/events/{id}` | Update event (admin/editor) | 10/min |
| DELETE | `/api/v1/events/{id}` | Delete event (admin/editor) | 10/min |
