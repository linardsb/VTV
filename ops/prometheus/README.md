# VTV Prometheus Alert Rules

Alert rules for the VTV backend, keyed to OPS-2.1 metrics from `app/core/metrics.py`.

## Contents

- `alerts.yml` - 7 alert rules across 5 groups (latency, errors, infrastructure, pollers, agent tools)

## Loading into Prometheus

Add to your `prometheus.yml`:

```yaml
rule_files:
  - /path/to/vtv/ops/prometheus/alerts.yml
```

Reload Prometheus after changing rules:

```bash
curl -X POST http://<prometheus-host>:9090/-/reload
```

## Validation

Validate YAML structure (no Prometheus needed):

```bash
make validate-alerts
```

Full validation with promtool (if installed):

```bash
promtool check rules ops/prometheus/alerts.yml
```

Test alert routing with amtool:

```bash
amtool config routes test --config.file=alertmanager.yml
```

## Related

- [SLO Definitions](../../docs/slos.md) - targets, error budgets, rationale
- [Runbooks](../../docs/runbooks/) - remediation procedures for each alert
- [Metrics Source](../../app/core/metrics.py) - OPS-2.1 metric definitions
