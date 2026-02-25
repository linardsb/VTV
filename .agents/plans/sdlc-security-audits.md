# Plan: SDLC-Integrated Security Audit Framework

## Feature Metadata
**Feature Type**: Enhancement (Infrastructure + Tooling)
**Estimated Complexity**: High
**Primary Systems Affected**: CI/CD pipeline, pre-commit hooks, convention tests, scripts, audit documentation

## Feature Description

VTV has completed 5 manual security audits producing 80+ findings across authentication, infrastructure, code quality, and runtime vulnerabilities. While remediation quality is excellent (94 convention tests, 5-layer enforcement), audit initiation is reactive — vulnerabilities sit undetected until someone explicitly audits.

This plan formalizes security auditing into every SDLC phase: development time (enhanced pre-commit), PR time (existing CI + new checks), weekly scheduled scans (new GitHub Actions workflow), on-demand full audits (new script), and structured tracking (audit registry). The framework ensures no code reaches production without passing automated security gates.

## User Story

As a developer working on the VTV platform
I want automated security checks at every stage of my development workflow
So that vulnerabilities are caught early, tracked systematically, and never regress

## Solution Approach

Build on existing 5-layer enforcement by filling gaps identified across 5 audit cycles: secrets scanning (pre-commit), container/nginx validation (scripts), scheduled deep scans (CI), and audit tracking (structured markdown registry).

**Approach Decision:** Incremental enhancement over new security framework because VTV already has strong foundations — the gaps are specific and addressable without rearchitecting CI/CD.

**Alternatives Considered:**
- Full SAST platform (Semgrep Enterprise): Rejected — overkill for single-repo project; Ruff Bandit + convention tests cover same patterns at zero cost
- Security orchestration platform (DefectDojo): Rejected — infrastructure complexity; structured markdown achieves same tracking for a small team
- External audit-as-a-service: Rejected — pre-production project; manual quarterly audits with automated regression prevention is more cost-effective

## Relevant Files

### Core Files
- `CLAUDE.md` — Security practices (lines 194-271), 5-layer enforcement (lines 236-248)
- `.github/workflows/ci.yml` — Current CI pipeline (199 lines, 3 jobs)
- `scripts/pre-commit` — Current pre-commit hook (53 lines, 3 checks)
- `app/tests/test_security.py` — Convention tests (94 tests, class-per-finding)
- `pyproject.toml` — Ruff config with Bandit rules (lines 57-77)

### Similar Features (Examples to Follow)
- `scripts/pre-commit` — Shell script pattern: fast, color-coded, staged-file-only
- `app/tests/test_security.py` (lines 1-60) — Convention test structure: class per finding, `inspect.getsource()`
- `.github/workflows/ci.yml` (lines 60-85) — CI step pattern: name, run, gate behavior

