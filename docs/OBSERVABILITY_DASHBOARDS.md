# Grafana Dashboards - Observability

> **Status**: Production-Ready  
> **Date**: 2025-12-16  
> **Dashboards**: 4 (1 global + 3 flow-specific)

---

## Overview

This document provides Grafana-ready dashboard configurations with exact PromQL queries for monitoring Cosmetica 5.

**Anti-Cardinality Rules** (CRITICAL):
- ❌ **NEVER use as label**: `sale_id`, `refund_id`, `user_id`, `request_id`, `email`, `phone`
- ✅ **Safe labels**: `status`, `result`, `flow`, `endpoint`, `method`, `from_status`, `to_status`
- ⚠️ High cardinality = memory explosion + slow queries + Prometheus crash

---

## Dashboard 1: System Overview

**Purpose**: High-level system health and traffic patterns  
**Refresh**: 30s  
**Time Range**: Last 1 hour (default)

### Panels

#### 1.1 Request Throughput

**Type**: Graph  
**Description**: Requests per second across all endpoints

```promql
# Total request rate
sum(rate(http_requests_total[5m]))

# By status code family
sum by (status) (rate(http_requests_total[5m]))
```

**Thresholds**:
- Normal: < 50 req/s
- Busy: 50-100 req/s
- High: > 100 req/s

---

#### 1.2 Error Rate (4xx vs 5xx)

**Type**: Graph  
**Description**: Error percentage separated by client vs server errors

```promql
# 4xx rate (client errors)
sum(rate(http_requests_total{status=~"4.."}[5m])) / sum(rate(http_requests_total[5m])) * 100

# 5xx rate (server errors) - CRITICAL
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100
```

**Alert Thresholds**:
- 4xx: Warning if > 10%
- 5xx: Critical if > 1%

---

#### 1.3 Latency Distribution (p50/p95/p99)

**Type**: Graph  
**Description**: HTTP request latency percentiles

```promql
# p50 (median)
histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))

# p95
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))

# p99
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
```

**SLO Targets**:
- p50: < 100ms
- p95: < 500ms
- p99: < 1000ms

---

#### 1.4 Top Errors (Status Code + Exception)

**Type**: Table  
**Description**: Most frequent errors in last 5 minutes

```promql
# Top HTTP errors by path and status
topk(10, sum by (path, status) (increase(http_requests_total{status=~"[45].."}[5m])))

# Top exceptions by type
topk(10, sum by (exception_type, location) (increase(exceptions_total[5m])))
```

**Columns**: Exception Type, Location, Count (5m)

---

#### 1.5 Domain Events Activity

**Type**: Graph  
**Description**: Business events emitted (observability only, not logged)

```promql
# Sale transitions
sum(rate(sales_transition_total[5m]))

# Refunds created
sum(rate(sale_refunds_total[5m]))

# Leads submitted
sum(rate(public_leads_requests_total[5m]))
```

**Note**: This tracks instrumentation health, not business KPIs

---

#### 1.6 Request Correlation Guide

**Type**: Text Panel  
**Content**:

```
🔍 How to Trace a Request:

1. Get X-Request-ID from API response header
2. Query logs:
   grep "550e8400-e29b-41d4-a716-446655440000" /var/log/app.log
   
3. If using structured logging:
   jq 'select(.request_id == "550e8400-e29b-41d4-a716-446655440000")' < app.json

4. If using OpenTelemetry:
   Search Jaeger/Tempo by trace_id = request_id

⚠️ NEVER log PHI/PII:
   - Logs contain UUIDs, status codes, counts only
   - NO email, phone, names, addresses
```

---

## Dashboard 2: Flow 1 - Sales & Stock

**Purpose**: Monitor Sale → PAID transitions and stock consumption  
**Refresh**: 15s  
**Critical**: Yes (revenue impact)

### Panels

#### 2.1 Sale Transitions (Rate)

**Type**: Graph  
**Description**: Sale status transitions per minute

```promql
# All transitions
sum(rate(sales_transition_total[1m])) * 60

# Transitions to PAID (revenue!)
sum(rate(sales_transition_total{to_status="paid"}[1m])) * 60

# By result (success vs failures)
sum by (result) (rate(sales_transition_total{to_status="paid"}[1m])) * 60
```

---

#### 2.2 Stock Consumption Success Rate

**Type**: Singlestat (percentage)  
**Description**: Success rate of stock consumption operations

