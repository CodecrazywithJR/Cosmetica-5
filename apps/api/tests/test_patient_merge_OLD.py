"""
Integration tests for Patient Merge endpoint.

Tests POST /api/v1/patients/{id}/merge/ - Merge patient records.
Validates permissions, business rules, and relationship reassignment.
"""
import pytest
from rest_framework import status
from django.utils import timezone
from apps.clinical.models import (
    Patient,
    Appointment,
    Encounter,
    Consent,
    ClinicalPhoto,
    PatientGuardian,
)


@pytest.mark.django_db(transaction=True)
class TestPatientMergePermissions:
    """Test merge endpoint permissions by role."""
    
    @pytest.mark.parametrize('client_fixture,expected_status', [
        ('admin_client', status.HTTP_200_OK),
        ('practitioner_client', status.HTTP_200_OK),
        ('reception_client', status.HTTP_403_FORBIDDEN),
        ('accounting_client', status.HTTP_403_FORBIDDEN),
        ('marketing_client', status.HTTP_403_FORBIDDEN),
    ])
    def test_merge_permissions_by_role(
        self,
        client_fixture,
        expected_status,
        request,
        patient_factory
    ):
        """Only Admin and Practitioner can merge patients."""
        client = request.getfixturevalue(client_fixture)
        
        source = patient_factory(email='merge_source@test.com')
        target = patient_factory(email='merge_target@test.com')
        
        endpoint = f'/api/v1/patients/{source.id}/merge/'
        payload = {
            'target_patient_id': str(target.id),
            'merge_reason': 'Test merge',
        }
        
        response = client.post(endpoint, payload, format='json')
        
        assert response.status_code == expected_status


