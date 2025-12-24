"""
Observability module for Cosmetica 5.

Provides structured logging, metrics, tracing, and health checks
with PHI/PII protection.
"""
from .metrics import metrics
from .events import log_domain_event
from .logging import get_sanitized_logger

__all__ = ['metrics', 'log_domain_event', 'get_sanitized_logger']
