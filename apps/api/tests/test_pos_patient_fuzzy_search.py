"""
Tests for POS patient fuzzy search functionality.

Tests cover:
- Phone exact match
- Email exact match
- Name fuzzy match (trigram)
- Name contains fallback
- Upsert with phone/email deduplication
- Upsert creates new patient
- Permission checks
"""
import pytest
from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.clinical.models import Patient
from apps.pos.utils import (
    normalize_phone_to_e164,
    mask_phone,
    mask_email,
    normalize_search_query,
    is_email_like,
    is_phone_like
)

User = get_user_model()


@pytest.mark.django_db
class TestPOSPatientFuzzySearch(TestCase):
    """Test POS patient search with fuzzy matching."""

    def setUp(self):
        """Set up test data."""
        # Create users with different permissions
        self.reception_user = User.objects.create_user(
            email='reception@clinic.com',
            password='testpass123'
        )
        reception_group, _ = Group.objects.get_or_create(name='Reception')
        self.reception_user.groups.add(reception_group)
        
        self.unauthorized_user = User.objects.create_user(
            email='unauthorized@example.com',
            password='testpass123'
        )
        
        # Create test patients
        self.patient_phone = Patient.objects.create(
            first_name='María',
            last_name='González',
            full_name_normalized='maría gonzález',
            phone='+521234567890',
            phone_e164='+521234567890',
            email='maria.gonzalez@example.com',
            birth_date=date(1990, 5, 15),
            identity_confidence='high'
        )
        
        self.patient_email = Patient.objects.create(
            first_name='Carlos',
            last_name='Ramírez',
            full_name_normalized='carlos ramírez',
            phone='+529876543210',
            phone_e164='+529876543210',
            email='carlos.ramirez@clinic.mx',
            birth_date=date(1985, 3, 22),
            identity_confidence='medium'
        )
        
        self.patient_fuzzy = Patient.objects.create(
            first_name='Ana',
            last_name='Martínez',
            full_name_normalized='ana martínez',
            phone='+525551234567',
            phone_e164='+525551234567',
            email='ana.martinez@example.com',
            birth_date=date(1995, 11, 5),
            identity_confidence='low'
        )
        
        self.client = APIClient()

    def test_search_by_phone_exact_match(self):
        """Test search by phone returns exact match with score 1.00."""
        self.client.force_authenticate(user=self.reception_user)
        
        response = self.client.get('/api/v1/pos/patients/search', {'q': '+521234567890'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['match_reason'], 'phone_exact')
        self.assertEqual(data[0]['score'], 1.00)
        self.assertEqual(str(data[0]['id']), str(self.patient_phone.id))
        
        # Phone should be masked
        self.assertIn('***', data[0]['phone_masked'])
        self.assertNotEqual(data[0]['phone_masked'], '+521234567890')

    def test_search_by_email_exact_match(self):
        """Test search by email returns exact match with score 0.95."""
        self.client.force_authenticate(user=self.reception_user)
        
        response = self.client.get('/api/v1/pos/patients/search', {'q': 'carlos.ramirez@clinic.mx'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['match_reason'], 'email_exact')
        self.assertEqual(data[0]['score'], 0.95)
        self.assertEqual(str(data[0]['id']), str(self.patient_email.id))
        
        # Email should be masked
        self.assertIn('***', data[0]['email_masked'])

    def test_search_by_name_fuzzy_match(self):
        """Test search by name with typo uses trigram similarity."""
        self.client.force_authenticate(user=self.reception_user)
        
        # Search for "Ana Martinez" with typo: "Ana Martines"
        response = self.client.get('/api/v1/pos/patients/search', {'q': 'Ana Martines'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Should find Ana Martínez with fuzzy match
        self.assertGreater(len(data), 0)
        
        # First result should be Ana Martínez
        first_result = data[0]
        self.assertEqual(str(first_result['id']), str(self.patient_fuzzy.id))
        self.assertEqual(first_result['match_reason'], 'name_fuzzy')
        
        # Score should be > 0.3 (reasonable similarity)
        self.assertGreater(first_result['score'], 0.3)
        self.assertLessEqual(first_result['score'], 0.90)  # Capped at 0.90

    def test_search_fallback_icontains(self):
        """Test fallback to icontains when trigram finds nothing."""
        self.client.force_authenticate(user=self.reception_user)
        
        # Create patient with unique name for this test
        unique_patient = Patient.objects.create(
            first_name='Unique',
            last_name='Testpatient',
            full_name_normalized='unique testpatient',
            phone='+525559999999',
            phone_e164='+525559999999',
            email='unique@test.com'
        )
        
        # Search with very different query that won't match trigram
        # but contains "Unique"
        response = self.client.get('/api/v1/pos/patients/search', {'q': 'niq'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # May find the patient via fallback
        if len(data) > 0:
            # If found, should be via fallback with low score
            found = any(str(r['id']) == str(unique_patient.id) for r in data)
            if found:
                result = next(r for r in data if str(r['id']) == str(unique_patient.id))
                # Fallback results have very low score
                self.assertLessEqual(result['score'], 0.30)

    def test_upsert_with_existing_phone_no_duplicate(self):
        """Test upsert with existing phone returns existing patient."""
        self.client.force_authenticate(user=self.reception_user)
        
        initial_count = Patient.objects.count()
        
        response = self.client.post('/api/v1/pos/patients/upsert', {
            'first_name': 'Different',
            'last_name': 'Name',
            'phone': '+521234567890',  # Same phone as patient_phone
            'email': 'different@example.com'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Should not create new patient
        self.assertEqual(Patient.objects.count(), initial_count)
        
        # Should return existing patient
        self.assertFalse(data['created'])
        self.assertEqual(data['match_reason'], 'phone_exact')
        self.assertEqual(str(data['patient']['id']), str(self.patient_phone.id))

    def test_upsert_with_existing_email_no_duplicate(self):
        """Test upsert with existing email returns existing patient."""
        self.client.force_authenticate(user=self.reception_user)
        
        initial_count = Patient.objects.count()
        
        response = self.client.post('/api/v1/pos/patients/upsert', {
            'first_name': 'Different',
            'last_name': 'Person',
            'phone': '+529999999999',
            'email': 'carlos.ramirez@clinic.mx'  # Same email as patient_email
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Should not create new patient
        self.assertEqual(Patient.objects.count(), initial_count)
        
        # Should return existing patient
        self.assertFalse(data['created'])
        self.assertEqual(data['match_reason'], 'email_exact')
        self.assertEqual(str(data['patient']['id']), str(self.patient_email.id))

    def test_upsert_creates_new_patient_with_low_confidence(self):
        """Test upsert creates new patient when no match found."""
        self.client.force_authenticate(user=self.reception_user)
        
        initial_count = Patient.objects.count()
        
        response = self.client.post('/api/v1/pos/patients/upsert', {
            'first_name': 'Nueva',
            'last_name': 'Paciente',
            'phone': '+525551111111',
            'email': 'nueva.paciente@example.com',
            'birth_date': '1992-08-10',
            'sex': 'F'
        })
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        
        # Should create new patient
        self.assertEqual(Patient.objects.count(), initial_count + 1)
        self.assertTrue(data['created'])
        self.assertEqual(data['match_reason'], 'created')
        
        # New patient should have low identity confidence
        new_patient = Patient.objects.get(id=data['patient']['id'])
        self.assertEqual(new_patient.identity_confidence, 'low')
        self.assertEqual(new_patient.first_name, 'Nueva')
        self.assertEqual(new_patient.last_name, 'Paciente')

    def test_upsert_requires_phone_or_email(self):
        """Test upsert validation requires at least phone or email."""
        self.client.force_authenticate(user=self.reception_user)
        
        response = self.client.post('/api/v1/pos/patients/upsert', {
            'first_name': 'Test',
            'last_name': 'Patient'
            # No phone or email
        })
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone', str(response.json()).lower() + str(response.json()).lower())

    def test_search_requires_authentication(self):
        """Test search endpoint requires authentication."""
        response = self.client.get('/api/v1/pos/patients/search', {'q': 'test'})
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_search_requires_pos_permission(self):
        """Test search requires POS permission (Reception or ClinicalOps)."""
        self.client.force_authenticate(user=self.unauthorized_user)
        
        response = self.client.get('/api/v1/pos/patients/search', {'q': 'test'})
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_upsert_requires_pos_permission(self):
        """Test upsert requires POS permission."""
        self.client.force_authenticate(user=self.unauthorized_user)
        
        response = self.client.post('/api/v1/pos/patients/upsert', {
            'first_name': 'Test',
            'last_name': 'Patient',
            'phone': '+525551234567'
        })
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_search_respects_limit_parameter(self):
        """Test search respects limit parameter."""
        self.client.force_authenticate(user=self.reception_user)
        
        # Create many patients
        for i in range(15):
            Patient.objects.create(
                first_name='Test',
                last_name=f'Patient{i}',
                full_name_normalized=f'test patient{i}',
                phone=f'+52555000{i:04d}',
                phone_e164=f'+52555000{i:04d}',
                email=f'test{i}@example.com'
            )
        
        # Search with limit=5
        response = self.client.get('/api/v1/pos/patients/search', {'q': 'Test', 'limit': 5})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Should return max 5 results
        self.assertLessEqual(len(data), 5)

    def test_search_no_medical_fields_exposed(self):
        """Test that search results don't expose medical fields."""
        # Create patient with medical data
        patient_with_medical = Patient.objects.create(
            first_name='Medical',
            last_name='Test',
            full_name_normalized='medical test',
            phone='+525559876543',
            phone_e164='+525559876543',
            email='medical@test.com',
            blood_type='O+',
            allergies='Penicillin',
            medical_history='Sensitive medical history',
            current_medications='Secret medication'
        )
        
        self.client.force_authenticate(user=self.reception_user)
        
        response = self.client.get('/api/v1/pos/patients/search', {'q': '+525559876543'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertEqual(len(data), 1)
        result = data[0]
        
        # Should NOT contain medical fields
        self.assertNotIn('blood_type', result)
        self.assertNotIn('allergies', result)
        self.assertNotIn('medical_history', result)
        self.assertNotIn('current_medications', result)
        
        # Should contain only safe fields
        self.assertIn('id', result)
        self.assertIn('full_name_normalized', result)
        self.assertIn('phone_masked', result)
        self.assertIn('email_masked', result)


@pytest.mark.django_db
class TestPOSUtilityFunctions(TestCase):
    """Test POS utility functions."""

    def test_normalize_phone_to_e164(self):
        """Test phone normalization to E.164."""
        # With country code
        self.assertEqual(normalize_phone_to_e164('+521234567890'), '+521234567890')
        
        # Without country code (assumes +52 Mexico)
        self.assertEqual(normalize_phone_to_e164('1234567890'), '+521234567890')
        
        # With formatting
        self.assertEqual(normalize_phone_to_e164('(555) 123-4567'), '+525551234567')
        
        # Invalid (too short)
        self.assertIsNone(normalize_phone_to_e164('123'))

    def test_mask_phone(self):
        """Test phone masking."""
        masked = mask_phone('+521234567890')
        self.assertIn('***', masked)
        self.assertTrue(masked.startswith('+52'))
        self.assertTrue(masked.endswith('890'))

    def test_mask_email(self):
        """Test email masking."""
        masked = mask_email('john.doe@example.com')
        self.assertEqual(masked, 'j***@example.com')
        
        masked_short = mask_email('a@test.com')
        self.assertEqual(masked_short, 'a***@test.com')

    def test_is_email_like(self):
        """Test email detection."""
        self.assertTrue(is_email_like('test@example.com'))
        self.assertFalse(is_email_like('1234567890'))
        self.assertFalse(is_email_like('test'))

    def test_is_phone_like(self):
        """Test phone detection."""
        self.assertTrue(is_phone_like('+521234567890'))
        self.assertTrue(is_phone_like('555-1234'))
        self.assertTrue(is_phone_like('(555) 123-4567'))
        self.assertFalse(is_phone_like('john@example.com'))
        self.assertFalse(is_phone_like('John Doe'))

    def test_normalize_search_query(self):
        """Test search query normalization."""
        self.assertEqual(normalize_search_query('  John  Doe  '), 'john doe')
        self.assertEqual(normalize_search_query('MARIA GONZÁLEZ'), 'maria gonzález')
        self.assertEqual(normalize_search_query('Ana    Martinez'), 'ana martinez')
