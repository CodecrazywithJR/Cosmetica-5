"""
Business rules tests for Layer 1 ERP clinical module.

Tests cover:
1. Appointments require patient (no exceptions)
2. No overlapping appointments for same practitioner (active statuses only)
3. Cancelled/no_show do not block slots
4. Status transition validation
5. no_show only after scheduled_start
6. Reception cannot access clinical endpoints
7. Reception cannot see clinical fields in responses
8. Sale-Appointment relationship is optional
"""
import pytest
from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework import status

from apps.authz.models import User, Role, UserRole, Practitioner
from apps.clinical.models import Patient, Appointment, PractitionerSchedule
from apps.sales.models import Sale
from apps.core.models import Clinic
from tests.conftest import TEST_PASSWORD


@pytest.fixture
def api_client():
    """Create API client"""
    return APIClient()


@pytest.fixture
def admin_user(db):
    """Create admin user with role"""
    user = User.objects.create_user(
        email='admin@test.com',
        password=TEST_PASSWORD
    )
    role, _ = Role.objects.get_or_create(name='admin')
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.fixture
def practitioner_user(db):
    """Create practitioner user with role and practitioner profile"""
    user = User.objects.create_user(
        email='practitioner@test.com',
        password=TEST_PASSWORD
    )
    role, _ = Role.objects.get_or_create(name='practitioner')
    UserRole.objects.create(user=user, role=role)
    
    practitioner = Practitioner.objects.create(
        user=user,
        display_name='Dr. Test',
        specialty='Dermatology'
    )
    return user, practitioner


@pytest.fixture
def reception_user(db):
    """Create reception user with role"""
    user = User.objects.create_user(
        email='reception@test.com',
        password=TEST_PASSWORD
    )
    role, _ = Role.objects.get_or_create(name='reception')
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.fixture
def patient(db, admin_user):
    """Create test patient"""
    return Patient.objects.create(
        first_name='John',
        last_name='Doe',
        email='john.doe@test.com',
        created_by_user=admin_user
    )


@pytest.fixture
def location(db, legal_entity):
    return Clinic.objects.create(
        name='Main Clinic',
        city='Test City',
        legal_entity=legal_entity,
    )


@pytest.fixture
def practitioner_schedule(db, practitioner_user, location):
    """Create working hours for all weekdays so AvailabilityService generates slots."""
    from datetime import time
    _, practitioner = practitioner_user
    schedules = []
    for weekday in range(7):
        schedules.append(PractitionerSchedule(
            practitioner=practitioner,
            clinic=location,
            weekday=weekday,
            start_time=time(8, 0),
            end_time=time(18, 0),
            is_active=True,
        ))
    PractitionerSchedule.objects.bulk_create(schedules)
    return schedules


# ============================================================================
# BUSINESS RULE 1: Appointments require patient
# ============================================================================

@pytest.mark.django_db
def test_cannot_create_appointment_without_patient(api_client, admin_user, practitioner_user, location):
    """
    BUSINESS RULE: No se permite crear una cita sin paciente (sin excepciones).
    Direct API creation validates at model level.
    """
    _, practitioner = practitioner_user
    now = timezone.now()

    # Appointment model requires patient (NOT NULL FK)
    from django.db import IntegrityError
    with pytest.raises((IntegrityError, ValidationError)):
        Appointment.objects.create(
            practitioner=practitioner,
            clinic=location,
            source='erp',
            status='scheduled',
            scheduled_start=now + timedelta(days=1),
            scheduled_end=now + timedelta(days=1, hours=1),
        )


# ============================================================================
# BUSINESS RULE 2: No overlapping appointments for same practitioner
# ============================================================================

@pytest.mark.django_db
def test_cannot_overlap_appointments_for_same_professional_active_states(
    api_client, admin_user, practitioner_user, patient, location, practitioner_schedule
):
    """
    BUSINESS RULE: Un mismo profesional no puede tener dos citas con rangos de tiempo solapados.
    Direct API creation is disabled, so we use the booking endpoint.
    """
    _, practitioner = practitioner_user
    api_client.force_authenticate(user=admin_user)

    now = timezone.now()
    future_date = (now + timedelta(days=2)).date()

    # Book first appointment via booking endpoint
    response1 = api_client.post(
        f'/api/v1/clinical/practitioners/{practitioner.id}/book/',
        {
            'date': future_date.strftime('%Y-%m-%d'),
            'start': '10:00',
            'end': '11:00',
            'slot_duration': 60,
            'patient_id': str(patient.id),
            'location_id': str(location.id),
        },
        format='json',
    )
    assert response1.status_code == status.HTTP_201_CREATED

    # Attempt to book overlapping appointment (should fail with 409 Conflict)
    response2 = api_client.post(
        f'/api/v1/clinical/practitioners/{practitioner.id}/book/',
        {
            'date': future_date.strftime('%Y-%m-%d'),
            'start': '10:30',
            'end': '11:30',
            'slot_duration': 60,
            'patient_id': str(patient.id),
            'location_id': str(location.id),
        },
        format='json',
    )
    assert response2.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT)


