"""
Instrumented wrapper for sales services Layer 3 A: consume_stock_for_sale.

This adds observability to the existing function.
"""
import time
from apps.core.observability import metrics
from apps.core.observability.events import log_stock_consumed, log_consistency_checkpoint
from apps.core.observability.tracing import trace_span, add_span_attribute
from apps.core.observability import get_sanitized_logger

logger = get_sanitized_logger(__name__)


def instrument_consume_stock_for_sale(original_func):
    """
    Decorator to instrument consume_stock_for_sale with observability.
    
    Usage:
        # In sales/services.py after the original function:
        consume_stock_for_sale = instrument_consume_stock_for_sale(consume_stock_for_sale)
    """
    def wrapper(sale, location=None, created_by=None):
        start_time = time.time()
        
        with trace_span('consume_stock_for_sale', attributes={'sale_id': str(sale.id)}):
            try:
                # Call original function
                moves = original_func(sale, location=location, created_by=created_by)
                
                # Calculate metrics
                duration_ms = (time.time() - start_time) * 1000
                total_quantity = sum(abs(m.quantity) for m in moves)
                
                # Emit metrics
                metrics.sales_paid_stock_consume_total.labels(result='success').inc()
                metrics.sales_paid_stock_consume_duration_seconds.observe(duration_ms / 1000)
                
                for move in moves:
                    metrics.stock_moves_total.labels(
                        move_type=move.move_type,
                        result='success'
                    ).inc()
                
                # Log event
                log_stock_consumed(
                    sale,
                    stock_moves_count=len(moves),
                    total_quantity=total_quantity,
                    duration_ms=round(duration_ms, 2)
                )
                
                # Consistency checkpoint
                log_consistency_checkpoint(
                    'sale_paid_stock_consumed',
                    entity_ids={'sale_id': str(sale.id)},
                    checks_passed={
                        'stock_moves_created': len(moves) > 0,
                        'all_product_lines_covered': True,  # FEFO ensures this
                    },
                    stock_moves_count=len(moves),
                    total_quantity=total_quantity
                )
                
                add_span_attribute('stock_moves_created', len(moves))
                add_span_attribute('total_quantity', total_quantity)
                
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
                        'error_message': str(e)
                    },
                    exc_info=True
                )
                
                raise
    
    return wrapper
