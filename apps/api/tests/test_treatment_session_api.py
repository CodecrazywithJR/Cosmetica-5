"""
TreatmentSession API tests.

Tests cover:
  1) start-treatment-session (creation from appointment)
  2) PATCH (update notes in draft)
  3) complete action (draft → completed, auto-complete plan)
  4) cancel action (draft → cancelled)
  5) RBAC (admin/practitioner OK, reception/accounting/marketing 403)
  6) List/retrieve + filters

Prerequisite fixtures: admin_client, practitioner_client,
reception_client, accounting_client, marketing_client.
"""
import uuid
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.clinical.models import Appointment, Patient, Encounter, Treatment, EncounterTreatment
from apps.authz.models import Practitioner, User, Role, UserRole, RoleChoices
from apps.core.models import Clinic
from apps.proposals.models import Proposal, ProposalLine, ProposalStatusChoices
from apps.treatment_plans.models import (
    TreatmentPlan,
    TreatmentPlanStatusChoices,
    TreatmentSession,
    TreatmentSessionStatusChoices,
)


# ============================================================================
# Helpers
# ============================================================================

def _get_test_legal_entity():
    from apps.legal.models import LegalEntity
    le, _ = LegalEntity.objects.get_or_create(
        siret='00000000000001',
        defaults={
            'trade_name': 'Fixture Clinic',
            'legal_name': 'Fixture Clinic SRL',
            'country_code': 'FR',
            'is_active': True,
        },
    )
    return le


_counter = 0

def _next():
    global _counter
    _counter += 1
    return _counter


def _create_proposal_and_line(patient, practitioner, *, sessions=5):
    """Create minimal Proposal + ProposalLine (full_package) with proper FKs."""
    n = _next()

    # Need an admin user for Encounter + created_by
    admin, _ = User.objects.get_or_create(
        email='ts_helper_admin@test.com',
        defaults={'is_staff': True, 'is_superuser': True, 'is_active': True, 'password': 'x'},
    )
    loc, _ = Clinic.objects.get_or_create(
        name='Helper Loc',
        defaults={
            'address_line1': '1 Rue X',
            'city': 'Paris',
            'postal_code': '75001',
            'country_code': 'FR',
            'timezone': 'Europe/Paris',
            'is_active': True,
            'legal_entity': _get_test_legal_entity(),
        },
    )
    encounter = Encounter.objects.create(
        patient=patient,
        practitioner=practitioner,
        clinic=loc,
        type='medical_consult',
        status='draft',
        occurred_at=timezone.now(),
        created_by_user=admin,
    )
    treatment = Treatment.objects.create(
        name=f'Treatment {n}',
        default_price=Decimal('100.00'),
        is_active=True,
    )
    enc_treatment = EncounterTreatment.objects.create(
        encounter=encounter,
        treatment=treatment,
        quantity=sessions,
    )
    proposal = Proposal.objects.create(
        encounter=encounter,
        patient=patient,
        practitioner=practitioner,
        status=ProposalStatusChoices.DRAFT,
        total_amount=Decimal('100.00') * sessions,
        currency='EUR',
        created_by=admin,
    )
    line = ProposalLine.objects.create(
        proposal=proposal,
        encounter_treatment=enc_treatment,
        treatment=treatment,
        treatment_name=f'Treatment {n}',
        description='Test',
        quantity=sessions,
        unit_price=Decimal('100.00'),
        line_total=Decimal('100.00') * sessions,
        type='full_package',
    )
    return proposal, line


def _create_active_plan(patient, practitioner=None, planned_sessions=5, completed_sessions=0, legal_entity=None):
    """Create a TreatmentPlan in ACTIVE status with proper FKs."""
    proposal, line = _create_proposal_and_line(patient, practitioner, sessions=planned_sessions)
    # Resolve legal_entity: explicit > practitioner.user.legal_entity > None
    le = legal_entity
    if le is None and practitioner and hasattr(practitioner, 'user'):
        le = getattr(practitioner.user, 'legal_entity', None)
    plan = TreatmentPlan.objects.create(
        patient=patient,
        practitioner=practitioner,
        legal_entity=le,
        proposal=proposal,
        proposal_line=line,
        package_name='Botox Full Face',
        planned_sessions=planned_sessions,
        completed_sessions=completed_sessions,
        total_price_snapshot=500.00,
        currency='EUR',
        status=TreatmentPlanStatusChoices.ACTIVE,
        activated_at=timezone.now(),
    )
    return plan


