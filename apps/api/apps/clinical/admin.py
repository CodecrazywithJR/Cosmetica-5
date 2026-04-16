from django.contrib import admin
from .models import (
    ReferralSource, Patient, PatientGuardian, PatientInsurance,
    Encounter, Appointment, AppointmentType, Treatment, PractitionerTreatment, PractitionerSchedule,
    Consent, ClinicalPhoto, EncounterPhoto, EncounterDocument, PractitionerBlock
)


@admin.register(PractitionerTreatment)
class PractitionerTreatmentAdmin(admin.ModelAdmin):
    list_display = ['practitioner', 'treatment', 'is_active', 'created_at']
    list_filter = ['treatment', 'practitioner', 'is_active']
    autocomplete_fields = ['practitioner', 'treatment']
    readonly_fields = ['id', 'created_at']


@admin.register(PractitionerSchedule)
class PractitionerScheduleAdmin(admin.ModelAdmin):
    list_display = ['practitioner', 'clinic', 'weekday', 'start_time', 'end_time', 'is_active']
    list_filter = ['clinic', 'practitioner', 'weekday', 'is_active']
    autocomplete_fields = ['practitioner', 'clinic']
    readonly_fields = ['id', 'created_at']


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

    def has_delete_permission(self, request, obj=None):
        """Patients cannot be deleted to preserve clinical history."""
        return False


@admin.register(PatientGuardian)
class PatientGuardianAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'relationship', 'patient', 'phone', 'email']
    search_fields = ['full_name', 'patient__first_name', 'patient__last_name', 'phone', 'email']
    readonly_fields = ['id', 'created_at', 'updated_at']
    autocomplete_fields = ['patient']


@admin.register(PatientInsurance)
class PatientInsuranceAdmin(admin.ModelAdmin):
    list_display = ['provider_name', 'patient', 'valid_from', 'valid_to', 'is_active']
    list_filter = ['is_active']
    search_fields = ['provider_name', 'member_number', 'patient__first_name', 'patient__last_name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    autocomplete_fields = ['patient']


@admin.register(Encounter)
class EncounterAdmin(admin.ModelAdmin):
    list_display = ['patient', 'type', 'status', 'occurred_at', 'practitioner', 'is_deleted']
    list_filter = ['type', 'status', 'is_deleted', 'occurred_at']
    search_fields = ['patient__first_name', 'patient__last_name', 'chief_complaint']
    readonly_fields = ['id', 'row_version', 'created_at', 'updated_at', 'deleted_at', 'signed_at']
    autocomplete_fields = ['patient', 'practitioner', 'clinic', 'created_by_user', 'deleted_by_user', 'signed_by_user']
    date_hierarchy = 'occurred_at'
    
    def save_model(self, request, obj, form, change):
        """
        Enforce full_clean() validation.
        
        SECURITY: Prevents admin bypass of business rules (e.g., patient-appointment coherence).
        """
        obj.full_clean()
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        """Encounters cannot be deleted to preserve clinical history."""
        return False


@admin.register(Treatment)
class TreatmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'duration_minutes', 'default_price', 'is_active', 'requires_stock']
    list_filter = ['is_active', 'requires_stock']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    list_editable = ['duration_minutes', 'default_price', 'is_active']


@admin.register(AppointmentType)
class AppointmentTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'default_duration_minutes', 'color', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['scheduled_start', 'patient', 'practitioner', 'appointment_type', 'source', 'status', 'is_deleted']
    list_filter = ['source', 'status', 'is_deleted']
    search_fields = ['patient__first_name', 'patient__last_name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'deleted_at']
    autocomplete_fields = ['patient', 'practitioner', 'clinic', 'encounter', 'treatment', 'appointment_type']
    date_hierarchy = 'scheduled_start'
    
    def get_readonly_fields(self, request, obj=None):
        """
        Make all fields readonly for terminal status appointments.
        
        SECURITY: Prevents editing completed/cancelled/no_show appointments.
        """
        readonly = list(self.readonly_fields)
        
        if obj and obj.is_terminal_status:
            # Terminal status: make everything readonly except internal notes
            return [f.name for f in self.model._meta.fields if f.name != 'notes'] + ['notes']
        
        return readonly
    
    def has_change_permission(self, request, obj=None):
        """
        Allow viewing but warn about terminal status.
        Actual field protection is in get_readonly_fields.
        """
        return super().has_change_permission(request, obj)
    
    def has_delete_permission(self, request, obj=None):
        """
        Prevent deletion of terminal status appointments.
        Only superuser can delete.
        """
        if obj and obj.is_terminal_status:
            return request.user.is_superuser
        return super().has_delete_permission(request, obj)
    
    def save_model(self, request, obj, form, change):
        """
        Enforce full_clean() validation.
        
        SECURITY: Prevents admin bypass of business rules.
        """
        obj.full_clean()  # Explicit validation
        super().save_model(request, obj, form, change)


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


@admin.register(PractitionerBlock)
class PractitionerBlockAdmin(admin.ModelAdmin):
    list_display = ['practitioner', 'kind', 'title', 'start', 'end', 'is_deleted']
    list_filter = ['kind', 'is_deleted']
    search_fields = ['practitioner__user__first_name', 'practitioner__user__last_name', 'title']
    readonly_fields = ['id', 'created_at', 'updated_at', 'deleted_at']
    autocomplete_fields = ['practitioner', 'created_by']
    date_hierarchy = 'start'
    
    fieldsets = (
        ('Block Info', {
            'fields': ('id', 'practitioner', 'kind', 'title', 'notes')
        }),
        ('Schedule', {
            'fields': ('start', 'end')
        }),
        ('Soft Delete', {
            'fields': ('is_deleted', 'deleted_at')
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """
        Enforce full_clean() validation and set created_by if new.
        
        SECURITY: Prevents admin bypass of business rules (e.g., end > start constraint).
        """
        if not change:
            obj.created_by = request.user
        obj.full_clean()
        super().save_model(request, obj, form, change)
