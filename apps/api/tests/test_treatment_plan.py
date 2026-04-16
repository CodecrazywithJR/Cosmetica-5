"""
Tests for TreatmentPlan module.

Covers:
 1.  Auto-creation on Proposal.accept() for full_package lines
 2.  No TreatmentPlan created for per_session lines
 3.  TreatmentPlan initial state is 'draft'
 4.  Activation on first Appointment creation (draft → active)
 5.  Idempotent activation (second appointment doesn't error)
 6.  Session completion tracking (completed_sessions increments)
 7.  Auto-completion when completed_sessions == planned_sessions
 8.  Cancellation (draft → cancelled, active → cancelled)
 9.  Immutability: cannot modify completed/cancelled plans
10.  Blocking: cannot record session on non-active plan
11.  Mixed proposal: full_package + per_session lines
12.  Computed properties (remaining_sessions, progress_percent, is_terminal)
"""
import pytest
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.proposals.models import (
    Proposal,
    ProposalLine,
    ProposalStatusChoices,
    ProposalLineTypeChoices,
)
from apps.treatment_plans.models import (
    TreatmentPlan,
    TreatmentPlanStatusChoices,
    TERMINAL_STATES,
)
from apps.clinical.models import Appointment, AppointmentStatusChoices


# ============================================================================
# Helpers
# ============================================================================

def _make_treatment(admin_user, *, name='Laser Package', price='500.00'):
    from apps.clinical.models import Treatment
    return Treatment.objects.create(
        name=name,
        default_price=Decimal(price),
        is_active=True,
    )


def _make_encounter_treatment(encounter, treatment, *, quantity=1):
    from apps.clinical.models import EncounterTreatment
    return EncounterTreatment.objects.create(
        encounter=encounter,
        treatment=treatment,
        quantity=quantity,
    )


def _make_legal_entity():
    from apps.legal.models import LegalEntity
    return LegalEntity.objects.create(
        trade_name='TP Test Clinic',
        legal_name='TP Test Clinic SRL',
        country_code='FR',
        is_active=True,
    )


def _make_proposal_with_line(
    encounter,
    admin_user,
    *,
    line_type=ProposalLineTypeChoices.FULL_PACKAGE,
    quantity=5,
    unit_price='100.00',
    treatment_name='Laser Package',
):
    """Create a SENT proposal with a single line of the specified type."""
    treatment = _make_treatment(admin_user, name=treatment_name, price=unit_price)
    enc_treatment = _make_encounter_treatment(encounter, treatment, quantity=quantity)

    proposal = Proposal.objects.create(
        encounter=encounter,
        patient=encounter.patient,
        practitioner=encounter.practitioner,
        status=ProposalStatusChoices.DRAFT,
        total_amount=Decimal(unit_price) * quantity,
        currency='EUR',
        created_by=admin_user,
    )
    line = ProposalLine.objects.create(
        proposal=proposal,
        encounter_treatment=enc_treatment,
        treatment=treatment,
        treatment_name=treatment_name,
        description='Test description',
        quantity=quantity,
        unit_price=Decimal(unit_price),
        line_total=Decimal(unit_price) * quantity,
        type=line_type,
    )
    # Move to SENT so it can be accepted
    proposal.send(user=admin_user)
    return proposal, line


def _make_appointment(patient, practitioner, clinic, *, treatment_plan=None, status='scheduled', day_offset=1):
    """Create an appointment, optionally linked to a treatment plan."""
    treatment = treatment_plan.proposal_line.treatment if treatment_plan else None
    return Appointment.objects.create(
        patient=patient,
        practitioner=practitioner,
        clinic=clinic,
        source='erp',
        status=status,
        scheduled_start=timezone.now() + timedelta(days=day_offset),
        scheduled_end=timezone.now() + timedelta(days=day_offset, hours=1),
        treatment_plan=treatment_plan,
        treatment=treatment,
    )


# ============================================================================
# 1. Auto-creation on accept()
# ============================================================================

