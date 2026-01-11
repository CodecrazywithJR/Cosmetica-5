# Operational Runbooks

> **Status**: Production-Ready  
> **Date**: 2025-12-16  
> **Runbooks**: 5 (for CRITICAL alerts)

---

## Overview

This document provides step-by-step runbooks for responding to critical production alerts in Cosmetica 5.

**When to Use**: Alert fired with `severity: critical`  
**Response Time**: 15 minutes to acknowledgement, 1 hour to resolution  
**Escalation**: After 30 minutes if stuck

---

## Runbook Template

Each runbook follows this structure:

1. **Alert Context**: What the alert means
2. **First Look**: Dashboard + panels to check
3. **Diagnostic Queries**: PromQL to investigate
4. **Common Hypotheses**: Top 3 root causes
5. **Safe Actions**: What to do without data risk
6. **When to Escalate**: Clear criteria

---

## Runbook 1: APIHigh5xxRate

### Alert Context

**Alert**: `APIHigh5xxRate`  
**Severity**: `critical`  
**Meaning**: > 1% of API requests returning 5xx errors  
**Impact**: User-facing failures, revenue loss, customer support burden

### First Look

**Dashboard**: [System Overview](https://grafana.cosmetica5.com/d/system-overview)

**Panels to Check**:
1. **Error Rate (4xx vs 5xx)**: Confirm 5xx spike, not 4xx
2. **Top Errors**: Identify which endpoint and status code
3. **Exception Hotspots**: Find exception type and location

### Diagnostic Queries

#### 1. Find Top Failing Endpoints

```promql
topk(10, sum by (path, status) (
  rate(http_requests_total{status=~"5.."}[5m])
))
```

**Expected Output**:
```
/api/sales/123/transition/ {status="500"} 0.5
/api/website/leads/ {status="503"} 0.2
```

#### 2. Find Top Exceptions

```promql
topk(10, sum by (exception_type, location) (
  rate(exceptions_total[5m])
))
```

**Expected Output**:
```
InsufficientStockError {location="consume_stock_for_sale"} 0.3
DatabaseError {location="django_db"} 0.1
```

#### 3. Correlate with Logs

```bash
# Get request IDs from last 5 minutes with 5xx
grep "status_code=5" /var/log/app.log | tail -50 | jq -r '.request_id'

# Example: 550e8400-e29b-41d4-a716-446655440000

# Trace full request
grep "550e8400-e29b-41d4-a716-446655440000" /var/log/app.log | jq .
```

**What to Look For**:
- Repeated exception type
- Database connection errors
- External API timeouts
- Stack traces (if logged)

### Common Hypotheses

#### Hypothesis 1: Database Connection Pool Exhausted

**Symptoms**:
- Exception: `DatabaseError: too many connections`
- Multiple endpoints affected equally
- Latency p95 also spiking

**Diagnostic**:
```sql
-- Check active connections (PostgreSQL)
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';

-- Check long-running queries
SELECT pid, now() - pg_stat_activity.query_start AS duration, query 
FROM pg_stat_activity 
WHERE state = 'active' 
ORDER BY duration DESC;
```

**Safe Action**:
```bash
# Restart Gunicorn workers (releases DB connections)
sudo systemctl restart gunicorn

# Or rolling restart (zero downtime)
kill -HUP $(cat /var/run/gunicorn.pid)
```

#### Hypothesis 2: Specific Flow Failing (e.g., Stock Consumption)

**Symptoms**:
- Exception: `InsufficientStockError` or `ExpiredBatchError`
- Only `/api/sales/{id}/transition/` failing
- Error rate correlates with sales activity

**Diagnostic**:
```promql
# Check stock consumption failures
sum by (result) (
  rate(sales_paid_stock_consume_total{result!="success"}[5m])
)
```

**Safe Action**:
```sql
-- Check for negative stock (data inconsistency)
SELECT product_id, location_id, SUM(quantity_on_hand) 
FROM stock_onhand 
GROUP BY product_id, location_id 
HAVING SUM(quantity_on_hand) < 0;

-- Check for expired batches not cleaned up
SELECT COUNT(*) 
FROM stock_batch 
WHERE expiry_date < NOW() AND is_active = true;
```

**Mitigation**:
- If many expired batches: Run batch cleanup job
- If negative stock: Investigate data corruption, may need manual correction

#### Hypothesis 3: External Dependency Down

**Symptoms**:
- Exception: `ConnectionError`, `TimeoutError`
- All requests to specific flow failing
- No database issues

**Diagnostic**:
```bash
# Check external services
curl -I https://external-api.example.com/health

# Check network
ping external-api.example.com
traceroute external-api.example.com
```

**Safe Action**:
- If payment gateway: Notify customers, pause sales
- If email service: Queue emails, process later
- If optional service: Disable feature flag

### When to Escalate

**Escalate After 30 Minutes If**:
- Cannot identify root cause from logs/metrics
- Database is healthy but errors persist
- Requires schema change or code deployment
- Data corruption suspected

**Escalate To**:
- Backend lead engineer
- Database administrator (if DB-related)
- Infrastructure team (if network/server)

---

## Runbook 2: SalePaidTransitionFailures

### Alert Context

**Alert**: `SalePaidTransitionFailures`  
**Severity**: `critical`  
**Meaning**: > 5% of PAID transitions failing  
**Impact**: Revenue loss, customers cannot complete purchases

### First Look

**Dashboard**: [Sales & Stock](https://grafana.cosmetica5.com/d/sales-stock)

**Panels to Check**:
1. **Sale Transition Failures (Breakdown)**: See if `insufficient_stock`, `expired_batch`, or `validation_error`
2. **Stock Consumption Success Rate**: Confirm stock service health
3. **Exception Hotspots**: Find exact error

### Diagnostic Queries

#### 1. Breakdown of Failure Reasons

```promql
sum by (result) (
  rate(sales_transition_total{to_status="paid", result!="success"}[5m])
)
```

**Expected Output**:
```
{result="insufficient_stock"} 0.3
{result="expired_batch"} 0.1
{result="validation_error"} 0.05
```

#### 2. Recent Failed Sales (from Logs)

```bash
# Find sales that failed to transition
grep "sale.transition" /var/log/app.log \
  | jq 'select(.result == "insufficient_stock")' \
  | tail -20
```

**Example Output**:
```json
{
  "event": "sale.transition",
  "sale_id": "abc-123",
  "from_status": "draft",
  "to_status": "paid",
  "result": "insufficient_stock",
  "product_id": "prod-456"
}
```

### Common Hypotheses

#### Hypothesis 1: Actual Stock Shortage

**Symptoms**:
- `result="insufficient_stock"` dominates failures
- Specific products affected
- Error rate correlates with sales volume

**Diagnostic**:
```sql
-- Find products with low/zero stock
SELECT p.name, l.code, SUM(soh.quantity_on_hand) as total_stock
FROM stock_onhand soh
JOIN stock_product p ON p.id = soh.product_id
JOIN stock_location l ON l.id = soh.location_id
WHERE soh.quantity_on_hand > 0
GROUP BY p.name, l.code
HAVING SUM(soh.quantity_on_hand) < 10
ORDER BY total_stock ASC;
```

**Safe Action**:
- **Notify sales team**: "Product X low stock"
- **Check pending stock receipts**: May arrive soon
- **Disable online sales** for out-of-stock products (if UI supports)

**NOT Safe**:
- ❌ Manually adjusting `quantity_on_hand` (creates inconsistency)
- ❌ Allowing negative stock (violates business rule)

#### Hypothesis 2: Expired Batches Not Cleaned

**Symptoms**:
- `result="expired_batch"` significant
- Products have stock on hand but still fail
- Older products affected

**Diagnostic**:
```sql
-- Count expired batches still active
SELECT COUNT(*), p.name
FROM stock_batch sb
JOIN stock_product p ON p.id = sb.product_id
WHERE sb.expiry_date < NOW() 
  AND sb.is_active = true
GROUP BY p.name;
```

**Safe Action**:
```python
# Django shell
from apps.stock.models import StockBatch
from django.utils import timezone

# Mark expired batches as inactive
expired = StockBatch.objects.filter(
    expiry_date__lt=timezone.now(),
    is_active=True
)
print(f"Marking {expired.count()} batches as expired")
expired.update(is_active=False)
```

#### Hypothesis 3: Database Transaction Deadlock

**Symptoms**:
- Generic `error` result (not specific)
- Happens intermittently
- High concurrency (multiple sales at once)

**Diagnostic**:
```sql
-- PostgreSQL: Check for deadlocks
SELECT * FROM pg_stat_database WHERE datname = 'cosmetica5';
-- Look at deadlocks column

-- Check for lock waits
SELECT * FROM pg_locks WHERE NOT granted;
```

**Safe Action**:
- **Short-term**: Add retry logic with exponential backoff
- **Medium-term**: Review transaction isolation levels
- **Long-term**: Optimize queries to reduce lock contention

### When to Escalate

**Escalate Immediately If**:
- > 50% of transitions failing (major outage)
- Database corruption suspected
- Requires code deployment to fix

**Escalate After 30 Minutes If**:
- Stock data looks correct but errors persist
- Cannot identify pattern in failures

---

## Runbook 3: StockConsumeFailures

### Alert Context

**Alert**: `StockConsumeFailures`  
**Severity**: `critical`  
**Meaning**: Stock consumption failing (non-idempotent errors)  
**Impact**: Sales cannot complete, inventory inconsistency risk

### First Look

**Dashboard**: [Sales & Stock](https://grafana.cosmetica5.com/d/sales-stock)

**Panels to Check**:
1. **Stock Consumption Success Rate**: Current percentage
2. **Sale Transition Failures**: Confirm correlation
3. **Exception Hotspots**: `consume_stock_for_sale` exceptions

### Diagnostic Queries

```promql
# Breakdown of stock consumption failures
sum by (result) (
  rate(sales_paid_stock_consume_total{result!="success", result!="idempotent"}[5m])
)
```

### Common Hypotheses

#### Hypothesis 1: FEFO Algorithm Timeout

**Symptoms**:
- Generic `error` result
- Affects large sales (many line items)
- Latency also high

**Diagnostic**:
```promql
# Check p99 latency
histogram_quantile(0.99, 
  sum(rate(sales_paid_stock_consume_duration_seconds_bucket[5m])) by (le)
)
```

**Safe Action**:
- Review FEFO query: Add index on `(product_id, expiry_date, quantity_on_hand)`
- Increase timeout temporarily
- Paginate stock allocation if > 100 line items

#### Hypothesis 2: Database Constraint Violation

**Symptoms**:
- Exception: `IntegrityError` or `OperationalError`
- Specific to certain products/locations

**Diagnostic**:
```bash
# Check PostgreSQL logs
sudo tail -100 /var/log/postgresql/postgresql-*.log | grep ERROR
```

**Safe Action**:
- Identify constraint violated (e.g., unique, foreign key)
- Check for duplicate `StockMove` records
- Verify referential integrity: `sale_id`, `batch_id`, `location_id`

#### Hypothesis 3: Race Condition (Concurrent Sales)

**Symptoms**:
- Errors spike during high traffic
- Same product sold simultaneously
- Stock goes negative briefly

**Diagnostic**:
```sql
-- Check for negative stock
SELECT * FROM stock_onhand WHERE quantity_on_hand < 0;
```

**Safe Action**:
- Verify `@transaction.atomic` wraps stock consumption
- Add `select_for_update()` on `StockOnHand` query
- Review isolation level (should be `READ COMMITTED` minimum)

### When to Escalate

**Escalate Immediately If**:
- Stock data corrupted (negative quantities)
- Database locks preventing all sales

---

## Runbook 4: RefundFailures

### Alert Context

**Alert**: `RefundFailures`  
**Severity**: `critical`  
**Meaning**: > 10% of refunds failing  
**Impact**: Customer support burden, financial reconciliation issues

### First Look

**Dashboard**: [Refunds](https://grafana.cosmetica5.com/d/refunds)

**Panels to Check**:
1. **Refund Success Rate**: Current percentage
2. **Refund Rollbacks**: Transaction failures
3. **Over-Refund Blocked**: Validation working?

### Diagnostic Queries

```promql
# Refund failure rate
sum(rate(sale_refunds_total{result="failure"}[5m])) 
/ 
sum(rate(sale_refunds_total[5m])) * 100
```

### Common Hypotheses

#### Hypothesis 1: Over-Refund Validation Too Strict

**Symptoms**:
- Legitimate partial refunds blocked
- Customer support receiving complaints
- Business logic change needed

**Diagnostic**:
```sql
-- Check refund amounts vs original sale
SELECT s.sale_number, s.total, 
       SUM(sr.refund_amount) as total_refunded
FROM sales_sale s
JOIN sales_salerefund sr ON sr.original_sale_id = s.id
GROUP BY s.id, s.sale_number, s.total
HAVING SUM(sr.refund_amount) > s.total * 0.9;  -- Near limit
```

**Safe Action**:
- Manually approve edge cases
- Document pattern for future logic update

#### Hypothesis 2: Stock Refund IN Mismatch

**Symptoms**:
- Stock not returning to inventory
- `stock_refund_in_mismatch_total` increasing

**Diagnostic**:
```promql
sum by (type) (
  rate(stock_refund_in_mismatch_total[5m])
)
```

**Safe Action**:
- Check if original `StockMove` exists
- Verify batch still active
- Manual stock adjustment if needed (with audit trail)

#### Hypothesis 3: Idempotency Key Collision

**Symptoms**:
- `sale_refund_idempotency_conflicts_total` spiking
- Same refund attempted multiple times

**Diagnostic**:
```bash
# Find duplicate idempotency keys
grep "idempotency_conflict" /var/log/app.log | jq -r '.idempotency_key' | sort | uniq -c | sort -rn
```

**Safe Action**:
- Return existing refund with 200 OK (idempotent behavior correct)
- Investigate client retry logic

### When to Escalate

**Escalate After 30 Minutes If**:
- Refund logic needs code change
- Financial reconciliation discrepancies found

---

## Runbook 5: ThrottleDisabledOrNotWorking

### Alert Context

**Alert**: `ThrottleDisabledOrNotWorking`  
**Severity**: `critical`  
**Meaning**: High traffic but no throttling events  
**Impact**: Risk of DDoS, resource exhaustion, abuse

### First Look

**Dashboard**: [Public Leads](https://grafana.cosmetica5.com/d/public-leads)

**Panels to Check**:
1. **Throttling Activity**: Should show throttled requests
2. **Lead Submission Rate**: Confirm traffic is high
3. **HTTP 429 Rate**: Should be > 0

### Diagnostic Queries

```promql
# Traffic rate
sum(rate(public_leads_requests_total[5m]))

# Throttle events (should be > 0)
sum(increase(public_leads_throttled_total[1h]))
```

### Common Hypotheses

#### Hypothesis 1: Throttle Middleware Disabled

**Symptoms**:
- No 429 responses at all
- Traffic uncapped
- System under load

**Diagnostic**:
```python
# Django shell
from django.conf import settings

# Check throttle classes configured
print(settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_CLASSES'))

# Check throttle rates
from rest_framework.throttling import AnonRateThrottle
print(AnonRateThrottle().get_rate())
```

**Safe Action**:
```python
# Verify in views.py
from apps.website.views import create_lead
print(create_lead.cls.throttle_classes)

# Should show: [LeadBurstThrottle, LeadHourlyThrottle]
```

#### Hypothesis 2: Cache Backend Not Working

**Symptoms**:
- Throttle classes configured
- But not enforcing limits (cache unavailable)

**Diagnostic**:
```python
# Django shell
from django.core.cache import cache

# Test cache
cache.set('test_key', 'test_value', 60)
assert cache.get('test_key') == 'test_value'
```

**Safe Action**:
- Restart Redis/Memcached
- Check `CACHES` configuration in settings
- Fallback to database cache if needed

#### Hypothesis 3: Bypass Route

**Symptoms**:
- Throttle working for some requests
- Not others (e.g., authenticated users)

**Diagnostic**:
```bash
# Check nginx logs for direct access
tail -100 /var/log/nginx/access.log | grep "/public/leads/"
```

**Safe Action**:
- Add IP-based rate limiting at nginx level
- Verify throttle applies to all users

### When to Escalate

**Escalate Immediately If**:
- System under active attack (traffic > 1000 req/s)
- Cannot re-enable throttling

---

## General Troubleshooting Tips

### Finding Request Correlation

```bash
# From alert, get time range
START="2025-12-16T10:00:00Z"
END="2025-12-16T10:05:00Z"

# Find errors in that window
jq -r 'select(.timestamp >= "'$START'" and .timestamp <= "'$END'" and .level == "ERROR")' < /var/log/app.json

# Get unique request IDs
jq -r 'select(.level == "ERROR") | .request_id' < /var/log/app.json | sort -u

# Trace one request end-to-end
grep "550e8400-e29b-41d4-a716-446655440000" /var/log/app.json | jq -s 'sort_by(.timestamp)'
```

### PHI/PII Protection Reminder

**When investigating logs**:
- ✅ DO: Search by `sale_id`, `request_id`, `status_code`
- ❌ DON'T: Log `email`, `phone`, `patient_name`
- ✅ DO: Share UUIDs with team
- ❌ DON'T: Share customer data in Slack

**All logs are sanitized**, but double-check before sharing:
```bash
# Safe to share
grep "sale_id=abc-123" /var/log/app.log

# NOT safe (though should be redacted)
grep "email=" /var/log/app.log  # Should find nothing
```

---

## Escalation Contacts

| Role | Contact | Escalation Criteria |
|------|---------|---------------------|
| Backend Lead | backend-lead@cosmetica5.com | Code/database issues after 30min |
| DBA | dba@cosmetica5.com | Database corruption, performance |
| Infrastructure | infra@cosmetica5.com | Network, server, deployment |
| Security | security@cosmetica5.com | DDoS, abuse, data breach |

---

## Post-Incident Review

After resolving critical alert:

1. **Document RCA** (Root Cause Analysis)
2. **Update runbook** if new pattern discovered
3. **Adjust alert threshold** if false positive
4. **Create follow-up ticket** for permanent fix
5. **Share lessons learned** in team retrospective

---

## References

- **Alerts**: `docs/ALERTING.md`
- **Dashboards**: `docs/OBSERVABILITY_DASHBOARDS.md`
- **Metrics**: `docs/OBSERVABILITY_FLOWS.md`
- **SLOs**: `docs/SLO.md`
