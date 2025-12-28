"""
Tests for Layer 2 A1: Clinical Domain Integrity.

Validates business rules and invariants:
1. Encounter requires patient (NOT NULL)
2. If encounter.appointment exists, then encounter.patient == appointment.patient
3. Encounter can exist without appointment
4. If photo.encounter exists, then photo.patient == encounter.patient
5. Reception cannot access clinical entities
"""
import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.test import APIClient
from django.utils import timezone
from datetime import timedelta

pytestmark = pytest.mark.django_db


class TestEncounterPatientInvariant:
    """Test that Encounter requires a patient."""
    
    def test_encounter_requires_patient_model_level(self):
        """Encounter.patient is NOT NULL at model level."""
        from apps.clinical.models import Encounter
        from django.db import IntegrityError
        
        # Attempt to create encounter without patient should fail at DB level
        with pytest.raises((IntegrityError, DjangoValidationError)):
            encounter = Encounter(
                type='consultation',
                status='scheduled',
                occurred_at=timezone.now(),
                chief_complaint='Test'
            )
            encounter.save()  # Should fail: patient is required
    
    def test_encounter_requires_patient_serializer_level(self, api_client, practitioner_user):
        """Encounter creation without patient fails at serializer level."""
        api_client.force_authenticate(user=practitioner_user)
        
        response = api_client.post(
            '/api/encounters/',
            {
                'type': 'consultation',
                'status': 'scheduled',
                'occurred_at': timezone.now().isoformat(),
                'chief_complaint': 'Test complaint'
            },
            format='json'
        )
        
        # Should fail with 400 Bad Request
        assert response.status_code == 400
        assert 'patient' in response.data or 'patient' in str(response.data).lower()


class TestEncounterAppointmentPatientCoherence:
    """Test that if encounter.appointment exists, both must share the same patient."""
    
    @pytest.fixture
    def patient_a(self):
        from apps.clinical.models import Patient
        return Patient.objects.create(
            first_name='Alice',
            last_name='Anderson',
            birth_date='1990-01-01',
            phone='555-0001',
            email='alice@example.com'
        )
    
    @pytest.fixture
    def patient_b(self):
        from apps.clinical.models import Patient
        return Patient.objects.create(
            first_name='Bob',
            last_name='Brown',
            birth_date='1985-05-15',
            phone='555-0002',
            email='bob@example.com'
        )
    
    @pytest.fixture
    def practitioner(self, practitioner_user):
        from apps.authz.models import Practitioner
        practitioner, _ = Practitioner.objects.get_or_create(
            user=practitioner_user,
            defaults={
                'license_number': 'MED12345',
                'specialty': 'Dermatology'
            }
        )
        return practitioner
    
    @pytest.fixture
    def appointment_for_patient_a(self, patient_a, practitioner):
        from apps.clinical.models import Appointment
        return Appointment.objects.create(
            patient=patient_a,
            practitioner=practitioner,
            source='manual',
            status='confirmed',
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2)
        )
    
    def test_encounter_appointment_patient_must_match_serializer(
        self, api_client, practitioner_user, patient_a, patient_b, appointment_for_patient_a
    ):
        """Creating encounter with mismatched patient and appointment fails."""
        api_client.force_authenticate(user=practitioner_user)
        
        response = api_client.post(
            '/api/encounters/',
            {
                'patient': str(patient_b.id),  # Patient B
                'appointment': str(appointment_for_patient_a.id),  # Appointment for Patient A
                'type': 'consultation',
                'status': 'scheduled',
                'occurred_at': timezone.now().isoformat(),
                'chief_complaint': 'Test'
            },
            format='json'
        )
        
        # Should fail with 400
        assert response.status_code == 400
        
        # Error should mention patient mismatch
        error_message = str(response.data).lower()
        assert 'patient' in error_message or 'mismatch' in error_message
    
    def test_encounter_appointment_patient_must_match_model(
        self, patient_a, patient_b, appointment_for_patient_a, practitioner
    ):
        """Model-level validation rejects patient-appointment mismatch."""
        from apps.clinical.models import Encounter
        
        encounter = Encounter(
            patient=patient_b,  # Patient B
            appointment=appointment_for_patient_a,  # Appointment for Patient A
            practitioner=practitioner,
            type='consultation',
            status='scheduled',
            occurred_at=timezone.now()
        )
        
        # Should fail at clean() level
        with pytest.raises(DjangoValidationError) as exc_info:
            encounter.clean()
        
        # Error should be on 'appointment' field
        assert 'appointment' in exc_info.value.message_dict
    
    def test_encounter_with_matching_patient_appointment_succeeds(
        self, api_client, practitioner_user, patient_a, appointment_for_patient_a
    ):
        """Creating encounter with matching patient and appointment succeeds."""
        api_client.force_authenticate(user=practitioner_user)
        
        response = api_client.post(
            '/api/encounters/',
            {
                'patient': str(patient_a.id),  # Same patient
                'appointment': str(appointment_for_patient_a.id),  # Appointment for Patient A
                'type': 'consultation',
                'status': 'scheduled',
                'occurred_at': timezone.now().isoformat(),
                'chief_complaint': 'Matching test'
            },
            format='json'
        )
        
        # Should succeed
        assert response.status_code == 201
        assert response.data['patient'] == str(patient_a.id)
        assert response.data['appointment'] == str(appointment_for_patient_a.id)


