# Contributing to VTV

## First-Time Setup

```bash
# Clone and bootstrap
git clone <repo-url>
cd VTV
make bootstrap
```

`make bootstrap` installs Python dependencies and configures pre-commit hooks (ruff formatting, linting, type checking, and secrets detection).

## Development Workflow

```bash
make db          # Start PostgreSQL + Redis
make dev         # Start backend (:8123) + frontend (:3000)
make check       # Run all quality checks (lint + types + tests)
```

See `make help` for all available commands.

## Pre-Commit Hooks

Hooks run automatically on every commit:
- **ruff-format** - auto-fixes formatting
- **ruff** - linting with auto-fix
- **trailing-whitespace / end-of-file-fixer** - file hygiene
- **check-yaml** - validates YAML files
- **check-added-large-files** - blocks files >1MB
- **detect-secrets** - scans for leaked credentials
- **VTV security checks** - Bandit rules, sensitive file detection, hardcoded credential detection

On push (not commit): **mypy** strict type checking.

### Updating the Secrets Baseline

If detect-secrets flags a false positive:

```bash
# Review flagged secrets interactively
uv run detect-secrets audit .secrets.baseline

# Or regenerate the full baseline
uv run detect-secrets scan \
  --exclude-files '\.env$' \
  --exclude-files '\.env\..*' \
  --exclude-files 'uv\.lock' \
  --exclude-files 'pnpm-lock\.yaml' \
  > .secrets.baseline
```

Commit the updated `.secrets.baseline` alongside your changes.

### Bypassing Hooks

```bash
git commit --no-verify  # Skip all hooks (use sparingly)
```

## Code Standards

- **Python 3.12+**, strict MyPy + Pyright
- **Vertical Slice Architecture** - features in `app/{feature}/`
- **Structured logging** - `domain.component.action_state` pattern
- See `CLAUDE.md` for full architecture and conventions
