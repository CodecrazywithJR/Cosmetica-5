# Observability Instrumentation Guide

This document provides step-by-step instructions for instrumenting existing code with observability features.

## Quick Start: Instrumenting a Service Function

### Before (No Observability)

```python
@transaction.atomic
def consume_stock_for_sale(sale, location=None, created_by=None):
    # ... business logic ...
    return moves
```

### After (With Observability)

```python
from apps.core.observability import metrics, get_sanitized_logger
from apps.core.observability.events import log_stock_consumed, log_consistency_checkpoint
from apps.core.observability.tracing import trace_span
import time

logger = get_sanitized_logger(__name__)

@transaction.atomic
def consume_stock_for_sale(sale, location=None, created_by=None):
    start_time = time.time()
    
    with trace_span('consume_stock_for_sale', attributes={'sale_id': str(sale.id)}):
        try:
            # ... existing business logic ...
            moves = _original_logic(sale, location, created_by)
            
            # Emit metrics
            duration_ms = (time.time() - start_time) * 1000
            metrics.sales_paid_stock_consume_total.labels(result='success').inc()
            metrics.sales_paid_stock_consume_duration_seconds.observe(duration_ms / 1000)
            
            # Log event
            log_stock_consumed(
                sale,
                stock_moves_count=len(moves),
                total_quantity=sum(abs(m.quantity) for m in moves),
                duration_ms=round(duration_ms, 2)
            )
            
            # Consistency checkpoint
            log_consistency_checkpoint(
                'sale_paid_stock_consumed',
                entity_ids={'sale_id': str(sale.id)},
                checks_passed={
                    'stock_moves_created': len(moves) > 0,
                    'all_lines_covered': True,
                },
                stock_moves_count=len(moves)
            )
            
            return moves
            
        except Exception as e:
            # Emit failure metrics
            metrics.sales_paid_stock_consume_total.labels(result='failure').inc()
            metrics.exceptions_total.labels(
                exception_type=e.__class__.__name__,
                location='consume_stock_for_sale'
            ).inc()
            
            logger.error(
                f'Stock consumption failed: {e.__class__.__name__}',
                extra={
                    'event': 'stock_consume_failed',
                    'sale_id': str(sale.id),
                    'error_type': e.__class__.__name__,
                },
                exc_info=True
            )
            
            raise
```

## Pattern 1: Simple Function Instrumentation

Use this for functions that don't require complex tracing.

```python
from apps.core.observability import metrics, log_domain_event

def my_business_function(entity):
    try:
        # Business logic
        result = perform_operation(entity)
        
        # Emit metric
        metrics.my_operation_total.labels(result='success').inc()
        
        # Log event
        log_domain_event(
            'operation_completed',
            entity_type='MyEntity',
            entity_id=str(entity.id),
            result='success'
        )
        
        return result
    except Exception as e:
        metrics.my_operation_total.labels(result='failure').inc()
        metrics.exceptions_total.labels(
            exception_type=e.__class__.__name__,
            location='my_business_function'
        ).inc()
        raise
```

## Pattern 2: Validation with Metrics

Track validation failures and blocked operations.

```python
from apps.core.observability import metrics
from apps.core.observability.events import log_over_refund_blocked

def validate_refund_quantity(sale_line, qty_refunded):
    already_refunded = calculate_already_refunded(sale_line)
    available = sale_line.quantity - already_refunded
    
    if qty_refunded > available:
        # Emit metric
        metrics.sale_refund_over_refund_attempts_total.inc()
        
        # Log detailed event
        log_over_refund_blocked(sale_line, qty_refunded, available)
        
        # Raise validation error
        raise ValidationError(f'Cannot refund {qty_refunded}. Available: {available}')
```

## Pattern 3: Idempotency Detection

Track when duplicate requests are detected.

```python
from apps.core.observability import metrics
from apps.core.observability.events import log_idempotency_conflict

def create_refund_with_idempotency(sale, idempotency_key):
    # Check for existing refund
    existing = SaleRefund.objects.filter(
        sale=sale,
        metadata__idempotency_key=idempotency_key
    ).first()
    
    if existing:
        # Emit metric
        metrics.sale_refund_idempotency_conflicts_total.inc()
        
        # Log event
        log_idempotency_conflict(sale, idempotency_key, existing.id)
        
        # Return existing (idempotent behavior)
        return existing
    
    # Create new refund
    # ...
```

## Pattern 4: Instrumentation Wrapper

For minimal code changes, wrap existing functions:

```python
# In apps/core/observability/instrumentation_sales.py

def instrument_consume_stock_for_sale(original_func):
    """Decorator to add observability to consume_stock_for_sale."""
    def wrapper(sale, location=None, created_by=None):
        start_time = time.time()
        
        with trace_span('consume_stock_for_sale', attributes={'sale_id': str(sale.id)}):
            try:
                moves = original_func(sale, location, created_by)
                
                # Metrics and events
                duration_ms = (time.time() - start_time) * 1000
                metrics.sales_paid_stock_consume_total.labels(result='success').inc()
                log_stock_consumed(sale, len(moves), sum(abs(m.quantity) for m in moves), duration_ms)
                
                return moves
            except Exception as e:
                metrics.sales_paid_stock_consume_total.labels(result='failure').inc()
                raise
    
    return wrapper

# In apps/sales/services.py (at end of file):
consume_stock_for_sale = instrument_consume_stock_for_sale(consume_stock_for_sale)
```

## Pattern 5: View/Endpoint Instrumentation

DRF views with request/response tracking.

