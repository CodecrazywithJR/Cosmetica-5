"""
Clinical models: patient, guardian, encounter, appointment, consent, clinical_photo, etc.
Based on DOMAIN_MODEL.md sections 3-7
"""
import uuid
from django.db import models
from django.conf import settings

from apps.core.tenant_model import TenantModel
from apps.core.managers import TenantManager

# Re-export so Django discovers the model via this module
from apps.clinical.audit_access_log import ClinicalAccessLog, ClinicalAccessAction  # noqa: F401

# FK reference constants (avoid S1192 duplicate literals)
FK_PRACTITIONER = 'authz.Practitioner'
FK_CLINIC = 'core.Clinic'


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


class DocumentTypeChoices(models.TextChoices):
    """Patient official document types"""
    DNI = 'dni', 'DNI/ID Card'
    PASSPORT = 'passport', 'Passport'
    OTHER = 'other', 'Other'


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
    PRIVACY_POLICY = 'privacy_policy', 'Privacy Policy'
    TERMS_AND_CONDITIONS = 'terms_and_conditions', 'Terms and Conditions'
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
    """Appointment source (how the appointment was booked)"""
    ERP = 'erp', 'ERP'
    PUBLIC_API = 'public_api', 'Public API'
    MANUAL = 'manual', 'Manual'


# ProposalStatusChoices moved to apps.proposals.models
from apps.proposals.models import ProposalStatusChoices  # noqa: F401 — backward compat


class AppointmentStatusChoices(models.TextChoices):
    """
    Appointment status with allowed transitions:
    - scheduled -> confirmed | cancelled | no_show
    - confirmed -> checked_in
    - checked_in -> completed
    - completed, cancelled, no_show are terminal states
    """
    SCHEDULED = 'scheduled', 'Scheduled'
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


class PractitionerBlockKindChoices(models.TextChoices):
    """Practitioner calendar block types"""
    VACATION = 'vacation', 'Vacation'
    BLOCKED = 'blocked', 'Blocked/Unavailable'
    PERSONAL = 'personal', 'Personal Time'
    TRAINING = 'training', 'Training'


# ============================================================================
# Models
# ============================================================================

class ReferralSource(TenantModel):
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


# ============================================================================
# Patient soft-delete queryset and manager
# ============================================================================

class PatientQuerySet(models.QuerySet):
    """QuerySet helpers for Patient live/deleted subsets."""

    def alive(self):
        """Return only non-deleted patients."""
        return self.filter(is_deleted=False)

    def deleted(self):
        """Return only soft-deleted patients."""
        return self.filter(is_deleted=True)


class PatientManager(TenantManager):
    """
    Default manager for Patient.

    Combines:
      1. Tenant isolation (inherited from TenantManager via legal_entity filter).
      2. Soft-delete exclusion — is_deleted=False records only.

    Use Patient.unfiltered for admin/data-migration access to all rows.
    """

    def get_queryset(self):
        from apps.core.tenant_context import get_current_tenant
        qs = PatientQuerySet(self.model, using=self._db).filter(is_deleted=False)
        tenant = get_current_tenant()
        if tenant is not None:
            return qs.filter(legal_entity=tenant)
        return qs


