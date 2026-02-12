# VTV Commands

Slash commands for AI-assisted development workflows. Run any command by typing `/command-name` in Claude Code.

---

## Setup Commands

### `/init-project`

**Usage:** `/init-project`

Checks that all prerequisites are installed (Python 3.12+, uv, Docker, Docker Compose), starts Docker services with `docker-compose up -d`, verifies containers are running and healthy, and hits the `/health` endpoint to confirm the API is responding. Run this at the start of a session or after a reboot to get everything up.

**What it does:**
1. Verifies Python, uv, Docker, and Docker Compose versions
2. Starts PostgreSQL and app containers
3. Confirms both containers are running and DB is healthy
4. Hits `http://localhost:8123/health` to verify the API
5. Reports status and links to Swagger UI at `/docs`

---

### `/create-feature`

**Usage:** `/create-feature orders`

Scaffolds a complete vertical slice feature directory with all the files defined in `reference/vsa-patterns.md`. Generates the full directory structure (`schemas.py`, `models.py`, `repository.py`, `service.py`, `exceptions.py`, `routes.py`, `tests/`, `README.md`), wires the router into `app/main.py`, and follows VTV's async patterns. You fill in the actual fields and business logic after scaffolding.

**What it creates:**
- `app/{feature}/` with all VSA files using async SQLAlchemy patterns
- `app/{feature}/tests/` with conftest, test stubs for service and routes
- `app/{feature}/README.md` from the feature README template
- Import + `include_router()` line in `app/main.py`

**After running:** Fill in schemas with real fields, create a migration with `uv run alembic revision --autogenerate`, and run `/validate`.

---

## Context Loading Commands

### `/prime`

**Usage:** `/prime`

Loads the full VTV project context into Claude's working memory for the current session. Reads `CLAUDE.md`, `PRD.md`, and `mvp-tool-designs.md` for architecture and product context. Analyzes the `app/` directory structure to identify implemented vs. planned features. Checks `app/main.py` for registered routers, reads `docker-compose.yml` and `pyproject.toml` for infrastructure config, reviews recent git history, and checks if Docker services and the API are running.

**Output:** A structured summary covering project identity, tech stack, implemented/planned features, infrastructure health, recent commits, and key entry point file paths. Use this before working on features so Claude understands the full picture.

**When to use:** Start of a new session, before planning, or whenever Claude seems to lack project context.

---

### `/prime-tools`

**Usage:** `/prime-tools`

Specialized context loading for AI agent tool development. Reads tool specifications from `mvp-tool-designs.md`, PRD agent sections, and CLAUDE.md's tool docstring standards. Inventories which tools are implemented vs. planned, checks existing tool docstrings against the agent-optimized format (selection guidance, composition hints, token efficiency), reviews dry-run patterns, and inspects error response formats.

**Output:** A tool-focused summary covering tool inventory (implemented/planned), design patterns, workflow chains, docstring standards, and next steps. Use this before building or modifying any agent tools.

**When to use:** Before running `/planning` for a tool feature, or when debugging agent tool behavior.

---

## Planning Commands

### `/planning`

**Usage:** `/planning add obsidian search tool`

Researches the codebase and creates a detailed implementation plan that another agent (or `/execute`) can follow without any additional context. Reads CLAUDE.md, PRD.md, and existing features to understand conventions. Identifies reusable shared utilities, finds similar features to use as patterns, and designs the full vertical slice. If the feature involves agent tools (detected by keywords like "tool", "agent", "Obsidian"), it adds tool-specific planning sections: agent-optimized docstrings, dry-run support, token efficiency, and composition chains.

**Output:** A plan file saved to `plans/{feature-name}.md` containing: feature description, user story, solution approach with alternatives considered, relevant files with exact line ranges, step-by-step implementation tasks with per-task validation commands, testing strategy, logging events, acceptance criteria, and final validation commands.

**Key design:** The plan is self-contained — it includes everything needed for execution without referencing the original conversation. This means `/execute` can run it in a completely separate session.

---

### `/plan-template`

**Usage:** `/plan-template`

Outputs the blank VTV plan template to `plans/template.md`. Use this when you want to write a plan manually instead of having `/planning` generate one, or as a reference for the plan structure. The template has all the sections that `/execute` expects: feature description, user story, solution approach, relevant files, implementation tasks, testing strategy, acceptance criteria, and final validation.

---

## Execution Commands

### `/execute`

**Usage:** `/execute plans/user-profiles.md`

Reads a plan file and implements every step in order. Creates all specified files following VTV conventions (type annotations, async patterns, structured logging, Google-style docstrings). Runs database migrations if the plan requires them. After implementation, runs the full 5-step validation suite (ruff format, ruff check, mypy, pyright, pytest) and fixes any failures before reporting results.

**What it checks post-implementation:**
- Router registered in `app/main.py`
- All functions have type annotations
- No type suppressions added
- Logging follows `domain.component.action_state` format
- Models inherit `TimestampMixin`
- Tests exist and pass

**After running:** Review the output, then `/commit` if satisfied.

---

### `/implement-fix`

**Usage:** `/implement-fix 42`

Reads the RCA document at `docs/rca/issue-42.md` (created by `/rca`) and implements the proposed fix. Applies each code change described in the RCA's "Proposed Fix" section, writes regression tests named `test_issue_42_{description}()`, runs migrations if needed, and validates with the full 5-step suite. Suggests a commit message in `fix(scope): description (Fixes #42)` format.

**Prerequisite:** Run `/rca 42` first to create the RCA document.

---

## Validation & Review Commands

### `/validate`

**Usage:** `/validate`

Runs all 5 VTV quality checks in sequence against the current codebase. Each check must pass before reporting the next:

