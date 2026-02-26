# Plan: Calendar "Created By" Column

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Medium
**Primary Systems Affected**: schedules (backend model/service/routes/repository), schedules (frontend table/types/i18n), database migration

## Feature Description

Add a "Created By" column to the calendar table in the Schedules page that displays the name of the user who created each calendar. Currently the calendar table shows Service ID, day indicators, date range, status, and a "Created" timestamp — but there is no indication of WHO created the calendar.

The backend Calendar model already has a `created_by_id` foreign key column defined in the ORM (pointing to `users.id` with `ondelete="SET NULL"`), and the `CalendarResponse` schema already includes `created_by_id: int | None` and `created_by_name: str | None` fields. However, the wiring is incomplete: the column is missing from the database migration, the service layer doesn't set `created_by_id` when creating calendars, the routes don't pass the authenticated user to the service, and the repository doesn't JOIN to fetch the user's name.

On the frontend, the TypeScript `Calendar` type is missing both fields, and the table has no column for "Created By".

This plan completes the full vertical wiring: migration, repository JOIN, service user capture, route user passing, frontend types, i18n, and table column.

## User Story

As an admin or editor managing service calendars,
I want to see who created each calendar in the table,
So that I can track accountability and know who to contact about specific calendar configurations.

## Solution Approach

We chose a LEFT JOIN approach in the repository's list/get methods to resolve `created_by_id` into a user name. The Calendar model already has the FK column; we add a `relationship()` to eagerly load the user's name. The `CalendarResponse` schema already has `created_by_name` — we just need to populate it via a model property.

**Approach Decision:**
We chose to add a `relationship()` + `@property` on the Calendar model because:
- SQLAlchemy `selectinload`/`joinedload` efficiently loads related data in list queries
- The `created_by_name` is a simple derived value (user.name) — no complex computation
- The `from_attributes=True` on CalendarResponse automatically reads model properties