class Patient(TenantModel):
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
    
    # Official identification
    document_type = models.CharField(
        max_length=20,
        choices=DocumentTypeChoices.choices,
        blank=True,
        null=True
    )
    document_number = models.CharField(max_length=100, blank=True, null=True)
    nationality = models.CharField(max_length=100, blank=True, null=True)
    
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
    
    # Medical fields (unified from legacy patients app)
    blood_type = models.CharField(max_length=8, blank=True, null=True)
    allergies = models.TextField(blank=True, default="")
    medical_history = models.TextField(blank=True, default="")
    current_medications = models.TextField(blank=True, default="")
    
    # Emergency contact
    emergency_contact_name = models.CharField(max_length=255, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=50, blank=True, null=True)
    
    # Legal consents (quick flags - complement to Consent model)
    privacy_policy_accepted = models.BooleanField(default=False)
    privacy_policy_accepted_at = models.DateTimeField(blank=True, null=True)
    terms_accepted = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(blank=True, null=True)
    
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
    
    # Managers — override TenantModel defaults
    objects = PatientManager()
    unfiltered = models.Manager()

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
            models.Index(fields=['is_merged'], name='idx_patient_merged'),
            models.Index(fields=['merged_into_patient'], name='idx_patient_merge_target'),
        ]
        constraints = [
            # Prevent self-merge
            models.CheckConstraint(
                check=~models.Q(merged_into_patient=models.F('id')),
                name='patient_no_self_merge'
            ),
            # If merged, must have target
            models.CheckConstraint(
                check=models.Q(is_merged=False) | models.Q(merged_into_patient__isnull=False),
                name='patient_merged_requires_target'
            ),
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


# ============================================================================
# Patient Insurance
# ============================================================================

class PatientInsurance(models.Model):
    """
    Historical record of a patient's medical insurance coverage.

    Business rules:
    - R1: Only one active coverage per patient (enforced by DB constraint).
    - R2: No overlapping date ranges per patient.
    - R3: When creating a new active coverage, automatically close the
           previous active one (valid_to = new.valid_from - 1 day, is_active=False).
    - R4: valid_from is required.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        'Patient',
        on_delete=models.CASCADE,
        related_name='insurances',
    )
    provider_name = models.CharField(max_length=255)
    member_number = models.CharField(max_length=255, null=True, blank=True)
    social_security_number = models.CharField(max_length=255, null=True, blank=True)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'patient_insurance'
        verbose_name = 'Patient Insurance'
        verbose_name_plural = 'Patient Insurances'
        ordering = ['-valid_from']
        indexes = [
            models.Index(fields=['patient'], name='idx_insurance_patient'),
            models.Index(fields=['is_active'], name='idx_insurance_active'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['patient'],
                condition=models.Q(is_active=True),
                name='unique_active_insurance_per_patient',
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError as DjangoValidationError

        if self.valid_to and self.valid_from and self.valid_to < self.valid_from:
            raise DjangoValidationError(
                {'valid_to': 'valid_to cannot be before valid_from.'}
            )

    def __str__(self):
        status = 'Active' if self.is_active else 'Inactive'
        return f"{self.provider_name} ({status}) — {self.patient}"


class PatientMergeLog(models.Model):
    """
    Audit log for patient merge operations.
    
    Tracks when patients are merged for deduplication,
    maintaining full traceability of the merge operation.
    
    Fields:
    - source_patient: The duplicate patient being merged (deactivated)
    - target_patient: The canonical patient (kept active)
    - merged_by_user: Who performed the merge
    - merged_at: When the merge occurred
    - strategy: How the duplicate was detected/matched
    - evidence: JSON with match details (sanitized, no PHI)
    - notes: Free-text explanation
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    source_patient = models.ForeignKey(
        'Patient',
        on_delete=models.PROTECT,  # Never delete merge logs
        related_name='merge_source_logs',
        help_text='Patient being merged (becomes inactive)'
    )
    target_patient = models.ForeignKey(
        'Patient',
        on_delete=models.PROTECT,
        related_name='merge_target_logs',
        help_text='Patient receiving merged data (remains active)'
    )
    
    merged_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='patient_merges_performed',
        help_text='User who performed the merge'
    )
    
    merged_at = models.DateTimeField(auto_now_add=True)
    
    # Match strategy
    STRATEGY_CHOICES = [
        ('phone_exact', 'Phone Exact Match'),
        ('email_exact', 'Email Exact Match'),
        ('name_trgm', 'Name Trigram Similarity'),
        ('manual', 'Manual Merge'),
        ('other', 'Other'),
    ]
    strategy = models.CharField(
        max_length=20,
        choices=STRATEGY_CHOICES,
        default='manual',
        help_text='How the duplicate was identified'
    )
    
    # Evidence (sanitized JSON - no medical fields)
    evidence = models.JSONField(
        blank=True,
        null=True,
        help_text='Match evidence (sanitized): phone_masked, email_masked, similarity_score, etc.'
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        help_text='Free-text explanation of merge reason'
    )
    
    class Meta:
        db_table = 'patient_merge_log'
        verbose_name = 'Patient Merge Log'
        verbose_name_plural = 'Patient Merge Logs'
        ordering = ['-merged_at']
        indexes = [
            models.Index(fields=['source_patient'], name='idx_merge_source'),
            models.Index(fields=['target_patient'], name='idx_merge_target'),
            models.Index(fields=['-merged_at'], name='idx_merge_date'),
        ]
    
    def __str__(self):
        return f"Merge: {self.source_patient} → {self.target_patient} ({self.merged_at.date()})"


# ============================================================================
# Encounter soft-delete queryset and manager
# ============================================================================

class EncounterQuerySet(models.QuerySet):
    """QuerySet helpers for Encounter live/deleted subsets."""

    def alive(self):
        """Return only non-deleted encounters."""
        return self.filter(is_deleted=False)

    def deleted(self):
        """Return only soft-deleted encounters."""
        return self.filter(is_deleted=True)


class EncounterManager(TenantManager):
    """
    Default manager for Encounter.

    Combines:
      1. Tenant isolation (inherited from TenantManager via legal_entity filter).
      2. Soft-delete exclusion — is_deleted=False records only.

    Use Encounter.unfiltered for state-machine guard checks and data migrations.
    """

    def get_queryset(self):
        from apps.core.tenant_context import get_current_tenant
        qs = EncounterQuerySet(self.model, using=self._db).filter(is_deleted=False)
        tenant = get_current_tenant()
        if tenant is not None:
            return qs.filter(legal_entity=tenant)
        return qs


