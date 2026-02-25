# Agent Skills

Reusable knowledge packages (procedures, protocols, glossaries) stored in PostgreSQL and injected into the AI agent's system context on every request via Pydantic AI's `instructions` parameter.

## Key Flows

### Create Skill

1. Validate input (name uniqueness, field constraints)
2. Check for duplicate name via repository
3. Persist to `agent_skills` table
4. Return SkillResponse

### Load Active Skills into Agent Context

1. Fetch all active skills ordered by priority DESC
2. Build combined text with header: `"AGENT SKILLS (always-available operational knowledge):"`
3. Append skills respecting TOKEN_BUDGET_CHARS (8000 chars, ~2000 tokens)
4. Drop lower-priority skills when budget exceeded (log warning)
5. Pass combined text as `instructions` parameter to `agent.run()`
6. If skill loading fails, agent runs normally without skills (non-fatal)

### Seed Default Skills

1. Check if `agent_skills` table is empty
2. If empty, create 5 pre-built Latvian transit operations skills
3. If table has data, skip seeding

### Agent Skill Management (via AI tool)

1. Agent receives dispatcher request about procedures
2. Agent calls `manage_agent_skills(action="list")` to show available skills
3. Agent calls `manage_agent_skills(action="create", ...)` to save new procedures
4. Uses standalone `AsyncSessionLocal()` sessions (not request-scoped)

## Database Schema

Table: `agent_skills`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `name` | String(100) | Unique, not null | Skill display name |
| `description` | String(500) | Not null | Short description |
| `content` | Text | Not null | Full skill content (max 10000 chars) |
| `category` | String(50) | Not null, default "transit_ops" | One of: transit_ops, procedures, glossary, reporting |
| `is_active` | Boolean | Not null, default true | Whether injected into agent context |
| `priority` | Integer | Not null, default 0 | Loading order (0-100, higher = loaded first) |
| `created_by_id` | Integer | FK users.id, nullable, SET NULL on delete | Creator reference |
| `created_at` | DateTime | Not null | Auto-set via TimestampMixin |
| `updated_at` | DateTime | Not null | Auto-set via TimestampMixin |

## Business Rules

1. Skill name must be unique across all skills
2. Name max 100 chars, description max 500 chars, content max 10000 chars
3. Category must be one of: `transit_ops`, `procedures`, `glossary`, `reporting`
4. Priority range 0-100 (higher priority skills loaded first when budget is tight)
5. TOKEN_BUDGET_CHARS = 8000 (~2000 tokens) — maximum chars injected into agent prompt
6. Skills are loaded fresh on every agent request (no caching)
7. Skill loading failure is non-fatal — agent works without skills if DB is down
8. Empty PATCH body rejected via model_validator
9. Seed only runs when table is completely empty
10. Write operations (create/update/delete/seed) require admin role

## Seed Skills

5 pre-built Latvian transit operations skills:

| Name | Priority | Category | Description |
|------|----------|----------|-------------|
| Operaciju Prioritizacija | 90 | transit_ops | ATC-inspired P1-P5 incident priority system |
| Marsrutu Traucejumu Protokols | 80 | procedures | 6-step route disruption response procedure |
| Mainas Nodosana | 70 | procedures | Dispatcher shift handover checklist |
| GTFS Datu Kvalitate | 60 | reporting | GTFS import validation and data quality rules |
| Latviesu Terminu Paplasinajums | 50 | glossary | Extended Latvian transit terminology |

## Integration Points

- **Agent Module** (`app/core/agents/`): Skills injected into agent context via `build_instructions_with_skills()` in agent.py and `instructions` param in service.py. Agent tool `manage_agent_skills` registered as Tool 11.
- **Auth** (`app/auth/`): All REST endpoints require authentication. Write endpoints require admin role via `require_role("admin")`.
- **Users** (`app/auth/models.User`): `created_by_id` FK references users table (SET NULL on delete).

## API Endpoints

| Method | Path | Auth | Rate | Description |
|--------|------|------|------|-------------|
| GET | `/api/v1/skills/` | Any | 30/min | List skills (paginated, filterable by category/is_active) |
| GET | `/api/v1/skills/{id}` | Any | 30/min | Get skill by ID |
| POST | `/api/v1/skills/` | Admin | 10/min | Create a new skill |
| PATCH | `/api/v1/skills/{id}` | Admin | 10/min | Update a skill |
| DELETE | `/api/v1/skills/{id}` | Admin | 10/min | Delete a skill |
| POST | `/api/v1/skills/seed` | Admin | 5/min | Seed 5 default skills (only when table empty) |
