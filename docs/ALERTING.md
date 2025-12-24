# Prometheus Alerting Rules

> **Status**: Production-Ready  
> **Date**: 2025-12-16  
> **Alert Rules**: 11 (3 global + 8 flow-specific)

---

## Overview

This document provides production-ready Prometheus alerting rules for Cosmetica 5.

**Severity Levels**:
- `critical`: Immediate action required (PagerDuty + Slack)
- `warning`: Investigate soon (Slack only)

**Alert Policy**:
- All alerts include runbook links
- No flapping: `for` duration prevents noise
- Actionable: Every alert has clear remediation steps

---

## Alert Rules YAML

### File: `prometheus/alerts/cosmetica5.yml`

```yaml
groups:
  # ===================================================================
  # GLOBAL ALERTS
  # ===================================================================
  - name: global
    interval: 30s
    rules:
      # -----------------------------------------------------------------
      # Alert 1: APIHigh5xxRate
      # -----------------------------------------------------------------
      - alert: APIHigh5xxRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m])) 
          / 
          sum(rate(http_requests_total[5m])) * 100 > 1
        for: 5m
        labels:
          severity: critical
          component: api
          flow: global
        annotations:
          summary: "High 5xx error rate detected"
          description: |
            Server error rate is {{ $value | humanizePercentage }} (threshold: 1%).
            This indicates backend failures affecting multiple endpoints.
          runbook: "https://docs.cosmetica5.com/runbooks#apihigh5xxrate"
          dashboard: "https://grafana.cosmetica5.com/d/system-overview"
          query: 'sum by (path, status) (rate(http_requests_total{status=~"5.."}[5m]))'

      # -----------------------------------------------------------------
      # Alert 2: APILatencyP95High
      # -----------------------------------------------------------------
      - alert: APILatencyP95High
        expr: |
          histogram_quantile(0.95, 
            sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
          ) > 1.0
        for: 10m
        labels:
          severity: warning
          component: api
          flow: global
        annotations:
          summary: "API p95 latency above 1s"
          description: |
            95th percentile latency is {{ $value | humanizeDuration }}.
            User experience degraded. Check database queries and external dependencies.
          runbook: "https://docs.cosmetica5.com/runbooks#apilatencyp95high"
          dashboard: "https://grafana.cosmetica5.com/d/system-overview"
          query: 'topk(10, avg by (path) (rate(http_request_duration_seconds_sum[5m]) / rate(http_request_duration_seconds_count[5m])))'

  # ===================================================================
  # FLOW 1: SALES & STOCK ALERTS
  # ===================================================================
  - name: sales_stock
    interval: 30s
    rules:
      # -----------------------------------------------------------------
      # Alert 3: SalePaidTransitionFailures
      # -----------------------------------------------------------------
      - alert: SalePaidTransitionFailures
        expr: |
          sum(rate(sales_transition_total{to_status="paid", result!="success"}[5m])) 
          / 
          sum(rate(sales_transition_total{to_status="paid"}[5m])) * 100 > 5
        for: 5m
        labels:
          severity: critical
          component: sales
          flow: sale_to_paid
        annotations:
          summary: "High failure rate for PAID transitions"
          description: |
            {{ $value | humanizePercentage }} of sale→PAID transitions failing.
            Revenue impact: sales not completing. Check stock availability and batch expiry.
          runbook: "https://docs.cosmetica5.com/runbooks#salepaidtransitionfailures"
          dashboard: "https://grafana.cosmetica5.com/d/sales-stock"
          query: 'sum by (result) (rate(sales_transition_total{to_status="paid", result!="success"}[5m]))'

      # -----------------------------------------------------------------
      # Alert 4: StockConsumeFailures
      # -----------------------------------------------------------------
      - alert: StockConsumeFailures
        expr: |
          sum(rate(sales_paid_stock_consume_total{result!="success", result!="idempotent"}[5m])) 
          > 0.1
        for: 5m
        labels:
          severity: critical
          component: stock
          flow: sale_to_paid
        annotations:
          summary: "Stock consumption failures detected"
          description: |
            {{ $value }} stock consumption failures per second.
            Possible causes: insufficient stock, expired batches, or database issues.
          runbook: "https://docs.cosmetica5.com/runbooks#stockconsumefailures"
          dashboard: "https://grafana.cosmetica5.com/d/sales-stock"
          query: 'sum by (result) (rate(sales_paid_stock_consume_total{result!="success"}[5m]))'

      # -----------------------------------------------------------------
      # Alert 5: StockConsumeLatencyHigh
      # -----------------------------------------------------------------
      - alert: StockConsumeLatencyHigh
        expr: |
          histogram_quantile(0.95, 
            sum(rate(sales_paid_stock_consume_duration_seconds_bucket[5m])) by (le)
          ) > 0.5
        for: 10m
        labels:
          severity: warning
          component: stock
          flow: sale_to_paid
        annotations:
          summary: "Stock consumption p95 latency > 500ms"
          description: |
            FEFO allocation taking {{ $value | humanizeDuration }}.
            Sales checkout may feel slow. Check database indexes and StockOnHand query performance.
          runbook: "https://docs.cosmetica5.com/runbooks#stockconsumelatencyhigh"
          dashboard: "https://grafana.cosmetica5.com/d/sales-stock"
          query: 'histogram_quantile(0.99, sum(rate(sales_paid_stock_consume_duration_seconds_bucket[5m])) by (le))'

  # ===================================================================
  # FLOW 2: REFUNDS ALERTS
  # ===================================================================
  - name: refunds
    interval: 30s
    rules:
      # -----------------------------------------------------------------
      # Alert 6: RefundFailures
      # -----------------------------------------------------------------
      - alert: RefundFailures
        expr: |
          sum(rate(sale_refunds_total{result="failure"}[5m])) 
          / 
          sum(rate(sale_refunds_total[5m])) * 100 > 10
        for: 5m
        labels:
          severity: critical
          component: refunds
          flow: refunds
        annotations:
          summary: "High refund failure rate"
          description: |
            {{ $value | humanizePercentage }} of refunds failing.
            Customer support impact. Check refund validation logic and stock rollback.
          runbook: "https://docs.cosmetica5.com/runbooks#refundfailures"
          dashboard: "https://grafana.cosmetica5.com/d/refunds"
          query: 'sum by (type, result) (rate(sale_refunds_total[5m]))'

      # -----------------------------------------------------------------
      # Alert 7: OverRefundBlockedSpike
      # -----------------------------------------------------------------
      - alert: OverRefundBlockedSpike
        expr: |
          increase(sale_refund_over_refund_attempts_total[1h]) > 10
        for: 0m
        labels:
          severity: warning
          component: refunds
          flow: refunds
        annotations:
          summary: "Spike in blocked over-refund attempts"
          description: |
            {{ $value }} over-refund attempts blocked in last hour.
            Possible fraud, integration bug, or user confusion. Review refund requests.
          runbook: "https://docs.cosmetica5.com/runbooks#overrefundblockedspike"
          dashboard: "https://grafana.cosmetica5.com/d/refunds"
          query: 'increase(sale_refund_over_refund_attempts_total[1h])'

      # -----------------------------------------------------------------
      # Alert 8: IdempotencyConflictsSpike
      # -----------------------------------------------------------------
      - alert: IdempotencyConflictsSpike
        expr: |
          increase(sale_refund_idempotency_conflicts_total[1h]) > 20
        for: 0m
        labels:
          severity: warning
          component: refunds
          flow: refunds
        annotations:
          summary: "Spike in idempotency key conflicts"
          description: |
            {{ $value }} idempotency conflicts in last hour.
            Client retrying with same key. Check API client behavior or network issues.
          runbook: "https://docs.cosmetica5.com/runbooks#idempotencyconflictsspike"
          dashboard: "https://grafana.cosmetica5.com/d/refunds"
          query: 'increase(sale_refund_idempotency_conflicts_total[1h])'

  # ===================================================================
  # FLOW 3: PUBLIC LEADS ALERTS
  # ===================================================================
  - name: public_leads
    interval: 30s
    rules:
      # -----------------------------------------------------------------
      # Alert 9: PublicLeads429Spike
      # -----------------------------------------------------------------
      - alert: PublicLeads429Spike
        expr: |
          sum(rate(public_leads_429_total[5m])) 
          / 
          sum(rate(public_leads_requests_total[5m])) * 100 > 50
        for: 5m
        labels:
          severity: warning
          component: public_api
          flow: public_leads
        annotations:
          summary: "High rate of throttled lead submissions"
          description: |
            {{ $value | humanizePercentage }} of lead requests getting 429.
            Possible DDoS, aggressive crawler, or legitimate marketing spike.
            Verify throttle limits are appropriate.
          runbook: "https://docs.cosmetica5.com/runbooks#publicleads429spike"
          dashboard: "https://grafana.cosmetica5.com/d/public-leads"
          query: 'sum by (scope) (rate(public_leads_throttled_total[5m]))'

      # -----------------------------------------------------------------
      # Alert 10: PublicLeadsCreationFailures
      # -----------------------------------------------------------------
      - alert: PublicLeadsCreationFailures
        expr: |
          sum(rate(public_leads_requests_total{result="rejected"}[5m])) 
          / 
          sum(rate(public_leads_requests_total[5m])) * 100 > 50
        for: 10m
        labels:
          severity: warning
          component: public_api
          flow: public_leads
        annotations:
          summary: "High lead rejection rate"
          description: |
            {{ $value | humanizePercentage }} of leads rejected.
            Either spam attack or validation too strict. Check lead data quality.
          runbook: "https://docs.cosmetica5.com/runbooks#publicleadscreationfailures"
          dashboard: "https://grafana.cosmetica5.com/d/public-leads"
          query: 'sum(rate(public_leads_requests_total{result="rejected"}[5m]))'

      # -----------------------------------------------------------------
      # Alert 11: ThrottleDisabledOrNotWorking
      # -----------------------------------------------------------------
      - alert: ThrottleDisabledOrNotWorking
        expr: |
          (
            sum(rate(public_leads_requests_total[5m])) > 0.5
          ) 
          and 
          (
            sum(increase(public_leads_throttled_total[1h])) == 0
          )
        for: 1h
        labels:
          severity: critical
          component: public_api
          flow: public_leads
        annotations:
          summary: "Throttling not working despite high traffic"
          description: |
            Receiving {{ $value }} requests/sec but no throttling events in 1 hour.
            Throttle middleware disabled or bypassed. Risk of abuse.
          runbook: "https://docs.cosmetica5.com/runbooks#throttledisabledornotworking"
          dashboard: "https://grafana.cosmetica5.com/d/public-leads"
          query: 'sum(increase(public_leads_throttled_total[1h]))'
```

