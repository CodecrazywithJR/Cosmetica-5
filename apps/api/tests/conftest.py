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
from apps.core.models import Clinic
from apps.clinical.models import Patient, Appointment, Encounter

TEST_PASSWORD = 'testpass123'  # noqa: S105


def _get_test_legal_entity():
    """Get or create a shared LegalEntity for non-superuser test fixtures."""
    from apps.legal.models import LegalEntity
    le, _ = LegalEntity.objects.get_or_create(
        siret='00000000000001',
        defaults={
            'trade_name': 'Fixture Clinic',
            'legal_name': 'Fixture Clinic SRL',
            'country_code': 'FR',
            'is_active': True,
        },
    )
    return le


# ============================================================================
# Shared Tenant Fixture
# ============================================================================

@pytest.fixture
def legal_entity(db):
    """Shared LegalEntity for tenant-aware test fixtures."""
    return _get_test_legal_entity()


@pytest.fixture(autouse=True)
def _auto_legal_entity_for_users(db, monkeypatch):
    """Auto-assign legal_entity to non-superuser users created via create_user,
    and to Patient/Appointment/Encounter objects created via ORM without a
    legal_entity, so that TenantManager filters don't hide them from
    tenant-scoped clients.
    """
    from apps.authz.models import UserManager
    from apps.clinical.models import Patient, Appointment, Encounter

    # ---- User.objects.create_user patch ----
    _original_create_user = UserManager.create_user

    def _patched_create_user(self, email=None, password=None, **extra_fields):
        if email is None:
            email = extra_fields.pop('username', None)
        if 'username' in extra_fields:
            extra_fields.pop('username')
        if not extra_fields.get('is_superuser') and 'legal_entity' not in extra_fields:
            extra_fields['legal_entity'] = _get_test_legal_entity()
        return _original_create_user(self, email, password, **extra_fields)

    monkeypatch.setattr(UserManager, 'create_user', _patched_create_user)

    # ---- TenantModel.objects.create + get_or_create patch ----
    from apps.clinical.models import ClinicalPhoto, Consent
    from apps.treatment_plans.models import TreatmentPlan
    from apps.treatment_plans.treatment_session_models import TreatmentSession
    from apps.products.models import Product
    from apps.stock.models import StockLocation, StockBatch, StockMove, StockOnHand
    from apps.documents.models import Document
    from apps.photos.models import SkinPhoto
    for ModelClass in (Patient, Appointment, Encounter, ClinicalPhoto, Consent,
                       TreatmentPlan, TreatmentSession,
                       Document, SkinPhoto,
                       Product, StockLocation, StockBatch, StockMove, StockOnHand):
        _original_create = ModelClass.objects.create

        def _patched_create(_orig=_original_create, **kwargs):
            if 'legal_entity' not in kwargs or kwargs.get('legal_entity') is None:
                kwargs['legal_entity'] = _get_test_legal_entity()
            return _orig(**kwargs)

        monkeypatch.setattr(ModelClass.objects, 'create', _patched_create)

        _original_goc = ModelClass.objects.get_or_create

        def _patched_goc(_orig=_original_goc, **kwargs):
            defaults = kwargs.get('defaults', {})
            if 'legal_entity' not in kwargs and 'legal_entity' not in defaults:
                defaults['legal_entity'] = _get_test_legal_entity()
                kwargs['defaults'] = defaults
            return _orig(**kwargs)

        monkeypatch.setattr(ModelClass.objects, 'get_or_create', _patched_goc)


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
        password=TEST_PASSWORD,
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
    # Superusers resolve their tenant from X-Legal-Entity-ID — required by
    # the new mandatory-header enforcement in TenantQuerySetMixin.initial().
    le = _get_test_legal_entity()
    client.credentials(HTTP_X_LEGAL_ENTITY_ID=str(le.id))
    return client