@pytest.mark.django_db
class TestAutoCreation:
    """TreatmentPlan is auto-created when a full_package line's proposal is accepted."""

    def test_accept_full_package_creates_treatment_plan(self, encounter, admin_user):
        """Accepting a proposal with a full_package line creates a TreatmentPlan."""
        proposal, line = _make_proposal_with_line(encounter, admin_user)
        legal_entity = _make_legal_entity()

        assert TreatmentPlan.objects.count() == 0

        sale = proposal.accept(user=admin_user, legal_entity=legal_entity)

        assert TreatmentPlan.objects.count() == 1
        tp = TreatmentPlan.objects.first()
        assert tp.patient == encounter.patient
        assert tp.practitioner == encounter.practitioner
        assert tp.proposal == proposal
        assert tp.proposal_line == line
        assert tp.sale == sale
        assert tp.package_name == 'Laser Package'
        assert tp.description_snapshot == 'Test description'
        assert tp.planned_sessions == 5
        assert tp.completed_sessions == 0
        assert tp.total_price_snapshot == Decimal('500.00')
        assert tp.currency == 'EUR'
        assert tp.status == TreatmentPlanStatusChoices.DRAFT

    def test_accept_per_session_no_treatment_plan(self, encounter, admin_user):
        """Accepting a proposal with only per_session lines does NOT create a TreatmentPlan."""
        proposal, _ = _make_proposal_with_line(
            encounter, admin_user,
            line_type=ProposalLineTypeChoices.PER_SESSION,
        )
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)

        assert TreatmentPlan.objects.count() == 0

    def test_mixed_lines_only_full_package_creates_plan(self, encounter, admin_user):
        """Only full_package lines generate TreatmentPlans; per_session lines don't."""
        treatment_pkg = _make_treatment(admin_user, name='Package Treatment', price='200.00')
        treatment_single = _make_treatment(admin_user, name='Single Treatment', price='50.00')
        enc_t1 = _make_encounter_treatment(encounter, treatment_pkg, quantity=4)
        enc_t2 = _make_encounter_treatment(encounter, treatment_single, quantity=1)

        proposal = Proposal.objects.create(
            encounter=encounter,
            patient=encounter.patient,
            practitioner=encounter.practitioner,
            status=ProposalStatusChoices.DRAFT,
            total_amount=Decimal('850.00'),
            currency='EUR',
            created_by=admin_user,
        )
        # full_package line
        pkg_line = ProposalLine.objects.create(
            proposal=proposal,
            encounter_treatment=enc_t1,
            treatment=treatment_pkg,
            treatment_name='Package Treatment',
            quantity=4,
            unit_price=Decimal('200.00'),
            line_total=Decimal('800.00'),
            type=ProposalLineTypeChoices.FULL_PACKAGE,
        )
        # per_session line
        ProposalLine.objects.create(
            proposal=proposal,
            encounter_treatment=enc_t2,
            treatment=treatment_single,
            treatment_name='Single Treatment',
            quantity=1,
            unit_price=Decimal('50.00'),
            line_total=Decimal('50.00'),
            type=ProposalLineTypeChoices.PER_SESSION,
        )
        proposal.send(user=admin_user)

        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)

        assert TreatmentPlan.objects.count() == 1
        tp = TreatmentPlan.objects.first()
        assert tp.proposal_line == pkg_line
        assert tp.package_name == 'Package Treatment'
        assert tp.planned_sessions == 4


# ============================================================================
# 2. Initial state
# ============================================================================

@pytest.mark.django_db
class TestInitialState:
    """TreatmentPlan is created in DRAFT status with zero completed sessions."""

    def test_initial_status_is_draft(self, encounter, admin_user):
        proposal, _ = _make_proposal_with_line(encounter, admin_user)
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)

        tp = TreatmentPlan.objects.first()
        assert tp.status == TreatmentPlanStatusChoices.DRAFT
        assert tp.completed_sessions == 0
        assert tp.activated_at is None
        assert tp.completed_at is None
        assert tp.cancelled_at is None


# ============================================================================
# 3. Activation on first Appointment
# ============================================================================