@pytest.mark.django_db
def test_cancelled_or_no_show_does_not_block_slot(
    api_client, admin_user, practitioner_user, patient, location, practitioner_schedule
):
    """
    BUSINESS RULE: cancelled y no_show no deben bloquear la agenda.
    Use booking endpoint since direct creation is disabled.
    """
    _, practitioner = practitioner_user
    api_client.force_authenticate(user=admin_user)

    now = timezone.now()
    future_date = (now + timedelta(days=3)).date()

    # Create cancelled appointment at model level
    Appointment.objects.create(
        patient=patient,
        practitioner=practitioner,
        clinic=location,
        source='erp',
        status='cancelled',
        scheduled_start=timezone.make_aware(
            timezone.datetime.combine(future_date, timezone.datetime.strptime('10:00', '%H:%M').time())
        ) if timezone.is_naive(timezone.datetime.combine(future_date, timezone.datetime.strptime('10:00', '%H:%M').time())) else timezone.datetime.combine(future_date, timezone.datetime.strptime('10:00', '%H:%M').time()).replace(tzinfo=timezone.utc),
        scheduled_end=timezone.make_aware(
            timezone.datetime.combine(future_date, timezone.datetime.strptime('11:00', '%H:%M').time())
        ) if timezone.is_naive(timezone.datetime.combine(future_date, timezone.datetime.strptime('11:00', '%H:%M').time())) else timezone.datetime.combine(future_date, timezone.datetime.strptime('11:00', '%H:%M').time()).replace(tzinfo=timezone.utc),
    )

    # Book same slot — should succeed because cancelled doesn't block
    response = api_client.post(
        f'/api/v1/clinical/practitioners/{practitioner.id}/book/',
        {
            'date': future_date.strftime('%Y-%m-%d'),
            'start': '10:00',
            'end': '11:00',
            'slot_duration': 60,
            'patient_id': str(patient.id),
            'location_id': str(location.id),
        },
        format='json',
    )
    assert response.status_code == status.HTTP_201_CREATED


# ============================================================================
# BUSINESS RULE 3: Status transitions validation
# ============================================================================

@pytest.mark.django_db
def test_invalid_status_transition_is_rejected(
    api_client, admin_user, practitioner_user, patient, location
):
    """
    BUSINESS RULE: Debe impedirse cambiar el estado por PATCH directo si no es una transición válida.
    completed, cancelled, no_show son terminales.
    """
    _, practitioner = practitioner_user
    api_client.force_authenticate(user=admin_user)
    
    now = timezone.now()
    
    # Create completed appointment (terminal state)
    appt = Appointment.objects.create(
        patient=patient,
        practitioner=practitioner,
        clinic=location,
        source='erp',
        status='completed',
        scheduled_start=now - timedelta(hours=2),
        scheduled_end=now - timedelta(hours=1)
    )
    
    # Attempt to transition from terminal state (should fail)
    response = api_client.post(f'/api/v1/clinical/appointments/{appt.id}/transition/', {
        'status': 'cancelled'
    })
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'terminal' in str(response.data).lower()


@pytest.mark.django_db
def test_scheduled_to_confirmed_transition_allowed(
    api_client, admin_user, practitioner_user, patient, location
):
    """
    BUSINESS RULE: scheduled -> confirmed es una transición permitida.
    """
    _, practitioner = practitioner_user
    api_client.force_authenticate(user=admin_user)
    
    now = timezone.now()
    
    # Create draft appointment
    appt = Appointment.objects.create(
        patient=patient,
        practitioner=practitioner,
        clinic=location,
        source='erp',
        status='scheduled',
        scheduled_start=now + timedelta(days=1),
        scheduled_end=now + timedelta(days=1, hours=1)
    )
    
    # Transition to confirmed (should succeed)
    response = api_client.post(f'/api/v1/clinical/appointments/{appt.id}/transition/', {
        'status': 'confirmed'
    })
    
    assert response.status_code == status.HTTP_200_OK
    assert response.data['status'] == 'confirmed'


# ============================================================================
# BUSINESS RULE 4: no_show only after scheduled_start
# ============================================================================