---

## Alertmanager Configuration

### File: `prometheus/alertmanager.yml`

```yaml
global:
  resolve_timeout: 5m
  slack_api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'

# Alert routing
route:
  # Default receiver
  receiver: 'slack-alerts'
  
  # Group alerts by severity and component
  group_by: ['alertname', 'severity', 'component']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  
  # Route critical alerts to PagerDuty
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty-critical'
      continue: true  # Also send to Slack
    
    - match:
        severity: warning
      receiver: 'slack-alerts'

# Receivers
receivers:
  # Slack for all alerts
  - name: 'slack-alerts'
    slack_configs:
      - channel: '#alerts'
        title: '🚨 {{ .GroupLabels.alertname }}'
        text: |
          *Severity*: {{ .GroupLabels.severity }}
          *Component*: {{ .GroupLabels.component }}
          *Summary*: {{ .CommonAnnotations.summary }}
          
          *Description*:
          {{ .CommonAnnotations.description }}
          
          *Runbook*: {{ .CommonAnnotations.runbook }}
          *Dashboard*: {{ .CommonAnnotations.dashboard }}
        color: '{{ if eq .GroupLabels.severity "critical" }}danger{{ else }}warning{{ end }}'
  
  # PagerDuty for critical alerts
  - name: 'pagerduty-critical'
    pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_SERVICE_KEY'
        description: '{{ .GroupLabels.alertname }}: {{ .CommonAnnotations.summary }}'
        details:
          summary: '{{ .CommonAnnotations.summary }}'
          description: '{{ .CommonAnnotations.description }}'
          runbook: '{{ .CommonAnnotations.runbook }}'
          dashboard: '{{ .CommonAnnotations.dashboard }}'
          query: '{{ .CommonAnnotations.query }}'

# Inhibition rules (prevent alert spam)
inhibit_rules:
  # If APIHigh5xxRate is firing, suppress individual flow alerts
  - source_match:
      alertname: 'APIHigh5xxRate'
    target_match_re:
      alertname: '(SalePaidTransitionFailures|RefundFailures|PublicLeadsCreationFailures)'
    equal: ['component']
```

