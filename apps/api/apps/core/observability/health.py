"""
Health check endpoints.

Provides /healthz and /readyz endpoints for monitoring.
"""
import logging
from django.http import JsonResponse
from django.views import View
from django.db import connection
from django.conf import settings

logger = logging.getLogger(__name__)


class HealthzView(View):
    """
    Basic health check endpoint.
    
    Returns 200 OK if application is running.
    Does not check dependencies.
    """
    
    def get(self, request):
        """Return basic health status."""
        health_data = {
            'status': 'ok',
            'version': getattr(settings, 'VERSION', 'unknown'),
        }
        
        # Add commit hash if available (set by deployment)
        commit_hash = getattr(settings, 'COMMIT_HASH', None)
        if commit_hash:
            health_data['commit'] = commit_hash
        
        return JsonResponse(health_data, status=200)


class ReadyzView(View):
    """
    Readiness check endpoint.
    
    Returns 200 OK if application is ready to serve traffic.
    Checks database connection.
    """
    
    def get(self, request):
        """Return readiness status with dependency checks."""
        checks = {
            'database': self._check_database(),
        }
        
        all_healthy = all(checks.values())
        
        response_data = {
            'status': 'ready' if all_healthy else 'not_ready',
            'checks': checks,
        }
        
        status_code = 200 if all_healthy else 503
        
        return JsonResponse(response_data, status=status_code)
    
    def _check_database(self):
        """Check database connection."""
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                return True
        except Exception as e:
            logger.error(
                'Database health check failed',
                extra={
                    'event': 'health_check_failed',
                    'check': 'database',
                    'error': str(e)
                }
            )
            return False