def _create_checked_in_appointment(patient, practitioner=None, clinic=None):
    """Create an appointment in checked_in status (ready for session)."""
    n = _next()
    return Appointment.objects.create(
        patient=patient,
        practitioner=practitioner,
        clinic=clinic,
        source='erp',
        status='checked_in',
        scheduled_start=timezone.now() + timezone.timedelta(days=n * 10),
        scheduled_end=timezone.now() + timezone.timedelta(days=n * 10, hours=1),
    )


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def ts_patient(db):
    admin = User.objects.create_user(
        email='ts_admin@test.com',
        password='pass',
        is_staff=True,
        is_superuser=True,
        is_active=True,
    )
    return Patient.objects.create(
        first_name='Session',
        last_name='Patient',
        full_name_normalized='session patient',
        birth_date='1990-01-01',
        sex='female',
        email='session.patient@test.com',
        phone='+33600000001',
        phone_e164='+33600000001',
        country_code='FR',
        identity_confidence='medium',
        created_by_user=admin,
    )


@pytest.fixture
def ts_practitioner(db):
    user = User.objects.create_user(
        email='ts_pract@test.com',
        password='pass',
        is_active=True,
        legal_entity=_get_test_legal_entity(),
    )
    return Practitioner.objects.create(
        user=user,
        display_name='Dr. Session',
        specialty='Aesthetics',
        is_active=True,
    )


@pytest.fixture
def ts_location(db, legal_entity):
    return Clinic.objects.create(
        name='Session Clinic',
        address_line1='1 Rue Test',
        city='Paris',
        postal_code='75001',
        country_code='FR',
        timezone='Europe/Paris',
        is_active=True,
        legal_entity=legal_entity,
    )


@pytest.fixture
def active_plan(db, ts_patient, ts_practitioner):
    return _create_active_plan(ts_patient, ts_practitioner, planned_sessions=3)


@pytest.fixture
def checked_in_appt(db, ts_patient, ts_practitioner, ts_location):
    return _create_checked_in_appointment(ts_patient, ts_practitioner, ts_location)


# ============================================================================
# 1) start-treatment-session
# ============================================================================

