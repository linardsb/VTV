# Operational Events

Manages time-bounded operational events (maintenance windows, route changes, driver shifts, service alerts) displayed on the dashboard calendar.

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
| `updated_at` | DateTime(tz) | Not null | Auto-set via TimestampMixin |

## Business Rules

1. Title must be 1-200 characters
2. Priority values: "high", "medium", "low" (default: "medium")
3. Category values: "maintenance", "route-change", "driver-shift", "service-alert" (default: "maintenance")
4. Date range filter uses overlap logic — events are included if they overlap with the requested range
5. Hard delete (no soft delete) — operational events are ephemeral by nature
6. Read endpoints (list/get) are public — dashboard calendar fetches from client-side hooks
7. Create/update/delete require admin or editor role
8. PATCH rejects empty bodies — `model_validator(mode="before")` raises if all fields are None

## Integration Points

- **Dashboard (frontend)**: `CalendarPanel` component fetches events via `useCalendarEvents` hook (60s polling, 6-month window)
- **No cross-feature backend dependencies**: standalone feature with no imports from other `app/{feature}/` directories

## API Endpoints

| Method | Path | Description | Rate Limit |
|--------|------|-------------|------------|
| GET | `/api/v1/events/` | List events (paginated, date range filter) | 30/min |
| GET | `/api/v1/events/{id}` | Get event by ID | 30/min |
| POST | `/api/v1/events/` | Create event (admin/editor) | 10/min |
| PATCH | `/api/v1/events/{id}` | Update event (admin/editor) | 10/min |
| DELETE | `/api/v1/events/{id}` | Delete event (admin/editor) | 10/min |
