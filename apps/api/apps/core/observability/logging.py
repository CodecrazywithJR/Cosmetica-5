"""
Structured logging with PHI/PII protection.

Provides filters, formatters, and helpers for safe logging.
"""
import logging
import json
from datetime import datetime
from .correlation import get_request_id, get_trace_id, get_user_id, get_user_roles


# Fields that should NEVER be logged (PHI/PII)
SENSITIVE_FIELDS = {
    'password',
    'token',
    'secret',
    'api_key',
    'chief_complaint',
    'assessment',
    'plan',
    'internal_notes',
    'notes',
    'first_name',
    'last_name',
    'email',
    'phone',
    'phone_number',
    'address',
    'date_of_birth',
    'ssn',
    'medical_record_number',
}


class CorrelationFilter(logging.Filter):
    """
    Logging filter that injects correlation context into log records.
    """
    
    def filter(self, record):
        """Add correlation fields to log record."""
        record.request_id = get_request_id() or '-'
        record.trace_id = get_trace_id() or '-'
        record.user_id = get_user_id() or '-'
        record.user_roles = ','.join(get_user_roles()) or '-'
        return True


class SanitizedJSONFormatter(logging.Formatter):
    """
    JSON formatter that sanitizes sensitive fields.
    """
    
    def format(self, record):
        """Format log record as JSON with sanitized fields."""
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'request_id': getattr(record, 'request_id', '-'),
            'trace_id': getattr(record, 'trace_id', '-'),
            'user_id': getattr(record, 'user_id', '-'),
            'user_roles': getattr(record, 'user_roles', '-'),
        }
        
        # Add extra fields if present (from extra={} in logging calls)
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if key not in log_data and not key.startswith('_'):
                    # Skip standard logging attributes
                    if key in ['name', 'msg', 'args', 'created', 'filename', 
                              'funcName', 'levelname', 'levelno', 'lineno', 
                              'module', 'msecs', 'pathname', 'process', 
                              'processName', 'relativeCreated', 'thread', 
                              'threadName', 'exc_info', 'exc_text', 'stack_info']:
                        continue
                    
                    # Sanitize sensitive fields
                    if key.lower() in SENSITIVE_FIELDS:
                        log_data[key] = '[REDACTED]'
                    else:
                        log_data[key] = self._sanitize_value(value)
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, default=str)
    
    def _sanitize_value(self, value):
        """Sanitize a value recursively."""
        if isinstance(value, dict):
            return {
                k: '[REDACTED]' if k.lower() in SENSITIVE_FIELDS else self._sanitize_value(v)
                for k, v in value.items()
            }
        elif isinstance(value, (list, tuple)):
            return [self._sanitize_value(v) for v in value]
        else:
            return value


def get_sanitized_logger(name):
    """
    Get a logger with correlation filter applied.
    
    Usage:
        logger = get_sanitized_logger(__name__)
        logger.info('Event', extra={'event': 'user_login', 'user_id': user.id})
    """
    logger = logging.getLogger(name)
    
    # Add correlation filter if not already present
    if not any(isinstance(f, CorrelationFilter) for f in logger.filters):
        logger.addFilter(CorrelationFilter())
    
    return logger


def sanitize_dict(data):
    """
    Sanitize a dictionary by removing/redacting sensitive fields.
    
    Args:
        data: Dictionary to sanitize
        
    Returns:
        Sanitized copy of dictionary
    """
    if not isinstance(data, dict):
        return data
    
    sanitized = {}
    for key, value in data.items():
        if key.lower() in SENSITIVE_FIELDS:
            sanitized[key] = '[REDACTED]'
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict(value)
        elif isinstance(value, (list, tuple)):
            sanitized[key] = [
                sanitize_dict(v) if isinstance(v, dict) else v
                for v in value
            ]
        else:
            sanitized[key] = value
    
    return sanitized
