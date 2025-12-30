"""
Tests for new Patient fields:
- Official identification (document_type, document_number, nationality)
- Legal consents (privacy_policy_accepted, terms_accepted)
- Emergency contact (emergency_contact_name, emergency_contact_phone)
"""
import pytest
from datetime import datetime
from rest_framework import status
from apps.clinical.models import Patient


@pytest.mark.django_db
class TestPatientNewFields:
    """Test new Patient fields added in migration 0014."""
    
    endpoint = '/api/v1/clinical/patients/'
    
    def test_create_patient_without_new_fields(self, admin_client):
        """Create patient without new fields (backward compatibility)."""
        payload = {
            'first_name': 'Test',
            'last_name': 'Patient',
        }
        
        response = admin_client.post(self.endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['first_name'] == 'Test'
        assert response.data['last_name'] == 'Patient'
        
        # New fields should have default/null values
        assert response.data['document_type'] is None
        assert response.data['document_number'] is None
        assert response.data['nationality'] is None
        assert response.data['emergency_contact_name'] is None
        assert response.data['emergency_contact_phone'] is None
        assert response.data['privacy_policy_accepted'] is False
        assert response.data['privacy_policy_accepted_at'] is None
        assert response.data['terms_accepted'] is False
        assert response.data['terms_accepted_at'] is None
    
    def test_create_patient_with_identification_fields(self, admin_client):
        """Create patient with official identification fields."""
        payload = {
            'first_name': 'Juan',
            'last_name': 'Pérez',
            'document_type': 'dni',
            'document_number': '12345678Z',
            'nationality': 'Spanish',
        }
        
        response = admin_client.post(self.endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['document_type'] == 'dni'
        assert response.data['document_number'] == '12345678Z'
        assert response.data['nationality'] == 'Spanish'
    
    def test_create_patient_with_passport(self, admin_client):
        """Create patient with passport document type."""
        payload = {
            'first_name': 'Marie',
            'last_name': 'Dupont',
            'document_type': 'passport',
            'document_number': 'FR1234567',
            'nationality': 'French',
        }
        
        response = admin_client.post(self.endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['document_type'] == 'passport'
        assert response.data['document_number'] == 'FR1234567'
    
    def test_create_patient_with_emergency_contact(self, admin_client):
        """Create patient with emergency contact information."""
        payload = {
            'first_name': 'Child',
            'last_name': 'Patient',
            'emergency_contact_name': 'Parent Guardian',
            'emergency_contact_phone': '+34600999888',
        }
        
        response = admin_client.post(self.endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['emergency_contact_name'] == 'Parent Guardian'
        assert response.data['emergency_contact_phone'] == '+34600999888'
    
    def test_create_patient_with_legal_consents(self, admin_client):
        """Create patient with legal consent flags."""
        now = datetime.now().isoformat()
        payload = {
            'first_name': 'Consenting',
            'last_name': 'Patient',
            'privacy_policy_accepted': True,
            'privacy_policy_accepted_at': now,
            'terms_accepted': True,
            'terms_accepted_at': now,
        }
        
        response = admin_client.post(self.endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['privacy_policy_accepted'] is True
        assert response.data['privacy_policy_accepted_at'] is not None
        assert response.data['terms_accepted'] is True
        assert response.data['terms_accepted_at'] is not None
    
    def test_create_patient_with_all_new_fields(self, admin_client):
        """Create patient with all new fields populated."""
        now = datetime.now().isoformat()
        payload = {
            'first_name': 'Complete',
            'last_name': 'Patient',
            'document_type': 'dni',
            'document_number': '87654321X',
            'nationality': 'Spanish',
            'emergency_contact_name': 'Emergency Contact',
            'emergency_contact_phone': '+34611222333',
            'privacy_policy_accepted': True,
            'privacy_policy_accepted_at': now,
            'terms_accepted': True,
            'terms_accepted_at': now,
        }
        
        response = admin_client.post(self.endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['document_type'] == 'dni'
        assert response.data['document_number'] == '87654321X'
        assert response.data['nationality'] == 'Spanish'
        assert response.data['emergency_contact_name'] == 'Emergency Contact'
        assert response.data['emergency_contact_phone'] == '+34611222333'
        assert response.data['privacy_policy_accepted'] is True
        assert response.data['terms_accepted'] is True
    
    def test_serializer_includes_new_fields(self, admin_client, patient):
        """GET patient includes all new fields in response."""
        endpoint = f'/api/v1/clinical/patients/{patient.id}/'
        
        response = admin_client.get(endpoint)
        
        assert response.status_code == status.HTTP_200_OK
        # Verify all new fields are in the response
        assert 'document_type' in response.data
        assert 'document_number' in response.data
        assert 'nationality' in response.data
        assert 'emergency_contact_name' in response.data
        assert 'emergency_contact_phone' in response.data
        assert 'privacy_policy_accepted' in response.data
        assert 'privacy_policy_accepted_at' in response.data
        assert 'terms_accepted' in response.data
        assert 'terms_accepted_at' in response.data


@pytest.mark.django_db
class TestPatientModelNewFields:
    """Test Patient model with new fields at database level."""
    
    def test_patient_model_new_fields_nullable(self):
        """New fields are nullable and don't break existing patients."""
        patient = Patient.objects.create(
            first_name='Test',
            last_name='Patient'
        )
        
        assert patient.document_type is None
        assert patient.document_number is None
        assert patient.nationality is None
        assert patient.emergency_contact_name is None
        assert patient.emergency_contact_phone is None
        assert patient.privacy_policy_accepted is False
        assert patient.privacy_policy_accepted_at is None
        assert patient.terms_accepted is False
        assert patient.terms_accepted_at is None
    
    def test_patient_model_with_all_new_fields(self):
        """Can create patient with all new fields populated."""
        now = datetime.now()
        patient = Patient.objects.create(
            first_name='Complete',
            last_name='Patient',
            document_type='dni',
            document_number='12345678Z',
            nationality='Spanish',
            emergency_contact_name='Emergency Person',
            emergency_contact_phone='+34600111222',
            privacy_policy_accepted=True,
            privacy_policy_accepted_at=now,
            terms_accepted=True,
            terms_accepted_at=now,
        )
        
        assert patient.document_type == 'dni'
        assert patient.document_number == '12345678Z'
        assert patient.nationality == 'Spanish'
        assert patient.emergency_contact_name == 'Emergency Person'
        assert patient.emergency_contact_phone == '+34600111222'
        assert patient.privacy_policy_accepted is True
        assert patient.privacy_policy_accepted_at == now
        assert patient.terms_accepted is True
        assert patient.terms_accepted_at == now
    
    def test_patient_model_document_type_choices(self):
        """Document type accepts valid choices."""
        valid_types = ['dni', 'passport', 'other']
        
        for doc_type in valid_types:
            patient = Patient.objects.create(
                first_name='Test',
                last_name=f'Patient-{doc_type}',
                document_type=doc_type,
            )
            assert patient.document_type == doc_type
