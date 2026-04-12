# High Latency Runbook

## Alert

- **Name:** `VTVHighLatencyP95` / `VTVHighLatencyP99`
- **Severity:** warning (p95) / critical (p99)
- **Fires when:** p95 latency > 500ms for 10m, or p99 latency > 2s for 10m

## Impact

Users experience slow page loads in the CMS dashboard. Agent tool calls may time out. GTFS-RT feed consumers see stale data.

## Investigation

1. Check which endpoints are slow: query `topk(10, histogram_quantile(0.95, rate(vtv_http_request_duration_seconds_bucket{status!~"5.."}[5m])) by (path))`
2. Check database: `vtv_db_pool_checked_out` gauge - if near pool limit, see [db-pool-exhaustion.md](db-pool-exhaustion.md)
3. Check Redis connectivity: `redis-cli -h <redis-host> ping`
4. Check external API latency: `vtv_agent_tool_duration_seconds` histogram for slow tool calls
5. Check recent deploys: `git log --oneline -10` on the production server
6. Check host resources: `docker stats` for CPU/memory pressure

## Remediation

- **Quick fix:** If a single endpoint is the outlier, check its specific dependency (DB query, external API, Redis). Restart the app container if unresponsive: `docker compose restart app`
- **Root cause fix:** Add caching for slow queries, optimize N+1 database access patterns, increase DB pool size if connection-bound

## Escalation

- If not resolved in 15 minutes: escalate to backend engineering lead

## Related

- SLO: [docs/slos.md](../slos.md)
- Metrics: [app/core/metrics.py](../../app/core/metrics.py)
- Health probes: [app/core/health.py](../../app/core/health.py)