```python
from apps.core.observability import metrics, log_domain_event
from rest_framework import status

class SaleRefundViewSet(viewsets.ModelViewSet):
    
    @action(detail=True, methods=['post'])
    def refunds(self, request, pk=None):
        sale = self.get_object()
        
        try:
            refund = create_partial_refund(sale, request.data, request.user)
            
            # Emit metric
            metrics.sale_refunds_total.labels(type='partial', result='success').inc()
            
            # Log event
            log_domain_event(
                'sale_refund_api_request',
                entity_type='Sale',
                entity_id=str(sale.id),
                result='success',
                refund_id=str(refund.id),
                user_id=str(request.user.id)
            )
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except ValidationError as e:
            metrics.sale_refunds_total.labels(type='partial', result='validation_error').inc()
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
```

## Instrumenting Existing Codebase

### Step 1: Import Observability Tools

Add to top of service/views file:

```python
from apps.core.observability import metrics, get_sanitized_logger
from apps.core.observability.events import (
    log_domain_event,
    log_consistency_checkpoint,
    # ... other event helpers
)
from apps.core.observability.tracing import trace_span, add_span_attribute

logger = get_sanitized_logger(__name__)
```

### Step 2: Identify Critical Operations

Operations that should be instrumented:
- ✅ Stock consumption (FEFO allocation)
- ✅ Sale status transitions
- ✅ Refund creation (full and partial)
- ✅ Stock moves creation
- ✅ Payment processing
- ✅ Audit log creation
- ✅ Public lead submissions

### Step 3: Add Metrics Emission

At success/failure points:

```python
# Success case
metrics.operation_total.labels(result='success').inc()

# Failure case
metrics.operation_total.labels(result='failure').inc()
metrics.exceptions_total.labels(
    exception_type=e.__class__.__name__,
    location='function_name'
).inc()
```

### Step 4: Add Event Logging

For business milestones:

```python
log_domain_event(
    'event_name',
    entity_type='EntityType',
    entity_id=str(entity.id),
    result='success',
    additional_field=value
)
```

### Step 5: Add Consistency Checkpoints

After critical multi-step operations:

```python
log_consistency_checkpoint(
    'checkpoint_name',
    entity_ids={'entity_id': str(id)},
    checks_passed={
        'check1': True,
        'check2': condition_met,
    },
    expected_value=10,
    actual_value=10
)
```

## Testing Instrumentation

### Unit Test with Mocks

```python
from unittest.mock import patch

@patch('apps.sales.services.metrics')
@patch('apps.sales.services.log_stock_consumed')
def test_consume_stock_emits_metrics(mock_log, mock_metrics, sale):
    consume_stock_for_sale(sale)
    
    # Verify metric emitted
    mock_metrics.sales_paid_stock_consume_total.labels.assert_called_with(result='success')
    mock_metrics.sales_paid_stock_consume_total.labels().inc.assert_called_once()
    
    # Verify event logged
    mock_log.assert_called_once()
```

### Integration Test

```python
def test_refund_creates_domain_event(sale, caplog):
    refund = create_partial_refund(sale, {...})
    
    # Check log contains event
    assert any('sale_refund_created' in record.message for record in caplog.records)
    
    # Check no PHI in logs
    log_text = ' '.join([record.message for record in caplog.records])
    assert 'first_name' not in log_text
    assert 'email' not in log_text
```

## Common Pitfalls

### ❌ Don't Log PHI/PII

```python
# WRONG - Logs patient name
logger.info(f'Sale for patient {patient.first_name} {patient.last_name}')

# CORRECT - Use ID only
logger.info('Sale created', extra={'patient_id': str(patient.id)})
```

### ❌ Don't Create High-Cardinality Metrics

```python
# WRONG - Unique label per user creates millions of series
metrics.user_action.labels(user_email=user.email).inc()

# CORRECT - Use aggregated labels
metrics.user_action.labels(user_role=user.groups.first().name).inc()
```

### ❌ Don't Forget Error Cases

```python
# WRONG - Only tracks success
metrics.operation_total.inc()
return result

# CORRECT - Track both success and failure
try:
    result = operation()
    metrics.operation_total.labels(result='success').inc()
    return result
except Exception as e:
    metrics.operation_total.labels(result='failure').inc()
    raise
```

## Migration Checklist

For each service function:

- [ ] Add imports for observability tools
- [ ] Wrap in `trace_span()` context manager
- [ ] Add metrics emission on success/failure
- [ ] Add `log_domain_event()` for milestone
- [ ] Add consistency checkpoint if multi-step
- [ ] Add unit test verifying metrics/events
- [ ] Verify no PHI/PII in logs

## Quick Reference

### Metrics

```python
# Counter
metrics.operation_total.labels(label='value').inc()

# Histogram (duration)
metrics.operation_duration_seconds.observe(duration_in_seconds)

# Gauge (current value)
metrics.current_stock_level.set(quantity)
```

### Logging

```python
# Get logger
logger = get_sanitized_logger(__name__)

# Log with extra fields
logger.info('Event', extra={'sale_id': str(sale.id), 'key': 'value'})

# Log with levels
logger.debug('Detail')
logger.info('Normal')
logger.warning('Anomaly')
logger.error('Failure', exc_info=True)
```

### Tracing

```python
# Create span
with trace_span('operation_name', attributes={'entity_id': str(id)}):
    # ... operation ...
    add_span_attribute('result', 'success')
```

### Domain Events

```python
log_domain_event(
    'event_name',
    entity_type='Type',
    entity_id=str(id),
    result='success',
    **extra_fields
)
```

---

**For more details, see**: `docs/OBSERVABILITY.md`