**Alternatives Considered:**
- **Separate API call to fetch user names**: Rejected because it adds N+1 network calls on the frontend
- **Denormalized `created_by_name` column in calendars table**: Rejected because it diverges from the user's actual name if updated later
- **Computed field on schema level**: Rejected because the schema doesn't have DB session access

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/schedules/models.py` (lines 49-69) — Calendar model with existing `created_by_id` FK
- `app/schedules/schemas.py` (lines 137-156) — CalendarResponse with `created_by_id` and `created_by_name` fields already declared
- `app/schedules/service.py` (lines 276-301) — `create_calendar()` method that needs `user_id` parameter
- `app/schedules/routes.py` (lines 169-179) — `create_calendar` endpoint with `_current_user` available but unused
- `app/schedules/repository.py` (lines 258-320) — `create_calendar()`, `list_calendars()`, `get_calendar()` methods
- `app/auth/models.py` (lines 12-30) — User model with `name` field (line 24)

### Similar Features (Examples to Follow)
- `app/skills/models.py` — AgentSkill model has `created_by_id` FK + relationship pattern
- `alembic/versions/96fe33fb032c_add_agent_skills_table.py` (lines 33, 36) — Migration pattern for `created_by_id` + FK constraint

### Files to Modify
- `app/schedules/models.py` — Add relationship to User
- `app/schedules/repository.py` — Add joinedload for creator in list/get queries
- `app/schedules/service.py` — Accept user_id param in create_calendar
- `app/schedules/routes.py` — Pass current_user.id to service
- `alembic/versions/` — New migration for created_by_id column
- `app/schedules/tests/conftest.py` — Update make_calendar factory
- `app/schedules/tests/test_service.py` — Update create_calendar tests
- `cms/apps/web/src/types/schedule.ts` — Add created_by fields to Calendar type
- `cms/apps/web/src/components/schedules/calendar-table.tsx` — Add "Created By" column
- `cms/apps/web/messages/en.json` — Add createdBy i18n key
- `cms/apps/web/messages/lv.json` — Add createdBy i18n key

## Implementation Plan

### Phase 1: Database Migration
Add the `created_by_id` column to the calendars table with FK to users.id.

### Phase 2: Backend Wiring
Add relationship on model, update repository queries with joinedload, update service to accept user_id, update routes to pass current_user.

### Phase 3: Frontend Display
Update TypeScript types, add i18n keys, add table column.

### Phase 4: Tests
Update test factories and service tests to cover the new behavior.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

### Task 1: Create Database Migration
**File:** `alembic/versions/{auto}_add_created_by_id_to_calendars.py` (create new)
**Action:** CREATE

Generate an Alembic migration to add the `created_by_id` column to the existing `calendars` table.

**If database is running (Docker containers up):**
```bash
uv run alembic revision --autogenerate -m "add created_by_id to calendars"
```

Review the generated migration to ensure it contains:
- `op.add_column('calendars', sa.Column('created_by_id', sa.Integer(), nullable=True))`
- `op.create_foreign_key(None, 'calendars', 'users', ['created_by_id'], ['id'], ondelete='SET NULL')`

Then apply:
```bash
uv run alembic upgrade head
```

**If database is NOT running (manual fallback):**
Create a migration file manually with:
- `created_by_id`: `sa.Integer()`, nullable=True (existing calendars will have NULL)
- Foreign key: `calendars.created_by_id` -> `users.id`, ondelete="SET NULL"
- Downgrade: drop FK constraint, then drop column

**Per-task validation:**
- Migration file exists and has correct upgrade/downgrade
- `uv run alembic upgrade head` completes (if DB running)

---

### Task 2: Add Relationship to Calendar Model
**File:** `app/schedules/models.py` (modify existing)
**Action:** UPDATE

Add a SQLAlchemy `relationship()` to the Calendar model to load the creator user, and a property to expose the name.

1. Add import at top of file:
   ```python
   from sqlalchemy.orm import Mapped, mapped_column, relationship
   ```
   (Add `relationship` to the existing import from `sqlalchemy.orm`)

2. Add after the `created_by_id` field (line 69), inside the Calendar class:
   ```python
   creator: Mapped["User | None"] = relationship(
       "User", foreign_keys=[created_by_id], lazy="joined"
   )

   @property
   def created_by_name(self) -> str | None:
       """Return the creator's name, or None if no creator is set."""
       return self.creator.name if self.creator else None
   ```

Note: Using `lazy="joined"` so that the creator is always loaded with the calendar in a single query. The string `"User"` avoids circular imports (forward reference resolved by SQLAlchemy at runtime). Do NOT import User directly.

**Per-task validation:**
- `uv run ruff format app/schedules/models.py`
- `uv run ruff check --fix app/schedules/models.py` passes
- `uv run mypy app/schedules/models.py` passes with 0 errors
- `uv run pyright app/schedules/models.py` passes

---

### Task 3: Update Service to Accept User ID on Calendar Creation
**File:** `app/schedules/service.py` (modify existing)
**Action:** UPDATE

Update `create_calendar()` to accept an optional `user_id` parameter and set it on the Calendar model before saving.

1. Change the `create_calendar` method signature (line 276):
   ```python
   async def create_calendar(
       self, data: CalendarCreate, *, user_id: int | None = None
   ) -> CalendarResponse:
   ```

2. Update the Calendar construction (line 294) to include `created_by_id`:
   ```python
   calendar = Calendar(**data.model_dump(), created_by_id=user_id)
   ```

3. Add `user_id` to the structured log (line 296-300):
   ```python
   logger.info(
       "schedules.calendar.create_completed",
       calendar_id=calendar.id,
       gtfs_service_id=calendar.gtfs_service_id,
       created_by_id=user_id,
   )
   ```

No other methods need changes — `list_calendars`, `get_calendar`, `update_calendar` will automatically return `created_by_name` from the model relationship.

**Per-task validation:**
- `uv run ruff format app/schedules/service.py`
- `uv run ruff check --fix app/schedules/service.py` passes
- `uv run mypy app/schedules/service.py` passes with 0 errors
- `uv run pyright app/schedules/service.py` passes

---

### Task 4: Update Route to Pass Current User ID to Service
**File:** `app/schedules/routes.py` (modify existing)
**Action:** UPDATE

Update the `create_calendar` endpoint (lines 169-179) to pass the authenticated user's ID to the service.

1. Change the parameter name from `_current_user` to `current_user` (removing the underscore since we now use it):
   ```python
   @router.post("/calendars", response_model=CalendarResponse, status_code=status.HTTP_201_CREATED)
   @limiter.limit("10/minute")
   async def create_calendar(
       request: Request,
       data: CalendarCreate,
       service: ScheduleService = Depends(get_service),  # noqa: B008
       current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
   ) -> CalendarResponse:
       """Create a new service calendar."""
       _ = request
       return await service.create_calendar(data, user_id=current_user.id)
   ```

**Per-task validation:**
- `uv run ruff format app/schedules/routes.py`
- `uv run ruff check --fix app/schedules/routes.py` passes
- `uv run mypy app/schedules/routes.py` passes with 0 errors
- `uv run pyright app/schedules/routes.py` passes

---

### Task 5: Update Test Factories to Include created_by_id
**File:** `app/schedules/tests/conftest.py` (modify existing)
**Action:** UPDATE

Update the `make_calendar` factory (lines 71-97) to include `created_by_id` in defaults:

1. Add `"created_by_id": None,` to the defaults dict (after `"end_date"`):
   ```python
   defaults: dict[str, object] = {
       "id": 1,
       "gtfs_service_id": "weekday_1",
       "monday": True,
       "tuesday": True,
       "wednesday": True,
       "thursday": True,
       "friday": True,
       "saturday": False,
       "sunday": False,
       "start_date": date(2026, 1, 1),
       "end_date": date(2026, 12, 31),
       "created_by_id": None,
       "created_at": now,
       "updated_at": now,
   }
   ```

**Per-task validation:**
- `uv run ruff format app/schedules/tests/conftest.py`
- `uv run ruff check --fix app/schedules/tests/conftest.py` passes

---

### Task 6: Update Service Tests for create_calendar with user_id
**File:** `app/schedules/tests/test_service.py` (modify existing)
**Action:** UPDATE

Update `test_create_calendar_success` (lines 154-173) to test the `user_id` parameter:

1. Update the existing test to pass `user_id`:
   ```python
   @pytest.mark.asyncio
   async def test_create_calendar_success(service):
       data = CalendarCreate(
           gtfs_service_id="weekday_1",
           monday=True,
           tuesday=True,
           wednesday=True,
           thursday=True,
           friday=True,
           saturday=False,
           sunday=False,
           start_date=date(2026, 1, 1),
           end_date=date(2026, 12, 31),
       )
       calendar = make_calendar(created_by_id=42)
       service.repository.get_calendar_by_gtfs_id = AsyncMock(return_value=None)
       service.repository.create_calendar = AsyncMock(return_value=calendar)

       result = await service.create_calendar(data, user_id=42)
       assert result.gtfs_service_id == "weekday_1"
       assert result.created_by_id == 42
   ```

2. Add a new test for calendar creation WITHOUT user_id (GTFS import path):
   ```python
   @pytest.mark.asyncio
   async def test_create_calendar_without_user(service):
       """Calendar created without user_id (e.g. GTFS import) has created_by_id=None."""
       data = CalendarCreate(
           gtfs_service_id="weekend_1",
           monday=False,
           tuesday=False,
           wednesday=False,
           thursday=False,
           friday=False,
           saturday=True,
           sunday=True,
           start_date=date(2026, 1, 1),
           end_date=date(2026, 12, 31),
       )
       calendar = make_calendar(gtfs_service_id="weekend_1", created_by_id=None)
       service.repository.get_calendar_by_gtfs_id = AsyncMock(return_value=None)
       service.repository.create_calendar = AsyncMock(return_value=calendar)

       result = await service.create_calendar(data)
       assert result.created_by_id is None
       assert result.created_by_name is None
   ```

**Per-task validation:**
- `uv run ruff format app/schedules/tests/test_service.py`
- `uv run ruff check --fix app/schedules/tests/test_service.py` passes
- `uv run pytest app/schedules/tests/test_service.py -v` — all tests pass

---

### Task 7: Update Frontend TypeScript Types
**File:** `cms/apps/web/src/types/schedule.ts` (modify existing)
**Action:** UPDATE

Add `created_by_id` and `created_by_name` fields to the `Calendar` interface (lines 31-45):

```typescript
/** Calendar — service schedule (days of week + date range) */
export interface Calendar {
  id: number;
  gtfs_service_id: string;
  monday: boolean;
  tuesday: boolean;
  wednesday: boolean;
  thursday: boolean;
  friday: boolean;
  saturday: boolean;
  sunday: boolean;
  start_date: string;
  end_date: string;
  created_by_id: number | null;
  created_by_name: string | null;
  created_at: string;
  updated_at: string;
}
```

Add the two new fields (`created_by_id` and `created_by_name`) after `end_date` and before `created_at`.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes (run from `cms/` directory)

---

### Task 8: Add i18n Keys for "Created By"
**File:** `cms/apps/web/messages/en.json` AND `cms/apps/web/messages/lv.json` (modify existing)
**Action:** UPDATE

**English (en.json):** Add `"createdBy": "Created by"` to the `schedules.calendars` section, right after the existing `"createdAt": "Created"` key (around line 278):

```json
"createdAt": "Created",
"createdBy": "Created by",
```

**Latvian (lv.json):** Add `"createdBy": "Izveidoja"` to the `schedules.calendars` section, right after the existing `"createdAt": "Izveidots"` key:

```json
"createdAt": "Izveidots",
"createdBy": "Izveidoja",
```

**Per-task validation:**
- JSON files are valid (no trailing commas, proper syntax)
- Both files have the `createdBy` key in the `schedules.calendars` section

---

### Task 9: Add "Created By" Column to Calendar Table
**File:** `cms/apps/web/src/components/schedules/calendar-table.tsx` (modify existing)
**Action:** UPDATE

Add a new column after the Status column and before the Created (timestamp) column. The column should:
- Show at `xl` breakpoint (same as createdAt)
- Display `cal.created_by_name` or a dash if null
- Use the same text styling as the createdAt column

1. Add a new `<TableHead>` in the header section, between the Status header (line 109) and the createdAt header (line 110):
   ```tsx
   <TableHead className="hidden xl:table-cell">{t("createdBy")}</TableHead>
   ```

2. Add a corresponding skeleton cell in the loading state, between the Status skeleton (line 127) and createdAt skeleton (line 128):
   ```tsx
   <TableCell className="hidden xl:table-cell"><Skeleton className="h-5 w-24" /></TableCell>
   ```

3. Add a data cell in the calendar rows, between the Status cell (lines 147-149) and the createdAt cell (lines 150-152):
   ```tsx
   <TableCell className="hidden xl:table-cell text-foreground-muted text-sm whitespace-nowrap">
     {cal.created_by_name || "-"}
   </TableCell>
   ```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes (from `cms/` directory)
- `pnpm --filter @vtv/web lint` passes (from `cms/` directory)

---

### Task 10: Full Backend Validation
**Action:** VALIDATE

Run the full backend validation pyramid:

**Level 1: Syntax & Style**
```bash
uv run ruff format .
uv run ruff check --fix .
```

**Level 2: Type Safety**
```bash
uv run mypy app/
uv run pyright app/
```

**Level 3: Feature Tests**
```bash
uv run pytest app/schedules/tests/ -v
```

**Level 4: Full Test Suite**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Health (if Docker running)**
```bash
curl -s http://localhost:8123/health
```

All levels must pass with 0 errors.

---

## Migration

**Prefer autogenerate when database is running:**
```bash
uv run alembic revision --autogenerate -m "add created_by_id to calendars"
uv run alembic upgrade head
```

**When database may not be running (manual fallback):**
Create migration manually with:
- Column: `created_by_id`, type=`sa.Integer()`, nullable=True
- Foreign key: `calendars.created_by_id` -> `users.id`, ondelete="SET NULL"
- Downgrade: drop FK, drop column

## Logging Events

- `schedules.calendar.create_completed` — Now includes `created_by_id` (the user ID who created the calendar)

## Testing Strategy

### Unit Tests
**Location:** `app/schedules/tests/test_service.py`
- `test_create_calendar_success` — Updated to verify `created_by_id` is set and `user_id` is passed
- `test_create_calendar_without_user` — New: verifies GTFS import path works without user_id

### Edge Cases
- Calendar created via GTFS import — `created_by_id` is NULL, `created_by_name` is NULL
- Calendar created via API — `created_by_id` is set, `created_by_name` shows user's name
- Creator user deleted — `created_by_id` becomes NULL (FK ondelete=SET NULL), `created_by_name` shows NULL
- Frontend display — NULL `created_by_name` shows "-" in the table

## Acceptance Criteria

This feature is complete when:
- [ ] `created_by_id` column exists in the `calendars` database table
- [ ] Creating a calendar via the API stores the authenticated user's ID
- [ ] Listing/getting calendars returns `created_by_name` with the creator's name
- [ ] Calendars without a creator (GTFS import, pre-existing) show `created_by_name: null`
- [ ] Frontend calendar table shows a "Created by" column at xl breakpoint
- [ ] Both LV and EN i18n keys exist for the column header
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (unit + existing)
- [ ] No type suppressions added
- [ ] No regressions in existing tests

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All tasks completed in order (1-10)
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-5)
- [ ] No deviations from plan (or deviations documented with reasons)
- [ ] Ready for `/commit`

## Final Validation (5-Level Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: Syntax & Style**
```bash
uv run ruff format .
uv run ruff check --fix .
```

**Level 2: Type Safety**
```bash
uv run mypy app/
uv run pyright app/
```

**Level 3: Unit Tests (feature-specific)**
```bash
uv run pytest app/schedules/tests/ -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Validation (if Docker running)**
```bash
curl -s http://localhost:8123/health
```

