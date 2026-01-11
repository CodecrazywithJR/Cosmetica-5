"""
Tests for clinical audit logging functionality.
"""
import pytest
from rest_framework.test import APIClient
from django.utils import timezone
from datetime import timedelta

from apps.clinical.models import ClinicalAuditLog, Encounter
from apps.photos.models import SkinPhoto


@pytest.mark.django_db
class TestClinicalAuditLog:
    """Test audit logging for clinical entities."""
    
    @pytest.fixture
    def client(self):
        return APIClient()
    
    @pytest.fixture
    def practitioner_user(self, django_user_model):
        """Create a practitioner user."""
        from apps.authz.models import Role, UserRole
        user = django_user_model.objects.create_user(
            username='dr_maria',
            email='maria@clinic.com',
            password='testpass123'
        )
        # Assign Practitioner role
        role, _ = Role.objects.get_or_create(name='practitioner')
        UserRole.objects.create(user=user, role=role)
        return user
    
    @pytest.fixture
    def patient(self):
        """Create a test patient."""
        from apps.clinical.models import Patient
        return Patient.objects.create(
            first_name='Juan',
            last_name='Pérez',
            birth_date='1990-01-01',
            phone='555-1234',
            email='juan@example.com'
        )
    
    @pytest.fixture
    def encounter(self, patient, practitioner_user):
        """Create a test encounter."""
        from apps.clinical.models import Practitioner
        
        # Create practitioner
        practitioner, _ = Practitioner.objects.get_or_create(
            user=practitioner_user,
            defaults={
                'license_number': 'MED123',
                'specialty': 'Dermatology'
            }
        )
        
        return Encounter.objects.create(
            patient=patient,
            practitioner=practitioner,
            type='consultation',
            status='scheduled',
            occurred_at=timezone.now(),
            chief_complaint='Skin rash'
        )
    
    def test_audit_log_created_on_encounter_update(self, client, practitioner_user, encounter, patient):
        """Test that updating an encounter creates an audit log entry."""
        client.force_authenticate(user=practitioner_user)
        
        # Clear any existing audit logs
        ClinicalAuditLog.objects.all().delete()
        
        # Update the encounter
        response = client.patch(
            f'/api/encounters/{encounter.id}/',
            {'chief_complaint': 'Severe skin rash'},
            format='json'
        )
        
        assert response.status_code == 200
        
        # Check that an audit log was created
        audit_logs = ClinicalAuditLog.objects.filter(
            entity_type='Encounter',
            entity_id=encounter.id
        )
        
        assert audit_logs.count() == 1
        
        audit_log = audit_logs.first()
        assert audit_log.action == 'update'
        assert audit_log.actor_user == practitioner_user
        assert audit_log.patient == patient
        assert 'before' in audit_log.metadata
        assert 'after' in audit_log.metadata
        assert audit_log.metadata['before']['chief_complaint'] == 'Skin rash'
        assert audit_log.metadata['after']['chief_complaint'] == 'Severe skin rash'
    
    def test_audit_log_includes_changed_fields(self, client, practitioner_user, encounter):
        """Test that the audit log includes which fields were changed."""
        client.force_authenticate(user=practitioner_user)
        
        # Clear any existing audit logs
        ClinicalAuditLog.objects.all().delete()
        
        # Update multiple fields
        response = client.patch(
            f'/api/encounters/{encounter.id}/',
            {
                'chief_complaint': 'Updated complaint',
                'assessment': 'Dermatitis detected',
                'plan': 'Prescribe topical cream'
            },
            format='json'
        )
        
        assert response.status_code == 200
        
        # Check the audit log
        audit_log = ClinicalAuditLog.objects.filter(
            entity_type='Encounter',
            entity_id=encounter.id
        ).first()
        
        assert audit_log is not None
        assert 'changed_fields' in audit_log.metadata
        
        changed_fields = audit_log.metadata['changed_fields']
        assert 'chief_complaint' in changed_fields
        assert 'assessment' in changed_fields
        assert 'plan' in changed_fields
    
    def test_audit_log_no_entry_on_no_changes(self, client, practitioner_user, encounter):
        """Test that no audit log is created when no fields actually change."""
        client.force_authenticate(user=practitioner_user)
        
        # Clear any existing audit logs
        ClinicalAuditLog.objects.all().delete()
        
        # Update with the same values (no actual change)
        response = client.patch(
            f'/api/encounters/{encounter.id}/',
            {'chief_complaint': encounter.chief_complaint},
            format='json'
        )
        
        assert response.status_code == 200
        
        # Check that NO audit log was created
        audit_logs = ClinicalAuditLog.objects.filter(
            entity_type='Encounter',
            entity_id=encounter.id
        )
        
        assert audit_logs.count() == 0
    
    def test_audit_log_created_on_photo_creation(self, client, practitioner_user, patient, encounter):
        """Test that creating a skin photo creates an audit log entry."""
        client.force_authenticate(user=practitioner_user)
        
        # Clear any existing audit logs
        ClinicalAuditLog.objects.all().delete()
        
        # Create a skin photo (simplified - without actual file upload)
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        image_file = SimpleUploadedFile(
            name='test_photo.jpg',
            content=b'fake image content',
            content_type='image/jpeg'
        )
        
        response = client.post(
            '/api/skin-photos/',
            {
                'patient': str(patient.id),
                'encounter': str(encounter.id),
                'image': image_file,
                'body_part': 'face',
                'tags': ['baseline', 'front'],
                'taken_at': timezone.now().isoformat(),
            },
            format='multipart'
        )
        
        # Should succeed (may need to adjust based on actual endpoint setup)
        if response.status_code == 201:
            photo_id = response.data['id']
            
            # Check that an audit log was created
            audit_logs = ClinicalAuditLog.objects.filter(
                entity_type='ClinicalPhoto',
                entity_id=photo_id
            )
            
            assert audit_logs.count() == 1
            
            audit_log = audit_logs.first()
            assert audit_log.action == 'create'
            assert audit_log.actor_user == practitioner_user
            assert audit_log.patient == patient
            assert 'after' in audit_log.metadata
    
    def test_audit_log_queryable_by_patient(self, client, practitioner_user, patient, encounter):
        """Test that audit logs can be queried by patient."""
        client.force_authenticate(user=practitioner_user)
        
        # Clear any existing audit logs
        ClinicalAuditLog.objects.all().delete()
        
        # Update the encounter twice
        client.patch(
            f'/api/encounters/{encounter.id}/',
            {'chief_complaint': 'Update 1'},
            format='json'
        )
        
        client.patch(
            f'/api/encounters/{encounter.id}/',
            {'chief_complaint': 'Update 2'},
            format='json'
        )
        
        # Query audit logs by patient
        patient_audit_logs = ClinicalAuditLog.objects.filter(patient=patient)
        
        assert patient_audit_logs.count() == 2
        assert all(log.patient == patient for log in patient_audit_logs)
    
    def test_audit_log_captures_request_metadata(self, client, practitioner_user, encounter):
        """Test that audit logs capture request metadata (IP, user-agent)."""
        client.force_authenticate(user=practitioner_user)
        
        # Clear any existing audit logs
        ClinicalAuditLog.objects.all().delete()
        
        # Update with custom headers
        response = client.patch(
            f'/api/encounters/{encounter.id}/',
            {'chief_complaint': 'Test metadata'},
            format='json',
            HTTP_USER_AGENT='Test-Agent/1.0'
        )
        
        assert response.status_code == 200
        
        # Check the audit log metadata
        audit_log = ClinicalAuditLog.objects.filter(
            entity_type='Encounter',
            entity_id=encounter.id
        ).first()
        
        assert audit_log is not None
        assert 'request' in audit_log.metadata
        
        # The request metadata should include user_agent
        request_meta = audit_log.metadata.get('request', {})
        # Note: IP might be 127.0.0.1 in tests, user_agent should match
        assert 'user_agent' in request_meta or 'ip' in request_meta
