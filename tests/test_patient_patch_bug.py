"""
Test to reproduce the PATCH bug with new Patient fields.
This test MUST FAIL before the fix and PASS after the fix.
"""
import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.clinical.models import Patient
from apps.authz.models import Role, RoleChoices
from datetime import date

User = get_user_model()

@pytest.mark.django_db
class TestPatientPatchBug:
    """Reproduce bug: PATCH does not persist new fields"""
    
    @pytest.fixture
    def admin_user(self):
        """Create admin user"""
        user = User.objects.create_user(
            email='admin@test.com',
            password='test123',
            first_name='Admin',
            last_name='User'
        )
        admin_role, _ = Role.objects.get_or_create(name=RoleChoices.ADMIN)
        user.user_roles.create(role=admin_role)
        return user
    
    @pytest.fixture
    def patient(self):
        """Create a patient"""
        return Patient.objects.create(
            first_name='Test',
            last_name='Patient',
            birth_date=date(1990, 1, 1),
            sex='M'
        )
    
    @pytest.fixture
    def api_client(self, admin_user):
        """API client authenticated as admin"""
        client = APIClient()
        client.force_authenticate(user=admin_user)
        return client
    
    def test_patch_identity_fields_are_persisted(self, api_client, patient):
        """
        BUG REPRODUCTION: PATCH with identity fields returns 200 but does NOT save.
        This test MUST FAIL before fix.
        """
        # Step 1: GET initial state
        response = api_client.get(f'/api/v1/clinical/patients/{patient.id}/')
        assert response.status_code == 200
        initial_data = response.json()
        
        # Verify fields are empty initially
        assert initial_data['document_type'] is None
        assert initial_data['document_number'] is None
        assert initial_data['nationality'] is None
        
        # Step 2: PATCH with new identity fields
        patch_data = {
            'document_type': 'dni',
            'document_number': 'TEST123456',
            'nationality': 'Spanish',
            'row_version': initial_data['row_version']
        }
        
        response = api_client.patch(
            f'/api/v1/clinical/patients/{patient.id}/',
            data=patch_data,
            format='json'
        )
        
        assert response.status_code == 200
        patch_response = response.json()
        
        # BUG: These assertions WILL FAIL because values are not saved
        assert patch_response['document_type'] == 'dni', "PATCH response does not include updated document_type"
        assert patch_response['document_number'] == 'TEST123456', "PATCH response does not include updated document_number"
        assert patch_response['nationality'] == 'Spanish', "PATCH response does not include updated nationality"
        
        # Step 3: GET again to verify persistence
        response = api_client.get(f'/api/v1/clinical/patients/{patient.id}/')
        assert response.status_code == 200
        final_data = response.json()
        
        # BUG: These assertions WILL FAIL because values were not persisted to DB
        assert final_data['document_type'] == 'dni', "GET after PATCH shows document_type was not saved"
        assert final_data['document_number'] == 'TEST123456', "GET after PATCH shows document_number was not saved"
        assert final_data['nationality'] == 'Spanish', "GET after PATCH shows nationality was not saved"
    
    def test_patch_emergency_contact_fields_are_persisted(self, api_client, patient):
        """
        BUG REPRODUCTION: PATCH with emergency contact returns 200 but does NOT save.
        """
        response = api_client.get(f'/api/v1/clinical/patients/{patient.id}/')
        initial_data = response.json()
        
        patch_data = {
            'emergency_contact_name': 'Emergency Contact',
            'emergency_contact_phone': '+34666777888',
            'row_version': initial_data['row_version']
        }
        
        response = api_client.patch(
            f'/api/v1/clinical/patients/{patient.id}/',
            data=patch_data,
            format='json'
        )
        
        assert response.status_code == 200
        
        # Verify persistence
        response = api_client.get(f'/api/v1/clinical/patients/{patient.id}/')
        final_data = response.json()
        
        assert final_data['emergency_contact_name'] == 'Emergency Contact'
        assert final_data['emergency_contact_phone'] == '+34666777888'
    
    def test_patch_legal_consent_fields_are_persisted(self, api_client, patient):
        """
        BUG REPRODUCTION: PATCH with legal consents returns 200 but does NOT save.
        """
        response = api_client.get(f'/api/v1/clinical/patients/{patient.id}/')
        initial_data = response.json()
        
        from django.utils import timezone
        now = timezone.now().isoformat()
        
        patch_data = {
            'privacy_policy_accepted': True,
            'privacy_policy_accepted_at': now,
            'terms_accepted': True,
            'terms_accepted_at': now,
            'row_version': initial_data['row_version']
        }
        
        response = api_client.patch(
            f'/api/v1/clinical/patients/{patient.id}/',
            data=patch_data,
            format='json'
        )
        
        assert response.status_code == 200
        
        # Verify persistence
        response = api_client.get(f'/api/v1/clinical/patients/{patient.id}/')
        final_data = response.json()
        
        assert final_data['privacy_policy_accepted'] is True
        assert final_data['privacy_policy_accepted_at'] is not None
        assert final_data['terms_accepted'] is True
        assert final_data['terms_accepted_at'] is not None
    
    def test_patch_all_new_fields_together(self, api_client, patient):
        """
        BUG REPRODUCTION: PATCH with ALL 9 new fields returns 200 but does NOT save.
        """
        response = api_client.get(f'/api/v1/clinical/patients/{patient.id}/')
        initial_data = response.json()
        
        from django.utils import timezone
        now = timezone.now().isoformat()
        
        patch_data = {
            'document_type': 'passport',
            'document_number': 'PASS999',
            'nationality': 'French',
            'emergency_contact_name': 'Jean Dupont',
            'emergency_contact_phone': '+33123456789',
            'privacy_policy_accepted': True,
            'privacy_policy_accepted_at': now,
            'terms_accepted': True,
            'terms_accepted_at': now,
            'row_version': initial_data['row_version']
        }
        
        response = api_client.patch(
            f'/api/v1/clinical/patients/{patient.id}/',
            data=patch_data,
            format='json'
        )
        
        assert response.status_code == 200
        
        # Verify ALL fields persisted
        response = api_client.get(f'/api/v1/clinical/patients/{patient.id}/')
        final_data = response.json()
        
        assert final_data['document_type'] == 'passport'
        assert final_data['document_number'] == 'PASS999'
        assert final_data['nationality'] == 'French'
        assert final_data['emergency_contact_name'] == 'Jean Dupont'
        assert final_data['emergency_contact_phone'] == '+33123456789'
        assert final_data['privacy_policy_accepted'] is True
        assert final_data['privacy_policy_accepted_at'] is not None
        assert final_data['terms_accepted'] is True
        assert final_data['terms_accepted_at'] is not None
