"""
Operations/Diagnostics serializers.
"""
from rest_framework import serializers


class ServiceStatusSerializer(serializers.Serializer):
    """Service health status."""
    name = serializers.CharField()
    status = serializers.CharField()
    details = serializers.DictField(required=False)


class DiskSpaceSerializer(serializers.Serializer):
    """Disk space information."""
    total = serializers.CharField()
    used = serializers.CharField()
    free = serializers.CharField()
    percent = serializers.FloatField()


class DatabaseConnectionSerializer(serializers.Serializer):
    """Database connection pool info."""
    total_connections = serializers.IntegerField()
    active_connections = serializers.IntegerField()
    idle_connections = serializers.IntegerField()


class RedisInfoSerializer(serializers.Serializer):
    """Redis information."""
    connected_clients = serializers.IntegerField()
    used_memory = serializers.CharField()
    used_memory_peak = serializers.CharField()
    uptime_days = serializers.IntegerField()


class MinioBucketSerializer(serializers.Serializer):
    """MinIO bucket information."""
    name = serializers.CharField()
    object_count = serializers.IntegerField(required=False)
    size = serializers.CharField(required=False)
    accessible = serializers.BooleanField()


class CeleryWorkerSerializer(serializers.Serializer):
    """Celery worker information."""
    hostname = serializers.CharField()
    status = serializers.CharField()
    active_tasks = serializers.IntegerField()
    processed_tasks = serializers.IntegerField()


class RecentErrorSerializer(serializers.Serializer):
    """Recent error log entry."""
    timestamp = serializers.DateTimeField()
    level = serializers.CharField()
    message = serializers.CharField()
    logger = serializers.CharField()


class SystemDiagnosticsSerializer(serializers.Serializer):
    """Complete system diagnostics."""
    timestamp = serializers.DateTimeField()
    services = ServiceStatusSerializer(many=True)
    disk_space = DiskSpaceSerializer()
    database = DatabaseConnectionSerializer()
    redis = RedisInfoSerializer()
    minio_buckets = MinioBucketSerializer(many=True)
    celery_workers = CeleryWorkerSerializer(many=True)
    recent_errors = RecentErrorSerializer(many=True)
