"""
Tracing support (optional OpenTelemetry integration).

Provides context managers for manual span creation when OpenTelemetry
is not available or for additional custom spans.
"""
import logging
import time
from contextlib import contextmanager
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Try to import OpenTelemetry
try:
    from opentelemetry import trace
    from opentelemetry.trace import SpanKind
    OTEL_AVAILABLE = True
    tracer = trace.get_tracer(__name__)
except ImportError:
    OTEL_AVAILABLE = False
    tracer = None


@contextmanager
def trace_span(
    name: str,
    kind: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None
):
    """
    Context manager for creating trace spans.
    
    Works with OpenTelemetry if available, otherwise provides
    basic logging-based tracing.
    
    Args:
        name: Span name
        kind: Span kind (server, client, internal, etc.)
        attributes: Span attributes
    
    Usage:
        with trace_span('consume_stock_for_sale', attributes={'sale_id': str(sale.id)}):
            # ... operation ...
    """
    start_time = time.time()
    
    if OTEL_AVAILABLE and tracer:
        # Use OpenTelemetry
        span_kind_map = {
            'server': SpanKind.SERVER,
            'client': SpanKind.CLIENT,
            'internal': SpanKind.INTERNAL,
        }
        span_kind = span_kind_map.get(kind, SpanKind.INTERNAL)
        
        with tracer.start_as_current_span(name, kind=span_kind) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            
            try:
                yield span
            except Exception as e:
                span.set_attribute('error', True)
                span.set_attribute('error.type', e.__class__.__name__)
                span.set_attribute('error.message', str(e))
                raise
    else:
        # Fallback: log-based tracing
        logger.debug(
            f'Span started: {name}',
            extra={
                'event': 'span_start',
                'span_name': name,
                'attributes': attributes or {}
            }
        )
        
        try:
            yield None
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f'Span failed: {name}',
                extra={
                    'event': 'span_error',
                    'span_name': name,
                    'duration_ms': duration_ms,
                    'error_type': e.__class__.__name__,
                    'attributes': attributes or {}
                }
            )
            raise
        else:
            duration_ms = (time.time() - start_time) * 1000
            logger.debug(
                f'Span completed: {name}',
                extra={
                    'event': 'span_complete',
                    'span_name': name,
                    'duration_ms': duration_ms,
                    'attributes': attributes or {}
                }
            )


def add_span_attribute(key: str, value: Any):
    """
    Add attribute to current span if tracing is enabled.
    
    Args:
        key: Attribute key
        value: Attribute value
    """
    if OTEL_AVAILABLE:
        span = trace.get_current_span()
        if span and span.is_recording():
            span.set_attribute(key, value)
