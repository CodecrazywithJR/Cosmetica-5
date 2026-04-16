"""
Proposal models — canonical app for clinical charge proposals.

DB tables remain unchanged (clinical_charge_proposal, clinical_charge_proposal_line).
"""
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core.tenant_model import TenantModel


# ============================================================================
# Default validity period
# ============================================================================
PROPOSAL_VALIDITY_DAYS = 30


class ProposalStatusChoices(models.TextChoices):
    """
    Proposal lifecycle states (formal state machine).

    Transitions:
        draft   → sent | cancelled | expired
        sent    → accepted | cancelled | expired
        accepted  (terminal)
        cancelled (terminal)
        expired   (terminal)
    """
    DRAFT = 'draft', 'Draft'
    SENT = 'sent', 'Sent'
    ACCEPTED = 'accepted', 'Accepted'
    CANCELLED = 'cancelled', 'Cancelled'
    EXPIRED = 'expired', 'Expired'


# Terminal states — no further transitions allowed
TERMINAL_STATES = frozenset({
    ProposalStatusChoices.ACCEPTED,
    ProposalStatusChoices.CANCELLED,
    ProposalStatusChoices.EXPIRED,
})


class ProposalLineTypeChoices(models.TextChoices):
    """
    Proposal line billing type.

    - per_session:  Each session billed individually (default).
    - full_package: All sessions bundled; generates a TreatmentPlan on accept.
    """
    PER_SESSION = 'per_session', 'Per Session'
    FULL_PACKAGE = 'full_package', 'Full Package'


