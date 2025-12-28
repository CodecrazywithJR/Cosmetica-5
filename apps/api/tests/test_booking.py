"""
Sprint 3 Tests: Appointment Booking from Available Slots

Tests for POST /api/v1/clinical/practitioners/{practitioner_id}/book/

CRITICAL: All tests use timezone-aware datetimes (UTC)
CRITICAL: Tests validate that slots already started are REJECTED
"""
import pytest
from datetime import datetime, timedelta
from django.utils import timezone
from rest_framework.test import APIClient
from apps.authz.models import User, Practitioner, Role, UserRole, RoleChoices
from apps.clinical.models import Appointment, PractitionerBlock, Patient
from apps.core.models import ClinicLocation
import pytz


def create_user_with_role(email, role_name):
    """Helper function to create user with role"""
    user = User.objects.create_user(
        email=email,
        password='test123',
        is_active=True
    )
    role, _ = Role.objects.get_or_create(
        name=role_name,
        defaults={'name': role_name}
    )
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.fixture
def api_client():
    """API client for making requests"""
    return APIClient()


@pytest.fixture
def admin_user(db):
    """Admin user with credentials"""
    return create_user_with_role('admin_booking@test.com', RoleChoices.ADMIN)


@pytest.fixture
def reception_user(db):
    """Reception user with credentials"""
    return create_user_with_role('reception_booking@test.com', RoleChoices.RECEPTION)


@pytest.fixture
def practitioner_user(db):
    """Practitioner user with profile"""
    user = create_user_with_role('practitioner_booking@test.com', RoleChoices.PRACTITIONER)
    
    practitioner = Practitioner.objects.create(
        user=user,
        display_name='Dr. Test',
        specialty='dermatology'
    )
    return user, practitioner


@pytest.fixture
def other_practitioner(db):
    """Another practitioner for testing access control"""
    user = create_user_with_role('other_practitioner@test.com', RoleChoices.PRACTITIONER)
    
    practitioner = Practitioner.objects.create(
        user=user,
        display_name='Dr. Other',
        specialty='dermatology'
    )
    return practitioner


@pytest.fixture
def marketing_user(db):
    """Marketing user (should NOT be able to book)"""
    return create_user_with_role('marketing_booking@test.com', RoleChoices.MARKETING)


@pytest.fixture
def patient(db):
    """Test patient"""
    return Patient.objects.create(
        first_name='John',
        last_name='Doe',
        birth_date='1990-01-01',
        sex='M'
    )


@pytest.fixture
def location(db):
    """Test clinic location"""
    return ClinicLocation.objects.create(
        name='Test Clinic',
        address_line1='123 Test St',
        city='Test City',
        is_active=True
    )


