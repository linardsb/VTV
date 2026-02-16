---
description: Scaffold a complete vertical slice feature directory with all VSA files
argument-hint: [feature-name] e.g. orders, transit-stops
allowed-tools: Read, Write, Edit
---

Scaffold a new VTV feature slice named "$ARGUMENTS" with all VSA files, tests, and router wiring.

@reference/vsa-patterns.md
@reference/feature-readme-template.md

## Steps

1. **Validate the feature name**: Must be lowercase, alphanumeric with hyphens (e.g., `products`, `transit-stops`). Convert to a valid Python package name (hyphens → underscores) for the directory.

2. **Create the feature directory** at `app/{feature_name}/` with these files:
   - `__init__.py` (empty)
   - `schemas.py` — Pydantic schemas with `{Feature}Base`, `{Feature}Create`, `{Feature}Update`, `{Feature}Response`
   - `models.py` — SQLAlchemy model inheriting `Base` and `TimestampMixin`, using `Mapped[]` annotations
   - `repository.py` — Async repository class with `get()`, `list()`, `create()` methods
   - `service.py` — Service class with structured logging (`{feature}.action_state` pattern)
   - `exceptions.py` — Feature exceptions inheriting from `app.core.exceptions` base classes
   - `routes.py` — FastAPI router with `prefix="/{feature}"` and service dependency

3. **Create the test directory** at `app/{feature_name}/tests/` with:
   - `__init__.py` (empty)
   - `conftest.py` — Feature-specific test fixtures
   - `test_service.py` — Service test stubs
   - `test_routes.py` — Route test stubs

4. **Create `app/{feature_name}/README.md`** using the template from `reference/feature-readme-template.md`

5. **Wire the router** into `app/main.py` by adding the import and `app.include_router()` call

6. **Follow the patterns** in `reference/vsa-patterns.md` for all generated code

7. **Report what was created** and remind the user to:
   - Fill in schemas with actual fields
   - Create a database migration: `uv run alembic revision --autogenerate -m "add {feature} table"`
   - Run validation: `/be-validate`

**Next steps:**
1. Fill in schemas, models, and business logic in the scaffolded files
2. Run `/be-validate` to check all quality gates
3. Run `/commit` when ready