1. **Ruff format** — Auto-fixes formatting issues
2. **Ruff check** — Linting (style, imports, security, type annotation rules)
3. **MyPy** — Strict mode type checking
4. **Pyright** — Strict mode type checking (catches issues MyPy misses)
5. **Pytest** — Full test suite with verbose output

**Output:** A pass/fail scorecard for all 5 checks with specific error locations if anything fails. Run this after any code changes and before committing.

---

### `/review`

**Usage:** `/review app/agent/` or `/review app/core/health.py`

Reads all files in the target path and reviews them against VTV's 8 quality standards: type safety, Pydantic schemas, structured logging, database patterns, architecture (VSA boundaries), docstrings, testing, and security. Produces a table of findings with file:line references, descriptions, fix suggestions, and priority levels (Critical/High/Medium/Low).

**What it checks:**
- Type annotations complete, no `Any` without justification, no suppressions
- Logging events follow `domain.component.action_state` with started/completed/failed pairs
- Async/await + `select()` style for database operations
- VSA boundaries respected (no cross-feature imports violating rules)
- Agent tool docstrings follow the 5-principle format (if applicable)
- Tests exist with integration tests properly marked
- No hardcoded secrets, SQL injection prevention via SQLAlchemy

---

## Git Commands

### `/commit`

**Usage:** `/commit` or `/commit app/agent/routes.py app/agent/service.py`

Reviews all changes (or specified files), performs safety checks for secrets (`.env`, `.pem`, `.key`, `credentials.*`), stages files explicitly (never `git add .`), and creates a conventional commit. Uses VTV-specific scopes: `core`, `shared`, `agent`, `transit`, `obsidian`, `config`, `db`, `health`, or the feature name.

**Commit format:**
```
type(scope): short description

Optional body explaining WHY.

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`, `style`

---

## Investigation Commands

### `/rca`

**Usage:** `/rca 42`

Performs root cause analysis for a GitHub issue. Reads the issue details, then systematically investigates the VTV codebase: routes for affected endpoints, services for business logic edge cases, models for constraint issues, schemas for validation gaps, middleware for cross-cutting problems, and config for environment issues. Checks for `_failed` log events related to the issue, reviews migration history, and identifies the root cause with specific file:line references.

**Output:** An RCA document saved to `docs/rca/issue-42.md` containing: summary, symptoms, root cause location and category, evidence, proposed fix with exact file changes, required tests, and validation steps. Tells you to run `/implement-fix 42` to apply the fix.

---

## Autonomous Commands

### `/end-to-end-feature`

**Usage:** `/end-to-end-feature add health dashboard`

Runs the complete feature development lifecycle autonomously in 5 phases:

1. **Prime** — Loads project context (CLAUDE.md, PRD.md, app structure, git state). Auto-detects agent tool features and loads tool-specific context.
2. **Plan** — Designs the vertical slice, identifies shared utilities to reuse, plans migrations, defines logging events. Saves plan to `plans/`.
3. **Execute** — Implements every file with type annotations, async patterns, structured logging, docstrings. Registers router, runs migrations.
4. **Validate** — Runs all 5 checks (ruff format, ruff check, mypy, pyright, pytest). Fixes any failures before proceeding.
5. **Commit** — Stages files explicitly, creates conventional commit with Co-Authored-By.

**Output:** Full summary with files created/modified, validation scorecard, and commit hash.

**Trust level:** Only use this after you've run each individual command (`/prime`, `/planning`, `/execute`, `/validate`, `/commit`) separately and verified their output. See Trust Progression below.

---

## Workflows

### Feature Development (manual steps)
```
/prime                                    # Load project context
/planning add user authentication         # Create the plan
/execute plans/user-authentication.md     # Implement it
/validate                                 # Verify everything passes
/commit                                   # Commit with conventional format
```

### Feature Development (autonomous)
```
/end-to-end-feature add user authentication
```

### New Feature Scaffolding
```
/create-feature orders                    # Generate VSA skeleton
# Fill in schemas, models, business logic
/validate                                 # Verify checks pass
/commit                                   # Commit the feature
```

### Bug Fix
```
/rca 42                    # Investigate and document root cause
/implement-fix 42          # Fix from the RCA document
/validate                  # Verify the fix
/commit                    # Commit with "Fixes #42"
```

### Agent Tool Development
```
/prime-tools                              # Load tool designs and patterns
/planning add obsidian search tool        # Plan with tool-specific sections
/execute plans/obsidian-search-tool.md    # Implement with agent-optimized docstrings
/validate                                 # Verify all checks pass
/commit                                   # Commit
```

### Quick Check
```
/validate        # Run all linting, type checking, and tests
/review app/     # Review code against VTV standards
```

## Output Directories

- `plans/` — Implementation plans created by `/planning`
- `docs/rca/` — Root cause analysis documents created by `/rca`

## Trust Progression

Follow this progression before using autonomous commands:

1. **Manual prompts** — Learn what instructions work
2. **Individual commands** — Run `/prime`, `/planning`, `/execute`, `/commit` separately and verify each
3. **Chained commands** — Use `/end-to-end-feature` only after trusting each individual command

<claude-mem-context>
# Recent Activity

<!-- This section is auto-generated by claude-mem. Edit content outside the tags. -->

### Feb 12, 2026

| ID | Time | T | Title | Read |
|----|------|---|-------|------|
| #13777 | 6:28 AM | 🔵 | VTV init-project Command - Docker-Based Project Initialization Pattern | ~325 |
| #13776 | " | 🔵 | VTV Commands CLAUDE.md - Empty Context File Ready for Command Documentation | ~195 |
</claude-mem-context>
