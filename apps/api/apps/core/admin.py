from django.contrib import admin
from .models import AppSettings, Clinic


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    list_display = ['id', 'default_country_code', 'default_currency', 'default_language', 'timezone']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ['name', 'legal_entity', 'city', 'country_code', 'is_active', 'created_at']
    list_filter = ['legal_entity', 'is_active', 'country_code']
    search_fields = ['name', 'city', 'postal_code']
    readonly_fields = ['id', 'created_at', 'updated_at']
