from django.contrib import admin

from .models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['id', 'last_name', 'first_name', 'date_of_birth', 'phone', 'email', 'is_active', 'created_at']
    list_filter = ['is_active', 'gender', 'created_at']
    search_fields = ['first_name', 'last_name', 'phone', 'email']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = [
        ('Personal Information', {
            'fields': ['first_name', 'middle_name', 'last_name', 'date_of_birth', 'gender']
        }),
        ('Contact', {
            'fields': ['phone', 'email', 'address', 'city', 'postal_code', 'country']
        }),
        ('Medical', {
            'fields': ['blood_type', 'allergies', 'medical_history', 'current_medications']
        }),
        ('Notes', {
            'fields': ['notes']
        }),
        ('Metadata', {
            'fields': ['is_active', 'created_at', 'updated_at']
        }),
    ]
