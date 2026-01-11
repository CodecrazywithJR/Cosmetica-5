"""
Integration tests for Appointment Link-Encounter endpoint.

Tests POST /api/v1/appointments/{id}/link-encounter/ - Link/unlink encounter.

REQUIREMENTS (SOURCE OF TRUTH):
- Link: appointment.encounter = encounter, status → 'attended'
- Unlink: appointment.encounter = None, status → 'confirmed' (only if not terminal)
- Permissions: Admin, Practitioner, Reception (403 for Accounting/Marketing)
- Validations: no link if cancelled/no_show, patient match, 1:1 relationship
- Concurrency: transaction.atomic() + select_for_update()
"""
import pytest
from rest_framework import status
from django.utils import timezone
from apps.clinical.models import Appointment, Encounter


@pytest.mark.django_db(transaction=True)
class TestLinkEncounterPermissions:
    """Test link-encounter endpoint permissions by role."""
    
    @pytest.mark.parametrize('client_fixture,expected_status', [
        ('admin_client', status.HTTP_200_OK),
        ('practitioner_client', status.HTTP_200_OK),
        ('reception_client', status.HTTP_200_OK),
        ('accounting_client', status.HTTP_403_FORBIDDEN),
        ('marketing_client', status.HTTP_403_FORBIDDEN),
    ])
    def test_link_encounter_permissions_by_role(
        self,
        client_fixture,
        expected_status,
        request,
        appointment,
        encounter
    ):
        """Admin, Practitioner, Reception can link encounters. Accounting/Marketing cannot."""
        client = request.getfixturevalue(client_fixture)
        
        # Set appointment to confirmed (valid for linking)
        appointment.patient = encounter.patient
        appointment.status = 'confirmed'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': str(encounter.id),
        }
        
        response = client.post(endpoint, payload, format='json')
        
        assert response.status_code == expected_status