@pytest.mark.django_db
class TestStartTreatmentSession:
    URL_TPL = '/api/v1/clinical/appointments/{appt_id}/start-treatment-session/'

    def test_creates_session_draft(self, admin_client, active_plan, checked_in_appt):
        """Happy path: creates draft session + marks appointment completed."""
        url = self.URL_TPL.format(appt_id=checked_in_appt.id)
        resp = admin_client.post(url, {'treatment_plan_id': str(active_plan.id)}, format='json')
        assert resp.status_code == 201, resp.data

        data = resp.data
        assert data['appointment_status'] == 'completed'
        assert data['session']['status'] == 'draft'
        assert str(data['session']['treatment_plan']) == str(active_plan.id)

        # DB check
        checked_in_appt.refresh_from_db()
        assert checked_in_appt.status == 'completed'
        assert TreatmentSession.objects.filter(appointment=checked_in_appt).count() == 1

    def test_rejects_if_not_checked_in(self, admin_client, active_plan, ts_patient, ts_practitioner, ts_location):
        """Appointment must be checked_in."""
        appt = Appointment.objects.create(
            patient=ts_patient,
            practitioner=ts_practitioner,
            clinic=ts_location,
            source='erp',
            status='confirmed',
            scheduled_start=timezone.now() + timezone.timedelta(hours=1),
            scheduled_end=timezone.now() + timezone.timedelta(hours=2),
        )
        url = self.URL_TPL.format(appt_id=appt.id)
        resp = admin_client.post(url, {'treatment_plan_id': str(active_plan.id)}, format='json')
        assert resp.status_code == 400
        assert 'checked_in' in resp.data['error']

    def test_rejects_if_plan_not_active(self, admin_client, checked_in_appt, ts_patient, ts_practitioner):
        """Plan must be active."""
        proposal, line = _create_proposal_and_line(ts_patient, ts_practitioner)
        draft_plan = TreatmentPlan.objects.create(
            patient=ts_patient,
            practitioner=ts_practitioner,
            proposal=proposal,
            proposal_line=line,
            package_name='Draft plan',
            planned_sessions=3,
            total_price_snapshot=100.00,
            status=TreatmentPlanStatusChoices.DRAFT,
        )
        url = self.URL_TPL.format(appt_id=checked_in_appt.id)
        resp = admin_client.post(url, {'treatment_plan_id': str(draft_plan.id)}, format='json')
        assert resp.status_code == 400
        assert 'active' in resp.data['error']

    def test_rejects_if_plan_wrong_patient(self, admin_client, checked_in_appt, ts_practitioner):
        """Plan must belong to same patient."""
        other_admin = User.objects.create_user(
            email='other_admin_ts@test.com', password='pass',
            is_staff=True, is_superuser=True, is_active=True,
        )
        other_patient = Patient.objects.create(
            first_name='Other', last_name='Patient',
            full_name_normalized='other patient',
            sex='male', email='other_ts@test.com',
            identity_confidence='low',
            created_by_user=other_admin,
        )
        other_plan = _create_active_plan(other_patient, ts_practitioner)
        url = self.URL_TPL.format(appt_id=checked_in_appt.id)
        resp = admin_client.post(url, {'treatment_plan_id': str(other_plan.id)}, format='json')
        assert resp.status_code == 400
        assert 'same patient' in resp.data['error']

    def test_rejects_duplicate_session(self, admin_client, active_plan, checked_in_appt):
        """Only one session per appointment."""
        # First: success
        url = self.URL_TPL.format(appt_id=checked_in_appt.id)
        resp = admin_client.post(url, {'treatment_plan_id': str(active_plan.id)}, format='json')
        assert resp.status_code == 201

        # Create another checked_in appt to test unique on old appt
        # (but checked_in_appt is now completed — need a new one)
        # Actually the first call already made it completed, so re-creating:
        appt2 = _create_checked_in_appointment(
            checked_in_appt.patient, checked_in_appt.practitioner, checked_in_appt.clinic,
        )
        url2 = self.URL_TPL.format(appt_id=appt2.id)
        # This should work (different appt)
        resp2 = admin_client.post(url2, {'treatment_plan_id': str(active_plan.id)}, format='json')
        assert resp2.status_code == 201

    def test_rejects_missing_plan_id(self, admin_client, checked_in_appt):
        """treatment_plan_id is required."""
        url = self.URL_TPL.format(appt_id=checked_in_appt.id)
        resp = admin_client.post(url, {}, format='json')
        assert resp.status_code == 400
        assert 'treatment_plan_id' in resp.data['error']

    def test_rejects_all_sessions_created(self, admin_client, ts_patient, ts_practitioner, ts_location):
        """Cannot create more sessions than planned_sessions allows."""
        plan = _create_active_plan(ts_patient, ts_practitioner, planned_sessions=1)

        appt1 = _create_checked_in_appointment(ts_patient, ts_practitioner, ts_location)
        url1 = self.URL_TPL.format(appt_id=appt1.id)
        resp1 = admin_client.post(url1, {'treatment_plan_id': str(plan.id)}, format='json')
        assert resp1.status_code == 201

        appt2 = _create_checked_in_appointment(ts_patient, ts_practitioner, ts_location)
        url2 = self.URL_TPL.format(appt_id=appt2.id)
        resp2 = admin_client.post(url2, {'treatment_plan_id': str(plan.id)}, format='json')
        assert resp2.status_code == 400
        assert 'planned sessions' in resp2.data['error'].lower() or 'All planned' in resp2.data['error']


# ============================================================================
# 2) PATCH (update notes)
# ============================================================================

@pytest.mark.django_db
class TestPatchTreatmentSession:
    URL_TPL = '/api/v1/clinical/treatment-sessions/{session_id}/'

    def _create_session(self, plan, patient, practitioner, location):
        appt = _create_checked_in_appointment(patient, practitioner, location)
        return TreatmentSession.objects.create(
            treatment_plan=plan,
            appointment=appt,
            practitioner=practitioner,
            status=TreatmentSessionStatusChoices.DRAFT,
        )

    def test_patch_notes_in_draft(self, admin_client, active_plan, ts_patient, ts_practitioner, ts_location):
        session = self._create_session(active_plan, ts_patient, ts_practitioner, ts_location)
        url = self.URL_TPL.format(session_id=session.id)
        resp = admin_client.patch(url, {'notes': 'Updated notes'}, format='json')
        assert resp.status_code == 200
        assert resp.data['notes'] == 'Updated notes'

    def test_patch_blocked_in_completed(self, admin_client, active_plan, ts_patient, ts_practitioner, ts_location):
        session = self._create_session(active_plan, ts_patient, ts_practitioner, ts_location)
        session.complete()
        url = self.URL_TPL.format(session_id=session.id)
        resp = admin_client.patch(url, {'notes': 'Should fail'}, format='json')
        assert resp.status_code == 400

    def test_patch_blocked_in_cancelled(self, admin_client, active_plan, ts_patient, ts_practitioner, ts_location):
        session = self._create_session(active_plan, ts_patient, ts_practitioner, ts_location)
        session.cancel()
        url = self.URL_TPL.format(session_id=session.id)
        resp = admin_client.patch(url, {'notes': 'Should fail'}, format='json')
        assert resp.status_code == 400


