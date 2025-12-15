from django.contrib import admin

from .models import Encounter


@admin.register(Encounter)
class EncounterAdmin(admin.ModelAdmin):
    list_display = ['id', 'patient', 'encounter_type', 'status', 'scheduled_at', 'created_at']
    list_filter = ['status', 'encounter_type', 'scheduled_at']
    search_fields = ['patient__first_name', 'patient__last_name', 'chief_complaint']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['patient']
