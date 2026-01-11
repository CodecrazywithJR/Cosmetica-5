"""
Tests for Clinical Core Fase 2.2: Practitioners + Appointments + Appointment→Encounter Integration.

Test coverage:
1. Practitioner model tests (role_type)
2. Appointment model tests (new states: SCHEDULED, source: PUBLIC_LEAD)
3. Appointment→Encounter integration (create_encounter_from_appointment)
4. Permission tests (Practitioner + Appointment RBAC)
5. E2E flow: create appointment → complete → create encounter → finalize
"""
import pytest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework import status

from apps.authz.models import Practitioner, PractitionerRoleChoices, Role, UserRole
from apps.clinical.models import (
    Patient,
    Appointment,
    Encounter,
    Treatment,
    EncounterTreatment,
    AppointmentStatusChoices,
    AppointmentSourceChoices,
    EncounterTypeChoices,
    EncounterStatusChoices,
    ReferralSource,
)
from apps.clinical.services import create_encounter_from_appointment
from apps.core.models import ClinicLocation

User = get_user_model()


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def clinic_location(db):
    """Create a test clinic location."""
    return ClinicLocation.objects.create(
        name="Test Clinic",
        address_line1="123 Test St",
        city="Paris",
        postal_code="75001",
        country_code="FR"
    )


@pytest.fixture
def referral_source(db):
    """Create a test referral source."""
    return ReferralSource.objects.create(
        code="test",
        label="Test Source"
    )


@pytest.fixture
def patient(db, referral_source):
    """Create a test patient."""
    return Patient.objects.create(
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone="+33612345678",
        referral_source=referral_source
    )


@pytest.fixture
def admin_user(db):
    """Create an admin user with Admin role."""
    user = User.objects.create_user(
        email="admin@example.com",
        password="admin123"
    )
    role = Role.objects.create(name="Admin")
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.fixture
def practitioner_user(db):
    """Create a practitioner user with Practitioner role."""
    user = User.objects.create_user(
        email="practitioner@example.com",
        password="practitioner123"
    )
    role = Role.objects.create(name="Practitioner")
    UserRole.objects.create(user=user, role=role)
    
    # Create Practitioner record with PRACTITIONER role_type
    practitioner = Practitioner.objects.create(
        user=user,
        display_name="Dr. Jane Smith",
        role_type=PractitionerRoleChoices.PRACTITIONER,
        specialty="Dermatology"
    )
    return user


@pytest.fixture
def clinical_ops_user(db):
    """Create a clinical ops user with ClinicalOps role."""
    user = User.objects.create_user(
        email="clinicalops@example.com",
        password="clinicalops123"
    )
    role = Role.objects.create(name="ClinicalOps")
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.fixture
def reception_user(db):
    """Create a reception user with Reception role."""
    user = User.objects.create_user(
        email="reception@example.com",
        password="reception123"
    )
    role = Role.objects.create(name="Reception")
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.fixture
def api_client():
    """Create an API client."""
    return APIClient()


# ============================================================================
# Model Tests: Practitioner (role_type)
# ============================================================================

@pytest.mark.django_db
class TestPractitionerModel:
    """Test Practitioner model with role_type field."""
    
    def test_create_practitioner_with_default_role(self):
        """Test creating practitioner with default role_type (PRACTITIONER)."""
        user = User.objects.create_user(
            email="doctor1@example.com",
            password="test123"
        )
        
        practitioner = Practitioner.objects.create(
            user=user,
            display_name="Dr. John Smith"
        )
        
        assert practitioner.role_type == PractitionerRoleChoices.PRACTITIONER
        assert practitioner.specialty == "Dermatology"  # Default
        assert practitioner.is_active is True
    
    def test_create_practitioner_with_assistant_role(self):
        """Test creating practitioner with ASSISTANT role_type."""
        user = User.objects.create_user(
            email="assistant1@example.com",
            password="test123"
        )
        
        practitioner = Practitioner.objects.create(
            user=user,
            display_name="Marie Dupont",
            role_type=PractitionerRoleChoices.ASSISTANT,
            specialty="Clinical Assistant"
        )
        
        assert practitioner.role_type == PractitionerRoleChoices.ASSISTANT
        assert practitioner.get_role_type_display() == "Assistant"
    
    def test_create_practitioner_with_clinical_manager_role(self):
        """Test creating practitioner with CLINICAL_MANAGER role_type."""
        user = User.objects.create_user(
            email="manager1@example.com",
            password="test123"
        )
        
        practitioner = Practitioner.objects.create(
            user=user,
            display_name="Sophie Martin",
            role_type=PractitionerRoleChoices.CLINICAL_MANAGER,
            specialty="Clinical Operations"
        )
        
        assert practitioner.role_type == PractitionerRoleChoices.CLINICAL_MANAGER
        assert str(practitioner) == "Sophie Martin (Clinical Manager)"


