# Plan Stub: Backend Goals Model + Route Assignment (Session 2 of 4)

**Status:** STUB — flesh out with `/be-planning` before executing
**Depends on:** Session 1 (drag-and-drop fix) completed
**Command to flesh out:** `/be-planning add goals JSONB field to events model for driver scheduling with route assignment and goal tracking`

## Scope

Add a `goals` JSONB column to the events table so the frontend can store structured driver scheduling goals (route assignments, training objectives, performance notes, checklists) alongside calendar events.

## Decisions Made (from Q&A)

| Question | Answer |
|----------|--------|
| Storage approach | C) JSON field on events model (not separate table, not description hack) |
| Route assignment | B) Filtered to driver's `qualified_route_ids` |
| Transport assignment | C) Both type (bus/trolleybus/tram) and optional vehicle number |
| Backward compatible | Yes — existing events without goals return `goals: null` |
| Goal tracking | Yes — each goal item has a `completed` boolean |
| Checklist items | C) Mix — pre-filled templates + custom items |

## Deliverables

### 1. Alembic Migration
- Add `goals` column to `events` table: `Column(JSONB, nullable=True, default=None)`
- Non-destructive — existing rows get `NULL`

### 2. Goals Schema (Pydantic)
Proposed structure (refine during `/be-planning`):

```python
class GoalItem(BaseModel):
    text: str
    completed: bool = False
    type: Literal["route", "training", "note", "checklist"]

class EventGoals(BaseModel):
    items: list[GoalItem] = []
    route_id: int | None = None           # assigned route (from qualified_route_ids)
    transport_type: str | None = None      # "bus", "trolleybus", "tram"
    vehicle_id: str | None = None          # optional specific vehicle number
```

### 3. Updated Event Schemas
- `EventCreate` — add `goals: EventGoals | None = None`
- `EventUpdate` — add `goals: EventGoals | None = None`
- `EventResponse` — add `goals: EventGoals | None = None`

### 4. Updated Routes
- `POST /api/v1/events` — accept goals in body
- `PATCH /api/v1/events/{id}` — accept goals update (partial update of goals field)
- `GET /api/v1/events` — return goals in response
- `GET /api/v1/events/{id}` — return goals in response

### 5. Goal Completion Endpoint (optional, may defer to Session 4)
- `PATCH /api/v1/events/{id}/goals/{index}` — toggle single goal item completion
- Or: just use the existing `PATCH /api/v1/events/{id}` with updated goals JSON

## Files Likely Modified

```
app/events/schemas.py      — Add GoalItem, EventGoals, update EventCreate/Update/Response
app/events/models.py       — Add goals JSONB column
app/events/repository.py   — Handle goals field in CRUD
app/events/service.py      — Pass goals through
app/events/routes.py       — Accept/return goals
alembic/versions/xxx_add_goals_to_events.py  — New migration
app/tests/test_events.py   — Update tests for goals field
```

## Validation

```bash
make lint && make types && make test
```

## SDK Regeneration

After backend changes, regenerate the TypeScript SDK:
```bash
cd cms && pnpm --filter @vtv/sdk refresh
```

This updates `cms/packages/sdk/src/client/types.gen.ts` with the new `EventGoals` type, which Session 3 frontend work depends on.

## Notes for `/be-planning` Agent

- Check `app/events/` vertical slice for current model/schema/route patterns
- The `goals` field must be nullable with default None for backward compat
- Use JSONB (not JSON) for indexing capability if needed later
- Follow VTV anti-patterns doc (`docs/python-anti-patterns.md`) — especially Pattern #12 (Pydantic schema naming)
- Run full `make check` before marking complete