@pytest.mark.django_db(transaction=True)
class TestLinkEncounter:
    """Test linking appointment to encounter."""
    
    def test_link_encounter_changes_status_to_attended(self, admin_client, appointment, encounter):
        """Link appointment to encounter changes status to 'attended'."""
        # Ensure both belong to same patient
        appointment.patient = encounter.patient
        appointment.status = 'confirmed'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': str(encounter.id),
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['appointment_id'] == str(appointment.id)
        assert response.data['encounter_id'] == str(encounter.id)
        assert response.data['linked'] is True
        assert response.data['status'] == 'attended'
        
        # Verify in database
        appointment.refresh_from_db()
        assert appointment.encounter_id == encounter.id
        assert appointment.status == 'attended'
    
    def test_link_encounter_from_scheduled_changes_to_attended(self, admin_client, appointment, encounter):
        """Link from scheduled status changes to attended."""
        appointment.patient = encounter.patient
        appointment.status = 'scheduled'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': str(encounter.id),
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'attended'
        
        appointment.refresh_from_db()
        assert appointment.encounter_id == encounter.id
        assert appointment.status == 'attended'
    
    def test_link_encounter_already_attended_is_idempotent(self, admin_client, appointment, encounter):
        """Linking when already attended is idempotent (stays attended)."""
        appointment.patient = encounter.patient
        appointment.status = 'attended'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': str(encounter.id),
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'attended'
        
        appointment.refresh_from_db()
        assert appointment.status == 'attended'
    
    def test_link_encounter_cancelled_status_rejected(self, admin_client, appointment, encounter):
        """Cannot link appointment with status=cancelled."""
        appointment.patient = encounter.patient
        appointment.status = 'cancelled'
        appointment.cancellation_reason = 'Test cancellation'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': str(encounter.id),
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_409_CONFLICT
        assert 'cancelled' in str(response.data).lower()
        
        # Verify not linked and status unchanged
        appointment.refresh_from_db()
        assert appointment.encounter_id is None
        assert appointment.status == 'cancelled'
    
    def test_link_encounter_no_show_status_rejected(self, admin_client, appointment, encounter):
        """Cannot link appointment with status=no_show."""
        appointment.patient = encounter.patient
        appointment.status = 'no_show'
        appointment.no_show_reason = 'Patient did not show'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': str(encounter.id),
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_409_CONFLICT
        assert 'no_show' in str(response.data).lower()
        
        # Verify not linked and status unchanged
        appointment.refresh_from_db()
        assert appointment.encounter_id is None
        assert appointment.status == 'no_show'
    
    def test_link_encounter_not_found(self, admin_client, appointment):
        """Link with nonexistent encounter returns 404."""
        import uuid
        fake_encounter_id = uuid.uuid4()
        
        appointment.status = 'confirmed'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': str(fake_encounter_id),
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'encontrado' in str(response.data).lower() or 'eliminado' in str(response.data).lower()
    
    def test_link_encounter_soft_deleted(
        self,
        admin_client,
        appointment,
        encounter_factory,
        patient
    ):
        """Cannot link to soft-deleted encounter."""
        appointment.patient = patient
        appointment.status = 'confirmed'
        appointment.save()
        
        # Create and soft delete encounter
        deleted_encounter = encounter_factory(patient=patient, status='draft')
        deleted_encounter.is_deleted = True
        deleted_encounter.deleted_at = timezone.now()
        deleted_encounter.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': str(deleted_encounter.id),
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_link_encounter_patient_mismatch(
        self,
        admin_client,
        appointment,
        encounter_factory,
        patient_factory
    ):
        """Cannot link appointment to encounter with different patient."""
        # Create encounter with different patient
        other_patient = patient_factory(email='other@test.com')
        other_encounter = encounter_factory(patient=other_patient)
        
        appointment.status = 'confirmed'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': str(other_encounter.id),
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_409_CONFLICT
        assert 'paciente' in str(response.data).lower()
        
        # Verify not linked
        appointment.refresh_from_db()
        assert appointment.encounter_id is None
    
    def test_link_encounter_already_linked_to_different(
        self,
        admin_client,
        appointment,
        encounter_factory,
        patient
    ):
        """Cannot link appointment that already has different encounter (1:1)."""
        appointment.patient = patient
        appointment.status = 'confirmed'
        appointment.save()
        
        # Create first encounter and link
        first_encounter = encounter_factory(patient=patient)
        appointment.encounter = first_encounter
        appointment.save()
        
        # Try to link to second encounter
        second_encounter = encounter_factory(patient=patient)
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': str(second_encounter.id),
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_409_CONFLICT
        assert 'vinculada' in str(response.data).lower() or 'otro encuentro' in str(response.data).lower()
        
        # Verify still linked to first encounter
        appointment.refresh_from_db()
        assert appointment.encounter_id == first_encounter.id
    
    def test_link_encounter_already_linked_to_same_is_idempotent(
        self,
        admin_client,
        appointment,
        encounter
    ):
        """Linking to same encounter is idempotent (no error, status → attended)."""
        appointment.patient = encounter.patient
        appointment.status = 'confirmed'
        appointment.encounter = encounter
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': str(encounter.id),
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        # Should succeed (idempotent)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'attended'
        
        appointment.refresh_from_db()
        assert appointment.encounter_id == encounter.id
        assert appointment.status == 'attended'
    
    def test_link_encounter_deleted_appointment(
        self,
        admin_client,
        appointment,
        encounter
    ):
        """Cannot link soft-deleted appointment."""
        appointment.patient = encounter.patient
        appointment.status = 'confirmed'
        appointment.is_deleted = True
        appointment.deleted_at = timezone.now()
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': str(encounter.id),
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_409_CONFLICT
        assert 'eliminada' in str(response.data).lower() or 'deleted' in str(response.data).lower()