```promql
sum(rate(sales_paid_stock_consume_total{result="success"}[5m])) 
/ 
sum(rate(sales_paid_stock_consume_total[5m])) * 100
```

**Thresholds**:
- Green: > 99%
- Yellow: 95-99%
- Red: < 95%

---

#### 2.3 Stock Consumption Latency

**Type**: Graph  
**Description**: Time to consume stock (FEFO allocation)

```promql
# p95 latency
histogram_quantile(0.95, sum(rate(sales_paid_stock_consume_duration_seconds_bucket[5m])) by (le))

# p99 latency
histogram_quantile(0.99, sum(rate(sales_paid_stock_consume_duration_seconds_bucket[5m])) by (le))
```

**SLO**: p95 < 500ms

---

#### 2.4 Sale Transition Failures (Breakdown)

**Type**: Graph (stacked)  
**Description**: Reasons for transition failures

```promql
# Insufficient stock
sum(rate(sales_transition_total{result="insufficient_stock"}[5m]))

# Expired batch
sum(rate(sales_transition_total{result="expired_batch"}[5m]))

# Validation errors
sum(rate(sales_transition_total{result="validation_error"}[5m]))

# Generic errors
sum(rate(sales_transition_total{result="error"}[5m]))
```

---

#### 2.5 Idempotency Events

**Type**: Counter  
**Description**: Duplicate stock consumption attempts (should be rare)

```promql
increase(sales_paid_stock_consume_total{result="idempotent"}[1h])
```

**Expected**: < 1% of total operations  
**Alert If**: Spike (possible retry storm)

---

#### 2.6 Exception Hotspots

**Type**: Table  
**Description**: Exceptions in stock consumption flow

```promql
topk(5, sum by (exception_type) (increase(exceptions_total{location="consume_stock_for_sale"}[15m])))
```

---

## Dashboard 3: Flow 2 - Refunds

**Purpose**: Monitor full and partial refund operations  
**Refresh**: 30s  
**Critical**: Yes (fraud detection)

### Panels

#### 3.1 Refund Creation Rate

**Type**: Graph  
**Description**: Refunds created per hour

```promql
# Total refunds
sum(rate(sale_refunds_total[5m])) * 3600

# By type (full vs partial)
sum by (type) (rate(sale_refunds_total[5m])) * 3600
```

---

#### 3.2 Refund Success Rate

**Type**: Singlestat (percentage)  
**Description**: Percentage of successful refunds

```promql
sum(rate(sale_refunds_total{result="success"}[5m])) 
/ 
sum(rate(sale_refunds_total[5m])) * 100
```

**Thresholds**:
- Green: > 98%
- Yellow: 90-98%
- Red: < 90%

---

#### 3.3 Over-Refund Blocked Attempts

**Type**: Counter  
**Description**: Blocked refund attempts exceeding original sale amount

```promql
increase(sale_refund_over_refund_attempts_total[1h])
```

**Alert If**: > 5 in 1 hour (possible fraud or bug)

---

#### 3.4 Idempotency Conflicts

**Type**: Counter  
**Description**: Duplicate refund attempts with same idempotency key

```promql
increase(sale_refund_idempotency_conflicts_total[1h])
```

**Expected**: 0 (well-behaved clients)  
**Alert If**: > 10 in 1 hour (integration issue)

---

#### 3.5 Stock Refund IN Operations

**Type**: Graph  
**Description**: Stock movements created for refunds

```promql
# Successful refund stock moves
sum(rate(stock_refund_in_total{result="success"}[5m]))

# Mismatches
sum by (type) (rate(stock_refund_in_mismatch_total[5m]))
```

**Alert If**: Mismatch rate > 1%

---

#### 3.6 Refund Rollbacks

**Type**: Counter  
**Description**: Transactions rolled back (should be rare)

```promql
topk(5, sum by (reason) (increase(sale_refund_rollback_total[1h])))
```

**Expected**: Near zero  
**Investigate If**: > 5 in 1 hour

---

## Dashboard 4: Flow 3 - Public Leads

**Purpose**: Monitor public-facing lead submission endpoint  
**Refresh**: 10s  
**Critical**: Yes (customer acquisition)

### Panels

#### 4.1 Lead Submission Rate

**Type**: Graph  
**Description**: Leads submitted per minute