### Files to Modify
- `.github/workflows/ci.yml` — No changes (existing pipeline sufficient for PR-time)
- `scripts/pre-commit` — Add secrets detection (check #4)
- `app/tests/test_security.py` — Add SDLC meta-tests (11 new tests)
- `CLAUDE.md` — Document 6th enforcement layer and framework references
- `Makefile` — Add `security-audit`, `security-audit-quick`, `security-audit-full` targets
- `.claude/commands/be-execute.md` — Add explicit security validation step
- `.claude/commands/be-validate.md` — Elevate security to explicit hard gate with clear sequencing
- `.claude/commands/fe-validate.md` — Add automated frontend security checks (promote to hard gate)
- `.claude/commands/fe-execute.md` — Add automated security verification step
- `.claude/commands/be-end-to-end-feature.md` — Add dedicated security step in Phase 4
- `.claude/commands/fe-end-to-end-page.md` — Add security checks to Phase 4 (currently absent)
- `.claude/commands/commit.md` — Add security audit quick-check before staging

### Files to Create
- `scripts/security-audit.sh` — Comprehensive on-demand audit runner (3 levels)
- `scripts/check-docker-security.py` — Docker Compose security validator
- `scripts/check-nginx-security.py` — nginx config security validator
- `.github/workflows/security.yml` — Dedicated weekly security workflow
- `.agents/audits/audit-template.md` — Standardized finding template
- `.agents/audits/tracking.md` — Living audit finding tracker
- `docs/sdlc-security-framework.md` — Framework documentation

## Research Documentation

- [Ruff Bandit Rules](https://docs.astral.sh/ruff/rules/#flake8-bandit-s)
  - Section: Full rule listing S001-S999
  - Summary: Current SAST coverage via Ruff; identifies which patterns are caught
  - Use for: Understanding what the Bandit lint layer already covers

- [GitHub Actions Security Hardening](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions)
  - Section: Using third-party actions, secrets management
  - Summary: Best practices — pin action versions, minimal permissions
  - Use for: Task 7 (CI pipeline security workflow)

- [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/)
  - Section: V1-V14 verification requirements
  - Summary: Industry standard for what to verify in security audits
  - Use for: Task 1 (audit checklist categories), Task 11 (framework docs)

## Current Security Landscape (Context for Executing Agent)

The executing agent must understand VTV's existing 5-layer security enforcement to avoid duplicating or conflicting with it:

**Layer 1 — Pre-commit hook** (`scripts/pre-commit`, 53 lines): Runs `ruff --select=S` on staged Python files, blocks `.env`/`.pem`/`.key` files, blocks `postgres:postgres@` in config files. Fast (<5s). Gap: no secrets entropy scanning.

**Layer 2 — Convention tests** (`app/tests/test_security.py`, 94 tests): Class-per-finding structure. `TestAllEndpointsRequireAuth` auto-discovers all routes. Tests use `inspect.getsource()` for code pattern verification and `Path().read_text()` for config file checks. Gap: no tests verifying the SDLC framework itself.

**Layer 3 — Secure scaffold** (`/be-create-feature`): Generates routes with `get_current_user`/`require_role` already in every endpoint. No gap.

**Layer 4 — CI security gate** (`.github/workflows/ci.yml`, line 73): Dedicated `ruff check --select=S --no-fix` step. Also has `pip-audit` (line 61) and `uv lock --check` (line 64). Gap: no scheduled runs, no container/nginx validation.

**Layer 5 — CI dependency audit** (same workflow, line 61): `pip-audit --desc` with 2 CVE ignores. Gap: no SBOM, no container image scanning.

**What this plan adds:**
- Layer 1 enhancement: secrets detection patterns (Task 4)
- Layer 2 enhancement: SDLC meta-tests (Tasks 8-9)
- Layer 6 (new): scheduled weekly audit workflow (Task 7)
- New tooling: comprehensive audit script (Task 3), Docker/nginx validators (Tasks 5-6)
- New process: audit tracking registry (Tasks 1-2), framework documentation (Task 11)
- **Command integration:** Security checks wired into all 7 slash commands (Tasks 13-19) so checks run automatically during feature development — not just as standalone tools

## Implementation Plan

### Phase 1: Audit Infrastructure (Tasks 1-4)
Foundation: standardized audit tracking, enhanced pre-commit secrets scanning, comprehensive audit runner.

### Phase 2: Automated Scanning Scripts (Tasks 5-7)
Docker and nginx security validators, dedicated CI workflow for scheduled scans.

### Phase 3: Convention Test Expansion (Tasks 8-10)
Meta-tests verifying the SDLC framework itself, audit coverage completeness, Makefile targets.

### Phase 4: Documentation & Integration (Tasks 11-12)
Framework docs, CLAUDE.md updates.

### Phase 5: Slash Command Integration (Tasks 13-19)
Wire security checks into the 7 slash commands that comprise the actual development workflow. Without this phase, all tooling from Phases 1-3 exists but is never automatically invoked when building or amending features.

### Phase 6: Final Verification (Task 20)
End-to-end verification of all tooling AND command integration.

## Step by Step Tasks

---

### Task 1: Create Audit Finding Template
**File:** `.agents/audits/audit-template.md` (create new)
**Action:** CREATE

Create standardized template for security audit findings with these sections:
- **Metadata block:** Date, auditor, scope, trigger, commit SHA
- **Executive summary:** Total findings, severity breakdown, risk assessment
- **Finding entries** (repeatable): ID, severity (CRITICAL/HIGH/MEDIUM/LOW/INFO), category (AUTH/INFRASTRUCTURE/CODE_QUALITY/DEPENDENCY/CONFIGURATION/DATA_PROTECTION), OWASP mapping, status (OPEN/IN_PROGRESS/REMEDIATED/ACCEPTED_RISK/FALSE_POSITIVE), affected files with line numbers, description, impact, remediation steps, convention test reference, remediation commit
- **Severity summary table:** Count per severity with remediated/open columns
- **Audit trail:** Timestamped lifecycle events (initiated, reviewed, planned, remediated)

The template must be copy-pasteable to start a new audit. Example finding entry:

```markdown
### SA-006-001: Missing Rate Limiting on New Endpoint
- **Severity:** MEDIUM
- **Category:** AUTH
- **OWASP:** A07:2021 - Identification and Authentication Failures
- **Status:** OPEN
- **File(s):** `app/newfeature/routes.py` (lines 45-52)
- **Description:** The `/api/v1/newfeature/search` endpoint lacks rate limiting via slowapi.
- **Impact:** An attacker could perform unlimited searches, potentially causing DoS or data enumeration.
- **Remediation:** Add `@limiter.limit("30/minute")` decorator and `request: Request` parameter.
- **Convention Test:** NEEDED — Add to TestAllEndpointsRequireAuth or create TestNewFeatureRateLimiting
- **Remediated In:** (pending)
```

**Per-task validation:**
- File exists at `.agents/audits/audit-template.md`
- All sections present, markdown renders correctly
- Example finding entry is valid and demonstrates all fields

---

### Task 2: Create Audit Tracking Registry
**File:** `.agents/audits/tracking.md` (create new)
**Action:** CREATE

Create a living registry indexing all past and future security audits with:
- **Active Findings table:** All OPEN findings across audits (currently empty — all remediated)
- **Audit History table** with columns: Audit ID, Date, Trigger, Scope, Findings count, Remediated count, Plan link. Populate with historical data:
  - SA-001 (2026-02-22): 13 findings (5C/3H/5M), all remediated
  - SA-002 (2026-02-23): 16 findings (2C/8H/6M), all remediated, plan: security-hardening-v3.md
  - SA-003 (2026-02-21): 120 findings (8C/29H/49M/34L), partial, ref: AUDIT-SUMMARY.md
  - SA-004 (2026-02-24): ~20 findings, all remediated, plan: security-hardening-v4.md
  - SA-005 (2026-02-25): 16 findings (4C/5H/7M), all remediated (commit 6eb1ed0), plan: security-hardening-v5.md
- **Metrics section:** Total audits, total findings, convention test growth (33→51→84→94), recurring categories
- **SDLC Security Gates reference:** Link to `docs/sdlc-security-framework.md`

**Per-task validation:**
- File exists at `.agents/audits/tracking.md`
- Historical data matches `docs/security_audit*.txt` files

---

### Task 3: Create Comprehensive Security Audit Script
**File:** `scripts/security-audit.sh` (create new)
**Action:** CREATE

Create an executable bash script (`chmod +x`) that consolidates all automated security checks. Match `scripts/pre-commit` style: color output (RED/GREEN/YELLOW), `set -euo pipefail`.

Accept `--level` flag with three levels:

**Quick (<10s):** Bandit lint (`ruff check --select=S app/ --no-fix`), sensitive file scan (`git ls-files | grep` for .env/.pem/.key), hardcoded credential grep.

**Standard (~60s, default):** Quick checks plus dependency audit (`pip-audit --desc` with CVE ignores), lock integrity (`uv lock --check`), type safety (`mypy app/` + `pyright app/`), convention tests (`pytest app/tests/test_security.py -v --tb=short`).

**Full (~120s):** Standard plus full test suite (`pytest -v -m "not integration" --tb=short`), Docker security check (`python3 scripts/check-docker-security.py`), nginx security check (`python3 scripts/check-nginx-security.py`).

Implement a `run_check()` helper function that tracks TOTAL/PASSED/FAILED/SKIPPED counters and prints status per check. Output a summary table at the end. Exit code = number of failed checks.

Handle gracefully: missing tools skip with SKIPPED counter and YELLOW warning.

Key implementation details for the `run_check()` function:
```bash
run_check() {
    local name="$1"
    local cmd="$2"
    TOTAL=$((TOTAL + 1))
    printf "${BLUE}[%d] %s${NC}\n" "$TOTAL" "$name"
    if eval "$cmd" > /dev/null 2>&1; then
        PASSED=$((PASSED + 1))
        printf "  ${GREEN}PASS${NC}\n"
    else
        FAILED=$((FAILED + 1))
        printf "  ${RED}FAIL${NC}\n"
    fi
}
```

For the `--level` argument parsing, use a simple positional approach:
```bash
LEVEL="standard"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --level) LEVEL="$2"; shift 2 ;;
        quick|standard|full) LEVEL="$1"; shift ;;
        *) echo "Usage: $0 [--level quick|standard|full]"; exit 1 ;;
    esac
done
```

The CVE ignores in `pip-audit` must match the existing CI config exactly:
`uv run pip-audit --desc --ignore-vuln CVE-2025-69872 --ignore-vuln CVE-2024-23342`

**Per-task validation:**
- `chmod +x scripts/security-audit.sh`
- `bash -n scripts/security-audit.sh` (syntax check passes)
- `./scripts/security-audit.sh --level quick` completes successfully

---

### Task 4: Enhance Pre-commit Hook with Secrets Detection
**File:** `scripts/pre-commit` (modify existing — currently 53 lines)
**Action:** UPDATE

Add check #4 after existing check #3 (hardcoded postgres credentials). Scan staged file diffs for:
- AWS access keys: `AKIA[0-9A-Z]{16}`
- Private key material: `-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----`
- JWT tokens (full 3-part): `eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}`

Exclusions: test files (`test_*`, `*/tests/*`), docs (`docs/`, `*.md`), `.env.example`. Only check staged diffs (`git diff --cached`), not full file content. Must add <2s to current <5s budget.

Set `FAILED=1` if any pattern matches (consistent with existing checks). Each pattern gets its own descriptive RED message.

**Per-task validation:**
- `bash -n scripts/pre-commit` (syntax check passes)
- Existing 3 checks still function (stage a normal Python file, verify hook passes)
- Test: stage a file containing `AKIAIOSFODNN7EXAMPLE`, verify hook blocks

---

### Task 5: Create Docker Security Check Script
**File:** `scripts/check-docker-security.py` (create new)
**Action:** CREATE

Python script parsing `docker-compose.yml` with `yaml.safe_load()` (NOT string parsing — lesson from v5 code review). Skip one-shot containers (`migrate`).

Validate per long-running service:
1. `security_opt` contains `no-new-privileges:true`
2. `cap_drop` contains `ALL`
3. `deploy.resources.limits` exists (prevent resource exhaustion)

Output: one PASS/FAIL line per check per service. Exit code = number of FAILs.

Include `from __future__ import annotations`, proper type hints, and a docstring. Handle missing `docker-compose.yml` gracefully (print SKIP, exit 0).

Script skeleton:
```python
#!/usr/bin/env python3
"""Docker Compose security validator for VTV platform."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml  # PyYAML — available as transitive dependency


def main() -> int:
    compose_path = Path("docker-compose.yml")
    if not compose_path.exists():
        print("SKIP: docker-compose.yml not found")
        return 0

    with compose_path.open() as f:
        compose = yaml.safe_load(f)

    services: dict[str, dict[str, object]] = compose.get("services", {})
    failures = 0
    skip_services = {"migrate"}  # One-shot containers

    for name, config in services.items():
        if name in skip_services:
            continue
        # Check each security property...
    return failures

if __name__ == "__main__":
    sys.exit(main())
```

The current `docker-compose.yml` has these long-running services that must be checked: `db`, `redis`, `app`, `cms`, `nginx`. The `migrate` container is one-shot and should be skipped.

**Per-task validation:**
- `uv run ruff format scripts/check-docker-security.py`
- `uv run ruff check --fix scripts/check-docker-security.py` passes
- `python3 scripts/check-docker-security.py` runs against current config (all PASS)

---

### Task 6: Create nginx Security Check Script
**File:** `scripts/check-nginx-security.py` (create new)
**Action:** CREATE

Python script reading `nginx/nginx.conf` as plain text. Use regex matching for header validation (no nginx parser needed).

Validate:
1. `Content-Security-Policy` header present (`add_header\s+Content-Security-Policy`)
2. `X-Frame-Options` header present
3. `X-Content-Type-Options` header present
4. `Strict-Transport-Security` header present
5. No `unsafe-eval` in CSP (WARN, not FAIL — may be transitional)
6. Rate limiting configured (`limit_req_zone` directive present)

Output: PASS/FAIL/WARN per check. Exit code = number of FAILs. Handle missing file gracefully.

**Per-task validation:**
- `uv run ruff format scripts/check-nginx-security.py`
- `uv run ruff check --fix scripts/check-nginx-security.py` passes
- `python3 scripts/check-nginx-security.py` runs against current config

---

### Task 7: Create Dedicated Security CI Workflow
**File:** `.github/workflows/security.yml` (create new)
**Action:** CREATE

GitHub Actions workflow with triggers:
- `schedule: cron: '0 2 * * 0'` (weekly Sunday 02:00 UTC)
- `workflow_dispatch` with `level` input (choice: quick/standard/full, default: full)

Single job `security-audit` with:
- Services: PostgreSQL 18 (pgvector) + Redis 7 (matching existing CI service config)
- Environment: `DATABASE_URL`, `REDIS_URL`, `ENVIRONMENT=development`
- Steps: checkout, install uv, install Python 3.12, install deps (`uv sync --frozen`), run migrations (`alembic upgrade head`), run audit script (tee output to `audit-results.txt`, `continue-on-error: true`), upload results artifact (90-day retention)
- Concurrency: `group: security-audit`, `cancel-in-progress: false` (never cancel security scans)

Pin action versions: `actions/checkout@v4`, `astral-sh/setup-uv@v6`, `actions/upload-artifact@v4`.

The PostgreSQL and Redis service config must EXACTLY match the existing CI workflow (`ci.yml` lines 19-42) — same images (`pgvector/pgvector:pg18`, `redis:7-alpine`), same ports (5433:5432, 6379:6379), same healthchecks. Copy the service blocks verbatim from `ci.yml`.

The audit step must use `continue-on-error: true` so the artifact upload always runs even on check failures.

**Per-task validation:**
- `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/security.yml'))"` (valid YAML)
- Workflow references correct script path and has valid cron syntax
- Service config matches `ci.yml` (same images, ports, healthchecks)

---

### Task 8: Add SDLC Meta-Convention Tests
**File:** `app/tests/test_security.py` (modify existing)
**Action:** UPDATE

Add at the end of the file, after all existing test classes:

```python
# === SDLC Security Framework Verification ===

class TestSDLCSecurityGates:
    """Verify that all SDLC security gates are properly configured."""
```

10 tests verifying:
1. `test_precommit_hook_exists` — `Path("scripts/pre-commit").exists()`
2. `test_precommit_has_bandit_check` — `"ruff check --select=S"` in pre-commit content
3. `test_precommit_has_sensitive_file_check` — `.env`, `.pem`, `.key` in content
4. `test_precommit_has_secrets_detection` — `"AKIA"` or `"PRIVATE KEY"` in content
5. `test_ci_has_security_audit_step` — `"--select=S"` in `ci.yml`
6. `test_ci_has_dependency_audit` — `"pip-audit"` in `ci.yml`
7. `test_ci_has_lock_file_integrity` — `"uv lock --check"` in `ci.yml`
8. `test_security_audit_script_exists` — `Path("scripts/security-audit.sh").exists()`
9. `test_scheduled_security_workflow_exists` — `Path(".github/workflows/security.yml").exists()` + `"cron"` in content
10. `test_audit_tracking_exists` — `Path(".agents/audits/tracking.md").exists()`

All tests use `from pathlib import Path` and read file content via `Path(...).read_text()`. Follow the existing test class pattern — no pytest marks needed (these are fast file-system checks, not integration tests).

Example test implementation:
```python
class TestSDLCSecurityGates:
    """Verify that all SDLC security gates are properly configured."""

    def test_precommit_hook_exists(self) -> None:
        """Pre-commit hook must exist and be executable."""
        from pathlib import Path
        hook = Path("scripts/pre-commit")
        assert hook.exists(), "Pre-commit hook missing at scripts/pre-commit"

    def test_precommit_has_bandit_check(self) -> None:
        """Pre-commit hook must include Bandit security lint."""
        from pathlib import Path
        content = Path("scripts/pre-commit").read_text()
        assert "ruff check --select=S" in content

    def test_ci_has_security_audit_step(self) -> None:
        """CI pipeline must have a dedicated security audit step."""
        from pathlib import Path
        ci_content = Path(".github/workflows/ci.yml").read_text()
        assert "ruff check" in ci_content and "--select=S" in ci_content

    # ... remaining 7 tests follow same pattern
```

Note: Place imports inside each test method (matching existing convention in this file — see `TestStreamingUploadSizeLimit` which imports `from app.core.rate_limit import limiter` inside the test method).

**Per-task validation:**
- `uv run ruff format app/tests/test_security.py`
- `uv run ruff check --fix app/tests/test_security.py` passes
- `uv run pytest app/tests/test_security.py::TestSDLCSecurityGates -v` — all 10 pass

---

### Task 9: Add Audit Coverage Completeness Test
**File:** `app/tests/test_security.py` (modify existing)
**Action:** UPDATE

Add after `TestSDLCSecurityGates`:

```python
class TestAuditCoverageCompleteness:
    """Verify all historical audit finding categories have convention test coverage."""
    REQUIRED_TEST_CLASSES: ClassVar[list[str]] = [...]
```

Define `REQUIRED_TEST_CLASSES` as a `ClassVar[list[str]]` listing all 23+ existing test class names (every `Test*` class in the file including the new `TestSDLCSecurityGates`). Import `ClassVar` from `typing`.

Single test `test_all_audit_categories_have_tests` that:
1. Imports `app.tests.test_security` as a module
2. Collects all `Test*` class names via `dir()` + `isinstance(..., type)`
3. Asserts every entry in `REQUIRED_TEST_CLASSES` exists in the module
4. Provides actionable error message listing missing classes

The `REQUIRED_TEST_CLASSES` list must include ALL existing test classes. To build this list, the executing agent should first read `app/tests/test_security.py` and extract every class name starting with `Test`. As of this plan, the known classes are:

```python
REQUIRED_TEST_CLASSES: ClassVar[list[str]] = [
    "TestStreamingUploadSizeLimit",
    "TestFilenameSanitization",
    "TestIlikeWildcardEscaping",
    "TestAllEndpointsRequireAuth",
    "TestJwtAlgorithmSafety",
    "TestBcryptRounds",
    "TestPasswordComplexityOnCorrectSchema",
    "TestNginxSecurityHeaders",
    "TestNoDebugLoggingInSecurityPaths",
    "TestSQLInjectionPosture",
    "TestContainerHardening",
    "TestDependencyScanningInCI",
    "TestBackupInfrastructure",
    "TestGDPRDeletion",
    "TestCSRFProtection",
    "TestQuotaIPTracking",
    "TestLogoutRevocation",
    "TestRefreshTokenSingleUse",
    "TestZipBombDetection",
    "TestTimingAttackPrevention",
    "TestFilePathExposure",
    "TestRequestIdSanitization",
    "TestDbContainerCapDrop",
    "TestSDLCSecurityGates",       # Added in Task 8
    "TestAuditCoverageCompleteness",  # This class itself
]
```

IMPORTANT: The executing agent MUST verify this list matches the actual classes in the file. Read the file first, collect all `class Test*` names, and use the real list. Some class names above may differ slightly from the actual code.

**Per-task validation:**
- `uv run ruff format app/tests/test_security.py`
- `uv run ruff check --fix app/tests/test_security.py` passes
- `uv run pytest app/tests/test_security.py::TestAuditCoverageCompleteness -v` — passes

---

### Task 10: Add Makefile Targets
**File:** `Makefile` (modify existing)
**Action:** UPDATE

Add near existing security targets (`security-check`, `install-hooks`):

```makefile
## Security audit (quick - pre-commit equivalent, <10s)
security-audit-quick:
	./scripts/security-audit.sh --level quick

## Security audit (standard - CI equivalent, ~60s)
security-audit:
	./scripts/security-audit.sh --level standard

## Security audit (full - all checks including container + nginx, ~120s)
security-audit-full:
	./scripts/security-audit.sh --level full
```

CRITICAL: Use tab indentation (not spaces) for recipe lines.

**Per-task validation:**
- `make security-audit-quick` runs and completes
- Verify targets appear in `make help` (if help target exists)

---

### Task 11: Create SDLC Security Framework Documentation
**File:** `docs/sdlc-security-framework.md` (create new)
**Action:** CREATE

Create framework documentation covering:

1. **Overview** — Security enforced at every SDLC phase, no code reaches production without gates
2. **Phase 1: Development (Local)** — Pre-commit hook checks (4 checks, <7s), install via `make install-hooks`, bypass via `--no-verify`
3. **Phase 2: Code Review (PR)** — CI pipeline checks (13 steps across 3 jobs), all hard-fail gates
4. **Phase 3: Scheduled Audit (Weekly)** — `.github/workflows/security.yml`, Sunday 02:00 UTC, full level, artifact upload
5. **Phase 4: On-Demand Audit** — `make security-audit-full`, before releases/after incidents
6. **Phase 5: Manual Audit (Quarterly)** — Process: run full audit, manual code review, document via template, create plan, update tracking
7. **Convention Test Categories** — List all test classes with the audit finding they prevent
8. **Adding New Security Checks** — 5-step process: fix, add test, update coverage list, update docs, update tracking
9. **Metrics** — Findings per audit, remediation time, test count, false positive rate

Key content requirements for each section:

**Phase 2 (Code Review):** List all 13 CI steps (pip-audit, uv lock --check, ruff format, ruff check, ruff --select=S, mypy, pyright, migrations, pytest with 105 convention tests, frontend type-check, frontend lint, frontend build, E2E Playwright).

**Adding New Security Checks (5-step process):** Fix vulnerability → add convention test class → add to `REQUIRED_TEST_CLASSES` → update framework docs → update tracking registry.

**Metrics KPIs:** Findings per audit (declining trend), time to remediation (<48h CRITICAL, <1wk HIGH), convention test count (monotonically growing), false positive rate (<10%), pre-commit bypass rate.

**Per-task validation:**
- File exists at `docs/sdlc-security-framework.md`
- All referenced scripts and files exist
- All 5 SDLC phases documented with check tables

---

### Task 12: Update CLAUDE.md
**File:** `CLAUDE.md` (modify existing)
**Action:** UPDATE

Three changes:

1. **Key Reference Documents section** — After `.agents/code-reviews/AUDIT-SUMMARY.md` line, add:
   - `docs/sdlc-security-framework.md` — SDLC security audit framework (5 phases, automated gates)
   - `.agents/audits/tracking.md` — Living security audit finding tracker
   - `scripts/security-audit.sh` — Comprehensive security audit runner (quick/standard/full)

2. **Automated Security Enforcement section** — Change "5 layers" to "6 layers" throughout. Add layer 6 after layer 5:
   ```
   6. **Scheduled security audit** (`.github/workflows/security.yml`) — Weekly full security audit (Bandit, pip-audit, type checkers, convention tests, Docker security, nginx headers). Results as artifacts. On-demand via `workflow_dispatch`.
   ```

3. **Convention test count** — Find all occurrences of "94 tests" and update to "105 tests" (94 existing + 11 new SDLC tests).

**Per-task validation:**
- `grep "6 layers\|6\. \*\*Scheduled" CLAUDE.md` shows new layer
- `grep "sdlc-security-framework" CLAUDE.md` shows references
- `grep "105 tests" CLAUDE.md` shows updated count (verify no "94 tests" remain)

---

### Task 13: Integrate Security into `/be-execute`
**File:** `.claude/commands/be-execute.md` (modify existing)
**Action:** UPDATE

**Change 1:** In Step 4 (validation suite, after the `pytest -v -m "not integration"` block around line 166), add an explicit security validation step:

```markdown
**Security convention tests (explicit gate):**

```bash
uv run pytest app/tests/test_security.py -v --tb=short
```

Security convention tests verify all endpoints require auth, JWT safety, bcrypt rounds, nginx headers, container hardening, and SDLC gates. This runs separately from the general test suite to ensure security regressions are immediately visible — not buried in 600+ test results.
```

**Change 2:** In Step 5 (post-implementation checks, line 197), update the existing security checklist item from:
```
- [ ] **Security convention tests pass**: `uv run pytest app/tests/test_security.py -v`
```
to:
```
- [ ] **Security convention tests pass** (already verified in Step 4 — confirm no regressions from post-impl edits)
```

This elevates security from a post-implementation checklist item to an explicit validation gate that runs as part of the automated sequence.

**Per-task validation:**
- `grep "Security convention tests" .claude/commands/be-execute.md` shows the new step
- The command still has valid markdown structure

---

### Task 14: Integrate Security into `/be-validate`
**File:** `.claude/commands/be-validate.md` (modify existing)
**Action:** UPDATE

The existing Steps 9-10 already cover security. Enhance them:

**Change 1:** Add a header note after the Step 10 description (after line 110) to make the hard-gate nature explicit:

```markdown
Steps 9-10 are **hard gates** — security lint violations or convention test failures MUST be fixed before committing. These are not warnings.
```

**Change 2:** Update the OUTPUT scorecard (lines 114-127) to visually group security as a distinct section:

```
Validation Results:
  1. Ruff format:          PASS / FAIL
  2. Ruff check:           PASS / FAIL  [N issues]
  3. MyPy:                 PASS / FAIL  [N errors]
  4. Pyright:              PASS / FAIL  [N errors]
  5. Pytest (unit):        PASS / FAIL  [X passed, Y failed]
  6. Pytest (integration): PASS / FAIL / SKIPPED (Docker not running)
  7. SDK sync:             IN SYNC / OUT OF SYNC / SKIPPED (FastAPI not running)
  8. Server:               PASS / FAIL / SKIPPED (Docker not running)
  --- Security Gates ---
  9. Security lint:        PASS / FAIL  [N violations]
 10. Security conventions: PASS / FAIL  [X passed, Y failed]

Overall: ALL PASS / X FAILURES / Y WARNINGS
```

**Per-task validation:**
- `grep "hard gates" .claude/commands/be-validate.md` shows new emphasis
- `grep "Security Gates" .claude/commands/be-validate.md` shows grouped output

---

### Task 15: Integrate Security into `/fe-validate`
**File:** `.claude/commands/fe-validate.md` (modify existing)
**Action:** UPDATE

This is the **highest-impact change** — frontend currently has NO automated security checks.

**Change 1:** Replace Check 7 (lines 82-87) entirely. The old manual grep-based check becomes an automated 2-part gate:

```markdown
### 7. Security Patterns (HARD GATE)

**7a. Automated pattern scan** — Run these greps and FAIL if any match:

```bash
# Hardcoded API URLs (should use NEXT_PUBLIC_* env vars)
grep -rn "http://localhost:8123\|http://127.0.0.1:8123" cms/apps/web/src/ --include="*.ts" --include="*.tsx" | grep -v node_modules | grep -v ".next"

# Auth tokens in localStorage (must use httpOnly cookies)
grep -rn "localStorage\.\(set\|get\)Item.*\(token\|auth\|session\|jwt\)" cms/apps/web/src/ --include="*.ts" --include="*.tsx"

# Unsanitized innerHTML (XSS vector)
grep -rn "dangerouslySetInnerHTML" cms/apps/web/src/ --include="*.tsx" | grep -v "DOMPurify"

# Hardcoded credentials
grep -rn "password.*=.*['\"]" cms/apps/web/src/ --include="*.ts" --include="*.tsx" | grep -v "type\|interface\|placeholder\|label\|name="
```

Each grep that returns results is a FAIL. Report file:line for each match.

**7b. Manual verification checklist** (report as WARN, not FAIL):
- [ ] Cookies use `SameSite=Lax` or `Strict`
- [ ] Redirects preserve locale
- [ ] External links use `rel="noopener noreferrer"`
- [ ] File uploads validate type AND size client-side
```

**Change 2:** Update the OUTPUT section (lines 89-104) to include security as a hard gate:

```
Frontend Validation Results:
  1. TypeScript:          PASS / FAIL  [N errors]
  2. Lint:                PASS / FAIL  [N issues]
  3. Build:               PASS / FAIL
  4. Security patterns:   PASS / FAIL  [N violations]
  --- Soft Gates ---
  5. Design system:       PASS / WARN  [N violations]
  6. i18n completeness:   PASS / FAIL  [N missing keys]
  7. Accessibility:       PASS / WARN  [N issues]

Overall: ALL PASS / X FAILURES / Y WARNINGS
```

**Change 3:** Update the gate description (lines 103-104) from:
```
Checks 1-3 are **hard gates** — must pass before committing.
Checks 4-6 are **soft gates** — warnings are reported but don't block commits.
```
to:
```
Checks 1-4 are **hard gates** — must pass before committing.
Checks 5-7 are **soft gates** — warnings are reported but don't block commits.
```

**Per-task validation:**
- `grep "HARD GATE" .claude/commands/fe-validate.md` shows security promoted
- `grep "Security patterns" .claude/commands/fe-validate.md` shows new check
- Output section shows 7 checks with security at position 4

---

### Task 16: Integrate Security into `/fe-execute`
**File:** `.claude/commands/fe-execute.md` (modify existing)
**Action:** UPDATE

**Change 1:** After Step 6 (Design system compliance scan, around line 181), add a new Step 7:

```markdown
### 7. Automated security verification

Run the same security pattern scans as `/fe-validate` Check 7a:

```bash
# Hardcoded API URLs
grep -rn "http://localhost:8123\|http://127.0.0.1:8123" cms/apps/web/src/ --include="*.ts" --include="*.tsx" | grep -v node_modules | grep -v ".next"

# Auth tokens in localStorage
grep -rn "localStorage\.\(set\|get\)Item.*\(token\|auth\|session\|jwt\)" cms/apps/web/src/ --include="*.ts" --include="*.tsx"

# Unsanitized innerHTML
grep -rn "dangerouslySetInnerHTML" cms/apps/web/src/ --include="*.tsx" | grep -v "DOMPurify"

# Hardcoded credentials
grep -rn "password.*=.*['\"]" cms/apps/web/src/ --include="*.ts" --include="*.tsx" | grep -v "type\|interface\|placeholder\|label\|name="
```

If any violations found, fix them immediately before proceeding to the Security Checklist.
```

This ensures security patterns are verified automatically during execution, not left to the manual checklist at the end.

**Per-task validation:**
- `grep "Automated security verification" .claude/commands/fe-execute.md` shows new step
- The existing Security Checklist (lines 183-191) remains as a manual backup

---

### Task 17: Integrate Security into `/be-end-to-end-feature`
**File:** `.claude/commands/be-end-to-end-feature.md` (modify existing)
**Action:** UPDATE

In Phase 4 (Validate, after the `pytest -v -m "not integration"` block around line 94), add an explicit security validation step:

```markdown
**Security gate (explicit — must pass):**

```bash
uv run pytest app/tests/test_security.py -v --tb=short
```

Verify all security convention tests pass. If this feature added new endpoints, `TestAllEndpointsRequireAuth` will catch missing auth dependencies. If new SDLC tooling was modified, `TestSDLCSecurityGates` will catch broken gates.
```

Also add to the Phase 4 error recovery (after line 111):
```markdown
- Security test failures are treated as hard failures — do NOT proceed to Phase 5
```

**Per-task validation:**
- `grep "Security gate" .claude/commands/be-end-to-end-feature.md` shows new step
- Security is explicitly called out between pytest and error recovery

---

### Task 18: Integrate Security into `/fe-end-to-end-page`
**File:** `.claude/commands/fe-end-to-end-page.md` (modify existing)
**Action:** UPDATE

This is the **second highest-impact change** — frontend e2e pipeline currently has ZERO security checks.

In Phase 4 (Validate, after the soft gate checks around line 92), add a security gate:

```markdown
**Security gate (hard — must pass):**

Run automated security pattern scans on all new/modified `.tsx` and `.ts` files:

```bash
# Hardcoded API URLs
grep -rn "http://localhost:8123\|http://127.0.0.1:8123" cms/apps/web/src/ --include="*.ts" --include="*.tsx" | grep -v node_modules | grep -v ".next"

# Auth tokens in localStorage
grep -rn "localStorage\.\(set\|get\)Item.*\(token\|auth\|session\|jwt\)" cms/apps/web/src/ --include="*.ts" --include="*.tsx"

# Unsanitized innerHTML without sanitization
grep -rn "dangerouslySetInnerHTML" cms/apps/web/src/ --include="*.tsx" | grep -v "DOMPurify"

# Hardcoded credentials
grep -rn "password.*=.*['\"]" cms/apps/web/src/ --include="*.ts" --include="*.tsx" | grep -v "type\|interface\|placeholder\|label\|name="
```

Any match is a FAIL. Fix before proceeding to Phase 5.
```

Also add to Phase 4 error recovery (after line 102):
```markdown
- Security pattern violations are hard failures — do NOT proceed to Phase 5
```

**Per-task validation:**
- `grep "Security gate" .claude/commands/fe-end-to-end-page.md` shows new section
- Security is positioned as a hard gate alongside type-check/lint/build

---

### Task 19: Integrate Security into `/commit`
**File:** `.claude/commands/commit.md` (modify existing)
**Action:** UPDATE

**Change 1:** Enhance Step 2 (Safety checks, lines 31-35) to include a quick security scan:

After the existing sensitive file check, add:

```markdown
- Run a quick security lint on staged Python files (same as pre-commit hook):
  ```bash
  git diff --cached --name-only --diff-filter=ACMR | grep '\.py$' | xargs -r uv run ruff check --select=S --no-fix
  ```
  If violations found, STOP and report them. This catches Bandit-level issues even when the pre-commit hook isn't installed.

- For frontend changes, run quick pattern scan on staged `.ts`/`.tsx` files:
  ```bash
  git diff --cached --name-only --diff-filter=ACMR | grep -E '\.(ts|tsx)$' | xargs -r grep -n "dangerouslySetInnerHTML\|localStorage.*token\|localStorage.*auth"
  ```
  If violations found, WARN the user (soft gate for commit, hard gate in `/fe-validate`).
```

**Change 2:** Update the Note at line 35 from:
```
- **Note:** If the pre-commit hook is installed (`make install-hooks`), it will also automatically block...
```
to:
```
- **Note:** The inline checks above work even WITHOUT the pre-commit hook. If the hook IS installed (`make install-hooks`), it provides additional coverage (secrets detection, hardcoded postgres credentials).
```

**Per-task validation:**
- `grep "ruff check --select=S" .claude/commands/commit.md` shows security lint step
- `grep "dangerouslySetInnerHTML" .claude/commands/commit.md` shows frontend pattern check
- The commit command still follows the 6-step structure

---

### Task 20: Final Verification
**Action:** VERIFY

Run end-to-end verification of both tooling AND command integration:

**Tooling verification:**
1. All new scripts executable: `ls -la scripts/security-audit.sh scripts/check-docker-security.py scripts/check-nginx-security.py`
2. Quick audit passes: `./scripts/security-audit.sh --level quick`
3. Docker check passes: `python3 scripts/check-docker-security.py`
4. nginx check passes: `python3 scripts/check-nginx-security.py`
5. New convention tests pass: `uv run pytest app/tests/test_security.py -v -k "SDLC or AuditCoverage"`
6. Full existing test suite still passes: `uv run pytest -v -m "not integration" --tb=short`

**Command integration verification:**
7. `grep "Security convention tests\|Security gate\|security-audit" .claude/commands/be-execute.md` — shows security step
8. `grep "Security Gates\|hard gates" .claude/commands/be-validate.md` — shows security grouping
9. `grep "HARD GATE\|Security patterns" .claude/commands/fe-validate.md` — shows promoted security
10. `grep "Automated security verification" .claude/commands/fe-execute.md` — shows security step
11. `grep "Security gate" .claude/commands/be-end-to-end-feature.md` — shows explicit gate
12. `grep "Security gate" .claude/commands/fe-end-to-end-page.md` — shows new security checks
13. `grep "ruff check --select=S" .claude/commands/commit.md` — shows inline security lint

**Per-task validation:**
- All 13 verification steps produce expected output

---

## Logging Events

No new application logging events — this is infrastructure tooling with console output only.

## Testing Strategy

### Unit Tests
**Location:** `app/tests/test_security.py`
- `TestSDLCSecurityGates` (10 tests) — Verify all security gates exist and are configured
- `TestAuditCoverageCompleteness` (1 test) — Verify all audit categories have convention tests

### Edge Cases
- Pre-commit hook with no staged files — passes silently
- Audit script with missing tools — skips with WARN
- Convention tests when working directory varies — `Path()` handles this

## Acceptance Criteria

This feature is complete when:
- [ ] Audit finding template exists at `.agents/audits/audit-template.md`
- [ ] Audit tracking registry with all 5 historical audits at `.agents/audits/tracking.md`
- [ ] Security audit script runs at 3 levels via `scripts/security-audit.sh`
- [ ] Pre-commit hook detects leaked secrets (AWS keys, JWT tokens, private keys)
- [ ] Docker security validator passes against current `docker-compose.yml`
- [ ] nginx security validator passes against current `nginx/nginx.conf`
- [ ] Weekly security workflow exists at `.github/workflows/security.yml`
- [ ] 11 new convention tests verify SDLC framework integrity
- [ ] CLAUDE.md updated with 6-layer enforcement and framework references
- [ ] Framework docs at `docs/sdlc-security-framework.md`
- [ ] `make security-audit-quick` completes in <10s
- [ ] `/be-execute` has explicit security convention test step in validation
- [ ] `/be-validate` has security grouped as explicit hard gate in output
- [ ] `/fe-validate` has automated security pattern checks promoted to hard gate
- [ ] `/fe-execute` has automated security verification step
- [ ] `/be-end-to-end-feature` Phase 4 has dedicated security gate
- [ ] `/fe-end-to-end-page` Phase 4 has security checks (previously absent)
- [ ] `/commit` has inline security lint for staged files
- [ ] All existing tests pass (zero regressions)

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 20 tasks completed in order
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-5)
- [ ] Command integration verified (Task 20 checks 7-13)
- [ ] No deviations from plan (or deviations documented)
- [ ] Ready for `/commit`

## Final Validation (5-Level Pyramid)

**Level 1: Syntax & Style**
```bash
uv run ruff format .
uv run ruff check --fix .
```

**Level 2: Type Safety**
```bash
uv run mypy app/
uv run pyright app/
```

**Level 3: Security Tests**
```bash
uv run pytest app/tests/test_security.py -v
```

**Level 4: Full Test Suite**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Security Audit Script**
```bash
./scripts/security-audit.sh --level quick
```

**Success:** Levels 1-4 exit code 0, all tests pass. Level 5 confirms new tooling works.

## Dependencies

- Shared utilities: None (infrastructure tooling)
- New dependencies: None (PyYAML available as transitive dep via pydantic-settings)
- New env vars: None

## Known Pitfalls

1. **Shell scripts must use `set -euo pipefail`** — catches undefined variables and pipe failures. The existing `scripts/pre-commit` uses `set -e` only; new scripts should use the stricter `set -euo pipefail`.
2. **Docker check must use `yaml.safe_load()`** — NOT string parsing. The security-hardening-v5 code review found that `compose.split("redis:")[0]` breaks if service order changes. Always parse YAML properly.
3. **Convention tests must use `Path()`** — resilient to working directory changes. Tests run from the repo root via pytest, so `Path("scripts/pre-commit")` works. Do NOT use absolute paths.
4. **Pre-commit patterns must exclude test files** — secrets in test fixtures are intentional. The JWT token pattern `eyJ...` appears in auth test files legitimately. Always filter staged files to exclude `test_*` and `*/tests/*`.
5. **CI workflow needs `continue-on-error: true`** on the audit step — results must be uploaded as artifacts even when security checks fail. Without this, the upload step is skipped on failure.
6. **Makefile recipe lines must use tabs** — spaces cause `Makefile:N: *** missing separator. Stop.` errors. The executing agent's editor must preserve tab characters.
7. **Python scripts stay in `scripts/`** — they are tooling, not application code. Do NOT place them under `app/` where mypy/pyright would type-check them with strict mode.
8. **Count update must be global** — search ALL occurrences of "94 tests" in CLAUDE.md (appears at least 3 times: in Security Practices, Automated Security Enforcement items 2 and 5). Missing any creates an inconsistency.
9. **`yaml` import needs PyYAML** — available as transitive dependency via `pydantic-settings` → `pydantic` → etc. Do NOT add it to `pyproject.toml` dependencies. If import fails in scripts, the user can `pip install pyyaml`.
10. **Ruff per-file-ignores don't cover `scripts/`** — Python files in `scripts/` are subject to full Ruff rules. Include `# noqa` comments where needed (e.g., `T201` for print statements if not already exempted).
11. **Command files use markdown code blocks with triple backticks** — When editing `.claude/commands/*.md` files, ensure bash code blocks are properly fenced. A missing closing ``` breaks the entire command parser.
12. **`/fe-validate` grep patterns must exclude `node_modules` and `.next`** — Without `--exclude-dir` or `grep -v`, security scans will match thousands of false positives in vendor code. Always pipe through `grep -v node_modules | grep -v ".next"`.
13. **Command edits must preserve `allowed-tools` frontmatter** — Each command file has a YAML frontmatter block specifying which tools the command can use. Adding new bash commands (like grep or security-audit.sh) must not violate the allowed-tools constraint. If the command needs new tools, update the frontmatter.
14. **Frontend security greps must account for TypeScript type definitions** — `grep "password"` matches interface definitions like `password: string` which are NOT security violations. Always filter out `type\|interface\|placeholder\|label` patterns.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Read `scripts/pre-commit` (53 lines) to understand existing hook structure
- [ ] Read first 100 lines of `app/tests/test_security.py` to understand convention test patterns
- [ ] Read `.github/workflows/ci.yml` to understand existing CI structure
- [ ] Read `Makefile` to find existing security targets and understand target naming conventions
- [ ] Understood the solution approach and why alternatives were rejected
- [ ] Clear on task execution order (1-13, no skipping)
- [ ] Validation commands are executable in this environment

## Notes

**Design Decisions:**
- Shell script for audit runner (not Python) — consistent with `scripts/pre-commit` pattern, no import overhead, faster startup for quick level
- Python for Docker/nginx checks — YAML parsing and regex matching are cleaner in Python
- Convention tests in existing file (not separate) — keeps all security tests in one discoverable location, avoids test discovery fragmentation
- Weekly scheduled audit (not daily) — balances CI minutes cost with detection latency; daily is overkill for a pre-production project
- Markdown for audit tracking (not database/JIRA) — aligns with existing `.agents/` directory pattern; machine-readable, version-controlled, zero infrastructure
- **Command integration is mandatory, not optional** — Creating security scripts without wiring them into slash commands means developers never invoke them. Security checks that require manual invocation get skipped. Every command that can modify code must automatically verify security.
- **Frontend security is grep-based, not test-based** — Unlike backend (which has `test_security.py` as a pytest suite), frontend security checks use grep patterns because Next.js doesn't have an equivalent convention test framework. The grep patterns are duplicated across `/fe-validate`, `/fe-execute`, and `/fe-end-to-end-page` intentionally — each command needs to be self-contained.
- **`/commit` gets lightweight checks only** — The commit command adds inline `ruff --select=S` on staged Python files and grep patterns on staged TS/TSX files. Full security audits belong in `/be-validate` and `/fe-validate`. The commit check is a fast safety net, not a comprehensive scan.

**Future Enhancements (not in this plan):**
- DAST integration (OWASP ZAP) in E2E pipeline — requires running app + ZAP proxy in Docker
- Container image scanning (Trivy/Grype) — requires Docker build in security workflow
- SBOM generation (CycloneDX) for government procurement compliance
- Signed commits enforcement — requires team GPG key infrastructure
- Semgrep custom rules for VTV-specific patterns (ILIKE injection, file path exposure)
- Security findings → GitHub Issues automation via GitHub API
- detect-secrets integration with baseline file — more sophisticated entropy-based scanning