class TestEncounterCanExistWithoutAppointment:
    """Test that encounters can exist without appointments."""
    
    @pytest.fixture
    def patient(self):
        from apps.clinical.models import Patient
        return Patient.objects.create(
            first_name='Charlie',
            last_name='Chen',
            birth_date='1992-03-20',
            phone='555-0003',
            email='charlie@example.com'
        )
    
    def test_encounter_without_appointment_is_valid(
        self, api_client, practitioner_user, patient
    ):
        """Encounter can be created without appointment (walk-in patient)."""
        api_client.force_authenticate(user=practitioner_user)
        
        response = api_client.post(
            '/api/encounters/',
            {
                'patient': str(patient.id),
                'type': 'consultation',
                'status': 'scheduled',
                'occurred_at': timezone.now().isoformat(),
                'chief_complaint': 'Walk-in patient'
                # No appointment field
            },
            format='json'
        )
        
        # Should succeed
        assert response.status_code == 201
        assert response.data['patient'] == str(patient.id)
        assert response.data['appointment'] is None


class TestSkinPhotoEncounterPatientCoherence:
    """Test that if photo.encounter exists, both must share the same patient."""
    
    @pytest.fixture
    def patient_a(self):
        from apps.clinical.models import Patient
        return Patient.objects.create(
            first_name='Diana',
            last_name='Davis',
            birth_date='1988-07-12',
            phone='555-0004',
            email='diana@example.com'
        )
    
    @pytest.fixture
    def patient_b(self):
        from apps.clinical.models import Patient
        return Patient.objects.create(
            first_name='Eve',
            last_name='Evans',
            birth_date='1995-11-30',
            phone='555-0005',
            email='eve@example.com'
        )
    
    @pytest.fixture
    def encounter_for_patient_a(self, patient_a, practitioner_user):
        from apps.clinical.models import Encounter
        from apps.authz.models import Practitioner
        
        practitioner, _ = Practitioner.objects.get_or_create(
            user=practitioner_user,
            defaults={'license_number': 'MED67890', 'specialty': 'Dermatology'}
        )
        
        return Encounter.objects.create(
            patient=patient_a,
            practitioner=practitioner,
            type='consultation',
            status='scheduled',
            occurred_at=timezone.now()
        )
    
    def test_photo_encounter_patient_must_match_model(
        self, patient_a, patient_b, encounter_for_patient_a
    ):
        """Model-level validation rejects photo-encounter patient mismatch."""
        from apps.photos.models import SkinPhoto
        
        photo = SkinPhoto(
            patient=patient_b,  # Patient B
            encounter=encounter_for_patient_a,  # Encounter for Patient A
            body_part='face',
            tags='test'
        )
        
        # Should fail at clean() level
        with pytest.raises(DjangoValidationError) as exc_info:
            photo.clean()
        
        # Error should be on 'encounter' field
        assert 'encounter' in exc_info.value.message_dict
    
    def test_photo_with_matching_patient_encounter_succeeds(
        self, patient_a, encounter_for_patient_a
    ):
        """Creating photo with matching patient and encounter succeeds."""
        from apps.photos.models import SkinPhoto
        
        photo = SkinPhoto(
            patient=patient_a,  # Same patient
            encounter=encounter_for_patient_a,  # Encounter for Patient A
            body_part='arm',
            tags='baseline'
        )
        
        # Should not raise validation error
        photo.clean()  # Validation should pass
        
        # Note: We don't save because we don't have actual image files in tests
    
    def test_photo_without_encounter_is_valid(self, patient_a):
        """Photo can exist without encounter (standalone clinical photo)."""
        from apps.photos.models import SkinPhoto
        
        photo = SkinPhoto(
            patient=patient_a,
            body_part='back',
            tags='standalone'
            # No encounter field
        )
        
        # Should not raise validation error
        photo.clean()  # Validation should pass