```promql
# Accepted leads
sum(rate(public_leads_requests_total{result="accepted"}[1m])) * 60

# Rejected leads (validation failures)
sum(rate(public_leads_requests_total{result="rejected"}[1m])) * 60
```

---

#### 4.2 Acceptance Rate

**Type**: Singlestat (percentage)  
**Description**: Percentage of leads accepted

```promql
sum(rate(public_leads_requests_total{result="accepted"}[5m])) 
/ 
sum(rate(public_leads_requests_total[5m])) * 100
```

**Thresholds**:
- Green: > 80% (good data quality)
- Yellow: 50-80%
- Red: < 50% (spam or validation too strict)

---

#### 4.3 Throttling Activity

**Type**: Graph (stacked)  
**Description**: Rate limiting in action

```promql
# Burst throttling
sum(rate(public_leads_throttled_total{scope="burst"}[1m])) * 60

# Hourly throttling
sum(rate(public_leads_throttled_total{scope="hourly"}[1m])) * 60

# Total 429 responses
sum(rate(public_leads_429_total[1m])) * 60
```

---

#### 4.4 Throttle Health Check

**Type**: Singlestat (boolean)  
**Description**: Verify throttling is working

```promql
# Should be > 0 if system is under load
increase(public_leads_throttled_total[5m]) > 0
```

**Value Mappings**:
- 1 = "Throttling Active ✅"
- 0 = "No Throttling Events ⚠️"

**Alert If**: 0 for > 1 hour AND high traffic (throttle disabled/broken)

---

#### 4.5 HTTP 429 Rate

**Type**: Graph  
**Description**: Rate limit responses

```promql
sum(rate(public_leads_429_total[5m]))
```

**Expected**: > 0 during high traffic  
**Alert If**: Excessive (> 50% of requests = DDoS or legitimate spike)

---

#### 4.6 Lead Validation Failures

**Type**: Table  
**Description**: Reasons for lead rejection (inferred from logs, not metrics)

**Note**: This panel requires structured logging with rejection reasons.  
If not available, use:

```promql
# Generic rejection rate
increase(public_leads_requests_total{result="rejected"}[1h])
```

---

## Anti-Cardinality Checklist

Before deploying any panel, verify:

- [ ] No `sale_id`, `refund_id`, `lead_id` in labels
- [ ] No `user_id`, `customer_id`, `patient_id` in labels
- [ ] No `email`, `phone`, `name` in labels
- [ ] No `request_id` in labels (use for correlation in logs, not metrics)
- [ ] No unbounded text fields (e.g., `reason`, `message`)
- [ ] All labels are from a fixed set (status codes, result types, flows)

**Rule of Thumb**: If cardinality can exceed 1000 unique values, don't use it as a label.

---

## Deployment Instructions

### Grafana JSON Export

To export these queries as Grafana dashboards:

1. Create a new dashboard in Grafana
2. Add panels with the PromQL queries above
3. Configure thresholds and alerts as specified
4. Export as JSON: Settings → JSON Model
5. Store in version control: `grafana/dashboards/`

### Prometheus Data Source

```yaml
# grafana/provisioning/datasources/prometheus.yml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

---

## Variable Templates (Recommended)

Add these variables to dashboards for filtering:

```
$environment = label_values(http_requests_total, environment)
$status_code = label_values(http_requests_total, status)
$result = label_values(sales_transition_total, result)
```

**Usage in queries**:
```promql
http_requests_total{environment="$environment", status="$status_code"}
```

---

## Dashboard Annotations

Use Prometheus Alertmanager alerts as annotations:

```json
{
  "enable": true,
  "datasource": "Prometheus",
  "expr": "ALERTS{alertstate=\"firing\"}",
  "titleFormat": "{{ alertname }}",
  "textFormat": "{{ annotations.summary }}"
}
```

Shows alert firing events directly on graphs.

---

## Next Steps

1. ✅ Import dashboards to Grafana
2. ✅ Configure Prometheus scraping (see `OBSERVABILITY.md`)
3. ✅ Set up alert routing (see `ALERTING.md`)
4. ✅ Test with load (see `RUNBOOKS.md`)
5. ✅ Verify PHI/PII not exposed in any panel

---

## References

- **Metrics Catalog**: `docs/OBSERVABILITY_FLOWS.md`
- **Alert Rules**: `docs/ALERTING.md`
- **Runbooks**: `docs/RUNBOOKS.md`
- **SLOs**: `docs/SLO.md`
