# Feature README Template

Use this template when creating `README.md` for a new feature slice.

---

```markdown
# {Feature Name}

{One sentence describing what this feature does and why it exists.}

## Key Flows

### {Flow Name} (e.g., Create Thing)

1. Validate input data
2. Check business rules (uniqueness, permissions, etc.)
3. Persist to database
4. Return response

### {Flow Name} (e.g., Search Things)

1. Parse search parameters
2. Query database with filters
3. Return paginated results

## Database Schema

Table: `{table_name}`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `slug` | String(50) | Unique, indexed | URL-safe identifier |
| `name` | String(200) | Not null | Display name |
| `is_active` | Boolean | Default true | Soft delete flag |
| `created_at` | DateTime | Not null | Auto-set on create |
| `updated_at` | DateTime | Not null | Auto-set on update |

## Business Rules

1. {Rule about uniqueness, e.g., "Slug must be unique across all things"}
2. {Rule about validation, e.g., "Name must be 1-200 characters"}
3. {Rule about behavior, e.g., "Deletion uses soft delete (is_active=False)"}

## Integration Points

- **{Other Feature}**: {How this feature relates, e.g., "Orders reference products by ID"}
- **{Other Feature}**: {Direction of data flow, e.g., "Read-only access to inventory levels"}

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/{feature}/` | Create a new thing |
| GET | `/{feature}/{id}` | Get thing by ID |
| GET | `/{feature}/` | List things (paginated) |
| PATCH | `/{feature}/{id}` | Update a thing |
```