@pytest.mark.django_db
class TestActivation:
    """TreatmentPlan activates when first Appointment is created with its FK."""

    def test_first_appointment_activates_plan(
        self, encounter, admin_user, practitioner, clinic
    ):
        proposal, _ = _make_proposal_with_line(encounter, admin_user)
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)
        tp = TreatmentPlan.objects.first()
        assert tp.status == TreatmentPlanStatusChoices.DRAFT

        _make_appointment(
            encounter.patient, practitioner, clinic,
            treatment_plan=tp,
        )

        tp.refresh_from_db()
        assert tp.status == TreatmentPlanStatusChoices.ACTIVE
        assert tp.activated_at is not None

    def test_second_appointment_is_idempotent(
        self, encounter, admin_user, practitioner, clinic
    ):
        """Creating a second appointment doesn't error — activate() is idempotent for ACTIVE."""
        proposal, _ = _make_proposal_with_line(encounter, admin_user)
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)
        tp = TreatmentPlan.objects.first()

        _make_appointment(
            encounter.patient, practitioner, clinic,
            treatment_plan=tp, day_offset=1,
        )
        _make_appointment(
            encounter.patient, practitioner, clinic,
            treatment_plan=tp, day_offset=2,
        )

        tp.refresh_from_db()
        assert tp.status == TreatmentPlanStatusChoices.ACTIVE

    def test_appointment_without_plan_no_side_effect(
        self, encounter, admin_user, practitioner, clinic
    ):
        """Creating an appointment without treatment_plan does nothing to plans."""
        proposal, _ = _make_proposal_with_line(encounter, admin_user)
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)
        tp = TreatmentPlan.objects.first()

        _make_appointment(
            encounter.patient, practitioner, clinic,
            treatment_plan=None,
        )

        tp.refresh_from_db()
        assert tp.status == TreatmentPlanStatusChoices.DRAFT


# ============================================================================
# 4. Session completion tracking
# ============================================================================

@pytest.mark.django_db
class TestSessionCompletion:
    """Completed appointments increment the plan's completed_sessions counter."""

    def _setup_active_plan(self, encounter, admin_user, practitioner, clinic, *, planned=3):
        proposal, _ = _make_proposal_with_line(
            encounter, admin_user, quantity=planned,
        )
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)
        tp = TreatmentPlan.objects.first()

        # Create & activate via first appointment
        apt = _make_appointment(
            encounter.patient, practitioner, clinic,
            treatment_plan=tp, status='scheduled',
        )
        tp.refresh_from_db()
        assert tp.status == TreatmentPlanStatusChoices.ACTIVE
        return tp, apt

    def test_completing_appointment_increments_sessions(
        self, encounter, admin_user, practitioner, clinic
    ):
        tp, apt = self._setup_active_plan(
            encounter, admin_user, practitioner, clinic, planned=3,
        )

        # Transition through allowed states: scheduled → confirmed → checked_in → completed
        apt.status = 'confirmed'
        apt.save(skip_validation=True)
        apt.status = 'checked_in'
        apt.save(skip_validation=True)
        apt.status = 'completed'
        apt.save(skip_validation=True)

        tp.refresh_from_db()
        assert tp.completed_sessions == 1
        assert tp.status == TreatmentPlanStatusChoices.ACTIVE

    def test_auto_completion_when_all_sessions_done(
        self, encounter, admin_user, practitioner, clinic
    ):
        tp, apt1 = self._setup_active_plan(
            encounter, admin_user, practitioner, clinic, planned=2,
        )

        # Complete first appointment
        apt1.status = 'confirmed'
        apt1.save(skip_validation=True)
        apt1.status = 'checked_in'
        apt1.save(skip_validation=True)
        apt1.status = 'completed'
        apt1.save(skip_validation=True)

        tp.refresh_from_db()
        assert tp.completed_sessions == 1
        assert tp.status == TreatmentPlanStatusChoices.ACTIVE

        # Create & complete second appointment
        apt2 = _make_appointment(
            encounter.patient, practitioner, clinic,
            treatment_plan=tp, status='scheduled', day_offset=2,
        )
        apt2.status = 'confirmed'
        apt2.save(skip_validation=True)
        apt2.status = 'checked_in'
        apt2.save(skip_validation=True)
        apt2.status = 'completed'
        apt2.save(skip_validation=True)

        tp.refresh_from_db()
        assert tp.completed_sessions == 2
        assert tp.status == TreatmentPlanStatusChoices.COMPLETED
        assert tp.completed_at is not None

    def test_completion_no_double_count(
        self, encounter, admin_user, practitioner, clinic
    ):
        """Re-saving an already-completed appointment doesn't re-increment."""
        tp, apt = self._setup_active_plan(
            encounter, admin_user, practitioner, clinic, planned=3,
        )

        # Complete
        apt.status = 'confirmed'
        apt.save(skip_validation=True)
        apt.status = 'checked_in'
        apt.save(skip_validation=True)
        apt.status = 'completed'
        apt.save(skip_validation=True)

        tp.refresh_from_db()
        assert tp.completed_sessions == 1

        # Save again with same status — should NOT increment
        apt.save(skip_validation=True)

        tp.refresh_from_db()
        assert tp.completed_sessions == 1