# ============================================================================
# Model Tests: Appointment (SCHEDULED state, PUBLIC_LEAD source)
# ============================================================================

@pytest.mark.django_db
class TestAppointmentModel:
    """Test Appointment model with new SCHEDULED state and PUBLIC_LEAD source."""
    
    def test_create_appointment_scheduled_state(self, patient, practitioner_user, clinic_location):
        """Test creating appointment with SCHEDULED as initial state."""
        practitioner = practitioner_user.practitioner
        scheduled_start = timezone.now() + timedelta(days=1)
        scheduled_end = scheduled_start + timedelta(hours=1)
        
        appointment = Appointment.objects.create(
            patient=patient,
            practitioner=practitioner,
            location=clinic_location,
            source=AppointmentSourceChoices.MANUAL,
            status=AppointmentStatusChoices.SCHEDULED,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            notes="Initial consultation"
        )
        
        assert appointment.status == AppointmentStatusChoices.SCHEDULED
        assert appointment.source == AppointmentSourceChoices.MANUAL
    
    def test_create_appointment_public_lead_source(self, patient, clinic_location):
        """Test creating appointment with PUBLIC_LEAD source."""
        scheduled_start = timezone.now() + timedelta(days=2)
        scheduled_end = scheduled_start + timedelta(hours=1)
        
        appointment = Appointment.objects.create(
            patient=patient,
            location=clinic_location,
            source=AppointmentSourceChoices.PUBLIC_LEAD,
            status=AppointmentStatusChoices.SCHEDULED,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            notes="Lead from website form"
        )
        
        assert appointment.source == AppointmentSourceChoices.PUBLIC_LEAD
        assert appointment.status == AppointmentStatusChoices.SCHEDULED
    
    def test_appointment_status_transitions_from_scheduled(self, patient, clinic_location):
        """Test allowed transitions from SCHEDULED state."""
        scheduled_start = timezone.now() + timedelta(days=1)
        scheduled_end = scheduled_start + timedelta(hours=1)
        
        appointment = Appointment.objects.create(
            patient=patient,
            location=clinic_location,
            source=AppointmentSourceChoices.MANUAL,
            status=AppointmentStatusChoices.SCHEDULED,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end
        )
        
        # Allowed transition: SCHEDULED → CONFIRMED
        appointment.status = AppointmentStatusChoices.CONFIRMED
        appointment.save()
        assert appointment.status == AppointmentStatusChoices.CONFIRMED
        
        # Allowed transition: CONFIRMED → CHECKED_IN
        appointment.status = AppointmentStatusChoices.CHECKED_IN
        appointment.save()
        assert appointment.status == AppointmentStatusChoices.CHECKED_IN
        
        # Allowed transition: CHECKED_IN → COMPLETED
        appointment.status = AppointmentStatusChoices.COMPLETED
        appointment.save()
        assert appointment.status == AppointmentStatusChoices.COMPLETED


# ============================================================================
# Integration Tests: Appointment → Encounter
# ============================================================================

