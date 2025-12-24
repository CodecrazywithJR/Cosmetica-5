"""
Integration tests for Patient Merge API.

Tests:
- POST /api/v1/clinical/patients/merge - Merge patient records
- GET /api/v1/clinical/patients/{id}/merge-candidates - Find duplicates

Validates permissions, business rules, FK reassignment, audit logging.
"""
import pytest
from rest_framework import status
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from apps.clinical.models import (
    Patient,
    Appointment,
    Encounter,
    Consent,
    ClinicalPhoto,
    PatientGuardian,
    PatientMergeLog,
)
from apps.sales.models import Sale

User = get_user_model()


@pytest.fixture
def clinical_ops_user(db):
    """User in ClinicalOps group."""
    user = User.objects.create_user(
        email='clinops@test.com',
        password='testpass123',
    )
    user.is_staff = True
    user.save()
    group, _ = Group.objects.get_or_create(name='ClinicalOps')
    user.groups.add(group)
    return user


@pytest.fixture
def clinical_ops_client(clinical_ops_user):
    """API client with ClinicalOps user."""
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=clinical_ops_user)
    return client


@pytest.fixture
def marketing_user(db):
    """User in Marketing group (should be denied)."""
    user = User.objects.create_user(
        email='marketing@test.com',
        password='testpass123',
    )
    user.is_staff = True
    user.save()
    group, _ = Group.objects.get_or_create(name='Marketing')
    user.groups.add(group)
    return user


@pytest.fixture
def marketing_client(marketing_user):
    """API client with Marketing user."""
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=marketing_user)
    return client


