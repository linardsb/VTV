# Circuit Breaker Open Runbook

## Alert

- **Name:** `VTVCircuitBreakerOpen`
- **Severity:** warning
- **Fires when:** Circuit breaker state > 1 (open) for 5 minutes

## Impact

LLM-powered features are degraded. Agent chat will return fallback responses or errors. Knowledge base search may be unavailable. Memory operations that require embeddings will fail.

## Investigation

1. Identify which provider is affected: check `vtv_circuit_breaker_state` labels for `provider` value
2. Check provider status page (OpenAI: status.openai.com, Anthropic: status.anthropic.com)
3. Check application logs for the provider error: `docker compose logs app --tail=100 | grep -i "circuit\|breaker\|openai\|anthropic"`
4. Check if the issue is network-related: `curl -s https://api.openai.com/v1/models -H "Authorization: Bearer test"` (expect 401, not timeout)
5. Check `/health/deep` for the `llm_providers` probe status

## Remediation

- **Quick fix:** If the provider is back up, the circuit breaker will auto-recover (half_open -> closed on next successful call). Monitor `vtv_circuit_breaker_state` gauge
- **Quick fix:** If urgent, restart the app to reset breaker state: `docker compose restart app`
- **Root cause fix:** If a specific provider is chronically unreliable, configure a fallback provider in `app/core/config.py`

## Escalation

- If not resolved in 15 minutes: escalate to backend engineering lead
- If provider outage is confirmed: post status update to team, wait for provider recovery

## Related

- SLO: [docs/slos.md](../slos.md)
- Metrics: [app/core/metrics.py](../../app/core/metrics.py)
- Health probes: [app/core/health.py](../../app/core/health.py)
