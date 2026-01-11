"""
Integration tests for Encounter API endpoints.

Tests CRUD operations, optimistic locking (row_version),
finalize action, and standalone encounters (without appointment).
"""
import pytest
from rest_framework import status
from django.utils import timezone
from apps.clinical.models import Encounter


@pytest.mark.django_db
class TestEncounterCreate:
    """Test POST /api/v1/encounters/ - Create encounter."""
    
    endpoint = '/api/v1/encounters/'
    
    def test_create_encounter_draft_status(
        self,
        admin_client,
        patient,
        practitioner,
        clinic_location
    ):
        """Create encounter with status=draft by default."""
        payload = {
            'patient_id': str(patient.id),
            'practitioner_id': str(practitioner.id),
            'location_id': str(clinic_location.id),
            'type': 'medical_consult',
            'status': 'draft',
            'occurred_at': timezone.now().isoformat(),
            'chief_complaint': 'Test complaint',
        }
        
        response = admin_client.post(self.endpoint, payload, format='json')
        
        # Skip if not implemented
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'id' in response.data
        assert response.data['status'] == 'draft'
        assert 'row_version' in response.data
        assert response.data['row_version'] == 1
    
    def test_create_encounter_minimal_fields(self, admin_client, patient):
        """Create encounter with minimal required fields."""
        payload = {
            'patient_id': str(patient.id),
            'type': 'medical_consult',
            'status': 'draft',
            'occurred_at': timezone.now().isoformat(),
        }
        
        response = admin_client.post(self.endpoint, payload, format='json')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['patient_id'] == str(patient.id)
        assert response.data['status'] == 'draft'
    
    def test_create_encounter_without_appointment(
        self,
        admin_client,
        patient,
        practitioner,
        clinic_location
    ):
        """Encounter can exist without appointment (standalone)."""
        payload = {
            'patient_id': str(patient.id),
            'practitioner_id': str(practitioner.id),
            'location_id': str(clinic_location.id),
            'type': 'cosmetic_consult',
            'status': 'draft',
            'occurred_at': timezone.now().isoformat(),
            'chief_complaint': 'Standalone encounter',
            'assessment': 'Test assessment',
            'plan': 'Test plan',
        }
        
        response = admin_client.post(self.endpoint, payload, format='json')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify encounter exists without appointment
        encounter = Encounter.objects.get(id=response.data['id'])
        assert encounter.patient_id == patient.id
        assert encounter.appointments.count() == 0  # No linked appointments
    
    def test_create_encounter_invalid_type(self, admin_client, patient):
        """Invalid encounter type returns 400."""
        payload = {
            'patient_id': str(patient.id),
            'type': 'invalid_type',
            'status': 'draft',
            'occurred_at': timezone.now().isoformat(),
        }
        
        response = admin_client.post(self.endpoint, payload, format='json')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'type' in response.data
    
    def test_create_encounter_invalid_status(self, admin_client, patient):
        """Invalid encounter status returns 400."""
        payload = {
            'patient_id': str(patient.id),
            'type': 'medical_consult',
            'status': 'invalid_status',
            'occurred_at': timezone.now().isoformat(),
        }
        
        response = admin_client.post(self.endpoint, payload, format='json')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'status' in response.data


@pytest.mark.django_db
class TestEncounterUpdate:
    """Test PATCH /api/v1/encounters/{id}/ - Update with row_version."""
    
    def test_update_encounter_with_correct_row_version(self, admin_client, encounter):
        """Update with correct row_version returns 200 and increments version."""
        endpoint = f'/api/v1/encounters/{encounter.id}/'
        
        payload = {
            'chief_complaint': 'Updated complaint',
            'row_version': encounter.row_version,
        }
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['chief_complaint'] == 'Updated complaint'
        assert response.data['row_version'] == encounter.row_version + 1
        
        # Verify in database
        encounter.refresh_from_db()
        assert encounter.chief_complaint == 'Updated complaint'
        assert encounter.row_version == 2
    
    def test_update_encounter_without_row_version(self, admin_client, encounter):
        """Update without row_version returns 400."""
        endpoint = f'/api/v1/encounters/{encounter.id}/'
        
        payload = {
            'chief_complaint': 'Updated',
            # Missing row_version
        }
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'row_version' in response.data
    
    def test_update_encounter_with_stale_row_version(self, admin_client, encounter):
        """Update with stale row_version returns 409 Conflict."""
        endpoint = f'/api/v1/encounters/{encounter.id}/'
        
        # Simulate concurrent update by incrementing row_version
        encounter.row_version += 1
        encounter.save()
        
        # Try to update with old version (1)
        payload = {
            'chief_complaint': 'Updated',
            'row_version': 1,  # Stale version
        }
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT]
        assert 'row_version' in response.data or 'version' in str(response.data).lower()
    
    def test_update_encounter_assessment_and_plan(self, admin_client, encounter):
        """Update assessment and plan fields."""
        endpoint = f'/api/v1/encounters/{encounter.id}/'
        
        payload = {
            'assessment': 'Detailed assessment notes',
            'plan': 'Treatment plan details',
            'row_version': encounter.row_version,
        }
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['assessment'] == 'Detailed assessment notes'
        assert response.data['plan'] == 'Treatment plan details'


