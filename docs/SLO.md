# Service Level Objectives (SLOs)

> **Status**: Production-Ready  
> **Date**: 2025-12-16  
> **SLOs Defined**: 3 flows

---

## Overview

This document defines Service Level Objectives (SLOs), Service Level Indicators (SLIs), and burn-rate alerts for Cosmetica 5.

**Purpose**: Quantify reliability targets and detect when we're burning error budget too fast.

**Methodology**: Google SRE burn-rate alerts with multi-window detection.

---

## SLO Framework

### Definitions

- **SLO (Service Level Objective)**: Target reliability (e.g., 99.9% availability)
- **SLI (Service Level Indicator)**: Measurement of actual reliability (PromQL query)
- **Error Budget**: Allowed failure rate (e.g., 0.1% for 99.9% SLO)
- **Burn Rate**: How fast we're consuming error budget (e.g., 2x = twice as fast as normal)

### Alerting Philosophy

**Multi-Window Burn Rate**:
- Short window (5m-1h): Detect fast burns (incidents)
- Long window (6h-24h): Detect slow burns (degradation)

**Thresholds**:
- **2x burn rate**: Warning (notify team)
- **5x burn rate**: Critical (page on-call)

---

## Flow 1: Sales & Stock

### SLO 1.1: Availability (Sale → PAID)

**Target**: 99.9% of sale transitions succeed  
**Error Budget**: 0.1% (1 in 1000 can fail)

#### SLI Definition

```promql
# Success rate (1 = 100%, 0 = 0%)
sum(rate(sales_transition_total{to_status="paid", result="success"}[5m]))
/
sum(rate(sales_transition_total{to_status="paid"}[5m]))
```

#### Error Budget Calculation

```promql
# Error rate (should be < 0.001 for 99.9% SLO)
1 - (
  sum(rate(sales_transition_total{to_status="paid", result="success"}[5m]))
  /
  sum(rate(sales_transition_total{to_status="paid"}[5m]))
)
```

#### Burn Rate Alerts

**Alert 1.1a: Fast Burn (5x)**

```yaml
- alert: SalePaidSLOFastBurn
  expr: |
    # Error rate in last 5 minutes
    (
      1 - (
        sum(rate(sales_transition_total{to_status="paid", result="success"}[5m]))
        /
        sum(rate(sales_transition_total{to_status="paid"}[5m]))
      )
    ) > (0.001 * 5)  # 5x burn rate = 0.5% errors
  for: 5m
  labels:
    severity: critical
    slo: sale_paid_availability
    window: short
  annotations:
    summary: "Sale→PAID SLO burning 5x faster than budget"
    description: |
      Error rate is {{ $value | humanizePercentage }} in last 5 minutes.
      At this rate, we'll exhaust monthly error budget in 6 days.
    runbook: "https://docs.cosmetica5.com/runbooks#salepaidtransitionfailures"
```

**Alert 1.1b: Slow Burn (2x)**

```yaml
- alert: SalePaidSLOSlowBurn
  expr: |
    # Error rate in last 1 hour
    (
      1 - (
        sum(rate(sales_transition_total{to_status="paid", result="success"}[1h]))
        /
        sum(rate(sales_transition_total{to_status="paid"}[1h]))
      )
    ) > (0.001 * 2)  # 2x burn rate = 0.2% errors
  for: 1h
  labels:
    severity: warning
    slo: sale_paid_availability
    window: long
  annotations:
    summary: "Sale→PAID SLO burning 2x faster than budget"
    description: |
      Error rate is {{ $value | humanizePercentage }} in last hour.
      Sustained degradation detected. Investigate before critical.
    runbook: "https://docs.cosmetica5.com/runbooks#salepaidtransitionfailures"
```

---

### SLO 1.2: Latency (Stock Consumption)

**Target**: 95% of stock consumption operations complete in < 500ms  
**Error Budget**: 5% can be slower

#### SLI Definition

```promql
# Percentage of requests under 500ms
sum(rate(sales_paid_stock_consume_duration_seconds_bucket{le="0.5"}[5m]))
/
sum(rate(sales_paid_stock_consume_duration_seconds_count[5m]))
```

#### Burn Rate Alert

**Alert 1.2a: Latency SLO Burn**

```yaml
- alert: StockConsumeLatencySLOBurn
  expr: |
    # Percentage OVER 500ms (should be < 0.05)
    (
      1 - (
        sum(rate(sales_paid_stock_consume_duration_seconds_bucket{le="0.5"}[5m]))
        /
        sum(rate(sales_paid_stock_consume_duration_seconds_count[5m]))
      )
    ) > (0.05 * 2)  # 2x burn = 10% slow requests
  for: 10m
  labels:
    severity: warning
    slo: stock_consume_latency
    window: short
  annotations:
    summary: "Stock consumption p95 latency SLO burning"
    description: |
      {{ $value | humanizePercentage }} of requests taking > 500ms.
      FEFO queries may be slow. Check database indexes.
    runbook: "https://docs.cosmetica5.com/runbooks#stockconsumelatencyhigh"
```

