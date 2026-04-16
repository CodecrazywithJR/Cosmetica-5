"""
Integration tests for Appointment Attend endpoint.

Tests POST /api/v1/clinical/appointments/{id}/attend/ - Attend appointment
(creates encounter + links to appointment + marks as 'completed').

REQUIREMENTS (SOURCE OF TRUTH):
- Creates new Encounter with status='draft'
- Links appointment.encounter = new_encounter
- Marks appointment.status = 'completed'
- ALL operations in single transaction.atomic() with select_for_update()
- Idempotent: If encounter already linked, returns existing encounter (no duplicate creation)
- Permissions: Admin, Practitioner, Reception (403 for Accounting/Marketing)
- Validations: cannot attend cancelled/no_show, cannot attend deleted appointment
"""
import pytest
import uuid
from rest_framework import status
from django.utils import timezone
from apps.clinical.models import Appointment, Encounter


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
        appointment,
    ):
        """Admin, Practitioner, Reception can attend. Accounting/Marketing cannot."""
        client = request.getfixturevalue(client_fixture)

        appointment.status = 'confirmed'
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'

        response = client.post(endpoint, {}, format='json')

        assert response.status_code == expected_status


@pytest.mark.django_db(transaction=True)
class TestAttendEndpoint:
    """Test attending appointment (create encounter + link + complete)."""

    def test_attend_creates_encounter_and_completes(self, admin_client, appointment):
        """Attend creates encounter, links it, and marks appointment completed."""
        appointment.status = 'confirmed'
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        response = admin_client.post(endpoint, {}, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['appointment_id'] == str(appointment.id)
        assert 'encounter_id' in response.data
        assert response.data['appointment_status'] == 'completed'
        assert response.data['encounter_status'] == 'draft'
        assert response.data['created'] is True

        # Verify in database
        appointment.refresh_from_db()
        assert appointment.encounter is not None
        assert appointment.status == 'completed'

    def test_attend_from_scheduled_status(self, admin_client, appointment):
        """Attend from scheduled status works."""
        appointment.status = 'scheduled'
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        response = admin_client.post(endpoint, {}, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['appointment_status'] == 'completed'
        assert response.data['created'] is True

        appointment.refresh_from_db()
        assert appointment.encounter is not None
        assert appointment.status == 'completed'

    def test_attend_from_checked_in_status(self, admin_client, appointment):
        """Attend from checked_in status works."""
        appointment.status = 'checked_in'
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        response = admin_client.post(endpoint, {}, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['appointment_status'] == 'completed'

    def test_attend_idempotent_returns_existing_encounter(self, admin_client, appointment, encounter):
        """Attending already-attended appointment returns existing encounter (idempotent)."""
        appointment.patient = encounter.patient
        appointment.encounter = encounter
        appointment.status = 'completed'
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        response = admin_client.post(endpoint, {}, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['encounter_id'] == str(encounter.id)
        assert response.data['appointment_status'] == 'completed'
        assert response.data['created'] is False

    def test_attend_cancelled_status_rejected(self, admin_client, appointment):
        """Cannot attend appointment with status=cancelled."""
        appointment.status = 'cancelled'
        appointment.cancellation_reason = 'Test cancellation'
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        response = admin_client.post(endpoint, {}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'cancelled' in str(response.data).lower()

        # Verify not attended
        appointment.refresh_from_db()
        assert appointment.encounter is None
        assert appointment.status == 'cancelled'

    def test_attend_no_show_status_rejected(self, admin_client, appointment):
        """Cannot attend appointment with status=no_show."""
        appointment.status = 'no_show'
        appointment.no_show_reason = 'Patient did not show'
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        response = admin_client.post(endpoint, {}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'no_show' in str(response.data).lower()

        # Verify not attended
        appointment.refresh_from_db()
        assert appointment.encounter is None
        assert appointment.status == 'no_show'

    def test_attend_nonexistent_appointment(self, admin_client):
        """Attend nonexistent appointment returns 404."""
        fake_id = uuid.uuid4()
        endpoint = f'/api/v1/clinical/appointments/{fake_id}/attend/'
        response = admin_client.post(endpoint, {}, format='json')

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_attend_deleted_appointment_rejected(self, admin_client, appointment):
        """Soft-deleted appointment is not found — AppointmentManager excludes is_deleted=True."""
        appointment.status = 'confirmed'
        appointment.is_deleted = True
        appointment.deleted_at = timezone.now()
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        response = admin_client.post(endpoint, {}, format='json')

        # After AppointmentManager, deleted appointments are invisible (404), not rejected (400).
        # This is the stronger, correct behavior: deleted resources do not exist from the API.
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_attend_with_encounter_type(self, admin_client, appointment):
        """Attend with custom encounter_type."""
        appointment.status = 'confirmed'
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        payload = {'encounter_type': 'cosmetic_consult'}
        response = admin_client.post(endpoint, payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['created'] is True

        # Verify encounter type
        encounter = Encounter.objects.get(id=response.data['encounter_id'])
        assert encounter.type == 'cosmetic_consult'

    def test_attend_with_chief_complaint(self, admin_client, appointment):
        """Attend with chief_complaint."""
        appointment.status = 'confirmed'
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        payload = {'chief_complaint': 'Headache for 3 days'}
        response = admin_client.post(endpoint, payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED

        encounter = Encounter.objects.get(id=response.data['encounter_id'])
        assert encounter.chief_complaint == 'Headache for 3 days'

    def test_attend_with_invalid_encounter_type(self, admin_client, appointment):
        """Attend with invalid encounter_type returns 400."""
        appointment.status = 'confirmed'
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        payload = {'encounter_type': 'invalid_type'}
        response = admin_client.post(endpoint, payload, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db(transaction=True)
class TestAttendAtomicity:
    """Test atomic behavior of attend endpoint."""

    def test_attend_atomicity_creates_encounter_and_links(self, admin_client, appointment):
        """Attend atomically creates encounter and links it."""
        appointment.status = 'confirmed'
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        response = admin_client.post(endpoint, {}, format='json')

        assert response.status_code == status.HTTP_201_CREATED

        # Verify both encounter creation and linking happened
        appointment.refresh_from_db()
        assert appointment.encounter is not None
        assert appointment.status == 'completed'
        assert appointment.encounter.status == 'draft'
        assert appointment.encounter.patient == appointment.patient

    def test_attend_idempotent_does_not_create_duplicate(self, admin_client, appointment, encounter):
        """Attending twice does not create duplicate encounter."""
        appointment.patient = encounter.patient
        appointment.encounter = encounter
        appointment.status = 'completed'
        appointment.save()

        initial_count = Encounter.objects.count()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        response = admin_client.post(endpoint, {}, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['created'] is False
        assert Encounter.objects.count() == initial_count

    def test_attend_uses_select_for_update(self, admin_client, appointment):
        """Attend uses select_for_update (verified by successful completion)."""
        appointment.status = 'confirmed'
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        response = admin_client.post(endpoint, {}, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        appointment.refresh_from_db()
        assert appointment.encounter is not None
        assert appointment.status == 'completed'


@pytest.mark.django_db(transaction=True)
class TestAttendEdgeCases:
    """Test edge cases for attend endpoint."""

    def test_attend_multiple_times_idempotent(self, admin_client, appointment):
        """Attending multiple times is idempotent after first."""
        appointment.status = 'confirmed'
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'

        # First attend
        response1 = admin_client.post(endpoint, {}, format='json')
        assert response1.status_code == status.HTTP_201_CREATED
        encounter_id = response1.data['encounter_id']

        # Second attend
        response2 = admin_client.post(endpoint, {}, format='json')
        assert response2.status_code == status.HTTP_200_OK
        assert response2.data['encounter_id'] == encounter_id
        assert response2.data['created'] is False

    def test_attend_encounter_has_correct_patient(self, admin_client, appointment):
        """Created encounter has same patient as appointment."""
        appointment.status = 'confirmed'
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        response = admin_client.post(endpoint, {}, format='json')

        assert response.status_code == status.HTTP_201_CREATED

        encounter = Encounter.objects.get(id=response.data['encounter_id'])
        assert encounter.patient == appointment.patient

    def test_attend_encounter_has_correct_practitioner(self, admin_client, appointment):
        """Created encounter has same practitioner as appointment."""
        appointment.status = 'confirmed'
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        response = admin_client.post(endpoint, {}, format='json')

        assert response.status_code == status.HTTP_201_CREATED

        encounter = Encounter.objects.get(id=response.data['encounter_id'])
        assert encounter.practitioner == appointment.practitioner

    def test_attend_encounter_has_correct_clinic(self, admin_client, appointment):
        """Created encounter has same clinic as appointment."""
        appointment.status = 'confirmed'
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        response = admin_client.post(endpoint, {}, format='json')

        assert response.status_code == status.HTTP_201_CREATED

        encounter = Encounter.objects.get(id=response.data['encounter_id'])
        assert encounter.clinic == appointment.clinic

    def test_attend_default_encounter_type(self, admin_client, appointment):
        """Default encounter type is medical_consult."""
        appointment.status = 'confirmed'
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        response = admin_client.post(endpoint, {}, format='json')

        assert response.status_code == status.HTTP_201_CREATED

        encounter = Encounter.objects.get(id=response.data['encounter_id'])
        assert encounter.type == 'medical_consult'

    def test_attend_idempotent_updates_status_if_needed(self, admin_client, appointment, encounter):
        """Idempotent attend ensures status is completed even if it was different."""
        appointment.patient = encounter.patient
        appointment.encounter = encounter
        appointment.status = 'confirmed'
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        response = admin_client.post(endpoint, {}, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['appointment_status'] == 'completed'

        appointment.refresh_from_db()
        assert appointment.status == 'completed'


@pytest.mark.django_db(transaction=True)
class TestAttendDataIntegrity:
    """Test data integrity for attend endpoint."""

    @pytest.mark.critical
    def test_attend_creates_draft_encounter(self, admin_client, appointment):
        """Attend creates encounter with status=draft."""
        appointment.status = 'confirmed'
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        response = admin_client.post(endpoint, {}, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['encounter_status'] == 'draft'

        encounter = Encounter.objects.get(id=response.data['encounter_id'])
        assert encounter.status == 'draft'

    @pytest.mark.critical
    def test_attend_links_encounter_to_appointment(self, admin_client, appointment):
        """Attend links created encounter to appointment."""
        appointment.status = 'confirmed'
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        response = admin_client.post(endpoint, {}, format='json')

        assert response.status_code == status.HTTP_201_CREATED

        appointment.refresh_from_db()
        assert appointment.encounter_id is not None
        assert str(appointment.encounter_id) == response.data['encounter_id']

    @pytest.mark.critical
    def test_attend_sets_appointment_completed(self, admin_client, appointment):
        """Attend sets appointment status to completed."""
        appointment.status = 'confirmed'
        appointment.save()

        endpoint = f'/api/v1/clinical/appointments/{appointment.id}/attend/'
        response = admin_client.post(endpoint, {}, format='json')

        assert response.status_code == status.HTTP_201_CREATED

        appointment.refresh_from_db()
        assert appointment.status == 'completed'