class Encounter(TenantModel):
    """
    Clinical encounters (visits, consultations, procedures).
    
    Fields from DOMAIN_MODEL.md:
    - id: UUID PK
    - patient_id: FK -> patient
    - practitioner_id: FK -> practitioner nullable
    - clinic_id: FK -> clinic nullable
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
        on_delete=models.PROTECT,
        related_name='encounters'
    )
    practitioner = models.ForeignKey(
        FK_PRACTITIONER,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='encounters'
    )
    clinic = models.ForeignKey(
        FK_CLINIC,
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
    # Attachments summary cache fields (v1.1)
    photo_count_cached = models.IntegerField(default=0)
    document_count_cached = models.IntegerField(default=0)
    has_photos_cached = models.BooleanField(default=False)
    has_documents_cached = models.BooleanField(default=False)
    
    # Managers — override TenantModel defaults
    objects = EncounterManager()
    unfiltered = models.Manager()

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
            # Timeline index: ordered by patient and creation date
            models.Index(fields=['patient', '-created_at'], name='idx_encounter_patient_timeline'),
        ]
    
    def __str__(self):
        return f"Encounter {self.type} - {self.patient} ({self.occurred_at.date()})"
    
    def clean(self):
        """
        Validate clinical domain invariants.
        """
        from django.core.exceptions import ValidationError
        
        super().clean()
        
        # INVARIANT: Patient is required (already enforced by FK NOT NULL)
        if not self.patient_id:
            raise ValidationError({
                'patient': 'Encounter must have a patient assigned.'
            })

    def save(self, *args, **kwargs):
        """
        Enforce encounter status transition machine.

        Allowed transitions (from → to):
            draft → finalized
            draft → cancelled

        finalized and cancelled are terminal states.

        Pass skip_validation=True to bypass the check (test fixtures only).
        Pass update_fields=[...] without 'status' to save other fields on a
        terminal encounter without triggering the transition guard.
        """
        skip_validation = kwargs.pop('skip_validation', False)
        if not skip_validation and not self._state.adding and self.pk:
            self._validate_status_transition(kwargs.get('update_fields'))
        super().save(*args, **kwargs)

    def _validate_status_transition(self, update_fields):
        """Guard against invalid status transitions."""
        if update_fields is not None and 'status' not in update_fields:
            return
        _old = (
            Encounter.unfiltered
            .filter(pk=self.pk)
            .values('status')
            .first()
        )
        if not _old or _old['status'] == self.status:
            return
        _ALLOWED = {
            EncounterStatusChoices.DRAFT: {
                EncounterStatusChoices.FINALIZED,
                EncounterStatusChoices.CANCELLED,
            },
        }
        valid_next = _ALLOWED.get(_old['status'], set())
        if self.status not in valid_next:
            from django.core.exceptions import ValidationError as DjangoValidationError
            raise DjangoValidationError({
                'status': (
                    f"Invalid encounter status transition from "
                    f"'{_old['status']}' to '{self.status}'. "
                    f"Allowed from '{_old['status']}': "
                    f"{sorted(valid_next) if valid_next else 'none (terminal state)'}."
                )
            })


# ============================================================================
# AppointmentType
# ============================================================================

class AppointmentType(TenantModel):
    """
    Catalog of appointment types.

    Examples: INITIAL_CONSULT, FOLLOW_UP, TREATMENT_SESSION, CHECKUP,
    EMERGENCY, ESTHETIC_EVALUATION.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    default_duration_minutes = models.PositiveIntegerField(default=30)
    color = models.CharField(max_length=20, blank=True, default='#3B82F6')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'appointment_type'
        verbose_name = 'Appointment Type'
        verbose_name_plural = 'Appointment Types'
        constraints = [
            models.UniqueConstraint(
                fields=['legal_entity', 'name'],
                name='unique_appointment_type_name_per_tenant',
            ),
        ]
        indexes = [
            models.Index(fields=['is_active'], name='idx_apt_type_active'),
        ]

    def __str__(self):
        return self.name


class AppointmentQuerySet(models.QuerySet):
    """QuerySet helpers for Appointment live/deleted subsets."""

    def alive(self):
        """Return only non-deleted appointments."""
        return self.filter(is_deleted=False)

    def deleted(self):
        """Return only soft-deleted appointments."""
        return self.filter(is_deleted=True)


class AppointmentManager(TenantManager):
    """
    Default manager for Appointment.

    Combines:
      1. Tenant isolation (inherited from TenantManager via legal_entity filter).
      2. Soft-delete exclusion — is_deleted=False records only.

    Use Appointment.unfiltered for admin access to all rows (e.g. include_deleted).
    """

    def get_queryset(self):
        from apps.core.tenant_context import get_current_tenant
        qs = AppointmentQuerySet(self.model, using=self._db).filter(is_deleted=False)
        tenant = get_current_tenant()
        if tenant is not None:
            return qs.filter(legal_entity=tenant)
        return qs


