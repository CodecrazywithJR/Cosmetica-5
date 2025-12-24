"""
Core views - Health checks, system status, diagnostics.
"""
import os
import shutil
from datetime import datetime, timedelta
from django.db import connection
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import SystemDiagnosticsSerializer, UserProfileSerializer

try:
    import redis
    from django.conf import settings
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    from minio import Minio
    MINIO_AVAILABLE = True
except ImportError:
    MINIO_AVAILABLE = False


class HealthCheckView(APIView):
    """
    Health check endpoint for monitoring and load balancers.
    
    Checks:
    - API is responding
    - Database connection
    - Redis connection
    
    Returns:
    - 200 OK if all systems are healthy
    - 503 Service Unavailable if any system is down
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        health_status = {
            'status': 'ok',
            'database': 'unknown',
            'redis': 'unknown',
        }
        
        all_healthy = True
        
        # Check database
        try:
            connection.ensure_connection()
            health_status['database'] = 'ok'
        except Exception as e:
            health_status['database'] = f'error: {str(e)}'
            all_healthy = False
        
        # Check Redis
        if REDIS_AVAILABLE:
            try:
                from django.conf import settings
                r = redis.Redis.from_url(settings.CELERY_BROKER_URL)
                r.ping()
                health_status['redis'] = 'ok'
            except Exception as e:
                health_status['redis'] = f'error: {str(e)}'
                all_healthy = False
        else:
            health_status['redis'] = 'not configured'
        
        # Set overall status
        if not all_healthy:
            health_status['status'] = 'degraded'
            return Response(health_status, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        return Response(health_status, status=status.HTTP_200_OK)


class DiagnosticsView(APIView):
    """
    System diagnostics endpoint - STAFF ONLY.
    
    Returns comprehensive system information:
    - Service health status
    - Disk space
    - Database connections
    - Redis info
    - MinIO buckets
    - Celery workers
    - Recent errors
    """
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        diagnostics = {
            'timestamp': timezone.now(),
            'services': self._get_services_status(),
            'disk_space': self._get_disk_space(),
            'database': self._get_database_info(),
            'redis': self._get_redis_info(),
            'minio_buckets': self._get_minio_buckets(),
            'celery_workers': self._get_celery_workers(),
            'recent_errors': self._get_recent_errors(),
        }
        
        serializer = SystemDiagnosticsSerializer(diagnostics)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def _get_services_status(self):
        """Check health of all services."""
        services = []
        
        # Database
        try:
            connection.ensure_connection()
            services.append({
                'name': 'PostgreSQL',
                'status': 'healthy',
                'details': {'vendor': connection.vendor}
            })
        except Exception as e:
            services.append({
                'name': 'PostgreSQL',
                'status': 'unhealthy',
                'details': {'error': str(e)}
            })
        
        # Redis
        if REDIS_AVAILABLE:
            try:
                r = redis.Redis.from_url(settings.CELERY_BROKER_URL)
                r.ping()
                services.append({
                    'name': 'Redis',
                    'status': 'healthy',
                })
            except Exception as e:
                services.append({
                    'name': 'Redis',
                    'status': 'unhealthy',
                    'details': {'error': str(e)}
                })
        
        # MinIO
        if MINIO_AVAILABLE:
            try:
                minio_client = self._get_minio_client()
                # Try to list buckets as health check
                list(minio_client.list_buckets())
                services.append({
                    'name': 'MinIO',
                    'status': 'healthy',
                })
            except Exception as e:
                services.append({
                    'name': 'MinIO',
                    'status': 'unhealthy',
                    'details': {'error': str(e)}
                })
        
        return services
    
    def _get_disk_space(self):
        """Get disk space information."""
        try:
            stat = shutil.disk_usage('/')
            total_gb = stat.total / (1024 ** 3)
            used_gb = stat.used / (1024 ** 3)
            free_gb = stat.free / (1024 ** 3)
            percent = (stat.used / stat.total) * 100
            
            return {
                'total': f"{total_gb:.2f} GB",
                'used': f"{used_gb:.2f} GB",
                'free': f"{free_gb:.2f} GB",
                'percent': round(percent, 2)
            }
        except Exception:
            return {
                'total': 'unknown',
                'used': 'unknown',
                'free': 'unknown',
                'percent': 0.0
            }
    
    def _get_database_info(self):
        """Get database connection pool info."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        (SELECT count(*) FROM pg_stat_activity) as total,
                        (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') as active,
                        (SELECT count(*) FROM pg_stat_activity WHERE state = 'idle') as idle
                """)
                row = cursor.fetchone()
                return {
                    'total_connections': row[0],
                    'active_connections': row[1],
                    'idle_connections': row[2]
                }
        except Exception:
            return {
                'total_connections': 0,
                'active_connections': 0,
                'idle_connections': 0
            }
    
    def _get_redis_info(self):
        """Get Redis information."""
        if not REDIS_AVAILABLE:
            return {
                'connected_clients': 0,
                'used_memory': 'N/A',
                'used_memory_peak': 'N/A',
                'uptime_days': 0
            }
        
        try:
            r = redis.Redis.from_url(settings.CELERY_BROKER_URL)
            info = r.info()
            return {
                'connected_clients': info.get('connected_clients', 0),
                'used_memory': f"{info.get('used_memory_human', '0B')}",
                'used_memory_peak': f"{info.get('used_memory_peak_human', '0B')}",
                'uptime_days': info.get('uptime_in_days', 0)
            }
        except Exception:
            return {
                'connected_clients': 0,
                'used_memory': 'Error',
                'used_memory_peak': 'Error',
                'uptime_days': 0
            }
    
    def _get_minio_client(self):
        """Get MinIO client instance."""
        from django.conf import settings
        return Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_USE_SSL
        )
    
    def _get_minio_buckets(self):
        """Get MinIO bucket information."""
        if not MINIO_AVAILABLE:
            return []
        
        buckets = []
        try:
            minio_client = self._get_minio_client()
            
            # Check clinical bucket
            try:
                clinical_exists = minio_client.bucket_exists(settings.MINIO_CLINICAL_BUCKET)
                if clinical_exists:
                    objects = list(minio_client.list_objects(settings.MINIO_CLINICAL_BUCKET))
                    buckets.append({
                        'name': settings.MINIO_CLINICAL_BUCKET,
                        'object_count': len(objects),
                        'size': 'N/A',
                        'accessible': True
                    })
                else:
                    buckets.append({
                        'name': settings.MINIO_CLINICAL_BUCKET,
                        'accessible': False
                    })
            except Exception:
                buckets.append({
                    'name': settings.MINIO_CLINICAL_BUCKET,
                    'accessible': False
                })
            
            # Check marketing bucket
            try:
                marketing_exists = minio_client.bucket_exists(settings.MINIO_MARKETING_BUCKET)
                if marketing_exists:
                    objects = list(minio_client.list_objects(settings.MINIO_MARKETING_BUCKET))
                    buckets.append({
                        'name': settings.MINIO_MARKETING_BUCKET,
                        'object_count': len(objects),
                        'size': 'N/A',
                        'accessible': True
                    })
                else:
                    buckets.append({
                        'name': settings.MINIO_MARKETING_BUCKET,
                        'accessible': False
                    })
            except Exception:
                buckets.append({
                    'name': settings.MINIO_MARKETING_BUCKET,
                    'accessible': False
                })
        except Exception:
            pass
        
        return buckets
    
    def _get_celery_workers(self):
        """Get Celery worker information."""
        workers = []
        try:
            from celery import current_app
            inspect = current_app.control.inspect()
            
            # Get active workers
            active = inspect.active()
            stats = inspect.stats()
            
            if active and stats:
                for worker_name in active.keys():
                    worker_stats = stats.get(worker_name, {})
                    workers.append({
                        'hostname': worker_name,
                        'status': 'active',
                        'active_tasks': len(active.get(worker_name, [])),
                        'processed_tasks': worker_stats.get('total', {}).get('tasks', 0)
                    })
            else:
                # No workers detected
                workers.append({
                    'hostname': 'N/A',
                    'status': 'no workers detected',
                    'active_tasks': 0,
                    'processed_tasks': 0
                })
        except Exception:
            workers.append({
                'hostname': 'N/A',
                'status': 'error',
                'active_tasks': 0,
                'processed_tasks': 0
            })
        
        return workers
    
    def _get_recent_errors(self):
        """Get recent error logs (last 24 hours)."""
        # This is a simplified version - in production you'd query actual log storage
        # For now, return empty list
        # In future: integrate with logging backend (e.g., Sentry, CloudWatch)
        return []


class CurrentUserView(APIView):
    """
    Current authenticated user profile endpoint.
    
    GET /api/auth/me/ - Returns profile of the authenticated user.
    
    This endpoint is the contract between backend authentication and frontend UI:
    - Frontend calls this after successful JWT login to get user details
    - Returns user ID, email, active status, and roles array
    - Frontend uses roles to determine UI permissions (which screens to show)
    
    Security:
    - Requires valid JWT access token (IsAuthenticated)
    - Backend remains the authorization authority (frontend only improves UX)
    - No sensitive data is exposed (no password hash, no PII beyond email)
    
    Response format:
    {
        "id": "uuid",
        "email": "user@example.com",
        "is_active": true,
        "roles": ["admin", "practitioner"]
    }
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Return current user profile with roles."""
        user = request.user
        
        # Get user roles from UserRole relationship
        roles = list(user.user_roles.values_list('role__name', flat=True))
        
        # Prepare profile data
        profile_data = {
            'id': user.id,
            'email': user.email,
            'is_active': user.is_active,
            'roles': roles,
        }
        
        # Serialize and return
        serializer = UserProfileSerializer(profile_data)
        return Response(serializer.data, status=status.HTTP_200_OK)
