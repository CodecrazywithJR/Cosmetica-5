"""
Tests for Proposal state machine, immutability, and lifecycle.

Covers:
- send()
- accept()
- cancel()
- expire()
- Immutability blocking (accepted/cancelled/expired)
- Acceptance blocked after expiration
- valid_until = created_at + 30 days
- Atomicity of accept()
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
    PROPOSAL_VALIDITY_DAYS,
)


# ============================================================================
# Helpers — minimal factory functions
# ============================================================================

def _make_treatment(admin_user, *, name='Botox', price='150.00'):
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
        trade_name='Test Clinic',
        legal_name='Test Clinic SRL',
        country_code='FR',
        is_active=True,
    )


def _make_proposal(encounter, admin_user, *, status=ProposalStatusChoices.DRAFT):
    """Create a proposal with one line so accept() won't fail on empty lines."""
    treatment = _make_treatment(admin_user)
    enc_treatment = _make_encounter_treatment(encounter, treatment, quantity=2)

    proposal = Proposal.objects.create(
        encounter=encounter,
        patient=encounter.patient,
        practitioner=encounter.practitioner,
        status=status,
        total_amount=Decimal('300.00'),
        currency='EUR',
        created_by=admin_user,
    )
    ProposalLine.objects.create(
        proposal=proposal,
        encounter_treatment=enc_treatment,
        treatment=treatment,
        treatment_name=treatment.name,
        quantity=2,
        unit_price=Decimal('150.00'),
        line_total=Decimal('300.00'),
    )
    return proposal


# ============================================================================
# 1. send() tests
# ============================================================================

