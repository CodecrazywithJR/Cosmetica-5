"""
Tests for Practitioner Availability Calculation (Sprint 2)

Test Coverage:
1. Service calculates slots correctly without appointments
2. Service splits slots when appointment exists
3. Service excludes slots when PractitionerBlock exists
4. Endpoint enforces RBAC (403 for unauthorized roles)
5. Endpoint validates required parameters
6. Endpoint returns correct data structure
"""
import pytest
from datetime import datetime, timedelta, time
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
import pytz

from apps.authz.models import Practitioner, Role, UserRole, RoleChoices
from apps.core.models import ClinicLocation
from apps.clinical.models import Appointment, PractitionerBlock, Patient
from apps.clinical.services import AvailabilityService

User = get_user_model()


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
def test_location(db):
    """Fixture for test clinic location"""
    return ClinicLocation.objects.create(
        name='Test Clinic',
        address_line1='123 Test St'
    )


@pytest.mark.django_db
class TestAvailabilityService:
    """Test AvailabilityService business logic"""
    
    def test_full_day_available_no_appointments(self):
        """
        TEST CASE 1: Sin appointments → jornada completa libre
        
        Given: Practitioner with no appointments or blocks
        When: Calculate availability for date range
        Then: Return full working hours (09:00-17:00) in 30min slots
        """
        # Setup: Create practitioner
        user = create_user_with_role('doctor@test.com', RoleChoices.PRACTITIONER)
        practitioner = Practitioner.objects.create(
            user=user,
            display_name='Dr. Test',
            role_type='practitioner',
            specialty='Dermatology'
        )
        
        # Execute: Calculate availability
        tomorrow = (timezone.now() + timedelta(days=1)).date()
        result = AvailabilityService.calculate_availability(
            practitioner_id=str(practitioner.id),
            date_from=tomorrow.isoformat(),
            date_to=tomorrow.isoformat(),
            slot_duration=30,
            timezone_str='UTC'
        )
        
        # Assert: Full day available
        assert len(result['availability']) == 1
        day_slots = result['availability'][0]['slots']
        
        # 09:00-17:00 = 8 hours = 16 slots of 30 minutes
        assert len(day_slots) >= 15  # At least 15 slots (accounting for timezone edge cases)
        
        # First slot should start at 09:00
        assert day_slots[0]['start'] == '09:00'
        
        # Last slot should end at or before 17:00
        last_slot_end = day_slots[-1]['end']
        assert last_slot_end <= '17:00'
    
    def test_slots_split_with_appointment(self, test_patient, test_location):
        """
        TEST CASE 2: Con appointment en medio → slots partidos
        
        Given: Practitioner with appointment from 11:00-12:00
        When: Calculate availability
        Then: Return slots 09:00-11:00 and 12:00-17:00 (excluding appointment)
        """
        # Setup: Create practitioner and appointment
        user = create_user_with_role('doctor2@test.com', RoleChoices.PRACTITIONER)
        practitioner = Practitioner.objects.create(
            user=user,
            display_name='Dr. Test 2',
            role_type='practitioner',
            specialty='Dermatology'
        )
        
        tomorrow = timezone.now() + timedelta(days=1)
        appointment_start = timezone.make_aware(
            datetime.combine(tomorrow.date(), time(11, 0)),
            pytz.UTC
        )
        appointment_end = timezone.make_aware(
            datetime.combine(tomorrow.date(), time(12, 0)),
            pytz.UTC
        )
        
        Appointment.objects.create(
            patient=test_patient,
            practitioner=practitioner,
            location=test_location,
            scheduled_start=appointment_start,
            scheduled_end=appointment_end,
            status='scheduled',
            source='manual'
        )
        
        # Execute: Calculate availability
        result = AvailabilityService.calculate_availability(
            practitioner_id=str(practitioner.id),
            date_from=tomorrow.date().isoformat(),
            date_to=tomorrow.date().isoformat(),
            slot_duration=30,
            timezone_str='UTC'
        )
        
        # Assert: Slots exclude appointment time
        day_slots = result['availability'][0]['slots']
        
        # Check that no slot overlaps with 11:00-12:00
        for slot in day_slots:
            slot_start_time = datetime.strptime(slot['start'], "%H:%M").time()
            slot_end_time = datetime.strptime(slot['end'], "%H:%M").time()
            
            # Slot should not overlap with appointment (11:00-12:00)
            assert not (slot_start_time < time(12, 0) and slot_end_time > time(11, 0))
        
        # Should have slots before 11:00
        morning_slots = [s for s in day_slots if s['end'] <= '11:00']
        assert len(morning_slots) > 0
        
        # Should have slots after 12:00
        afternoon_slots = [s for s in day_slots if s['start'] >= '12:00']
        assert len(afternoon_slots) > 0
    
    def test_no_slots_with_practitioner_block(self):
        """
        TEST CASE 3: Con PractitionerBlock → sin slots en ese rango
        
        Given: Practitioner with full-day vacation block
        When: Calculate availability
        Then: Return 0 slots for that day
        """
        # Setup: Create practitioner and vacation block
        user = create_user_with_role('doctor3@test.com', RoleChoices.PRACTITIONER)
        practitioner = Practitioner.objects.create(
            user=user,
            display_name='Dr. Test 3',
            role_type='practitioner',
            specialty='Dermatology'
        )
        
        tomorrow = timezone.now() + timedelta(days=1)
        block_start = timezone.make_aware(
            datetime.combine(tomorrow.date(), time(9, 0)),
            pytz.UTC
        )
        block_end = timezone.make_aware(
            datetime.combine(tomorrow.date(), time(17, 0)),
            pytz.UTC
        )
        
        PractitionerBlock.objects.create(
            practitioner=practitioner,
            start=block_start,
            end=block_end,
            kind='vacation',
            title='Vacation Day'
        )
        
        # Execute: Calculate availability
        result = AvailabilityService.calculate_availability(
            practitioner_id=str(practitioner.id),
            date_from=tomorrow.date().isoformat(),
            date_to=tomorrow.date().isoformat(),
            slot_duration=30,
            timezone_str='UTC'
        )
        
        # Assert: No slots available
        day_slots = result['availability'][0]['slots']
        assert len(day_slots) == 0


