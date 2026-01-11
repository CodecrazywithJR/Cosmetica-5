"""
Domain events logging helpers.

Provides structured event logging for business operations.
"""
import logging
from typing import Dict, Any, Optional
from .logging import get_sanitized_logger, sanitize_dict

logger = get_sanitized_logger(__name__)


def log_domain_event(
    event_name: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    entity_ids: Optional[Dict[str, str]] = None,
    result: str = 'success',
    **extra_fields
):
    """
    Log a domain event with structured data.
    
    Args:
        event_name: Name of the event (e.g., 'sale_transition', 'stock_consumed')
        entity_type: Type of entity (e.g., 'Sale', 'StockMove')
        entity_id: ID of primary entity
        entity_ids: Dictionary of related entity IDs
        result: Result of operation (success, failure, etc.)
        **extra_fields: Additional fields to log (will be sanitized)
    
    Example:
        log_domain_event(
            'sale_paid_stock_consumed',
            entity_type='Sale',
            entity_id=str(sale.id),
            entity_ids={'sale_id': str(sale.id)},
            result='success',
            stock_moves_count=5,
            total_quantity=10
        )
    """
    event_data = {
        'event': event_name,
        'result': result,
    }
    
    if entity_type:
        event_data['entity_type'] = entity_type
    
    if entity_id:
        event_data['entity_id'] = entity_id
    
    if entity_ids:
        event_data.update(entity_ids)
    
    # Sanitize extra fields
    sanitized_extra = sanitize_dict(extra_fields)
    event_data.update(sanitized_extra)
    
    # Log at appropriate level based on result
    if result in ['failure', 'error']:
        logger.error(f'Domain event: {event_name}', extra=event_data)
    elif result in ['warning', 'blocked', 'throttled']:
        logger.warning(f'Domain event: {event_name}', extra=event_data)
    else:
        logger.info(f'Domain event: {event_name}', extra=event_data)


def log_consistency_checkpoint(
    checkpoint_name: str,
    entity_ids: Dict[str, str],
    checks_passed: Dict[str, bool],
    **extra_fields
):
    """
    Log a consistency checkpoint event.
    
    Used to verify data integrity at critical points.
    
    Args:
        checkpoint_name: Name of checkpoint (e.g., 'sale_refund_stock_consistency')
        entity_ids: Dictionary of entity IDs involved
        checks_passed: Dictionary of check results {check_name: passed}
        **extra_fields: Additional context
    
    Example:
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
    """
    all_passed = all(checks_passed.values())
    
    event_data = {
        'event': 'consistency_checkpoint',
        'checkpoint': checkpoint_name,
        'status': 'passed' if all_passed else 'failed',
        'checks': checks_passed,
    }
    event_data.update(entity_ids)
    event_data.update(sanitize_dict(extra_fields))
    
    if all_passed:
        logger.info(f'Checkpoint passed: {checkpoint_name}', extra=event_data)
    else:
        logger.error(f'Checkpoint FAILED: {checkpoint_name}', extra=event_data)


def log_sale_transition(sale, from_status, to_status, result='success', **extra):
    """Log sale status transition event."""
    log_domain_event(
        'sale_transition',
        entity_type='Sale',
        entity_id=str(sale.id),
        entity_ids={'sale_id': str(sale.id)},
        result=result,
        from_status=from_status,
        to_status=to_status,
        **extra
    )


def log_stock_consumed(sale, stock_moves_count, total_quantity, duration_ms=None):
    """Log stock consumption for sale payment."""
    extra = {
        'stock_moves_count': stock_moves_count,
        'total_quantity': total_quantity,
    }
    if duration_ms:
        extra['duration_ms'] = duration_ms
    
    log_domain_event(
        'sale_paid_stock_consumed',
        entity_type='Sale',
        entity_id=str(sale.id),
        entity_ids={'sale_id': str(sale.id)},
        result='success',
        **extra
    )


def log_refund_created(refund, refund_type='partial', stock_moves_count=0, **extra):
    """Log refund creation event."""
    log_domain_event(
        'sale_refund_created',
        entity_type='SaleRefund',
        entity_id=str(refund.id),
        entity_ids={
            'refund_id': str(refund.id),
            'sale_id': str(refund.sale_id)
        },
        result='success',
        refund_type=refund_type,
        stock_moves_count=stock_moves_count,
        **extra
    )


def log_over_refund_blocked(sale_line, requested_qty, available_qty):
    """Log blocked over-refund attempt."""
    log_domain_event(
        'sale_refund_over_refund_blocked',
        entity_type='SaleLine',
        entity_id=str(sale_line.id),
        entity_ids={
            'sale_line_id': str(sale_line.id),
            'sale_id': str(sale_line.sale_id)
        },
        result='blocked',
        requested_qty=float(requested_qty),
        available_qty=float(available_qty),
        product_name=sale_line.product_name
    )


def log_idempotency_conflict(sale, idempotency_key, existing_refund_id):
    """Log idempotency key conflict (duplicate request)."""
    log_domain_event(
        'sale_refund_idempotency_conflict',
        entity_type='Sale',
        entity_id=str(sale.id),
        entity_ids={
            'sale_id': str(sale.id),
            'existing_refund_id': str(existing_refund_id)
        },
        result='duplicate',
        idempotency_key=idempotency_key
    )


def log_stock_refund_mismatch(refund, mismatch_type, **extra):
    """Log stock refund mismatch (source_move missing, wrong batch, etc.)."""
    log_domain_event(
        'stock_refund_mismatch',
        entity_type='SaleRefund',
        entity_id=str(refund.id),
        entity_ids={'refund_id': str(refund.id)},
        result='warning',
        mismatch_type=mismatch_type,
        **extra
    )
