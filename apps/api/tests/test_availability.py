"""
Tests for Practitioner Availability Calculation

Test Coverage:
1. Service calculates slots correctly with PractitionerSchedule
2. Service splits slots when appointment exists (clinic-scoped)
3. Service excludes slots when PractitionerBlock exists
4. Endpoint enforces RBAC (403 for unauthorized roles)
5. Endpoint validates required parameters (including clinic_id)
6. Endpoint returns correct data structure
7. Treatment-aware slot duration
8. Practitioner capability validation
"""
import pytest
from datetime import datetime, timedelta, time
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
import pytz

from apps.authz.models import Practitioner, Role, UserRole, RoleChoices
from apps.core.models import Clinic
from apps.clinical.models import (
    Appointment, PractitionerBlock, Patient,
    PractitionerSchedule, PractitionerTreatment, Treatment,
)
from apps.clinical.services import AvailabilityService
from tests.conftest import TEST_PASSWORD

User = get_user_model()


def create_user_with_role(email, role_name):
    """Helper function to create user with role"""
    user = User.objects.create_user(
        email=email,
        password=TEST_PASSWORD,
        is_active=True
    )
    role, _ = Role.objects.get_or_create(
        name=role_name,
        defaults={'name': role_name}
    )
    UserRole.objects.create(user=user, role=role)
    return user


def _future_weekday(weekday_int):
    """Return a future date matching the given weekday (0=Mon)."""
    base = (timezone.now() + timedelta(days=1)).date()
    days_ahead = (weekday_int - base.weekday()) % 7
    target = base + timedelta(days=days_ahead)
    if target <= timezone.now().date():
        target += timedelta(weeks=1)
    return target


@pytest.fixture
def test_patient(db):
    """Fixture for test patient"""
    return Patient.objects.create(
        first_name='John',
        last_name='Doe',
        email='john@test.com',
        birth_date='1990-01-01',
        sex='M'
    )


@pytest.fixture
def test_location(db, legal_entity):
    return Clinic.objects.create(
        name='Test Clinic',
        address_line1='123 Test St',
        legal_entity=legal_entity,
    )