@pytest.mark.django_db
class TestBookingEndpoint:
    """Test POST /api/v1/clinical/practitioners/{id}/book/"""
    
    def test_admin_can_book_valid_slot(self, api_client, admin_user, practitioner_user, patient, location):
        """Test: Admin successfully books a valid future slot"""
        _, practitioner = practitioner_user
        
        # Authenticate as admin
        api_client.force_authenticate(user=admin_user)
        
        # Calculate a slot 2 days in the future (09:00-09:30)
        future_date = (timezone.now() + timedelta(days=2)).date()
        
        payload = {
            'date': future_date.strftime('%Y-%m-%d'),
            'start': '09:00',
            'end': '09:30',
            'slot_duration': 30,
            'patient_id': str(patient.id),
            'location_id': str(location.id),
            'notes': 'Test booking by admin'
        }
        
        response = api_client.post(
            f'/api/v1/clinical/practitioners/{practitioner.id}/book/',
            data=payload,
            format='json'
        )
        
        # Assert 201 CREATED
        assert response.status_code == 201
        assert response.data['success'] is True
        assert 'appointment_id' in response.data
        
        # Verify appointment exists in DB
        appointment_id = response.data['appointment_id']
        appointment = Appointment.objects.get(id=appointment_id)
        assert appointment.practitioner == practitioner
        assert appointment.patient == patient
        assert appointment.status == 'scheduled'
        assert appointment.source == 'manual'
    
    def test_reject_slot_that_already_started(self, api_client, admin_user, practitioner_user, patient, location):
        """
        CRITICAL TEST: Reject booking if slot_start <= now
        Sprint 3 requirement: "NO se puede reservar un slot que ya comenzó"
        """
        _, practitioner = practitioner_user
        
        api_client.force_authenticate(user=admin_user)
        
        # Use today's date with a time in the past (00:00)
        past_date = timezone.now().date()
        
        payload = {
            'date': past_date.strftime('%Y-%m-%d'),
            'start': '00:00',
            'end': '00:30',
            'slot_duration': 30,
            'patient_id': str(patient.id),
            'location_id': str(location.id)
        }
        
        response = api_client.post(
            f'/api/v1/clinical/practitioners/{practitioner.id}/book/',
            data=payload,
            format='json'
        )
        
        # Assert 400 BAD REQUEST (slot already started)
        assert response.status_code == 400
        assert 'Slot already started' in response.data['error']
        
        # Verify NO appointment was created
        assert Appointment.objects.filter(
            practitioner=practitioner,
            scheduled_start__date=past_date
        ).count() == 0
    
    def test_reject_slot_in_past(self, api_client, admin_user, practitioner_user, patient, location):
        """Test: Reject booking for a date/time in the past"""
        _, practitioner = practitioner_user
        
        api_client.force_authenticate(user=admin_user)
        
        # Use yesterday's date
        past_date = (timezone.now() - timedelta(days=1)).date()
        
        payload = {
            'date': past_date.strftime('%Y-%m-%d'),
            'start': '10:00',
            'end': '10:30',
            'slot_duration': 30,
            'patient_id': str(patient.id),
            'location_id': str(location.id)
        }
        
        response = api_client.post(
            f'/api/v1/clinical/practitioners/{practitioner.id}/book/',
            data=payload,
            format='json'
        )
        
        # Assert 400 BAD REQUEST
        assert response.status_code == 400
        assert 'Slot already started' in response.data['error']
    
    def test_double_booking_same_slot(self, api_client, admin_user, practitioner_user, patient, location):
        """Test: Reject double booking for the same slot"""
        _, practitioner = practitioner_user
        
        api_client.force_authenticate(user=admin_user)
        
        # Calculate future slot
        future_date = (timezone.now() + timedelta(days=3)).date()
        tz = pytz.UTC
        slot_start = tz.localize(datetime.combine(future_date, datetime.strptime('10:00', '%H:%M').time()))
        slot_end = tz.localize(datetime.combine(future_date, datetime.strptime('10:30', '%H:%M').time()))
        
        # Create first appointment manually
        existing_appointment = Appointment.objects.create(
            practitioner=practitioner,
            patient=patient,
            location=location,
            scheduled_start=slot_start,
            scheduled_end=slot_end,
            status='scheduled',
            source='manual'
        )
        
        # Try to book the same slot again
        payload = {
            'date': future_date.strftime('%Y-%m-%d'),
            'start': '10:00',
            'end': '10:30',
            'slot_duration': 30,
            'patient_id': str(patient.id),
            'location_id': str(location.id)
        }
        
        response = api_client.post(
            f'/api/v1/clinical/practitioners/{practitioner.id}/book/',
            data=payload,
            format='json'
        )
        
        # Assert 409 CONFLICT (slot not available)
        assert response.status_code == 409
        assert 'Slot not available' in response.data['error']
    
    def test_booking_over_practitioner_block(self, api_client, admin_user, practitioner_user, patient, location):
        """Test: Reject booking over a PractitionerBlock"""
        _, practitioner = practitioner_user
        
        api_client.force_authenticate(user=admin_user)
        
        # Calculate future slot
        future_date = (timezone.now() + timedelta(days=3)).date()
        tz = pytz.UTC
        block_start = tz.localize(datetime.combine(future_date, datetime.strptime('14:00', '%H:%M').time()))
        block_end = tz.localize(datetime.combine(future_date, datetime.strptime('15:00', '%H:%M').time()))
        
        # Create a block
        PractitionerBlock.objects.create(
            practitioner=practitioner,
            start=block_start,
            end=block_end,
            kind='personal',
            title='Lunch Break',
            is_deleted=False
        )
        
        # Try to book in the blocked slot
        payload = {
            'date': future_date.strftime('%Y-%m-%d'),
            'start': '14:00',
            'end': '14:30',
            'slot_duration': 30,
            'patient_id': str(patient.id),
            'location_id': str(location.id)
        }
        
        response = api_client.post(
            f'/api/v1/clinical/practitioners/{practitioner.id}/book/',
            data=payload,
            format='json'
        )
        
        # Assert 409 CONFLICT
        assert response.status_code == 409
        assert 'Slot not available' in response.data['error']
    
    def test_practitioner_cannot_book_for_other(self, api_client, practitioner_user, other_practitioner, patient, location):
        """Test: Practitioner cannot book for another practitioner"""
        user, _ = practitioner_user
        
        api_client.force_authenticate(user=user)
        
        future_date = (timezone.now() + timedelta(days=2)).date()
        
        payload = {
            'date': future_date.strftime('%Y-%m-%d'),
            'start': '09:00',
            'end': '09:30',
            'slot_duration': 30,
            'patient_id': str(patient.id),
            'location_id': str(location.id)
        }
        
        # Try to book for OTHER practitioner
        response = api_client.post(
            f'/api/v1/clinical/practitioners/{other_practitioner.id}/book/',
            data=payload,
            format='json'
        )
        
        # Assert 403 FORBIDDEN
        assert response.status_code == 403
        assert 'You can only book appointments for yourself' in response.data['detail']
    
    def test_practitioner_can_book_own_slot(self, api_client, practitioner_user, patient, location):
        """Test: Practitioner can book their own slots"""
        user, practitioner = practitioner_user
        
        api_client.force_authenticate(user=user)
        
        future_date = (timezone.now() + timedelta(days=2)).date()
        
        payload = {
            'date': future_date.strftime('%Y-%m-%d'),
            'start': '11:00',
            'end': '11:30',
            'slot_duration': 30,
            'patient_id': str(patient.id),
            'location_id': str(location.id)
        }
        
        response = api_client.post(
            f'/api/v1/clinical/practitioners/{practitioner.id}/book/',
            data=payload,
            format='json'
        )
        
        # Assert 201 CREATED
        assert response.status_code == 201
        assert response.data['success'] is True
    
    def test_marketing_cannot_book(self, api_client, marketing_user, practitioner_user, patient, location):
        """Test: Marketing role cannot book appointments"""
        _, practitioner = practitioner_user
        
        api_client.force_authenticate(user=marketing_user)
        
        future_date = (timezone.now() + timedelta(days=2)).date()
        
        payload = {
            'date': future_date.strftime('%Y-%m-%d'),
            'start': '09:00',
            'end': '09:30',
            'slot_duration': 30,
            'patient_id': str(patient.id),
            'location_id': str(location.id)
        }
        
        response = api_client.post(
            f'/api/v1/clinical/practitioners/{practitioner.id}/book/',
            data=payload,
            format='json'
        )
        
        # Assert 403 FORBIDDEN
        assert response.status_code == 403
        assert 'You do not have permission to book appointments' in response.data['detail']
    
    def test_reception_can_book_any_practitioner(self, api_client, reception_user, practitioner_user, patient, location):
        """Test: Reception can book for any practitioner"""
        _, practitioner = practitioner_user
        
        api_client.force_authenticate(user=reception_user)
        
        future_date = (timezone.now() + timedelta(days=2)).date()
        
        payload = {
            'date': future_date.strftime('%Y-%m-%d'),
            'start': '15:00',
            'end': '15:30',
            'slot_duration': 30,
            'patient_id': str(patient.id),
            'location_id': str(location.id)
        }
        
        response = api_client.post(
            f'/api/v1/clinical/practitioners/{practitioner.id}/book/',
            data=payload,
            format='json'
        )
        
        # Assert 201 CREATED
        assert response.status_code == 201
        assert response.data['success'] is True
    
    def test_missing_required_fields(self, api_client, admin_user, practitioner_user, patient, location):
        """Test: Reject request with missing required fields"""
        _, practitioner = practitioner_user
        
        api_client.force_authenticate(user=admin_user)
        
        # Missing patient_id
        payload = {
            'date': '2025-12-30',
            'start': '09:00',
            'end': '09:30',
            'location_id': str(location.id)
        }
        
        response = api_client.post(
            f'/api/v1/clinical/practitioners/{practitioner.id}/book/',
            data=payload,
            format='json'
        )
        
        # Assert 400 BAD REQUEST
        assert response.status_code == 400
        assert 'Missing required fields' in response.data['error']
    
    def test_invalid_time_range(self, api_client, admin_user, practitioner_user, patient, location):
        """Test: Reject booking where start >= end"""
        _, practitioner = practitioner_user
        
        api_client.force_authenticate(user=admin_user)
        
        future_date = (timezone.now() + timedelta(days=2)).date()
        
        # start >= end (invalid)
        payload = {
            'date': future_date.strftime('%Y-%m-%d'),
            'start': '10:00',
            'end': '09:30',  # Earlier than start
            'slot_duration': 30,
            'patient_id': str(patient.id),
            'location_id': str(location.id)
        }
        
        response = api_client.post(
            f'/api/v1/clinical/practitioners/{practitioner.id}/book/',
            data=payload,
            format='json'
        )
        
        # Assert 400 BAD REQUEST
        assert response.status_code == 400
        assert 'Invalid time range' in response.data['error']