**Success definition:** Levels 1-4 exit code 0, all tests pass, zero errors or warnings. Level 5 optional.

## Dependencies

- Shared utilities used: `TimestampMixin` from `app.shared.models`, `PaginatedResponse`/`PaginationParams` from `app.shared.schemas`
- Core modules used: `get_db` from `app.core.database`, `get_logger` from `app.core.logging`
- Auth modules used: `User` from `app.auth.models`, `get_current_user`/`require_role` from `app.auth.dependencies`
- New dependencies: None
- New env vars: None

## Known Pitfalls

The executing agent MUST follow these rules:

1. **`lazy="joined"` on the relationship** — This ensures the creator User is loaded in the same query. Without it, accessing `calendar.creator` triggers a lazy load which fails with async sessions. Do NOT use `lazy="select"` (the default) — it requires a sync session.

2. **Forward reference string for relationship** — Use `relationship("User", ...)` with the string `"User"`, NOT `relationship(User, ...)`. The User model is in `app.auth.models` and importing it directly would create a circular dependency since both modules import from `app.core.database`.

3. **`created_by_name` as a model property, not schema computed_field** — The schema has `created_by_name: str | None = None` with `from_attributes=True`. Pydantic will call `getattr(calendar, "created_by_name")` which hits our `@property`. Do NOT add `@computed_field` on the schema — the model property approach is simpler and avoids mypy `prop-decorator` issues.

