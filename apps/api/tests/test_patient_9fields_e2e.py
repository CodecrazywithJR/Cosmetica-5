"""
END-TO-END tests for the 9 new Patient fields.
Verifies that PATCH/PUT operations PERSIST data to the database.

New fields tested:
1. document_type
2. document_number
3. nationality
4. emergency_contact_name
5. emergency_contact_phone
6. privacy_policy_accepted
7. privacy_policy_accepted_at
8. terms_accepted
9. terms_accepted_at
"""
import pytest
from datetime import datetime, timezone
from rest_framework.test import APIClient
from apps.authz.models import User, Role, UserRole, RoleChoices
from apps.clinical.models import Patient


@pytest.mark.django_db
class TestPatient9FieldsEndToEnd:
    """
    END-TO-END tests for the 9 new Patient fields.
    Focus: PATCH operation MUST persist to database.
    """
    
    def test_create_patient_without_new_fields(self, admin_client):
        """
        TEST 1: Create patient without the 9 new fields -> Should return 201
        """
        payload = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe.9fields@example.com',
            'birth_date': '1990-01-15',
            'sex': 'male',
        }
        
        response = admin_client.post(
            '/api/v1/clinical/patients/',
            payload,
            format='json'
        )
        
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.data}"
        patient_id = response.data['id']
        
        # Verify default values for the 9 fields
        patient = Patient.objects.get(id=patient_id)
        assert patient.document_type is None
        assert patient.document_number is None
        assert patient.nationality is None
        assert patient.emergency_contact_name is None
        assert patient.emergency_contact_phone is None
        assert patient.privacy_policy_accepted is False
        assert patient.privacy_policy_accepted_at is None
        assert patient.terms_accepted is False
        assert patient.terms_accepted_at is None
        
        return patient_id
    
    def test_patch_patient_with_all_9_fields(self, admin_client):
        """
        TEST 2: PATCH patient with ALL 9 new fields -> Should return 200 AND persist
        """
        # First, create a patient
        payload = {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'email': 'jane.smith.9fields@example.com',
            'birth_date': '1985-05-20',
            'sex': 'female',
        }
        response = admin_client.post(
            '/api/v1/clinical/patients/',
            payload,
            format='json'
        )
        assert response.status_code == 201
        patient_id = response.data['id']
        row_version = response.data['row_version']
        
        # Now PATCH with all 9 fields
        now_iso = datetime.now(timezone.utc).isoformat()
        patch_payload = {
            'row_version': row_version,
            'document_type': 'dni',
            'document_number': '12345678A',
            'nationality': 'Spanish',
            'emergency_contact_name': 'Emergency Contact Person',
            'emergency_contact_phone': '+34600123456',
            'privacy_policy_accepted': True,
            'privacy_policy_accepted_at': now_iso,
            'terms_accepted': True,
            'terms_accepted_at': now_iso,
        }
        
        response = admin_client.patch(
            f'/api/v1/clinical/patients/{patient_id}/',
            patch_payload,
            format='json'
        )
        
        # Verify response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.data}"
        assert response.data['document_type'] == 'dni'
        assert response.data['document_number'] == '12345678A'
        assert response.data['nationality'] == 'Spanish'
        assert response.data['emergency_contact_name'] == 'Emergency Contact Person'
        assert response.data['emergency_contact_phone'] == '+34600123456'
        assert response.data['privacy_policy_accepted'] is True
        assert response.data['privacy_policy_accepted_at'] is not None
        assert response.data['terms_accepted'] is True
        assert response.data['terms_accepted_at'] is not None
        
        # CRITICAL: Verify persistence in database via refresh_from_db
        patient = Patient.objects.get(id=patient_id)
        patient.refresh_from_db()
        
        assert patient.document_type == 'dni', "document_type NOT persisted!"
        assert patient.document_number == '12345678A', "document_number NOT persisted!"
        assert patient.nationality == 'Spanish', "nationality NOT persisted!"
        assert patient.emergency_contact_name == 'Emergency Contact Person', "emergency_contact_name NOT persisted!"
        assert patient.emergency_contact_phone == '+34600123456', "emergency_contact_phone NOT persisted!"
        assert patient.privacy_policy_accepted is True, "privacy_policy_accepted NOT persisted!"
        assert patient.privacy_policy_accepted_at is not None, "privacy_policy_accepted_at NOT persisted!"
        assert patient.terms_accepted is True, "terms_accepted NOT persisted!"
        assert patient.terms_accepted_at is not None, "terms_accepted_at NOT persisted!"
        
        print("\n✅ ALL 9 FIELDS PERSISTED TO DATABASE")
        return patient_id
    
    def test_get_after_patch_confirms_persistence(self, admin_client):
        """
        TEST 3: GET after PATCH should return the updated values
        """
        # Create patient
        payload = {
            'first_name': 'Bob',
            'last_name': 'Johnson',
            'email': 'bob.johnson.9fields@example.com',
            'birth_date': '1992-03-10',
            'sex': 'male',
        }
        response = admin_client.post(
            '/api/v1/clinical/patients/',
            payload,
            format='json'
        )
        assert response.status_code == 201
        patient_id = response.data['id']
        row_version = response.data['row_version']
        
        # PATCH with 9 fields
        now_iso = datetime.now(timezone.utc).isoformat()
        patch_payload = {
            'row_version': row_version,
            'document_type': 'passport',
            'document_number': 'AB1234567',
            'nationality': 'British',
            'emergency_contact_name': 'Alice Johnson',
            'emergency_contact_phone': '+44123456789',
            'privacy_policy_accepted': True,
            'privacy_policy_accepted_at': now_iso,
            'terms_accepted': True,
            'terms_accepted_at': now_iso,
        }
        
        patch_response = admin_client.patch(
            f'/api/v1/clinical/patients/{patient_id}/',
            patch_payload,
            format='json'
        )
        assert patch_response.status_code == 200
        
        # GET to verify values
        get_response = admin_client.get(
            f'/api/v1/clinical/patients/{patient_id}/'
        )
        
        assert get_response.status_code == 200
        data = get_response.data
        
        # Verify all 9 fields in GET response
        assert data['document_type'] == 'passport', "document_type not in GET response!"
        assert data['document_number'] == 'AB1234567', "document_number not in GET response!"
        assert data['nationality'] == 'British', "nationality not in GET response!"
        assert data['emergency_contact_name'] == 'Alice Johnson', "emergency_contact_name not in GET response!"
        assert data['emergency_contact_phone'] == '+44123456789', "emergency_contact_phone not in GET response!"
        assert data['privacy_policy_accepted'] is True, "privacy_policy_accepted not in GET response!"
        assert data['privacy_policy_accepted_at'] is not None, "privacy_policy_accepted_at not in GET response!"
        assert data['terms_accepted'] is True, "terms_accepted not in GET response!"
        assert data['terms_accepted_at'] is not None, "terms_accepted_at not in GET response!"
        
        print("\n✅ GET CONFIRMS ALL 9 FIELDS PERSISTED")
    
    def test_patch_partial_fields(self, admin_client):
        """
        TEST 4: PATCH with only SOME of the 9 fields -> Should update only those
        """
        # Create patient
        payload = {
            'first_name': 'Charlie',
            'last_name': 'Brown',
            'email': 'charlie.brown.9fields@example.com',
            'birth_date': '1988-07-25',
            'sex': 'other',
        }
        response = admin_client.post(
            '/api/v1/clinical/patients/',
            payload,
            format='json'
        )
        assert response.status_code == 201
        patient_id = response.data['id']
        row_version = response.data['row_version']
        
        # PATCH with only document fields
        patch_payload = {
            'row_version': row_version,
            'document_type': 'other',
            'document_number': 'X9876543',
            'nationality': 'French',
        }
        
        response = admin_client.patch(
            f'/api/v1/clinical/patients/{patient_id}/',
            patch_payload,
            format='json'
        )
        
        assert response.status_code == 200
        
        # Verify persistence
        patient = Patient.objects.get(id=patient_id)
        assert patient.document_type == 'other'
        assert patient.document_number == 'X9876543'
        assert patient.nationality == 'French'
        # Other fields should remain default
        assert patient.emergency_contact_name is None
        assert patient.emergency_contact_phone is None
        assert patient.privacy_policy_accepted is False
        assert patient.terms_accepted is False
        
        print("\n✅ PARTIAL PATCH WORKS CORRECTLY")
    
    def test_patch_boolean_fields_without_timestamps(self, admin_client):
        """
        TEST 5: PATCH with privacy_policy_accepted=True but no timestamp
        Current behavior: accepts null timestamp (field is optional)
        """
        # Create patient
        payload = {
            'first_name': 'Diana',
            'last_name': 'Prince',
            'email': 'diana.prince.9fields@example.com',
            'birth_date': '1995-12-01',
            'sex': 'female',
        }
        response = admin_client.post(
            '/api/v1/clinical/patients/',
            payload,
            format='json'
        )
        assert response.status_code == 201
        patient_id = response.data['id']
        row_version = response.data['row_version']
        
        # PATCH with boolean True but no timestamp
        patch_payload = {
            'row_version': row_version,
            'privacy_policy_accepted': True,
            'terms_accepted': True,
            # Note: NOT providing timestamps
        }
        
        response = admin_client.patch(
            f'/api/v1/clinical/patients/{patient_id}/',
            patch_payload,
            format='json'
        )
        
        assert response.status_code == 200
        
        # Verify persistence
        patient = Patient.objects.get(id=patient_id)
        assert patient.privacy_policy_accepted is True
        assert patient.terms_accepted is True
        # Timestamps should be None (not auto-set)
        assert patient.privacy_policy_accepted_at is None
        assert patient.terms_accepted_at is None
        
        print("\n✅ BOOLEAN FIELDS WITHOUT TIMESTAMPS ACCEPTED (current behavior)")
    
    def test_put_full_update_with_9_fields(self, admin_client):
        """
        TEST 6: PUT (full update) should also persist the 9 fields
        """
        # Create patient
        payload = {
            'first_name': 'Eve',
            'last_name': 'Adams',
            'email': 'eve.adams.9fields@example.com',
            'birth_date': '1993-08-14',
            'sex': 'female',
        }
        response = admin_client.post(
            '/api/v1/clinical/patients/',
            payload,
            format='json'
        )
        assert response.status_code == 201
        patient_id = response.data['id']
        row_version = response.data['row_version']
        
        # PUT with all required fields + 9 new fields
        now_iso = datetime.now(timezone.utc).isoformat()
        put_payload = {
            'first_name': 'Eve',
            'last_name': 'Adams-Updated',
            'birth_date': '1993-08-14',
            'sex': 'female',
            'email': 'eve.adams.updated.9fields@example.com',
            'row_version': row_version,
            'document_type': 'dni',
            'document_number': 'DNI123456',
            'nationality': 'Spanish',
            'emergency_contact_name': 'Emergency Eve',
            'emergency_contact_phone': '+34611222333',
            'privacy_policy_accepted': True,
            'privacy_policy_accepted_at': now_iso,
            'terms_accepted': True,
            'terms_accepted_at': now_iso,
        }
        
        response = admin_client.put(
            f'/api/v1/clinical/patients/{patient_id}/',
            put_payload,
            format='json'
        )
        
        assert response.status_code == 200
        
        # Verify persistence
        patient = Patient.objects.get(id=patient_id)
        patient.refresh_from_db()
        
        assert patient.last_name == 'Adams-Updated'
        assert patient.document_type == 'dni'
        assert patient.document_number == 'DNI123456'
        assert patient.nationality == 'Spanish'
        assert patient.emergency_contact_name == 'Emergency Eve'
        assert patient.emergency_contact_phone == '+34611222333'
        assert patient.privacy_policy_accepted is True
        assert patient.privacy_policy_accepted_at is not None
        assert patient.terms_accepted is True
        assert patient.terms_accepted_at is not None
        
        print("\n✅ PUT (full update) ALSO PERSISTS ALL 9 FIELDS")


