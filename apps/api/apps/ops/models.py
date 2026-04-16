"""
Generic immutable audit log for the ERP.

Tracks clinical and commercial domain events for traceability, legal
auditing, debugging and analytics.

Rules:
  - append-only: no UPDATE, no DELETE is allowed at the ORM / service layer
  - every entry must carry a valid legal_entity (tenant isolation)
"""
import uuid

from django.conf import settings
from django.db import models


# ---------------------------------------------------------------------------
# Event type constants
# ---------------------------------------------------------------------------

class AuditEventType(models.TextChoices):
    # Patient
    PATIENT_CREATED         = 'PATIENT_CREATED',         'Patient Created'
    PATIENT_UPDATED         = 'PATIENT_UPDATED',         'Patient Updated'
    PATIENT_SOFT_DELETED    = 'PATIENT_SOFT_DELETED',    'Patient Soft-Deleted'

    # Appointment
    APPOINTMENT_CREATED     = 'APPOINTMENT_CREATED',     'Appointment Created'
    APPOINTMENT_UPDATED     = 'APPOINTMENT_UPDATED',     'Appointment Updated'
    APPOINTMENT_CANCELLED   = 'APPOINTMENT_CANCELLED',   'Appointment Cancelled'
    APPOINTMENT_NO_SHOW     = 'APPOINTMENT_NO_SHOW',     'Appointment No-Show'
    APPOINTMENT_CHECKED_IN  = 'APPOINTMENT_CHECKED_IN',  'Appointment Checked-In'

    # Encounter
    ENCOUNTER_CREATED       = 'ENCOUNTER_CREATED',       'Encounter Created'
    ENCOUNTER_FINALIZED     = 'ENCOUNTER_FINALIZED',     'Encounter Finalized'
    ENCOUNTER_CANCELLED     = 'ENCOUNTER_CANCELLED',     'Encounter Cancelled'

    # Clinical
    CONSENT_SIGNED          = 'CONSENT_SIGNED',          'Consent Signed'
    CLINICAL_PHOTO_UPLOADED = 'CLINICAL_PHOTO_UPLOADED', 'Clinical Photo Uploaded'

    # Proposals
    PROPOSAL_CREATED        = 'PROPOSAL_CREATED',        'Proposal Created'
    PROPOSAL_SENT           = 'PROPOSAL_SENT',           'Proposal Sent'
    PROPOSAL_ACCEPTED       = 'PROPOSAL_ACCEPTED',       'Proposal Accepted'
    PROPOSAL_CANCELLED      = 'PROPOSAL_CANCELLED',      'Proposal Cancelled'

    # Commerce
    SALE_CREATED            = 'SALE_CREATED',            'Sale Created'
    REFUND_CREATED          = 'REFUND_CREATED',          'Refund Created'

    # Treatment
    TREATMENT_SESSION_COMPLETED = 'TREATMENT_SESSION_COMPLETED', 'Treatment Session Completed'


# ---------------------------------------------------------------------------
# AuditLog model
# ---------------------------------------------------------------------------

class AuditLog(models.Model):
    """
    Generic immutable event table for clinical and commercial domain events.

    Invariants enforced at the service layer:
      - No updates (save() raises on existing records)
      - No deletes (delete() always raises)
      - legal_entity must be non-null (enforced in AuditLog.save())
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text='UTC timestamp when the event was recorded.',
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_events',
        help_text='User who triggered the event (null for system/Celery actions).',
    )

    legal_entity = models.ForeignKey(
        'legal.LegalEntity',
        on_delete=models.PROTECT,
        null=False,
        related_name='audit_events',
        help_text='Owning legal entity — required for tenant isolation.',
    )

    entity_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text='Python class name of the entity (e.g. "Patient", "Appointment").',
    )

    entity_id = models.UUIDField(
        db_index=True,
        help_text='PK of the entity that triggered the event.',
    )

    event_type = models.CharField(
        max_length=60,
        choices=AuditEventType.choices,
        db_index=True,
        help_text='Semantic event name from AuditEventType.',
    )

    payload_json = models.JSONField(
        default=dict,
        help_text='Arbitrary JSON payload — must be serialisable.',
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Alias for timestamp (same value).',
    )

    class Meta:
        app_label = 'ops'
        db_table = 'ops_audit_log'
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp'],    name='idx_auditlog_timestamp'),
            models.Index(fields=['legal_entity'], name='idx_auditlog_le'),
            models.Index(fields=['entity_type'],  name='idx_auditlog_entity_type'),
            models.Index(fields=['entity_id'],    name='idx_auditlog_entity_id'),
            models.Index(fields=['event_type'],   name='idx_auditlog_event_type'),
        ]

    # ------------------------------------------------------------------
    # Immutability guards
    # ------------------------------------------------------------------

    def save(self, *args, **kwargs):
        if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
            raise TypeError('AuditLog records are immutable and cannot be updated.')
        if self.legal_entity_id is None:
            raise ValueError('AuditLog.legal_entity must not be None.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # noqa: D102
        raise TypeError('AuditLog records are immutable and cannot be deleted.')

    def __str__(self) -> str:
        actor = self.user.email if self.user_id else 'system'
        return f'[{self.event_type}] {self.entity_type}#{str(self.entity_id)[:8]} by {actor}'

