# Plan: OPS-1.1 — `.pre-commit-config.yaml` + `make bootstrap`

## Context

Pre-commit hooks exist as a custom bash script (`scripts/pre-commit`) but there is no `.pre-commit-config.yaml` framework. The `make install-hooks` target just copies the bash script. A new contributor can skip hooks entirely. This plan adds the `pre-commit` framework with ruff-format, ruff-check, mypy, detect-secrets, and standard pre-commit-hooks, plus a `make bootstrap` onboarding target and CI integration.

## Security Context Assessment

**Active:** CTX-INFRA (modifying CI/config, Makefile, adding new tool dependencies)

- No hardcoded credentials in new config files
- detect-secrets baseline must not contain real secrets
- CI integration must not expose secrets in logs

## Research Summary

### Key Files

| File | Role | Lines |
|------|------|-------|
| `Makefile` | Build targets — `install-hooks` at L137-140 | 193 |
| `scripts/pre-commit` | Existing bash hook (Bandit, sensitive files, creds, secrets regex) | 71 |
| `.github/workflows/ci.yml` | CI pipeline — backend+frontend+e2e | 199 |
| `.github/workflows/security.yml` | Weekly security audit | 86 |
| `pyproject.toml` | Ruff (L70-128), mypy (L130-226), dev deps (L41-52) | ~260 |
| `app/tests/test_security.py` | 41 security test classes; `TestSDLCSecurityGates` at L1333 checks `scripts/pre-commit` exists | 1467 |
| `.gitignore` | Does not include `.secrets.baseline` (will need to NOT gitignore it) | 72 |

### Existing Hook Script (`scripts/pre-commit`)

Custom bash: (1) ruff --select=S on staged .py, (2) sensitive file scan (.env/.pem/.key), (3) hardcoded postgres creds, (4) AWS/private key/JWT regex detection. Must be preserved — `TestSDLCSecurityGates` asserts on its existence and content (L1336-1364).

### Ruff Version

Pinned at `0.14.2` in both `pyproject.toml` and `uv.lock`. Use matching version in pre-commit config.

### CI Structure

`ci.yml` backend-checks job: checkout → uv install → pip-audit → uv lock --check → ruff format --check → ruff check → ruff --select=S → mypy → pyright → alembic → pytest. Insert `pre-commit run --all-files` as an early step (after install).

## Test Landscape

### Security Convention Tests (L1330-1378)

`TestSDLCSecurityGates` validates:
- `scripts/pre-commit` exists (L1340) — **must keep this file**
- Contains `ruff check --select=S` (L1347)
- Contains `.env`, `.pem`, `.key` (L1354)
- Contains `AKIA`, `PRIVATE KEY` (L1363)
- CI has `--select=S` and `pip-audit` (L1370-1378)

**Impact:** The existing `scripts/pre-commit` bash script MUST remain untouched. The pre-commit framework will run alongside it (detect-secrets adds value on top).

### No Existing Tests for `.pre-commit-config.yaml`

Will add a test to `TestSDLCSecurityGates` asserting `.pre-commit-config.yaml` exists.

## Type Check Baseline

| Tool | Errors |
|------|--------|
| Pyright | 0 (372 source files) |
| MyPy | 0 (372 source files) |
| Ruff | 0 |

No Python source files are modified in this plan — baseline should remain at 0.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `.pre-commit-config.yaml` | Pre-commit framework config with 5 hook sources |
| CREATE | `.secrets.baseline` | detect-secrets baseline (generated) |
| CREATE | `docs/CONTRIBUTING.md` | Contributor onboarding guide |
| UPDATE | `Makefile` L1 (PHONY), after L140 | Add `bootstrap` target, update `install-hooks` |
| UPDATE | `.github/workflows/ci.yml` after L58 | Add pre-commit step |
| UPDATE | `app/tests/test_security.py` after L1364 | Add test for `.pre-commit-config.yaml` existence |