4. **Nullable column for backwards compatibility** — The `created_by_id` column MUST be nullable. Existing calendars (including GTFS-imported ones) have no creator. Setting `nullable=False` would require a data migration.

5. **Do not modify the GTFS import path** — The `import_gtfs` method in the service creates calendars via `bulk_upsert_calendars` which operates on raw dicts, not the `create_calendar` method. These imported calendars will correctly have `created_by_id=NULL`.

6. **Test factory must include `created_by_id`** — The `make_calendar()` factory in conftest.py must have `created_by_id: None` in its defaults. Otherwise `Calendar(**defaults)` will miss the field, and `CalendarResponse.model_validate(calendar)` will fail to find `created_by_name` property since the relationship won't be loaded in test mocks.

7. **Mock calendars in tests won't have the relationship loaded** — Since test factories create Calendar objects directly (not from DB), the `creator` relationship will be `None`. This means `created_by_name` property returns `None` in tests — which is correct behavior for the existing tests.

## Notes

- The "Created By" column is positioned between Status and Created (timestamp) in the table, matching the user's request for it to be "next to status"
- At `xl` breakpoint, both "Created By" and "Created" (timestamp) columns are visible together
- Pre-existing calendars and GTFS-imported calendars will show "-" in the Created By column
- If the creator user is later deleted from the system, the FK `ondelete="SET NULL"` will set `created_by_id` to NULL, and the column will show "-"

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Understood the solution approach (model relationship + property)
- [ ] Clear that migration is needed (column not in DB yet)
- [ ] Clear that GTFS import path is NOT modified
- [ ] Validation commands are executable in this environment
