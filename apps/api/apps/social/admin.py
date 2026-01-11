from django.contrib import admin
from .models import InstagramPost, InstagramHashtag


@admin.register(InstagramPost)
class InstagramPostAdmin(admin.ModelAdmin):
    list_display = ['caption_preview', 'language', 'status', 'media_count', 'scheduled_at', 'published_at', 'created_at']
    list_filter = ['status', 'language', 'created_at', 'published_at']
    search_fields = ['caption', 'hashtags']
    readonly_fields = ['created_at', 'updated_at', 'pack_generated_at', 'published_at']
    
    fieldsets = [
        ('Content', {
            'fields': ['caption', 'language', 'hashtags']
        }),
        ('Media (Marketing Bucket ONLY)', {
            'fields': ['media_keys'],
            'description': 'MinIO object keys from MARKETING bucket. Never use clinical bucket.'
        }),
        ('Publishing', {
            'fields': ['status', 'scheduled_at', 'published_at', 'instagram_url']
        }),
        ('Pack Generation', {
            'fields': ['pack_generated_at', 'pack_file_path'],
            'classes': ['collapse']
        }),
        ('Analytics (Optional)', {
            'fields': ['likes_count', 'comments_count'],
            'classes': ['collapse']
        }),
        ('Metadata', {
            'fields': ['created_by', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    def caption_preview(self, obj):
        """Show caption preview."""
        preview = obj.caption[:60]
        if len(obj.caption) > 60:
            preview += '...'
        return preview
    caption_preview.short_description = 'Caption'
    
    def media_count(self, obj):
        """Show number of media items."""
        return len(obj.media_keys) if obj.media_keys else 0
    media_count.short_description = 'Media'
    
    def save_model(self, request, obj, form, change):
        """Set created_by on creation."""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['mark_as_ready', 'mark_as_archived']
    
    def mark_as_ready(self, request, queryset):
        """Mark selected posts as ready to publish."""
        count = 0
        for post in queryset:
            if post.can_generate_pack():
                post.mark_as_ready()
                count += 1
        self.message_user(request, f"{count} post(s) marked as ready.")
    mark_as_ready.short_description = "Mark as ready to publish"
    
    def mark_as_archived(self, request, queryset):
        """Archive selected posts."""
        count = queryset.update(status='archived')
        self.message_user(request, f"{count} post(s) archived.")
    mark_as_archived.short_description = "Archive selected posts"


@admin.register(InstagramHashtag)
class InstagramHashtagAdmin(admin.ModelAdmin):
    list_display = ['tag', 'category', 'usage_count']
    list_filter = ['category']
    search_fields = ['tag']
    ordering = ['-usage_count', 'tag']