@pytest.mark.django_db
class TestPatient9FieldsRowVersionIncrement:
    """
    Verify that row_version increments correctly with updates
    """
    
    def test_patch_increments_row_version(self, admin_client):
        """PATCH should increment row_version"""
        # Create patient
        payload = {
            'first_name': 'Test',
            'last_name': 'RowVersion',
            'email': 'test.rowversion@example.com',
            'birth_date': '1990-01-01',
            'sex': 'male',
        }
        response = admin_client.post(
            '/api/v1/clinical/patients/',
            payload,
            format='json'
        )
        assert response.status_code == 201
        patient_id = response.data['id']
        initial_version = response.data['row_version']
        assert initial_version == 1
        
        # PATCH with new fields
        patch_payload = {
            'row_version': initial_version,
            'document_type': 'passport',
            'document_number': 'PASS123',
        }
        
        response = admin_client.patch(
            f'/api/v1/clinical/patients/{patient_id}/',
            patch_payload,
            format='json'
        )
        
        assert response.status_code == 200
        new_version = response.data['row_version']
        assert new_version == initial_version + 1
        
        # Verify in database
        patient = Patient.objects.get(id=patient_id)
        assert patient.row_version == new_version
        
        print("\n✅ ROW_VERSION INCREMENTS CORRECTLY")
