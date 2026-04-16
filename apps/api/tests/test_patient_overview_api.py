"""
Tests for Patient 360 Overview endpoint.

GET /api/v1/clinical/patients/{id}/overview/

RBAC rules:
- admin / practitioner: full patient (incl. notes), full KPIs (incl. clinical)
- reception / accounting: patient WITHOUT notes, KPIs WITHOUT clinical
- marketing: 403
"""
import pytest
from datetime import date
from decimal import Decimal
from django.utils import timezone
from rest_framework import status as http_status

from apps.clinical.models import (
    Patient, PatientInsurance, Encounter, Appointment,
    Treatment, EncounterTreatment,
)
from apps.proposals.models import (
    Proposal, ProposalLine, ProposalStatusChoices, ProposalLineTypeChoices,
)
from apps.sales.models import Sale, SaleStatusChoices
from apps.treatment_plans.models import TreatmentPlan, TreatmentPlanStatusChoices
from tests.conftest import TEST_PASSWORD


def _overview_url(patient_id):
    return f'/api/v1/clinical/patients/{patient_id}/overview/'


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


@pytest.fixture
def practitioner_client_with_le(db):
    """Practitioner client with legal_entity (required by User.save)."""
    from apps.authz.models import User, Role, UserRole, Practitioner, RoleChoices
    le = _get_test_legal_entity()
    user = User.objects.create_user(
        email='practitioner_overview@test.com',
        password=TEST_PASSWORD,
        is_active=True,
        legal_entity=le,
    )
    role, _ = Role.objects.get_or_create(
        name=RoleChoices.PRACTITIONER,
        defaults={'name': RoleChoices.PRACTITIONER},
    )
    UserRole.objects.create(user=user, role=role)
    Practitioner.objects.create(
        user=user,
        display_name='Dr. Overview Practitioner',
        specialty='Dermatology',
        is_active=True,
    )
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ============================================================================
# T1 — Admin sees everything
# ============================================================================

@pytest.mark.django_db
class TestT1_AdminOverview:
    def test_admin_sees_notes(self, admin_client, patient):
        patient.notes = 'Secret clinical note'
        patient.save(update_fields=['notes'])

        resp = admin_client.get(_overview_url(patient.id))
        assert resp.status_code == http_status.HTTP_200_OK
        assert 'notes' in resp.data['patient']
        assert resp.data['patient']['notes'] == 'Secret clinical note'

    def test_admin_sees_clinical_kpis(self, admin_client, patient):
        resp = admin_client.get(_overview_url(patient.id))
        assert resp.status_code == http_status.HTTP_200_OK
        kpis = resp.data['kpis']
        assert 'total_encounters' in kpis
        assert 'active_treatment_plans_count' in kpis
        assert 'proposals_draft_count' in kpis
        assert 'proposals_sent_count' in kpis
        assert 'last_sale_date' in kpis

    def test_admin_shape_complete(self, admin_client, patient):
        resp = admin_client.get(_overview_url(patient.id))
        assert resp.status_code == http_status.HTTP_200_OK
        assert 'patient' in resp.data
        assert 'insurance_active' in resp.data
        assert 'kpis' in resp.data


# ============================================================================
# T2 — Practitioner sees same as admin
# ============================================================================

@pytest.mark.django_db
class TestT2_PractitionerOverview:
    def test_practitioner_sees_notes(self, practitioner_client_with_le, patient):
        patient.notes = 'Clinical note for doctor'
        patient.save(update_fields=['notes'])

        resp = practitioner_client_with_le.get(_overview_url(patient.id))
        assert resp.status_code == http_status.HTTP_200_OK
        assert 'notes' in resp.data['patient']
        assert resp.data['patient']['notes'] == 'Clinical note for doctor'

    def test_practitioner_sees_clinical_kpis(self, practitioner_client_with_le, patient):
        resp = practitioner_client_with_le.get(_overview_url(patient.id))
        assert resp.status_code == http_status.HTTP_200_OK
        kpis = resp.data['kpis']
        assert 'total_encounters' in kpis
        assert 'active_treatment_plans_count' in kpis


# ============================================================================
# T3 — Reception: no notes, no clinical KPIs
# ============================================================================