class Appointment(TenantModel):
    """
    Scheduled appointments — ERP is the sole scheduling engine.

    State machine:
        scheduled → confirmed | cancelled | no_show
        confirmed → checked_in | cancelled | no_show
        checked_in → completed
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    patient = models.ForeignKey(
        'Patient',
        on_delete=models.PROTECT,
        related_name='appointments',
    )
    practitioner = models.ForeignKey(
        FK_PRACTITIONER,
        on_delete=models.PROTECT,
        related_name='appointments',
    )
    clinic = models.ForeignKey(
        FK_CLINIC,
        on_delete=models.PROTECT,
        related_name='appointments',
        null=True,
        blank=True,
    )
    appointment_type = models.ForeignKey(
        'AppointmentType',
        on_delete=models.PROTECT,
        related_name='appointments',
        null=True,
        blank=True,
    )
    encounter = models.ForeignKey(
        'Encounter',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='appointments',
    )
    treatment_plan = models.ForeignKey(
        'treatment_plans.TreatmentPlan',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='appointments',
        help_text='Treatment plan this appointment belongs to (package sessions)',
    )
    treatment = models.ForeignKey(
        'Treatment',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='appointments',
        help_text='Treatment expected for this appointment',
    )
    source = models.CharField(
        max_length=20,
        choices=AppointmentSourceChoices.choices,
        default=AppointmentSourceChoices.ERP,
    )
    status = models.CharField(
        max_length=20,
        choices=AppointmentStatusChoices.choices,
        default=AppointmentStatusChoices.SCHEDULED,
    )
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    duration_planned = models.PositiveIntegerField(
        help_text='Planned duration in minutes',
        default=30,
    )
    duration_real = models.PositiveIntegerField(
        help_text='Actual duration in minutes (filled on completion)',
        blank=True,
        null=True,
    )
    notes = models.TextField(blank=True, null=True)
    cancellation_reason = models.TextField(blank=True, null=True)
    no_show_reason = models.TextField(blank=True, null=True)

    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='deleted_appointments',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Managers — override TenantModel defaults
    objects = AppointmentManager()
    unfiltered = models.Manager()

    class Meta:
        db_table = 'appointment'
        verbose_name = 'Appointment'
        verbose_name_plural = 'Appointments'
        indexes = [
            models.Index(fields=['patient'], name='idx_appointment_patient'),
            models.Index(fields=['practitioner'], name='idx_appointment_practitioner'),
            models.Index(fields=['scheduled_start'], name='idx_appointment_start'),
            models.Index(fields=['status'], name='idx_appointment_status'),
            models.Index(fields=['clinic'], name='idx_appointment_clinic'),
            models.Index(fields=['is_deleted'], name='idx_appointment_deleted'),
        ]
        # Database-level overbooking protection (GiST exclusion constraint).
        # Managed via RunSQL in migration 0116 because it uses tstzrange()
        # on plain DateTimeField columns (not Django RangeField).
        # Constraint name: prevent_practitioner_overbooking
        # Condition: same practitioner + overlapping time range +
        #            status IN (scheduled, confirmed, checked_in) + is_deleted=false
    
    # BUSINESS RULE: Allowed status transitions
    _ALLOWED_TRANSITIONS = {
        'scheduled': ['confirmed', 'cancelled', 'no_show'],
        'confirmed': ['checked_in', 'cancelled', 'no_show'],
        'checked_in': ['completed'],
        'completed': [],  # Terminal state
        'cancelled': [],  # Terminal state
        'no_show': [],    # Terminal state
    }

    # BUSINESS RULE: Active statuses that block practitioner availability
    _ACTIVE_STATUSES = ['scheduled', 'confirmed', 'checked_in']
    
    def __str__(self):
        return f"Appointment {self.scheduled_start.date()} - {self.patient}"
    
    def save(self, *args, **kwargs):
        """
        Override save to enforce full_clean() validation.

        - Auto-compute duration_planned from treatment or appointment_type.
        - Treatment-plan hooks on create/completion.
        """
        # Skip validation during migrations (when loading fixtures)
        skip_validation = kwargs.pop('skip_validation', False)

        self._compute_duration()

        if not skip_validation:
            self.full_clean()

        is_new = self._state.adding
        old_status = self._get_old_status()

        super().save(*args, **kwargs)

        self._handle_treatment_plan_effects(is_new, old_status)

    def _compute_duration(self):
        """Duration rule: treatment.duration_minutes → appointment_type.default_duration_minutes → 30."""
        if not (self._state.adding or not self.duration_planned):
            return
        if self.treatment_id:
            try:
                self.duration_planned = self.treatment.duration_minutes
            except Exception:
                pass
        elif self.appointment_type_id:
            try:
                self.duration_planned = self.appointment_type.default_duration_minutes
            except Exception:
                pass

    def _get_old_status(self):
        """Capture old status for completion tracking."""
        if self._state.adding or not self.pk:
            return None
        return (
            Appointment.objects
            .filter(pk=self.pk)
            .values_list('status', flat=True)
            .first()
        )

    def _handle_treatment_plan_effects(self, is_new, old_status):
        """Treatment-plan side-effects (post-save)."""
        if not self.treatment_plan_id:
            return
        if is_new:
            self.treatment_plan.activate()
        if (
            old_status
            and old_status != AppointmentStatusChoices.COMPLETED
            and self.status == AppointmentStatusChoices.COMPLETED
        ):
            self.treatment_plan.record_session_completed()
    
    @property
    def is_terminal_status(self):
        """Check if appointment is in a terminal state (immutable)."""
        return self.status in ['completed', 'cancelled', 'no_show']
    
    def clean(self):
        """
        Model-level validation for business rules.

        BUSINESS RULES:
        1. Patient is required
        2. scheduled_end must be after scheduled_start
        3. No overlapping appointments for same practitioner
        4. treatment_plan requires treatment
        5. treatment_plan.proposal_line.treatment must equal treatment
        6. Duration rule: treatment.duration_minutes or appointment_type.default_duration_minutes
        """
        from django.core.exceptions import ValidationError

        errors = {}

        # RULE 1: Patient is required
        if not self.patient_id:
            errors['patient'] = 'La cita requiere un paciente asignado'

        # RULE 2: Valid time range
        if self.scheduled_start and self.scheduled_end and self.scheduled_end <= self.scheduled_start:
            errors['scheduled_end'] = 'La hora de fin debe ser posterior a la hora de inicio'

        # RULE 3: No overlaps for same practitioner (only for active statuses)
        if self.practitioner_id and self.status in self._ACTIVE_STATUSES:
            overlaps = self._check_practitioner_overlap()
            if overlaps.exists():
                errors['scheduled_start'] = (
                    f'El profesional ya tiene una cita en este horario. '
                    f'Estados que bloquean: {", ".join(self._ACTIVE_STATUSES)}'
                )

        # RULE 4: treatment_plan requires treatment
        if self.treatment_plan_id and not self.treatment_id:
            errors['treatment'] = 'Un plan de tratamiento requiere un tratamiento asignado'

        # RULE 5: treatment_plan.proposal_line.treatment must equal appointment treatment
        self._validate_treatment_plan_match(errors)

        if errors:
            raise ValidationError(errors)

    def _validate_treatment_plan_match(self, errors):
        """RULE 5: treatment_plan.proposal_line.treatment must equal appointment treatment."""
        if not (self.treatment_plan_id and self.treatment_id):
            return
        try:
            plan_treatment_id = self.treatment_plan.proposal_line.treatment_id
            if plan_treatment_id and plan_treatment_id != self.treatment_id:
                errors['treatment'] = (
                    'El tratamiento de la cita no coincide con el del plan de tratamiento'
                )
        except Exception:
            pass  # plan or proposal_line not loaded yet, skip cross-check
    
    def _check_practitioner_overlap(self):
        """
        Application-level overlap check (early validation layer).

        This runs BEFORE save() to provide user-friendly error messages.
        The database ExclusionConstraint 'prevent_practitioner_overbooking'
        is the final safety net against race conditions.

        Overlap occurs when:
        - Same practitioner
        - Status is in active statuses (scheduled, confirmed, checked_in)
        - Time ranges overlap: (start1 < end2) AND (start2 < end1)
        - Not soft-deleted
        - Not the current instance (for updates)
        
        Returns:
            QuerySet of overlapping appointments
        """
        from django.db.models import Q
        
        if not self.practitioner_id or not self.scheduled_start or not self.scheduled_end:
            return Appointment.objects.none()
        
        # Base query: same practitioner, same tenant, active statuses, not deleted.
        # IMPORTANT: use Appointment.unfiltered + explicit legal_entity filter so this
        # method is safe when called from Celery tasks or signal handlers where
        # get_current_tenant() may return None.  Scoping through self.legal_entity
        # guarantees the overlap check never reads across tenant boundaries.
        qs = Appointment.unfiltered.filter(
            practitioner_id=self.practitioner_id,
            legal_entity=self.legal_entity,
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

        Auto-creates an Encounter when transitioning to checked_in (max 1).

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
                f'Transición no permitida: {self.status} → {new_status}. '
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

        self.status = new_status

        # Auto-create encounter on checked_in (max 1 per appointment)
        if new_status == AppointmentStatusChoices.CHECKED_IN and not self.encounter_id:
            encounter = Encounter(
                legal_entity=self.legal_entity,
                patient=self.patient,
                practitioner=self.practitioner,
                clinic=self.clinic,
                type=EncounterTypeChoices.COSMETIC_CONSULT,
                status=EncounterStatusChoices.DRAFT,
                occurred_at=timezone.now(),
            )
            encounter.save(skip_validation=True)
            self.encounter = encounter

        return True, None


class Consent(TenantModel):
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


class ClinicalPhoto(TenantModel):
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
            # Timeline index: ordered by patient and creation date
            models.Index(fields=['patient', '-created_at'], name='idx_clin_photo_timeline'),
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
    
    # Capture request metadata if available (anonymized for privacy)
    if request:
        # Anonymize IP: keep first 3 octets, mask last one (e.g., 192.168.1.xxx)
        ip = request.META.get('REMOTE_ADDR', '')
        if ip and '.' in ip:
            parts = ip.split('.')
            if len(parts) == 4:
                ip = f"{parts[0]}.{parts[1]}.{parts[2]}.xxx"
        
        metadata['request'] = {
            'ip': ip,
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:100],  # Truncate to 100 chars
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


# ============================================================================
# Clinical Core v1: Treatment Catalog + Encounter-Treatment Linking
# ============================================================================

class Treatment(TenantModel):
    """
    Treatment/Procedure catalog (master list of services).
    
    Purpose:
    - Central catalog of all available treatments/procedures
    - Referenced by EncounterTreatment to link encounters to treatments
    - Stores default pricing and stock requirements
    
    Fields:
    - id: UUID PK
    - name: string (max_length=255)
    - description: text nullable
    - is_active: bool default true (soft disable treatments)
    - default_price: decimal(10,2) nullable (in EUR)
    - requires_stock: bool default false (if true, check stock availability)
    - created_at, updated_at
    
    Examples:
    - "Botox Injection", "Hyaluronic Acid Filler", "Chemical Peel"
    - "Consultation - Dermatology", "Follow-up Visit"
    
    BUSINESS RULES:
    - Cannot delete treatments with encounter references (PROTECT)
    - Can soft-disable via is_active=false
    - default_price is nullable (manual pricing at encounter level)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    default_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text='Default price in EUR (nullable for flexible pricing)'
    )
    requires_stock = models.BooleanField(
        default=False,
        help_text='If true, check stock availability before booking'
    )
    duration_minutes = models.PositiveIntegerField(
        default=30,
        help_text='Standard duration of the treatment in minutes',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'treatment'
        verbose_name = 'Treatment'
        verbose_name_plural = 'Treatments'
        indexes = [
            models.Index(fields=['is_active'], name='idx_treatment_active'),
            models.Index(fields=['name'], name='idx_treatment_name'),
        ]
        ordering = ['name']
    
    def __str__(self):
        return self.name


class EncounterTreatment(models.Model):
    """
    Link table: Encounter <-> Treatment (many-to-many with metadata).
    
    Purpose:
    - Records which treatments were performed during an encounter
    - Stores quantity, unit price, and notes per treatment
    - Supports multiple treatments per encounter
    
    Fields:
    - id: UUID PK
    - encounter_id: FK -> encounter (CASCADE)
    - treatment_id: FK -> treatment (PROTECT)
    - quantity: int default 1 (e.g., 3 vials of filler)
    - unit_price: decimal(10,2) nullable (overrides Treatment.default_price)
    - notes: text nullable (e.g., "Applied to nasolabial folds")
    - created_at, updated_at
    
    BUSINESS RULES:
    - Quantity must be >= 1
    - Cannot delete treatments if referenced by encounters (PROTECT)
    - Can delete encounters (CASCADE deletes links)
    - unit_price nullable (falls back to Treatment.default_price)
    
    Example:
    Encounter #123 → [
        (Botox, qty=2, unit_price=350.00, notes="Forehead + glabella"),
        (Consultation, qty=1, unit_price=100.00, notes="Initial assessment")
    ]
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.ForeignKey(
        'Encounter',
        on_delete=models.CASCADE,
        related_name='encounter_treatments'
    )
    treatment = models.ForeignKey(
        'Treatment',
        on_delete=models.PROTECT,
        related_name='encounter_treatments'
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text='Overrides Treatment.default_price (nullable)'
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'encounter_treatment'
        verbose_name = 'Encounter Treatment'
        verbose_name_plural = 'Encounter Treatments'
        indexes = [
            models.Index(fields=['encounter'], name='idx_encounter_treatment_enc'),
            models.Index(fields=['treatment'], name='idx_encounter_treatment_trt'),
        ]
        unique_together = [['encounter', 'treatment']]  # Prevent duplicate treatments per encounter
    
    def __str__(self):
        return f"{self.encounter} - {self.treatment} (x{self.quantity})"
    
    @property
    def effective_price(self):
        """Return unit_price if set, else Treatment.default_price."""
        return self.unit_price if self.unit_price is not None else self.treatment.default_price
    
    @property
    def total_price(self):
        """Calculate total price: quantity * effective_price."""
        if self.effective_price is None:
            return None
        return self.quantity * self.effective_price


# ============================================================================
# Clinical → Sales Integration (Fase 3)
# Models moved to apps.proposals.models — backward-compatible imports below
# ============================================================================
from apps.proposals.models import Proposal as ClinicalChargeProposal  # noqa: F401
from apps.proposals.models import ProposalLine as ClinicalChargeProposalLine  # noqa: F401


class PractitionerBlock(TenantModel):
    """
    Calendar blocks for practitioners (vacations, unavailability, etc).
    Used to mark time ranges when a practitioner is NOT available for appointments.
    
    Sprint 1 - Agenda feature
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # FK
    practitioner = models.ForeignKey(
        FK_PRACTITIONER,
        on_delete=models.CASCADE,
        related_name='calendar_blocks'
    )
    
    # Time range
    start = models.DateTimeField(
        help_text='Block start time (timezone-aware)'
    )
    end = models.DateTimeField(
        help_text='Block end time (timezone-aware)'
    )
    
    # Kind and details
    kind = models.CharField(
        max_length=20,
        choices=PractitionerBlockKindChoices.choices,
        default=PractitionerBlockKindChoices.BLOCKED
    )
    title = models.CharField(
        max_length=255,
        help_text='Display title (e.g., "Vacaciones", "No disponible")'
    )
    notes = models.TextField(blank=True, default='')
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_practitioner_blocks'
    )
    
    class Meta:
        db_table = 'practitioner_blocks'
        verbose_name = 'Practitioner Block'
        verbose_name_plural = 'Practitioner Blocks'
        ordering = ['start']
        indexes = [
            models.Index(fields=['practitioner', 'start'], name='idx_block_pract_start'),
            models.Index(fields=['practitioner', 'is_deleted'], name='idx_block_pract_deleted'),
            models.Index(fields=['start', 'end'], name='idx_block_time_range'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(end__gt=models.F('start')),
                name='block_end_after_start'
            ),
        ]
    
    def __str__(self):
        return f"{self.practitioner.display_name}: {self.title} ({self.start.date()} - {self.end.date()})"