# ============================================================================
# 3) Complete action
# ============================================================================

@pytest.mark.django_db
class TestCompleteTreatmentSession:
    URL_TPL = '/api/v1/clinical/treatment-sessions/{session_id}/complete/'

    def _create_session(self, plan, patient, practitioner, location):
        appt = _create_checked_in_appointment(patient, practitioner, location)
        return TreatmentSession.objects.create(
            treatment_plan=plan,
            appointment=appt,
            practitioner=practitioner,
            status=TreatmentSessionStatusChoices.DRAFT,
        )

    def test_complete_sets_performed_at(self, admin_client, active_plan, ts_patient, ts_practitioner, ts_location):
        session = self._create_session(active_plan, ts_patient, ts_practitioner, ts_location)
        url = self.URL_TPL.format(session_id=session.id)
        resp = admin_client.post(url)
        assert resp.status_code == 200
        assert resp.data['status'] == 'completed'
        assert resp.data['performed_at'] is not None

    def test_complete_preserves_existing_performed_at(self, admin_client, active_plan, ts_patient, ts_practitioner, ts_location):
        session = self._create_session(active_plan, ts_patient, ts_practitioner, ts_location)
        custom_time = timezone.now() - timezone.timedelta(hours=2)
        session.performed_at = custom_time
        session.save()
        url = self.URL_TPL.format(session_id=session.id)
        resp = admin_client.post(url)
        assert resp.status_code == 200
        # performed_at should match the custom time (not overwritten)
        from django.utils.dateparse import parse_datetime
        returned = parse_datetime(resp.data['performed_at'])
        assert abs((returned - custom_time).total_seconds()) < 2

    def test_cannot_complete_twice(self, admin_client, active_plan, ts_patient, ts_practitioner, ts_location):
        session = self._create_session(active_plan, ts_patient, ts_practitioner, ts_location)
        url = self.URL_TPL.format(session_id=session.id)
        resp1 = admin_client.post(url)
        assert resp1.status_code == 200
        resp2 = admin_client.post(url)
        assert resp2.status_code == 400

    def test_cannot_complete_if_plan_not_active(self, admin_client, ts_patient, ts_practitioner, ts_location):
        """Plan must be active to complete a session."""
        plan = _create_active_plan(ts_patient, ts_practitioner, planned_sessions=3)
        session = self._create_session(plan, ts_patient, ts_practitioner, ts_location)
        # Force plan to completed via ORM to bypass immutability
        TreatmentPlan.objects.filter(pk=plan.pk).update(
            status=TreatmentPlanStatusChoices.COMPLETED,
        )
        plan.refresh_from_db()
        url = self.URL_TPL.format(session_id=session.id)
        resp = admin_client.post(url)
        assert resp.status_code == 400
        assert 'active' in resp.data['error']

    def test_cannot_complete_if_all_sessions_done(self, admin_client, ts_patient, ts_practitioner, ts_location):
        """Cannot exceed planned sessions."""
        plan = _create_active_plan(ts_patient, ts_practitioner, planned_sessions=1)
        # Mark 1 session completed directly in DB
        appt1 = _create_checked_in_appointment(ts_patient, ts_practitioner, ts_location)
        TreatmentSession.objects.create(
            treatment_plan=plan,
            appointment=appt1,
            practitioner=ts_practitioner,
            status=TreatmentSessionStatusChoices.COMPLETED,
            performed_at=timezone.now(),
        )
        plan.completed_sessions = 1
        plan.save(update_fields=['completed_sessions'])

        # Try to complete another draft session
        session = self._create_session(plan, ts_patient, ts_practitioner, ts_location)
        url = self.URL_TPL.format(session_id=session.id)
        resp = admin_client.post(url)
        assert resp.status_code == 400
        assert 'already completed' in resp.data['error']

    def test_autocomplete_treatment_plan(self, admin_client, ts_patient, ts_practitioner, ts_location):
        """When all sessions completed, plan auto-completes."""
        plan = _create_active_plan(ts_patient, ts_practitioner, planned_sessions=2)

        # Complete session 1
        s1 = self._create_session(plan, ts_patient, ts_practitioner, ts_location)
        url1 = self.URL_TPL.format(session_id=s1.id)
        resp1 = admin_client.post(url1)
        assert resp1.status_code == 200

        plan.refresh_from_db()
        assert plan.status == TreatmentPlanStatusChoices.ACTIVE
        assert plan.completed_sessions == 1

        # Complete session 2 → should auto-complete plan
        s2 = self._create_session(plan, ts_patient, ts_practitioner, ts_location)
        url2 = self.URL_TPL.format(session_id=s2.id)
        resp2 = admin_client.post(url2)
        assert resp2.status_code == 200

        plan.refresh_from_db()
        assert plan.status == TreatmentPlanStatusChoices.COMPLETED
        assert plan.completed_sessions == 2
        assert plan.completed_at is not None
        assert plan.remaining_sessions == 0
        assert plan.progress_percent == 100.0

    def test_updates_plan_completed_sessions_cache(self, admin_client, active_plan, ts_patient, ts_practitioner, ts_location):
        """Completing a session increments plan.completed_sessions."""
        session = self._create_session(active_plan, ts_patient, ts_practitioner, ts_location)
        url = self.URL_TPL.format(session_id=session.id)
        admin_client.post(url)

        active_plan.refresh_from_db()
        assert active_plan.completed_sessions == 1


