# Observability Flows - End-to-End Instrumentation

> **Status**: Implemented  
> **Date**: 2025-12-16  
> **Flows Instrumented**: 3 critical business flows

---

## Overview

This document describes the 3 end-to-end flows that have been instrumented with comprehensive observability:

1. **Flow 1**: Sale → PAID + Stock Consumption
2. **Flow 2**: Refunds (Full + Partial)
3. **Flow 3**: Public Lead Submission

Each flow emits:
- ✅ **Metrics** (Prometheus counters + histograms)
- ✅ **Structured logs** (JSON with PHI/PII sanitization)
- ✅ **Domain events** (business milestones)
- ✅ **Distributed traces** (if OpenTelemetry enabled)
- ✅ **Request correlation** (via X-Request-ID)

---

## Flow 1: Sale → PAID + Stock Consumption

### Business Logic

When a sale transitions from DRAFT/PENDING → PAID:
1. Validate transition is allowed
2. Call `consume_stock_for_sale()`
3. Use FEFO allocation to consume stock
4. Create `StockMove` records (SALE_OUT)
5. Update `StockOnHand` balances
6. Mark sale as PAID

### Instrumentation Points

#### 1.1 Transition API (`POST /api/sales/{id}/transition/`)

**Location**: `apps/sales/views.py::SaleViewSet.transition()`

**Metrics Emitted**:
```python
# Success
sales_transition_total{from_status="draft", to_status="paid", result="success"} 1

# Failures
sales_transition_total{from_status="draft", to_status="paid", result="insufficient_stock"} 1
sales_transition_total{from_status="draft", to_status="paid", result="expired_batch"} 1
sales_transition_total{from_status="draft", to_status="paid", result="validation_error"} 1
```

**Events Emitted**:
```json
{
  "event": "sale.transition",
  "entity_type": "Sale",
  "entity_id": "sale-uuid-123",
  "result": "success",
  "from_status": "draft",
  "to_status": "paid",
  "duration_ms": 245,
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Tracing**:
```
Span: sale_transition
  ├─ Attribute: sale_id = "sale-uuid-123"
  ├─ Attribute: from_status = "draft"
  └─ Attribute: to_status = "paid"
```

---

#### 1.2 Stock Consumption (`consume_stock_for_sale()`)

**Location**: `apps/sales/services.py::consume_stock_for_sale()`

**Metrics Emitted**:
```python
# Success
sales_paid_stock_consume_total{result="success"} 1
sales_paid_stock_consume_duration_seconds_bucket{le="0.1"} 1
sales_paid_stock_consume_duration_seconds_sum 0.085

# Idempotent (already processed)
sales_paid_stock_consume_total{result="idempotent"} 1

# Errors
sales_paid_stock_consume_total{result="insufficient_stock"} 1
sales_paid_stock_consume_total{result="expired_batch"} 1
sales_paid_stock_consume_total{result="error"} 1

