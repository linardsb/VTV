# Command Architecture Planning

## Current Command Inventory

### Prime Commands (Context Loading)
| Command | Scope | Status |
|---------|-------|--------|
| `/prime` | General project context — CLAUDE.md, PRD, app structure, Docker, DB, git | Exists |
| `/prime-tools` | Agent tool depth — tool designs, composition chains, docstring patterns | Exists |
| `/prime-frontend` | Frontend/CMS patterns, component structure, state management | Planned |

**Decision:** No `/prime-backend` needed — `/prime` already serves this role. Only add specialized primes for genuinely different domains.

### Planning & Execution Commands
| Command | Stack-agnostic? | Status |
|---------|-----------------|--------|
| `/planning` | Yes — plan-driven, researches whatever codebase it finds | Exists |
| `/execute` | Yes — follows the plan, doesn't care what language | Exists |
| `/commit` | Yes — git is language-agnostic | Exists |

### Quality Commands
| Command | Stack-agnostic? | Status |
|---------|-----------------|--------|
| `/validate` | No — hardcoded to ruff/mypy/pyright/pytest (Python only) | Exists |
| `/validate-frontend` | No — will need eslint/tsc/vitest or equivalent | Planned |
| `/review` | No — 8 checks are Python-specific (SQLAlchemy, Pydantic, logging) | Exists |
| `/review-frontend` | No — will need frontend standards (components, a11y, state) | Planned |

### Investigation & Scaffolding Commands
| Command | Stack-agnostic? | Status |
|---------|-----------------|--------|
| `/rca` | Mostly — investigates codebase, but examples are backend-focused | Exists |
| `/implement-fix` | Yes — reads RCA doc and applies fix | Exists |
| `/create-feature` | No — scaffolds Python VSA structure | Exists |
| `/init-project` | No — checks Python/Docker prerequisites | Exists |

### Autonomous Commands
| Command | Status |
|---------|--------|
| `/end-to-end-feature` | Exists — chains prime → planning → execute → validate → commit |

## Command Chaining

### Intended Pipeline (Feature Development)

```
/prime → /planning → [human reviews plan] → /execute → /review → /validate → /commit
```

### Current Chaining Gaps

Each command's OUTPUT section should point to the next step. Full audit:

| Command | Current OUTPUT says | Should say | Fix status |
|---------|-------------------|------------|------------|
| `/init-project` | Nothing | Next: `/prime` | Fixed |
| `/prime` | Nothing | Next: `/planning`, `/create-feature`, or `/rca` | Fixed |
| `/prime-tools` | Nothing | Next: `/planning [tool]` | Fixed |
| `/create-feature` | "run /validate" (partial) | Next: fill in code → `/validate` → `/commit` | Fixed |
| `/planning` | "To execute: `/execute`" | Already correct | Done |
| `/execute` | "/commit or manual review" | Already sufficient | Done |
| `/review` | Nothing | Next: `/validate` then `/commit` | Fixed |
| `/validate` | Nothing | Next: `/commit` if pass, fix if fail | Fixed |
| `/rca` | "/implement-fix $ARGUMENTS" | Already correct | Done |
| `/implement-fix` | Suggests commit message | Add explicit: `/commit` | Fixed |
| `/commit` | Reports push status | Terminal — push now optional | Fixed |
| `/end-to-end-feature` | Full summary | Terminal | Done |

**Status:** All gaps fixed (Feb 13, 2026).

### Frontend Pipeline (When CMS is Added)

```
/prime → /prime-frontend → /planning → [review plan] → /execute → /review-frontend → /validate-frontend → /commit
```

Reusable commands: `/prime`, `/planning`, `/execute`, `/commit`
New commands needed: `/prime-frontend`, `/review-frontend`, `/validate-frontend`

## Planning Improvements Applied

Changes made to `/planning` command (Feb 13, 2026):

1. **Research phase** — added 3 bullets:
   - Check `pyproject.toml` for existing dependencies, note `uv add` commands needed
   - Check `.env.example` for env vars, note if feature needs new ones
   - Identify cross-feature impact (existing code that might need changes)
   - Check `alembic/versions/` for migration conflicts (updated wording)

