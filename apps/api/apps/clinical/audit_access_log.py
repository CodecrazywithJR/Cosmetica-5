"""
ClinicalAccessLog — audit trail for meaningful clinical data access.

Unlike ClinicalAuditLog (which tracks data *changes*), this model records
*who accessed what* patient-related data and when.

Designed for SaaS medical-product compliance (RGPD / HIPAA-like).
"""
import uuid

from django.conf import settings
from django.db import models


class ClinicalAccessAction:
    """Enumeration of auditable clinical access actions."""

    # Patient
    VIEW_PATIENT = "view_patient"
    CREATE_PATIENT = "create_patient"
    UPDATE_PATIENT = "update_patient"
    MERGE_PATIENT = "merge_patient"

    # Encounter
    VIEW_ENCOUNTER = "view_encounter"
    CREATE_ENCOUNTER = "create_encounter"
    UPDATE_ENCOUNTER = "update_encounter"

    # Clinical media / photos
    VIEW_CLINICAL_MEDIA = "view_clinical_media"
    UPLOAD_CLINICAL_MEDIA = "upload_clinical_media"
    DELETE_CLINICAL_MEDIA = "delete_clinical_media"

    # Treatment sessions
    CREATE_TREATMENT_SESSION = "create_treatment_session"
    UPDATE_TREATMENT_SESSION = "update_treatment_session"
    COMPLETE_TREATMENT_SESSION = "complete_treatment_session"


class ClinicalAccessLog(models.Model):
    """
    Records meaningful clinical-data accesses per tenant.

    Every row answers: *who* accessed *what* about *which patient*, *when*,
    and from *where* (IP / UA).

    Indexed on ``(legal_entity, timestamp)`` for efficient per-tenant
    compliance queries.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    legal_entity = models.ForeignKey(
        "legal.LegalEntity",
        on_delete=models.PROTECT,
        related_name="clinical_access_logs",
        help_text="Tenant that owns this log entry.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="clinical_access_logs",
        help_text="User who performed the action.",
    )
    patient = models.ForeignKey(
        "clinical.Patient",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="access_logs",
        help_text="Patient whose data was accessed (if applicable).",
    )

    action = models.CharField(
        max_length=40,
        help_text="Qualified action name, e.g. 'view_patient'.",
    )
    resource_type = models.CharField(
        max_length=60,
        help_text="Model / resource name, e.g. 'Patient', 'Encounter'.",
    )
    resource_id = models.UUIDField(
        blank=True,
        null=True,
        help_text="PK of the accessed resource (if applicable).",
    )

    ip_address = models.GenericIPAddressField(
        blank=True,
        null=True,
        help_text="Client IP address.",
    )
    user_agent = models.TextField(
        blank=True,
        null=True,
        help_text="Client User-Agent header.",
    )

    class Meta:
        db_table = "clinical_access_log"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(
                fields=["legal_entity", "timestamp"],
                name="idx_access_log_le_ts",
            ),
        ]

    def __str__(self):
        return f"{self.action} by {self.user_id} @ {self.timestamp}"