---

## Flow 2: Refunds

### SLO 2.1: Availability (Refund Operations)

**Target**: 99.5% of refunds succeed  
**Error Budget**: 0.5% (1 in 200 can fail)

**Rationale**: Slightly lower than sales (0.5% vs 0.1%) because refunds are less time-sensitive.

#### SLI Definition

```promql
# Refund success rate
sum(rate(sale_refunds_total{result="success"}[5m]))
/
sum(rate(sale_refunds_total[5m]))
```

#### Burn Rate Alerts

**Alert 2.1a: Fast Burn (5x)**

```yaml
- alert: RefundSLOFastBurn
  expr: |
    (
      1 - (
        sum(rate(sale_refunds_total{result="success"}[5m]))
        /
        sum(rate(sale_refunds_total[5m]))
      )
    ) > (0.005 * 5)  # 5x burn = 2.5% errors
  for: 5m
  labels:
    severity: critical
    slo: refund_availability
    window: short
  annotations:
    summary: "Refund SLO burning 5x faster than budget"
    description: |
      Refund error rate is {{ $value | humanizePercentage }}.
      Customer support impact. Check refund validation logic.
    runbook: "https://docs.cosmetica5.com/runbooks#refundfailures"
```

**Alert 2.1b: Slow Burn (2x)**

```yaml
- alert: RefundSLOSlowBurn
  expr: |
    (
      1 - (
        sum(rate(sale_refunds_total{result="success"}[1h]))
        /
        sum(rate(sale_refunds_total[1h]))
      )
    ) > (0.005 * 2)  # 2x burn = 1% errors
  for: 1h
  labels:
    severity: warning
    slo: refund_availability
    window: long
  annotations:
    summary: "Refund SLO burning 2x faster than budget"
    description: |
      Sustained refund failure rate: {{ $value | humanizePercentage }}.
      Investigate before critical.
    runbook: "https://docs.cosmetica5.com/runbooks#refundfailures"
```

---

### SLO 2.2: Latency (Refund Processing)

**Target**: 95% of refunds complete in < 800ms  
**Error Budget**: 5% can be slower

**Rationale**: Refunds involve stock rollback, so higher latency tolerance than sales.

#### SLI Definition

```promql
# Percentage under 800ms
# NOTE: Requires refund duration histogram (not implemented yet)
# Placeholder for future instrumentation:

# sum(rate(sale_refund_duration_seconds_bucket{le="0.8"}[5m]))
# /
# sum(rate(sale_refund_duration_seconds_count[5m]))
```

**Status**: ⏳ Pending instrumentation (no duration metric exists yet)

---

## Flow 3: Public Leads

### SLO 3.1: Availability (Lead Submission)

**Target**: 99.0% of legitimate leads accepted  
**Error Budget**: 1% (rejections due to validation)

**Rationale**: Public endpoint, more tolerant of spam/invalid data.

#### SLI Definition

```promql
# Acceptance rate (excluding throttled)
sum(rate(public_leads_requests_total{result="accepted"}[5m]))
/
sum(rate(public_leads_requests_total[5m]))
```

#### Burn Rate Alerts

**Alert 3.1a: Fast Burn (5x)**

```yaml
- alert: PublicLeadsSLOFastBurn
  expr: |
    (
      1 - (
        sum(rate(public_leads_requests_total{result="accepted"}[5m]))
        /
        sum(rate(public_leads_requests_total[5m]))
      )
    ) > (0.01 * 5)  # 5x burn = 5% rejected
  for: 5m
  labels:
    severity: critical
    slo: public_leads_availability
    window: short
  annotations:
    summary: "Public leads SLO burning 5x faster"
    description: |
      Lead rejection rate: {{ $value | humanizePercentage }}.
      Either spam attack or validation too strict.
    runbook: "https://docs.cosmetica5.com/runbooks#publicleadscreationfailures"
```

**Alert 3.1b: Slow Burn (2x)**

```yaml
- alert: PublicLeadsSLOSlowBurn
  expr: |
    (
      1 - (
        sum(rate(public_leads_requests_total{result="accepted"}[6h]))
        /
        sum(rate(public_leads_requests_total[6h]))
      )
    ) > (0.01 * 2)  # 2x burn = 2% rejected
  for: 6h
  labels:
    severity: warning
    slo: public_leads_availability
    window: long
  annotations:
    summary: "Public leads SLO burning 2x faster"
    description: |
      Sustained lead rejection: {{ $value | humanizePercentage }} over 6 hours.
      Review validation rules or check for spam patterns.
    runbook: "https://docs.cosmetica5.com/runbooks#publicleadscreationfailures"
```