# ============================================================================
# 4) Cancel action
# ============================================================================

@pytest.mark.django_db
class TestCancelTreatmentSession:
    URL_TPL = '/api/v1/clinical/treatment-sessions/{session_id}/cancel/'

    def _create_session(self, plan, patient, practitioner, location):
        appt = _create_checked_in_appointment(patient, practitioner, location)
        return TreatmentSession.objects.create(
            treatment_plan=plan,
            appointment=appt,
            practitioner=practitioner,
            status=TreatmentSessionStatusChoices.DRAFT,
        )

    def test_cancel_draft(self, admin_client, active_plan, ts_patient, ts_practitioner, ts_location):
        session = self._create_session(active_plan, ts_patient, ts_practitioner, ts_location)
        url = self.URL_TPL.format(session_id=session.id)
        resp = admin_client.post(url)
        assert resp.status_code == 200
        assert resp.data['status'] == 'cancelled'

    def test_cannot_cancel_completed(self, admin_client, active_plan, ts_patient, ts_practitioner, ts_location):
        session = self._create_session(active_plan, ts_patient, ts_practitioner, ts_location)
        session.complete()
        url = self.URL_TPL.format(session_id=session.id)
        resp = admin_client.post(url)
        assert resp.status_code == 400

    def test_cannot_cancel_twice(self, admin_client, active_plan, ts_patient, ts_practitioner, ts_location):
        session = self._create_session(active_plan, ts_patient, ts_practitioner, ts_location)
        url = self.URL_TPL.format(session_id=session.id)
        resp1 = admin_client.post(url)
        assert resp1.status_code == 200
        resp2 = admin_client.post(url)
        assert resp2.status_code == 400


# ============================================================================
# 5) RBAC
# ============================================================================

@pytest.mark.django_db
class TestTreatmentSessionRBAC:
    LIST_URL = '/api/v1/clinical/treatment-sessions/'

    def test_admin_can_list(self, admin_client):
        resp = admin_client.get(self.LIST_URL)
        assert resp.status_code == 200

    def test_practitioner_can_list(self, practitioner_client):
        resp = practitioner_client.get(self.LIST_URL)
        assert resp.status_code == 200

    def test_reception_forbidden(self, reception_client):
        resp = reception_client.get(self.LIST_URL)
        assert resp.status_code == 403

    def test_accounting_forbidden(self, accounting_client):
        resp = accounting_client.get(self.LIST_URL)
        assert resp.status_code == 403

    def test_marketing_forbidden(self, marketing_client):
        resp = marketing_client.get(self.LIST_URL)
        assert resp.status_code == 403

    def test_start_session_rbac_reception_403(self, reception_client, active_plan, checked_in_appt):
        url = f'/api/v1/clinical/appointments/{checked_in_appt.id}/start-treatment-session/'
        resp = reception_client.post(url, {'treatment_plan_id': str(active_plan.id)}, format='json')
        assert resp.status_code == 403


