"""
Smoke tests for Encounter domain.

PURPOSE:
These tests validate that the Encounter architecture cleanup was successful.
They are NOT comprehensive functional tests.

SCOPE:
1. Model creation and UUID primary key
2. ClinicalMedia relationship to Encounter
3. Basic API endpoint availability
4. No references to deprecated apps.encounters module

NOT COVERED (future phases):
- Business logic validation (status transitions, etc.)
- Permission edge cases
- Complex API workflows
- Data validation rules
"""
import uuid
from datetime import datetime, timezone as dt_timezone
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from apps.authz.models import Practitioner, Role, UserRole
from apps.clinical.models import (
    ClinicalMedia,
    Encounter,
    EncounterStatusChoices,
    EncounterTypeChoices,
    Patient,
)

User = get_user_model()


def create_test_image():
    """Create a minimal valid image file for testing."""
    file = BytesIO()
    image = Image.new('RGB', (100, 100), color='red')
    image.save(file, 'JPEG')
    file.seek(0)
    return SimpleUploadedFile(
        "test_photo.jpg",
        file.getvalue(),
        content_type="image/jpeg"
    )


@pytest.mark.django_db
class TestEncounterModelArchitecture(TestCase):
    """
    Smoke tests for Encounter model.
    
    Validates:
    - Model can be created with required fields
    - Primary key is UUID
    - Model persists to database correctly
    """
    
    def setUp(self):
        """Create minimal fixtures."""
        self.patient = Patient.objects.create(
            first_name='Test',
            last_name='Patient',
            email='patient@test.com'
        )
    
    def test_encounter_has_uuid_primary_key(self):
        """Encounter.id is a UUID, not an integer."""
        encounter = Encounter.objects.create(
            patient=self.patient,
            type=EncounterTypeChoices.MEDICAL_CONSULT,
            status=EncounterStatusChoices.DRAFT,
            occurred_at=datetime.now(dt_timezone.utc)
        )
        
        # Validate UUID
        self.assertIsInstance(encounter.id, uuid.UUID)
        self.assertIsNotNone(encounter.id)
    
    def test_encounter_minimal_creation(self):
        """Can create Encounter with only required fields."""
        encounter = Encounter.objects.create(
            patient=self.patient,
            type=EncounterTypeChoices.FOLLOW_UP,
            status=EncounterStatusChoices.DRAFT,
            occurred_at=datetime.now(dt_timezone.utc)
        )
        
        # Validate required fields
        self.assertEqual(encounter.patient, self.patient)
        self.assertEqual(encounter.type, EncounterTypeChoices.FOLLOW_UP)
        self.assertEqual(encounter.status, EncounterStatusChoices.DRAFT)
        self.assertIsNotNone(encounter.occurred_at)
        
        # Validate defaults
        self.assertEqual(encounter.row_version, 1)  # Default is 1, not 0
        self.assertFalse(encounter.is_deleted)
        self.assertIsNone(encounter.deleted_at)
    
    def test_encounter_retrieval_from_database(self):
        """Encounter can be saved and retrieved from DB."""
        created_encounter = Encounter.objects.create(
            patient=self.patient,
            type=EncounterTypeChoices.AESTHETIC_PROCEDURE,
            status=EncounterStatusChoices.FINALIZED,
            occurred_at=datetime.now(dt_timezone.utc),
            chief_complaint='Test complaint',
            assessment='Test assessment'
        )
        
        # Retrieve from DB
        retrieved_encounter = Encounter.objects.get(id=created_encounter.id)
        
        self.assertEqual(retrieved_encounter.id, created_encounter.id)
        self.assertEqual(retrieved_encounter.patient, self.patient)
        self.assertEqual(retrieved_encounter.chief_complaint, 'Test complaint')
        self.assertEqual(retrieved_encounter.assessment, 'Test assessment')
    
    def test_encounter_soft_delete_fields_exist(self):
        """Encounter has soft delete fields (architecture requirement)."""
        encounter = Encounter.objects.create(
            patient=self.patient,
            type=EncounterTypeChoices.MEDICAL_CONSULT,
            status=EncounterStatusChoices.DRAFT,
            occurred_at=datetime.now(dt_timezone.utc)
        )
        
        # Validate soft delete fields exist and have correct defaults
        self.assertFalse(encounter.is_deleted)
        self.assertIsNone(encounter.deleted_at)
        self.assertIsNone(encounter.deleted_by_user)
    
    def test_encounter_model_is_in_clinical_app(self):
        """Encounter model is in apps.clinical, not apps.encounters."""
        self.assertEqual(Encounter._meta.app_label, 'clinical')
        self.assertEqual(Encounter._meta.db_table, 'encounter')


