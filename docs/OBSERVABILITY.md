# Observability Guide - Cosmetica 5

## Overview

Cosmetica 5 implements a comprehensive observability layer with:
- **Structured logging** with request correlation and PHI/PII protection
- **Prometheus metrics** for monitoring business and technical operations
- **Distributed tracing** support (OpenTelemetry compatible)
- **Domain events** for business milestone tracking
- **Health checks** for liveness and readiness probes

**Security First**: All logging and metrics are designed to NEVER expose PHI/PII data.

---

## Architecture

### Components

```
┌──────────────────────────────────────────────────────────┐
│                  Request Middleware                       │
│  - Generate/propagate X-Request-ID                       │
│  - Extract trace context                                 │
│  - Inject correlation into logs                          │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│              Application Layer                            │
│  - Service functions (consume_stock, refunds, etc.)      │
│  - Emit metrics via metrics.sales_*                      │
│  - Log events via log_domain_event()                     │
│  - Create trace spans via trace_span()                   │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│           Observability Backend                           │
│  Logs → JSON stdout → Aggregator (Loki/CloudWatch)       │
│  Metrics → Prometheus client → Scraper                   │
│  Traces → OpenTelemetry → Jaeger/Tempo (optional)        │
└──────────────────────────────────────────────────────────┘
```

### Request Correlation

Every HTTP request gets a unique `request_id` that flows through:
1. Middleware generates/extracts from `X-Request-ID` header
2. Stored in thread-local storage for the request lifecycle
3. Injected into all log records via `CorrelationFilter`
4. Added to response headers for client correlation

**User Context**: Authenticated requests also track `user_id` and `user_roles` (group names).

---

## Metrics

### HTTP Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `http_requests_total` | Counter | `path`, `method`, `status` | Total HTTP requests |
| `http_request_duration_seconds` | Histogram | `path`, `method` | Request latency |
| `exceptions_total` | Counter | `exception_type`, `location` | Unhandled exceptions |

**Buckets** for duration: `[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]`

### Sales Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `sales_transition_total` | Counter | `from_status`, `to_status`, `result` | Sale status transitions |
| `sales_paid_stock_consume_total` | Counter | `result` | Stock consumption on payment (success/failure) |
| `sales_paid_stock_consume_duration_seconds` | Histogram | - | Duration of FEFO allocation |
| `sale_refunds_total` | Counter | `type` (full/partial), `result` | Refunds created |
| `sale_refund_lines_total` | Counter | `result` | Refund lines processed |
| `sale_refund_over_refund_attempts_total` | Counter | - | Blocked over-refund attempts |
| `sale_refund_idempotency_conflicts_total` | Counter | - | Duplicate refund requests detected |
| `sale_refund_stock_moves_created_total` | Counter | `type` | Stock moves for refunds |
| `sale_refund_rollback_total` | Counter | `reason` | Refund transaction rollbacks |

### Stock Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `stock_moves_total` | Counter | `move_type`, `result` | Stock movements (IN/OUT/REFUND_IN/etc.) |
| `stock_negative_onhand_detected_total` | Counter | - | Negative stock warnings |
| `stock_allocation_fefo_duration_seconds` | Histogram | - | FEFO allocation performance |
| `stock_refund_in_total` | Counter | `result` | Refund IN moves |
| `stock_refund_in_mismatch_total` | Counter | `type` | Refund mismatches (source_move_missing, wrong_batch) |

### Clinical Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `clinical_auditlog_created_total` | Counter | `model`, `action` | Audit logs created |
| `clinical_auditlog_sanitized_fields_total` | Counter | - | Fields sanitized in audit |
| `clinical_auditlog_access_denied_total` | Counter | `role` | Audit access blocked |

### Public/Leads Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `public_leads_requests_total` | Counter | `result` (accepted/throttled) | Public lead submissions |
| `public_leads_throttled_total` | Counter | `scope` (burst/hourly) | Throttled requests |
| `public_leads_429_total` | Counter | - | HTTP 429 responses |

---

## Logging

### Log Format