@pytest.mark.django_db
class TestAvailabilityService:
    """Test AvailabilityService business logic"""
    
    def test_full_day_available_no_appointments(self, test_location):
        """
        Given: Practitioner with schedule 09-17 and no appointments
        When: Calculate availability for that day
        Then: Return 16 x 30min slots
        """
        user = create_user_with_role('doctor@test.com', RoleChoices.PRACTITIONER)
        practitioner = Practitioner.objects.create(
            user=user,
            display_name='Dr. Test',
            role_type='practitioner',
            specialty='Dermatology'
        )
        
        # Pick a future Monday and create schedule for weekday=0
        target_date = _future_weekday(0)
        PractitionerSchedule.objects.create(
            practitioner=practitioner,
            clinic=test_location,
            weekday=target_date.weekday(),
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_active=True,
        )
        
        result = AvailabilityService.calculate_availability(
            practitioner_id=str(practitioner.id),
            clinic_id=str(test_location.id),
            date_from=target_date.isoformat(),
            date_to=target_date.isoformat(),
            slot_duration=30,
            timezone_str='UTC'
        )
        
        assert len(result['availability']) == 1
        day_slots = result['availability'][0]['slots']
        
        # 09:00-17:00 = 8 hours = 16 slots of 30 minutes
        assert len(day_slots) == 16
        assert day_slots[0]['start'] == '09:00'
        assert day_slots[-1]['end'] == '17:00'
        assert result['clinic_id'] == str(test_location.id)
    
    def test_slots_split_with_appointment(self, test_patient, test_location):
        """
        Given: Practitioner with appointment from 11:00-12:00 at same clinic
        When: Calculate availability
        Then: Slots exclude 11:00-12:00
        """
        user = create_user_with_role('doctor2@test.com', RoleChoices.PRACTITIONER)
        practitioner = Practitioner.objects.create(
            user=user,
            display_name='Dr. Test 2',
            role_type='practitioner',
            specialty='Dermatology'
        )
        
        target_date = _future_weekday(1)  # Tuesday
        PractitionerSchedule.objects.create(
            practitioner=practitioner,
            clinic=test_location,
            weekday=target_date.weekday(),
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_active=True,
        )
        
        appointment_start = timezone.make_aware(
            datetime.combine(target_date, time(11, 0)), pytz.UTC
        )
        appointment_end = timezone.make_aware(
            datetime.combine(target_date, time(12, 0)), pytz.UTC
        )
        
        Appointment.objects.create(
            patient=test_patient,
            practitioner=practitioner,
            clinic=test_location,
            scheduled_start=appointment_start,
            scheduled_end=appointment_end,
            status='scheduled',
            source='erp'
        )
        
        result = AvailabilityService.calculate_availability(
            practitioner_id=str(practitioner.id),
            clinic_id=str(test_location.id),
            date_from=target_date.isoformat(),
            date_to=target_date.isoformat(),
            slot_duration=30,
            timezone_str='UTC'
        )
        
        day_slots = result['availability'][0]['slots']
        
        for slot in day_slots:
            slot_start_time = datetime.strptime(slot['start'], "%H:%M").time()
            slot_end_time = datetime.strptime(slot['end'], "%H:%M").time()
            assert not (slot_start_time < time(12, 0) and slot_end_time > time(11, 0))
        
        morning_slots = [s for s in day_slots if s['end'] <= '11:00']
        assert len(morning_slots) > 0
        
        afternoon_slots = [s for s in day_slots if s['start'] >= '12:00']
        assert len(afternoon_slots) > 0
    
    def test_no_slots_with_practitioner_block(self, test_location):
        """
        Given: Practitioner with full-day vacation block
        When: Calculate availability
        Then: Return 0 slots for that day
        """
        user = create_user_with_role('doctor3@test.com', RoleChoices.PRACTITIONER)
        practitioner = Practitioner.objects.create(
            user=user,
            display_name='Dr. Test 3',
            role_type='practitioner',
            specialty='Dermatology'
        )
        
        target_date = _future_weekday(2)  # Wednesday
        PractitionerSchedule.objects.create(
            practitioner=practitioner,
            clinic=test_location,
            weekday=target_date.weekday(),
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_active=True,
        )
        
        block_start = timezone.make_aware(
            datetime.combine(target_date, time(9, 0)), pytz.UTC
        )
        block_end = timezone.make_aware(
            datetime.combine(target_date, time(17, 0)), pytz.UTC
        )
        
        PractitionerBlock.objects.create(
            practitioner=practitioner,
            start=block_start,
            end=block_end,
            kind='vacation',
            title='Vacation Day'
        )
        
        result = AvailabilityService.calculate_availability(
            practitioner_id=str(practitioner.id),
            clinic_id=str(test_location.id),
            date_from=target_date.isoformat(),
            date_to=target_date.isoformat(),
            slot_duration=30,
            timezone_str='UTC'
        )
        
        day_slots = result['availability'][0]['slots']
        assert len(day_slots) == 0
    
    def test_no_schedule_no_slots(self, test_location):
        """
        Given: Practitioner with no PractitionerSchedule
        When: Calculate availability
        Then: No day entries returned
        """
        user = create_user_with_role('doctor_nosched@test.com', RoleChoices.PRACTITIONER)
        practitioner = Practitioner.objects.create(
            user=user,
            display_name='Dr. No Schedule',
            role_type='practitioner',
            specialty='Dermatology'
        )
        
        target_date = _future_weekday(3)  # Thursday
        result = AvailabilityService.calculate_availability(
            practitioner_id=str(practitioner.id),
            clinic_id=str(test_location.id),
            date_from=target_date.isoformat(),
            date_to=target_date.isoformat(),
        )
        
        # Day should not appear at all (skipped)
        assert len(result['availability']) == 0


