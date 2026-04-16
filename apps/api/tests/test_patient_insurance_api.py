"""
Tests for PatientInsurance CRUD + business rules.

T1: Create first coverage → stays active.
T2: Create second coverage → auto-closes previous (is_active=False, valid_to adjusted).
T3: DB constraint prevents two active simultaneously.
T4: PATCH that would create overlap is rejected.
"""
import pytest
from datetime import date, timedelta
from django.db import IntegrityError
from rest_framework import status as http_status

from apps.clinical.models import Patient, PatientInsurance

# Base URL inside the clinical router: /api/v1/clinical/patient-insurances/
URL = '/api/v1/clinical/patient-insurances/'


@pytest.fixture
def second_patient(db, admin_user):
    """A second patient for isolation tests."""
    return Patient.objects.create(
        first_name='Jane',
        last_name='Smith',
        full_name_normalized='jane smith',
        birth_date='1985-06-20',
        sex='female',
        email='jane.smith@test.com',
        phone='+33600000001',
        phone_e164='+33600000001',
        country_code='FR',
        identity_confidence='medium',
        created_by_user=admin_user,
    )


# ============================================================================
# T1 — Create first coverage → active
# ============================================================================

@pytest.mark.django_db
class TestT1_FirstCoverage:
    def test_create_first_insurance_is_active(self, admin_client, patient):
        payload = {
            'patient': str(patient.id),
            'provider_name': 'AXA Insurance',
            'member_number': 'MEM-001',
            'valid_from': '2025-01-01',
        }
        resp = admin_client.post(URL, payload, format='json')
        assert resp.status_code == http_status.HTTP_201_CREATED, resp.data
        data = resp.data
        assert data['is_active'] is True
        assert data['provider_name'] == 'AXA Insurance'
        assert data['valid_from'] == '2025-01-01'
        assert data['valid_to'] is None

    def test_created_insurance_appears_in_list(self, admin_client, patient):
        admin_client.post(URL, {
            'patient': str(patient.id),
            'provider_name': 'AXA',
            'valid_from': '2025-01-01',
        }, format='json')
        resp = admin_client.get(f'{URL}?patient_id={patient.id}')
        assert resp.status_code == http_status.HTTP_200_OK
        results = resp.data.get('results', resp.data)
        # Ensure at least 1 result
        assert len(results) >= 1


# ============================================================================
# T2 — Create second coverage → auto-close previous
# ============================================================================

@pytest.mark.django_db
class TestT2_AutoClose:
    def test_second_insurance_closes_first(self, admin_client, patient):
        # 1. Create first
        resp1 = admin_client.post(URL, {
            'patient': str(patient.id),
            'provider_name': 'AXA',
            'valid_from': '2025-01-01',
        }, format='json')
        assert resp1.status_code == http_status.HTTP_201_CREATED
        first_id = resp1.data['id']

        # 2. Create second with a later valid_from
        resp2 = admin_client.post(URL, {
            'patient': str(patient.id),
            'provider_name': 'Allianz',
            'valid_from': '2025-06-01',
        }, format='json')
        assert resp2.status_code == http_status.HTTP_201_CREATED
        second_id = resp2.data['id']

        # 3. Verify: new one is active
        assert resp2.data['is_active'] is True

        # 4. Verify: old one is now closed
        first = PatientInsurance.objects.get(pk=first_id)
        assert first.is_active is False
        assert first.valid_to == date(2025, 5, 31)  # new.valid_from - 1 day

    def test_third_insurance_only_one_active(self, admin_client, patient):
        for i, (name, vfrom) in enumerate([
            ('AXA', '2025-01-01'),
            ('Allianz', '2025-06-01'),
            ('MutualSalud', '2025-09-01'),
        ]):
            resp = admin_client.post(URL, {
                'patient': str(patient.id),
                'provider_name': name,
                'valid_from': vfrom,
            }, format='json')
            assert resp.status_code == http_status.HTTP_201_CREATED

        active_count = PatientInsurance.objects.filter(
            patient=patient, is_active=True,
        ).count()
        assert active_count == 1

        last_active = PatientInsurance.objects.get(
            patient=patient, is_active=True,
        )
        assert last_active.provider_name == 'MutualSalud'


# ============================================================================
# T3 — DB constraint: no two active simultaneously
# ============================================================================

