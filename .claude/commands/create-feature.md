---
description: Scaffold a complete vertical slice feature directory with all VSA files
argument-hint: [feature-name] e.g. orders, transit-stops
allowed-tools: Read, Write, Edit
---

This command generates the full directory structure for a new VTV feature slice. Given a feature name, it creates `app/{feature}/` with all the standard VSA files: `schemas.py` (Pydantic request/response models), `models.py` (SQLAlchemy with `Base` + `TimestampMixin` + `Mapped[]`), `repository.py` (async data access), `service.py` (business logic with structured logging), `exceptions.py` (feature-specific errors), `routes.py` (thin FastAPI router), and a `tests/` directory with conftest and test stubs.

All generated code follows the patterns defined in `reference/vsa-patterns.md` — async SQLAlchemy 2.0 style with `select()`, dependency injection via `Depends(get_service)`, structured logging with the `domain.component.action_state` pattern, and complete type annotations. The router is automatically wired into `app/main.py` with the import and `include_router()` call, and a `README.md` is created from the feature template.

After scaffolding, you fill in the actual fields in schemas and models, write your business logic in the service layer, create a database migration with `uv run alembic revision --autogenerate -m "add {feature} table"`, and run `/validate` to verify everything passes. This is the fastest way to start a new feature while ensuring it follows all VTV conventions from the beginning.

Scaffold a new VTV feature slice named "$ARGUMENTS".

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
   - Run validation: `/validate`