# ============================================================================
# 5. Cancellation
# ============================================================================

@pytest.mark.django_db
class TestCancellation:
    """TreatmentPlan can be cancelled from draft or active states."""

    def test_cancel_draft_plan(self, encounter, admin_user):
        proposal, _ = _make_proposal_with_line(encounter, admin_user)
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)
        tp = TreatmentPlan.objects.first()

        tp.cancel(reason='Patient changed mind')

        tp.refresh_from_db()
        assert tp.status == TreatmentPlanStatusChoices.CANCELLED
        assert tp.cancelled_at is not None
        assert tp.cancellation_reason == 'Patient changed mind'

    def test_cancel_active_plan(
        self, encounter, admin_user, practitioner, clinic
    ):
        proposal, _ = _make_proposal_with_line(encounter, admin_user)
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)
        tp = TreatmentPlan.objects.first()

        _make_appointment(
            encounter.patient, practitioner, clinic,
            treatment_plan=tp,
        )
        tp.refresh_from_db()
        assert tp.status == TreatmentPlanStatusChoices.ACTIVE

        tp.cancel(reason='Discontinued')

        tp.refresh_from_db()
        assert tp.status == TreatmentPlanStatusChoices.CANCELLED

    def test_cancel_completed_plan_fails(
        self, encounter, admin_user, practitioner, clinic
    ):
        proposal, _ = _make_proposal_with_line(
            encounter, admin_user, quantity=1,
        )
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)
        tp = TreatmentPlan.objects.first()

        # Activate & complete
        apt = _make_appointment(
            encounter.patient, practitioner, clinic,
            treatment_plan=tp,
        )
        apt.status = 'confirmed'
        apt.save(skip_validation=True)
        apt.status = 'checked_in'
        apt.save(skip_validation=True)
        apt.status = 'completed'
        apt.save(skip_validation=True)

        tp.refresh_from_db()
        assert tp.status == TreatmentPlanStatusChoices.COMPLETED

        with pytest.raises(ValidationError, match="Cannot cancel"):
            tp.cancel(reason='Too late')

    def test_cancel_already_cancelled_fails(self, encounter, admin_user):
        proposal, _ = _make_proposal_with_line(encounter, admin_user)
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)
        tp = TreatmentPlan.objects.first()
        tp.cancel()

        with pytest.raises(ValidationError, match="Cannot cancel"):
            tp.cancel(reason='Double cancel')


# ============================================================================
# 6. Immutability
# ============================================================================

@pytest.mark.django_db
class TestImmutability:
    """Terminal plans cannot be modified without update_fields."""

    def test_completed_plan_is_immutable(
        self, encounter, admin_user, practitioner, clinic
    ):
        proposal, _ = _make_proposal_with_line(
            encounter, admin_user, quantity=1,
        )
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)
        tp = TreatmentPlan.objects.first()

        apt = _make_appointment(
            encounter.patient, practitioner, clinic,
            treatment_plan=tp,
        )
        apt.status = 'confirmed'
        apt.save(skip_validation=True)
        apt.status = 'checked_in'
        apt.save(skip_validation=True)
        apt.status = 'completed'
        apt.save(skip_validation=True)

        tp.refresh_from_db()
        assert tp.status == TreatmentPlanStatusChoices.COMPLETED

        tp.package_name = 'Hacked Name'
        with pytest.raises(ValidationError, match="Cannot modify"):
            tp.save()

    def test_cancelled_plan_is_immutable(self, encounter, admin_user):
        proposal, _ = _make_proposal_with_line(encounter, admin_user)
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)
        tp = TreatmentPlan.objects.first()
        tp.cancel()

        tp.package_name = 'Hacked Name'
        with pytest.raises(ValidationError, match="Cannot modify"):
            tp.save()

    def test_update_fields_bypasses_immutability(self, encounter, admin_user):
        proposal, _ = _make_proposal_with_line(encounter, admin_user)
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)
        tp = TreatmentPlan.objects.first()
        tp.cancel()

        tp.cancellation_reason = 'Admin override'
        tp.save(update_fields=['cancellation_reason'])  # should not raise

        tp.refresh_from_db()
        assert tp.cancellation_reason == 'Admin override'