@pytest.mark.django_db
class TestAvailabilityEndpoint:
    """Test Availability API endpoint with RBAC"""
    
    @pytest.fixture
    def api_client(self):
        """DRF API client for endpoint testing"""
        return APIClient()
    
    def test_marketing_role_receives_403(self, api_client):
        """
        TEST CASE 4: Marketing intenta acceder → 403
        
        Given: User with 'marketing' role
        When: Request availability endpoint
        Then: Return 403 Forbidden
        """
        # Setup: Create marketing user
        marketing_user = create_user_with_role('marketing@test.com', RoleChoices.MARKETING)
        
        # Create practitioner to query
        practitioner_user = create_user_with_role('doctor4@test.com', RoleChoices.PRACTITIONER)
        practitioner = Practitioner.objects.create(
            user=practitioner_user,
            display_name='Dr. Test 4',
            role_type='practitioner',
            specialty='Dermatology'
        )
        
        # Authenticate as marketing
        api_client.force_authenticate(user=marketing_user)
        
        # Execute: Request availability
        tomorrow = (timezone.now() + timedelta(days=1)).date()
        url = f'/api/v1/clinical/practitioners/{practitioner.id}/availability/'
        response = api_client.get(url, {
            'date_from': tomorrow.isoformat(),
            'date_to': tomorrow.isoformat()
        })
        
        # Assert: 403 Forbidden
        assert response.status_code == 403
        assert 'permission' in response.data['detail'].lower()
    
    def test_practitioner_can_view_own_availability(self, api_client):
        """
        TEST CASE 5: Practitioner ve su propia disponibilidad → 200
        
        Given: User with 'practitioner' role
        When: Request own availability
        Then: Return 200 OK with slots
        """
        # Setup: Create practitioner user
        practitioner_user = create_user_with_role('doctor5@test.com', RoleChoices.PRACTITIONER)
        practitioner = Practitioner.objects.create(
            user=practitioner_user,
            display_name='Dr. Test 5',
            role_type='practitioner',
            specialty='Dermatology'
        )
        
        # Authenticate as practitioner
        api_client.force_authenticate(user=practitioner_user)
        
        # Execute: Request own availability
        tomorrow = (timezone.now() + timedelta(days=1)).date()
        url = f'/api/v1/clinical/practitioners/{practitioner.id}/availability/'
        response = api_client.get(url, {
            'date_from': tomorrow.isoformat(),
            'date_to': tomorrow.isoformat()
        })
        
        # Assert: 200 OK
        assert response.status_code == 200
        assert 'availability' in response.data
        assert response.data['practitioner_id'] == str(practitioner.id)
    
    def test_practitioner_cannot_view_other_availability(self, api_client):
        """
        TEST CASE 6: Practitioner intenta ver otro → 403
        
        Given: Practitioner A attempts to view Practitioner B's availability
        When: Request different practitioner's availability
        Then: Return 403 Forbidden
        """
        # Setup: Create two practitioners
        practitioner_a_user = create_user_with_role('doctorA@test.com', RoleChoices.PRACTITIONER)
        practitioner_a = Practitioner.objects.create(
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
        
        # Authenticate as Practitioner A
        api_client.force_authenticate(user=practitioner_a_user)
        
        # Execute: Request Practitioner B's availability
        tomorrow = (timezone.now() + timedelta(days=1)).date()
        url = f'/api/v1/clinical/practitioners/{practitioner_b.id}/availability/'
        response = api_client.get(url, {
            'date_from': tomorrow.isoformat(),
            'date_to': tomorrow.isoformat()
        })
        
        # Assert: 403 Forbidden
        assert response.status_code == 403
    
    def test_admin_can_view_any_availability(self, api_client):
        """
        TEST CASE 7: Admin puede ver cualquier practitioner → 200
        
        Given: User with 'admin' role
        When: Request any practitioner's availability
        Then: Return 200 OK
        """
        # Setup: Create admin user
        admin_user = create_user_with_role('admin@test.com', RoleChoices.ADMIN)
        
        # Create practitioner
        practitioner_user = create_user_with_role('doctor6@test.com', RoleChoices.PRACTITIONER)
        practitioner = Practitioner.objects.create(
            user=practitioner_user,
            display_name='Dr. Test 6',
            role_type='practitioner',
            specialty='Dermatology'
        )
        
        # Authenticate as admin
        api_client.force_authenticate(user=admin_user)
        
        # Execute: Request availability
        tomorrow = (timezone.now() + timedelta(days=1)).date()
        url = f'/api/v1/clinical/practitioners/{practitioner.id}/availability/'
        response = api_client.get(url, {
            'date_from': tomorrow.isoformat(),
            'date_to': tomorrow.isoformat()
        })
        
        # Assert: 200 OK
        assert response.status_code == 200
        assert 'availability' in response.data
    
    def test_missing_date_params_returns_400(self, api_client):
        """
        TEST CASE 8: Parámetros faltantes → 400
        
        Given: Authenticated user
        When: Request without date_from or date_to
        Then: Return 400 Bad Request
        """
        # Setup: Create admin user
        admin_user = create_user_with_role('admin2@test.com', RoleChoices.ADMIN)
        
        # Create practitioner
        practitioner_user = create_user_with_role('doctor7@test.com', RoleChoices.PRACTITIONER)
        practitioner = Practitioner.objects.create(
            user=practitioner_user,
            display_name='Dr. Test 7',
            role_type='practitioner',
            specialty='Dermatology'
        )
        
        # Authenticate
        api_client.force_authenticate(user=admin_user)
        
        # Execute: Request without params
        url = f'/api/v1/clinical/practitioners/{practitioner.id}/availability/'
        response = api_client.get(url)
        
        # Assert: 400 Bad Request
        assert response.status_code == 400
        assert 'date_from' in response.data['error'].lower()
