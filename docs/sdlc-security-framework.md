# SDLC Security Audit Framework

Security is enforced at every phase of the software development lifecycle. No code reaches production without passing automated security gates.

## Overview

VTV uses a 6-layer security enforcement model integrated into 5 SDLC phases. Security checks run automatically during feature development, code review, and deployment - not as optional manual steps.

## Phase 1: Development (Local)

**When:** Before every `git commit` (automatic via pre-commit hook)
**Install:** `make install-hooks`
**Bypass:** `git commit --no-verify` (logged, auditable)

| Check | What it catches | Time |
|-------|----------------|------|
| Bandit lint (`ruff --select=S`) | Hardcoded creds, `assert` in prod, `exec`/`eval` | <2s |
| Sensitive file scan | `.env`, `*.pem`, `*.key` staged for commit | <1s |
| Hardcoded postgres credentials | `postgres:postgres@` in config files | <1s |
| Secrets detection | AWS keys (`AKIA...`), private keys, JWT tokens | <1s |

**Total:** <5s. All checks must pass for commit to proceed.

## Phase 2: Code Review (PR)

**When:** Every push to `main` and every pull request
**Config:** `.github/workflows/ci.yml`

### Backend Checks (9 steps)
1. pip-audit - Known CVE scanning
2. uv lock --check - Lock file integrity
3. ruff format --check - Code formatting
4. ruff check - Lint rules
5. ruff check --select=S - **Dedicated security audit step**
6. mypy - Type safety
7. pyright - Type safety (second checker)
8. alembic upgrade head - Migration integrity
9. pytest - All tests including 105 security convention tests

### Frontend Checks (3 steps)
1. TypeScript type-check
2. ESLint
3. Next.js build

### E2E Tests (depends on backend + frontend passing)
1. Docker Compose full stack
2. Playwright browser tests

**All steps are hard-fail gates.** Any failure blocks the PR.

## Phase 3: Scheduled Audit (Weekly)

**When:** Every Sunday at 02:00 UTC
**Config:** `.github/workflows/security.yml`
**On-demand:** GitHub Actions > Security Audit > Run workflow

Runs the full security audit script with all checks:
- Bandit lint + sensitive file scan + hardcoded credentials
- pip-audit + lock integrity
- mypy + pyright
- Security convention tests (105 tests)
- Full unit test suite
- Docker Compose security validation
- nginx security header validation

Results uploaded as GitHub Actions artifact (90-day retention).

## Phase 4: On-Demand Audit

**When:** Before releases, after incidents, during feature reviews
**Commands:**

```bash
make security-audit-quick   # <10s  - Bandit, sensitive files, creds
make security-audit          # ~60s  - Quick + deps, types, convention tests
make security-audit-full     # ~120s - Standard + full tests, Docker, nginx
```

## Phase 5: Manual Audit (Quarterly)

**Process:**
1. Run `make security-audit-full`
2. Manual code review of auth, middleware, config
3. Document findings using `.agents/audits/audit-template.md`
4. Create hardening plan via `/be-planning`
5. Execute via `/be-execute`
6. Update `.agents/audits/tracking.md`

## Convention Test Categories

Each test class in `app/tests/test_security.py` prevents regression of a specific security finding:

| Test Class | What It Prevents |
|-----------|-----------------|
| TestStreamingUploadSizeLimit | File upload bypassing size limits |
| TestFilenameSanitization | Path traversal via malicious filenames |
| TestAllEndpointsRequireAuth | Endpoints without authentication |
| TestNoDebugSecurityLogging | Debug-level logging in security paths |
| TestJwtAlgorithmNotNone | JWT `alg: none` attack |
| TestBcryptRoundsSufficient | Weak password hashing |
| TestContainerHardening | Containers running as root |
| TestDependencySecurity | Missing CVE scanning in CI |
| TestZipBombProtection | ZIP bomb denial of service |
| TestTimingAttackPrevention | Email enumeration via timing |
| TestSDLCSecurityGates | SDLC framework integrity |
| TestAuditCoverageCompleteness | Missing test coverage for findings |

See the full list of 40+ test classes in `app/tests/test_security.py`.

## Adding New Security Checks

When a new vulnerability is discovered or a new security requirement is added:

1. **Fix** the vulnerability in application code
2. **Add convention test** class to `app/tests/test_security.py`
3. **Update coverage list** - add the new class name to `TestAuditCoverageCompleteness.REQUIRED_TEST_CLASSES`
4. **Update docs** - add the test to the Convention Test Categories table above
5. **Update tracking** - add finding to `.agents/audits/tracking.md`

## Metrics

Track these KPIs across audits:

| Metric | Target | Current |
|--------|--------|---------|
| Findings per audit | Declining trend | 16 (SA-005) |
| Time to remediation (CRITICAL) | <48 hours | <48h |
| Time to remediation (HIGH) | <1 week | <1 week |
| Convention test count | Monotonically growing | 105 |
| False positive rate | <10% | ~5% |
| Pre-commit bypass rate | <5% | N/A (tracking not implemented) |

## Slash Command Integration

Security checks are wired into every development command:

| Command | Security Integration |
|---------|---------------------|
| `/be-execute` | Explicit security convention test step in validation |
| `/be-validate` | Security lint + convention tests as hard gates (steps 9-10) |
| `/fe-validate` | Automated security pattern scanning (hard gate) |
| `/fe-execute` | Automated security verification after implementation |
| `/be-end-to-end-feature` | Dedicated security gate in Phase 4 |
| `/fe-end-to-end-page` | Security pattern checks in Phase 4 |
| `/commit` | Inline security lint on staged files |