@pytest.mark.django_db
class TestProposalSend:
    """Tests for Proposal.send()."""

    def test_send_from_draft(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        assert proposal.status == ProposalStatusChoices.DRAFT
        assert proposal.sent_at is None

        proposal.send(user=admin_user)

        proposal.refresh_from_db()
        assert proposal.status == ProposalStatusChoices.SENT
        assert proposal.sent_at is not None

    def test_send_from_non_draft_raises(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        proposal.send(user=admin_user)  # → sent

        with pytest.raises(ValidationError, match="Cannot send"):
            proposal.send(user=admin_user)  # already sent

    def test_send_from_cancelled_raises(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        proposal.cancel(user=admin_user)

        with pytest.raises(ValidationError, match="Cannot send"):
            proposal.send(user=admin_user)


# ============================================================================
# 2. accept() tests
# ============================================================================

@pytest.mark.django_db
class TestProposalAccept:
    """Tests for Proposal.accept()."""

    def test_accept_from_sent(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        proposal.send(user=admin_user)

        legal_entity = _make_legal_entity()
        sale = proposal.accept(user=admin_user, legal_entity=legal_entity)

        proposal.refresh_from_db()
        assert proposal.status == ProposalStatusChoices.ACCEPTED
        assert proposal.accepted_at is not None
        assert proposal.accepted_by == admin_user
        assert proposal.converted_to_sale == sale
        assert proposal.converted_at is not None
        assert sale is not None
        assert sale.status == 'draft'
        assert sale.total == proposal.total_amount
        assert sale.lines.count() == proposal.lines.count()

    def test_accept_from_draft_raises(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        legal_entity = _make_legal_entity()

        with pytest.raises(ValidationError, match="Cannot accept"):
            proposal.accept(user=admin_user, legal_entity=legal_entity)

    def test_accept_requires_legal_entity(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        proposal.send(user=admin_user)

        with pytest.raises(ValidationError, match="legal_entity is required"):
            proposal.accept(user=admin_user, legal_entity=None)

    def test_accept_blocked_when_expired(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        proposal.send(user=admin_user)

        # Force valid_until to the past
        Proposal.objects.filter(pk=proposal.pk).update(
            valid_until=timezone.now() - timedelta(hours=1)
        )
        proposal.refresh_from_db()

        legal_entity = _make_legal_entity()
        with pytest.raises(ValidationError, match="expired"):
            proposal.accept(user=admin_user, legal_entity=legal_entity)

        # After the failed accept, status should be expired
        proposal.refresh_from_db()
        assert proposal.status == ProposalStatusChoices.EXPIRED

    def test_accept_atomicity_creates_sale_and_lines(self, encounter, admin_user):
        """accept() creates Sale + SaleLines in one atomic transaction."""
        proposal = _make_proposal(encounter, admin_user)
        proposal.send(user=admin_user)

        legal_entity = _make_legal_entity()
        sale = proposal.accept(user=admin_user, legal_entity=legal_entity)

        from apps.sales.models import Sale, SaleLine
        assert Sale.objects.filter(pk=sale.pk).exists()
        assert SaleLine.objects.filter(sale=sale).count() == 1
        line = SaleLine.objects.get(sale=sale)
        assert line.product is None
        assert line.quantity == 2
        assert line.unit_price == Decimal('150.00')
        assert line.line_total == Decimal('300.00')


# ============================================================================
# 3. cancel() tests
# ============================================================================

@pytest.mark.django_db
class TestProposalCancel:
    """Tests for Proposal.cancel()."""

    def test_cancel_from_draft(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        proposal.cancel(user=admin_user, reason='Changed mind')

        proposal.refresh_from_db()
        assert proposal.status == ProposalStatusChoices.CANCELLED
        assert proposal.cancellation_reason == 'Changed mind'

    def test_cancel_from_sent(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        proposal.send(user=admin_user)
        proposal.cancel(user=admin_user)

        proposal.refresh_from_db()
        assert proposal.status == ProposalStatusChoices.CANCELLED

    def test_cancel_from_accepted_raises(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        proposal.send(user=admin_user)

        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)

        with pytest.raises(ValidationError, match="Cannot cancel"):
            proposal.cancel(user=admin_user)

    def test_cancel_from_expired_raises(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        proposal.expire()

        with pytest.raises(ValidationError, match="Cannot cancel"):
            proposal.cancel(user=admin_user)


# ============================================================================
# 4. expire() tests
# ============================================================================

@pytest.mark.django_db
class TestProposalExpire:
    """Tests for Proposal.expire()."""

    def test_expire_from_draft(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        proposal.expire()

        proposal.refresh_from_db()
        assert proposal.status == ProposalStatusChoices.EXPIRED

    def test_expire_from_sent(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        proposal.send(user=admin_user)
        proposal.expire()

        proposal.refresh_from_db()
        assert proposal.status == ProposalStatusChoices.EXPIRED

    def test_expire_from_accepted_raises(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        proposal.send(user=admin_user)

        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)

        with pytest.raises(ValidationError, match="Cannot expire"):
            proposal.expire()

    def test_expire_from_cancelled_raises(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        proposal.cancel(user=admin_user)

        with pytest.raises(ValidationError, match="Cannot expire"):
            proposal.expire()


# ============================================================================
# 5. Immutability blocking
# ============================================================================

@pytest.mark.django_db
class TestProposalImmutability:
    """Proposals in terminal states cannot be edited."""

    def test_cannot_edit_accepted_proposal(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        proposal.send(user=admin_user)
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)

        proposal.notes = 'Trying to edit'
        with pytest.raises(ValidationError, match="Cannot modify"):
            proposal.save()

    def test_cannot_edit_cancelled_proposal(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        proposal.cancel(user=admin_user)

        proposal.notes = 'Trying to edit'
        with pytest.raises(ValidationError, match="Cannot modify"):
            proposal.save()

    def test_cannot_edit_expired_proposal(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        proposal.expire()

        proposal.notes = 'Trying to edit'
        with pytest.raises(ValidationError, match="Cannot modify"):
            proposal.save()

    def test_can_edit_draft_proposal(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        proposal.notes = 'Updated notes'
        proposal.save()  # Should not raise
        proposal.refresh_from_db()
        assert proposal.notes == 'Updated notes'

    def test_cannot_edit_line_on_accepted_proposal(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        proposal.send(user=admin_user)
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)

        line = proposal.lines.first()
        line.quantity = 99
        with pytest.raises(ValidationError, match="Cannot modify lines"):
            line.save()

    def test_cannot_delete_line_on_accepted_proposal(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        proposal.send(user=admin_user)
        legal_entity = _make_legal_entity()
        proposal.accept(user=admin_user, legal_entity=legal_entity)

        line = proposal.lines.first()
        with pytest.raises(ValidationError, match="Cannot delete lines"):
            line.delete()


# ============================================================================
# 6. valid_until default
# ============================================================================

@pytest.mark.django_db
class TestProposalValidUntil:
    """valid_until defaults to created_at + 30 days."""

    def test_valid_until_auto_set(self, encounter, admin_user):
        proposal = _make_proposal(encounter, admin_user)
        proposal.refresh_from_db()

        expected = proposal.created_at + timedelta(days=PROPOSAL_VALIDITY_DAYS)
        # Allow 1 second tolerance
        assert abs((proposal.valid_until - expected).total_seconds()) < 1

    def test_valid_until_explicit_override(self, encounter, admin_user):
        custom_deadline = timezone.now() + timedelta(days=7)
        treatment = _make_treatment(admin_user)
        enc_treatment = _make_encounter_treatment(encounter, treatment)

        proposal = Proposal.objects.create(
            encounter=encounter,
            patient=encounter.patient,
            practitioner=encounter.practitioner,
            status=ProposalStatusChoices.DRAFT,
            total_amount=Decimal('150.00'),
            currency='EUR',
            valid_until=custom_deadline,
            created_by=admin_user,
        )
        proposal.refresh_from_db()
        assert abs((proposal.valid_until - custom_deadline).total_seconds()) < 1


# ============================================================================
# 7. Status choices enum
# ============================================================================

@pytest.mark.django_db
class TestProposalStatusChoices:
    """Verify all five status values exist and old 'converted' is gone."""

    def test_all_statuses_exist(self):
        values = {c.value for c in ProposalStatusChoices}
        assert values == {'draft', 'sent', 'accepted', 'cancelled', 'expired'}

    def test_converted_removed(self):
        values = {c.value for c in ProposalStatusChoices}
        assert 'converted' not in values
