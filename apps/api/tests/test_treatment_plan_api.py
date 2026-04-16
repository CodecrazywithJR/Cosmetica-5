"""
Tests for TreatmentPlan read-only API.

T1-T5: RBAC (5 roles)
T6-T7: Query-param filters (patient, status)
T8-T9: Computed fields (remaining_sessions, progress_percent)
T10:   Division-by-zero guard (planned_sessions == 0 edge-case)

Endpoint: GET /api/v1/clinical/treatment-plans/
"""
import pytest
from decimal import Decimal
from rest_framework import status as http_status

from apps.clinical.models import (
    Patient,
    Encounter,
    Treatment,
    EncounterTreatment,
)
from apps.proposals.models import Proposal, ProposalLine
from apps.treatment_plans.models import TreatmentPlan

URL = '/api/v1/clinical/treatment-plans/'


# ============================================================================
# Shared fixture — full object chain for TreatmentPlan
# ============================================================================

@pytest.fixture
def treatment_catalog(db):
    """A catalog treatment entry."""
    return Treatment.objects.create(
        name='Botox Package',
        description='Full-face botox package',
        is_active=True,
        default_price=Decimal('1200.00'),
    )


@pytest.fixture
def _proposal_chain(db, patient, encounter, practitioner, treatment_catalog, admin_user):
    """
    Build the full FK chain:
      Encounter → EncounterTreatment → Proposal → ProposalLine

    Returns (proposal, proposal_line) tuple.

    Note: Proposal is created as 'draft' first so ProposalLine.save()
    doesn't reject the insert.  Then we flip to 'accepted' via raw update.
    """
    enc_trt = EncounterTreatment.objects.create(
        encounter=encounter,
        treatment=treatment_catalog,
        quantity=1,
        unit_price=Decimal('1200.00'),
    )
    proposal = Proposal.objects.create(
        encounter=encounter,
        patient=patient,
        practitioner=practitioner,
        status='draft',
        total_amount=Decimal('1200.00'),
        currency='EUR',
        created_by=admin_user,
    )
    proposal_line = ProposalLine.objects.create(
        proposal=proposal,
        encounter_treatment=enc_trt,
        treatment=treatment_catalog,
        type='full_package',
        treatment_name='Botox Package',
        description='Full-face botox',
        quantity=1,
        unit_price=Decimal('1200.00'),
        line_total=Decimal('1200.00'),
    )
    # Flip to accepted after line creation (bypasses save() guard)
    Proposal.objects.filter(pk=proposal.pk).update(status='accepted')
    proposal.refresh_from_db()
    return proposal, proposal_line


@pytest.fixture
def treatment_plan(db, patient, practitioner, _proposal_chain):
    """A TreatmentPlan with 10 planned / 3 completed sessions."""
    proposal, proposal_line = _proposal_chain
    return TreatmentPlan.objects.create(
        patient=patient,
        practitioner=practitioner,
        proposal=proposal,
        proposal_line=proposal_line,
        package_name='Botox Package',
        planned_sessions=10,
        completed_sessions=3,
        total_price_snapshot=Decimal('1200.00'),
        currency='EUR',
        status='active',
    )


# ============================================================================
# T1 — Admin can list treatment plans (200)
# ============================================================================

@pytest.mark.django_db
class TestT1_AdminAccess:
    def test_admin_can_list(self, admin_client, treatment_plan):
        resp = admin_client.get(URL)
        assert resp.status_code == http_status.HTTP_200_OK
        results = resp.data.get('results', resp.data)
        assert len(results) >= 1
        item = results[0]
        assert item['package_name'] == 'Botox Package'
        assert item['status'] == 'active'

    def test_admin_can_retrieve(self, admin_client, treatment_plan):
        resp = admin_client.get(f'{URL}{treatment_plan.id}/')
        assert resp.status_code == http_status.HTTP_200_OK
        assert resp.data['id'] == str(treatment_plan.id)


# ============================================================================
# T2 — Practitioner can list treatment plans (200)
# ============================================================================

@pytest.mark.django_db
class TestT2_PractitionerAccess:
    def test_practitioner_can_list(self, practitioner_client, treatment_plan):
        resp = practitioner_client.get(URL)
        assert resp.status_code == http_status.HTTP_200_OK
        results = resp.data.get('results', resp.data)
        assert len(results) >= 1