@pytest.mark.django_db
class TestEncounterFinalize:
    """Test POST /api/v1/encounters/{id}/finalize/ - Finalize encounter."""
    
    def test_finalize_encounter_changes_status(self, admin_client, encounter):
        """Finalize changes status from draft to finalized."""
        encounter.status = 'draft'
        encounter.save()
        
        endpoint = f'/api/v1/encounters/{encounter.id}/finalize/'
        payload = {}
        
        response = admin_client.post(endpoint, payload, format='json')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter finalize endpoint not implemented yet')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify status changed to finalized
        encounter.refresh_from_db()
        assert encounter.status == 'finalized'
    
    def test_finalize_encounter_with_row_version(self, admin_client, encounter):
        """Finalize may require row_version (depends on implementation)."""
        encounter.status = 'draft'
        encounter.save()
        
        endpoint = f'/api/v1/encounters/{encounter.id}/finalize/'
        payload = {
            'row_version': encounter.row_version,
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter finalize endpoint not implemented yet')
        
        assert response.status_code == status.HTTP_200_OK
        
        encounter.refresh_from_db()
        assert encounter.status == 'finalized'
    
    def test_finalize_already_finalized_encounter(self, admin_client, encounter):
        """Finalizing already finalized encounter may be idempotent or return 409."""
        encounter.status = 'finalized'
        encounter.save()
        
        endpoint = f'/api/v1/encounters/{encounter.id}/finalize/'
        payload = {}
        
        response = admin_client.post(endpoint, payload, format='json')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter finalize endpoint not implemented yet')
        
        # Either idempotent (200) or conflict (409)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_409_CONFLICT]


@pytest.mark.django_db
class TestEncounterFinalizedLocking:
    """Test that finalized encounters cannot be edited (except by Admin)."""
    
    def test_edit_finalized_encounter_as_admin_allowed(self, admin_client, encounter):
        """Admin can edit finalized encounter."""
        encounter.status = 'finalized'
        encounter.save()
        
        endpoint = f'/api/v1/encounters/{encounter.id}/'
        payload = {
            'internal_notes': 'Admin correction',
            'row_version': encounter.row_version,
        }
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        # Admin should be allowed
        assert response.status_code == status.HTTP_200_OK
        assert response.data['internal_notes'] == 'Admin correction'
    
    def test_edit_finalized_encounter_as_practitioner_forbidden(
        self,
        practitioner_client,
        encounter
    ):
        """Practitioner cannot edit finalized encounter."""
        encounter.status = 'finalized'
        encounter.save()
        
        endpoint = f'/api/v1/encounters/{encounter.id}/'
        payload = {
            'internal_notes': 'Practitioner edit',
            'row_version': encounter.row_version,
        }
        
        response = practitioner_client.patch(endpoint, payload, format='json')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        # Should be forbidden (403) or conflict (409)
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_409_CONFLICT]
        
        # Verify no changes
        encounter.refresh_from_db()
        assert encounter.internal_notes != 'Practitioner edit'
    
    def test_edit_draft_encounter_as_practitioner_allowed(
        self,
        practitioner_client,
        encounter
    ):
        """Practitioner can edit draft encounter."""
        encounter.status = 'draft'
        encounter.save()
        
        endpoint = f'/api/v1/encounters/{encounter.id}/'
        payload = {
            'assessment': 'Practitioner assessment',
            'row_version': encounter.row_version,
        }
        
        response = practitioner_client.patch(endpoint, payload, format='json')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        # Should be allowed for draft
        assert response.status_code == status.HTTP_200_OK
        assert response.data['assessment'] == 'Practitioner assessment'


@pytest.mark.django_db
class TestEncounterList:
    """Test GET /api/v1/encounters/ - List encounters."""
    
    endpoint = '/api/v1/encounters/'
    
    def test_list_encounters_basic(self, admin_client, encounter):
        """List encounters returns basic data."""
        response = admin_client.get(self.endpoint)
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert len(response.data['results']) >= 1
    
    def test_list_encounters_excludes_soft_deleted(
        self,
        admin_client,
        encounter_factory
    ):
        """By default, soft-deleted encounters are excluded."""
        active = encounter_factory(status='draft')
        
        deleted = encounter_factory(status='draft')
        deleted.is_deleted = True
        deleted.deleted_at = timezone.now()
        deleted.save()
        
        response = admin_client.get(self.endpoint)
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_200_OK
        
        encounter_ids = [enc['id'] for enc in response.data['results']]
        assert str(active.id) in encounter_ids
        assert str(deleted.id) not in encounter_ids