@pytest.mark.django_db
class TestT3_ReceptionOverview:
    def test_reception_no_notes(self, reception_client, patient):
        patient.notes = 'You should not see this'
        patient.save(update_fields=['notes'])

        resp = reception_client.get(_overview_url(patient.id))
        assert resp.status_code == http_status.HTTP_200_OK
        assert 'notes' not in resp.data['patient']

    def test_reception_no_clinical_kpis(self, reception_client, patient):
        resp = reception_client.get(_overview_url(patient.id))
        assert resp.status_code == http_status.HTTP_200_OK
        kpis = resp.data['kpis']
        assert 'total_encounters' not in kpis
        assert 'active_treatment_plans_count' not in kpis

    def test_reception_has_financial_kpis(self, reception_client, patient):
        resp = reception_client.get(_overview_url(patient.id))
        assert resp.status_code == http_status.HTTP_200_OK
        kpis = resp.data['kpis']
        assert 'proposals_draft_count' in kpis
        assert 'proposals_sent_count' in kpis
        assert 'last_sale_date' in kpis


# ============================================================================
# T4 — Accounting: same restrictions as reception
# ============================================================================

@pytest.mark.django_db
class TestT4_AccountingOverview:
    def test_accounting_no_notes(self, accounting_client, patient):
        patient.notes = 'Hidden from accounting'
        patient.save(update_fields=['notes'])

        resp = accounting_client.get(_overview_url(patient.id))
        assert resp.status_code == http_status.HTTP_200_OK
        assert 'notes' not in resp.data['patient']

    def test_accounting_no_clinical_kpis(self, accounting_client, patient):
        resp = accounting_client.get(_overview_url(patient.id))
        assert resp.status_code == http_status.HTTP_200_OK
        kpis = resp.data['kpis']
        assert 'total_encounters' not in kpis
        assert 'active_treatment_plans_count' not in kpis
        assert 'proposals_draft_count' in kpis
        assert 'proposals_sent_count' in kpis
        assert 'last_sale_date' in kpis


# ============================================================================
# T5 — Marketing: 403
# ============================================================================

@pytest.mark.django_db
class TestT5_MarketingBlocked:
    def test_marketing_forbidden(self, marketing_client, patient):
        resp = marketing_client.get(_overview_url(patient.id))
        assert resp.status_code == http_status.HTTP_403_FORBIDDEN


# ============================================================================
# T6 — Insurance block
# ============================================================================

@pytest.mark.django_db
class TestT6_Insurance:
    def test_active_insurance_returned(self, admin_client, patient):
        PatientInsurance.objects.create(
            patient=patient,
            provider_name='Old Insurer',
            valid_from=date(2024, 1, 1),
            valid_to=date(2024, 12, 31),
            is_active=False,
        )
        active = PatientInsurance.objects.create(
            patient=patient,
            provider_name='Current Insurer',
            member_number='MEM-999',
            valid_from=date(2025, 1, 1),
            is_active=True,
        )

        resp = admin_client.get(_overview_url(patient.id))
        assert resp.status_code == http_status.HTTP_200_OK
        ins = resp.data['insurance_active']
        assert ins is not None
        assert ins['id'] == str(active.id)
        assert ins['provider_name'] == 'Current Insurer'
        assert ins['member_number'] == 'MEM-999'
        assert ins['is_active'] is True

    def test_no_insurance_returns_null(self, admin_client, patient):
        resp = admin_client.get(_overview_url(patient.id))
        assert resp.status_code == http_status.HTTP_200_OK
        assert resp.data['insurance_active'] is None


# ============================================================================
# T7 — KPI correctness
# ============================================================================

