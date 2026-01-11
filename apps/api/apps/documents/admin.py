from django.contrib import admin
from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'object_key',
        'content_type',
        'size_bytes',
        'is_deleted',
        'created_by_user',
        'created_at'
    ]
    list_filter = ['is_deleted', 'content_type', 'created_at']
    search_fields = ['title', 'object_key', 'sha256']
    readonly_fields = [
        'id',
        'storage_bucket',
        'created_at',
        'updated_at',
        'deleted_at'
    ]
    autocomplete_fields = ['created_by_user', 'deleted_by_user']
    
    fieldsets = (
        ('Document Info', {
            'fields': ('id', 'title', 'storage_bucket', 'object_key')
        }),
        ('File Metadata', {
            'fields': ('content_type', 'size_bytes', 'sha256')
        }),
        ('Soft Delete', {
            'fields': ('is_deleted', 'deleted_at', 'deleted_by_user')
        }),
        ('Audit', {
            'fields': ('created_by_user', 'created_at', 'updated_at')
        }),
    )
    
    def get_queryset(self, request):
        """Show all documents including soft-deleted by default in admin."""
        return super().get_queryset(request)