# ============================================================================
# ClinicalMedia Model (moved from apps.encounters)
# ============================================================================

def clinical_media_upload_path(instance, filename):
    """
    Generate secure upload path for clinical media.
    Pattern: clinical_media/encounter_{uuid}/media_{uuid}.{ext}
    """
    ext = filename.split('.')[-1].lower()
    media_filename = f"media_{uuid.uuid4()}.{ext}"
    return f"clinical_media/encounter_{instance.encounter.id}/{media_filename}"


class ClinicalMediaQuerySet(models.QuerySet):
    """Custom queryset for filtering soft-deleted media."""
    
    def active(self):
        """Return only active (not deleted) media."""
        return self.filter(deleted_at__isnull=True)
    
    def deleted(self):
        """Return only soft-deleted media."""
        return self.filter(deleted_at__isnull=False)


class ClinicalMediaManager(TenantManager):
    """Tenant-aware manager with soft-delete helpers."""

    def get_queryset(self):
        # Build a ClinicalMediaQuerySet and apply the inherited tenant filter.
        # IMPORTANT: must call get_current_tenant() here rather than delegating
        # to super(), because super() returns a plain TenantQuerySet instance
        # rather than ClinicalMediaQuerySet.  The tenant logic is replicated
        # explicitly so the correct QuerySet class is returned.
        from apps.core.tenant_context import get_current_tenant
        qs = ClinicalMediaQuerySet(self.model, using=self._db)
        tenant = get_current_tenant()
        if tenant is not None:
            return qs.filter(legal_entity=tenant)
        return qs

    def active(self):
        return self.get_queryset().active()

    def deleted(self):
        return self.get_queryset().deleted()