@pytest.mark.django_db
class TestAppointmentEncounterIntegration:
    """Test create_encounter_from_appointment service."""
    
    def test_create_encounter_from_completed_appointment(
        self,
        patient,
        practitioner_user,
        clinic_location
    ):
        """Test creating encounter from COMPLETED appointment."""
        practitioner = practitioner_user.practitioner
        scheduled_start = timezone.now()
        scheduled_end = scheduled_start + timedelta(hours=1)
        
        # Create and complete appointment
        appointment = Appointment.objects.create(
            patient=patient,
            practitioner=practitioner,
            location=clinic_location,
            source=AppointmentSourceChoices.MANUAL,
            status=AppointmentStatusChoices.COMPLETED,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end
        )
        
        # Create encounter from appointment
        encounter = create_encounter_from_appointment(
            appointment=appointment,
            encounter_type=EncounterTypeChoices.MEDICAL_CONSULT,
            created_by=practitioner_user,
            chief_complaint="Patient reports acne",
            assessment="Mild inflammatory acne"
        )
        
        assert encounter is not None
        assert encounter.patient == patient
        assert encounter.practitioner == practitioner
        assert encounter.location == clinic_location
        assert encounter.type == EncounterTypeChoices.MEDICAL_CONSULT
        assert encounter.status == EncounterStatusChoices.DRAFT
        assert encounter.chief_complaint == "Patient reports acne"
        
        # Verify appointment is linked to encounter
        appointment.refresh_from_db()
        assert appointment.encounter == encounter
    
    def test_create_encounter_from_non_completed_appointment_fails(
        self,
        patient,
        clinic_location,
        practitioner_user
    ):
        """Test that creating encounter from non-COMPLETED appointment fails."""
        scheduled_start = timezone.now()
        scheduled_end = scheduled_start + timedelta(hours=1)
        
        appointment = Appointment.objects.create(
            patient=patient,
            location=clinic_location,
            source=AppointmentSourceChoices.MANUAL,
            status=AppointmentStatusChoices.SCHEDULED,  # NOT completed
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end
        )
        
        # Should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            create_encounter_from_appointment(
                appointment=appointment,
                encounter_type=EncounterTypeChoices.MEDICAL_CONSULT,
                created_by=practitioner_user
            )
        
        assert "must be 'completed' first" in str(exc_info.value)
    
    def test_create_encounter_from_appointment_already_with_encounter_fails(
        self,
        patient,
        practitioner_user,
        clinic_location
    ):
        """Test that creating encounter from appointment that already has one fails."""
        practitioner = practitioner_user.practitioner
        scheduled_start = timezone.now()
        
        # Create encounter manually
        existing_encounter = Encounter.objects.create(
            patient=patient,
            practitioner=practitioner,
            location=clinic_location,
            type=EncounterTypeChoices.MEDICAL_CONSULT,
            status=EncounterStatusChoices.DRAFT,
            occurred_at=scheduled_start
        )
        
        # Create appointment linked to encounter
        appointment = Appointment.objects.create(
            patient=patient,
            practitioner=practitioner,
            location=clinic_location,
            source=AppointmentSourceChoices.MANUAL,
            status=AppointmentStatusChoices.COMPLETED,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_start + timedelta(hours=1),
            encounter=existing_encounter
        )
        
        # Should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            create_encounter_from_appointment(
                appointment=appointment,
                encounter_type=EncounterTypeChoices.MEDICAL_CONSULT,
                created_by=practitioner_user
            )
        
        assert "already has an encounter" in str(exc_info.value)


# ============================================================================
# Permission Tests: Practitioner RBAC
# ============================================================================