2. **Task section** — added "one task per file" instruction for cleaner `/execute` handoff

3. **Dependencies template** — added env vars line

## Deleted Commands

| Command | Reason | Date |
|---------|--------|------|
| `/plan-template` | Duplicated the template already embedded in `/planning`. Manual plan writing is unlikely in an AI-assisted workflow. | Feb 13, 2026 |

## Design Principles

- **Separate commands per domain** — no magic stack detection, no ambiguous flags
- **Reuse where genuinely agnostic** — `/planning`, `/execute`, `/commit` work for any stack
- **Specialize where the toolchain differs** — validate, review, prime need per-stack variants
- **YAGNI** — don't build frontend commands until the frontend exists
- **Each OUTPUT chains forward** — every command tells you what to run next

## Command Audit — Feb 13, 2026

Full audit of all 12 active commands against codebase architecture and Anthropic prompt engineering guidance.

### Findings

| # | Severity | Issue | File | Status |
|---|----------|-------|------|--------|
| 1 | CRITICAL | Dead `/plan-template` reference in hub CLAUDE.md | commands/CLAUDE.md | Fixed |
| 2 | CRITICAL | `/commit` auto-pushes without user consent | commands/commit.md | Fixed |
| 3 | HIGH | `/review` tool docstring check is vague (missing 5-principle list) | commands/review.md | Fixed |
| 4 | HIGH | No retry limits in `/execute` error recovery | commands/execute.md | Fixed |
| 5 | HIGH | No retry limits in `/end-to-end-feature` autonomous mode | commands/end-to-end-feature.md | Fixed |
| 6 | MEDIUM | 7 commands don't suggest next step in OUTPUT | 7 files | Fixed |
| 7 | MEDIUM | `/execute` has no pre-flight environment checks | commands/execute.md | Fixed |
| 8 | LOW | `/rca` input source ambiguous (how to get GitHub issue?) | commands/rca.md | Fixed |

### What Passed Audit

- All 12 commands have consistent frontmatter (description, argument-hint, allowed-tools)
- VSA patterns enforced uniformly across all code-generation commands
- Type safety emphasis (mypy + pyright strict) is consistent
- Logging pattern `domain.component.action_state` is consistent
- 5-step validation suite identical in /validate, /execute, /implement-fix, /end-to-end-feature
- Tool permissions (allowed-tools) appropriately scoped per command
- `/planning` → `/execute` chain is solid with self-contained plan format
- `/rca` → `/implement-fix` chain works well

### Codebase Alignment

| Category | Status | Notes |
|----------|--------|-------|
| Directory structure | Aligned | All expected dirs exist (plans/, docs/rca/, app/shared/, alembic/) |
| Core infrastructure | Aligned | app/core/ and app/shared/ fully implemented |
| Feature modules | Expected | Agent module not yet built (planned) — this is correct |
| pyproject.toml | Aligned | ruff, mypy, pyright, pytest configs match command expectations |
| docker-compose.yml | Aligned | Services match /init-project expectations |
| Reference docs | Aligned | All 4 reference files exist (PRD, mvp-tool-designs, vsa-patterns, feature-readme-template) |

### Anthropic Prompt Engineering Research

**Source:** [Chain Prompts](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/chain-prompts)

Key guidance applied:
- **Single-task goal per prompt** — VTV commands already follow this
- **Clear handoffs between prompts** — Fixed in 7 commands (Fix 6)
- **Self-correction chains need bounds** — Fixed with retry limits (Fixes 4, 5)
- **Traceability** — VTV commands use file:line references
- **Run independent subtasks in parallel** — applicable to future /end-to-end-feature optimization

**Source:** [Extended Thinking Tips](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/extended-thinking-tips)

Key guidance applied:
- **General instructions first, then troubleshoot step-by-step** — Some commands could trust LLM more, but current prescriptiveness is appropriate for consistency
- **Have Claude reflect and check its work** — /execute post-implementation checks do this
- **Be clear and specific** — Commands are detailed and specific
- **Multishot prompting** — Not directly applicable to slash commands, but patterns in vsa-patterns.md serve similar purpose