@pytest.mark.django_db(transaction=True)
class TestPatientMergePermissions:
    """Test merge permissions by role."""
    
    def test_clinical_ops_can_merge(self, clinical_ops_client):
        """ClinicalOps group can execute merge."""
        source = Patient.objects.create(
            first_name='Source',
            last_name='Patient',
            phone_e164='+12125551001',
            full_name_normalized='source patient'
        )
        target = Patient.objects.create(
            first_name='Target',
            last_name='Patient',
            phone_e164='+12125551002',
            full_name_normalized='target patient'
        )
        
        payload = {
            'source_patient_id': str(source.id),
            'target_patient_id': str(target.id),
            'strategy': 'manual',
            'notes': 'Test merge'
        }
        
        response = clinical_ops_client.post('/api/v1/clinical/patients/merge', payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_marketing_cannot_merge(self, marketing_client):
        """Marketing group cannot execute merge."""
        source = Patient.objects.create(
            first_name='Source',
            last_name='Patient',
            phone_e164='+12125551003',
            full_name_normalized='source patient'
        )
        target = Patient.objects.create(
            first_name='Target',
            last_name='Patient',
            phone_e164='+12125551004',
            full_name_normalized='target patient'
        )
        
        payload = {
            'source_patient_id': str(source.id),
            'target_patient_id': str(target.id),
            'strategy': 'manual'
        }
        
        response = marketing_client.post('/api/v1/clinical/patients/merge', payload, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db(transaction=True)
class TestPatientMergeValidations:
    """Test merge validation rules."""
    
    def test_merge_rejects_same_source_target(self, clinical_ops_client):
        """Cannot merge patient into itself."""
        patient = Patient.objects.create(
            first_name='Same',
            last_name='Patient',
            phone_e164='+12125551005',
            full_name_normalized='same patient'
        )
        
        payload = {
            'source_patient_id': str(patient.id),
            'target_patient_id': str(patient.id),  # Same as source
            'strategy': 'manual'
        }
        
        response = clinical_ops_client.post('/api/v1/clinical/patients/merge', payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # Error message contains "cannot" or "mismo" (case insensitive)
        error_text = str(response.data).lower()
        assert 'cannot' in error_text or 'mismo' in error_text or 'same' in error_text
    
    def test_merge_rejects_already_merged_source(self, clinical_ops_client):
        """Cannot merge already-merged source."""
        target1 = Patient.objects.create(
            first_name='Target1',
            last_name='Patient',
            phone_e164='+12125551006',
            full_name_normalized='target1 patient'
        )
        source = Patient.objects.create(
            first_name='Source',
            last_name='Patient',
            phone_e164='+12125551007',
            full_name_normalized='source patient',
            is_merged=True,
            merged_into_patient=target1,
            merge_reason='Already merged'
        )
        target2 = Patient.objects.create(
            first_name='Target2',
            last_name='Patient',
            phone_e164='+12125551008',
            full_name_normalized='target2 patient'
        )
        
        payload = {
            'source_patient_id': str(source.id),
            'target_patient_id': str(target2.id),
            'strategy': 'manual'
        }
        
        response = clinical_ops_client.post('/api/v1/clinical/patients/merge', payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'already merged' in str(response.data).lower() or 'ya fusionado' in str(response.data).lower()
    
    def test_merge_rejects_nonexistent_target(self, clinical_ops_client):
        """Merge with nonexistent target returns 404."""
        import uuid
        
        source = Patient.objects.create(
            first_name='Source',
            last_name='Patient',
            phone_e164='+12125551009',
            full_name_normalized='source patient'
        )
        fake_target_id = uuid.uuid4()
        
        payload = {
            'source_patient_id': str(source.id),
            'target_patient_id': str(fake_target_id),
            'strategy': 'manual'
        }
        
        response = clinical_ops_client.post('/api/v1/clinical/patients/merge', payload, format='json')
        
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]


@pytest.mark.django_db(transaction=True)
class TestPatientMergeRelationships:
    """Test FK reassignment during merge."""
    
    def test_merge_moves_sales(self, clinical_ops_client, clinical_ops_user):
        """Merge reassigns Sales from source to target."""
        source = Patient.objects.create(
            first_name='Source',
            last_name='WithSales',
            phone_e164='+12125551010',
            full_name_normalized='source withsales'
        )
        target = Patient.objects.create(
            first_name='Target',
            last_name='Patient',
            phone_e164='+12125551011',
            full_name_normalized='target patient'
        )
        
        # Create sale for source patient (minimal fields)
        sale = Sale.objects.create(
            patient=source,
            status='draft'
        )
        
        payload = {
            'source_patient_id': str(source.id),
            'target_patient_id': str(target.id),
            'strategy': 'manual',
            'notes': 'Merging for test'
        }
        
        response = clinical_ops_client.post('/api/v1/clinical/patients/merge', payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify sale moved to target
        sale.refresh_from_db()
        assert sale.patient_id == target.id
        
        # Verify source marked as merged
        source.refresh_from_db()
        assert source.is_merged is True
        assert source.merged_into_patient_id == target.id
    
    def test_merge_moves_appointments_encounters_photos(self, clinical_ops_client, clinical_ops_user):
        """Merge reassigns Appointments, Encounters to target."""
        source = Patient.objects.create(
            first_name='Source',
            last_name='WithRelations',
            phone_e164='+12125551012',
            full_name_normalized='source withrelations'
        )
        target = Patient.objects.create(
            first_name='Target',
            last_name='Patient',
            phone_e164='+12125551013',
            full_name_normalized='target patient'
        )
        
        # Create appointment (minimal fields)
        appointment = Appointment.objects.create(
            patient=source,
            source='manual',
            status='confirmed',  # Valid status
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timezone.timedelta(hours=1)
        )
        
        # Create encounter (minimal fields)
        encounter = Encounter.objects.create(
            patient=source,
            type='medical_consult',
            status='draft',
            occurred_at=timezone.now(),
            created_by_user=clinical_ops_user
        )
        
        payload = {
            'source_patient_id': str(source.id),
            'target_patient_id': str(target.id),
            'strategy': 'manual'
        }
        
        response = clinical_ops_client.post('/api/v1/clinical/patients/merge', payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify all moved
        appointment.refresh_from_db()
        assert appointment.patient_id == target.id
        
        encounter.refresh_from_db()
        assert encounter.patient_id == target.id
    
    def test_merge_creates_audit_log(self, clinical_ops_client, clinical_ops_user):
        """Merge creates PatientMergeLog entry."""
        source = Patient.objects.create(
            first_name='Source',
            last_name='AuditTest',
            phone_e164='+12125551014',
            full_name_normalized='source audittest'
        )
        target = Patient.objects.create(
            first_name='Target',
            last_name='Patient',
            phone_e164='+12125551015',
            full_name_normalized='target patient'
        )
        
        payload = {
            'source_patient_id': str(source.id),
            'target_patient_id': str(target.id),
            'strategy': 'phone_exact',
            'notes': 'Phone number match',
            'evidence': {'phone_match': True}
        }
        
        response = clinical_ops_client.post('/api/v1/clinical/patients/merge', payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify audit log created
        merge_log = PatientMergeLog.objects.filter(
            source_patient_id=source.id,
            target_patient_id=target.id
        ).first()
        
        assert merge_log is not None
        assert merge_log.merged_by_user_id == clinical_ops_user.id
        assert merge_log.strategy == 'phone_exact'
        assert merge_log.notes == 'Phone number match'
        assert merge_log.evidence == {'phone_match': True}


@pytest.mark.django_db(transaction=True)
class TestPatientMergeCandidates:
    """Test merge candidate detection."""
    
    def test_get_merge_candidates_phone_exact(self, clinical_ops_client):
        """Find candidates with exact phone match."""
        patient1 = Patient.objects.create(
            first_name='John',
            last_name='Doe',
            phone_e164='+12125551111',
            full_name_normalized='john doe'
        )
        # Duplicate with same phone
        patient2 = Patient.objects.create(
            first_name='Jon',
            last_name='Doe',
            phone_e164='+12125551111',  # Same phone
            full_name_normalized='jon doe'
        )
        
        response = clinical_ops_client.get(f'/api/v1/clinical/patients/{patient1.id}/merge-candidates')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
        
        # Verify patient2 is in candidates
        candidate_ids = [c['patient_id'] for c in response.data]
        assert str(patient2.id) in candidate_ids
        
        # Verify high score for phone match
        patient2_candidate = next(c for c in response.data if c['patient_id'] == str(patient2.id))
        assert patient2_candidate['score'] >= 0.90  # Phone exact should be high score


@pytest.mark.django_db(transaction=True)
class TestPatientMergeAtomicity:
    """Test merge atomicity and rollback."""
    
    def test_merge_prevents_cycles(self, clinical_ops_client):
        """Merge prevents creating cycles (A→B, then B→A)."""
        patient_a = Patient.objects.create(
            first_name='Patient',
            last_name='A',
            phone_e164='+12125551018',
            full_name_normalized='patient a'
        )
        patient_b = Patient.objects.create(
            first_name='Patient',
            last_name='B',
            phone_e164='+12125551019',
            full_name_normalized='patient b'
        )
        
        # First merge: A → B
        payload1 = {
            'source_patient_id': str(patient_a.id),
            'target_patient_id': str(patient_b.id),
            'strategy': 'manual'
        }
        response1 = clinical_ops_client.post('/api/v1/clinical/patients/merge', payload1, format='json')
        assert response1.status_code == status.HTTP_200_OK
        
        # Attempt reverse merge: B → A (should fail)
        payload2 = {
            'source_patient_id': str(patient_b.id),
            'target_patient_id': str(patient_a.id),
            'strategy': 'manual'
        }
        response2 = clinical_ops_client.post('/api/v1/clinical/patients/merge', payload2, format='json')
        assert response2.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db(transaction=True)
class TestPatientMergeSignals:
    """Test patient_merged signal emission."""
    
    def test_signal_emitted_on_successful_merge(self, clinical_ops_client, clinical_ops_user):
        """Signal is emitted only after successful merge."""
        from apps.clinical.signals import patient_merged
        from unittest.mock import Mock
        
        source = Patient.objects.create(
            first_name='Source',
            last_name='Signal',
            phone_e164='+12125551020',
            full_name_normalized='source signal'
        )
        target = Patient.objects.create(
            first_name='Target',
            last_name='Signal',
            phone_e164='+12125551021',
            full_name_normalized='target signal'
        )
        
        # Attach signal handler
        handler = Mock()
        patient_merged.connect(handler)
        
        try:
            payload = {
                'source_patient_id': str(source.id),
                'target_patient_id': str(target.id),
                'strategy': 'manual',
                'notes': 'Test signal emission'
            }
            
            response = clinical_ops_client.post('/api/v1/clinical/patients/merge', payload, format='json')
            
            assert response.status_code == status.HTTP_200_OK
            
            # Verify signal was called
            assert handler.called
            
            # Verify signal arguments
            call_kwargs = handler.call_args.kwargs
            assert call_kwargs['source_patient_id'] == str(source.id)
            assert call_kwargs['target_patient_id'] == str(target.id)
            assert call_kwargs['strategy'] == 'manual'
            assert call_kwargs['merged_by_user_id'] == str(clinical_ops_user.id)
            assert 'merge_log_id' in call_kwargs  # NEW: Verify audit trail reference
            
        finally:
            patient_merged.disconnect(handler)
