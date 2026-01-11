"""
Request correlation middleware.

Generates/propagates X-Request-ID and injects it into logs.
Supports distributed tracing integration.
"""
import uuid
import time
import logging
from django.utils.deprecation import MiddlewareMixin
from threading import local

# Thread-local storage for request context
_request_context = local()

logger = logging.getLogger(__name__)


def get_request_id():
    """Get current request ID from thread-local storage."""
    return getattr(_request_context, 'request_id', None)


def get_trace_id():
    """Get current trace ID from thread-local storage."""
    return getattr(_request_context, 'trace_id', None)


def get_user_id():
    """Get current user ID from thread-local storage."""
    return getattr(_request_context, 'user_id', None)


def get_user_roles():
    """Get current user roles from thread-local storage."""
    return getattr(_request_context, 'user_roles', [])


class RequestCorrelationMiddleware(MiddlewareMixin):
    """
    Middleware to handle request correlation and tracing.
    
    - Generates/propagates X-Request-ID
    - Extracts trace context from headers
    - Stores context in thread-local for logging
    - Adds correlation headers to response
    - Tracks request duration
    """
    
    REQUEST_ID_HEADER = 'HTTP_X_REQUEST_ID'
    TRACE_ID_HEADER = 'HTTP_X_TRACE_ID'
    SPAN_ID_HEADER = 'HTTP_X_SPAN_ID'
    
    def process_request(self, request):
        """Process incoming request and setup correlation context."""
        # Generate or extract request ID
        request_id = request.META.get(self.REQUEST_ID_HEADER)
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Extract trace context if available
        trace_id = request.META.get(self.TRACE_ID_HEADER)
        span_id = request.META.get(self.SPAN_ID_HEADER)
        
        # Store in request object
        request.request_id = request_id
        request.trace_id = trace_id
        request.span_id = span_id
        request.start_time = time.time()
        
        # Store in thread-local for logging
        _request_context.request_id = request_id
        _request_context.trace_id = trace_id
        _request_context.span_id = span_id
        
        # Extract user context (populated after auth middleware)
        if hasattr(request, 'user') and request.user.is_authenticated:
            _request_context.user_id = str(request.user.id)
            _request_context.user_roles = list(
                request.user.groups.values_list('name', flat=True)
            )
        else:
            _request_context.user_id = None
            _request_context.user_roles = []
    
    def process_response(self, request, response):
        """Add correlation headers to response."""
        if hasattr(request, 'request_id'):
            response['X-Request-ID'] = request.request_id
        
        if hasattr(request, 'trace_id') and request.trace_id:
            response['X-Trace-ID'] = request.trace_id
        
        # Calculate duration
        if hasattr(request, 'start_time'):
            duration_ms = (time.time() - request.start_time) * 1000
            
            # Log request completion
            logger.info(
                'Request completed',
                extra={
                    'event': 'http_request_completed',
                    'path': request.path,
                    'method': request.method,
                    'status_code': response.status_code,
                    'duration_ms': round(duration_ms, 2),
                    'request_id': getattr(request, 'request_id', None),
                    'trace_id': getattr(request, 'trace_id', None),
                    'user_id': get_user_id(),
                    'user_roles': get_user_roles(),
                }
            )
        
        return response
    
    def process_exception(self, request, exception):
        """Log exceptions with correlation context."""
        duration_ms = 0
        if hasattr(request, 'start_time'):
            duration_ms = (time.time() - request.start_time) * 1000
        
        logger.error(
            f'Request failed: {exception.__class__.__name__}',
            exc_info=True,
            extra={
                'event': 'http_request_exception',
                'path': request.path,
                'method': request.method,
                'exception_type': exception.__class__.__name__,
                'duration_ms': round(duration_ms, 2),
                'request_id': getattr(request, 'request_id', None),
                'trace_id': getattr(request, 'trace_id', None),
                'user_id': get_user_id(),
                'user_roles': get_user_roles(),
            }
        )


def clear_request_context():
    """Clear thread-local request context (useful for testing)."""
    for attr in ['request_id', 'trace_id', 'span_id', 'user_id', 'user_roles']:
        if hasattr(_request_context, attr):
            delattr(_request_context, attr)
