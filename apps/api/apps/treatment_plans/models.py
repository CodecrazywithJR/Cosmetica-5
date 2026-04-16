"""
TreatmentPlan models — package-based treatment tracking.

A TreatmentPlan is auto-created when a Proposal with full_package lines
is accepted.  It tracks planned vs completed sessions and transitions
through a strict lifecycle: draft → active → completed | cancelled.

DB table: treatment_plan
"""
import uuid

# Re-export TreatmentSession so Django discovers it from this module.
from apps.treatment_plans.treatment_session_models import (  # noqa: F401
    TreatmentSession,
    TreatmentSessionStatusChoices,
    TREATMENT_SESSION_TERMINAL_STATES,
)
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.managers import TenantManager


# ============================================================================
# Choices
# ============================================================================

class TreatmentPlanStatusChoices(models.TextChoices):
    """
    TreatmentPlan lifecycle states.

    Transitions:
      draft   → active      (first appointment created)
      active  → completed   (completed_sessions == planned_sessions)
      draft   → cancelled
      active  → cancelled
    """
    DRAFT = 'draft', 'Draft'
    ACTIVE = 'active', 'Active'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'


TERMINAL_STATES = frozenset({
    TreatmentPlanStatusChoices.COMPLETED,
    TreatmentPlanStatusChoices.CANCELLED,
})


# ============================================================================
# Model
# ============================================================================