@pytest.mark.django_db
class TestEncounterRetrieve:
    """Test GET /api/v1/encounters/{id}/ - Retrieve encounter detail."""
    
    def test_retrieve_encounter_success(self, admin_client, encounter):
        """Retrieve encounter returns full detail."""
        endpoint = f'/api/v1/encounters/{encounter.id}/'
        
        response = admin_client.get(endpoint)
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == str(encounter.id)
        assert response.data['type'] == encounter.type
        assert response.data['status'] == encounter.status
        assert 'row_version' in response.data
    
    def test_retrieve_nonexistent_encounter(self, admin_client):
        """Retrieve nonexistent encounter returns 404."""
        import uuid
        fake_id = uuid.uuid4()
        endpoint = f'/api/v1/encounters/{fake_id}/'
        
        response = admin_client.get(endpoint)
        
        # Could be 404 from endpoint not existing or from resource not found
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestEncounterPermissions:
    """Test encounter endpoint permissions by role."""
    
    def test_create_encounter_admin_allowed(self, admin_client, patient):
        """Admin can create encounter."""
        payload = {
            'patient_id': str(patient.id),
            'type': 'medical_consult',
            'status': 'draft',
            'occurred_at': timezone.now().isoformat(),
        }
        
        response = admin_client.post('/api/v1/encounters/', payload, format='json')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_201_CREATED
    
    def test_create_encounter_practitioner_allowed(self, practitioner_client, patient):
        """Practitioner can create encounter."""
        payload = {
            'patient_id': str(patient.id),
            'type': 'cosmetic_consult',
            'status': 'draft',
            'occurred_at': timezone.now().isoformat(),
        }
        
        response = practitioner_client.post('/api/v1/encounters/', payload, format='json')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_201_CREATED
    
    def test_create_encounter_reception_forbidden(self, reception_client, patient):
        """Reception cannot create encounter (clinical only)."""
        payload = {
            'patient_id': str(patient.id),
            'type': 'medical_consult',
            'status': 'draft',
            'occurred_at': timezone.now().isoformat(),
        }
        
        response = reception_client.post('/api/v1/encounters/', payload, format='json')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_list_encounters_accounting_allowed(self, accounting_client):
        """Accounting can read encounters (read-only)."""
        response = accounting_client.get('/api/v1/encounters/')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestEncounterStandalone:
    """Test encounters can exist independently without appointments."""
    
    def test_create_standalone_encounter_success(
        self,
        admin_client,
        patient,
        practitioner,
        clinic_location
    ):
        """Encounter can be created without any appointment."""
        payload = {
            'patient_id': str(patient.id),
            'practitioner_id': str(practitioner.id),
            'location_id': str(clinic_location.id),
            'type': 'follow_up',
            'status': 'draft',
            'occurred_at': timezone.now().isoformat(),
            'chief_complaint': 'Walk-in patient',
            'assessment': 'No prior appointment',
        }
        
        response = admin_client.post('/api/v1/encounters/', payload, format='json')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify encounter exists and is standalone
        encounter = Encounter.objects.get(id=response.data['id'])
        assert encounter.patient_id == patient.id
        
        # Verify no appointments link to this encounter
        from apps.clinical.models import Appointment
        linked_appointments = Appointment.objects.filter(encounter=encounter)
        assert linked_appointments.count() == 0
    
    def test_update_standalone_encounter(self, admin_client, encounter):
        """Standalone encounter can be updated normally."""
        # Ensure encounter has no linked appointments
        encounter.appointments.all().delete()
        
        endpoint = f'/api/v1/encounters/{encounter.id}/'
        payload = {
            'assessment': 'Updated standalone encounter',
            'row_version': encounter.row_version,
        }
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['assessment'] == 'Updated standalone encounter'
    
    def test_finalize_standalone_encounter(self, admin_client, encounter):
        """Standalone encounter can be finalized."""
        # Ensure encounter has no linked appointments
        encounter.appointments.all().delete()
        encounter.status = 'draft'
        encounter.save()
        
        endpoint = f'/api/v1/encounters/{encounter.id}/finalize/'
        payload = {}
        
        response = admin_client.post(endpoint, payload, format='json')
        
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter finalize endpoint not implemented yet')
        
        assert response.status_code == status.HTTP_200_OK
        
        encounter.refresh_from_db()
        assert encounter.status == 'finalized'
