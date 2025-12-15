"""
Integration tests for Appointment API endpoints.

Tests CRUD operations, status transitions, locking rules,
soft delete, and filtering.
"""
import pytest
from rest_framework import status
from django.utils import timezone
from apps.clinical.models import Appointment


@pytest.mark.django_db
class TestAppointmentCreate:
    """Test POST /api/v1/appointments/ - Create manual appointment."""
    
    endpoint = '/api/v1/appointments/'
    
    def test_create_manual_appointment_success(
        self,
        admin_client,
        patient,
        practitioner,
        clinic_location
    ):
        """Create manual appointment with source=manual, external_id=null."""
        payload = {
            'patient_id': str(patient.id),
            'practitioner_id': str(practitioner.id),
            'location_id': str(clinic_location.id),
            'status': 'scheduled',
            'scheduled_start': (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            'scheduled_end': (timezone.now() + timezone.timedelta(days=1, hours=1)).isoformat(),
            'notes': 'Test appointment',
        }
        
        response = admin_client.post(self.endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'id' in response.data
        assert response.data['source'] == 'manual'
        assert response.data['external_id'] is None
        assert response.data['status'] == 'scheduled'
    
    def test_create_appointment_auto_sets_source_manual(
        self,
        admin_client,
        patient,
        practitioner,
        clinic_location
    ):
        """Source defaults to manual if not provided."""
        payload = {
            'patient_id': str(patient.id),
            'practitioner_id': str(practitioner.id),
            'location_id': str(clinic_location.id),
            'status': 'scheduled',
            'scheduled_start': (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            'scheduled_end': (timezone.now() + timezone.timedelta(days=1, hours=1)).isoformat(),
        }
        
        response = admin_client.post(self.endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['source'] == 'manual'
        assert response.data['external_id'] is None
    
    def test_create_appointment_minimal_fields(self, admin_client, patient):
        """Create appointment with minimal required fields."""
        payload = {
            'patient_id': str(patient.id),
            'status': 'scheduled',
            'scheduled_start': (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            'scheduled_end': (timezone.now() + timezone.timedelta(days=1, hours=1)).isoformat(),
        }
        
        response = admin_client.post(self.endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['patient_id'] == str(patient.id)


@pytest.mark.django_db
class TestAppointmentList:
    """Test GET /api/v1/appointments/ - List and filter appointments."""
    
    endpoint = '/api/v1/appointments/'
    
    def test_list_appointments_basic(self, admin_client, appointment):
        """List appointments returns basic data."""
        response = admin_client.get(self.endpoint)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert len(response.data['results']) >= 1
    
    def test_filter_by_status(self, admin_client, appointment_factory):
        """Filter appointments by status."""
        apt_scheduled = appointment_factory(status='scheduled')
        apt_confirmed = appointment_factory(status='confirmed')
        apt_cancelled = appointment_factory(status='cancelled', cancellation_reason='Test')
        
        response = admin_client.get(f'{self.endpoint}?status=scheduled')
        
        assert response.status_code == status.HTTP_200_OK
        statuses = [apt['status'] for apt in response.data['results']]
        assert 'scheduled' in statuses
        assert 'confirmed' not in statuses or len([s for s in statuses if s == 'confirmed']) == 0
    
    def test_filter_by_date_from(self, admin_client, appointment_factory):
        """Filter appointments by date_from (scheduled_start >= date_from)."""
        # Create appointment in the past
        past = appointment_factory(
            scheduled_start=timezone.now() - timezone.timedelta(days=7),
            scheduled_end=timezone.now() - timezone.timedelta(days=7, hours=-1)
        )
        
        # Create appointment in the future
        future = appointment_factory(
            scheduled_start=timezone.now() + timezone.timedelta(days=7),
            scheduled_end=timezone.now() + timezone.timedelta(days=7, hours=1)
        )
        
        # Filter from now onwards
        date_from = timezone.now().isoformat()
        response = admin_client.get(f'{self.endpoint}?date_from={date_from}')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Future appointment should be included
        appointment_ids = [apt['id'] for apt in response.data['results']]
        assert str(future.id) in appointment_ids
        assert str(past.id) not in appointment_ids
    
    def test_filter_by_date_to(self, admin_client, appointment_factory):
        """Filter appointments by date_to (scheduled_start <= date_to)."""
        # Create appointment in the past
        past = appointment_factory(
            scheduled_start=timezone.now() - timezone.timedelta(days=7),
            scheduled_end=timezone.now() - timezone.timedelta(days=7, hours=-1)
        )
        
        # Create appointment far future
        far_future = appointment_factory(
            scheduled_start=timezone.now() + timezone.timedelta(days=30),
            scheduled_end=timezone.now() + timezone.timedelta(days=30, hours=1)
        )
        
        # Filter up to now
        date_to = timezone.now().isoformat()
        response = admin_client.get(f'{self.endpoint}?date_to={date_to}')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Past appointment should be included
        appointment_ids = [apt['id'] for apt in response.data['results']]
        assert str(past.id) in appointment_ids
        assert str(far_future.id) not in appointment_ids
    
    def test_filter_by_date_range(self, admin_client, appointment_factory):
        """Filter appointments by date range (date_from and date_to)."""
        # Appointments at different times
        past = appointment_factory(
            scheduled_start=timezone.now() - timezone.timedelta(days=10),
            scheduled_end=timezone.now() - timezone.timedelta(days=10, hours=-1)
        )
        
        in_range = appointment_factory(
            scheduled_start=timezone.now() + timezone.timedelta(days=5),
            scheduled_end=timezone.now() + timezone.timedelta(days=5, hours=1)
        )
        
        future = appointment_factory(
            scheduled_start=timezone.now() + timezone.timedelta(days=20),
            scheduled_end=timezone.now() + timezone.timedelta(days=20, hours=1)
        )
        
        # Filter for next 10 days
        date_from = timezone.now().isoformat()
        date_to = (timezone.now() + timezone.timedelta(days=10)).isoformat()
        
        response = admin_client.get(
            f'{self.endpoint}?date_from={date_from}&date_to={date_to}'
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        appointment_ids = [apt['id'] for apt in response.data['results']]
        assert str(in_range.id) in appointment_ids
        assert str(past.id) not in appointment_ids
        assert str(future.id) not in appointment_ids
    
    def test_list_excludes_soft_deleted(self, admin_client, appointment_factory):
        """By default, soft-deleted appointments are excluded."""
        active = appointment_factory(status='scheduled')
        
        deleted = appointment_factory(status='cancelled', cancellation_reason='Test')
        deleted.is_deleted = True
        deleted.deleted_at = timezone.now()
        deleted.save()
        
        response = admin_client.get(self.endpoint)
        
        assert response.status_code == status.HTTP_200_OK
        
        appointment_ids = [apt['id'] for apt in response.data['results']]
        assert str(active.id) in appointment_ids
        assert str(deleted.id) not in appointment_ids


@pytest.mark.django_db
class TestAppointmentUpdate:
    """Test PATCH /api/v1/appointments/{id}/ - Update with status transitions."""
    
    def test_update_appointment_basic(self, admin_client, appointment):
        """Update appointment notes."""
        endpoint = f'/api/v1/appointments/{appointment.id}/'
        
        payload = {
            'notes': 'Updated notes',
        }
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['notes'] == 'Updated notes'
        
        appointment.refresh_from_db()
        assert appointment.notes == 'Updated notes'
    
    def test_update_status_scheduled_to_confirmed(self, admin_client, appointment):
        """Can transition from scheduled to confirmed."""
        appointment.status = 'scheduled'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/'
        payload = {'status': 'confirmed'}
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'confirmed'
    
    def test_update_status_confirmed_to_attended(self, admin_client, appointment):
        """Can transition from confirmed to attended."""
        appointment.status = 'confirmed'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/'
        payload = {'status': 'attended'}
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'attended'
    
    def test_update_status_from_attended_rejected(self, admin_client, appointment):
        """Cannot transition from attended (terminal state) to another status."""
        appointment.status = 'attended'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/'
        payload = {'status': 'confirmed'}
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'status' in response.data or 'transición' in str(response.data).lower()
    
    def test_update_status_from_no_show_rejected(self, admin_client, appointment):
        """Cannot transition from no_show (terminal state) to another status."""
        appointment.status = 'no_show'
        appointment.no_show_reason = 'Patient did not arrive'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/'
        payload = {'status': 'scheduled'}
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_update_status_from_cancelled_rejected(self, admin_client, appointment):
        """Cannot transition from cancelled (terminal state) to another status."""
        appointment.status = 'cancelled'
        appointment.cancellation_reason = 'Patient cancelled'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/'
        payload = {'status': 'scheduled'}
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_update_status_no_show_requires_reason(self, admin_client, appointment):
        """Setting status=no_show requires no_show_reason."""
        appointment.status = 'confirmed'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/'
        payload = {
            'status': 'no_show',
            # Missing no_show_reason
        }
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'no_show_reason' in response.data
    
    def test_update_status_no_show_with_reason_success(self, admin_client, appointment):
        """Setting status=no_show with reason succeeds."""
        appointment.status = 'confirmed'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/'
        payload = {
            'status': 'no_show',
            'no_show_reason': 'Patient did not show up',
        }
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'no_show'
        assert response.data['no_show_reason'] == 'Patient did not show up'
    
    def test_update_status_cancelled_requires_reason(self, admin_client, appointment):
        """Setting status=cancelled requires cancellation_reason."""
        appointment.status = 'scheduled'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/'
        payload = {
            'status': 'cancelled',
            # Missing cancellation_reason
        }
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'cancellation_reason' in response.data
    
    def test_update_status_cancelled_with_reason_success(self, admin_client, appointment):
        """Setting status=cancelled with reason succeeds."""
        appointment.status = 'scheduled'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/'
        payload = {
            'status': 'cancelled',
            'cancellation_reason': 'Patient requested cancellation',
        }
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'cancelled'
        assert response.data['cancellation_reason'] == 'Patient requested cancellation'


@pytest.mark.django_db
class TestAppointmentLocking:
    """Test appointment locking rules (encounter link, attended status)."""
    
    def test_edit_locked_by_encounter_admin_allowed(
        self,
        admin_client,
        appointment,
        encounter
    ):
        """Admin can edit appointment even if linked to encounter."""
        # Link appointment to encounter
        appointment.encounter = encounter
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/'
        payload = {'notes': 'Admin edit'}
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['notes'] == 'Admin edit'
    
    def test_edit_locked_by_encounter_practitioner_forbidden(
        self,
        practitioner_client,
        appointment,
        encounter
    ):
        """Practitioner cannot edit appointment if linked to encounter."""
        # Link appointment to encounter
        appointment.encounter = encounter
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/'
        payload = {'notes': 'Practitioner edit'}
        
        response = practitioner_client.patch(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'encounter' in str(response.data).lower()
    
    def test_edit_locked_by_encounter_reception_forbidden(
        self,
        reception_client,
        appointment,
        encounter
    ):
        """Reception cannot edit appointment if linked to encounter."""
        # Link appointment to encounter
        appointment.encounter = encounter
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/'
        payload = {'notes': 'Reception edit'}
        
        response = reception_client.patch(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_edit_locked_by_attended_status_admin_allowed(self, admin_client, appointment):
        """Admin can edit appointment with status=attended."""
        appointment.status = 'attended'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/'
        payload = {'notes': 'Admin edit after attended'}
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['notes'] == 'Admin edit after attended'
    
    def test_edit_locked_by_attended_status_practitioner_forbidden(
        self,
        practitioner_client,
        appointment
    ):
        """Practitioner cannot edit appointment with status=attended."""
        appointment.status = 'attended'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/'
        payload = {'notes': 'Practitioner edit'}
        
        response = practitioner_client.patch(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'attended' in str(response.data).lower() or 'status' in str(response.data).lower()
    
    def test_edit_locked_by_attended_status_reception_forbidden(
        self,
        reception_client,
        appointment
    ):
        """Reception cannot edit appointment with status=attended."""
        appointment.status = 'attended'
        appointment.save()
        
        endpoint = f'/api/v1/appointments/{appointment.id}/'
        payload = {'notes': 'Reception edit'}
        
        response = reception_client.patch(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestAppointmentSoftDelete:
    """Test soft delete for appointments."""
    
    def test_admin_can_soft_delete_appointment(self, admin_client, appointment_factory):
        """Admin can soft delete appointment."""
        appointment = appointment_factory(status='scheduled')
        endpoint = f'/api/v1/appointments/{appointment.id}/'
        
        response = admin_client.delete(endpoint)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify soft delete in database
        appointment.refresh_from_db()
        assert appointment.is_deleted is True
        assert appointment.deleted_at is not None
    
    def test_non_admin_cannot_delete_appointment(
        self,
        practitioner_client,
        appointment_factory
    ):
        """Non-admin cannot delete appointment."""
        appointment = appointment_factory(status='scheduled')
        endpoint = f'/api/v1/appointments/{appointment.id}/'
        
        response = practitioner_client.delete(endpoint)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Verify appointment is not deleted
        appointment.refresh_from_db()
        assert appointment.is_deleted is False
    
    def test_deleted_appointment_not_in_default_list(
        self,
        admin_client,
        appointment_factory
    ):
        """Soft-deleted appointment does not appear in default list."""
        appointment = appointment_factory(status='scheduled')
        
        # Soft delete
        appointment.is_deleted = True
        appointment.deleted_at = timezone.now()
        appointment.save()
        
        response = admin_client.get('/api/v1/appointments/')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify deleted appointment not in results
        appointment_ids = [apt['id'] for apt in response.data['results']]
        assert str(appointment.id) not in appointment_ids
    
    def test_admin_can_see_deleted_with_include_deleted(
        self,
        admin_client,
        appointment_factory
    ):
        """Admin can see deleted appointments with include_deleted=true."""
        appointment = appointment_factory(status='scheduled')
        
        # Soft delete
        appointment.is_deleted = True
        appointment.deleted_at = timezone.now()
        appointment.save()
        
        response = admin_client.get('/api/v1/appointments/?include_deleted=true')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify deleted appointment IS in results
        appointment_ids = [apt['id'] for apt in response.data['results']]
        assert str(appointment.id) in appointment_ids
    
    def test_non_admin_cannot_see_deleted_even_with_parameter(
        self,
        practitioner_client,
        appointment_factory
    ):
        """Non-admin cannot see deleted appointments even with include_deleted=true."""
        appointment = appointment_factory(status='scheduled')
        
        # Soft delete
        appointment.is_deleted = True
        appointment.deleted_at = timezone.now()
        appointment.save()
        
        response = practitioner_client.get('/api/v1/appointments/?include_deleted=true')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify deleted appointment NOT in results
        appointment_ids = [apt['id'] for apt in response.data['results']]
        assert str(appointment.id) not in appointment_ids


@pytest.mark.django_db
class TestAppointmentRetrieve:
    """Test GET /api/v1/appointments/{id}/ - Retrieve appointment detail."""
    
    def test_retrieve_appointment_success(self, admin_client, appointment):
        """Retrieve appointment returns full detail."""
        endpoint = f'/api/v1/appointments/{appointment.id}/'
        
        response = admin_client.get(endpoint)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == str(appointment.id)
        assert response.data['status'] == appointment.status
        assert 'scheduled_start' in response.data
        assert 'scheduled_end' in response.data
    
    def test_retrieve_nonexistent_appointment(self, admin_client):
        """Retrieve nonexistent appointment returns 404."""
        import uuid
        fake_id = uuid.uuid4()
        endpoint = f'/api/v1/appointments/{fake_id}/'
        
        response = admin_client.get(endpoint)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