# Exception tracking
exceptions_total{exception_type="InsufficientStockError", location="consume_stock_for_sale"} 1
```

**Events Emitted**:
```json
{
  "event": "sale.paid.stock_consumed",
  "entity_type": "Sale",
  "entity_id": "sale-uuid-123",
  "result": "success",
  "stock_moves_count": 3,
  "total_quantity": 5,
  "duration_ms": 85,
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Consistency Checkpoint**:
```json
{
  "event": "consistency_checkpoint",
  "checkpoint": "stock_consumed_for_sale",
  "status": "passed",
  "checks": {
    "moves_created": true,
    "all_lines_processed": true
  },
  "entity_type": "Sale",
  "entity_id": "sale-uuid-123",
  "metadata": {
    "location": "MAIN-WAREHOUSE"
  }
}
```

**Tracing**:
```
Span: consume_stock_for_sale
  ├─ Attribute: sale_id = "sale-uuid-123"
  ├─ Attribute: sale_number = "SALE-2025-001"
  ├─ Attribute: location_code = "MAIN-WAREHOUSE"
  └─ Child Spans: (FEFO allocation per product)
```

---

### Example Logs (Structured JSON)

**Success**:
```json
{
  "timestamp": "2025-12-16T10:30:45.123Z",
  "level": "INFO",
  "logger": "apps.sales.services",
  "message": "Domain event: sale.paid.stock_consumed",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user-abc-123",
  "sale_id": "sale-uuid-123",
  "stock_moves_count": 3,
  "total_quantity": 5,
  "duration_ms": 85
}
```

**Insufficient Stock**:
```json
{
  "timestamp": "2025-12-16T10:31:12.456Z",
  "level": "ERROR",
  "logger": "apps.sales.services",
  "message": "Stock consumption failed - insufficient stock",
  "request_id": "550e8400-e29b-41d4-a716-446655440001",
  "user_id": "user-abc-123",
  "sale_id": "sale-uuid-456",
  "product_name": "Botox 100U",
  "error": "Insufficient stock: requested 5, available 2"
}
```

---

## Flow 2: Refunds (Full + Partial)

### Business Logic

**Full Refund** (Layer 3 B):
1. Sale must be PAID
2. Create REFUND_IN moves (exact reversal of SALE_OUT)
3. Restore stock to original batch/location
4. Mark sale as REFUNDED

**Partial Refund** (Layer 3 C):
1. Sale must be PAID
2. Validate qty_refunded ≤ available (prevent over-refund)
3. Create partial REFUND_IN moves
4. Multiple refunds allowed per sale
5. Idempotency via `idempotency_key`

### Instrumentation Points

#### 2.1 Full Refund (`refund_stock_for_sale()`)

**Location**: `apps/sales/services.py::refund_stock_for_sale()`

**Metrics**:
```python
sale_refunds_total{type="full", result="success"} 1
sale_refunds_total{type="full", result="error"} 1
```

**Events**:
```json
{
  "event": "sale.refund.created",
  "refund_type": "full",
  "sale_id": "sale-uuid-123",
  "stock_moves_count": 3,
  "result": "success"
}
```

---

#### 2.2 Partial Refund (`refund_partial_for_sale()`)

**Location**: `apps/sales/services.py::refund_partial_for_sale()`

**Metrics**:
```python
# Success
sale_refunds_total{type="partial", result="success"} 1
sale_refund_lines_total{result="success"} 2

# Over-refund attempts
sale_refund_over_refund_attempts_total 1

# Idempotency conflicts
sale_refund_idempotency_conflicts_total 1

# Stock moves
sale_refund_stock_moves_created_total{type="partial"} 3
```

**Events**:
```json
{
  "event": "sale.refund.created",
  "refund_type": "partial",
  "refund_id": "refund-uuid-789",
  "sale_id": "sale-uuid-123",
  "lines_count": 2,
  "stock_moves_count": 3,
  "result": "success",
  "duration_ms": 125
}
```

**Over-Refund Blocked**:
```json
{
  "event": "sale.refund.over_refund_blocked",
  "sale_line_id": "line-uuid-456",
  "requested_qty": 5,
  "available_qty": 2,
  "result": "blocked"
}
```

**Idempotency Conflict**:
```json
{
  "event": "sale.refund.idempotency_conflict",
  "sale_id": "sale-uuid-123",
  "idempotency_key": "refund-2025-001",
  "existing_refund_id": "refund-uuid-111"
}
```

---

### Example Logs

**Partial Refund Success**:
```json
{
  "timestamp": "2025-12-16T11:15:30.789Z",
  "level": "INFO",
  "logger": "apps.sales.services",
  "message": "Domain event: sale.refund.created",
  "request_id": "550e8400-e29b-41d4-a716-446655440002",
  "refund_id": "refund-uuid-789",
  "refund_type": "partial",
  "sale_id": "sale-uuid-123",
  "lines_count": 2,
  "stock_moves_count": 3
}
```

**Over-Refund Blocked**:
```json
{
  "timestamp": "2025-12-16T11:16:45.123Z",
  "level": "WARNING",
  "logger": "apps.sales.services",
  "message": "Refund validation failed - over-refund attempt",
  "request_id": "550e8400-e29b-41d4-a716-446655440003",
  "sale_line_id": "line-uuid-456",
  "requested_qty": 5,
  "available_qty": 2
}
```

---

## Flow 3: Public Lead Submission

### Business Logic

1. Anonymous user submits contact form
2. Throttling applied (10/hour, 2/min burst)
3. Create `Lead` record
4. Send confirmation response

### Instrumentation Points

#### 3.1 Lead Creation (`POST /public/leads/`)

**Location**: `apps/website/views.py::create_lead()`

**Metrics**:
```python
# Success
public_leads_requests_total{result="accepted"} 1
public_leads_requests_total{result="rejected"} 1

# Throttling
public_leads_throttled_total{scope="hourly"} 1
public_leads_throttled_total{scope="burst"} 1
public_leads_429_total 1

# HTTP metrics (auto from middleware)
http_requests_total{path="/public/leads/", method="POST", status="201"} 1
http_requests_total{path="/public/leads/", method="POST", status="429"} 1
http_request_duration_seconds_bucket{path="/public/leads/", method="POST", le="0.1"} 1
```

**Events**:
```json
{
  "event": "public.lead.created",
  "lead_id": "lead-uuid-999",
  "result": "success",
  "source": "contact_form",
  "request_id": "550e8400-e29b-41d4-a716-446655440004"
}
```

**Throttled Event**:
```json
{
  "event": "public.lead.throttled",
  "scope": "hourly",
  "ip_address": "[REDACTED]",
  "result": "rejected",
  "request_id": "550e8400-e29b-41d4-a716-446655440005"
}
```

---

### Example Logs

**Lead Created (PHI-Safe)**:
```json
{
  "timestamp": "2025-12-16T12:00:15.456Z",
  "level": "INFO",
  "logger": "apps.website.views",
  "message": "Public lead created",
  "request_id": "550e8400-e29b-41d4-a716-446655440004",
  "lead_id": "lead-uuid-999",
  "source": "contact_form"
}
```

**Note**: Email, name, phone are NEVER logged (PHI protection).

---

## Metrics Catalog (Flow-Specific)

### Sales Flow Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `sales_transition_total` | Counter | `from_status`, `to_status`, `result` | Sale status transitions |
| `sales_paid_stock_consume_total` | Counter | `result` | Stock consumption attempts |
| `sales_paid_stock_consume_duration_seconds` | Histogram | - | Stock consumption duration |

### Refund Flow Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `sale_refunds_total` | Counter | `type`, `result` | Refund creations (full/partial) |
| `sale_refund_lines_total` | Counter | `result` | Refund lines processed |
| `sale_refund_over_refund_attempts_total` | Counter | - | Over-refund validations blocked |
| `sale_refund_idempotency_conflicts_total` | Counter | - | Duplicate refund attempts |
| `sale_refund_stock_moves_created_total` | Counter | `type` | Stock reversal moves created |

### Public Lead Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `public_leads_requests_total` | Counter | `result` | Lead submissions (accepted/rejected) |
| `public_leads_throttled_total` | Counter | `scope` | Throttled requests (hourly/burst) |
| `public_leads_429_total` | Counter | - | HTTP 429 responses |

---

## PHI/PII Protection

### Never Logged

The following fields are **NEVER** logged in any flow:

- ❌ `first_name`, `last_name`
- ❌ `email`, `phone`, `phone_number`
- ❌ `address`, `date_of_birth`
- ❌ `chief_complaint`, `assessment`, `plan`, `notes`
- ❌ `password`, `token`, `secret`

### Always Safe to Log

The following are **ALWAYS** safe:

- ✅ UUIDs (`sale_id`, `user_id`, `refund_id`, `lead_id`)
- ✅ Product names, quantities, amounts
- ✅ Status codes, event names
- ✅ Timestamps, durations
- ✅ User roles (group names, not personal info)

---

## Request Correlation

All logs, metrics, and events include `request_id` for distributed tracing:

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "trace_id": "1234567890abcdef",  // If OpenTelemetry enabled
  "user_id": "user-abc-123",
  "user_roles": "Reception,ClinicalOps"
}
```

**Propagation**:
- HTTP Header: `X-Request-ID` (auto-generated if missing)
- Thread-local storage: Available in all service layers
- Response header: Included in API responses

---

## Alerting Recommendations

### Critical Alerts (PagerDuty)

1. **High Error Rate (Sales)**:
   ```promql
   rate(sales_paid_stock_consume_total{result!="success"}[5m]) > 0.1
   ```

2. **Refund Rollbacks**:
   ```promql
   rate(sale_refund_rollback_total[15m]) > 5
   ```

3. **Stock Consumption Failures**:
   ```promql
   rate(sales_paid_stock_consume_total{result="insufficient_stock"}[5m]) > 10
   ```

### Warning Alerts (Slack)

1. **Over-Refund Attempts**:
   ```promql
   rate(sale_refund_over_refund_attempts_total[1h]) > 10
   ```

2. **Public Lead Throttling Spike**:
   ```promql
   rate(public_leads_throttled_total[5m]) > 50
   ```

3. **Idempotency Conflicts**:
   ```promql
   rate(sale_refund_idempotency_conflicts_total[30m]) > 20
   ```

---

## Testing

Run observability flow tests:

```bash
# All observability tests
pytest tests/test_observability_flows.py -v

