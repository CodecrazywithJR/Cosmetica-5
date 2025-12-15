from django.contrib import admin

from .models import SkinPhoto


@admin.register(SkinPhoto)
class SkinPhotoAdmin(admin.ModelAdmin):
    list_display = ['id', 'patient', 'body_part', 'taken_at', 'thumbnail_generated']
    list_filter = ['body_part', 'thumbnail_generated', 'taken_at']
    search_fields = ['patient__first_name', 'patient__last_name', 'tags']
    readonly_fields = ['created_at', 'updated_at', 'thumbnail', 'thumbnail_generated']
    autocomplete_fields = ['patient', 'encounter']
