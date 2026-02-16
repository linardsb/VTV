# Command Architecture Planning

## Current Command Inventory

### Prime Commands (Context Loading)
| Command | Scope | Status |
|---------|-------|--------|
| `/be-prime` | General project context — CLAUDE.md, PRD, app structure, Docker, DB, git | Exists |
| `/be-prime-tools` | Agent tool depth — tool designs, composition chains, docstring patterns | Exists |
| `/fe-prime` | Frontend context — design system, components, pages, i18n, RBAC | Shipped (Feb 16, 2026) |

**Decision:** Backend prime command serves the general project context role. Only add specialized primes for genuinely different domains.

### Planning & Execution Commands
| Command | Stack-agnostic? | Status |
|---------|-----------------|--------|
| `/be-planning` | Yes — plan-driven, researches whatever codebase it finds | Exists |
| `/be-execute` | Yes — follows the plan, doesn't care what language | Exists |
| `/commit` | Yes — git is language-agnostic | Exists |

### Quality Commands
| Command | Stack-agnostic? | Status |
|---------|-----------------|--------|
| `/be-validate` | No — hardcoded to ruff/mypy/pyright/pytest (Python only) | Exists |
| `/fe-validate` | No — uses pnpm type-check/lint/build + design system/i18n/a11y scans | Shipped (Feb 16, 2026) |
| `/review` | No — 8 checks are Python-specific (SQLAlchemy, Pydantic, logging) | Exists |
| `/review-frontend` | No — will need frontend standards (components, a11y, state) | Planned (not yet needed) |

### Investigation & Scaffolding Commands
| Command | Stack-agnostic? | Status |
|---------|-----------------|--------|
| `/rca` | Mostly — investigates codebase, but examples are backend-focused | Exists |
| `/implement-fix` | Yes — reads RCA doc and applies fix | Exists |
| `/be-create-feature` | No — scaffolds Python VSA structure | Exists |
| `/be-init-project` | No — checks Python/Docker prerequisites | Exists |

### Autonomous Commands
| Command | Status |
|---------|--------|
| `/be-end-to-end-feature` | Exists — chains prime → planning → execute → validate → commit |

## Command Chaining

### Intended Pipeline (Feature Development)

```
/be-prime → /be-planning → [human reviews plan] → /be-execute → /review → /be-validate → /commit
```

### Current Chaining Gaps

Each command's OUTPUT section should point to the next step. Full audit:

| Command | Current OUTPUT says | Should say | Fix status |
|---------|-------------------|------------|------------|
| `/be-init-project` | Nothing | Next: `/be-prime` | Fixed |
| `/be-prime` | Nothing | Next: `/be-planning`, `/be-create-feature`, or `/rca` | Fixed |
| `/be-prime-tools` | Nothing | Next: `/be-planning [tool]` | Fixed |
| `/be-create-feature` | "run /be-validate" (partial) | Next: fill in code → `/be-validate` → `/commit` | Fixed |
| `/be-planning` | "To execute: `/be-execute`" | Already correct | Done |
| `/be-execute` | "/commit or manual review" | Already sufficient | Done |
| `/review` | Nothing | Next: `/be-validate` then `/commit` | Fixed |
| `/be-validate` | Nothing | Next: `/commit` if pass, fix if fail | Fixed |
| `/rca` | "/implement-fix $ARGUMENTS" | Already correct | Done |
| `/implement-fix` | Suggests commit message | Add explicit: `/commit` | Fixed |
| `/commit` | Reports push status | Terminal — push now optional | Fixed |
| `/be-end-to-end-feature` | Full summary | Terminal | Done |

**Status:** All gaps fixed (Feb 13, 2026).

### Frontend Pipeline (Shipped Feb 16, 2026)

```
/fe-prime → /fe-planning → /fe-execute → /fe-validate → /commit
                                │
             /fe-create-page ───┘  (quick scaffold, skip planning)
```

5 dedicated frontend commands shipped: `/fe-prime`, `/fe-planning`, `/fe-create-page`, `/fe-execute`, `/fe-validate`.
Reusable command: `/commit` (git is language-agnostic).
Still planned: `/review-frontend` (not yet needed — `/fe-validate` covers quality gates).

## Planning Improvements Applied

Changes made to `/be-planning` command (Feb 13, 2026):

