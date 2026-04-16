"""
TreatmentSession models — session execution for TreatmentPlan.

A TreatmentSession is created exclusively from an Appointment via the
``start-treatment-session`` action.  It represents a single execution of
one session within a TreatmentPlan package.

Lifecycle:
    draft  →  completed
    draft  →  cancelled
    completed / cancelled are terminal and immutable.

DB table: treatment_session
"""
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.tenant_model import TenantModel


# ============================================================================
# Choices
# ============================================================================

class TreatmentSessionStatusChoices(models.TextChoices):
    """
    TreatmentSession lifecycle states.

    Transitions:
        draft     → completed
        draft     → cancelled
    """

    DRAFT = 'draft', 'Draft'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'


TREATMENT_SESSION_TERMINAL_STATES = frozenset({
    TreatmentSessionStatusChoices.COMPLETED,
    TreatmentSessionStatusChoices.CANCELLED,
})


# ============================================================================
# Model
# ============================================================================

class TreatmentSession(TenantModel):
    """
    Single session execution within a TreatmentPlan.

    Always created from an Appointment via the ``start-treatment-session``
    action.  One Appointment → one TreatmentSession (enforced by UNIQUE).

    Editable only while in ``draft`` status.  ``completed`` and
    ``cancelled`` are terminal and immutable.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Relationships ──────────────────────────────────────────────────
    treatment_plan = models.ForeignKey(
        'treatment_plans.TreatmentPlan',
        on_delete=models.PROTECT,
        related_name='sessions',
        help_text='Parent treatment plan',
    )
    appointment = models.OneToOneField(
        'clinical.Appointment',
        on_delete=models.PROTECT,
        related_name='treatment_session',
        help_text='Source appointment (1:1 — unique constraint)',
    )
    practitioner = models.ForeignKey(
        'authz.Practitioner',
        on_delete=models.PROTECT,
        related_name='treatment_sessions',
        help_text='Practitioner who performed the session',
    )

    # ── Session data ───────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=TreatmentSessionStatusChoices.choices,
        default=TreatmentSessionStatusChoices.DRAFT,
        help_text='Current lifecycle status',
    )
    notes = models.TextField(
        blank=True,
        default='',
        help_text='Brief session notes (editable in draft only)',
    )
    performed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text='When the session was performed (auto-set on complete if null)',
    )

    # ── Audit ──────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'treatment_session'
        verbose_name = 'Treatment Session'
        verbose_name_plural = 'Treatment Sessions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['treatment_plan'], name='idx_ts_treatment_plan'),
            models.Index(fields=['status'], name='idx_ts_status'),
            models.Index(fields=['practitioner'], name='idx_ts_practitioner'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(status__in=[
                    TreatmentSessionStatusChoices.DRAFT,
                    TreatmentSessionStatusChoices.COMPLETED,
                    TreatmentSessionStatusChoices.CANCELLED,
                ]),
                name='ts_status_valid',
            ),
            models.CheckConstraint(
                check=(
                    models.Q(status__in=['draft', 'cancelled'])
                    | models.Q(performed_at__isnull=False)
                ),
                name='ts_performed_at_required_when_completed',
            ),
        ]

    def __str__(self):
        return (
            f"Session {self.pk} — "
            f"{self.treatment_plan.package_name} ({self.status})"
        )

    # ── Save with immutability ─────────────────────────────────────────

    def save(self, *args, **kwargs):
        """
        Enforce immutability for terminal states.

        State-machine methods pass ``update_fields=[...]`` which skips
        the immutability check (the method's own guard already validated
        the transition).
        """
        if self.pk and not kwargs.get('update_fields'):
            current_status = (
                TreatmentSession.objects
                .filter(pk=self.pk)
                .values_list('status', flat=True)
                .first()
            )
            if current_status and current_status in TREATMENT_SESSION_TERMINAL_STATES:
                raise ValidationError(
                    f"Cannot modify a treatment session in '{current_status}' state."
                )

        super().save(*args, **kwargs)

    # ── State-machine methods ──────────────────────────────────────────

    def complete(self):
        """
        Transition: draft → completed.

        Sets ``performed_at`` to now() if not already provided.

        Does NOT handle TreatmentPlan auto-complete — that is the
        responsibility of the calling view/service so that proper
        locking and transaction semantics are applied.
        """
        if self.status != TreatmentSessionStatusChoices.DRAFT:
            raise ValidationError(
                f"Cannot complete a session in '{self.status}' state. "
                "Only DRAFT sessions can be completed."
            )

        self.status = TreatmentSessionStatusChoices.COMPLETED
        if not self.performed_at:
            self.performed_at = timezone.now()
        self.save(update_fields=['status', 'performed_at', 'updated_at'])

    def cancel(self):
        """
        Transition: draft → cancelled.

        Terminal — cannot be reverted.
        """
        if self.status != TreatmentSessionStatusChoices.DRAFT:
            raise ValidationError(
                f"Cannot cancel a session in '{self.status}' state. "
                "Only DRAFT sessions can be cancelled."
            )

        self.status = TreatmentSessionStatusChoices.CANCELLED
        self.save(update_fields=['status', 'updated_at'])