# ============================================================================
# T3 — Reception is blocked (403)
# ============================================================================

@pytest.mark.django_db
class TestT3_ReceptionBlocked:
    def test_reception_gets_403(self, reception_client, treatment_plan):
        resp = reception_client.get(URL)
        assert resp.status_code == http_status.HTTP_403_FORBIDDEN


# ============================================================================
# T4 — Accounting is blocked (403)
# ============================================================================

@pytest.mark.django_db
class TestT4_AccountingBlocked:
    def test_accounting_gets_403(self, accounting_client, treatment_plan):
        resp = accounting_client.get(URL)
        assert resp.status_code == http_status.HTTP_403_FORBIDDEN


# ============================================================================
# T5 — Marketing is blocked (403)
# ============================================================================

@pytest.mark.django_db
class TestT5_MarketingBlocked:
    def test_marketing_gets_403(self, marketing_client, treatment_plan):
        resp = marketing_client.get(URL)
        assert resp.status_code == http_status.HTTP_403_FORBIDDEN


# ============================================================================
# T6 — Filter by patient
# ============================================================================

@pytest.mark.django_db
class TestT6_FilterPatient:
    def test_filter_by_patient_returns_match(self, admin_client, treatment_plan, patient):
        resp = admin_client.get(f'{URL}?patient={patient.id}')
        assert resp.status_code == http_status.HTTP_200_OK
        results = resp.data.get('results', resp.data)
        assert len(results) == 1

    def test_filter_by_other_patient_returns_empty(self, admin_client, treatment_plan, admin_user):
        other = Patient.objects.create(
            first_name='Other',
            last_name='Patient',
            full_name_normalized='other patient',
            sex='female',
            email='other@test.com',
            identity_confidence='low',
            created_by_user=admin_user,
        )
        resp = admin_client.get(f'{URL}?patient={other.id}')
        assert resp.status_code == http_status.HTTP_200_OK
        results = resp.data.get('results', resp.data)
        assert len(results) == 0


# ============================================================================
# T7 — Filter by status
# ============================================================================

@pytest.mark.django_db
class TestT7_FilterStatus:
    def test_filter_active(self, admin_client, treatment_plan):
        resp = admin_client.get(f'{URL}?status=active')
        assert resp.status_code == http_status.HTTP_200_OK
        results = resp.data.get('results', resp.data)
        assert all(r['status'] == 'active' for r in results)
        assert len(results) >= 1

    def test_filter_draft_excludes_active(self, admin_client, treatment_plan):
        resp = admin_client.get(f'{URL}?status=draft')
        assert resp.status_code == http_status.HTTP_200_OK
        results = resp.data.get('results', resp.data)
        assert len(results) == 0   # fixture is 'active'


# ============================================================================
# T8 — Computed field: remaining_sessions
# ============================================================================

@pytest.mark.django_db
class TestT8_RemainingSessions:
    def test_remaining_sessions_calculated(self, admin_client, treatment_plan):
        resp = admin_client.get(f'{URL}{treatment_plan.id}/')
        assert resp.status_code == http_status.HTTP_200_OK
        # planned=10, completed=3 → remaining=7
        assert resp.data['remaining_sessions'] == 7


# ============================================================================
# T9 — Computed field: progress_percent
# ============================================================================

@pytest.mark.django_db
class TestT9_ProgressPercent:
    def test_progress_percent_calculated(self, admin_client, treatment_plan):
        resp = admin_client.get(f'{URL}{treatment_plan.id}/')
        assert resp.status_code == http_status.HTTP_200_OK
        # 3 / 10 * 100 = 30.0
        assert resp.data['progress_percent'] == 30.0


# ============================================================================
# T10 — Division-by-zero guard (planned_sessions == 0)
# ============================================================================

@pytest.mark.django_db
class TestT10_DivisionByZeroGuard:
    def test_zero_planned_returns_zero_percent(self):
        """
        The DB check constraint enforces planned_sessions > 0, so this
        case cannot happen through normal flows.  We verify the serializer
        method directly with a mock-like object to prove the guard works.
        """
        from apps.treatment_plans.serializers import TreatmentPlanListSerializer

        class _FakePlan:
            planned_sessions = 0
            completed_sessions = 0

        ser = TreatmentPlanListSerializer()
        assert ser.get_progress_percent(_FakePlan()) == 0.0
        assert ser.get_remaining_sessions(_FakePlan()) == 0