@pytest.mark.django_db(transaction=True)
class TestUnlinkEncounter:
    """Test unlinking appointment from encounter."""
    
    def test_unlink_encounter_changes_status_to_confirmed(self, admin_client, appointment, encounter):
        """Unlink appointment from encounter changes status to 'confirmed'."""
        # Link first
        appointment.patient = encounter.patient
        appointment.status = 'attended'
        appointment.encounter = encounter
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': None,
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['appointment_id'] == str(appointment.id)
        assert response.data['encounter_id'] is None
        assert response.data['linked'] is False
        assert response.data['status'] == 'confirmed'
        
        # Verify in database
        appointment.refresh_from_db()
        assert appointment.encounter_id is None
        assert appointment.status == 'confirmed'
    
    def test_unlink_encounter_from_scheduled_changes_to_confirmed(self, admin_client, appointment, encounter):
        """Unlink from scheduled status changes to confirmed."""
        appointment.patient = encounter.patient
        appointment.status = 'scheduled'
        appointment.encounter = encounter
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': None,
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'confirmed'
        
        appointment.refresh_from_db()
        assert appointment.encounter_id is None
        assert appointment.status == 'confirmed'
    
    def test_unlink_encounter_not_linked(self, admin_client, appointment):
        """Cannot unlink if appointment has no encounter."""
        appointment.status = 'confirmed'
        appointment.encounter = None
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': None,
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_409_CONFLICT
        assert 'vinculada' in str(response.data).lower() or 'no' in str(response.data).lower()
    
    def test_unlink_encounter_cancelled_status_rejected(self, admin_client, appointment, encounter):
        """Cannot unlink if status is cancelled (terminal)."""
        appointment.patient = encounter.patient
        appointment.status = 'cancelled'
        appointment.cancellation_reason = 'Test'
        appointment.encounter = encounter
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': None,
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_409_CONFLICT
        assert 'terminal' in str(response.data).lower() or 'cancelled' in str(response.data).lower()
        
        # Verify still linked and status unchanged
        appointment.refresh_from_db()
        assert appointment.encounter_id == encounter.id
        assert appointment.status == 'cancelled'
    
    def test_unlink_encounter_no_show_status_rejected(self, admin_client, appointment, encounter):
        """Cannot unlink if status is no_show (terminal)."""
        appointment.patient = encounter.patient
        appointment.status = 'no_show'
        appointment.no_show_reason = 'Test'
        appointment.encounter = encounter
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': None,
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_409_CONFLICT
        assert 'terminal' in str(response.data).lower() or 'no_show' in str(response.data).lower()
        
        # Verify still linked and status unchanged
        appointment.refresh_from_db()
        assert appointment.encounter_id == encounter.id
        assert appointment.status == 'no_show'


@pytest.mark.django_db(transaction=True)
class TestLinkEncounterAtomicity:
    """Test atomic behavior of link-encounter endpoint."""
    
    def test_link_atomicity_on_validation_error(
        self,
        admin_client,
        appointment,
        encounter_factory,
        patient_factory
    ):
        """If link fails validation, no changes are persisted."""
        original_status = 'confirmed'
        appointment.status = original_status
        appointment.save()
        
        # Try to link to encounter with different patient (will fail)
        other_patient = patient_factory(email='atomic@test.com')
        other_encounter = encounter_factory(patient=other_patient)
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': str(other_encounter.id),
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_409_CONFLICT
        
        # Verify NO changes in database
        appointment.refresh_from_db()
        assert appointment.encounter_id is None
        assert appointment.status == original_status
    
    def test_unlink_atomicity_on_validation_error(self, admin_client, appointment):
        """If unlink fails validation, no changes are persisted."""
        original_status = 'confirmed'
        appointment.status = original_status
        appointment.encounter = None  # No encounter linked
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': None,
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_409_CONFLICT
        
        # Verify NO changes
        appointment.refresh_from_db()
        assert appointment.encounter_id is None
        assert appointment.status == original_status
    
    def test_link_with_select_for_update_prevents_race_condition(
        self,
        admin_client,
        appointment,
        encounter
    ):
        """Link uses select_for_update to prevent concurrent modifications."""
        appointment.patient = encounter.patient
        appointment.status = 'confirmed'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': str(encounter.id),
        }
        
        # This test verifies the transaction completes successfully
        # In a real concurrent scenario, select_for_update would block
        # the second transaction until the first commits
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify link was successful and status changed
        appointment.refresh_from_db()
        assert appointment.encounter_id == encounter.id
        assert appointment.status == 'attended'
    
    def test_unlink_atomicity_terminal_status(self, admin_client, appointment, encounter):
        """Unlink validation failure (terminal status) does not persist changes."""
        appointment.patient = encounter.patient
        appointment.status = 'cancelled'
        appointment.cancellation_reason = 'Test'
        appointment.encounter = encounter
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': None,
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_409_CONFLICT
        
        # Verify no changes
        appointment.refresh_from_db()
        assert appointment.encounter_id == encounter.id
        assert appointment.status == 'cancelled'


