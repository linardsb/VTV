# DB Pool Exhaustion Runbook

## Alert

- **Name:** `VTVDBPoolExhaustion`
- **Severity:** critical
- **Fires when:** DB connection pool utilization exceeds 80% for 5 minutes

## Impact

New database queries queue waiting for connections. API response times increase. At 100% utilization, requests start failing with connection timeout errors.

## Investigation

1. Check pool metrics: `vtv_db_pool_checked_out` (active connections) and `vtv_db_pool_overflow` (overflow connections)
2. Current pool config: pool_size=3, max_overflow=5, total capacity=8. Alert fires at > 6.4 connections
3. Check for slow queries: `docker compose exec db psql -U postgres vtv_db -c "SELECT pid, now() - pg_stat_activity.query_start AS duration, query FROM pg_stat_activity WHERE state = 'active' ORDER BY duration DESC LIMIT 10;"`
4. Check for idle-in-transaction connections: `docker compose exec db psql -U postgres vtv_db -c "SELECT pid, state, now() - state_change AS idle_time FROM pg_stat_activity WHERE state = 'idle in transaction' ORDER BY idle_time DESC;"`
5. Check application logs for connection errors: `docker compose logs app --tail=200 | grep -i "pool\|connection\|timeout"`

## Remediation

- **Quick fix:** Kill long-running or idle-in-transaction connections: `docker compose exec db psql -U postgres vtv_db -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND now() - state_change > interval '5 minutes';"`
- **Quick fix:** Restart the app to reset the connection pool: `docker compose restart app`
- **Root cause fix:** Increase `DB_POOL_SIZE` and `DB_POOL_MAX_OVERFLOW` in environment config. Optimize slow queries identified in step 3. Ensure all database sessions are properly closed (check `get_db()` usage)

## Escalation

- If not resolved in 15 minutes: escalate to backend engineering lead

## Related

- SLO: [docs/slos.md](../slos.md)
- Metrics: [app/core/metrics.py](../../app/core/metrics.py)
- Database config: [app/core/config.py](../../app/core/config.py)
- Pool settings: `DB_POOL_SIZE`, `DB_POOL_MAX_OVERFLOW`, `DB_POOL_RECYCLE` in `.env`
