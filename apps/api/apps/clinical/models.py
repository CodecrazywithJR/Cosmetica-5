"""
Clinical models: patient, guardian, encounter, appointment, consent, clinical_photo, etc.
Based on DOMAIN_MODEL.md sections 3-7
"""
import uuid
from django.db import models
from django.conf import settings


# ============================================================================
# Enums
# ============================================================================

class SexChoices(models.TextChoices):
    """Patient sex/gender"""
    FEMALE = 'female', 'Female'
    MALE = 'male', 'Male'
    OTHER = 'other', 'Other'
    UNKNOWN = 'unknown', 'Unknown'


class LanguageChoices(models.TextChoices):
    """Supported languages: ru|fr|en|uk|hy|es"""
    RUSSIAN = 'ru', 'Russian'
    FRENCH = 'fr', 'French'
    ENGLISH = 'en', 'English'
    UKRAINIAN = 'uk', 'Ukrainian'
    ARMENIAN = 'hy', 'Armenian'
    SPANISH = 'es', 'Spanish'


class ContactMethodChoices(models.TextChoices):
    """Preferred contact methods"""
    PHONE_CALL = 'phone_call', 'Phone Call'
    SMS = 'sms', 'SMS'
    WHATSAPP = 'whatsapp', 'WhatsApp'
    EMAIL = 'email', 'Email'


class IdentityConfidenceChoices(models.TextChoices):
    """Patient identity confidence level"""
    LOW = 'low', 'Low'
    MEDIUM = 'medium', 'Medium'
    HIGH = 'high', 'High'


class EncounterTypeChoices(models.TextChoices):
    """Encounter types"""
    MEDICAL_CONSULT = 'medical_consult', 'Medical Consult'
    COSMETIC_CONSULT = 'cosmetic_consult', 'Cosmetic Consult'
    AESTHETIC_PROCEDURE = 'aesthetic_procedure', 'Aesthetic Procedure'
    FOLLOW_UP = 'follow_up', 'Follow-up'
    SALE_ONLY = 'sale_only', 'Sale Only'


class EncounterStatusChoices(models.TextChoices):
    """Encounter status"""
    DRAFT = 'draft', 'Draft'
    FINALIZED = 'finalized', 'Finalized'
    CANCELLED = 'cancelled', 'Cancelled'


class ConsentTypeChoices(models.TextChoices):
    """Consent types"""
    CLINICAL_PHOTOS = 'clinical_photos', 'Clinical Photos'
    MARKETING_PHOTOS = 'marketing_photos', 'Marketing Photos'
    NEWSLETTER = 'newsletter', 'Newsletter'
    MARKETING_MESSAGES = 'marketing_messages', 'Marketing Messages'


class ConsentStatusChoices(models.TextChoices):
    """Consent status"""
    GRANTED = 'granted', 'Granted'
    REVOKED = 'revoked', 'Revoked'


class PhotoKindChoices(models.TextChoices):
    """Clinical photo kind"""
    CLINICAL = 'clinical', 'Clinical'
    BEFORE = 'before', 'Before'
    AFTER = 'after', 'After'


class ClinicalContextChoices(models.TextChoices):
    """Clinical photo context"""
    BASELINE = 'baseline', 'Baseline'
    FOLLOW_UP = 'follow_up', 'Follow-up'
    POST_PROCEDURE = 'post_procedure', 'Post-procedure'
    OTHER = 'other', 'Other'


class PhotoVisibilityChoices(models.TextChoices):
    """Photo visibility (v1: only clinical_only)"""
    CLINICAL_ONLY = 'clinical_only', 'Clinical Only'


class AppointmentSourceChoices(models.TextChoices):
    """Appointment source"""
    CALENDLY = 'calendly', 'Calendly'
    MANUAL = 'manual', 'Manual'


class AppointmentStatusChoices(models.TextChoices):
    """
    Appointment status with allowed transitions:
    - draft -> confirmed | cancelled
    - confirmed -> checked_in | cancelled | no_show
    - checked_in -> completed | cancelled
    - completed, cancelled, no_show are terminal states
    """
    DRAFT = 'draft', 'Draft'
    CONFIRMED = 'confirmed', 'Confirmed'
    CHECKED_IN = 'checked_in', 'Checked In'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'
    NO_SHOW = 'no_show', 'No Show'


