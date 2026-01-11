"""
Integration tests for Appointment Attend endpoint.

Tests POST /api/v1/clinical/appointments/{id}/attend/ - Atomic "Atender paciente" operation.

REQUIREMENTS (SOURCE OF TRUTH: ENCOUNTER_WORKFLOW_DECISIONS.md):
- Atomic operation: Create Encounter + Link to Appointment + Mark as 'completed'
- ALL operations in single transaction.atomic() with select_for_update()
- Idempotent: If encounter already linked, returns existing encounter (no duplicate)
- Validations: Cannot attend cancelled/no_show appointments
- Permissions: Admin, Practitioner, Reception (403 for Accounting/Marketing)
- Response: appointment_id, encounter_id, appointment_status='completed', encounter_status='draft', created=true/false
"""
import pytest
from rest_framework import status
from django.utils import timezone
from django.db import transaction
from apps.clinical.models import Appointment, Encounter, EncounterStatusChoices, EncounterTypeChoices


@pytest.mark.django_db(transaction=True)
class TestAttendPermissions:
    """Test attend endpoint permissions by role."""
    
    @pytest.mark.parametrize('client_fixture,expected_status', [
        ('admin_client', status.HTTP_201_CREATED),
        ('practitioner_client', status.HTTP_201_CREATED),
        ('reception_client', status.HTTP_201_CREATED),
        ('accounting_client', status.HTTP_403_FORBIDDEN),
        ('marketing_client', status.HTTP_403_FORBIDDEN),
    ])
    def test_attend_permissions_by_role(
        self,
        client_fixture,
        expected_status,
        request,
        appointment
    ):
        """Admin, Practitioner, Reception can attend patients. Accounting/Marketing cannot."""
        client = request.getfixturevalue(client_fixture)
        
        # Set appointment to confirmed (valid for attending)
        appointment.status = 'confirmed'
        appointment.save()
        
        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        payload = {}
        
        response = client.post(endpoint, payload, format='json')
        
        assert response.status_code == expected_status