@pytest.fixture
def practitioner_client(db):
    """
    Authenticated API client with Practitioner role.
    Practitioner has clinical access (patients, encounters, photos).
    """
    user = User.objects.create_user(
        email='practitioner@test.com',
        password=TEST_PASSWORD,
        is_active=True,
        legal_entity=_get_test_legal_entity(),
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
    le = _get_test_legal_entity()
    client.credentials(HTTP_X_LEGAL_ENTITY_ID=str(le.id))
    return client


@pytest.fixture
def reception_client(db):
    """
    Authenticated API client with Reception role.
    Reception has administrative access (patients, appointments, consents).
    """
    user = User.objects.create_user(
        email='reception@test.com',
        password=TEST_PASSWORD,
        is_active=True,
        legal_entity=_get_test_legal_entity()
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
    le = _get_test_legal_entity()
    client.credentials(HTTP_X_LEGAL_ENTITY_ID=str(le.id))
    return client


@pytest.fixture
def accounting_client(db):
    """
    Authenticated API client with Accounting role.
    Accounting has read-only access to financial/patient data.
    """
    user = User.objects.create_user(
        email='accounting@test.com',
        password=TEST_PASSWORD,
        is_active=True,
        legal_entity=_get_test_legal_entity()
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
    le = _get_test_legal_entity()
    client.credentials(HTTP_X_LEGAL_ENTITY_ID=str(le.id))
    return client


@pytest.fixture
def marketing_client(db):
    """
    Authenticated API client with Marketing role.
    Marketing has NO access to clinical data (should receive 403).
    """
    user = User.objects.create_user(
        email='marketing@test.com',
        password=TEST_PASSWORD,
        is_active=True,
        legal_entity=_get_test_legal_entity()
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
    le = _get_test_legal_entity()
    client.credentials(HTTP_X_LEGAL_ENTITY_ID=str(le.id))
    return client


# ============================================================================
# User Fixtures
# ============================================================================

@pytest.fixture
def admin_user(db):
    """Admin user (without authenticated client)."""
    user = User.objects.create_user(
        email='admin_user@test.com',
        password=TEST_PASSWORD,
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
        password=TEST_PASSWORD,
        is_active=True,
        legal_entity=_get_test_legal_entity(),
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
def clinic(db, legal_entity):
    """Create a clinic."""
    return Clinic.objects.create(
        name='Main Clinic',
        address_line1='123 Test Street',
        city='Paris',
        postal_code='75001',
        country_code='FR',
        timezone='Europe/Paris',
        is_active=True,
        legal_entity=legal_entity,
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
        created_by_user=admin_user,
        legal_entity=_get_test_legal_entity(),
    )


@pytest.fixture
def appointment(db, patient, practitioner, clinic):
    """Create an appointment."""
    return Appointment.objects.create(
        patient=patient,
        practitioner=practitioner,
        clinic=clinic,
        source='manual',
        status='scheduled',
        scheduled_start=timezone.now() + timezone.timedelta(days=1),
        scheduled_end=timezone.now() + timezone.timedelta(days=1, hours=1),
        notes='Test appointment',
        legal_entity=_get_test_legal_entity(),
    )


@pytest.fixture
def encounter(db, patient, practitioner, clinic, admin_user):
    """Create an encounter."""
    return Encounter.objects.create(
        patient=patient,
        practitioner=practitioner,
        clinic=clinic,
        type='medical_consult',
        status='draft',
        occurred_at=timezone.now(),
        chief_complaint='Test complaint',
        assessment='Test assessment',
        plan='Test plan',
        created_by_user=admin_user,
        legal_entity=_get_test_legal_entity(),
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
            'created_by_user': admin_user,
            'legal_entity': _get_test_legal_entity(),
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
def appointment_factory(db, patient, practitioner, clinic):
    """
    Factory fixture for creating multiple appointments.
    
    Usage:
        apt1 = appointment_factory(status='confirmed')
        apt2 = appointment_factory(source='erp')
    """
    created_appointments = []
    
    def _create_appointment(**kwargs):
        defaults = {
            'patient': patient,
            'practitioner': practitioner,
            'clinic': clinic,
            'source': 'erp',
            'status': 'scheduled',
            'scheduled_start': timezone.now() + timezone.timedelta(days=len(created_appointments) + 1),
            'scheduled_end': timezone.now() + timezone.timedelta(days=len(created_appointments) + 1, hours=1),
            'legal_entity': _get_test_legal_entity(),
        }
        defaults.update(kwargs)
        
        appointment = Appointment.objects.create(**defaults)
        created_appointments.append(appointment)
        return appointment
    
    return _create_appointment


@pytest.fixture
def encounter_factory(db, patient, practitioner, clinic, admin_user):
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
            'clinic': clinic,
            'type': 'medical_consult',
            'status': 'draft',
            'occurred_at': timezone.now() - timezone.timedelta(hours=len(created_encounters)),
            'created_by_user': admin_user,
            'legal_entity': _get_test_legal_entity(),
        }
        defaults.update(kwargs)
        
        encounter = Encounter.objects.create(**defaults)
        created_encounters.append(encounter)
        return encounter
    
    return _create_encounter