**Production** (JSON):
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "logger": "apps.sales.services",
  "message": "Domain event: sale_paid_stock_consumed",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "trace_id": "1234567890abcdef",
  "user_id": "user-abc-123",
  "user_roles": "Reception,ClinicalOps",
  "event": "sale_paid_stock_consumed",
  "sale_id": "sale-xyz-789",
  "stock_moves_count": 3,
  "total_quantity": 5,
  "duration_ms": 45.67
}
```

**Development** (Human-readable):
```
INFO 2024-01-15 10:30:45 sales.services Domain event: sale_paid_stock_consumed
```

### Log Levels

- **DEBUG**: Detailed diagnostic (span start/end, etc.)
- **INFO**: Normal operations (domain events, successful transitions)
- **WARNING**: Anomalies (over-refund attempts, idempotency conflicts)
- **ERROR**: Failures (exceptions, transaction rollbacks)

### Domain Events

**Format**:
```python
log_domain_event(
    event_name='sale_paid_stock_consumed',
    entity_type='Sale',
    entity_id=str(sale.id),
    entity_ids={'sale_id': str(sale.id)},
    result='success',  # success, failure, warning, blocked, etc.
    stock_moves_count=5,
    total_quantity=10
)
```

**Common Events**:
- `sale_transition` - Status change
- `sale_paid_stock_consumed` - FEFO allocation completed
- `sale_refund_created` - Refund processed
- `sale_refund_over_refund_blocked` - Over-refund prevented
- `sale_refund_idempotency_conflict` - Duplicate request
- `stock_consume_idempotent` - Already consumed
- `stock_refund_mismatch` - Reversal issues
- `consistency_checkpoint` - Data integrity verification

### PHI/PII Protection

**NEVER logged**:
- Patient names (`first_name`, `last_name`)
- Contact info (`email`, `phone`, `address`)
- Clinical data (`chief_complaint`, `assessment`, `plan`, `notes`, `internal_notes`)
- Passwords, tokens, secrets
- Date of birth, SSN, MRN

**Safe to log**:
- UUIDs (`sale_id`, `user_id`, `refund_id`, `stockmove_id`)
- Product names (`product_name`)
- Quantities, amounts (numeric data)
- Status codes, event names
- User roles (groups)

**Sanitization**: All `extra={}` dicts passed to loggers are automatically sanitized by `SanitizedJSONFormatter`.

---

## Tracing

### Span Creation

```python
from apps.core.observability.tracing import trace_span, add_span_attribute

with trace_span('consume_stock_for_sale', attributes={'sale_id': str(sale.id)}):
    # ... business logic ...
    add_span_attribute('stock_moves_created', len(moves))
```

**Automatic**:
- HTTP requests (via middleware)
- Service layer operations (instrumented functions)

**Manual**:
- Complex multi-step operations
- Async tasks (Celery)

### OpenTelemetry Integration

**Optional**: If `opentelemetry` package installed, spans are sent to configured exporter.

**Fallback**: Without OpenTelemetry, spans are logged as structured events.

**Configuration** (env vars):
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318
OTEL_SERVICE_NAME=cosmetica-5-api
OTEL_TRACES_EXPORTER=otlp
```

---

## Health Checks

### Endpoints

#### `GET /healthz`
**Purpose**: Liveness probe  
**Auth**: None required  
**Response**:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "commit": "abc123def" 
}
```
**Status**: Always 200 (unless app crashed)

#### `GET /readyz`
**Purpose**: Readiness probe  
**Auth**: None required  
**Response (healthy)**:
```json
{
  "status": "ready",
  "checks": {
    "database": true
  }
}
```
**Status**: 200 if all checks pass, 503 otherwise

**Use in Kubernetes**:
```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /readyz
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
```

---

## Consistency Checkpoints

Critical operations emit checkpoint events to verify data integrity:

```python
log_consistency_checkpoint(
    'sale_refund_stock_consistency',
    entity_ids={'sale_id': str(sale.id), 'refund_id': str(refund.id)},
    checks_passed={
        'stock_moves_created': True,
        'quantities_match': True,
        'no_over_refund': True
    },
    expected_moves=2,
    actual_moves=2
)
```

**Logged as ERROR if any check fails.**

**Checkpoints**:
- Sale paid → Stock consumed (quantities match)
- Refund full → Stock restored (exact reversal)
- Refund partial → Stock restored (proportional, no over-refund)

---

## Alerting Recommendations

### Critical Alerts (PagerDuty)

1. **Database Down**
   - `up{job="cosmetica-api"} == 0` OR `/readyz` returns 503
   - Action: Check DB connection, restart if needed

2. **High Error Rate**
   - `rate(exceptions_total[5m]) > 10`
   - Action: Check logs for exception_type, investigate

3. **Refund Rollbacks Spike**
   - `rate(sale_refund_rollback_total[15m]) > 5`
   - Action: Data corruption or bug, investigate logs

4. **Stock Goes Negative**
   - `stock_negative_onhand_detected_total > 0`
   - Action: Audit stock moves, manual correction

### Warning Alerts (Slack)

1. **Over-Refund Attempts**
   - `rate(sale_refund_over_refund_attempts_total[1h]) > 10`
   - Action: Possible fraud or UX issue

2. **High Latency**
   - `histogram_quantile(0.95, http_request_duration_seconds_bucket) > 2.0`
   - Action: Check DB performance, optimize queries

3. **Throttling Spike**
   - `rate(public_leads_throttled_total[5m]) > 50`
   - Action: Possible DDoS, adjust rate limits

4. **Idempotency Conflicts**
   - `rate(sale_refund_idempotency_conflicts_total[30m]) > 20`
   - Action: Client retry storm, check API clients

### Informational (Grafana Dashboards)

1. **Sales Throughput**
   - `rate(sales_transition_total{to_status="paid"}[1h])`
   
2. **Stock Consumption Performance**
   - `histogram_quantile(0.99, sales_paid_stock_consume_duration_seconds_bucket)`

3. **Refund Rates**
   - `rate(sale_refunds_total[24h]) / rate(sales_transition_total{to_status="paid"}[24h])`

---

## Example Queries

### Prometheus

**Sales per hour**:
```promql
rate(sales_transition_total{to_status="paid",result="success"}[1h]) * 3600
```

**P95 stock consumption latency**:
```promql
histogram_quantile(0.95, 
  rate(sales_paid_stock_consume_duration_seconds_bucket[5m])
)
```

**Error rate**:
```promql
sum(rate(exceptions_total[5m])) by (exception_type)
```

**Refund success rate**:
```promql
rate(sale_refunds_total{result="success"}[1h]) /
rate(sale_refunds_total[1h])
```

### Log Aggregation (Loki/CloudWatch)

**Find failed refunds**:
```logql
{app="cosmetica-api"} | json | event="sale_refund_created" | result="failure"
```

**Track user actions**:
```logql
{app="cosmetica-api"} | json | user_id="user-abc-123" | level="INFO"
```

**Over-refund attempts**:
```logql
{app="cosmetica-api"} | json | event="sale_refund_over_refund_blocked"
```

---

## Production Checklist

### Pre-Deployment

- [ ] Confirm `DEBUG=False` in production settings
- [ ] Set `LOG_LEVEL=INFO` (not DEBUG)
- [ ] Configure `APP_VERSION` and `COMMIT_HASH` env vars
- [ ] Install `prometheus_client` package
- [ ] (Optional) Install `opentelemetry-api` and `opentelemetry-exporter-otlp`

### Monitoring Setup

- [ ] Configure Prometheus scraper on `/metrics` endpoint
- [ ] Set up Grafana dashboards for key metrics
- [ ] Configure log aggregation (Loki, CloudWatch, etc.)
- [ ] Create critical alerts (database, error rate)
- [ ] Create warning alerts (latency, throttling)
- [ ] Set up on-call rotation for critical alerts

### Kubernetes/Docker

- [ ] Add health check endpoints to deployment config
- [ ] Set resource limits based on metric observations
- [ ] Configure horizontal pod autoscaling based on request rate
- [ ] Add log shipping sidecar (Fluent Bit, etc.)

### Verification

- [ ] Test `/healthz` returns 200
- [ ] Test `/readyz` checks database
- [ ] Verify metrics endpoint exposes Prometheus format
- [ ] Confirm logs are JSON format and include `request_id`
- [ ] Validate no PHI/PII in logs (search for `first_name`, `email`, etc.)
- [ ] Test tracing spans appear in Jaeger/Tempo (if configured)

---

## Development Workflow

### Local Testing

```bash
# Run with debug logging
export DJANGO_DEBUG=True
export LOG_LEVEL=DEBUG