@pytest.mark.django_db
class TestPractitionerPermissions:
    """Test Practitioner endpoint RBAC."""
    
    def test_admin_can_list_practitioners(self, admin_client):
        """Admin can list practitioners."""
        response = admin_client.get('/api/v1/practitioners/')
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data or isinstance(response.data, list)
    
    def test_practitioner_can_view_self(self, practitioner_client):
        """Practitioner can view their own profile."""
        response = practitioner_client.get('/api/v1/practitioners/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_reception_can_view_practitioners(self, reception_client):
        """Reception can view practitioners (for booking appointments)."""
        response = reception_client.get('/api/v1/practitioners/')
        assert response.status_code == status.HTTP_200_OK


# ============================================================================
# E2E Flow: Appointment → Encounter Complete Flow
# ============================================================================

@pytest.mark.django_db
class TestAppointmentEncounterE2E:
    """
    End-to-end test: Complete flow from appointment to closed encounter.
    
    Flow (Fase 2.2 complete):
    1. Create patient (model-level)
    2. Reception creates appointment (SCHEDULED) via API
    3. Reception confirms appointment (CONFIRMED)
    4. Reception checks in patient (CHECKED_IN)
    5. Reception completes appointment (COMPLETED)
    6. Practitioner creates encounter from completed appointment (service-level)
    7. Practitioner adds treatments to encounter
    8. Practitioner finalizes encounter (FINALIZED)
    9. Verify: Appointment linked to encounter, encounter has treatments
    """
    
    def test_complete_appointment_encounter_flow(
        self,
        reception_client,
        practitioner_client,
        clinic_location,
        referral_source
    ):
        """Test complete flow from appointment creation to encounter finalization."""
        
        # Step 1: Create patient (model-level for simplicity)
        patient = Patient.objects.create(
            first_name='Alice',
            last_name='Johnson',
            email='alice.johnson@example.com',
            phone='+33612345678',
            referral_source=referral_source
        )
        
        # Get practitioner from practitioner_client
        practitioner = Practitioner.objects.first()
        
        # Step 2: Reception creates appointment (SCHEDULED)
        scheduled_start = timezone.now() + timedelta(days=1)
        scheduled_end = scheduled_start + timedelta(hours=1)
        
        response = reception_client.post('/api/v1/clinical/appointments/', {
            'patient': str(patient.id),
            'practitioner': str(practitioner.id),
            'location': str(clinic_location.id),
            'source': 'manual',
            'status': 'scheduled',
            'scheduled_start': scheduled_start.isoformat(),
            'scheduled_end': scheduled_end.isoformat(),
            'notes': 'Initial consultation'
        })
        assert response.status_code == status.HTTP_201_CREATED
        appointment_id = response.data['id']
        
        # Step 3: Reception confirms appointment
        response = reception_client.patch(f'/api/v1/clinical/appointments/{appointment_id}/', {
            'status': 'confirmed'
        })
        assert response.status_code == status.HTTP_200_OK
        
        # Step 4: Reception checks in patient
        response = reception_client.patch(f'/api/v1/clinical/appointments/{appointment_id}/', {
            'status': 'checked_in'
        })
        assert response.status_code == status.HTTP_200_OK
        
        # Step 5: Reception completes appointment
        response = reception_client.patch(f'/api/v1/clinical/appointments/{appointment_id}/', {
            'status': 'completed'
        })
        assert response.status_code == status.HTTP_200_OK
        
        # Step 6: Practitioner creates encounter from completed appointment (service-level)
        appointment = Appointment.objects.get(id=appointment_id)
        user = practitioner_client.handler._force_user  # Get authenticated user
        
        # Create encounter using service
        encounter = create_encounter_from_appointment(
            appointment=appointment,
            encounter_type='medical_consult',
            created_by=user,
            chief_complaint='Acne treatment',
            assessment='Mild inflammatory acne',
            plan='Topical treatment'
        )
        
        assert encounter is not None
        assert encounter.status == 'draft'
        
        # Step 7: Practitioner adds treatments to encounter
        treatment = Treatment.objects.create(
            name="Acne Consultation",
            default_price=Decimal("100.00")
        )
        
        EncounterTreatment.objects.create(
            encounter=encounter,
            treatment=treatment,
            quantity=1,
            notes="Initial consultation"
        )
        
        # Verify encounter has treatments
        assert encounter.encounter_treatments.count() == 1
        
        # Step 8: Practitioner finalizes encounter
        encounter.status = 'finalized'
        encounter.save()
        
        # Step 9: Verify final state
        appointment.refresh_from_db()
        encounter.refresh_from_db()
        
        assert appointment.status == 'completed'
        assert appointment.encounter == encounter
        assert encounter.status == 'finalized'
        assert encounter.encounter_treatments.count() == 1
        assert encounter.patient == patient
        assert encounter.practitioner == practitioner