---

### SLO 3.2: Throttling Correctness

**Target**: Throttling activates when > 10 leads/min from single source  
**Measurement**: Throttle events > 0 during high traffic

#### SLI Definition

```promql
# Throttle is working if events > 0
sum(increase(public_leads_throttled_total[5m])) > 0
```

**Alert**: Already covered by `ThrottleDisabledOrNotWorking` in `ALERTING.md`

---

## Multi-Window Burn Rate Table

| SLO | Target | Error Budget | 2x Burn (Warning) | 5x Burn (Critical) |
|-----|--------|--------------|-------------------|---------------------|
| Sale→PAID Availability | 99.9% | 0.1% | 0.2% errors | 0.5% errors |
| Stock Consume Latency | 95% < 500ms | 5% slow | 10% slow | N/A (use 2x only) |
| Refund Availability | 99.5% | 0.5% | 1% errors | 2.5% errors |
| Refund Latency | 95% < 800ms | 5% slow | 10% slow | N/A (pending metric) |
| Public Leads Availability | 99.0% | 1% | 2% rejected | 5% rejected |

---

## Error Budget Monitoring

### Monthly Error Budget Dashboard

**Grafana Panel**: Error Budget Remaining

```promql
# Sale→PAID error budget (monthly)
# Assumes 30 days = 2,592,000 seconds
(
  0.001 -  # Target error rate (0.1%)
  (
    1 - (
      sum(rate(sales_transition_total{to_status="paid", result="success"}[30d]))
      /
      sum(rate(sales_transition_total{to_status="paid"}[30d]))
    )
  )
) / 0.001 * 100  # Percentage of budget remaining
```

**Interpretation**:
- 100% = No errors, full budget remaining
- 50% = Half budget used
- 0% = Budget exhausted (exceeded SLO)
- Negative = Over budget (SLO violated)

---

## Burn Rate Alert Windows

### Why Multi-Window?

**Short Window (5m-1h)**:
- Detects fast burns (incidents, outages)
- High sensitivity to spikes
- Risk: False positives from brief issues

**Long Window (6h-24h)**:
- Detects slow burns (gradual degradation)
- Smooths out noise
- Risk: Slow to detect sudden outages

**Combined**: Best of both worlds

### Recommended Windows by Severity

| Severity | Short Window | Long Window | Use Case |
|----------|--------------|-------------|----------|
| Critical (5x) | 5m | 1h | Immediate action required |
| Warning (2x) | 1h | 6h | Investigate before critical |
| Info | 6h | 24h | Trend monitoring only |

---

## SLO Review Process

### Weekly Review

**Metrics to Check**:
1. Error budget remaining (per flow)
2. Number of SLO burns (warning + critical)
3. Mean time to recovery (MTTR) for burns

### Monthly Review

**Questions**:
1. Did we meet all SLOs?
2. Were any SLOs too loose (never burned)?
3. Were any SLOs too strict (always burning)?
4. Do we need to adjust targets?

### SLO Adjustment Criteria

**Loosen SLO** (e.g., 99.9% → 99.5%) if:
- Never burned in 3 months
- Target unrealistic for business needs
- Too expensive to maintain

**Tighten SLO** (e.g., 99.0% → 99.5%) if:
- Always meeting target with margin
- Business requires higher reliability
- Competitive pressure

---

## Complete Burn Rate Alert Rules

### File: `prometheus/alerts/slo.yml`