class Proposal(TenantModel):
    """
    Intermediate model between Encounter and Sale.

    Represents a charge proposal derived from a finalized clinical encounter.
    Formal state machine with expiration support.

    Status transitions:
        draft  → send()   → sent
        sent   → accept() → accepted  (creates Sale + SaleLines atomically)
        draft/sent → cancel() → cancelled
        draft/sent → expire() → expired  (auto or manual)

    Business Rules:
    - Can only be created from FINALIZED encounters
    - Immutable once in terminal state (accepted/cancelled/expired)
    - One proposal per encounter (unique constraint via OneToOneField)
    - accept() checks valid_until before proceeding
    - accept() creates Sale + SaleLines in a single atomic transaction
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Core relationships
    encounter = models.OneToOneField(
        'clinical.Encounter',
        on_delete=models.PROTECT,
        related_name='charge_proposal',
        help_text='Source encounter (must be FINALIZED)'
    )
    patient = models.ForeignKey(
        'clinical.Patient',
        on_delete=models.PROTECT,
        related_name='charge_proposals',
        help_text='Patient from encounter (denormalized for querying)'
    )
    practitioner = models.ForeignKey(
        'authz.Practitioner',
        on_delete=models.PROTECT,
        related_name='charge_proposals',
        help_text='Practitioner from encounter (denormalized)'
    )

    # ── Status & lifecycle ──────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=ProposalStatusChoices.choices,
        default=ProposalStatusChoices.DRAFT,
        help_text='Proposal status (draft/sent/accepted/cancelled/expired)'
    )
    valid_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Proposal expiration timestamp (created_at + 30 days by default)'
    )

    # ── Sent tracking ──────────────────────────────────────────────────────
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when proposal was sent to patient'
    )

    # ── Acceptance / sale conversion tracking ──────────────────────────────
    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when proposal was accepted'
    )
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='accepted_proposals',
        help_text='User who accepted this proposal'
    )
    converted_to_sale = models.ForeignKey(
        'sales.Sale',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_proposal',
        help_text='Sale created from this proposal (null if not yet accepted)'
    )
    converted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when sale was created (same as accepted_at)'
    )

    # ── Financial summary ──────────────────────────────────────────────────
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Total charge amount (sum of line totals, NO TAX)'
    )
    currency = models.CharField(
        max_length=3,
        default='EUR',
        help_text='Currency code (ISO 4217)'
    )

    # ── Metadata ───────────────────────────────────────────────────────────
    notes = models.TextField(
        blank=True,
        null=True,
        help_text='Internal notes about this proposal'
    )
    cancellation_reason = models.TextField(
        blank=True,
        null=True,
        help_text='Reason for cancellation (if status=cancelled)'
    )

    # ── Audit timestamps ──────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_proposals',
        help_text='User who generated this proposal'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clinical_charge_proposal'
        verbose_name = 'Proposal'
        verbose_name_plural = 'Proposals'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at'], name='idx_proposal_created'),
            models.Index(fields=['status', '-created_at'], name='idx_proposal_status_created'),
            models.Index(fields=['patient', '-created_at'], name='idx_proposal_patient_created'),
            models.Index(fields=['encounter'], name='idx_proposal_encounter'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(total_amount__gte=0),
                name='proposal_total_non_negative'
            ),
        ]

    def __str__(self):
        return f"Proposal {self.id} - {self.patient} ({self.status})"

    # ── Auto-fill valid_until on first save ─────────────────────────────────
    def save(self, *args, **kwargs):
        # Set valid_until if not explicitly provided on creation
        if not self.valid_until:
            base = self.created_at or timezone.now()
            self.valid_until = base + timedelta(days=PROPOSAL_VALIDITY_DAYS)

        # Block edits when in terminal state (unless force_save is used internally)
        if not kwargs.pop('force_save', False):
            if self.pk:
                try:
                    old = Proposal.objects.only('status').get(pk=self.pk)
                    if old.status in TERMINAL_STATES:
                        raise ValidationError(
                            f"Cannot modify proposal in '{old.status}' state."
                        )
                except Proposal.DoesNotExist:
                    pass  # new record

        super().save(*args, **kwargs)

    def recalculate_total(self):
        """Recalculate total_amount from proposal lines and persist."""
        total = sum(
            (line.line_total for line in self.lines.all()),
            Decimal('0.00')
        )
        self.total_amount = total
        self.save(update_fields=['total_amount', 'updated_at'])
        return total

    # ====================================================================
    # State-machine transitions
    # ====================================================================

    def send(self, user):
        """
        Transition: draft → sent.

        Records who/when sent.  Does NOT create any Sale.
        """
        if self.status != ProposalStatusChoices.DRAFT:
            raise ValidationError(
                f"Cannot send proposal in '{self.status}' state. "
                "Only DRAFT proposals can be sent."
            )
        self.status = ProposalStatusChoices.SENT
        self.sent_at = timezone.now()
        self.save()

    def accept(self, user, legal_entity=None):
        """
        Transition: sent → accepted.

        Atomically:
        1. Verify not expired
        2. Set status = accepted + timestamps
        3. Create Sale + SaleLines from proposal lines
        4. Link converted_to_sale

        Args:
            user: The user accepting the proposal.
            legal_entity: LegalEntity for the Sale (required).

        Raises:
            ValidationError: If not in 'sent' state, expired, or missing legal_entity.
        """
        if self.status != ProposalStatusChoices.SENT:
            raise ValidationError(
                f"Cannot accept proposal in '{self.status}' state. "
                "Only SENT proposals can be accepted."
            )

        # Check expiration
        if timezone.now() > self.valid_until:
            self.expire()
            raise ValidationError("Proposal has expired and cannot be accepted.")

        if legal_entity is None:
            raise ValidationError("legal_entity is required to accept a proposal.")

        from apps.sales.models import Sale, SaleLine, SaleStatusChoices

        now = timezone.now()

        with transaction.atomic():
            # 1. Create Sale header
            sale = Sale.objects.create(
                legal_entity=legal_entity,
                patient=self.patient,
                status=SaleStatusChoices.DRAFT,
                subtotal=self.total_amount,
                tax=Decimal('0.00'),
                discount=Decimal('0.00'),
                total=self.total_amount,
                currency=self.currency,
                notes=f"Generated from proposal {self.id}",
            )

            # 2. Create SaleLines from proposal lines
            for prop_line in self.lines.all():
                SaleLine.objects.create(
                    sale=sale,
                    product=None,
                    product_name=prop_line.treatment_name,
                    product_code='',
                    description=prop_line.description or '',
                    quantity=prop_line.quantity,
                    unit_price=prop_line.unit_price,
                    discount=Decimal('0.00'),
                    line_total=prop_line.line_total,
                )

            # 3. Create TreatmentPlans for full_package lines
            from apps.treatment_plans.models import TreatmentPlan

            full_package_lines = self.lines.filter(
                type=ProposalLineTypeChoices.FULL_PACKAGE
            )
            for pkg_line in full_package_lines:
                TreatmentPlan.objects.create(
                    patient=self.patient,
                    practitioner=self.practitioner,
                    proposal=self,
                    proposal_line=pkg_line,
                    sale=sale,
                    package_name=pkg_line.treatment_name,
                    description_snapshot=pkg_line.description or '',
                    planned_sessions=pkg_line.quantity,
                    completed_sessions=0,
                    total_price_snapshot=pkg_line.line_total,
                    currency=self.currency,
                )

            # 4. Update proposal
            self.status = ProposalStatusChoices.ACCEPTED
            self.accepted_at = now
            self.accepted_by = user
            self.converted_to_sale = sale
            self.converted_at = now
            self.save(force_save=True)

        return sale

    def cancel(self, user, reason=''):
        """
        Transition: draft | sent → cancelled.
        """
        if self.status not in (ProposalStatusChoices.DRAFT, ProposalStatusChoices.SENT):
            raise ValidationError(
                f"Cannot cancel proposal in '{self.status}' state. "
                "Only DRAFT or SENT proposals can be cancelled."
            )
        self.status = ProposalStatusChoices.CANCELLED
        if reason:
            self.cancellation_reason = reason
        self.save(force_save=True)

    def expire(self):
        """
        Transition: draft | sent → expired.
        """
        if self.status not in (ProposalStatusChoices.DRAFT, ProposalStatusChoices.SENT):
            raise ValidationError(
                f"Cannot expire proposal in '{self.status}' state. "
                "Only DRAFT or SENT proposals can expire."
            )
        self.status = ProposalStatusChoices.EXPIRED
        self.save(force_save=True)


class ProposalLine(models.Model):
    """
    Line item in a clinical charge proposal.

    Derived from EncounterTreatment with immutable snapshot of pricing.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationships
    proposal = models.ForeignKey(
        'Proposal',
        on_delete=models.CASCADE,
        related_name='lines',
        help_text='Parent proposal'
    )
    encounter_treatment = models.ForeignKey(
        'clinical.EncounterTreatment',
        on_delete=models.PROTECT,
        related_name='proposal_lines',
        help_text='Source encounter treatment'
    )
    treatment = models.ForeignKey(
        'clinical.Treatment',
        on_delete=models.PROTECT,
        related_name='proposal_lines',
        help_text='Treatment reference (denormalized for reporting)'
    )

    # Line type — determines whether a TreatmentPlan is generated on accept
    type = models.CharField(
        max_length=20,
        choices=ProposalLineTypeChoices.choices,
        default=ProposalLineTypeChoices.PER_SESSION,
        help_text='Billing type: per_session (default) or full_package (creates TreatmentPlan)',
    )

    # Pricing snapshot (immutable)
    treatment_name = models.CharField(
        max_length=255,
        help_text='Treatment name at proposal creation time'
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text='Combined: treatment description + encounter treatment notes'
    )
    quantity = models.PositiveIntegerField(
        default=1,
        help_text='Quantity of treatment performed'
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Price per unit (snapshot from EncounterTreatment.effective_price)'
    )
    line_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Line total: quantity * unit_price (NO discounts, NO tax)'
    )

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'clinical_charge_proposal_line'
        verbose_name = 'Proposal Line'
        verbose_name_plural = 'Proposal Lines'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['proposal'], name='idx_proposal_line_proposal'),
            models.Index(fields=['encounter_treatment'], name='idx_proposal_line_enc_trt'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gt=0),
                name='proposal_line_quantity_positive'
            ),
            models.CheckConstraint(
                check=models.Q(unit_price__gte=0),
                name='proposal_line_unit_price_non_negative'
            ),
            models.CheckConstraint(
                check=models.Q(line_total__gte=0),
                name='proposal_line_total_non_negative'
            ),
        ]

    def __str__(self):
        return f"{self.treatment_name} x {self.quantity} = {self.line_total}"

    def save(self, *args, **kwargs):
        """Auto-calculate line_total on save and block edits on terminal proposals."""
        # Block edits when parent proposal is in a terminal state
        if self.proposal_id:
            try:
                parent_status = Proposal.objects.only('status').get(pk=self.proposal_id).status
                if parent_status in TERMINAL_STATES:
                    raise ValidationError(
                        f"Cannot modify lines of a proposal in '{parent_status}' state."
                    )
            except Proposal.DoesNotExist:
                pass

        if self.quantity and self.unit_price is not None:
            self.line_total = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Block deletion when parent proposal is in a terminal state."""
        if self.proposal_id:
            try:
                parent_status = Proposal.objects.only('status').get(pk=self.proposal_id).status
                if parent_status in TERMINAL_STATES:
                    raise ValidationError(
                        f"Cannot delete lines of a proposal in '{parent_status}' state."
                    )
            except Proposal.DoesNotExist:
                pass
        super().delete(*args, **kwargs)


# Backward-compatible aliases (will be removed in a future cleanup)
ClinicalChargeProposal = Proposal
ClinicalChargeProposalLine = ProposalLine