class AuditActionChoices(models.TextChoices):
    """Clinical audit log action types"""
    CREATE = 'create', 'Create'
    UPDATE = 'update', 'Update'
    DELETE = 'delete', 'Delete'


class AuditEntityTypeChoices(models.TextChoices):
    """Clinical entity types for audit logging"""
    ENCOUNTER = 'Encounter', 'Encounter'
    CLINICAL_PHOTO = 'ClinicalPhoto', 'Clinical Photo'
    CONSENT = 'Consent', 'Consent'
    APPOINTMENT = 'Appointment', 'Appointment'


class EncounterPhotoRelationChoices(models.TextChoices):
    """Relation type for encounter-photo link"""
    ATTACHED = 'attached', 'Attached'
    COMPARISON = 'comparison', 'Comparison'


class EncounterDocumentKindChoices(models.TextChoices):
    """Encounter document kind"""
    CONSENT_COPY = 'consent_copy', 'Consent Copy'
    LAB_RESULT = 'lab_result', 'Lab Result'
    INSTRUCTION = 'instruction', 'Instruction'
    OTHER = 'other', 'Other'


# ============================================================================
# Models
# ============================================================================

class ReferralSource(models.Model):
    """
    Referral sources (how patients found the clinic).
    
    Fields from DOMAIN_MODEL.md:
    - id: UUID PK
    - code: unique (instagram|google_maps|friend|doctor|walk_in|website|other)
    - label: string
    - is_active: bool default true
    - created_at, updated_at
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'referral_source'
        verbose_name = 'Referral Source'
        verbose_name_plural = 'Referral Sources'
        indexes = [
            models.Index(fields=['is_active'], name='idx_referral_source_active'),
        ]
    
    def __str__(self):
        return self.label


class Patient(models.Model):
    """
    Patient records with demographics, contact info, and merge support.
    
    Fields from DOMAIN_MODEL.md:
    - id: UUID PK
    - first_name, last_name, full_name_normalized nullable
    - birth_date nullable
    - sex nullable enum
    - email, phone, phone_e164 nullable
    - address fields nullable
    - preferred_language, preferred_contact_method, preferred_contact_time nullable
    - contact_opt_out bool default false
    - identity_confidence enum default low
    - is_merged bool default false
    - merged_into_patient_id FK -> patient nullable
    - merge_reason nullable
    - referral_source_id FK -> referral_source nullable
    - referral_details nullable
    - notes nullable
    - row_version int default 1
    - Soft delete fields
    - created_by_user_id FK -> auth_user nullable
    - created_at, updated_at
    
    Indices: (last_name, first_name), email, phone_e164, country_code, full_name_normalized
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Name fields
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    full_name_normalized = models.CharField(max_length=255, blank=True, null=True)
    
    # Demographics
    birth_date = models.DateField(blank=True, null=True)
    sex = models.CharField(
        max_length=20,
        choices=SexChoices.choices,
        blank=True,
        null=True
    )
    
    # Contact
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    phone_e164 = models.CharField(max_length=20, blank=True, null=True, help_text="E.164 format")
    
    # Address
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    country_code = models.CharField(max_length=2, blank=True, null=True)
    
    # Preferences
    preferred_language = models.CharField(
        max_length=2,
        choices=LanguageChoices.choices,
        blank=True,
        null=True
    )
    preferred_contact_method = models.CharField(
        max_length=20,
        choices=ContactMethodChoices.choices,
        blank=True,
        null=True
    )
    preferred_contact_time = models.CharField(max_length=255, blank=True, null=True)
    contact_opt_out = models.BooleanField(default=False)
    
    # Identity quality
    identity_confidence = models.CharField(
        max_length=10,
        choices=IdentityConfidenceChoices.choices,
        default=IdentityConfidenceChoices.LOW
    )
    
    # Merge support
    is_merged = models.BooleanField(default=False)
    merged_into_patient = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='merged_patients'
    )
    merge_reason = models.TextField(blank=True, null=True)
    
    # Marketing/referral
    referral_source = models.ForeignKey(
        'ReferralSource',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='patients'
    )
    referral_details = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    # Concurrency control
    row_version = models.IntegerField(default=1)
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='deleted_patients'
    )
    
    # Audit
    created_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='created_patients'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'patient'
        verbose_name = 'Patient'
        verbose_name_plural = 'Patients'
        indexes = [
            models.Index(fields=['last_name', 'first_name'], name='idx_patient_name'),
            models.Index(fields=['email'], name='idx_patient_email'),
            models.Index(fields=['phone_e164'], name='idx_patient_phone_e164'),
            models.Index(fields=['country_code'], name='idx_patient_country'),
            models.Index(fields=['full_name_normalized'], name='idx_patient_full_name_norm'),
            models.Index(fields=['is_deleted'], name='idx_patient_deleted'),
        ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class PatientGuardian(models.Model):
    """
    Guardians for minor patients.
    
    Fields from DOMAIN_MODEL.md:
    - id: UUID PK
    - patient_id: FK -> patient
    - full_name
    - relationship
    - phone, email nullable
    - address fields nullable
    - created_at, updated_at
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        'Patient',
        on_delete=models.CASCADE,
        related_name='guardians'
    )
    full_name = models.CharField(max_length=255)
    relationship = models.CharField(max_length=100)
    phone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    country_code = models.CharField(max_length=2, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'patient_guardian'
        verbose_name = 'Patient Guardian'
        verbose_name_plural = 'Patient Guardians'
        indexes = [
            models.Index(fields=['patient'], name='idx_guardian_patient'),
        ]
    
    def __str__(self):
        return f"{self.full_name} (Guardian of {self.patient})"


class Encounter(models.Model):
    """
    Clinical encounters (visits, consultations, procedures).
    
    Fields from DOMAIN_MODEL.md:
    - id: UUID PK
    - patient_id: FK -> patient
    - practitioner_id: FK -> practitioner nullable
    - location_id: FK -> clinic_location nullable
    - type: enum
    - status: enum
    - occurred_at: datetime
    - chief_complaint, assessment, plan, internal_notes nullable
    - signed_at nullable (not used in v1)
    - signed_by_user_id nullable (not used in v1)
    - row_version int default 1
    - Soft delete fields
    - created_by_user_id FK -> auth_user nullable
    - created_at, updated_at
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        'Patient',
        on_delete=models.CASCADE,
        related_name='encounters'
    )
    practitioner = models.ForeignKey(
        'authz.Practitioner',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='encounters'
    )
    location = models.ForeignKey(
        'core.ClinicLocation',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='encounters'
    )
    type = models.CharField(
        max_length=30,
        choices=EncounterTypeChoices.choices
    )
    status = models.CharField(
        max_length=20,
        choices=EncounterStatusChoices.choices
    )
    occurred_at = models.DateTimeField()
    chief_complaint = models.TextField(blank=True, null=True)
    assessment = models.TextField(blank=True, null=True)
    plan = models.TextField(blank=True, null=True)
    internal_notes = models.TextField(blank=True, null=True)
    
    # Future signature fields (not used in v1)
    signed_at = models.DateTimeField(blank=True, null=True)
    signed_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='signed_encounters'
    )
    
    # Concurrency control
    row_version = models.IntegerField(default=1)
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='deleted_encounters'
    )
    
    # Audit
    created_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='created_encounters'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'encounter'
        verbose_name = 'Encounter'
        verbose_name_plural = 'Encounters'
        indexes = [
            models.Index(fields=['patient'], name='idx_encounter_patient'),
            models.Index(fields=['practitioner'], name='idx_encounter_practitioner'),
            models.Index(fields=['occurred_at'], name='idx_encounter_occurred_at'),
            models.Index(fields=['status'], name='idx_encounter_status'),
            models.Index(fields=['is_deleted'], name='idx_encounter_deleted'),
        ]
    
    def __str__(self):
        return f"Encounter {self.type} - {self.patient} ({self.occurred_at.date()})"


