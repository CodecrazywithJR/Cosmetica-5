from django.contrib import admin
from .models import (
    ReferralSource, Patient, PatientGuardian, Encounter, Appointment,
    Consent, ClinicalPhoto, EncounterPhoto, EncounterDocument
)


@admin.register(ReferralSource)
class ReferralSourceAdmin(admin.ModelAdmin):
    list_display = ['code', 'label', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['code', 'label']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'email', 'phone', 'is_merged', 'is_deleted', 'created_at']
    list_filter = ['sex', 'identity_confidence', 'is_merged', 'is_deleted', 'country_code']
    search_fields = ['first_name', 'last_name', 'email', 'phone', 'phone_e164', 'full_name_normalized']
    readonly_fields = ['id', 'row_version', 'created_at', 'updated_at', 'deleted_at']
    autocomplete_fields = ['merged_into_patient', 'referral_source', 'created_by_user', 'deleted_by_user']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('id', 'first_name', 'last_name', 'full_name_normalized', 'birth_date', 'sex')
        }),
        ('Contact', {
            'fields': ('email', 'phone', 'phone_e164', 'preferred_contact_method', 'preferred_contact_time', 'contact_opt_out')
        }),
        ('Address', {
            'fields': ('address_line1', 'city', 'postal_code', 'country_code')
        }),
        ('Preferences', {
            'fields': ('preferred_language', 'identity_confidence')
        }),
        ('Merge', {
            'fields': ('is_merged', 'merged_into_patient', 'merge_reason')
        }),
        ('Referral', {
            'fields': ('referral_source', 'referral_details')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Soft Delete', {
            'fields': ('is_deleted', 'deleted_at', 'deleted_by_user')
        }),
        ('Audit', {
            'fields': ('row_version', 'created_by_user', 'created_at', 'updated_at')
        }),
    )


@admin.register(PatientGuardian)
class PatientGuardianAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'relationship', 'patient', 'phone', 'email']
    search_fields = ['full_name', 'patient__first_name', 'patient__last_name', 'phone', 'email']
    readonly_fields = ['id', 'created_at', 'updated_at']
    autocomplete_fields = ['patient']


@admin.register(Encounter)
class EncounterAdmin(admin.ModelAdmin):
    list_display = ['patient', 'type', 'status', 'occurred_at', 'practitioner', 'is_deleted']
    list_filter = ['type', 'status', 'is_deleted', 'occurred_at']
    search_fields = ['patient__first_name', 'patient__last_name', 'chief_complaint']
    readonly_fields = ['id', 'row_version', 'created_at', 'updated_at', 'deleted_at', 'signed_at']
    autocomplete_fields = ['patient', 'practitioner', 'location', 'created_by_user', 'deleted_by_user', 'signed_by_user']
    date_hierarchy = 'occurred_at'


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['scheduled_start', 'patient', 'practitioner', 'source', 'status', 'is_deleted']
    list_filter = ['source', 'status', 'is_deleted']
    search_fields = ['patient__first_name', 'patient__last_name', 'external_id']
    readonly_fields = ['id', 'created_at', 'updated_at', 'deleted_at']
    autocomplete_fields = ['patient', 'practitioner', 'location', 'encounter']
    date_hierarchy = 'scheduled_start'


@admin.register(Consent)
class ConsentAdmin(admin.ModelAdmin):
    list_display = ['patient', 'consent_type', 'status', 'granted_at', 'revoked_at']
    list_filter = ['consent_type', 'status']
    search_fields = ['patient__first_name', 'patient__last_name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    autocomplete_fields = ['patient', 'document']


@admin.register(ClinicalPhoto)
class ClinicalPhotoAdmin(admin.ModelAdmin):
    list_display = ['patient', 'photo_kind', 'clinical_context', 'taken_at', 'is_deleted']
    list_filter = ['photo_kind', 'clinical_context', 'visibility', 'is_deleted']
    search_fields = ['patient__first_name', 'patient__last_name', 'object_key', 'body_area']
    readonly_fields = ['id', 'storage_bucket', 'created_at', 'updated_at', 'deleted_at']
    autocomplete_fields = ['patient', 'created_by_user', 'deleted_by_user']
    date_hierarchy = 'taken_at'


@admin.register(EncounterPhoto)
class EncounterPhotoAdmin(admin.ModelAdmin):
    list_display = ['encounter', 'photo', 'relation_type']
    list_filter = ['relation_type']
    search_fields = ['encounter__patient__first_name', 'encounter__patient__last_name']
    autocomplete_fields = ['encounter', 'photo']


@admin.register(EncounterDocument)
class EncounterDocumentAdmin(admin.ModelAdmin):
    list_display = ['encounter', 'document', 'kind']
    list_filter = ['kind']
    search_fields = ['encounter__patient__first_name', 'encounter__patient__last_name', 'document__title']
    autocomplete_fields = ['encounter', 'document']

