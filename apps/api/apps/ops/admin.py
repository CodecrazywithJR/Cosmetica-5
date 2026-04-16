"""
Admin for the Ops app.

AuditLog is registered as a read-only view: no create, edit or delete
actions are permitted via the Django admin.
"""
from django.contrib import admin

from apps.ops.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only admin for the generic audit log."""

    list_display = (
        'timestamp',
        'event_type',
        'entity_type',
        'entity_id',
        'user',
        'legal_entity',
    )
    list_filter  = ('event_type', 'entity_type', 'legal_entity')
    search_fields = ('entity_type', 'entity_id', 'event_type', 'user__email')
    ordering = ('-timestamp',)
    readonly_fields = (
        'id', 'timestamp', 'created_at',
        'user', 'legal_entity',
        'entity_type', 'entity_id', 'event_type', 'payload_json',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