class TestReceptionCannotAccessClinicalEntities:
    """Test that reception users cannot access clinical data (Layer 1 validation)."""
    
    @pytest.fixture
    def reception_user(self, django_user_model):
        from apps.authz.models import Role, UserRole
        
        user = django_user_model.objects.create_user(
            username='reception_test',
            email='reception@clinic.com',
            password='testpass123'
        )
        
        # Assign Reception role
        role, _ = Role.objects.get_or_create(name='reception')
        UserRole.objects.create(user=user, role=role)
        
        return user
    
    @pytest.fixture
    def patient(self):
        from apps.clinical.models import Patient
        return Patient.objects.create(
            first_name='Frank',
            last_name='Foster',
            birth_date='1987-02-14',
            phone='555-0006',
            email='frank@example.com'
        )
    
    @pytest.fixture
    def encounter(self, patient, practitioner_user):
        from apps.clinical.models import Encounter
        from apps.authz.models import Practitioner
        
        practitioner, _ = Practitioner.objects.get_or_create(
            user=practitioner_user,
            defaults={'license_number': 'MED11111', 'specialty': 'Dermatology'}
        )
        
        return Encounter.objects.create(
            patient=patient,
            practitioner=practitioner,
            type='consultation',
            status='scheduled',
            occurred_at=timezone.now(),
            chief_complaint='Private clinical data'
        )
    
    def test_reception_cannot_list_encounters(self, reception_user, encounter):
        """Reception user receives 403 when listing encounters."""
        client = APIClient()
        client.force_authenticate(user=reception_user)
        
        response = client.get('/api/encounters/')
        
        # Should be forbidden
        assert response.status_code == 403
    
    def test_reception_cannot_retrieve_encounter(self, reception_user, encounter):
        """Reception user receives 403 when retrieving specific encounter."""
        client = APIClient()
        client.force_authenticate(user=reception_user)
        
        response = client.get(f'/api/encounters/{encounter.id}/')
        
        # Should be forbidden
        assert response.status_code == 403
    
    def test_reception_cannot_create_encounter(self, reception_user, patient):
        """Reception user receives 403 when creating encounter."""
        client = APIClient()
        client.force_authenticate(user=reception_user)
        
        response = client.post(
            '/api/encounters/',
            {
                'patient': str(patient.id),
                'type': 'consultation',
                'status': 'scheduled',
                'occurred_at': timezone.now().isoformat(),
                'chief_complaint': 'Should not be allowed'
            },
            format='json'
        )
        
        # Should be forbidden
        assert response.status_code == 403


# Fixtures shared across tests
@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def practitioner_user(django_user_model):
    from apps.authz.models import Role, UserRole
    
    user = django_user_model.objects.create_user(
        username='dr_practitioner',
        email='practitioner@clinic.com',
        password='testpass123'
    )
    
    # Assign Practitioner role
    role, _ = Role.objects.get_or_create(name='practitioner')
    UserRole.objects.create(user=user, role=role)
    
    return user
