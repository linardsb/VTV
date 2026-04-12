# ADR-0001: Vertical Slice Architecture

## Status

Accepted

## Context

VTV is a transit operations platform with 15+ domain areas (transit, vehicles, drivers, alerts, knowledge, auth, etc.). The codebase needed an organizing principle that:

- Lets a developer work on one domain without understanding (or breaking) others
- Supports AI-assisted development where agents implement entire features from plans
- Keeps shared code minimal to avoid hidden coupling
- Scales to 20+ features without a "shared utilities" dumping ground

Traditional layered architecture (controllers -> services -> repositories as top-level directories) forces every feature change to touch files across multiple directories, creates merge conflicts between unrelated features, and makes it hard for AI agents to reason about feature boundaries.

## Decision

We use **Vertical Slice Architecture**: each feature lives under `app/{feature}/` with its own `models.py`, `schemas.py`, `repository.py`, `service.py`, `exceptions.py`, `routes.py`, and `tests/` directory. The full pattern is documented in `reference/vsa-patterns.md`.

Three rules govern cross-feature interaction:

1. **Read-only cross-feature access** - A service may import another feature's *repository* (not service) for read queries. All repositories share the same `AsyncSession`, so reads participate in the caller's transaction. Direct writes to another feature's tables are forbidden.

2. **Three-feature rule for shared code** - Inline the first use, duplicate the second (with a `# NOTE: duplicated from {feature}`), extract to `app/shared/` only on the third use. This prevents premature abstraction.

3. **Core infrastructure in `app/core/`** - Database, Redis, config, logging, middleware, auth, and rate limiting live in `app/core/`. These are framework concerns, not business logic.

## Consequences

**Easier:**
- Feature scaffolding is mechanical (`/be-create-feature` generates the entire skeleton)
- AI agents can implement a feature by reading one directory and its plan
- Deleting a feature is a single directory removal + one line in `app/main.py`
- Test isolation: feature tests depend only on their own fixtures + shared test utilities

**Harder:**
- Cross-feature queries require importing another feature's repository, which can feel indirect
- The three-feature rule means some code is intentionally duplicated before extraction
- New contributors sometimes propose per-feature `shared/` subdirectories - this ADR is the answer to why we don't