@pytest.mark.django_db(transaction=True)
class TestPatientMergeValidations:
    """Test merge endpoint validation rules."""
    
    def test_merge_source_equals_target(self, admin_client, patient):
        """Cannot merge patient into itself (source == target)."""
        endpoint = f'/api/v1/patients/{patient.id}/merge/'
        payload = {
            'target_patient_id': str(patient.id),  # Same as source
            'merge_reason': 'Test',
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'target_patient_id' in str(response.data).lower() or 'mismo' in str(response.data).lower()
    
    def test_merge_source_not_found(self, admin_client, patient):
        """Merge with nonexistent source returns 404."""
        import uuid
        fake_source_id = uuid.uuid4()
        
        endpoint = f'/api/v1/patients/{fake_source_id}/merge/'
        payload = {
            'target_patient_id': str(patient.id),
            'merge_reason': 'Test',
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_merge_target_not_found(self, admin_client, patient):
        """Merge with nonexistent target returns 400."""
        import uuid
        fake_target_id = uuid.uuid4()
        
        endpoint = f'/api/v1/patients/{patient.id}/merge/'
        payload = {
            'target_patient_id': str(fake_target_id),
            'merge_reason': 'Test',
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_merge_source_already_merged(self, admin_client, patient_factory):
        """Cannot merge patient that is already merged."""
        source = patient_factory(email='already_merged@test.com')
        target = patient_factory(email='merge_target1@test.com')
        other_target = patient_factory(email='other_target@test.com')
        
        # Mark source as already merged
        source.is_merged = True
        source.merged_into_patient = other_target
        source.merge_reason = 'Previous merge'
        source.save()
        
        endpoint = f'/api/v1/patients/{source.id}/merge/'
        payload = {
            'target_patient_id': str(target.id),
            'merge_reason': 'Test',
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_409_CONFLICT
        assert 'merged' in str(response.data).lower()
    
    def test_merge_target_already_merged(self, admin_client, patient_factory):
        """Cannot merge into patient that is already merged."""
        source = patient_factory(email='merge_source2@test.com')
        target = patient_factory(email='already_merged_target@test.com')
        other_patient = patient_factory(email='other@test.com')
        
        # Mark target as already merged
        target.is_merged = True
        target.merged_into_patient = other_patient
        target.merge_reason = 'Previous merge'
        target.save()
        
        endpoint = f'/api/v1/patients/{source.id}/merge/'
        payload = {
            'target_patient_id': str(target.id),
            'merge_reason': 'Test',
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_409_CONFLICT
        assert 'merged' in str(response.data).lower()
    
    def test_merge_source_soft_deleted(self, admin_client, patient_factory):
        """Cannot merge soft-deleted source patient."""
        source = patient_factory(email='deleted_source@test.com')
        target = patient_factory(email='merge_target3@test.com')
        
        # Soft delete source
        source.is_deleted = True
        source.deleted_at = timezone.now()
        source.save()
        
        endpoint = f'/api/v1/patients/{source.id}/merge/'
        payload = {
            'target_patient_id': str(target.id),
            'merge_reason': 'Test',
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_409_CONFLICT
        assert 'deleted' in str(response.data).lower() or 'eliminado' in str(response.data).lower()
    
    def test_merge_target_soft_deleted(self, admin_client, patient_factory):
        """Cannot merge into soft-deleted target patient."""
        source = patient_factory(email='merge_source4@test.com')
        target = patient_factory(email='deleted_target@test.com')
        
        # Soft delete target
        target.is_deleted = True
        target.deleted_at = timezone.now()
        target.save()
        
        endpoint = f'/api/v1/patients/{source.id}/merge/'
        payload = {
            'target_patient_id': str(target.id),
            'merge_reason': 'Test',
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_409_CONFLICT
        assert 'deleted' in str(response.data).lower() or 'eliminado' in str(response.data).lower()
    
    def test_merge_missing_target_patient_id(self, admin_client, patient):
        """Merge without target_patient_id returns 400."""
        endpoint = f'/api/v1/patients/{patient.id}/merge/'
        payload = {
            # Missing target_patient_id
            'merge_reason': 'Test',
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_merge_missing_merge_reason(self, admin_client, patient_factory):
        """Merge without merge_reason returns 400."""
        source = patient_factory(email='merge_source5@test.com')
        target = patient_factory(email='merge_target5@test.com')
        
        endpoint = f'/api/v1/patients/{source.id}/merge/'
        payload = {
            'target_patient_id': str(target.id),
            # Missing merge_reason
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db(transaction=True)
class TestPatientMergeRelationships:
    """Test relationship reassignment during merge."""
    
    def test_merge_reassigns_all_relationships(
        self,
        admin_client,
        patient_factory,
        practitioner,
        clinic_location,
        admin_user
    ):
        """Merge reassigns Encounters, Appointments, Consents, Photos, Guardians to target."""
        # Create source and target patients
        source = patient_factory(email='source_relations@test.com')
        target = patient_factory(email='target_relations@test.com')
        
        # Create relationships for source patient
        # 1. Encounter
        encounter = Encounter.objects.create(
            patient=source,
            practitioner=practitioner,
            location=clinic_location,
            type='medical_consult',
            status='draft',
            occurred_at=timezone.now(),
            created_by_user=admin_user
        )
        
        # 2. Appointment
        appointment = Appointment.objects.create(
            patient=source,
            practitioner=practitioner,
            location=clinic_location,
            source='manual',
            status='scheduled',
            scheduled_start=timezone.now() + timezone.timedelta(days=1),
            scheduled_end=timezone.now() + timezone.timedelta(days=1, hours=1),
        )
        
        # 3. Consent
        consent = Consent.objects.create(
            patient=source,
            consent_type='clinical_photos',
            status='granted',
            granted_at=timezone.now()
        )
        
        # 4. ClinicalPhoto
        photo = ClinicalPhoto.objects.create(
            patient=source,
            photo_kind='clinical',
            object_key='photos/test.jpg',
            content_type='image/jpeg',
            size_bytes=1024,
            storage_bucket='clinical',
        )
        
        # 5. PatientGuardian
        guardian = PatientGuardian.objects.create(
            patient=source,
            full_name='Test Guardian',
            relationship='parent',
            phone='+34600000000'
        )
        
        # Perform merge
        endpoint = f'/api/v1/patients/{source.id}/merge/'
        payload = {
            'target_patient_id': str(target.id),
            'merge_reason': 'Duplicate patient - consolidating records',
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify response contains reassignment counts (if API returns them)
        if 'reassigned' in response.data:
            assert response.data['reassigned']['encounters'] == 1
            assert response.data['reassigned']['appointments'] == 1
            assert response.data['reassigned']['consents'] == 1
            assert response.data['reassigned']['clinical_photos'] == 1
            assert response.data['reassigned']['guardians'] == 1
        
        # Verify relationships reassigned in database
        encounter.refresh_from_db()
        assert encounter.patient_id == target.id
        
        appointment.refresh_from_db()
        assert appointment.patient_id == target.id
        
        consent.refresh_from_db()
        assert consent.patient_id == target.id
        
        photo.refresh_from_db()
        assert photo.patient_id == target.id
        
        guardian.refresh_from_db()
        assert guardian.patient_id == target.id
        
        # Verify source patient is marked as merged
        source.refresh_from_db()
        assert source.is_merged is True
        assert source.merged_into_patient_id == target.id
        assert source.merge_reason == 'Duplicate patient - consolidating records'
        assert source.row_version == 2  # Incremented after merge
    
    def test_merge_with_no_relationships(self, admin_client, patient_factory):
        """Merge works even if source has no relationships."""
        source = patient_factory(email='source_empty@test.com')
        target = patient_factory(email='target_empty@test.com')
        
        endpoint = f'/api/v1/patients/{source.id}/merge/'
        payload = {
            'target_patient_id': str(target.id),
            'merge_reason': 'Duplicate - no history',
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify source is merged
        source.refresh_from_db()
        assert source.is_merged is True
        assert source.merged_into_patient_id == target.id
    
    def test_merge_multiple_encounters(
        self,
        admin_client,
        patient_factory,
        practitioner,
        clinic_location,
        admin_user
    ):
        """Merge reassigns multiple encounters from source to target."""
        source = patient_factory(email='source_multi@test.com')
        target = patient_factory(email='target_multi@test.com')
        
        # Create multiple encounters for source
        encounter1 = Encounter.objects.create(
            patient=source,
            practitioner=practitioner,
            location=clinic_location,
            type='medical_consult',
            status='draft',
            occurred_at=timezone.now() - timezone.timedelta(days=7),
            created_by_user=admin_user
        )
        
        encounter2 = Encounter.objects.create(
            patient=source,
            practitioner=practitioner,
            location=clinic_location,
            type='cosmetic_consult',
            status='finalized',
            occurred_at=timezone.now() - timezone.timedelta(days=14),
            created_by_user=admin_user
        )
        
        # Perform merge
        endpoint = f'/api/v1/patients/{source.id}/merge/'
        payload = {
            'target_patient_id': str(target.id),
            'merge_reason': 'Multiple encounters test',
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify both encounters reassigned
        encounter1.refresh_from_db()
        assert encounter1.patient_id == target.id
        
        encounter2.refresh_from_db()
        assert encounter2.patient_id == target.id
        
        # Verify count in response (if available)
        if 'reassigned' in response.data:
            assert response.data['reassigned']['encounters'] == 2
    
    def test_merge_atomicity_on_error(self, admin_client, patient_factory):
        """Merge is atomic - if validation fails, no changes are made."""
        source = patient_factory(email='atomic_source@test.com')
        target = patient_factory(email='atomic_target@test.com')
        
        # Create appointment for source
        appointment = Appointment.objects.create(
            patient=source,
            source='manual',
            status='scheduled',
            scheduled_start=timezone.now() + timezone.timedelta(days=1),
            scheduled_end=timezone.now() + timezone.timedelta(days=1, hours=1),
        )
        
        # Try to merge with invalid target (source == target)
        endpoint = f'/api/v1/patients/{source.id}/merge/'
        payload = {
            'target_patient_id': str(source.id),  # Invalid: same as source
            'merge_reason': 'Test',
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        
        # Verify source NOT marked as merged
        source.refresh_from_db()
        assert source.is_merged is False
        assert source.merged_into_patient_id is None
        assert source.row_version == 1  # Not incremented
        
        # Verify appointment still points to source
        appointment.refresh_from_db()
        assert appointment.patient_id == source.id


@pytest.mark.django_db(transaction=True)
class TestPatientMergeResponse:
    """Test merge endpoint response format."""
    
    def test_merge_response_format(
        self,
        admin_client,
        patient_factory,
        practitioner,
        clinic_location,
        admin_user
    ):
        """Merge returns proper response with patient and reassignment info."""
        source = patient_factory(email='response_source@test.com')
        target = patient_factory(email='response_target@test.com')
        
        # Create one of each relationship type
        Encounter.objects.create(
            patient=source,
            practitioner=practitioner,
            location=clinic_location,
            type='medical_consult',
            status='draft',
            occurred_at=timezone.now(),
            created_by_user=admin_user
        )
        
        Appointment.objects.create(
            patient=source,
            source='manual',
            status='scheduled',
            scheduled_start=timezone.now() + timezone.timedelta(days=1),
            scheduled_end=timezone.now() + timezone.timedelta(days=1, hours=1),
        )
        
        # Perform merge
        endpoint = f'/api/v1/patients/{source.id}/merge/'
        payload = {
            'target_patient_id': str(target.id),
            'merge_reason': 'Response format test',
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify response contains expected fields
        assert 'source_patient_id' in response.data or 'source' in str(response.data).lower()
        assert 'target_patient_id' in response.data or 'target' in str(response.data).lower()
        
        # If API returns reassignment counts, verify they exist
        if 'reassigned' in response.data:
            assert 'encounters' in response.data['reassigned']
            assert 'appointments' in response.data['reassigned']