@pytest.mark.django_db
class TestT7_KPICorrectness:
    def test_proposal_counts(
        self, admin_client, patient, encounter_factory, practitioner
    ):
        """2 draft, 1 sent, 1 accepted → draft=2, sent=1."""
        # Create encounters for proposals (each proposal needs a unique encounter)
        encs = [encounter_factory(status='finalized') for _ in range(4)]
        le = _get_test_legal_entity()

        statuses = ['draft', 'draft', 'sent', 'accepted']
        for enc, st in zip(encs, statuses):
            Proposal.objects.create(
                encounter=enc,
                patient=patient,
                practitioner=practitioner,
                status=st,
                total_amount=Decimal('100.00'),
                legal_entity=le,
            )

        resp = admin_client.get(_overview_url(patient.id))
        assert resp.status_code == http_status.HTTP_200_OK
        kpis = resp.data['kpis']
        assert kpis['proposals_draft_count'] == 2
        assert kpis['proposals_sent_count'] == 1

    def test_last_sale_date(self, admin_client, patient):
        """Last sale date = most recent created_at."""
        le = _get_test_legal_entity()
        Sale.objects.create(
            legal_entity=le,
            patient=patient,
            subtotal=Decimal('50.00'),
            total=Decimal('50.00'),
        )
        last = Sale.objects.create(
            legal_entity=le,
            patient=patient,
            subtotal=Decimal('200.00'),
            total=Decimal('200.00'),
        )

        resp = admin_client.get(_overview_url(patient.id))
        kpis = resp.data['kpis']
        assert kpis['last_sale_date'] == last.created_at.date().isoformat()

    def test_last_sale_date_null_when_no_sales(self, admin_client, patient):
        resp = admin_client.get(_overview_url(patient.id))
        assert resp.data['kpis']['last_sale_date'] is None

    def test_encounter_count(
        self, admin_client, patient, encounter_factory
    ):
        encounter_factory()
        encounter_factory()

        resp = admin_client.get(_overview_url(patient.id))
        assert resp.data['kpis']['total_encounters'] == 2

    def test_active_treatment_plans_count(
        self, admin_client, patient, encounter_factory, practitioner
    ):
        """Create 2 active + 1 draft TreatmentPlan → count = 2."""
        enc = encounter_factory(status='finalized')
        proposal = Proposal.objects.create(
            encounter=enc,
            patient=patient,
            practitioner=practitioner,
            status='draft',
            total_amount=Decimal('300.00'),
        )

        # Need real Treatment + EncounterTreatment for ProposalLine FKs
        enc_treatments = []
        for i in range(3):
            treatment = Treatment.objects.create(
                name=f'Laser Test {i}',
                default_price=Decimal('100.00'),
            )
            et = EncounterTreatment.objects.create(
                encounter=enc,
                treatment=treatment,
                quantity=5,
                unit_price=Decimal('100.00'),
            )
            enc_treatments.append((et, treatment))

        lines = []
        for i, (et, trt) in enumerate(enc_treatments):
            line = ProposalLine.objects.create(
                proposal=proposal,
                encounter_treatment=et,
                treatment=trt,
                treatment_name=f'Package {i}',
                type=ProposalLineTypeChoices.FULL_PACKAGE,
                quantity=5,
                unit_price=Decimal('100.00'),
                line_total=Decimal('500.00'),
            )
            lines.append(line)

        # Move proposal to accepted AFTER lines are created (save blocks lines on terminal states)
        Proposal.objects.filter(pk=proposal.pk).update(status='accepted')

        le = _get_test_legal_entity()
        sale = Sale.objects.create(
            legal_entity=le,
            patient=patient,
            subtotal=Decimal('1500.00'),
            total=Decimal('1500.00'),
        )

        # 2 active, 1 draft
        TreatmentPlan.objects.create(
            patient=patient,
            practitioner=practitioner,
            proposal=proposal,
            proposal_line=lines[0],
            sale=sale,
            package_name='Laser A',
            planned_sessions=5,
            total_price_snapshot=Decimal('500.00'),
            status=TreatmentPlanStatusChoices.ACTIVE,
        )
        TreatmentPlan.objects.create(
            patient=patient,
            practitioner=practitioner,
            proposal=proposal,
            proposal_line=lines[1],
            sale=sale,
            package_name='Laser B',
            planned_sessions=5,
            total_price_snapshot=Decimal('500.00'),
            status=TreatmentPlanStatusChoices.ACTIVE,
        )
        TreatmentPlan.objects.create(
            patient=patient,
            practitioner=practitioner,
            proposal=proposal,
            proposal_line=lines[2],
            sale=sale,
            package_name='Laser C',
            planned_sessions=5,
            total_price_snapshot=Decimal('500.00'),
            status=TreatmentPlanStatusChoices.DRAFT,
        )

        resp = admin_client.get(_overview_url(patient.id))
        assert resp.data['kpis']['active_treatment_plans_count'] == 2