```yaml
groups:
  - name: slo_burn_rate
    interval: 30s
    rules:
      # ===============================================================
      # FLOW 1: SALES & STOCK
      # ===============================================================
      
      # Sale→PAID Availability: Fast Burn (5x)
      - alert: SalePaidSLOFastBurn
        expr: |
          (
            1 - (
              sum(rate(sales_transition_total{to_status="paid", result="success"}[5m]))
              /
              sum(rate(sales_transition_total{to_status="paid"}[5m]))
            )
          ) > 0.005
        for: 5m
        labels:
          severity: critical
          slo: sale_paid_availability
          window: short
        annotations:
          summary: "Sale→PAID SLO burning 5x faster than budget"
          description: "Error rate {{ $value | humanizePercentage }} (budget: 0.1%)"
          runbook: "https://docs.cosmetica5.com/runbooks#salepaidtransitionfailures"
      
      # Sale→PAID Availability: Slow Burn (2x)
      - alert: SalePaidSLOSlowBurn
        expr: |
          (
            1 - (
              sum(rate(sales_transition_total{to_status="paid", result="success"}[1h]))
              /
              sum(rate(sales_transition_total{to_status="paid"}[1h]))
            )
          ) > 0.002
        for: 1h
        labels:
          severity: warning
          slo: sale_paid_availability
          window: long
        annotations:
          summary: "Sale→PAID SLO burning 2x faster than budget"
          description: "Sustained error rate {{ $value | humanizePercentage }}"
          runbook: "https://docs.cosmetica5.com/runbooks#salepaidtransitionfailures"
      
      # Stock Consume Latency: Slow Burn (2x)
      - alert: StockConsumeLatencySLOBurn
        expr: |
          (
            1 - (
              sum(rate(sales_paid_stock_consume_duration_seconds_bucket{le="0.5"}[5m]))
              /
              sum(rate(sales_paid_stock_consume_duration_seconds_count[5m]))
            )
          ) > 0.10
        for: 10m
        labels:
          severity: warning
          slo: stock_consume_latency
          window: short
        annotations:
          summary: "Stock consumption latency SLO burning"
          description: "{{ $value | humanizePercentage }} of requests > 500ms"
          runbook: "https://docs.cosmetica5.com/runbooks#stockconsumelatencyhigh"
      
      # ===============================================================
      # FLOW 2: REFUNDS
      # ===============================================================
      
      # Refund Availability: Fast Burn (5x)
      - alert: RefundSLOFastBurn
        expr: |
          (
            1 - (
              sum(rate(sale_refunds_total{result="success"}[5m]))
              /
              sum(rate(sale_refunds_total[5m]))
            )
          ) > 0.025
        for: 5m
        labels:
          severity: critical
          slo: refund_availability
          window: short
        annotations:
          summary: "Refund SLO burning 5x faster than budget"
          description: "Refund error rate {{ $value | humanizePercentage }} (budget: 0.5%)"
          runbook: "https://docs.cosmetica5.com/runbooks#refundfailures"
      
      # Refund Availability: Slow Burn (2x)
      - alert: RefundSLOSlowBurn
        expr: |
          (
            1 - (
              sum(rate(sale_refunds_total{result="success"}[1h]))
              /
              sum(rate(sale_refunds_total[1h]))
            )
          ) > 0.01
        for: 1h
        labels:
          severity: warning
          slo: refund_availability
          window: long
        annotations:
          summary: "Refund SLO burning 2x faster than budget"
          description: "Sustained refund error rate {{ $value | humanizePercentage }}"
          runbook: "https://docs.cosmetica5.com/runbooks#refundfailures"
      
      # ===============================================================
      # FLOW 3: PUBLIC LEADS
      # ===============================================================
      
      # Public Leads Availability: Fast Burn (5x)
      - alert: PublicLeadsSLOFastBurn
        expr: |
          (
            1 - (
              sum(rate(public_leads_requests_total{result="accepted"}[5m]))
              /
              sum(rate(public_leads_requests_total[5m]))
            )
          ) > 0.05
        for: 5m
        labels:
          severity: critical
          slo: public_leads_availability
          window: short
        annotations:
          summary: "Public leads SLO burning 5x faster"
          description: "Lead rejection rate {{ $value | humanizePercentage }} (budget: 1%)"
          runbook: "https://docs.cosmetica5.com/runbooks#publicleadscreationfailures"
      
      # Public Leads Availability: Slow Burn (2x)
      - alert: PublicLeadsSLOSlowBurn
        expr: |
          (
            1 - (
              sum(rate(public_leads_requests_total{result="accepted"}[6h]))
              /
              sum(rate(public_leads_requests_total[6h]))
            )
          ) > 0.02
        for: 6h
        labels:
          severity: warning
          slo: public_leads_availability
          window: long
        annotations:
          summary: "Public leads SLO burning 2x faster"
          description: "Sustained rejection rate {{ $value | humanizePercentage }}"
          runbook: "https://docs.cosmetica5.com/runbooks#publicleadscreationfailures"
```

---

## References

- **Alert Rules (Symptom-Based)**: `docs/ALERTING.md`
- **Runbooks**: `docs/RUNBOOKS.md`
- **Dashboards**: `docs/OBSERVABILITY_DASHBOARDS.md`
- **Google SRE Book**: [https://sre.google/workbook/alerting-on-slos/](https://sre.google/workbook/alerting-on-slos/)

---

## Next Steps

1. ✅ Deploy SLO burn-rate alerts to Prometheus
2. ✅ Create error budget dashboard in Grafana
3. ✅ Schedule monthly SLO review meeting
4. ✅ Document SLO targets in team wiki
5. ⏳ Instrument refund duration histogram (for latency SLO)