# Specific flow
pytest tests/test_observability_flows.py::TestFlow1SalePaidStockConsumption -v

# PHI sanitization tests
pytest tests/test_observability_flows.py::TestPHISanitization -v
```

**Expected Output**:
```
tests/test_observability_flows.py::TestFlow1SalePaidStockConsumption::test_sale_paid_emits_metrics_and_events PASSED
tests/test_observability_flows.py::TestFlow1SalePaidStockConsumption::test_stock_consumption_logs_no_phi PASSED
tests/test_observability_flows.py::TestPHISanitization::test_sensitive_fields_not_in_logs PASSED
...
```

---

## Production Deployment

### Environment Variables

```bash
# Enable structured logging
LOG_LEVEL=INFO
DJANGO_DEBUG=False

# Metrics endpoint
PROMETHEUS_ENABLED=True
METRICS_PORT=8001

# Tracing (optional)
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318
OTEL_SERVICE_NAME=cosmetica-5-api

# Correlation
REQUEST_ID_HEADER=X-Request-ID
```

### Prometheus Scrape Config

```yaml
scrape_configs:
  - job_name: 'cosmetica-api'
    static_configs:
      - targets: ['api:8001']
    scrape_interval: 15s
    scrape_timeout: 10s
```

### Grafana Dashboard Queries

**Sale Transition Success Rate**:
```promql
rate(sales_transition_total{result="success"}[5m]) 
/ 
rate(sales_transition_total[5m])
```

**P95 Stock Consumption Duration**:
```promql
histogram_quantile(0.95, 
  rate(sales_paid_stock_consume_duration_seconds_bucket[5m])
)
```

**Refund Rate (per hour)**:
```promql
rate(sale_refunds_total{result="success"}[1h]) * 3600
```

---

## Next Steps

1. **Instrument remaining flows**:
   - Clinical audit logging
   - Stock FEFO allocation details
   - Appointment scheduling

2. **Add business KPI metrics**:
   - Revenue per day/hour
   - Top selling products
   - Refund ratio

3. **Set up alerting**:
   - Deploy Prometheus AlertManager
   - Configure PagerDuty integration
   - Test alert routing

---

*Last updated: 2025-12-16*  
*Instrumented flows: 3/3 ✅*  
*PHI protection: Verified ✅*  
*Tests: Passing ✅*