class TreatmentPlan(models.Model):
    """
    Tracks a patient's package-based treatment plan.

    Created automatically when Proposal.accept() encounters a
    ProposalLine with type='full_package'.

    Lifecycle:
      - DRAFT:     Created, no appointments scheduled yet.
      - ACTIVE:    First appointment linked → plan activated.
      - COMPLETED: All planned sessions completed.
      - CANCELLED: Manually cancelled before completion.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Tenant-aware managers
    objects = TenantManager()
    unfiltered = models.Manager()

    # ── Relationships ──────────────────────────────────────────────────
    legal_entity = models.ForeignKey(
        'legal.LegalEntity',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='treatment_plans',
        help_text='Owning legal entity for multi-tenant isolation',
    )
    patient = models.ForeignKey(
        'clinical.Patient',
        on_delete=models.PROTECT,
        related_name='treatment_plans',
        help_text='Patient receiving the treatment plan',
    )
    practitioner = models.ForeignKey(
        'authz.Practitioner',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='treatment_plans',
        help_text='Assigned practitioner (may differ per appointment)',
    )
    proposal = models.ForeignKey(
        'proposals.Proposal',
        on_delete=models.PROTECT,
        related_name='treatment_plans',
        help_text='Source proposal that generated this plan',
    )
    proposal_line = models.OneToOneField(
        'proposals.ProposalLine',
        on_delete=models.PROTECT,
        related_name='treatment_plan',
        help_text='Specific proposal line (full_package) that originated this plan',
    )
    sale = models.ForeignKey(
        'sales.Sale',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='treatment_plans',
        help_text='Sale generated alongside this plan',
    )

    # ── Plan details (snapshot at creation) ────────────────────────────
    package_name = models.CharField(
        max_length=255,
        help_text='Treatment name snapshot from proposal line',
    )
    description_snapshot = models.TextField(
        blank=True,
        default='',
        help_text='Treatment description snapshot from proposal line',
    )
    planned_sessions = models.PositiveIntegerField(
        help_text='Total number of sessions in the package',
    )
    completed_sessions = models.PositiveIntegerField(
        default=0,
        help_text='Number of sessions completed so far',
    )
    total_price_snapshot = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Total price snapshot from proposal line (line_total)',
    )
    currency = models.CharField(
        max_length=3,
        default='EUR',
        help_text='Currency code (snapshot from proposal)',
    )

    # ── Status lifecycle ───────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=TreatmentPlanStatusChoices.choices,
        default=TreatmentPlanStatusChoices.DRAFT,
        help_text='Current lifecycle status',
    )
    activated_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text='When the plan was activated (first appointment created)',
    )
    completed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text='When all planned sessions were completed',
    )
    cancelled_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text='When the plan was cancelled',
    )
    cancellation_reason = models.TextField(
        blank=True,
        default='',
        help_text='Reason for cancellation (if applicable)',
    )

    # ── Audit ──────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'treatment_plan'
        verbose_name = 'Treatment Plan'
        verbose_name_plural = 'Treatment Plans'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient'], name='idx_tp_patient'),
            models.Index(fields=['proposal'], name='idx_tp_proposal'),
            models.Index(fields=['status'], name='idx_tp_status'),
            models.Index(fields=['practitioner'], name='idx_tp_practitioner'),
            models.Index(fields=['legal_entity'], name='idx_tp_legal_entity'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(planned_sessions__gt=0),
                name='tp_planned_sessions_positive',
            ),
            models.CheckConstraint(
                check=models.Q(completed_sessions__gte=0),
                name='tp_completed_sessions_non_negative',
            ),
            models.CheckConstraint(
                check=models.Q(total_price_snapshot__gte=0),
                name='tp_total_price_non_negative',
            ),
        ]

    def __str__(self):
        return (
            f"{self.package_name} — "
            f"{self.completed_sessions}/{self.planned_sessions} sessions "
            f"({self.status})"
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
                TreatmentPlan.objects
                .filter(pk=self.pk)
                .values_list('status', flat=True)
                .first()
            )
            if current_status and current_status in TERMINAL_STATES:
                raise ValidationError(
                    f"Cannot modify a treatment plan in '{current_status}' state."
                )

        super().save(*args, **kwargs)

    # ── State-machine methods ──────────────────────────────────────────

    def activate(self):
        """
        Transition: draft → active.

        Called automatically when the first Appointment with this
        treatment_plan FK is created.
        """
        if self.status != TreatmentPlanStatusChoices.DRAFT:
            # Already active or terminal — idempotent for active
            if self.status == TreatmentPlanStatusChoices.ACTIVE:
                return  # idempotent
            raise ValidationError(
                f"Cannot activate a treatment plan in '{self.status}' state. "
                "Only DRAFT plans can be activated."
            )

        self.status = TreatmentPlanStatusChoices.ACTIVE
        self.activated_at = timezone.now()
        self.save(update_fields=['status', 'activated_at', 'updated_at'])

    def record_session_completed(self):
        """
        Increment completed_sessions.  If all planned sessions are done,
        transition to COMPLETED automatically.

        Called when an Appointment linked to this plan transitions to
        status='completed'.
        """
        if self.status != TreatmentPlanStatusChoices.ACTIVE:
            raise ValidationError(
                f"Cannot record session on a treatment plan in '{self.status}' state. "
                "Only ACTIVE plans accept session completions."
            )

        self.completed_sessions += 1

        update_cols = ['completed_sessions', 'updated_at']

        if self.completed_sessions >= self.planned_sessions:
            self.status = TreatmentPlanStatusChoices.COMPLETED
            self.completed_at = timezone.now()
            update_cols += ['status', 'completed_at']

        self.save(update_fields=update_cols)

    def cancel(self, reason=''):
        """
        Transition: draft | active → cancelled.
        """
        if self.status in TERMINAL_STATES:
            raise ValidationError(
                f"Cannot cancel a treatment plan in '{self.status}' state. "
                "Only DRAFT or ACTIVE plans can be cancelled."
            )

        self.status = TreatmentPlanStatusChoices.CANCELLED
        self.cancelled_at = timezone.now()
        update_cols = ['status', 'cancelled_at', 'updated_at']
        if reason:
            self.cancellation_reason = reason
            update_cols.append('cancellation_reason')
        self.save(update_fields=update_cols)

    # ── Computed properties ────────────────────────────────────────────

    @property
    def remaining_sessions(self):
        """Sessions still to be completed."""
        return max(0, self.planned_sessions - self.completed_sessions)

    @property
    def progress_percent(self):
        """Completion percentage (0-100)."""
        if self.planned_sessions == 0:
            return 0
        return round((self.completed_sessions / self.planned_sessions) * 100, 1)

    @property
    def is_terminal(self):
        """Whether the plan is in a terminal (immutable) state."""
        return self.status in TERMINAL_STATES
