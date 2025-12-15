"""
Global test fixtures for pytest.

Provides reusable fixtures for API testing:
- Authenticated API clients by role
- Model instances (Patient, Appointment, Encounter, etc.)
"""
import pytest
from rest_framework.test import APIClient
from django.utils import timezone
from apps.authz.models import User, Role, UserRole, Practitioner, RoleChoices
from apps.core.models import ClinicLocation
from apps.clinical.models import Patient, Appointment, Encounter


# ============================================================================
# API Clients
# ============================================================================

@pytest.fixture
def api_client():
    """Unauthenticated DRF API client."""
    return APIClient()


@pytest.fixture
def admin_client(db):
    """
    Authenticated API client with Admin role.
    Admin has full access to all resources.
    """
    user = User.objects.create_user(
        email='admin@test.com',
        password='testpass123',
        is_staff=True,
        is_superuser=True,
        is_active=True
    )
    
    # Create Admin role if not exists
    admin_role, _ = Role.objects.get_or_create(
        name=RoleChoices.ADMIN,
        defaults={'name': RoleChoices.ADMIN}
    )
    
    # Assign role to user
    UserRole.objects.create(user=user, role=admin_role)
    
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def practitioner_client(db):
    """
    Authenticated API client with Practitioner role.
    Practitioner has clinical access (patients, encounters, photos).
    """
    user = User.objects.create_user(
        email='practitioner@test.com',
        password='testpass123',
        is_active=True
    )
    
    # Create Practitioner role if not exists
    practitioner_role, _ = Role.objects.get_or_create(
        name=RoleChoices.PRACTITIONER,
        defaults={'name': RoleChoices.PRACTITIONER}
    )
    
    # Assign role to user
    UserRole.objects.create(user=user, role=practitioner_role)
    
    # Create Practitioner profile
    Practitioner.objects.create(
        user=user,
        display_name='Dr. Test Practitioner',
        specialty='Dermatology',
        is_active=True
    )
    
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def reception_client(db):
    """
    Authenticated API client with Reception role.
    Reception has administrative access (patients, appointments, consents).
    """
    user = User.objects.create_user(
        email='reception@test.com',
        password='testpass123',
        is_active=True
    )
    
    # Create Reception role if not exists
    reception_role, _ = Role.objects.get_or_create(
        name=RoleChoices.RECEPTION,
        defaults={'name': RoleChoices.RECEPTION}
    )
    
    # Assign role to user
    UserRole.objects.create(user=user, role=reception_role)
    
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def accounting_client(db):
    """
    Authenticated API client with Accounting role.
    Accounting has read-only access to financial/patient data.
    """
    user = User.objects.create_user(
        email='accounting@test.com',
        password='testpass123',
        is_active=True
    )
    
    # Create Accounting role if not exists
    accounting_role, _ = Role.objects.get_or_create(
        name=RoleChoices.ACCOUNTING,
        defaults={'name': RoleChoices.ACCOUNTING}
    )
    
    # Assign role to user
    UserRole.objects.create(user=user, role=accounting_role)
    
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def marketing_client(db):
    """
    Authenticated API client with Marketing role.
    Marketing has NO access to clinical data (should receive 403).
    """
    user = User.objects.create_user(
        email='marketing@test.com',
        password='testpass123',
        is_active=True
    )
    
    # Create Marketing role if not exists
    marketing_role, _ = Role.objects.get_or_create(
        name=RoleChoices.MARKETING,
        defaults={'name': RoleChoices.MARKETING}
    )
    
    # Assign role to user
    UserRole.objects.create(user=user, role=marketing_role)
    
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ============================================================================
# User Fixtures
# ============================================================================

@pytest.fixture
def admin_user(db):
    """Admin user (without authenticated client)."""
    user = User.objects.create_user(
        email='admin_user@test.com',
        password='testpass123',
        is_staff=True,
        is_superuser=True,
        is_active=True
    )
    
    admin_role, _ = Role.objects.get_or_create(
        name=RoleChoices.ADMIN,
        defaults={'name': RoleChoices.ADMIN}
    )
    UserRole.objects.create(user=user, role=admin_role)
    
    return user


@pytest.fixture
def practitioner_user(db):
    """Practitioner user (without authenticated client)."""
    user = User.objects.create_user(
        email='practitioner_user@test.com',
        password='testpass123',
        is_active=True
    )
    
    practitioner_role, _ = Role.objects.get_or_create(
        name=RoleChoices.PRACTITIONER,
        defaults={'name': RoleChoices.PRACTITIONER}
    )
    UserRole.objects.create(user=user, role=practitioner_role)
    
    return user


# ============================================================================
# Data Fixtures
# ============================================================================