@pytest.mark.django_db
class TestClinicalMediaRelationship(TestCase):
    """
    Smoke tests for ClinicalMedia relationship with Encounter.
    
    Validates:
    - ClinicalMedia can be created and linked to Encounter
    - FK points to clinical.Encounter (not deprecated module)
    - No references to apps.encounters exist
    """
    
    def setUp(self):
        """Create minimal fixtures."""
        self.user = User.objects.create_user(
            email='doctor@test.com',
            password='testpass123'
        )
        
        self.patient = Patient.objects.create(
            first_name='Test',
            last_name='Patient',
            email='patient@test.com'
        )
        
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            type=EncounterTypeChoices.MEDICAL_CONSULT,
            status=EncounterStatusChoices.DRAFT,
            occurred_at=datetime.now(dt_timezone.utc)
        )
    
    def test_clinical_media_fk_points_to_clinical_encounter(self):
        """ClinicalMedia.encounter FK points to clinical.Encounter."""
        encounter_field = ClinicalMedia._meta.get_field('encounter')
        related_model = encounter_field.related_model
        
        # Validate FK target
        self.assertEqual(related_model, Encounter)
        self.assertEqual(related_model._meta.app_label, 'clinical')
    
    def test_clinical_media_creation_with_encounter(self):
        """Can create ClinicalMedia associated with an Encounter."""
        media = ClinicalMedia.objects.create(
            encounter=self.encounter,
            uploaded_by=self.user,
            file=create_test_image(),
            media_type='photo',
            category='before'
        )
        
        # Validate relationship
        self.assertEqual(media.encounter, self.encounter)
        self.assertEqual(media.encounter.id, self.encounter.id)
        self.assertIsInstance(media.encounter.id, uuid.UUID)
    
    def test_clinical_media_reverse_relation(self):
        """Encounter.clinical_media reverse relationship works."""
        media1 = ClinicalMedia.objects.create(
            encounter=self.encounter,
            uploaded_by=self.user,
            file=create_test_image(),
            media_type='photo',
            category='before'
        )
        
        media2 = ClinicalMedia.objects.create(
            encounter=self.encounter,
            uploaded_by=self.user,
            file=create_test_image(),
            media_type='photo',
            category='after'
        )
        
        # Validate reverse relation
        related_media = self.encounter.clinical_media.all()
        self.assertEqual(related_media.count(), 2)
        self.assertIn(media1, related_media)
        self.assertIn(media2, related_media)
    
    def test_no_references_to_apps_encounters(self):
        """ClinicalMedia model has no references to deprecated apps.encounters."""
        # Check model meta
        self.assertEqual(ClinicalMedia._meta.app_label, 'clinical')
        
        # Check FK target is clinical.Encounter
        encounter_field = ClinicalMedia._meta.get_field('encounter')
        self.assertEqual(encounter_field.related_model._meta.app_label, 'clinical')
        
        # Verify no import errors from deprecated module
        with self.assertRaises(ModuleNotFoundError):
            # This should fail because apps.encounters is deleted
            from apps.encounters.models import Encounter as DeprecatedEncounter  # noqa: F401