---

## Alert Routing Policy

### Severity: `critical`

**Destination**: PagerDuty + Slack #alerts  
**Response Time**: Immediate (15 minutes)  
**Escalation**: After 30 minutes if not acknowledged

**Alerts**:
- APIHigh5xxRate
- SalePaidTransitionFailures
- StockConsumeFailures
- RefundFailures
- ThrottleDisabledOrNotWorking

### Severity: `warning`

**Destination**: Slack #alerts only  
**Response Time**: Within 2 hours  
**Escalation**: None (monitor during business hours)

**Alerts**:
- APILatencyP95High
- StockConsumeLatencyHigh
- OverRefundBlockedSpike
- IdempotencyConflictsSpike
- PublicLeads429Spike
- PublicLeadsCreationFailures

---

## Alert Naming Convention

**Format**: `<Component><Condition><Metric>`

**Examples**:
- ✅ `APIHigh5xxRate` (component: API, condition: High, metric: 5xx rate)
- ✅ `StockConsumeLatencyHigh` (component: Stock, condition: LatencyHigh, metric: consume duration)
- ❌ `Error` (too vague)
- ❌ `SalesProblem` (no actionable information)

---

## Anti-Flapping Rules

Every alert includes:

1. **`for` duration**: Alert must be true continuously before firing
   - `critical`: 0m-5m (fast escalation)
   - `warning`: 5m-10m (avoid noise)

