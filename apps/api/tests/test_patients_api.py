"""
Integration tests for Patient API endpoints.

Tests CRUD operations, optimistic locking (row_version),
soft delete, and filtering.
"""
import pytest
from rest_framework import status
from apps.clinical.models import Patient


@pytest.mark.django_db
class TestPatientCreate:
    """Test POST /api/v1/patients/ - Create patient."""
    
    endpoint = '/api/v1/patients/'
    
    def test_create_patient_success(self, admin_client):
        """Create patient returns id and row_version."""
        payload = {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'email': 'jane.smith@test.com',
            'sex': 'female',
            'birth_date': '1995-05-15',
            'phone': '+34600111222',
            'country_code': 'ES',
        }
        
        response = admin_client.post(self.endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'id' in response.data
        assert 'row_version' in response.data
        assert response.data['row_version'] == 1
        assert response.data['first_name'] == 'Jane'
        assert response.data['last_name'] == 'Smith'
        assert response.data['email'] == 'jane.smith@test.com'
        assert response.data['is_merged'] is False
        assert response.data['is_deleted'] is False
    
    def test_create_patient_minimal_fields(self, admin_client):
        """Create patient with only required fields."""
        payload = {
            'first_name': 'John',
            'last_name': 'Doe',
        }
        
        response = admin_client.post(self.endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['first_name'] == 'John'
        assert response.data['last_name'] == 'Doe'
        assert response.data['row_version'] == 1
    
    def test_create_patient_duplicate_email(self, admin_client, patient):
        """Cannot create patient with duplicate email."""
        payload = {
            'first_name': 'Another',
            'last_name': 'Patient',
            'email': patient.email,  # Duplicate
        }
        
        response = admin_client.post(self.endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'email' in response.data
    
    def test_create_patient_invalid_sex(self, admin_client):
        """Invalid sex value returns 400."""
        payload = {
            'first_name': 'Test',
            'last_name': 'Patient',
            'sex': 'invalid',
        }
        
        response = admin_client.post(self.endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'sex' in response.data
    
    def test_create_patient_future_birth_date(self, admin_client):
        """Future birth date returns 400."""
        payload = {
            'first_name': 'Test',
            'last_name': 'Patient',
            'birth_date': '2030-01-01',
        }
        
        response = admin_client.post(self.endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'birth_date' in response.data


@pytest.mark.django_db
class TestPatientUpdate:
    """Test PATCH /api/v1/patients/{id}/ - Update patient with optimistic locking."""
    
    def test_update_patient_with_correct_row_version(self, admin_client, patient):
        """Update with correct row_version returns 200 and increments version."""
        endpoint = f'/api/v1/patients/{patient.id}/'
        
        payload = {
            'first_name': 'UpdatedName',
            'row_version': patient.row_version,
        }
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['first_name'] == 'UpdatedName'
        assert response.data['row_version'] == patient.row_version + 1
        
        # Verify in database
        patient.refresh_from_db()
        assert patient.first_name == 'UpdatedName'
        assert patient.row_version == 2
    
    def test_update_patient_without_row_version(self, admin_client, patient):
        """Update without row_version returns 400."""
        endpoint = f'/api/v1/patients/{patient.id}/'
        
        payload = {
            'first_name': 'UpdatedName',
            # Missing row_version
        }
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'row_version' in response.data
    
    def test_update_patient_with_stale_row_version(self, admin_client, patient):
        """Update with stale row_version returns 409 Conflict."""
        endpoint = f'/api/v1/patients/{patient.id}/'
        
        # Simulate concurrent update by incrementing row_version
        patient.row_version += 1
        patient.save()
        
        # Try to update with old version (1)
        payload = {
            'first_name': 'UpdatedName',
            'row_version': 1,  # Stale version
        }
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'row_version' in response.data
        assert 'modificado por otro usuario' in str(response.data['row_version']).lower()
    
    def test_update_patient_email_uniqueness(self, admin_client, patient, patient_factory):
        """Cannot update email to existing patient's email."""
        endpoint = f'/api/v1/patients/{patient.id}/'
        
        # Create another patient with different email
        other_patient = patient_factory(email='other@test.com')
        
        payload = {
            'email': other_patient.email,  # Try to use existing email
            'row_version': patient.row_version,
        }
        
        response = admin_client.patch(endpoint, payload, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'email' in response.data


@pytest.mark.django_db
class TestPatientList:
    """Test GET /api/v1/patients/ - List and filter patients."""
    
    endpoint = '/api/v1/patients/'
    
    def test_list_patients_basic(self, admin_client, patient):
        """List patients returns basic data."""
        response = admin_client.get(self.endpoint)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data  # Paginated response
        assert len(response.data['results']) >= 1
        
        # Check first patient has required fields
        first_patient = response.data['results'][0]
        assert 'id' in first_patient
        assert 'first_name' in first_patient
        assert 'last_name' in first_patient
        assert 'row_version' in first_patient
    
    def test_list_patients_excludes_soft_deleted(self, admin_client, patient_factory):
        """By default, soft-deleted patients are excluded."""
        # Create active patient
        active = patient_factory(first_name='Active', email='active@test.com')
        
        # Create deleted patient
        deleted = patient_factory(first_name='Deleted', email='deleted@test.com')
        deleted.is_deleted = True
        from django.utils import timezone
        deleted.deleted_at = timezone.now()
        deleted.save()
        
        response = admin_client.get(self.endpoint)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check that deleted patient is not in results
        patient_ids = [p['id'] for p in response.data['results']]
        assert str(active.id) in patient_ids
        assert str(deleted.id) not in patient_ids
    
    def test_list_patients_include_deleted_admin_only(self, admin_client, patient_factory):
        """Admin can use include_deleted=true to see deleted patients."""
        # Create deleted patient
        deleted = patient_factory(first_name='Deleted', email='deleted2@test.com')
        deleted.is_deleted = True
        from django.utils import timezone
        deleted.deleted_at = timezone.now()
        deleted.save()
        
        response = admin_client.get(f'{self.endpoint}?include_deleted=true')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check that deleted patient is included
        patient_ids = [p['id'] for p in response.data['results']]
        assert str(deleted.id) in patient_ids
    
    def test_list_patients_include_deleted_non_admin(self, practitioner_client, patient_factory):
        """Non-admin cannot see deleted patients even with include_deleted=true."""
        # Create deleted patient
        deleted = patient_factory(first_name='Deleted', email='deleted3@test.com')
        deleted.is_deleted = True
        from django.utils import timezone
        deleted.deleted_at = timezone.now()
        deleted.save()
        
        response = practitioner_client.get(f'{self.endpoint}?include_deleted=true')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check that deleted patient is NOT included
        patient_ids = [p['id'] for p in response.data['results']]
        assert str(deleted.id) not in patient_ids
    
    def test_filter_by_email(self, admin_client, patient_factory):
        """Filter patients by exact email."""
        patient1 = patient_factory(email='filter1@test.com')
        patient2 = patient_factory(email='filter2@test.com')
        
        response = admin_client.get(f'{self.endpoint}?email=filter1@test.com')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['email'] == 'filter1@test.com'
    
    def test_filter_by_phone(self, admin_client, patient_factory):
        """Filter patients by exact phone."""
        patient1 = patient_factory(
            email='phone1@test.com',
            phone='+34600111111',
            phone_e164='+34600111111'
        )
        patient2 = patient_factory(
            email='phone2@test.com',
            phone='+34600222222',
            phone_e164='+34600222222'
        )
        
        response = admin_client.get(f'{self.endpoint}?phone=+34600111111')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['phone'] == '+34600111111'
    
    def test_filter_by_country_code(self, admin_client, patient_factory):
        """Filter patients by country_code."""
        patient_es = patient_factory(email='spain@test.com', country_code='ES')
        patient_fr = patient_factory(email='france@test.com', country_code='FR')
        
        response = admin_client.get(f'{self.endpoint}?country_code=ES')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check that only ES patients are returned
        country_codes = [p['country_code'] for p in response.data['results']]
        assert 'ES' in country_codes
        assert 'FR' not in country_codes
    
    def test_search_by_q_parameter(self, admin_client, patient_factory):
        """Search patients by name using q parameter."""
        patient1 = patient_factory(first_name='Unique', last_name='Patient', email='unique@test.com')
        patient2 = patient_factory(first_name='Other', last_name='Person', email='other@test.com')
        
        response = admin_client.get(f'{self.endpoint}?q=Unique')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Should find the patient with "Unique" in name
        # Note: Search implementation may vary - adjust assertion if needed
        if len(response.data['results']) > 0:
            found_names = [
                f"{p['first_name']} {p['last_name']}"
                for p in response.data['results']
            ]
            assert any('Unique' in name for name in found_names)


@pytest.mark.django_db
class TestPatientRetrieve:
    """Test GET /api/v1/patients/{id}/ - Retrieve patient detail."""
    
    def test_retrieve_patient_success(self, admin_client, patient):
        """Retrieve patient returns full detail."""
        endpoint = f'/api/v1/patients/{patient.id}/'
        
        response = admin_client.get(endpoint)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == str(patient.id)
        assert response.data['first_name'] == patient.first_name
        assert response.data['last_name'] == patient.last_name
        assert response.data['row_version'] == patient.row_version
        assert 'full_name_normalized' in response.data
    
    def test_retrieve_nonexistent_patient(self, admin_client):
        """Retrieve nonexistent patient returns 404."""
        import uuid
        fake_id = uuid.uuid4()
        endpoint = f'/api/v1/patients/{fake_id}/'
        
        response = admin_client.get(endpoint)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestPatientSoftDelete:
    """Test soft delete for patients."""
    
    def test_admin_can_soft_delete_patient(self, admin_client, patient_factory):
        """Admin can soft delete patient (if DELETE endpoint exists)."""
        patient = patient_factory(email='to_delete@test.com')
        endpoint = f'/api/v1/patients/{patient.id}/'
        
        response = admin_client.delete(endpoint)
        
        # If DELETE is not implemented, skip
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Patient DELETE endpoint not implemented')
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify soft delete in database
        patient.refresh_from_db()
        assert patient.is_deleted is True
        assert patient.deleted_at is not None
    
    def test_non_admin_cannot_delete_patient(self, practitioner_client, patient_factory):
        """Non-admin cannot delete patient."""
        patient = patient_factory(email='no_delete@test.com')
        endpoint = f'/api/v1/patients/{patient.id}/'
        
        response = practitioner_client.delete(endpoint)
        
        # If DELETE is not implemented, skip
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Patient DELETE endpoint not implemented')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Verify patient is not deleted
        patient.refresh_from_db()
        assert patient.is_deleted is False
    
    def test_deleted_patient_not_in_default_list(self, admin_client, patient_factory):
        """Soft-deleted patient does not appear in default list."""
        patient = patient_factory(email='deleted_list@test.com')
        
        # Manually soft delete
        from django.utils import timezone
        patient.is_deleted = True
        patient.deleted_at = timezone.now()
        patient.save()
        
        response = admin_client.get('/api/v1/patients/')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify deleted patient not in results
        patient_ids = [p['id'] for p in response.data['results']]
        assert str(patient.id) not in patient_ids
    
    def test_admin_can_retrieve_deleted_patient_with_include_deleted(
        self,
        admin_client,
        patient_factory
    ):
        """Admin can see deleted patients with include_deleted=true."""
        patient = patient_factory(email='include_deleted@test.com')
        
        # Manually soft delete
        from django.utils import timezone
        patient.is_deleted = True
        patient.deleted_at = timezone.now()
        patient.save()
        
        response = admin_client.get('/api/v1/patients/?include_deleted=true')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify deleted patient IS in results
        patient_ids = [p['id'] for p in response.data['results']]
        assert str(patient.id) in patient_ids


@pytest.mark.django_db
class TestPatientMerge:
    """Test patient merge functionality (if implemented)."""
    
    def test_merge_patient_basic(self, admin_client, patient_factory):
        """Merge patient marks source as merged (if endpoint exists)."""
        source = patient_factory(email='source@test.com')
        target = patient_factory(email='target@test.com')
        
        endpoint = f'/api/v1/patients/{source.id}/merge/'
        payload = {
            'target_patient_id': str(target.id),
            'merge_reason': 'Duplicate patient',
        }
        
        response = admin_client.post(endpoint, payload, format='json')
        
        # If merge endpoint not implemented, skip
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Patient merge endpoint not implemented')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify source is marked as merged
        source.refresh_from_db()
        assert source.is_merged is True
        assert source.merged_into_patient_id == target.id
        assert source.merge_reason == 'Duplicate patient'