class ClinicalMedia(TenantModel):
    """
    Clinical media (photos/images) associated with encounters.
    
    Design Decisions:
    - Associated with Encounter (not Patient) for temporal context
    - Soft delete (deleted_at) for audit trail
    - Local storage (Phase 1), prepared for S3 migration
    - No public URLs - authentication required
    """
    
    MEDIA_TYPE_CHOICES = [
        ('photo', 'Photo'),
        # Future: video, document, etc.
    ]
    
    CATEGORY_CHOICES = [
        ('before', 'Before Treatment'),
        ('after', 'After Treatment'),
        ('progress', 'Progress Photo'),
        ('other', 'Other'),
    ]
    
    # Custom tenant-aware manager
    objects = ClinicalMediaManager()
    unfiltered = models.Manager()
    
    # Core relationships
    encounter = models.ForeignKey(
        'Encounter',
        on_delete=models.CASCADE,
        related_name='clinical_media',
        verbose_name='Encounter',
        help_text='Clinical encounter this media is associated with'
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_media',
        verbose_name='Uploaded By',
        help_text='Practitioner who uploaded this media'
    )
    
    # Media details
    media_type = models.CharField(
        verbose_name='Media Type',
        max_length=20,
        choices=MEDIA_TYPE_CHOICES,
        default='photo'
    )
    category = models.CharField(
        verbose_name='Category',
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='other',
        help_text='Clinical category for this media'
    )
    file = models.ImageField(
        verbose_name='File',
        upload_to=clinical_media_upload_path,
        help_text='Clinical photo file'
    )
    
    # Optional metadata
    notes = models.TextField(
        verbose_name='Notes',
        blank=True,
        help_text='Clinical notes about this media (optional)'
    )
    
    # Audit trail
    created_at = models.DateTimeField(
        verbose_name='Created At',
        auto_now_add=True,
        db_index=True
    )
    deleted_at = models.DateTimeField(
        verbose_name='Deleted At',
        null=True,
        blank=True,
        help_text='Soft delete timestamp for audit trail'
    )
    
    class Meta:
        db_table = 'clinical_media'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['encounter', '-created_at'], name='idx_cmedia_encounter'),
            models.Index(fields=['uploaded_by', '-created_at'], name='idx_cmedia_uploader'),
            models.Index(fields=['deleted_at'], name='idx_cmedia_deleted'),
        ]
        verbose_name = 'Clinical Media'
        verbose_name_plural = 'Clinical Media'
    
    def __str__(self):
        return f"{self.get_media_type_display()} - {self.encounter} ({self.created_at.strftime('%Y-%m-%d')})"
    
    def soft_delete(self):
        """
        Soft delete media (preserves file and audit trail).
        File remains on disk but is hidden from queries.
        """
        from django.utils import timezone
        if not self.deleted_at:
            self.deleted_at = timezone.now()
            self.save(update_fields=['deleted_at'])
    
    @property
    def is_deleted(self):
        """Check if media is soft-deleted."""
        return self.deleted_at is not None
    
    @property
    def file_size_mb(self):
        """Get file size in MB (if file exists)."""
        try:
            return round(self.file.size / (1024 * 1024), 2)
        except (AttributeError, FileNotFoundError):
            return None