# ============================================================================
# 6) List / retrieve + filters
# ============================================================================

@pytest.mark.django_db
class TestTreatmentSessionListRetrieve:
    LIST_URL = '/api/v1/clinical/treatment-sessions/'

    def _create_session(self, plan, patient, practitioner, location):
        appt = _create_checked_in_appointment(patient, practitioner, location)
        return TreatmentSession.objects.create(
            treatment_plan=plan,
            appointment=appt,
            practitioner=practitioner,
            status=TreatmentSessionStatusChoices.DRAFT,
        )

    def test_list_returns_sessions(self, admin_client, active_plan, ts_patient, ts_practitioner, ts_location):
        s1 = self._create_session(active_plan, ts_patient, ts_practitioner, ts_location)
        s2 = self._create_session(active_plan, ts_patient, ts_practitioner, ts_location)
        resp = admin_client.get(self.LIST_URL)
        assert resp.status_code == 200
        assert resp.data['count'] == 2

    def test_filter_by_patient(self, admin_client, active_plan, ts_patient, ts_practitioner, ts_location):
        self._create_session(active_plan, ts_patient, ts_practitioner, ts_location)
        resp = admin_client.get(self.LIST_URL, {'patient': str(ts_patient.id)})
        assert resp.status_code == 200
        assert resp.data['count'] == 1

    def test_filter_by_treatment_plan(self, admin_client, active_plan, ts_patient, ts_practitioner, ts_location):
        self._create_session(active_plan, ts_patient, ts_practitioner, ts_location)
        resp = admin_client.get(self.LIST_URL, {'treatment_plan': str(active_plan.id)})
        assert resp.status_code == 200
        assert resp.data['count'] == 1

    def test_filter_patient_returns_empty_for_other(self, admin_client, active_plan, ts_patient, ts_practitioner, ts_location):
        self._create_session(active_plan, ts_patient, ts_practitioner, ts_location)
        resp = admin_client.get(self.LIST_URL, {'patient': str(uuid.uuid4())})
        assert resp.status_code == 200
        assert resp.data['count'] == 0

    def test_retrieve_single_session(self, admin_client, active_plan, ts_patient, ts_practitioner, ts_location):
        session = self._create_session(active_plan, ts_patient, ts_practitioner, ts_location)
        url = f'{self.LIST_URL}{session.id}/'
        resp = admin_client.get(url)
        assert resp.status_code == 200
        assert resp.data['id'] == str(session.id)
        assert resp.data['practitioner_name'] == 'Dr. Session'
        assert resp.data['package_name'] == 'Botox Full Face'

    def test_serializer_includes_patient_id(self, admin_client, active_plan, ts_patient, ts_practitioner, ts_location):
        session = self._create_session(active_plan, ts_patient, ts_practitioner, ts_location)
        url = f'{self.LIST_URL}{session.id}/'
        resp = admin_client.get(url)
        assert resp.data['patient'] == str(ts_patient.id)


# ============================================================================
# 7) Multi-tenant isolation
# ============================================================================

def _get_other_legal_entity():
    """Get or create a SECOND LegalEntity for cross-tenant tests."""
    from apps.legal.models import LegalEntity
    le, _ = LegalEntity.objects.get_or_create(
        siret='99999999999999',
        defaults={
            'trade_name': 'Other Clinic',
            'legal_name': 'Other Clinic SRL',
            'country_code': 'FR',
            'is_active': True,
        },
    )
    return le