@pytest.mark.django_db
def test_no_show_only_after_start_time(
    api_client, admin_user, practitioner_user, patient, location
):
    """
    BUSINESS RULE: no_show solo debe permitirse si start_at ya pasó.
    """
    _, practitioner = practitioner_user
    api_client.force_authenticate(user=admin_user)
    
    now = timezone.now()
    
    # Create future appointment
    appt = Appointment.objects.create(
        patient=patient,
        practitioner=practitioner,
        clinic=location,
        source='erp',
        status='confirmed',
        scheduled_start=now + timedelta(days=1),  # Future
        scheduled_end=now + timedelta(days=1, hours=1)
    )
    
    # Attempt to mark as no_show before start time (should fail)
    response = api_client.post(f'/api/v1/clinical/appointments/{appt.id}/transition/', {
        'status': 'no_show'
    })
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'no show' in str(response.data).lower() or 'hora de inicio' in str(response.data).lower()


# ============================================================================
# BUSINESS RULE 5: Reception cannot access clinical endpoints
# ============================================================================

@pytest.mark.django_db
def test_reception_cannot_access_clinical_endpoints(api_client, reception_user, patient):
    """
    BUSINESS RULE: Un usuario con rol "recepción" NO puede acceder a endpoints clínicos.
    """
    api_client.force_authenticate(user=reception_user)
    
    # Attempt to access encounters endpoint
    response = api_client.get('/api/v1/clinical/encounters/')
    assert response.status_code == status.HTTP_403_FORBIDDEN
    
    # Attempt to access photos endpoint (correct path is /api/v1/clinical/photos/)
    response = api_client.get('/api/v1/clinical/photos/')
    assert response.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)


# ============================================================================
# BUSINESS RULE 6: Reception cannot see clinical fields
# ============================================================================

@pytest.mark.django_db
def test_reception_cannot_see_diagnosis_fields_in_patient_payload(
    api_client, reception_user, admin_user, patient
):
    """
    BUSINESS RULE: Recepción no ve diagnósticos ni notas clínicas.
    Ni ver campos clínicos embebidos en respuestas (serializers deben ocultarlos).
    """
    # Add clinical notes to patient
    patient.notes = 'CONFIDENTIAL MEDICAL NOTES'
    patient.save()
    
    # Reception user should NOT see notes
    api_client.force_authenticate(user=reception_user)
    response = api_client.get(f'/api/v1/clinical/patients/{patient.id}/')
    
    assert response.status_code == status.HTTP_200_OK
    assert 'notes' not in response.data or response.data.get('notes') is None
    assert 'CONFIDENTIAL' not in str(response.data)
    
    # Admin user SHOULD see notes
    api_client.force_authenticate(user=admin_user)
    response = api_client.get(f'/api/v1/clinical/patients/{patient.id}/')
    
    assert response.status_code == status.HTTP_200_OK
    assert response.data.get('notes') == 'CONFIDENTIAL MEDICAL NOTES'


# ============================================================================
# BUSINESS RULE 7: Sale-Appointment relationship is optional
# ============================================================================

@pytest.mark.django_db
def test_sale_can_exist_without_appointment_and_link_is_optional(db, patient):
    """
    BUSINESS RULE: La venta puede existir sin cita. La cita puede existir sin venta.
    Si existe relación, validarla (FK nullable / m2m) y asegurar que no sea obligatoria.
    """
    from apps.legal.models import LegalEntity
    le = LegalEntity.objects.first() or LegalEntity.objects.create(
        siret='00000000000099',
        trade_name='Test LE',
        legal_name='Test Legal Entity',
        country_code='FR',
        is_active=True,
    )
    # Create sale without appointment (should succeed)
    sale = Sale.objects.create(
        patient=patient,
        legal_entity=le,
        subtotal=100.00,
        total=100.00,
        status='draft',
    )

    assert sale.id is not None
    # Verify appointment FK is nullable
    assert sale.appointment is None


# ============================================================================
# BUSINESS RULE 8: Patient is required for all appointments
# ============================================================================

@pytest.mark.django_db
def test_appointment_model_validates_patient_required(db, practitioner_user, location):
    """
    BUSINESS RULE: Patient is required at model level.
    """
    _, practitioner = practitioner_user
    now = timezone.now()
    
    # Attempt to create appointment without patient
    appt = Appointment(
        practitioner=practitioner,
        clinic=location,
        source='erp',
        status='scheduled',
        scheduled_start=now + timedelta(days=1),
        scheduled_end=now + timedelta(days=1, hours=1)
    )
    
    # Model validation should fail
    with pytest.raises(ValidationError) as exc_info:
        appt.clean()
    
    assert 'patient' in str(exc_info.value).lower()