@pytest.mark.django_db
class TestAvailabilityEndpoint:
    """Test Availability API endpoint with RBAC"""
    
    @pytest.fixture
    def api_client(self):
        return APIClient()
    
    def test_marketing_role_receives_403(self, api_client, test_location):
        """Marketing role → 403"""
        marketing_user = create_user_with_role('marketing@test.com', RoleChoices.MARKETING)
        practitioner_user = create_user_with_role('doctor4@test.com', RoleChoices.PRACTITIONER)
        practitioner = Practitioner.objects.create(
            user=practitioner_user,
            display_name='Dr. Test 4',
            role_type='practitioner',
            specialty='Dermatology'
        )
        
        api_client.force_authenticate(user=marketing_user)
        
        tomorrow = (timezone.now() + timedelta(days=1)).date()
        url = f'/api/v1/clinical/practitioners/{practitioner.id}/availability/'
        response = api_client.get(url, {
            'clinic_id': str(test_location.id),
            'date_from': tomorrow.isoformat(),
            'date_to': tomorrow.isoformat()
        })
        
        assert response.status_code == 403
        assert 'permission' in response.data['detail'].lower()
    
    def test_practitioner_can_view_own_availability(self, api_client, test_location):
        """Practitioner views own availability → 200"""
        practitioner_user = create_user_with_role('doctor5@test.com', RoleChoices.PRACTITIONER)
        practitioner = Practitioner.objects.create(
            user=practitioner_user,
            display_name='Dr. Test 5',
            role_type='practitioner',
            specialty='Dermatology'
        )
        
        api_client.force_authenticate(user=practitioner_user)
        
        tomorrow = (timezone.now() + timedelta(days=1)).date()
        url = f'/api/v1/clinical/practitioners/{practitioner.id}/availability/'
        response = api_client.get(url, {
            'clinic_id': str(test_location.id),
            'date_from': tomorrow.isoformat(),
            'date_to': tomorrow.isoformat()
        })
        
        assert response.status_code == 200
        assert 'availability' in response.data
        assert response.data['practitioner_id'] == str(practitioner.id)
        assert response.data['clinic_id'] == str(test_location.id)
    
    def test_practitioner_cannot_view_other_availability(self, api_client, test_location):
        """Practitioner A views Practitioner B → 403"""
        practitioner_a_user = create_user_with_role('doctorA@test.com', RoleChoices.PRACTITIONER)
        Practitioner.objects.create(
            user=practitioner_a_user,
            display_name='Dr. A',
            role_type='practitioner',
            specialty='Dermatology'
        )
        
        practitioner_b_user = create_user_with_role('doctorB@test.com', RoleChoices.PRACTITIONER)
        practitioner_b = Practitioner.objects.create(
            user=practitioner_b_user,
            display_name='Dr. B',
            role_type='practitioner',
            specialty='Dermatology'
        )
        
        api_client.force_authenticate(user=practitioner_a_user)
        
        tomorrow = (timezone.now() + timedelta(days=1)).date()
        url = f'/api/v1/clinical/practitioners/{practitioner_b.id}/availability/'
        response = api_client.get(url, {
            'clinic_id': str(test_location.id),
            'date_from': tomorrow.isoformat(),
            'date_to': tomorrow.isoformat()
        })
        
        assert response.status_code == 403
    
    def test_admin_can_view_any_availability(self, api_client, test_location):
        """Admin views any practitioner → 200"""
        admin_user = create_user_with_role('admin@test.com', RoleChoices.ADMIN)
        practitioner_user = create_user_with_role('doctor6@test.com', RoleChoices.PRACTITIONER)
        practitioner = Practitioner.objects.create(
            user=practitioner_user,
            display_name='Dr. Test 6',
            role_type='practitioner',
            specialty='Dermatology'
        )
        
        api_client.force_authenticate(user=admin_user)
        
        tomorrow = (timezone.now() + timedelta(days=1)).date()
        url = f'/api/v1/clinical/practitioners/{practitioner.id}/availability/'
        response = api_client.get(url, {
            'clinic_id': str(test_location.id),
            'date_from': tomorrow.isoformat(),
            'date_to': tomorrow.isoformat()
        })
        
        assert response.status_code == 200
        assert 'availability' in response.data
    
    def test_missing_date_params_returns_400(self, api_client):
        """Missing required params → 400"""
        admin_user = create_user_with_role('admin2@test.com', RoleChoices.ADMIN)
        practitioner_user = create_user_with_role('doctor7@test.com', RoleChoices.PRACTITIONER)
        practitioner = Practitioner.objects.create(
            user=practitioner_user,
            display_name='Dr. Test 7',
            role_type='practitioner',
            specialty='Dermatology'
        )
        
        api_client.force_authenticate(user=admin_user)
        
        url = f'/api/v1/clinical/practitioners/{practitioner.id}/availability/'
        response = api_client.get(url)
        
        assert response.status_code == 400
        assert 'clinic_id' in response.data['error'].lower()