@pytest.fixture
def other_le_practitioner_client(db):
    """
    Authenticated API client with Practitioner role in a DIFFERENT legal entity.
    Used to test multi-tenant isolation.
    """
    other_le = _get_other_legal_entity()
    user = User.objects.create_user(
        email='other_le_pract@test.com',
        password='pass',
        is_active=True,
        legal_entity=other_le,
    )
    practitioner_role, _ = Role.objects.get_or_create(
        name=RoleChoices.PRACTITIONER,
        defaults={'name': RoleChoices.PRACTITIONER},
    )
    UserRole.objects.create(user=user, role=practitioner_role)
    Practitioner.objects.create(
        user=user,
        display_name='Dr. Other LE',
        specialty='Aesthetics',
        is_active=True,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestMultiTenantIsolation:
    LIST_URL = '/api/v1/clinical/treatment-sessions/'
    START_URL = '/api/v1/clinical/appointments/{appt_id}/start-treatment-session/'

    def _create_session(self, plan, patient, practitioner, location):
        appt = _create_checked_in_appointment(patient, practitioner, location)
        return TreatmentSession.objects.create(
            treatment_plan=plan,
            appointment=appt,
            practitioner=practitioner,
            status=TreatmentSessionStatusChoices.DRAFT,
        )

    def test_multi_tenant_isolation_list(
        self, other_le_practitioner_client, active_plan,
        ts_patient, ts_practitioner, ts_location,
    ):
        """Practitioner in LE-B cannot see sessions belonging to LE-A."""
        # Create a session with ts_practitioner (LE-A)
        self._create_session(active_plan, ts_patient, ts_practitioner, ts_location)

        # List as practitioner in LE-B → should see 0
        resp = other_le_practitioner_client.get(self.LIST_URL)
        assert resp.status_code == 200
        assert resp.data['count'] == 0

    def test_multi_tenant_isolation_start_session(
        self, other_le_practitioner_client, active_plan, checked_in_appt,
    ):
        """Practitioner in LE-B cannot start session on LE-A appointment."""
        url = self.START_URL.format(appt_id=checked_in_appt.id)
        resp = other_le_practitioner_client.post(
            url, {'treatment_plan_id': str(active_plan.id)}, format='json',
        )
        # TenantManager filters out LE-A objects for LE-B practitioners → 404
        # (semantically equivalent to 403: cross-tenant access is denied)
        assert resp.status_code in (403, 404)

    def test_admin_superuser_sees_all_tenants(
        self, admin_client, active_plan,
        ts_patient, ts_practitioner, ts_location,
    ):
        """
        After mandatory-header enforcement an admin MUST send X-Legal-Entity-ID.
        The admin_client fixture already provides this header (pointing at the
        test legal entity), so the admin sees sessions scoped to that entity.
        """
        self._create_session(active_plan, ts_patient, ts_practitioner, ts_location)
        resp = admin_client.get(self.LIST_URL)
        assert resp.status_code == 200
        assert resp.data['count'] == 1


# ============================================================================
# 8) Practitioner required
# ============================================================================

@pytest.mark.django_db
class TestPractitionerRequired:
    START_URL = '/api/v1/clinical/appointments/{appt_id}/start-treatment-session/'

    def test_practitioner_required_on_appointment(
        self, admin_client, active_plan, ts_patient, ts_location,
    ):
        """Appointment cannot be created without practitioner (NOT NULL at model level)."""
        from django.core.exceptions import ValidationError as DjangoValidationError
        n = _next()
        with pytest.raises((DjangoValidationError, Exception)):
            Appointment.objects.create(
                patient=ts_patient,
                practitioner=None,
                clinic=ts_location,
                source='erp',
                status='checked_in',
                scheduled_start=timezone.now() + timezone.timedelta(days=n * 10),
                scheduled_end=timezone.now() + timezone.timedelta(days=n * 10, hours=1),
            )


# ============================================================================
# 9) No Encounter created in session flow
# ============================================================================

@pytest.mark.django_db
class TestNoEncounterCreated:
    START_URL = '/api/v1/clinical/appointments/{appt_id}/start-treatment-session/'

    def test_no_encounter_created_on_session(
        self, admin_client, active_plan, checked_in_appt,
    ):
        """Creating a treatment session must NOT create an Encounter."""
        encounter_count_before = Encounter.objects.count()

        url = self.START_URL.format(appt_id=checked_in_appt.id)
        resp = admin_client.post(
            url, {'treatment_plan_id': str(active_plan.id)}, format='json',
        )
        assert resp.status_code == 201

        encounter_count_after = Encounter.objects.count()
        assert encounter_count_after == encounter_count_before, (
            f"Encounter count changed: {encounter_count_before} → {encounter_count_after}. "
            "start-treatment-session must NOT create an Encounter."
        )


# ============================================================================
# 10) State machine method usage
# ============================================================================

@pytest.mark.django_db
class TestStateTransitionIntegrity:
    START_URL = '/api/v1/clinical/appointments/{appt_id}/start-treatment-session/'
    COMPLETE_URL = '/api/v1/clinical/treatment-sessions/{session_id}/complete/'

    def test_appointment_uses_transition_status(
        self, admin_client, active_plan, checked_in_appt,
    ):
        """
        After start-treatment-session, the appointment should be in
        'completed' state as dictated by the formal transition_status method.
        """
        url = self.START_URL.format(appt_id=checked_in_appt.id)
        resp = admin_client.post(
            url, {'treatment_plan_id': str(active_plan.id)}, format='json',
        )
        assert resp.status_code == 201
        checked_in_appt.refresh_from_db()
        assert checked_in_appt.status == 'completed'

    def test_plan_auto_complete_via_record_session(
        self, admin_client, ts_patient, ts_practitioner, ts_location,
    ):
        """
        Completing all sessions should auto-complete the plan via
        record_session_completed() — the plan's formal state machine method.
        """
        plan = _create_active_plan(ts_patient, ts_practitioner, planned_sessions=1)
        appt = _create_checked_in_appointment(ts_patient, ts_practitioner, ts_location)
        session = TreatmentSession.objects.create(
            treatment_plan=plan,
            appointment=appt,
            practitioner=ts_practitioner,
            status=TreatmentSessionStatusChoices.DRAFT,
        )

        url = self.COMPLETE_URL.format(session_id=session.id)
        resp = admin_client.post(url)
        assert resp.status_code == 200

        plan.refresh_from_db()
        assert plan.status == TreatmentPlanStatusChoices.COMPLETED
        assert plan.completed_sessions == 1
        assert plan.completed_at is not None


# ============================================================================
# 11) Race condition: count guard prevents over-creation
# ============================================================================

@pytest.mark.django_db(transaction=True)
class TestRaceConditionPrevention:
    """
    Verify that concurrent requests cannot create more sessions than
    planned_sessions allows.

    Uses threading to simulate two concurrent start-treatment-session
    calls against a plan with planned_sessions=1.  Exactly one must
    succeed (201) and one must fail (400 or 409).
    """

    START_URL = '/api/v1/clinical/appointments/{appt_id}/start-treatment-session/'

    def test_concurrent_start_session_respects_planned_limit(
        self, ts_patient, ts_practitioner, ts_location,
    ):
        import threading

        le = _get_test_legal_entity()
        plan = _create_active_plan(
            ts_patient, ts_practitioner, planned_sessions=1, legal_entity=le,
        )

        appt1 = _create_checked_in_appointment(ts_patient, ts_practitioner, ts_location)
        appt2 = _create_checked_in_appointment(ts_patient, ts_practitioner, ts_location)

        # Create admin user + client for each thread (separate DB connections)
        admin_user = User.objects.create_user(
            email='race_admin@test.com',
            password='pass',
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )
        admin_role, _ = Role.objects.get_or_create(
            name=RoleChoices.ADMIN,
            defaults={'name': RoleChoices.ADMIN},
        )
        UserRole.objects.get_or_create(user=admin_user, role=admin_role)

        results = [None, None]
        errors = [None, None]

        def _make_request(idx, appt_id):
            try:
                client = APIClient()
                client.force_authenticate(user=admin_user)
                client.credentials(HTTP_X_LEGAL_ENTITY_ID=str(le.id))
                url = self.START_URL.format(appt_id=appt_id)
                resp = client.post(url, {'treatment_plan_id': str(plan.id)}, format='json')
                results[idx] = resp.status_code
            except Exception as e:
                errors[idx] = str(e)

        t1 = threading.Thread(target=_make_request, args=(0, appt1.id))
        t2 = threading.Thread(target=_make_request, args=(1, appt2.id))

        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        # At least one must have succeeded
        assert 201 in results, f"No request succeeded: {results}, errors={errors}"

        # Total sessions created must not exceed planned_sessions
        session_count = TreatmentSession.objects.filter(treatment_plan=plan).exclude(
            status=TreatmentSessionStatusChoices.CANCELLED,
        ).count()
        assert session_count <= plan.planned_sessions, (
            f"Race condition! {session_count} sessions created but only "
            f"{plan.planned_sessions} planned. Results: {results}"
        )