class Appointment(models.Model):
    """
    Scheduled appointments (Calendly + manual).
    
    Fields from DOMAIN_MODEL.md:
    - id: UUID PK
    - patient_id: FK -> patient nullable
    - practitioner_id: FK -> practitioner nullable
    - location_id: FK -> clinic_location nullable
    - encounter_id: FK -> encounter nullable
    - source: enum (calendly|manual)
    - external_id: nullable unique (Calendly)
    - status: enum
    - scheduled_start, scheduled_end: datetime
    - notes nullable
    - cancellation_reason, no_show_reason nullable
    - Soft delete fields
    - created_at, updated_at
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # BUSINESS RULE: Patient is REQUIRED (no appointments without patient)
    patient = models.ForeignKey(
        'Patient',
        on_delete=models.PROTECT,  # Changed from SET_NULL - cannot delete patient with appointments
        related_name='appointments'
    )
    practitioner = models.ForeignKey(
        'authz.Practitioner',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='appointments'
    )
    location = models.ForeignKey(
        'core.ClinicLocation',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='appointments'
    )
    encounter = models.ForeignKey(
        'Encounter',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='appointments'
    )
    source = models.CharField(
        max_length=20,
        choices=AppointmentSourceChoices.choices
    )
    external_id = models.CharField(max_length=255, unique=True, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=AppointmentStatusChoices.choices
    )
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    notes = models.TextField(blank=True, null=True)
    cancellation_reason = models.TextField(blank=True, null=True)
    no_show_reason = models.TextField(blank=True, null=True)
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'appointment'
        verbose_name = 'Appointment'
        verbose_name_plural = 'Appointments'
        indexes = [
            models.Index(fields=['patient'], name='idx_appointment_patient'),
            models.Index(fields=['practitioner'], name='idx_appointment_practitioner'),
            models.Index(fields=['scheduled_start'], name='idx_appointment_start'),
            models.Index(fields=['status'], name='idx_appointment_status'),
            models.Index(fields=['external_id'], name='idx_appointment_external_id'),
            models.Index(fields=['is_deleted'], name='idx_appointment_deleted'),
        ]
    
    # BUSINESS RULE: Allowed status transitions
    _ALLOWED_TRANSITIONS = {
        'draft': ['confirmed', 'cancelled'],
        'confirmed': ['checked_in', 'cancelled', 'no_show'],
        'checked_in': ['completed', 'cancelled'],
        'completed': [],  # Terminal state
        'cancelled': [],  # Terminal state
        'no_show': [],    # Terminal state
    }
    
    # BUSINESS RULE: Active statuses that block practitioner availability
    _ACTIVE_STATUSES = ['draft', 'confirmed', 'checked_in']
    
    def __str__(self):
        return f"Appointment {self.scheduled_start.date()} - {self.patient}"
    
    def clean(self):
        """
        Model-level validation for business rules.
        
        BUSINESS RULES:
        1. Patient is required (no appointments without patient)
        2. scheduled_end must be after scheduled_start
        3. No overlapping appointments for same practitioner in active statuses
        """
        from django.core.exceptions import ValidationError
        from django.utils import timezone
        
        errors = {}
        
        # RULE 1: Patient is required
        if not self.patient_id:
            errors['patient'] = 'La cita requiere un paciente asignado'
        
        # RULE 2: Valid time range
        if self.scheduled_start and self.scheduled_end:
            if self.scheduled_end <= self.scheduled_start:
                errors['scheduled_end'] = 'La hora de fin debe ser posterior a la hora de inicio'
        
        # RULE 3: No overlaps for same practitioner (only for active statuses)
        if self.practitioner_id and self.status in self._ACTIVE_STATUSES:
            overlaps = self._check_practitioner_overlap()
            if overlaps.exists():
                errors['scheduled_start'] = (
                    f'El profesional ya tiene una cita en este horario. '
                    f'Estados que bloquean: {", ".join(self._ACTIVE_STATUSES)}'
                )
        
        if errors:
            raise ValidationError(errors)
    
    def _check_practitioner_overlap(self):
        """
        Check for overlapping appointments with same practitioner.
        
        Overlap occurs when:
        - Same practitioner
        - Status is in active statuses (draft, confirmed, checked_in)
        - Time ranges overlap: (start1 < end2) AND (start2 < end1)
        - Not soft-deleted
        - Not the current instance (for updates)
        
        Returns:
            QuerySet of overlapping appointments
        """
        from django.db.models import Q
        
        if not self.practitioner_id or not self.scheduled_start or not self.scheduled_end:
            return Appointment.objects.none()
        
        # Base query: same practitioner, active statuses, not deleted
        qs = Appointment.objects.filter(
            practitioner_id=self.practitioner_id,
            status__in=self._ACTIVE_STATUSES,
            is_deleted=False
        )
        
        # Exclude current instance if updating
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        
        # Check for time overlap: (start1 < end2) AND (start2 < end1)
        qs = qs.filter(
            Q(scheduled_start__lt=self.scheduled_end) &
            Q(scheduled_end__gt=self.scheduled_start)
        )
        
        return qs
    
    def transition_status(self, new_status, user=None, reason=None):
        """
        Transition appointment to a new status with validation.
        
        BUSINESS RULES:
        1. Only allowed transitions are permitted (see _ALLOWED_TRANSITIONS)
        2. no_show can only be set after scheduled_start has passed
        3. Terminal states cannot be changed
        
        Args:
            new_status: New status value
            user: User performing the transition (for audit)
            reason: Reason for transition (for cancellation/no_show)
        
        Returns:
            tuple: (success: bool, error_message: str | None)
        
        Raises:
            ValidationError: If transition is not allowed
        """
        from django.core.exceptions import ValidationError
        from django.utils import timezone
        
        # Check if current status allows any transitions
        allowed = self._ALLOWED_TRANSITIONS.get(self.status, [])
        if not allowed:
            raise ValidationError(
                f'El estado "{self.get_status_display()}" es terminal y no puede cambiarse'
            )
        
        # Check if transition is allowed
        if new_status not in allowed:
            raise ValidationError(
                f'Transición no permitida: {self.get_status_display()} → {self.get_status_display()}. '
                f'Transiciones válidas: {", ".join(allowed)}'
            )
        
        # RULE: no_show only after scheduled_start
        if new_status == 'no_show':
            now = timezone.now()
            if self.scheduled_start > now:
                raise ValidationError(
                    'No se puede marcar como "No Show" antes de la hora de inicio de la cita'
                )
            if reason:
                self.no_show_reason = reason
        
        # RULE: Store cancellation reason
        if new_status == 'cancelled' and reason:
            self.cancellation_reason = reason
        
        # Perform transition
        old_status = self.status
        self.status = new_status
        
        return True, None


class Consent(models.Model):
    """
    Patient consents (photos, marketing, newsletter).
    
    Fields from DOMAIN_MODEL.md:
    - id: UUID PK
    - patient_id: FK -> patient
    - consent_type: enum
    - status: enum (granted|revoked)
    - granted_at: datetime
    - revoked_at: nullable
    - document_id: FK -> document nullable
    - created_at, updated_at
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        'Patient',
        on_delete=models.CASCADE,
        related_name='consents'
    )
    consent_type = models.CharField(
        max_length=30,
        choices=ConsentTypeChoices.choices
    )
    status = models.CharField(
        max_length=20,
        choices=ConsentStatusChoices.choices
    )
    granted_at = models.DateTimeField()
    revoked_at = models.DateTimeField(blank=True, null=True)
    document = models.ForeignKey(
        'documents.Document',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='consents'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'consent'
        verbose_name = 'Consent'
        verbose_name_plural = 'Consents'
        indexes = [
            models.Index(fields=['patient'], name='idx_consent_patient'),
            models.Index(fields=['consent_type'], name='idx_consent_type'),
            models.Index(fields=['status'], name='idx_consent_status'),
        ]
    
    def __str__(self):
        return f"{self.patient} - {self.consent_type} ({self.status})"


class ClinicalPhoto(models.Model):
    """
    Clinical photos (immutable originals, can link to multiple encounters).
    
    Fields from DOMAIN_MODEL.md:
    - id: UUID PK
    - patient_id: FK -> patient
    - taken_at: nullable
    - photo_kind: enum (clinical|before|after)
    - clinical_context: nullable enum
    - body_area: nullable
    - notes: nullable
    - source_device: nullable
    - storage_bucket: fixed "clinical"
    - object_key
    - thumbnail_object_key: nullable
    - content_type
    - size_bytes
    - sha256: nullable
    - visibility: enum default clinical_only
    - Soft delete fields
    - created_by_user_id FK -> auth_user nullable
    - created_at, updated_at
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        'Patient',
        on_delete=models.CASCADE,
        related_name='clinical_photos'
    )
    taken_at = models.DateTimeField(blank=True, null=True)
    photo_kind = models.CharField(
        max_length=20,
        choices=PhotoKindChoices.choices
    )
    clinical_context = models.CharField(
        max_length=20,
        choices=ClinicalContextChoices.choices,
        blank=True,
        null=True
    )
    body_area = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    source_device = models.CharField(max_length=255, blank=True, null=True)
    
    # Storage (immutable)
    storage_bucket = models.CharField(
        max_length=64,
        default='clinical',
        editable=False
    )
    object_key = models.CharField(max_length=512)
    thumbnail_object_key = models.CharField(max_length=512, blank=True, null=True)
    content_type = models.CharField(max_length=128)
    size_bytes = models.BigIntegerField()
    sha256 = models.CharField(max_length=64, blank=True, null=True)
    
    # Visibility (v1: only clinical_only)
    visibility = models.CharField(
        max_length=20,
        choices=PhotoVisibilityChoices.choices,
        default=PhotoVisibilityChoices.CLINICAL_ONLY
    )
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='deleted_clinical_photos'
    )
    
    # Audit
    created_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='created_clinical_photos'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'clinical_photo'
        verbose_name = 'Clinical Photo'
        verbose_name_plural = 'Clinical Photos'
        indexes = [
            models.Index(fields=['patient'], name='idx_clinical_photo_patient'),
            models.Index(fields=['taken_at'], name='idx_clinical_photo_taken_at'),
            models.Index(fields=['photo_kind'], name='idx_clinical_photo_kind'),
            models.Index(fields=['is_deleted'], name='idx_clinical_photo_deleted'),
        ]
    
    def __str__(self):
        return f"Clinical Photo {self.patient} - {self.photo_kind}"


class EncounterPhoto(models.Model):
    """
    Many-to-many relationship between encounters and clinical photos.
    
    Fields from DOMAIN_MODEL.md:
    - encounter_id: FK -> encounter
    - photo_id: FK -> clinical_photo
    - relation_type: enum (attached|comparison)
    - Unique (encounter_id, photo_id)
    """
    encounter = models.ForeignKey(
        'Encounter',
        on_delete=models.CASCADE,
        related_name='encounter_photos'
    )
    photo = models.ForeignKey(
        'ClinicalPhoto',
        on_delete=models.CASCADE,
        related_name='encounter_photos'
    )
    relation_type = models.CharField(
        max_length=20,
        choices=EncounterPhotoRelationChoices.choices
    )
    
    class Meta:
        db_table = 'encounter_photo'
        verbose_name = 'Encounter Photo'
        verbose_name_plural = 'Encounter Photos'
        unique_together = [('encounter', 'photo')]
        indexes = [
            models.Index(fields=['encounter'], name='idx_encounter_photo_encounter'),
            models.Index(fields=['photo'], name='idx_encounter_photo_photo'),
        ]
    
    def __str__(self):
        return f"{self.encounter} - {self.photo} ({self.relation_type})"


class EncounterDocument(models.Model):
    """
    Many-to-many relationship between encounters and documents.
    
    Fields from DOMAIN_MODEL.md:
    - encounter_id: FK -> encounter
    - document_id: FK -> document
    - kind: enum (consent_copy|lab_result|instruction|other)
    - Unique (encounter_id, document_id)
    """
    encounter = models.ForeignKey(
        'Encounter',
        on_delete=models.CASCADE,
        related_name='encounter_documents'
    )
    document = models.ForeignKey(
        'documents.Document',
        on_delete=models.CASCADE,
        related_name='encounter_documents'
    )
    kind = models.CharField(
        max_length=20,
        choices=EncounterDocumentKindChoices.choices
    )
    
    class Meta:
        db_table = 'encounter_document'
        verbose_name = 'Encounter Document'
        verbose_name_plural = 'Encounter Documents'
        unique_together = [('encounter', 'document')]
        indexes = [
            models.Index(fields=['encounter'], name='idx_encounter_doc_encounter'),
            models.Index(fields=['document'], name='idx_encounter_doc_document'),
        ]
    
    def __str__(self):
        return f"{self.encounter} - {self.document} ({self.kind})"


class ClinicalAuditLog(models.Model):
    """
    Lightweight audit trail for clinical entity changes.
    
    BUSINESS RULE: Maintains traceability of clinical changes without locking.
    Tracks who changed what and when for Encounter, ClinicalPhoto, Consent, etc.
    
    Fields:
    - id: UUID PK
    - created_at: timestamp of action
    - actor_user: who made the change (nullable for system actions)
    - action: create|update|delete
    - entity_type: type of entity changed
    - entity_id: UUID of the entity
    - patient: related patient (for easier querying)
    - appointment: related appointment (if applicable)
    - metadata: JSON with changed_fields, before/after snapshots, request info
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='clinical_audit_logs',
        help_text='User who performed the action (null for system actions)'
    )
    
    action = models.CharField(
        max_length=10,
        choices=AuditActionChoices.choices
    )
    
    entity_type = models.CharField(
        max_length=50,
        choices=AuditEntityTypeChoices.choices,
        help_text='Type of clinical entity (Encounter, ClinicalPhoto, etc.)'
    )
    
    entity_id = models.UUIDField(
        help_text='UUID of the entity that was changed'
    )
    
    # Optional related entities for easier querying
    patient = models.ForeignKey(
        'Patient',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='audit_logs',
        help_text='Related patient (if applicable)'
    )
    
    appointment = models.ForeignKey(
        'Appointment',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='audit_logs',
        help_text='Related appointment (if applicable)'
    )
    
    metadata = models.JSONField(
        default=dict,
        help_text='Changed fields, before/after snapshots, request metadata'
    )
    
    class Meta:
        db_table = 'clinical_audit_log'
        verbose_name = 'Clinical Audit Log'
        verbose_name_plural = 'Clinical Audit Logs'
        indexes = [
            models.Index(fields=['created_at'], name='idx_audit_created_at'),
            models.Index(fields=['actor_user'], name='idx_audit_actor'),
            models.Index(fields=['entity_type'], name='idx_audit_entity_type'),
            models.Index(fields=['entity_id'], name='idx_audit_entity_id'),
            models.Index(fields=['patient'], name='idx_audit_patient'),
            models.Index(fields=['action'], name='idx_audit_action'),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        actor = self.actor_user.email if self.actor_user else 'system'
        return f"{self.action} on {self.entity_type}[{str(self.entity_id)[:8]}] by {actor}"


# ============================================================================
# Audit Helper Functions
# ============================================================================

def log_clinical_audit(
    actor,
    instance,
    action,
    before=None,
    after=None,
    changed_fields=None,
    patient=None,
    appointment=None,
    request=None
):
    """
    Helper function to create clinical audit log entries.
    
    Args:
        actor: User instance or None for system actions
        instance: The clinical entity instance being audited
        action: 'create'|'update'|'delete'
        before: Dict of field values before change (for updates)
        after: Dict of field values after change (for updates)
        changed_fields: List of field names that changed
        patient: Patient instance (optional, can be inferred from instance)
        appointment: Appointment instance (optional)
        request: Django request object (to capture IP/user-agent)
    
    Returns:
        ClinicalAuditLog instance
    """
    # Determine entity type from instance
    entity_type_map = {
        'Encounter': AuditEntityTypeChoices.ENCOUNTER,
        'ClinicalPhoto': AuditEntityTypeChoices.CLINICAL_PHOTO,
        'Consent': AuditEntityTypeChoices.CONSENT,
        'Appointment': AuditEntityTypeChoices.APPOINTMENT,
    }
    
    entity_type = entity_type_map.get(
        instance.__class__.__name__,
        instance.__class__.__name__
    )
    
    # Try to infer patient from instance if not provided
    if not patient and hasattr(instance, 'patient'):
        patient = instance.patient
    
    # Build metadata
    metadata = {}
    
    if changed_fields:
        metadata['changed_fields'] = changed_fields
    
    if before:
        metadata['before'] = before
    
    if after:
        metadata['after'] = after
    
    # Capture request metadata if available
    if request:
        metadata['request'] = {
            'ip': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
        }
    
    # Create audit log
    audit_log = ClinicalAuditLog.objects.create(
        actor_user=actor,
        action=action,
        entity_type=entity_type,
        entity_id=instance.pk,
        patient=patient,
        appointment=appointment,
        metadata=metadata
    )
    
    return audit_log