class PractitionerTreatment(models.Model):
    """
    Capability mapping: which practitioners can perform which treatments.

    Tenant safety: Treatment is already tenant-scoped via TenantModel,
    so the tenant boundary is enforced through the Treatment FK.
    No additional legal_entity FK is needed on this join table.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    practitioner = models.ForeignKey(
        FK_PRACTITIONER,
        on_delete=models.CASCADE,
        related_name='treatment_capabilities',
    )
    treatment = models.ForeignKey(
        'Treatment',
        on_delete=models.CASCADE,
        related_name='practitioner_capabilities',
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether the practitioner currently performs this treatment',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'practitioner_treatment'
        verbose_name = 'Practitioner Treatment Capability'
        verbose_name_plural = 'Practitioner Treatment Capabilities'
        unique_together = [('practitioner', 'treatment')]
        indexes = [
            models.Index(fields=['practitioner', 'is_active'], name='idx_pt_practitioner_active'),
            models.Index(fields=['treatment', 'is_active'], name='idx_pt_treatment_active'),
        ]

    def __str__(self):
        status = 'active' if self.is_active else 'inactive'
        return f"{self.practitioner} → {self.treatment} ({status})"


class WeekdayChoices(models.IntegerChoices):
    MONDAY = 0, 'Monday'
    TUESDAY = 1, 'Tuesday'
    WEDNESDAY = 2, 'Wednesday'
    THURSDAY = 3, 'Thursday'
    FRIDAY = 4, 'Friday'
    SATURDAY = 5, 'Saturday'
    SUNDAY = 6, 'Sunday'


class PractitionerSchedule(models.Model):
    """
    Per-clinic, per-weekday working hours for a practitioner.

    Replaces the hardcoded 09:00–17:00 in AvailabilityService.
    Multiple rows per (practitioner, clinic, weekday) are allowed when
    start_time differs (e.g. split shifts: 09:00-12:00 + 14:00-18:00).

    Tenant safety: Clinic and Practitioner (via User) both belong
    to a LegalEntity.  No additional legal_entity FK is needed.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    practitioner = models.ForeignKey(
        FK_PRACTITIONER,
        on_delete=models.CASCADE,
        related_name='schedules',
    )
    clinic = models.ForeignKey(
        FK_CLINIC,
        on_delete=models.CASCADE,
        related_name='practitioner_schedules',
    )
    weekday = models.PositiveSmallIntegerField(
        choices=WeekdayChoices.choices,
        help_text='Day of week (0=Monday … 6=Sunday)',
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'practitioner_schedule'
        verbose_name = 'Practitioner Schedule'
        verbose_name_plural = 'Practitioner Schedules'
        unique_together = [('practitioner', 'clinic', 'weekday', 'start_time')]
        indexes = [
            models.Index(fields=['practitioner', 'weekday'], name='idx_ps_pract_weekday'),
            models.Index(fields=['clinic', 'weekday'], name='idx_ps_clinic_weekday'),
            models.Index(fields=['is_active'], name='idx_ps_active'),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({'end_time': 'end_time must be after start_time.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        day = self.get_weekday_display()
        return f"{self.practitioner} @ {self.clinic} — {day} {self.start_time:%H:%M}–{self.end_time:%H:%M}"
