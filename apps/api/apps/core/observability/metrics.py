"""
Metrics instrumentation wrapper.

Supports Prometheus client or provides no-op fallback.
"""
import logging
from typing import Dict, List, Optional
from functools import wraps
import time

logger = logging.getLogger(__name__)

# Try to import prometheus_client
try:
    from prometheus_client import Counter, Histogram, Gauge, Info
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not available, using no-op metrics")


class NoOpMetric:
    """No-op metric for when Prometheus is not available."""
    
    def inc(self, amount=1, **labels):
        pass
    
    def observe(self, amount, **labels):
        pass
    
    def set(self, value, **labels):
        pass
    
    def labels(self, **labels):
        return self
    
    def info(self, data):
        pass


class MetricsRegistry:
    """
    Central metrics registry for Cosmetica 5.
    
    Provides typed access to all application metrics.
    """
    
    def __init__(self):
        """Initialize metrics registry."""
        self._metrics = {}
        self._setup_metrics()
    
    def _create_counter(self, name, description, labels=None):
        """Create a counter metric."""
        if PROMETHEUS_AVAILABLE:
            return Counter(name, description, labels or [])
        return NoOpMetric()
    
    def _create_histogram(self, name, description, labels=None, buckets=None):
        """Create a histogram metric."""
        if PROMETHEUS_AVAILABLE:
            if buckets:
                return Histogram(name, description, labels or [], buckets=buckets)
            return Histogram(name, description, labels or [])
        return NoOpMetric()
    
    def _create_gauge(self, name, description, labels=None):
        """Create a gauge metric."""
        if PROMETHEUS_AVAILABLE:
            return Gauge(name, description, labels or [])
        return NoOpMetric()
    
    def _create_info(self, name, description):
        """Create an info metric."""
        if PROMETHEUS_AVAILABLE:
            return Info(name, description)
        return NoOpMetric()
    
    def _setup_metrics(self):
        """Setup all application metrics."""
        
        # ===================================================================
        # HTTP Metrics
        # ===================================================================
        self.http_requests_total = self._create_counter(
            'http_requests_total',
            'Total HTTP requests',
            ['path', 'method', 'status']
        )
        
        self.http_request_duration_seconds = self._create_histogram(
            'http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['path', 'method'],
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )
        
        self.exceptions_total = self._create_counter(
            'exceptions_total',
            'Total exceptions',
            ['exception_type', 'location']
        )
        
        # ===================================================================
        # Sales Metrics
        # ===================================================================
        self.sales_transition_total = self._create_counter(
            'sales_transition_total',
            'Sale status transitions',
            ['from_status', 'to_status', 'result']
        )
        
        self.sales_paid_stock_consume_total = self._create_counter(
            'sales_paid_stock_consume_total',
            'Stock consumption on sale payment',
            ['result']
        )
        
        self.sales_paid_stock_consume_duration_seconds = self._create_histogram(
            'sales_paid_stock_consume_duration_seconds',
            'Duration of stock consumption on payment',
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
        )
        
        self.sale_refunds_total = self._create_counter(
            'sale_refunds_total',
            'Sale refunds created',
            ['type', 'result']  # type: full|partial, result: success|failure
        )
        
        self.sale_refund_lines_total = self._create_counter(
            'sale_refund_lines_total',
            'Sale refund lines processed',
            ['result']
        )
        
        self.sale_refund_over_refund_attempts_total = self._create_counter(
            'sale_refund_over_refund_attempts_total',
            'Blocked over-refund attempts'
        )
        
        self.sale_refund_idempotency_conflicts_total = self._create_counter(
            'sale_refund_idempotency_conflicts_total',
            'Idempotency key conflicts detected'
        )
        
        self.sale_refund_stock_moves_created_total = self._create_counter(
            'sale_refund_stock_moves_created_total',
            'Stock moves created for refunds',
            ['type']  # REFUND_IN
        )
        
        self.sale_refund_rollback_total = self._create_counter(
            'sale_refund_rollback_total',
            'Refund transaction rollbacks',
            ['reason']
        )
        
        # ===================================================================
        # Stock Metrics
        # ===================================================================
        self.stock_moves_total = self._create_counter(
            'stock_moves_total',
            'Stock movements',
            ['move_type', 'result']
        )
        
        self.stock_negative_onhand_detected_total = self._create_counter(
            'stock_negative_onhand_detected_total',
            'Negative stock on hand detected'
        )
        
        self.stock_allocation_fefo_duration_seconds = self._create_histogram(
            'stock_allocation_fefo_duration_seconds',
            'FEFO allocation duration',
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5]
        )
        
        self.stock_refund_in_total = self._create_counter(
            'stock_refund_in_total',
            'Refund IN stock moves',
            ['result']
        )
        
        self.stock_refund_in_mismatch_total = self._create_counter(
            'stock_refund_in_mismatch_total',
            'Refund IN mismatches',
            ['type']  # source_move_missing, wrong_batch, wrong_location
        )
        
        # ===================================================================
        # Clinical Metrics
        # ===================================================================
        self.clinical_auditlog_created_total = self._create_counter(
            'clinical_auditlog_created_total',
            'Clinical audit logs created',
            ['model', 'action']
        )
        
        self.clinical_auditlog_sanitized_fields_total = self._create_counter(
            'clinical_auditlog_sanitized_fields_total',
            'Clinical audit log fields sanitized'
        )
        
        self.clinical_auditlog_access_denied_total = self._create_counter(
            'clinical_auditlog_access_denied_total',
            'Clinical audit log access denied',
            ['role']
        )
        
        # ===================================================================
        # Public/Leads Metrics
        # ===================================================================
        self.public_leads_requests_total = self._create_counter(
            'public_leads_requests_total',
            'Public leads requests',
            ['result']  # accepted, throttled
        )
        
        self.public_leads_throttled_total = self._create_counter(
            'public_leads_throttled_total',
            'Public leads throttled requests',
            ['scope']  # burst, hourly
        )
        
        self.public_leads_429_total = self._create_counter(
            'public_leads_429_total',
            'Public leads HTTP 429 responses'
        )
    
    def track_duration(self, histogram_metric):
        """
        Decorator to track function duration.
        
        Usage:
            @metrics.track_duration(metrics.sales_paid_stock_consume_duration_seconds)
            def consume_stock_for_sale(sale):
                ...
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    return func(*args, **kwargs)
                finally:
                    duration = time.time() - start_time
                    histogram_metric.observe(duration)
            return wrapper
        return decorator


# Global metrics instance
metrics = MetricsRegistry()