@pytest.mark.django_db
class TestT3_UniqueConstraint:
    def test_db_constraint_prevents_two_active(self, patient):
        """Bypass serializer to test raw DB constraint."""
        PatientInsurance.objects.create(
            patient=patient,
            provider_name='AXA',
            valid_from=date(2025, 1, 1),
            is_active=True,
        )
        with pytest.raises(IntegrityError):
            PatientInsurance.objects.create(
                patient=patient,
                provider_name='Allianz',
                valid_from=date(2025, 6, 1),
                is_active=True,
            )

    def test_different_patients_can_both_be_active(self, patient, second_patient):
        """Two different patients can each have an active coverage."""
        ins1 = PatientInsurance.objects.create(
            patient=patient,
            provider_name='AXA',
            valid_from=date(2025, 1, 1),
            is_active=True,
        )
        ins2 = PatientInsurance.objects.create(
            patient=second_patient,
            provider_name='AXA',
            valid_from=date(2025, 1, 1),
            is_active=True,
        )
        assert ins1.is_active is True
        assert ins2.is_active is True


# ============================================================================
# T4 — PATCH must not allow overlaps
# ============================================================================

@pytest.mark.django_db
class TestT4_PatchOverlap:
    def test_patch_creating_overlap_is_rejected(self, admin_client, patient):
        # Two inactive records with non-overlapping ranges
        ins_a = PatientInsurance.objects.create(
            patient=patient,
            provider_name='AXA',
            valid_from=date(2025, 1, 1),
            valid_to=date(2025, 5, 31),
            is_active=False,
        )
        ins_b = PatientInsurance.objects.create(
            patient=patient,
            provider_name='Allianz',
            valid_from=date(2025, 7, 1),
            valid_to=date(2025, 12, 31),
            is_active=False,
        )

        # Try to PATCH ins_a to extend into ins_b's range
        resp = admin_client.patch(
            f'{URL}{ins_a.id}/',
            {'valid_to': '2025-08-01'},
            format='json',
        )
        assert resp.status_code == http_status.HTTP_400_BAD_REQUEST

    def test_patch_valid_to_before_valid_from_rejected(self, admin_client, patient):
        ins = PatientInsurance.objects.create(
            patient=patient,
            provider_name='AXA',
            valid_from=date(2025, 6, 1),
            is_active=True,
        )
        resp = admin_client.patch(
            f'{URL}{ins.id}/',
            {'valid_to': '2025-05-01'},
            format='json',
        )
        assert resp.status_code == http_status.HTTP_400_BAD_REQUEST

    def test_patch_provider_name_succeeds(self, admin_client, patient):
        ins = PatientInsurance.objects.create(
            patient=patient,
            provider_name='AXA',
            valid_from=date(2025, 1, 1),
            is_active=True,
        )
        resp = admin_client.patch(
            f'{URL}{ins.id}/',
            {'provider_name': 'AXA Premium'},
            format='json',
        )
        assert resp.status_code == http_status.HTTP_200_OK
        assert resp.data['provider_name'] == 'AXA Premium'


# ============================================================================
# Permission smoke tests
# ============================================================================

@pytest.mark.django_db
class TestPermissions:
    def test_marketing_cannot_access(self, marketing_client, patient):
        resp = marketing_client.get(f'{URL}?patient_id={patient.id}')
        assert resp.status_code == http_status.HTTP_403_FORBIDDEN

    def test_accounting_can_read(self, accounting_client, patient):
        PatientInsurance.objects.create(
            patient=patient,
            provider_name='AXA',
            valid_from=date(2025, 1, 1),
            is_active=True,
        )
        resp = accounting_client.get(f'{URL}?patient_id={patient.id}')
        assert resp.status_code == http_status.HTTP_200_OK

    def test_accounting_cannot_create(self, accounting_client, patient):
        resp = accounting_client.post(URL, {
            'patient': str(patient.id),
            'provider_name': 'AXA',
            'valid_from': '2025-01-01',
        }, format='json')
        assert resp.status_code == http_status.HTTP_403_FORBIDDEN


# ============================================================================
# T5 — Temporal blindaje: no time-travel on create
# ============================================================================