@pytest.fixture
def clinic_location(db):
    """Create a clinic location."""
    return ClinicLocation.objects.create(
        name='Main Clinic',
        address_line1='123 Test Street',
        city='Paris',
        postal_code='75001',
        country_code='FR',
        timezone='Europe/Paris',
        is_active=True
    )


@pytest.fixture
def practitioner(db, practitioner_user):
    """Create a practitioner profile."""
    return Practitioner.objects.create(
        user=practitioner_user,
        display_name='Dr. Jane Smith',
        specialty='Dermatology',
        is_active=True
    )


@pytest.fixture
def patient(db, admin_user):
    """Create a patient."""
    return Patient.objects.create(
        first_name='John',
        last_name='Doe',
        full_name_normalized='john doe',
        birth_date='1990-01-15',
        sex='male',
        email='john.doe@test.com',
        phone='+33600000000',
        phone_e164='+33600000000',
        country_code='FR',
        identity_confidence='medium',
        created_by_user=admin_user
    )


@pytest.fixture
def appointment(db, patient, practitioner, clinic_location):
    """Create an appointment."""
    return Appointment.objects.create(
        patient=patient,
        practitioner=practitioner,
        location=clinic_location,
        source='manual',
        status='scheduled',
        scheduled_start=timezone.now() + timezone.timedelta(days=1),
        scheduled_end=timezone.now() + timezone.timedelta(days=1, hours=1),
        notes='Test appointment'
    )


@pytest.fixture
def encounter(db, patient, practitioner, clinic_location, admin_user):
    """Create an encounter."""
    return Encounter.objects.create(
        patient=patient,
        practitioner=practitioner,
        location=clinic_location,
        type='medical_consult',
        status='draft',
        occurred_at=timezone.now(),
        chief_complaint='Test complaint',
        assessment='Test assessment',
        plan='Test plan',
        created_by_user=admin_user
    )


# ============================================================================
# Factory-style Fixtures (for creating multiple instances)
# ============================================================================

@pytest.fixture
def patient_factory(db, admin_user):
    """
    Factory fixture for creating multiple patients.
    
    Usage:
        patient1 = patient_factory(first_name='Jane', last_name='Smith')
        patient2 = patient_factory(email='test@example.com')
    """
    created_patients = []
    
    def _create_patient(**kwargs):
        defaults = {
            'first_name': 'Test',
            'last_name': 'Patient',
            'full_name_normalized': 'test patient',
            'sex': 'female',
            'email': f'patient{len(created_patients)}@test.com',
            'identity_confidence': 'low',
            'created_by_user': admin_user
        }
        defaults.update(kwargs)
        
        # Auto-generate full_name_normalized if not provided
        if 'first_name' in kwargs or 'last_name' in kwargs:
            defaults['full_name_normalized'] = (
                f"{defaults['first_name']} {defaults['last_name']}"
            ).lower()
        
        patient = Patient.objects.create(**defaults)
        created_patients.append(patient)
        return patient
    
    return _create_patient


@pytest.fixture
def appointment_factory(db, patient, practitioner, clinic_location):
    """
    Factory fixture for creating multiple appointments.
    
    Usage:
        apt1 = appointment_factory(status='confirmed')
        apt2 = appointment_factory(source='calendly', external_id='cal_123')
    """
    created_appointments = []
    
    def _create_appointment(**kwargs):
        defaults = {
            'patient': patient,
            'practitioner': practitioner,
            'location': clinic_location,
            'source': 'manual',
            'status': 'scheduled',
            'scheduled_start': timezone.now() + timezone.timedelta(days=len(created_appointments) + 1),
            'scheduled_end': timezone.now() + timezone.timedelta(days=len(created_appointments) + 1, hours=1),
        }
        defaults.update(kwargs)
        
        appointment = Appointment.objects.create(**defaults)
        created_appointments.append(appointment)
        return appointment
    
    return _create_appointment


@pytest.fixture
def encounter_factory(db, patient, practitioner, clinic_location, admin_user):
    """
    Factory fixture for creating multiple encounters.
    
    Usage:
        enc1 = encounter_factory(type='cosmetic_consult')
        enc2 = encounter_factory(status='finalized')
    """
    created_encounters = []
    
    def _create_encounter(**kwargs):
        defaults = {
            'patient': patient,
            'practitioner': practitioner,
            'location': clinic_location,
            'type': 'medical_consult',
            'status': 'draft',
            'occurred_at': timezone.now() - timezone.timedelta(hours=len(created_encounters)),
            'created_by_user': admin_user
        }
        defaults.update(kwargs)
        
        encounter = Encounter.objects.create(**defaults)
        created_encounters.append(encounter)
        return encounter
    
    return _create_encounter