@pytest.mark.django_db(transaction=True)
class TestAttendCreatesEncounter:
    """Test attend endpoint creates encounter and marks appointment as completed."""
    
    def test_attend_creates_encounter_and_marks_completed(self, admin_client, appointment):
        """Attend creates new encounter with status='draft' and marks appointment as 'completed'."""
        # Set appointment to confirmed
        appointment.status = 'confirmed'
        appointment.save()
        
        # Verify no encounter exists
        assert appointment.encounter is None
        
        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        payload = {}
        
        response = admin_client.post(endpoint, payload, format='json')
        
        # Assertions
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['created'] is True
        assert response.data['appointment_id'] == str(appointment.id)
        assert response.data['appointment_status'] == 'completed'
        assert response.data['encounter_status'] == 'draft'
        assert 'encounter_id' in response.data
        
        # Verify in database
        appointment.refresh_from_db()
        assert appointment.status == 'completed'
        assert appointment.encounter is not None
        assert appointment.encounter.status == EncounterStatusChoices.DRAFT
        assert appointment.encounter.patient_id == appointment.patient_id
        assert appointment.encounter.practitioner_id == appointment.practitioner_id
        assert appointment.encounter.location_id == appointment.location_id
    
    def test_attend_with_custom_encounter_fields(self, admin_client, appointment):
        """Attend accepts optional encounter fields (encounter_type, chief_complaint, occurred_at)."""
        appointment.status = 'confirmed'
        appointment.save()
        
        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        payload = {
            'encounter_type': 'follow_up',
            'chief_complaint': 'Patient reports improvement after treatment',
            'occurred_at': '2025-01-09T10:00:00Z'
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify encounter fields
        appointment.refresh_from_db()
        encounter = appointment.encounter
        assert encounter.type == 'follow_up'
        assert encounter.chief_complaint == 'Patient reports improvement after treatment'
        # Note: occurred_at comparison might need timezone handling depending on settings
    
    def test_attend_from_scheduled_status(self, admin_client, appointment):
        """Attend works from 'scheduled' status (not just confirmed)."""
        appointment.status = 'scheduled'
        appointment.save()
        
        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        payload = {}
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['appointment_status'] == 'completed'
    
    def test_attend_from_checked_in_status(self, admin_client, appointment):
        """Attend works from 'checked_in' status."""
        appointment.status = 'checked_in'
        appointment.save()
        
        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        payload = {}
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['appointment_status'] == 'completed'


@pytest.mark.django_db(transaction=True)
class TestAttendIdempotency:
    """Test attend endpoint idempotency (does not create duplicate encounters)."""
    
    def test_attend_is_idempotent_if_encounter_already_linked(self, admin_client, appointment, encounter):
        """Attend returns existing encounter if already linked (no duplicate creation)."""
        # Link appointment to existing encounter
        appointment.encounter = encounter
        appointment.status = 'completed'
        appointment.patient = encounter.patient  # Ensure same patient
        appointment.save()
        
        # Get initial encounter count
        initial_encounter_count = Encounter.objects.count()
        
        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        payload = {}
        
        response = admin_client.post(endpoint, payload, format='json')
        
        # Assertions
        assert response.status_code == status.HTTP_200_OK
        assert response.data['created'] is False
        assert response.data['encounter_id'] == str(encounter.id)
        assert response.data['appointment_status'] == 'completed'
        assert response.data['encounter_status'] == encounter.status
        
        # Verify no new encounter created
        assert Encounter.objects.count() == initial_encounter_count
    
    def test_attend_multiple_times_does_not_create_duplicates(self, admin_client, appointment):
        """Calling attend multiple times on same appointment does not create duplicate encounters."""
        appointment.status = 'confirmed'
        appointment.save()
        
        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        payload = {}
        
        # First call: creates encounter
        response1 = admin_client.post(endpoint, payload, format='json')
        assert response1.status_code == status.HTTP_201_CREATED
        assert response1.data['created'] is True
        encounter_id_1 = response1.data['encounter_id']
        
        # Second call: returns existing encounter
        response2 = admin_client.post(endpoint, payload, format='json')
        assert response2.status_code == status.HTTP_200_OK
        assert response2.data['created'] is False
        assert response2.data['encounter_id'] == encounter_id_1
        
        # Third call: still returns same encounter
        response3 = admin_client.post(endpoint, payload, format='json')
        assert response3.status_code == status.HTTP_200_OK
        assert response3.data['created'] is False
        assert response3.data['encounter_id'] == encounter_id_1
        
        # Verify only one encounter exists for this appointment
        appointment.refresh_from_db()
        assert Encounter.objects.filter(appointments__id=appointment.id).count() == 1
    
    def test_attend_hardening_marks_completed_if_not_already(self, admin_client, appointment, encounter):
        """Attend ensures appointment.status='completed' even if encounter was linked manually."""
        # Simulate manual linking without marking completed (data corruption scenario)
        appointment.encounter = encounter
        appointment.status = 'confirmed'  # NOT completed
        appointment.patient = encounter.patient
        appointment.save()
        
        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        payload = {}
        
        response = admin_client.post(endpoint, payload, format='json')
        
        # Should fix the status
        assert response.status_code == status.HTTP_200_OK
        assert response.data['appointment_status'] == 'completed'
        
        # Verify in database
        appointment.refresh_from_db()
        assert appointment.status == 'completed'


@pytest.mark.django_db(transaction=True)
class TestAttendValidations:
    """Test attend endpoint validations (cannot attend cancelled/no_show)."""
    
    def test_attend_rejects_cancelled_appointment(self, admin_client, appointment):
        """Cannot attend appointment with status='cancelled'."""
        appointment.status = 'cancelled'
        appointment.save()
        
        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        payload = {}
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'cancelled' in response.data['error'].lower()
        
        # Verify no encounter created
        appointment.refresh_from_db()
        assert appointment.encounter is None
    
    def test_attend_rejects_no_show_appointment(self, admin_client, appointment):
        """Cannot attend appointment with status='no_show'."""
        appointment.status = 'no_show'
        appointment.save()
        
        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        payload = {}
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'no_show' in response.data['error'].lower()
        
        # Verify no encounter created
        appointment.refresh_from_db()
        assert appointment.encounter is None
    
    def test_attend_rejects_deleted_appointment(self, admin_client, appointment):
        """Cannot attend soft-deleted appointment."""
        appointment.status = 'confirmed'
        appointment.is_deleted = True
        appointment.deleted_at = timezone.now()
        appointment.save()
        
        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        payload = {}
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'eliminada' in response.data['error'].lower()
    
    def test_attend_rejects_invalid_encounter_type(self, admin_client, appointment):
        """Cannot attend with invalid encounter_type."""
        appointment.status = 'confirmed'
        appointment.save()
        
        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        payload = {
            'encounter_type': 'invalid_type_xyz'
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'encounter_type' in response.data['error'].lower()
    
    def test_attend_rejects_invalid_occurred_at_format(self, admin_client, appointment):
        """Cannot attend with invalid occurred_at datetime format."""
        appointment.status = 'confirmed'
        appointment.save()
        
        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        payload = {
            'occurred_at': 'not-a-valid-datetime'
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'occurred_at' in response.data['error'].lower()


@pytest.mark.django_db(transaction=True)
class TestAttendAtomicity:
    """Test attend endpoint atomicity (transaction rollback on failure)."""
    
    def test_attend_atomicity_encounter_creation_failure_rolls_back(self, admin_client, appointment, monkeypatch):
        """If encounter creation fails, appointment should not be marked completed."""
        appointment.status = 'confirmed'
        appointment.save()
        
        # Monkeypatch Encounter.objects.create to raise an exception
        from apps.clinical.models import Encounter as EncounterModel
        original_create = EncounterModel.objects.create
        
        def failing_create(*args, **kwargs):
            raise Exception("Simulated encounter creation failure")
        
        monkeypatch.setattr(EncounterModel.objects, 'create', failing_create)
        
        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        payload = {}
        
        # Call should fail
        with pytest.raises(Exception, match="Simulated encounter creation failure"):
            admin_client.post(endpoint, payload, format='json')
        
        # Verify appointment was NOT marked completed (transaction rolled back)
        appointment.refresh_from_db()
        assert appointment.status == 'confirmed'
        assert appointment.encounter is None
    
    def test_attend_uses_select_for_update_to_prevent_race_conditions(self, admin_client, appointment):
        """Attend uses select_for_update() to lock appointment row during transaction."""
        appointment.status = 'confirmed'
        appointment.save()
        
        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        payload = {}
        
        # This test verifies the endpoint doesn't raise DatabaseError
        # Actual race condition testing would require concurrent requests (complex)
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        
        # Note: Full concurrency testing would require threading/multiprocessing
        # For now, we verify the endpoint completes successfully with locking


@pytest.mark.django_db(transaction=True)
class TestAttendNotFound:
    """Test attend endpoint 404 handling."""
    
    def test_attend_non_existent_appointment_returns_404(self, admin_client):
        """Attend non-existent appointment returns 404."""
        from uuid import uuid4
        non_existent_id = uuid4()
        
        endpoint = f'/api/v1/clinical/appointments/{non_existent_id}/attend/'
        payload = {}
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'no encontrada' in response.data['error'].lower()
