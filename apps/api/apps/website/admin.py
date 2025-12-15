from django.contrib import admin
from .models import (
    WebsiteSettings,
    Page,
    Post,
    Service,
    StaffMember,
    MarketingMediaAsset,
    Lead,
)


@admin.register(WebsiteSettings)
class WebsiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Clinic Information', {
            'fields': ['clinic_name', 'phone', 'email', 'address', 'opening_hours']
        }),
        ('Social Media', {
            'fields': ['instagram_url', 'facebook_url', 'youtube_url']
        }),
        ('Languages', {
            'fields': ['default_language', 'enabled_languages']
        }),
    ]
    
    def has_add_permission(self, request):
        # Only allow one instance
        return not WebsiteSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion of settings
        return False


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'language', 'status', 'updated_at']
    list_filter = ['status', 'language']
    search_fields = ['title', 'slug']
    prepopulated_fields = {'slug': ('title',)}
    fieldsets = [
        ('Basic Info', {
            'fields': ['title', 'slug', 'language', 'status']
        }),
        ('Content', {
            'fields': ['content_markdown', 'content_json'],
            'description': 'Use either Markdown or JSON, not both'
        }),
        ('SEO', {
            'fields': ['seo_title', 'seo_description', 'og_image_key'],
            'classes': ['collapse']
        }),
    ]


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'language', 'status', 'published_at', 'created_at']
    list_filter = ['status', 'language', 'published_at']
    search_fields = ['title', 'slug', 'tags']
    prepopulated_fields = {'slug': ('title',)}
    fieldsets = [
        ('Basic Info', {
            'fields': ['title', 'slug', 'language', 'status']
        }),
        ('Content', {
            'fields': ['excerpt', 'content_markdown', 'content_json', 'cover_image_key']
        }),
        ('Categorization', {
            'fields': ['tags']
        }),
        ('SEO', {
            'fields': ['seo_title', 'seo_description'],
            'classes': ['collapse']
        }),
        ('Publishing', {
            'fields': ['published_at']
        }),
    ]


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'language', 'status', 'price', 'duration_minutes', 'order_index']
    list_filter = ['status', 'language']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['order_index']


@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ['name', 'role', 'language', 'status', 'order_index']
    list_filter = ['status', 'language']
    search_fields = ['name', 'role']
    list_editable = ['order_index']


@admin.register(MarketingMediaAsset)
class MarketingMediaAssetAdmin(admin.ModelAdmin):
    list_display = ['object_key', 'type', 'language', 'file_size', 'created_at']
    list_filter = ['type', 'language']
    search_fields = ['object_key', 'alt_text']
    readonly_fields = ['bucket', 'file_size', 'mime_type', 'created_at']


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'status', 'preferred_language', 'created_at']
    list_filter = ['status', 'preferred_language', 'created_at']
    search_fields = ['name', 'email', 'phone', 'message']
    readonly_fields = ['created_at', 'updated_at', 'source']
    fieldsets = [
        ('Contact Information', {
            'fields': ['name', 'email', 'phone', 'preferred_language']
        }),
        ('Message', {
            'fields': ['message', 'source']
        }),
        ('Management', {
            'fields': ['status', 'notes']
        }),
        ('Metadata', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
