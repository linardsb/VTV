# VTV Operational Runbooks

Quick-reference index for on-call engineers.

## Runbooks

| Runbook | Scope | Last Updated |
|---------|-------|-------------|
| [Credential Rotation](credential-rotation.md) | All secrets (JWT, DB, Redis, API keys, SSH, SSL) | 2026-04-12 |

## General Guidance

- **Before any production change:** Back up the database (`./scripts/db-backup.sh`)
- **After any credential change:** Verify via health endpoints (`/health/ready`)
- **Rollback:** Keep the old `.env.production` as `.env.production.bak` before editing
- **Escalation:** If health checks fail after rotation, rollback immediately, then investigate

## Related Documentation

- [SDLC Security Framework](../sdlc-security-framework.md) - security enforcement gates
- [CONTRIBUTING.md](../CONTRIBUTING.md) - credential protection in development
- [CLAUDE.md](../../CLAUDE.md) - project-level operations overview
