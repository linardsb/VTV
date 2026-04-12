# VTV Operational Runbooks

Quick-reference index for on-call engineers.

## Runbooks

| Runbook | Scope | Last Updated |
|---------|-------|-------------|
| [Credential Rotation](credential-rotation.md) | All secrets (JWT, DB, Redis, API keys, SSH, SSL) | 2026-04-12 |
| [High Latency](high-latency.md) | API p95/p99 latency SLO breach | 2026-04-12 |
| [High Error Rate](high-error-rate.md) | 5xx error rate SLO breach | 2026-04-12 |
| [Circuit Breaker Open](circuit-breaker-open.md) | LLM provider circuit breaker open | 2026-04-12 |
| [Poller Stale](poller-stale.md) | Background poller liveness failure | 2026-04-12 |
| [DB Pool Exhaustion](db-pool-exhaustion.md) | Database connection pool saturation | 2026-04-12 |

## General Guidance

- **Before any production change:** Back up the database (`./scripts/db-backup.sh`)
- **After any credential change:** Verify via health endpoints (`/health/ready`)
- **Rollback:** Keep the old `.env.production` as `.env.production.bak` before editing
- **Escalation:** If health checks fail after rotation, rollback immediately, then investigate

## Related Documentation

- [SDLC Security Framework](../sdlc-security-framework.md) - security enforcement gates
- [CONTRIBUTING.md](../CONTRIBUTING.md) - credential protection in development
- [CLAUDE.md](../../CLAUDE.md) - project-level operations overview