1. **Research phase** — added 3 bullets:
   - Check `pyproject.toml` for existing dependencies, note `uv add` commands needed
   - Check `.env.example` for env vars, note if feature needs new ones
   - Identify cross-feature impact (existing code that might need changes)
   - Check `alembic/versions/` for migration conflicts (updated wording)

2. **Task section** — added "one task per file" instruction for cleaner `/be-execute` handoff

3. **Dependencies template** — added env vars line

## Deleted Commands

| Command | Reason | Date |
|---------|--------|------|
| `/plan-template` | Duplicated the template already embedded in `/be-planning`. Manual plan writing is unlikely in an AI-assisted workflow. | Feb 13, 2026 |

## Design Principles

- **Separate commands per domain** — no magic stack detection, no ambiguous flags
- **Reuse where genuinely agnostic** — `/be-planning`, `/be-execute`, `/commit` work for any stack
- **Specialize where the toolchain differs** — validate, review, prime need per-stack variants
- **YAGNI** — don't build frontend commands until the frontend exists
- **Each OUTPUT chains forward** — every command tells you what to run next

## Command Audit — Feb 13, 2026

Full audit of all 12 active backend commands against codebase architecture and Anthropic prompt engineering guidance. (Note: 5 frontend commands added Feb 16, 2026 — total now 21.)

### Findings

| # | Severity | Issue | File | Status |
|---|----------|-------|------|--------|
| 1 | CRITICAL | Dead `/plan-template` reference in hub CLAUDE.md | commands/CLAUDE.md | Fixed |
| 2 | CRITICAL | `/commit` auto-pushes without user consent | commands/commit.md | Fixed |
| 3 | HIGH | `/review` tool docstring check is vague (missing 5-principle list) | commands/review.md | Fixed |
| 4 | HIGH | No retry limits in `/be-execute` error recovery | commands/be-execute.md | Fixed |
| 5 | HIGH | No retry limits in `/be-end-to-end-feature` autonomous mode | commands/be-end-to-end-feature.md | Fixed |
| 6 | MEDIUM | 7 commands don't suggest next step in OUTPUT | 7 files | Fixed |
| 7 | MEDIUM | `/be-execute` has no pre-flight environment checks | commands/be-execute.md | Fixed |
| 8 | LOW | `/rca` input source ambiguous (how to get GitHub issue?) | commands/rca.md | Fixed |

### What Passed Audit

- All 12 commands have consistent frontmatter (description, argument-hint, allowed-tools)
- VSA patterns enforced uniformly across all code-generation commands
- Type safety emphasis (mypy + pyright strict) is consistent
- Logging pattern `domain.component.action_state` is consistent
- 5-step validation suite identical in /be-validate, /be-execute, /implement-fix, /be-end-to-end-feature
- Tool permissions (allowed-tools) appropriately scoped per command
- `/be-planning` → `/be-execute` chain is solid with self-contained plan format
- `/rca` → `/implement-fix` chain works well

### Codebase Alignment

| Category | Status | Notes |
|----------|--------|-------|
| Directory structure | Aligned | All expected dirs exist (plans/, docs/rca/, app/shared/, alembic/) |
| Core infrastructure | Aligned | app/core/ and app/shared/ fully implemented |
| Feature modules | Expected | Agent module not yet built (planned) — this is correct |
| pyproject.toml | Aligned | ruff, mypy, pyright, pytest configs match command expectations |
| docker-compose.yml | Aligned | Services match /be-init-project expectations |
| Reference docs | Aligned | All 4 reference files exist (PRD, mvp-tool-designs, vsa-patterns, feature-readme-template) |

### Anthropic Prompt Engineering Research

**Source:** [Chain Prompts](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/chain-prompts)

Key guidance applied:
- **Single-task goal per prompt** — VTV commands already follow this
- **Clear handoffs between prompts** — Fixed in 7 commands (Fix 6)
- **Self-correction chains need bounds** — Fixed with retry limits (Fixes 4, 5)
- **Traceability** — VTV commands use file:line references
- **Run independent subtasks in parallel** — applicable to future /be-end-to-end-feature optimization

**Source:** [Extended Thinking Tips](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/extended-thinking-tips)

Key guidance applied:
- **General instructions first, then troubleshoot step-by-step** — Some commands could trust LLM more, but current prescriptiveness is appropriate for consistency
- **Have Claude reflect and check its work** — /be-execute post-implementation checks do this
- **Be clear and specific** — Commands are detailed and specific
- **Multishot prompting** — Not directly applicable to slash commands, but patterns in vsa-patterns.md serve similar purpose