## Implementation Steps

### Step 1: Create `.pre-commit-config.yaml`

**Action:** CREATE `/Users/Berzins/Desktop/VTV/.pre-commit-config.yaml`

```yaml
# Pre-commit hooks — run on every commit
# Install: make bootstrap (or: pre-commit install)
# Manual run: pre-commit run --all-files

repos:
  # Ruff — format + lint (matches pyproject.toml config)
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.2
    hooks:
      - id: ruff-format
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]

  # Standard pre-commit hooks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: [--maxkb=1000]

  # Secrets detection
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: [--baseline, .secrets.baseline]
        exclude: (\.env\.example|\.env\.production\.example|uv\.lock|pnpm-lock\.yaml)$

  # MyPy — strict type checking (local hook to use project's venv + config)
  - repo: local
    hooks:
      - id: mypy
        name: mypy
        entry: uv run mypy app/
        language: system
        types: [python]
        pass_filenames: false
        stages: [pre-push]

  # Existing custom security hook (sensitive files, hardcoded creds, secrets regex)
  - repo: local
    hooks:
      - id: vtv-security
        name: VTV security checks
        entry: scripts/pre-commit
        language: script
        pass_filenames: false
```

**Design decisions:**
- **ruff-pre-commit** uses the exact version pinned in `pyproject.toml` (0.14.2) to avoid drift
- **mypy** runs as a local hook on `pre-push` (not pre-commit) because it takes ~15s — too slow for every commit. Pre-commit should stay <5s. CI catches mypy on every push regardless.
- **detect-secrets** excludes example env files and lock files (they produce false positives)
- **vtv-security** wraps the existing `scripts/pre-commit` so `TestSDLCSecurityGates` keeps passing
- **check-added-large-files** at 1MB threshold prevents accidental binary commits
- **pre-commit-hooks** rev v5.0.0 is the latest stable

**Validation:** `pre-commit run --all-files` (after Step 3 generates baseline)

---

### Step 2: Generate `.secrets.baseline`

**Action:** RUN shell commands

```bash
# Install pre-commit + detect-secrets into the project venv
uv add --dev pre-commit detect-secrets

# Generate baseline (scans all tracked files, produces JSON baseline)
uv run detect-secrets scan \
  --exclude-files '\.env$' \
  --exclude-files '\.env\..*' \
  --exclude-files 'uv\.lock' \
  --exclude-files 'pnpm-lock\.yaml' \
  --exclude-files '\.secrets\.baseline' \
  > .secrets.baseline
```

**Note:** The baseline will contain known false positives (e.g., JWT test fixtures, example keys in docs). These are allowlisted by being in the baseline. Real new secrets will be detected as additions above the baseline.

**Validation:** `uv run detect-secrets audit .secrets.baseline` — review flagged items, mark false positives

---

### Step 3: Update `Makefile`

**Action:** UPDATE `/Users/Berzins/Desktop/VTV/Makefile`

3a. Add `bootstrap` to `.PHONY` line (L1):
```
.PHONY: bootstrap dev dev-be dev-fe ... install-hooks ...
```

3b. Add `bootstrap` target after the `dev-fe` target (after L12, before Docker section):

```makefile
bootstrap: ## First-time setup: install deps + pre-commit hooks
	uv sync --all-extras
	uv run pre-commit install
	uv run pre-commit install --hook-type pre-push
	@echo "Bootstrap complete. Pre-commit hooks installed."
```

3c. Update `install-hooks` target (L137-140) to use pre-commit framework while keeping the bash script copy as fallback:

```makefile
install-hooks: ## Install git pre-commit hooks (pre-commit framework + legacy script)
	uv run pre-commit install
	uv run pre-commit install --hook-type pre-push
	@echo "Pre-commit hooks installed via pre-commit framework."
```

**Validation:** `make bootstrap` runs without error; `make install-hooks` runs without error

---

