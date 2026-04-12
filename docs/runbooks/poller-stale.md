# Poller Stale Runbook

## Alert

- **Name:** `VTVPollerStale`
- **Severity:** critical
- **Fires when:** Any background poller has not ticked in > 240s for 2 minutes

## Impact

Depends on which poller is stale:
- `transit_feed` - GTFS-RT vehicle positions stop updating, map shows stale data
- `alert_evaluator` - Alert conditions are not evaluated, notifications delayed
- `geofence_evaluator` - Geofence entry/exit events are not detected
- `anomaly_evaluator` - Off-route and stuck vehicle detection stops
- `off_route_evaluator` - Off-route detection stops
- `memory_compaction` / `memory_promotion` - Agent memory growth is unbounded (non-urgent)

## Investigation

1. Identify which poller is stale: check `vtv_poller_last_tick_seconds` labels for `poller_name`
2. Check if the app container is running: `docker compose ps app`
3. Check application logs for the poller: `docker compose logs app --tail=200 | grep "<poller_name>"`
4. Check Redis connectivity (pollers use Redis for leader election): `docker compose exec redis redis-cli ping`
5. Check if asyncio event loop is blocked: look for long-running synchronous operations in logs
6. Check `/health/deep` and `/health/ready` for overall service health

## Remediation

- **Quick fix:** Restart the app container to restart all pollers: `docker compose restart app`
- **Quick fix:** If Redis is down, restart Redis first: `docker compose restart redis`, then `docker compose restart app`
- **Root cause fix:** Check if the poller's task raised an unhandled exception (search logs for `_failed` events). Add error handling if missing

## Escalation

- If not resolved in 15 minutes: escalate to backend engineering lead
- If `transit_feed` poller is stale: public-facing real-time data is affected

## Related

- SLO: [docs/slos.md](../slos.md)
- Metrics: [app/core/metrics.py](../../app/core/metrics.py)
- Health probes: [app/core/health.py](../../app/core/health.py)
- Graceful shutdown: [app/core/shutdown.py](../../app/core/shutdown.py)
