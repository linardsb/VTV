# High Error Rate Runbook

## Alert

- **Name:** `VTVHighErrorRate`
- **Severity:** critical
- **Fires when:** 5xx error rate exceeds 1% for 5 minutes

## Impact

Users see error pages or failed API calls. CMS dashboard functionality is degraded. Agent tool calls may fail.

## Investigation

1. Check application logs: `docker compose logs app --tail=200 | grep ERROR`
2. Identify failing endpoints: query `topk(5, rate(vtv_http_request_duration_seconds_count{status=~"5.."}[5m]) by (path, status))`
3. Check recent deploys: `git log --oneline -5` on production - was there a recent push?
4. Check database health: `docker compose exec db pg_isready` and `vtv_db_pool_checked_out` gauge
5. Check Redis: `docker compose exec redis redis-cli ping`
6. Check `/health/deep` for degraded dependencies

## Remediation

- **Quick fix:** If caused by a recent deploy, rollback: `git revert HEAD && git push && make deploy`
- **Quick fix:** If a single endpoint is failing, check its specific handler for unhandled exceptions
- **Root cause fix:** Add error handling for the failing code path, add regression tests

## Escalation

- If not resolved in 15 minutes: escalate to backend engineering lead

## Related

- SLO: [docs/slos.md](../slos.md)
- Metrics: [app/core/metrics.py](../../app/core/metrics.py)
- Health probes: [app/core/health.py](../../app/core/health.py)