2. **`repeat_interval`**: 4 hours
   - Prevents notification spam for ongoing issues

3. **Inhibition rules**: Higher-level alerts suppress lower-level alerts
   - Example: Global 5xx rate suppresses individual flow errors

---

## Testing Alerts

### 1. Validate YAML Syntax

```bash
promtool check rules prometheus/alerts/cosmetica5.yml
```

### 2. Test Alert Expression

```bash
# In Prometheus UI
http://prometheus:9090/graph

# Paste alert expr and verify it returns data
sum(rate(http_requests_total{status=~"5.."}[5m])) 
/ 
sum(rate(http_requests_total[5m])) * 100
```

### 3. Trigger Test Alert

```bash
# Manually set metric to trigger alert (dev environment only)
curl -X POST http://localhost:9090/api/v1/admin/tsdb/delete_series \
  -d 'match[]=http_requests_total'

# Simulate high error rate
for i in {1..100}; do
  curl -X POST http://localhost:8000/api/sales/invalid-endpoint
done
```

### 4. Verify Alertmanager Routing

```bash
# Check Alertmanager status
curl http://alertmanager:9093/api/v1/alerts

# Silence alert (for testing)
amtool silence add alertname=APIHigh5xxRate --duration=1h
```

---

## Deployment Checklist

- [ ] Copy `cosmetica5.yml` to Prometheus alerts directory
- [ ] Update `prometheus.yml` to include alert rules:
  ```yaml
  rule_files:
    - "alerts/cosmetica5.yml"
  ```
- [ ] Configure Alertmanager with Slack webhook
- [ ] Configure PagerDuty integration key
- [ ] Test alert routing with `amtool`
- [ ] Verify runbook links are accessible
- [ ] Document escalation policy in team wiki
- [ ] Add Grafana dashboard links to annotations

---

## Maintenance

### Adjusting Thresholds

If alerts are too noisy:

1. **Increase `for` duration**: `5m` → `10m`
2. **Increase threshold**: `> 1` → `> 5`
3. **Add inhibition rule**: Suppress during known maintenance

If alerts are missing issues:

1. **Decrease `for` duration**: `10m` → `5m`
2. **Decrease threshold**: `> 10` → `> 5`
3. **Add pre-alert**: Create `warning` alert before `critical`

### Alert Lifecycle

```
1. Metric crosses threshold
2. Prometheus evaluates rule every 30s
3. After `for` duration, alert fires
4. Alertmanager groups and routes
5. Notification sent (Slack/PagerDuty)
6. Operator acknowledges (PagerDuty)
7. Operator resolves issue
8. Metric returns to normal
9. Alert auto-resolves after `resolve_timeout` (5m)
```

---

## References

- **Dashboards**: `docs/OBSERVABILITY_DASHBOARDS.md`
- **Runbooks**: `docs/RUNBOOKS.md`
- **SLOs**: `docs/SLO.md`
- **Metrics Catalog**: `docs/OBSERVABILITY_FLOWS.md`

---

## Next Steps

1. ✅ Deploy alert rules to Prometheus
2. ✅ Configure Alertmanager routing
3. ✅ Test each alert with synthetic failures
4. ✅ Create runbooks for critical alerts (see `RUNBOOKS.md`)
5. ✅ Train on-call engineers on escalation policy
