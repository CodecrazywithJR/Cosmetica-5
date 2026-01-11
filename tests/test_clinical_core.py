"""
Tests for Clinical Core v1: Treatment, Encounter, EncounterTreatment models + RBAC + E2E flow.

Test coverage:
1. Model tests (creation, validation, business rules)
2. Permission tests (RBAC matrix)
3. E2E flow: patient → appointment → encounter → treatment → close
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework import status

from apps.clinical.models import (
    Patient,
    Appointment,
    Encounter,
    Treatment,
    EncounterTreatment,
    AppointmentStatusChoices,
    EncounterStatusChoices,
    EncounterTypeChoices,
    ReferralSource,
)
from apps.authz.models import Practitioner, Role, UserRole
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
        username="admin",
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
        username="practitioner",
        email="practitioner@example.com",
        password="practitioner123"
    )
    role = Role.objects.create(name="Practitioner")
    UserRole.objects.create(user=user, role=role)
    
    # Create Practitioner record
    practitioner = Practitioner.objects.create(
        user=user,
        display_name="Dr. Jane Smith",
        specialty="Dermatology"
    )
    return user


@pytest.fixture
def clinical_ops_user(db):
    """Create a clinical ops user with ClinicalOps role."""
    user = User.objects.create_user(
        username="clinicalops",
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
        username="reception",
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
# Model Tests: Treatment
# ============================================================================

@pytest.mark.django_db
class TestTreatmentModel:
    """Test Treatment model creation and validation."""
    
    def test_create_treatment_minimal(self):
        """Test creating a treatment with minimal required fields."""
        treatment = Treatment.objects.create(
            name="Botox Injection"
        )
        
        assert treatment.id is not None
        assert treatment.name == "Botox Injection"
        assert treatment.is_active is True
        assert treatment.default_price is None
        assert treatment.requires_stock is False
    
    def test_create_treatment_full(self):
        """Test creating a treatment with all fields."""
        treatment = Treatment.objects.create(
            name="Hyaluronic Acid Filler",
            description="Dermal filler for facial volume restoration",
            is_active=True,
            default_price=Decimal("450.00"),
            requires_stock=True
        )
        
        assert treatment.id is not None
        assert treatment.name == "Hyaluronic Acid Filler"
        assert treatment.description == "Dermal filler for facial volume restoration"
        assert treatment.default_price == Decimal("450.00")
        assert treatment.requires_stock is True
    
    def test_treatment_unique_name(self):
        """Test that treatment names must be unique."""
        Treatment.objects.create(name="Chemical Peel")
        
        with pytest.raises(Exception):  # IntegrityError
            Treatment.objects.create(name="Chemical Peel")
    
    def test_treatment_soft_disable(self):
        """Test soft-disabling a treatment via is_active=false."""
        treatment = Treatment.objects.create(
            name="Laser Hair Removal",
            is_active=True
        )
        
        # Soft disable
        treatment.is_active = False
        treatment.save()
        
        # Can still query
        assert Treatment.objects.filter(id=treatment.id).exists()
        assert not Treatment.objects.get(id=treatment.id).is_active


# ============================================================================
# Model Tests: EncounterTreatment
# ============================================================================

@pytest.mark.django_db
class TestEncounterTreatmentModel:
    """Test EncounterTreatment linking model."""
    
    def test_create_encounter_treatment(self, patient, practitioner_user, clinic_location):
        """Test creating an encounter-treatment link."""
        practitioner = practitioner_user.practitioner
        
        encounter = Encounter.objects.create(
            patient=patient,
            practitioner=practitioner,
            location=clinic_location,
            type=EncounterTypeChoices.AESTHETIC_PROCEDURE,
            status=EncounterStatusChoices.DRAFT,
            occurred_at=timezone.now()
        )
        
        treatment = Treatment.objects.create(
            name="Botox",
            default_price=Decimal("300.00")
        )
        
        encounter_treatment = EncounterTreatment.objects.create(
            encounter=encounter,
            treatment=treatment,
            quantity=2,
            unit_price=Decimal("350.00"),
            notes="Applied to forehead and glabella"
        )
        
        assert encounter_treatment.id is not None
        assert encounter_treatment.encounter == encounter
        assert encounter_treatment.treatment == treatment
        assert encounter_treatment.quantity == 2
        assert encounter_treatment.unit_price == Decimal("350.00")
    
    def test_effective_price_with_unit_price(self):
        """Test effective_price returns unit_price when set."""
        patient_obj = Patient.objects.create(first_name="Test", last_name="Patient")
        encounter = Encounter.objects.create(
            patient=patient_obj,
            type=EncounterTypeChoices.MEDICAL_CONSULT,
            status=EncounterStatusChoices.DRAFT,
            occurred_at=timezone.now()
        )
        
        treatment = Treatment.objects.create(
            name="Filler",
            default_price=Decimal("400.00")
        )
        
        encounter_treatment = EncounterTreatment.objects.create(
            encounter=encounter,
            treatment=treatment,
            quantity=1,
            unit_price=Decimal("450.00")
        )
        
        assert encounter_treatment.effective_price == Decimal("450.00")
    
    def test_effective_price_fallback_to_default(self):
        """Test effective_price falls back to Treatment.default_price."""
        patient_obj = Patient.objects.create(first_name="Test", last_name="Patient")
        encounter = Encounter.objects.create(
            patient=patient_obj,
            type=EncounterTypeChoices.MEDICAL_CONSULT,
            status=EncounterStatusChoices.DRAFT,
            occurred_at=timezone.now()
        )
        
        treatment = Treatment.objects.create(
            name="Consultation",
            default_price=Decimal("100.00")
        )
        
        encounter_treatment = EncounterTreatment.objects.create(
            encounter=encounter,
            treatment=treatment,
            quantity=1
        )
        
        assert encounter_treatment.effective_price == Decimal("100.00")
    
    def test_total_price(self):
        """Test total_price = quantity * effective_price."""
        patient_obj = Patient.objects.create(first_name="Test", last_name="Patient")
        encounter = Encounter.objects.create(
            patient=patient_obj,
            type=EncounterTypeChoices.AESTHETIC_PROCEDURE,
            status=EncounterStatusChoices.DRAFT,
            occurred_at=timezone.now()
        )
        
        treatment = Treatment.objects.create(
            name="Botox",
            default_price=Decimal("300.00")
        )
        
        encounter_treatment = EncounterTreatment.objects.create(
            encounter=encounter,
            treatment=treatment,
            quantity=3,
            unit_price=Decimal("350.00")
        )
        
        assert encounter_treatment.total_price == Decimal("1050.00")  # 3 * 350
    
    def test_unique_treatment_per_encounter(self, patient, clinic_location):
        """Test that the same treatment cannot be added twice to an encounter."""
        encounter = Encounter.objects.create(
            patient=patient,
            location=clinic_location,
            type=EncounterTypeChoices.MEDICAL_CONSULT,
            status=EncounterStatusChoices.DRAFT,
            occurred_at=timezone.now()
        )
        
        treatment = Treatment.objects.create(name="Peel")
        
        EncounterTreatment.objects.create(
            encounter=encounter,
            treatment=treatment,
            quantity=1
        )
        
        # Attempt duplicate
        with pytest.raises(Exception):  # IntegrityError
            EncounterTreatment.objects.create(
                encounter=encounter,
                treatment=treatment,
                quantity=2
            )


# ============================================================================
# Permission Tests: RBAC Matrix
# ============================================================================

@pytest.mark.django_db
class TestTreatmentPermissions:
    """Test Treatment RBAC permissions."""
    
    def test_admin_full_access(self, admin_user, api_client):
        """Admin can CRUD treatments."""
        api_client.force_authenticate(user=admin_user)
        
        # Create
        response = api_client.post('/api/v1/clinical/treatments/', {
            'name': 'Admin Treatment',
            'default_price': '100.00'
        })
        assert response.status_code == status.HTTP_201_CREATED
        
        treatment_id = response.data['id']
        
        # Read
        response = api_client.get(f'/api/v1/clinical/treatments/{treatment_id}/')
        assert response.status_code == status.HTTP_200_OK
        
        # Update
        response = api_client.patch(f'/api/v1/clinical/treatments/{treatment_id}/', {
            'default_price': '120.00'
        })
        assert response.status_code == status.HTTP_200_OK
    
    def test_clinical_ops_full_access(self, clinical_ops_user, api_client):
        """ClinicalOps can CRUD treatments."""
        api_client.force_authenticate(user=clinical_ops_user)
        
        response = api_client.post('/api/v1/clinical/treatments/', {
            'name': 'ClinicalOps Treatment',
            'default_price': '200.00'
        })
        assert response.status_code == status.HTTP_201_CREATED
    
    def test_reception_read_only(self, reception_user, api_client):
        """Reception can read treatments but not write."""
        # Create treatment as admin
        treatment = Treatment.objects.create(name="Test Treatment")
        
        api_client.force_authenticate(user=reception_user)
        
        # Read - OK
        response = api_client.get(f'/api/v1/clinical/treatments/{treatment.id}/')
        assert response.status_code == status.HTTP_200_OK
        
        # Create - FORBIDDEN
        response = api_client.post('/api/v1/clinical/treatments/', {
            'name': 'Reception Treatment'
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_practitioner_read_only(self, practitioner_user, api_client):
        """Practitioner can read treatments but not write."""
        treatment = Treatment.objects.create(name="Test Treatment")
        
        api_client.force_authenticate(user=practitioner_user)
        
        # Read - OK
        response = api_client.get(f'/api/v1/clinical/treatments/{treatment.id}/')
        assert response.status_code == status.HTTP_200_OK
        
        # Create - FORBIDDEN
        response = api_client.post('/api/v1/clinical/treatments/', {
            'name': 'Practitioner Treatment'
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestEncounterPermissions:
    """Test Encounter RBAC permissions."""
    
    def test_reception_no_access(self, reception_user, patient, api_client):
        """Reception CANNOT access encounters (business rule)."""
        encounter = Encounter.objects.create(
            patient=patient,
            type=EncounterTypeChoices.MEDICAL_CONSULT,
            status=EncounterStatusChoices.DRAFT,
            occurred_at=timezone.now()
        )
        
        api_client.force_authenticate(user=reception_user)
        
        # Read - FORBIDDEN
        response = api_client.get(f'/api/v1/clinical/encounters/{encounter.id}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Create - FORBIDDEN
        response = api_client.post('/api/v1/clinical/encounters/', {
            'patient': str(patient.id),
            'type': 'medical_consult',
            'status': 'draft',
            'occurred_at': timezone.now().isoformat()
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_practitioner_full_access(self, practitioner_user, patient, api_client):
        """Practitioner can CRUD encounters."""
        api_client.force_authenticate(user=practitioner_user)
        
        # Create
        response = api_client.post('/api/v1/clinical/encounters/', {
            'patient': str(patient.id),
            'type': 'medical_consult',
            'status': 'draft',
            'occurred_at': timezone.now().isoformat(),
            'chief_complaint': 'Acne treatment'
        })
        assert response.status_code == status.HTTP_201_CREATED
    
    def test_clinical_ops_full_access(self, clinical_ops_user, patient, api_client):
        """ClinicalOps can CRUD encounters."""
        api_client.force_authenticate(user=clinical_ops_user)
        
        response = api_client.post('/api/v1/clinical/encounters/', {
            'patient': str(patient.id),
            'type': 'cosmetic_consult',
            'status': 'draft',
            'occurred_at': timezone.now().isoformat()
        })
        assert response.status_code == status.HTTP_201_CREATED


# ============================================================================
# E2E Flow: Patient → Appointment → Encounter → Treatment → Close
# ============================================================================

@pytest.mark.django_db
class TestClinicalE2E:
    """
    End-to-end test: Complete clinical flow from appointment to closed encounter.
    
    Flow:
    1. Reception creates patient
    2. Reception books appointment
    3. Reception checks in patient (appointment status = checked_in)
    4. Practitioner creates encounter (linked to appointment)
    5. Practitioner adds treatments to encounter
    6. Practitioner finalizes encounter (status = finalized)
    7. Verify: Appointment status = completed, encounter immutable
    """
    
    def test_complete_clinical_flow(
        self,
        reception_user,
        practitioner_user,
        clinic_location,
        referral_source,
        api_client
    ):
        """Test complete clinical flow from patient to closed encounter."""
        
        # Step 1: Reception creates patient
        api_client.force_authenticate(user=reception_user)
        response = api_client.post('/api/v1/clinical/patients/', {
            'first_name': 'Alice',
            'last_name': 'Johnson',
            'email': 'alice.johnson@example.com',
            'phone': '+33612345678',
            'referral_source': str(referral_source.id)
        })
        assert response.status_code == status.HTTP_201_CREATED
        patient_id = response.data['id']
        
        # Step 2: Reception books appointment
        practitioner = practitioner_user.practitioner
        scheduled_start = timezone.now() + timedelta(days=1)
        scheduled_end = scheduled_start + timedelta(hours=1)
        
        response = api_client.post('/api/v1/clinical/appointments/', {
            'patient': patient_id,
            'practitioner': str(practitioner.id),
            'location': str(clinic_location.id),
            'source': 'manual',
            'status': 'draft',
            'scheduled_start': scheduled_start.isoformat(),
            'scheduled_end': scheduled_end.isoformat(),
            'notes': 'Initial consultation'
        })
        assert response.status_code == status.HTTP_201_CREATED
        appointment_id = response.data['id']
        
        # Step 3: Reception confirms appointment
        response = api_client.patch(f'/api/v1/clinical/appointments/{appointment_id}/', {
            'status': 'confirmed'
        })
        assert response.status_code == status.HTTP_200_OK
        
        # Step 4: Reception checks in patient
        response = api_client.patch(f'/api/v1/clinical/appointments/{appointment_id}/', {
            'status': 'checked_in'
        })
        assert response.status_code == status.HTTP_200_OK
        
        # Step 5: Practitioner creates encounter
        api_client.force_authenticate(user=practitioner_user)
        
        # First create treatments
        treatment1 = Treatment.objects.create(
            name="Consultation - Dermatology",
            default_price=Decimal("100.00")
        )
        treatment2 = Treatment.objects.create(
            name="Botox Injection",
            default_price=Decimal("300.00")
        )
        
        response = api_client.post('/api/v1/clinical/encounters/', {
            'patient': patient_id,
            'practitioner': str(practitioner.id),
            'location': str(clinic_location.id),
            'type': 'aesthetic_procedure',
            'status': 'draft',
            'occurred_at': timezone.now().isoformat(),
            'chief_complaint': 'Wrinkles on forehead',
            'assessment': 'Dynamic wrinkles suitable for botulinum toxin',
            'plan': 'Botox 20 units forehead',
            'encounter_treatments': [
                {
                    'treatment_id': str(treatment1.id),
                    'quantity': 1,
                    'notes': 'Initial consultation'
                },
                {
                    'treatment_id': str(treatment2.id),
                    'quantity': 2,
                    'unit_price': '350.00',
                    'notes': 'Forehead and glabella'
                }
            ]
        })
        assert response.status_code == status.HTTP_201_CREATED
        encounter_id = response.data['id']
        
        # Verify encounter has treatments
        response = api_client.get(f'/api/v1/clinical/encounters/{encounter_id}/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['encounter_treatments']) == 2
        
        # Verify total price calculation
        total = sum(
            Decimal(str(t['total_price']))
            for t in response.data['encounter_treatments']
            if t['total_price'] is not None
        )
        # Expected: (1 * 100) + (2 * 350) = 800
        assert total == Decimal("800.00")
        
        # Step 6: Practitioner finalizes encounter
        response = api_client.patch(f'/api/v1/clinical/encounters/{encounter_id}/', {
            'status': 'finalized'
        })
        assert response.status_code == status.HTTP_200_OK
        
        # Step 7: Verify encounter is immutable (cannot change back to draft)
        response = api_client.patch(f'/api/v1/clinical/encounters/{encounter_id}/', {
            'status': 'draft'
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'status' in response.data
        
        # Step 8: Reception marks appointment as completed
        api_client.force_authenticate(user=reception_user)
        response = api_client.patch(f'/api/v1/clinical/appointments/{appointment_id}/', {
            'status': 'completed'
        })
        assert response.status_code == status.HTTP_200_OK
        
        # Verify final state
        response = api_client.get(f'/api/v1/clinical/appointments/{appointment_id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'completed'