# Start server
python manage.py runserver

# Make requests and check logs
curl -H "X-Request-ID: test-123" http://localhost:8000/api/sales/

# Check metrics (if prometheus_client installed)
curl http://localhost:8000/metrics
```

### Running Tests

```bash
# Test observability layer
pytest tests/test_observability.py -v

# Test with coverage
pytest tests/test_observability.py --cov=apps.core.observability --cov-report=term-missing

# All tests
pytest -v
```

### Adding New Metrics

1. Define metric in `apps/core/observability/metrics.py`:
```python
self.my_new_metric = self._create_counter(
    'my_new_metric_total',
    'Description of metric',
    ['label1', 'label2']
)
```

2. Emit metric in business logic:
```python
from apps.core.observability import metrics

metrics.my_new_metric.labels(label1='value1', label2='value2').inc()
```

3. Add test in `tests/test_observability.py`

4. Document in this file

---

## Troubleshooting

### Logs not showing request_id

**Cause**: Middleware not activated or wrong order

**Fix**: Ensure `RequestCorrelationMiddleware` is in `MIDDLEWARE` list AFTER `AuthenticationMiddleware`

### Metrics endpoint 404

**Cause**: `prometheus_client` not installed or endpoint not exposed

**Fix**:
```bash
pip install prometheus-client
# Add endpoint in urls.py:
path('metrics', prometheus_client.exposition.MetricsHandler)
```

### PHI appearing in logs

**Cause**: Field not in `SENSITIVE_FIELDS` list

**Fix**: Add field to `apps/core/observability/logging.py::SENSITIVE_FIELDS`

### Tracing spans not appearing

**Cause**: OpenTelemetry not configured or exporter not running

**Fix**:
```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

### High memory usage

**Cause**: Too many metric cardinality (unique label combinations)

**Fix**: Reduce label values or aggregate metrics

---

## References

- **Prometheus Best Practices**: https://prometheus.io/docs/practices/naming/
- **OpenTelemetry Python**: https://opentelemetry.io/docs/instrumentation/python/
- **Structured Logging**: https://www.structlog.org/
- **HIPAA Logging Guidelines**: Avoid all PHI in logs, use correlation IDs only

---

**Last Updated**: 2024-01-15  
**Version**: 1.0.0