# ============================================================================
# 7. Blocking: session on non-active plan
# ============================================================================

@pytest.mark.django_db
class TestSessionBlocking:
    """record_session_completed only works on ACTIVE plans."""

    def test_session_on_draft_fails(self, encounter, admin_user):
        proposal, _ = _make_proposal_with_line(encounter, admin_user)
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)
        tp = TreatmentPlan.objects.first()
        assert tp.status == TreatmentPlanStatusChoices.DRAFT

        with pytest.raises(ValidationError, match="Only ACTIVE"):
            tp.record_session_completed()

    def test_session_on_completed_fails(
        self, encounter, admin_user, practitioner, clinic
    ):
        proposal, _ = _make_proposal_with_line(
            encounter, admin_user, quantity=1,
        )
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)
        tp = TreatmentPlan.objects.first()

        apt = _make_appointment(
            encounter.patient, practitioner, clinic,
            treatment_plan=tp,
        )
        apt.status = 'confirmed'
        apt.save(skip_validation=True)
        apt.status = 'checked_in'
        apt.save(skip_validation=True)
        apt.status = 'completed'
        apt.save(skip_validation=True)

        tp.refresh_from_db()
        assert tp.status == TreatmentPlanStatusChoices.COMPLETED

        with pytest.raises(ValidationError, match="Only ACTIVE"):
            tp.record_session_completed()

    def test_activate_cancelled_plan_fails(self, encounter, admin_user):
        proposal, _ = _make_proposal_with_line(encounter, admin_user)
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)
        tp = TreatmentPlan.objects.first()
        tp.cancel()

        with pytest.raises(ValidationError, match="Cannot activate"):
            tp.activate()


# ============================================================================
# 8. Computed properties
# ============================================================================

@pytest.mark.django_db
class TestComputedProperties:
    """Test remaining_sessions, progress_percent, is_terminal."""

    def test_remaining_sessions(self, encounter, admin_user):
        proposal, _ = _make_proposal_with_line(
            encounter, admin_user, quantity=5,
        )
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)
        tp = TreatmentPlan.objects.first()

        assert tp.remaining_sessions == 5
        assert tp.progress_percent == pytest.approx(0.0)

    def test_progress_after_sessions(
        self, encounter, admin_user, practitioner, clinic
    ):
        proposal, _ = _make_proposal_with_line(
            encounter, admin_user, quantity=4,
        )
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)
        tp = TreatmentPlan.objects.first()

        # Activate
        apt = _make_appointment(
            encounter.patient, practitioner, clinic,
            treatment_plan=tp,
        )
        # Complete one session
        apt.status = 'confirmed'
        apt.save(skip_validation=True)
        apt.status = 'checked_in'
        apt.save(skip_validation=True)
        apt.status = 'completed'
        apt.save(skip_validation=True)

        tp.refresh_from_db()
        assert tp.remaining_sessions == 3
        assert tp.progress_percent == pytest.approx(25.0)

    def test_is_terminal(self, encounter, admin_user):
        proposal, _ = _make_proposal_with_line(encounter, admin_user)
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)
        tp = TreatmentPlan.objects.first()

        assert tp.is_terminal is False

        tp.cancel()
        tp.refresh_from_db()
        assert tp.is_terminal is True

    def test_str_representation(self, encounter, admin_user):
        proposal, _ = _make_proposal_with_line(encounter, admin_user, quantity=5)
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)
        tp = TreatmentPlan.objects.first()

        expected = "Laser Package — 0/5 sessions (draft)"
        assert str(tp) == expected
