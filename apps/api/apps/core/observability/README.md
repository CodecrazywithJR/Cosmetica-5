# Observability Module

Comprehensive observability layer for Cosmetica 5 with structured logging, metrics, tracing, and health checks.

## Features

- ✅ **Request Correlation**: Automatic request ID generation and propagation
- ✅ **Structured Logging**: JSON logs with PHI/PII protection
- ✅ **Prometheus Metrics**: Business and technical metrics
- ✅ **Distributed Tracing**: OpenTelemetry support (optional)
- ✅ **Domain Events**: Business milestone tracking
- ✅ **Health Checks**: Liveness and readiness probes
- ✅ **Security First**: NEVER logs sensitive patient data

## Quick Start

### 1. Install Dependencies

```bash
# Required
pip install Django djangorestframework

# Optional (recommended)
pip install prometheus-client  # For metrics
pip install opentelemetry-api opentelemetry-sdk  # For tracing
```

### 2. Configure Settings

Already configured in `config/settings.py`:

```python
MIDDLEWARE = [
    # ...
    'apps.core.observability.correlation.RequestCorrelationMiddleware',
    # ...
]

LOGGING = {
    'filters': {
        'correlation': {
            '()': 'apps.core.observability.logging.CorrelationFilter',
        },
    },
    'formatters': {
        'json': {
            '()': 'apps.core.observability.logging.SanitizedJSONFormatter',
        },
    },
    # ...
}
```

### 3. Use in Code

```python
from apps.core.observability import metrics, get_sanitized_logger
from apps.core.observability.events import log_domain_event

logger = get_sanitized_logger(__name__)

def my_function(entity):
    # Emit metric
    metrics.my_operation_total.labels(result='success').inc()
    
    # Log event (no PHI/PII!)
    log_domain_event(
        'operation_completed',
        entity_type='Entity',
        entity_id=str(entity.id),
        result='success'
    )
    
    logger.info('Operation completed', extra={'entity_id': str(entity.id)})
```

## Module Structure

```
apps/core/observability/
├── __init__.py              # Public API exports
├── correlation.py           # Request ID middleware
├── logging.py               # Structured logging + sanitization
├── metrics.py               # Prometheus metrics registry
├── events.py                # Domain event helpers
├── tracing.py               # OpenTelemetry integration
├── health.py                # Health check endpoints
└── instrumentation_sales.py # Example instrumentation wrappers
```

## API Reference

### Metrics

```python
from apps.core.observability import metrics

# Counter
metrics.sales_transition_total.labels(
    from_status='pending',
    to_status='paid',
    result='success'
).inc()

# Histogram (for durations)
metrics.sales_paid_stock_consume_duration_seconds.observe(0.123)
```

### Logging

```python
from apps.core.observability import get_sanitized_logger

logger = get_sanitized_logger(__name__)

# All extra fields automatically sanitized
logger.info(
    'Sale created',
    extra={
        'sale_id': str(sale.id),
        'user_id': str(user.id),
        # 'email': 'user@example.com'  # ❌ Automatically redacted!
    }
)
```

### Domain Events

```python
from apps.core.observability.events import (
    log_domain_event,
    log_stock_consumed,
    log_refund_created,
    log_over_refund_blocked,
)

# Generic event
log_domain_event(
    'custom_event',
    entity_type='Sale',
    entity_id=str(sale.id),
    result='success',
    custom_field='value'
)

# Pre-defined events
log_stock_consumed(sale, stock_moves_count=5, total_quantity=10)
log_refund_created(refund, refund_type='partial', stock_moves_count=2)
log_over_refund_blocked(sale_line, requested_qty=5, available_qty=2)
```

### Tracing

```python
from apps.core.observability.tracing import trace_span, add_span_attribute

with trace_span('my_operation', attributes={'entity_id': str(id)}):
    # ... business logic ...
    add_span_attribute('items_processed', 10)
```

### Health Checks

Endpoints automatically available:

- `GET /healthz` - Liveness probe (always 200)
- `GET /readyz` - Readiness probe (checks database)

## Security

### PHI/PII Protection

The following fields are **automatically redacted** in all logs:

- Patient: `first_name`, `last_name`, `email`, `phone`, `date_of_birth`
- Clinical: `chief_complaint`, `assessment`, `plan`, `notes`, `internal_notes`
- Auth: `password`, `token`, `secret`, `api_key`

**Safe to log**:
- UUIDs: `sale_id`, `user_id`, `refund_id`, etc.
- Status codes, event names
- Quantities, amounts (numeric)
- Product names (not patient names!)

### Testing for PHI Leaks

```python
def test_no_phi_in_logs(caplog):
    # Trigger operation
    create_sale(patient=patient)
    
    # Verify no PHI
    log_text = ' '.join([r.message for r in caplog.records])
    assert 'first_name' not in log_text
    assert 'email' not in log_text
    assert patient.email not in log_text
```

## Metrics Catalog

### Sales
- `sales_transition_total{from_status,to_status,result}`
- `sales_paid_stock_consume_total{result}`
- `sales_paid_stock_consume_duration_seconds`
- `sale_refunds_total{type,result}`
- `sale_refund_over_refund_attempts_total`
- `sale_refund_idempotency_conflicts_total`

### Stock
- `stock_moves_total{move_type,result}`
- `stock_allocation_fefo_duration_seconds`
- `stock_refund_in_total{result}`
- `stock_negative_onhand_detected_total`

### Clinical
- `clinical_auditlog_created_total{model,action}`
- `clinical_auditlog_access_denied_total{role}`

### Public
- `public_leads_requests_total{result}`
- `public_leads_throttled_total{scope}`

**Full list**: See `docs/OBSERVABILITY.md`

## Development

### Running Tests

```bash
# Test observability module
pytest tests/test_observability.py -v

# With coverage
pytest tests/test_observability.py --cov=apps.core.observability --cov-report=html
```

### Adding New Metrics

1. Define in `metrics.py`:
```python
self.my_metric = self._create_counter(
    'my_metric_total',
    'Description',
    ['label1', 'label2']
)
```

2. Use in code:
```python
metrics.my_metric.labels(label1='val1', label2='val2').inc()
```

3. Test:
```python
def test_my_metric_emitted(mock_metrics):
    # ... trigger operation ...
    mock_metrics.my_metric.labels.assert_called()
```

4. Document in `docs/OBSERVABILITY.md`

## Documentation

- **Observability Guide**: `docs/OBSERVABILITY.md` - Complete reference
- **Instrumentation Guide**: `docs/INSTRUMENTATION.md` - How to add observability to code
- **Tests**: `tests/test_observability.py` - Usage examples

## Production Setup

### Environment Variables

```bash
# Required
APP_VERSION=1.0.0
COMMIT_HASH=abc123def

# Recommended
LOG_LEVEL=INFO
DJANGO_LOG_LEVEL=WARNING

# Optional (tracing)
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318
OTEL_SERVICE_NAME=cosmetica-5-api
```

### Kubernetes

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8000
  initialDelaySeconds: 30

readinessProbe:
  httpGet:
    path: /readyz
    port: 8000
  initialDelaySeconds: 10
```

### Prometheus Scraping

```yaml
- job_name: 'cosmetica-api'
  static_configs:
    - targets: ['api:8000']
  metrics_path: /metrics
```

## Support

For issues or questions:
- Check `docs/OBSERVABILITY.md` for detailed guide
- Check `docs/INSTRUMENTATION.md` for code patterns
- Run tests: `pytest tests/test_observability.py -v`

## License

Same as parent project (Cosmetica 5).