@pytest.mark.django_db
class TestEncounterAPIEndpoint(TestCase):
    """
    Smoke tests for Encounter API endpoints.
    
    Validates:
    - GET /api/v1/clinical/encounters/ returns 200
    - Response format is correct (list)
    - Authentication is required
    
    NOT TESTED (future phases):
    - POST/PATCH/DELETE operations
    - Permission edge cases
    - Business logic validation
    """
    
    def setUp(self):
        """Create authenticated client with practitioner role."""
        self.client = APIClient()
        
        # Create user with practitioner role (required for Encounter access)
        self.user = User.objects.create_user(
            email='doctor@test.com',
            password='testpass123'
        )
        
        # Create practitioner role
        practitioner_role, _ = Role.objects.get_or_create(
            name='practitioner'
        )
        
        UserRole.objects.create(
            user=self.user,
            role=practitioner_role
        )
        
        # Create practitioner profile
        Practitioner.objects.create(
            user=self.user,
            display_name='Dr. Test'
        )
        
        # Authenticate
        self.client.force_authenticate(user=self.user)
        
        # Create test data
        self.patient = Patient.objects.create(
            first_name='Test',
            last_name='Patient',
            email='patient@test.com'
        )
    
    def test_encounter_list_endpoint_exists(self):
        """GET /api/v1/clinical/encounters/ returns 200."""
        response = self.client.get('/api/v1/clinical/encounters/')
        
        # Should return 200, even if empty list
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_encounter_list_returns_json_array(self):
        """Encounter list endpoint returns a paginated response."""
        response = self.client.get('/api/v1/clinical/encounters/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # API returns paginated dict with 'results' key, not plain list
        self.assertIsInstance(response.data, dict)
        self.assertIn('results', response.data)
        self.assertIsInstance(response.data['results'], list)
    
    def test_encounter_list_requires_authentication(self):
        """Encounter list requires authentication."""
        # Unauthenticated client
        anon_client = APIClient()
        response = anon_client.get('/api/v1/clinical/encounters/')
        
        # Should return 401 Unauthorized
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_encounter_list_with_data(self):
        """Encounter list returns encounters when they exist."""
        # Create an encounter
        encounter = Encounter.objects.create(
            patient=self.patient,
            type=EncounterTypeChoices.MEDICAL_CONSULT,
            status=EncounterStatusChoices.DRAFT,
            occurred_at=datetime.now(dt_timezone.utc)
        )
        
        response = self.client.get('/api/v1/clinical/encounters/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # API returns paginated response with 'results' list
        self.assertEqual(len(response.data['results']), 1)
        
        # Validate response structure (basic)
        encounter_data = response.data['results'][0]
        self.assertIn('id', encounter_data)
        self.assertIn('patient', encounter_data)
        self.assertIn('type', encounter_data)
        self.assertIn('status', encounter_data)
    
    def test_deprecated_endpoint_does_not_exist(self):
        """Old /api/encounters/ endpoint is removed."""
        response = self.client.get('/api/encounters/')
        
        # Should return 404 Not Found (route doesn't exist)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@pytest.mark.django_db
class TestEncounterArchitectureInvariants(TestCase):
    """
    Tests that validate architectural decisions are maintained.
    
    These tests document irreversible decisions from Section 16
    of PROJECT_DECISIONS.md.
    """
    
    def test_encounter_uses_uuid_not_bigint(self):
        """Encounter primary key is UUID, not bigint (irreversible decision)."""
        # This is documented as IRREVERSIBLE in PROJECT_DECISIONS.md Section 16.6
        id_field = Encounter._meta.get_field('id')
        
        self.assertEqual(id_field.get_internal_type(), 'UUIDField')
        self.assertTrue(id_field.primary_key)
    
    def test_encounter_has_soft_delete_pattern(self):
        """Encounter uses soft delete pattern (irreversible decision)."""
        # Documented in PROJECT_DECISIONS.md Section 16.6 Decision 2
        encounter_fields = [f.name for f in Encounter._meta.get_fields()]
        
        self.assertIn('is_deleted', encounter_fields)
        self.assertIn('deleted_at', encounter_fields)
        self.assertIn('deleted_by_user', encounter_fields)
    
    def test_encounter_has_optimistic_locking(self):
        """Encounter uses optimistic locking via row_version (irreversible decision)."""
        # Documented in PROJECT_DECISIONS.md Section 16.6 Decision 3
        row_version_field = Encounter._meta.get_field('row_version')
        
        self.assertEqual(row_version_field.get_internal_type(), 'IntegerField')
        self.assertEqual(row_version_field.default, 1)  # Default is 1, not 0
    
    def test_encounter_has_denormalized_counters(self):
        """Encounter has denormalized attachment counters (irreversible decision)."""
        # Documented in PROJECT_DECISIONS.md Section 16.6 Decision 4
        encounter_fields = [f.name for f in Encounter._meta.get_fields()]
        
        self.assertIn('photo_count_cached', encounter_fields)
        self.assertIn('document_count_cached', encounter_fields)
        self.assertIn('has_photos_cached', encounter_fields)
        self.assertIn('has_documents_cached', encounter_fields)
    
    def test_encounter_is_only_in_clinical_app(self):
        """Encounter exists ONLY in apps.clinical (single source of truth)."""
        # Documented in PROJECT_DECISIONS.md Section 16.2
        self.assertEqual(Encounter._meta.app_label, 'clinical')
        
        # Verify deprecated module doesn't exist
        import sys
        self.assertNotIn('apps.encounters', sys.modules)