@pytest.mark.django_db
class TestT5_NoTimeTravel:
    def test_create_with_valid_from_before_latest_rejected(self, admin_client, patient):
        """T1-blindaje: Cannot create coverage going backwards in time."""
        # Create first coverage at 2025-06-01
        resp1 = admin_client.post(URL, {
            'patient': str(patient.id),
            'provider_name': 'AXA',
            'valid_from': '2025-06-01',
        }, format='json')
        assert resp1.status_code == http_status.HTTP_201_CREATED

        # Try to create second with valid_from BEFORE the first → must fail
        resp2 = admin_client.post(URL, {
            'patient': str(patient.id),
            'provider_name': 'Allianz',
            'valid_from': '2025-03-01',
        }, format='json')
        assert resp2.status_code == http_status.HTTP_400_BAD_REQUEST
        assert 'valid_from' in resp2.data

    def test_create_chronology_regression_rejected(self, admin_client, patient):
        """T4-blindaje: Chain of 3, then try to go back → 400."""
        for vfrom in ['2025-01-01', '2025-06-01', '2025-09-01']:
            resp = admin_client.post(URL, {
                'patient': str(patient.id),
                'provider_name': f'Ins-{vfrom}',
                'valid_from': vfrom,
            }, format='json')
            assert resp.status_code == http_status.HTTP_201_CREATED

        # Try to go back to 2025-07-01 (before 2025-09-01)
        resp = admin_client.post(URL, {
            'patient': str(patient.id),
            'provider_name': 'Backward',
            'valid_from': '2025-07-01',
        }, format='json')
        assert resp.status_code == http_status.HTTP_400_BAD_REQUEST

    def test_create_same_date_as_latest_succeeds(self, admin_client, patient):
        """Same valid_from as latest is allowed (replacement, not regression)."""
        resp1 = admin_client.post(URL, {
            'patient': str(patient.id),
            'provider_name': 'AXA',
            'valid_from': '2025-06-01',
        }, format='json')
        assert resp1.status_code == http_status.HTTP_201_CREATED

        resp2 = admin_client.post(URL, {
            'patient': str(patient.id),
            'provider_name': 'Allianz',
            'valid_from': '2025-06-01',
        }, format='json')
        assert resp2.status_code == http_status.HTTP_201_CREATED


# ============================================================================
# T6 — PATCH hardening
# ============================================================================

@pytest.mark.django_db
class TestT6_PatchHardening:
    def test_patch_valid_from_on_historical_rejected(self, admin_client, patient):
        """T2-blindaje: Cannot PATCH valid_from on non-most-recent coverage."""
        # Create two coverages in order
        resp1 = admin_client.post(URL, {
            'patient': str(patient.id),
            'provider_name': 'AXA',
            'valid_from': '2025-01-01',
        }, format='json')
        assert resp1.status_code == http_status.HTTP_201_CREATED
        first_id = resp1.data['id']

        resp2 = admin_client.post(URL, {
            'patient': str(patient.id),
            'provider_name': 'Allianz',
            'valid_from': '2025-06-01',
        }, format='json')
        assert resp2.status_code == http_status.HTTP_201_CREATED

        # Try to PATCH valid_from on the first (now historical) → must fail
        resp = admin_client.patch(
            f'{URL}{first_id}/',
            {'valid_from': '2025-02-01'},
            format='json',
        )
        assert resp.status_code == http_status.HTTP_400_BAD_REQUEST
        assert 'valid_from' in resp.data

    def test_patch_is_active_rejected(self, admin_client, patient):
        """T3-blindaje: Cannot manually toggle is_active via PATCH."""
        ins = PatientInsurance.objects.create(
            patient=patient,
            provider_name='AXA',
            valid_from=date(2025, 1, 1),
            is_active=True,
        )
        resp = admin_client.patch(
            f'{URL}{ins.id}/',
            {'is_active': False},
            format='json',
        )
        assert resp.status_code == http_status.HTTP_400_BAD_REQUEST
        assert 'is_active' in resp.data

    def test_patch_is_active_true_also_rejected(self, admin_client, patient):
        """Cannot manually re-activate a historical coverage either."""
        ins = PatientInsurance.objects.create(
            patient=patient,
            provider_name='AXA',
            valid_from=date(2025, 1, 1),
            valid_to=date(2025, 5, 31),
            is_active=False,
        )
        resp = admin_client.patch(
            f'{URL}{ins.id}/',
            {'is_active': True},
            format='json',
        )
        assert resp.status_code == http_status.HTTP_400_BAD_REQUEST
        assert 'is_active' in resp.data