### Step 4: Add CI pre-commit step

**Action:** UPDATE `/Users/Berzins/Desktop/VTV/.github/workflows/ci.yml`

Insert after the "Install dependencies" step (L58-59) and before "Dependency audit" (L60-61):

```yaml
      - name: Pre-commit checks
        run: |
          uv run pre-commit run --all-files --show-diff-on-failure
```

This runs all pre-commit hooks (ruff, trailing whitespace, detect-secrets, etc.) as an early CI gate. Ruff format/check steps later in the pipeline are now redundant but kept for clearer CI output and independent failure reporting.

**Validation:** CI YAML is valid: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`

---

### Step 5: Create `docs/CONTRIBUTING.md`

**Action:** CREATE `/Users/Berzins/Desktop/VTV/docs/CONTRIBUTING.md`

```markdown
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
- **ruff-format** — auto-fixes formatting
- **ruff** — linting with auto-fix
- **trailing-whitespace / end-of-file-fixer** — file hygiene
- **check-yaml** — validates YAML files
- **check-added-large-files** — blocks files >1MB
- **detect-secrets** — scans for leaked credentials
- **VTV security checks** — Bandit rules, sensitive file detection, hardcoded credential detection

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
- **Vertical Slice Architecture** — features in `app/{feature}/`
- **Structured logging** — `domain.component.action_state` pattern
- See `CLAUDE.md` for full architecture and conventions
```

**Validation:** File exists and is valid markdown

---

### Step 6: Add security convention test for `.pre-commit-config.yaml`

**Action:** UPDATE `/Users/Berzins/Desktop/VTV/app/tests/test_security.py`

Insert after `test_precommit_has_secrets_detection` (after L1364):

```python
    def test_precommit_framework_config_exists(self) -> None:
        """Pre-commit framework config must exist at repo root."""
        from pathlib import Path

        assert Path(".pre-commit-config.yaml").exists(), (
            ".pre-commit-config.yaml missing — run: make bootstrap"
        )
```

Also add a test for `.secrets.baseline`:

```python
    def test_secrets_baseline_exists(self) -> None:
        """detect-secrets baseline must exist for pre-commit hook."""
        from pathlib import Path

        assert Path(".secrets.baseline").exists(), (
            ".secrets.baseline missing — run: uv run detect-secrets scan > .secrets.baseline"
        )
```

**Validation:** `uv run pytest app/tests/test_security.py::TestSDLCSecurityGates -v`

---

## Preflight Warnings

- `test_security.py` L1340: asserts `scripts/pre-commit` exists — do NOT delete the bash script
- `test_security.py` L1347: asserts `ruff check --select=S` in bash script — do NOT modify script content
- `.claude/rules/security.md` references `scripts/pre-commit` and `make install-hooks` — these still work after changes
- The `ship` target (L162) uses `git add -A` which would stage `.secrets.baseline` — this is fine, it should be committed

## Security Checklist

- [x] No new endpoints — CTX-RBAC not applicable
- [x] No hardcoded credentials in `.pre-commit-config.yaml`
- [x] `.secrets.baseline` generated from scan, not hand-crafted
- [x] detect-secrets excludes `.env` files (real secrets)
- [x] CI step doesn't expose secrets (runs pre-commit on code, not env)
- [x] `docs/CONTRIBUTING.md` doesn't contain real credentials

## Verification

- [ ] `make bootstrap` completes successfully
- [ ] `make install-hooks` still works (back-compat)
- [ ] `pre-commit run --all-files` passes on clean tree
- [ ] Committing a file with `GROQ_API_KEY="gsk_realkey"` is blocked by detect-secrets
- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] `uv run pytest app/tests/test_security.py::TestSDLCSecurityGates -v` — all pass
- [ ] Pyright errors = 0 (unchanged from baseline)
- [ ] MyPy errors = 0 (unchanged from baseline)
- [ ] CI YAML valid: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