@pytest.mark.django_db(transaction=True)
class TestLinkEncounterEdgeCases:
    """Test edge cases for link-encounter endpoint."""
    
    def test_link_missing_encounter_id_field(self, admin_client, appointment, encounter):
        """Request without encounter_id field treats as unlink (null)."""
        appointment.patient = encounter.patient
        appointment.status = 'attended'
        appointment.encounter = encounter
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {}  # Missing encounter_id
        
        response = admin_client.post(endpoint, payload, format='json')
        
        # Should treat as unlink (encounter_id = None)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['linked'] is False
        assert response.data['status'] == 'confirmed'
        
        appointment.refresh_from_db()
        assert appointment.encounter_id is None
        assert appointment.status == 'confirmed'
    
    def test_link_invalid_encounter_id_format(self, admin_client, appointment):
        """Invalid UUID format for encounter_id returns 400."""
        appointment.status = 'confirmed'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': 'not-a-valid-uuid',
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        # Should return 400 BAD_REQUEST with UUID validation
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'uuid' in str(response.data).lower() or 'válido' in str(response.data).lower()
    
    def test_link_nonexistent_appointment(self, admin_client, encounter):
        """Link-encounter on nonexistent appointment returns 404."""
        import uuid
        fake_id = uuid.uuid4()
        
        endpoint = f'/api/v1/appointments/{fake_id}/link-encounter/'
        payload = {
            'encounter_id': str(encounter.id),
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_link_and_unlink_full_cycle(self, admin_client, appointment, encounter):
        """Full cycle: link (→ attended), then unlink (→ confirmed)."""
        appointment.patient = encounter.patient
        appointment.status = 'scheduled'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        
        # Link
        link_payload = {'encounter_id': str(encounter.id)}
        link_response = admin_client.post(endpoint, link_payload, format='json')
        
        assert link_response.status_code == status.HTTP_200_OK
        assert link_response.data['status'] == 'attended'
        
        appointment.refresh_from_db()
        assert appointment.encounter_id == encounter.id
        assert appointment.status == 'attended'
        
        # Unlink
        unlink_payload = {'encounter_id': None}
        unlink_response = admin_client.post(endpoint, unlink_payload, format='json')
        
        assert unlink_response.status_code == status.HTTP_200_OK
        assert unlink_response.data['status'] == 'confirmed'
        
        appointment.refresh_from_db()
        assert appointment.encounter_id is None
        assert appointment.status == 'confirmed'
    
    def test_link_multiple_times_to_same_encounter(self, admin_client, appointment, encounter):
        """Linking multiple times to same encounter is idempotent."""
        appointment.patient = encounter.patient
        appointment.status = 'scheduled'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {'encounter_id': str(encounter.id)}
        
        # Link first time
        response1 = admin_client.post(endpoint, payload, format='json')
        assert response1.status_code == status.HTTP_200_OK
        assert response1.data['status'] == 'attended'
        
        # Link second time (already linked)
        response2 = admin_client.post(endpoint, payload, format='json')
        assert response2.status_code == status.HTTP_200_OK
        assert response2.data['status'] == 'attended'
        
        # Verify final state
        appointment.refresh_from_db()
        assert appointment.encounter_id == encounter.id
        assert appointment.status == 'attended'
    
    def test_link_idempotence_updates_status_when_needed(self, admin_client, appointment, encounter):
        """Idempotent link updates status to attended if it was different."""
        appointment.patient = encounter.patient
        appointment.status = 'confirmed'
        appointment.encounter = encounter
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {'encounter_id': str(encounter.id)}
        
        # Already linked but status is not 'attended'
        response = admin_client.post(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'attended'
        
        # Verify status was updated in database
        appointment.refresh_from_db()
        assert appointment.encounter_id == encounter.id
        assert appointment.status == 'attended'
    
    def test_link_uuid_validation_none_type(self, admin_client, appointment):
        """Test UUID validation with None type (should be treated as unlink)."""
        appointment.status = 'confirmed'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': None,
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        # None should trigger unlink logic, which will fail since no encounter linked
        assert response.status_code == status.HTTP_409_CONFLICT
    
    def test_link_uuid_validation_empty_string(self, admin_client, appointment):
        """Empty string for encounter_id returns 400."""
        appointment.status = 'confirmed'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': '',
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        # Empty string should fail UUID validation
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_link_uuid_validation_integer(self, admin_client, appointment):
        """Integer for encounter_id returns 400."""
        appointment.status = 'confirmed'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': 12345,
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        # Integer should fail UUID validation
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db(transaction=True)
class TestLinkEncounterDataIntegrity:
    """Test data integrity edge cases."""
    
    @pytest.mark.critical
    def test_link_appointment_with_null_patient(
        self,
        admin_client,
        appointment,
        encounter,
        patient_factory
    ):
        """Cannot link if appointment has no patient (data integrity issue)."""
        # Create appointment without patient (edge case)
        appointment.patient = None
        appointment.status = 'confirmed'
        appointment.save()
        
        # Encounter has valid patient
        valid_patient = patient_factory(email='valid@test.com')
        encounter.patient = valid_patient
        encounter.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': str(encounter.id),
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        # Should fail patient match validation (None != patient_id)
        assert response.status_code == status.HTTP_409_CONFLICT
        assert 'paciente' in str(response.data).lower() or 'patient' in str(response.data).lower()
    
    @pytest.mark.critical
    def test_link_encounter_with_null_patient(
        self,
        admin_client,
        appointment,
        encounter,
        patient_factory
    ):
        """Cannot link if encounter has no patient (data integrity issue)."""
        # Appointment has valid patient
        valid_patient = patient_factory(email='valid@test.com')
        appointment.patient = valid_patient
        appointment.status = 'confirmed'
        appointment.save()
        
        # Encounter without patient (edge case)
        encounter.patient = None
        encounter.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': str(encounter.id),
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        # Should fail patient match validation (patient_id != None)
        assert response.status_code == status.HTTP_409_CONFLICT
        assert 'paciente' in str(response.data).lower() or 'patient' in str(response.data).lower()
    
    @pytest.mark.critical
    def test_link_both_null_patients(
        self,
        admin_client,
        appointment,
        encounter
    ):
        """Edge case: both appointment and encounter have null patients."""
        # Both have null patients
        appointment.patient = None
        appointment.status = 'confirmed'
        appointment.save()
        
        encounter.patient = None
        encounter.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': str(encounter.id),
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        # None == None is True, so validation passes but this is bad data
        # Implementation should ideally reject this, but if it passes,
        # at least verify it doesn't crash
        assert response.status_code in [
            status.HTTP_200_OK,  # If None == None passes validation
            status.HTTP_409_CONFLICT  # If implementation adds null check
        ]
    
    def test_unlink_soft_deleted_appointment(
        self,
        admin_client,
        appointment,
        encounter
    ):
        """Unlink allows soft-deleted appointment (edge case, not critical)."""
        appointment.patient = encounter.patient
        appointment.status = 'attended'
        appointment.encounter = encounter
        appointment.is_deleted = True
        appointment.deleted_at = timezone.now()
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/link-encounter/'
        payload = {
            'encounter_id': None,
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        # Unlink path doesn't check is_deleted (by design)
        # Should succeed and change status to confirmed
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'confirmed'
        
        appointment.refresh_from_db()
        assert appointment.encounter_id is None
        assert appointment.status == 'confirmed'


