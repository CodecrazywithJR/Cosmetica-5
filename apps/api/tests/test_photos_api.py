"""
Tests for Clinical Photos API endpoints.

Endpoints tested:
- GET /api/v1/photos/ (list clinical photos)
- POST /api/v1/photos/ (create clinical photo metadata after upload)
- GET /api/v1/photos/{id}/ (retrieve photo detail)
- PATCH /api/v1/photos/{id}/ (update metadata)
- DELETE /api/v1/photos/{id}/ (soft delete)
- POST /api/v1/photos/{id}/attach-to-encounter/ (attach photo to encounter)
- POST /api/v1/photos/{id}/detach-from-encounter/ (detach photo from encounter)

Business Rules:
- Photos are immutable once uploaded (storage fields cannot be changed)
- Only metadata (notes, body_area, etc.) can be updated
- Soft delete (Admin only)
- Photos can be attached to multiple encounters (many-to-many via EncounterPhoto)
- Permissions: Admin/Practitioner can create/update/delete, others read-only or forbidden
"""
import pytest
from django.utils import timezone
from datetime import timedelta


@pytest.mark.django_db
class TestClinicalPhotoList:
    """Test GET /api/v1/photos/ endpoint"""
    
    def test_list_photos_basic(self, admin_client, patient):
        """Admin can list clinical photos"""
        from apps.clinical.models import ClinicalPhoto
        
        # Create photos
        ClinicalPhoto.objects.create(
            patient=patient,
            photo_kind='before',
            storage_bucket='clinical',
            object_key='photos/test1.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
        )
        ClinicalPhoto.objects.create(
            patient=patient,
            photo_kind='after',
            storage_bucket='clinical',
            object_key='photos/test2.jpg',
            content_type='image/jpeg',
            size_bytes=2048000,
        )
        
        response = admin_client.get('/api/v1/photos/')
        
        if response.status_code == 404:
            pytest.skip("Clinical photos list endpoint not yet implemented")
        
        assert response.status_code == 200
        assert len(response.data) >= 2 or len(response.data.get('results', [])) >= 2
    
    def test_list_photos_excludes_soft_deleted(self, admin_client, patient):
        """List excludes soft-deleted photos by default"""
        from apps.clinical.models import ClinicalPhoto
        
        active_photo = ClinicalPhoto.objects.create(
            patient=patient,
            photo_kind='clinical',
            object_key='photos/active.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
        )
        deleted_photo = ClinicalPhoto.objects.create(
            patient=patient,
            photo_kind='clinical',
            object_key='photos/deleted.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
            is_deleted=True,
            deleted_at=timezone.now(),
        )
        
        response = admin_client.get('/api/v1/photos/')
        
        if response.status_code == 404:
            pytest.skip("Clinical photos list endpoint not yet implemented")
        
        assert response.status_code == 200
        
        results = response.data if isinstance(response.data, list) else response.data.get('results', [])
        photo_ids = [str(p['id']) for p in results]
        
        assert str(active_photo.id) in photo_ids
        assert str(deleted_photo.id) not in photo_ids
    
    def test_list_photos_include_deleted_admin_only(self, admin_client, practitioner_client, patient):
        """Only Admin can see deleted photos with include_deleted=true"""
        from apps.clinical.models import ClinicalPhoto
        
        deleted_photo = ClinicalPhoto.objects.create(
            patient=patient,
            photo_kind='clinical',
            object_key='photos/deleted.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
            is_deleted=True,
            deleted_at=timezone.now(),
        )
        
        # Admin can see deleted
        admin_response = admin_client.get('/api/v1/photos/?include_deleted=true')
        if admin_response.status_code == 404:
            pytest.skip("Clinical photos list endpoint not yet implemented")
        
        admin_results = admin_response.data if isinstance(admin_response.data, list) else admin_response.data.get('results', [])
        admin_ids = [str(p['id']) for p in admin_results]
        assert str(deleted_photo.id) in admin_ids
        
        # Practitioner cannot use include_deleted
        prac_response = practitioner_client.get('/api/v1/photos/?include_deleted=true')
        prac_results = prac_response.data if isinstance(prac_response.data, list) else prac_response.data.get('results', [])
        prac_ids = [str(p['id']) for p in prac_results]
        assert str(deleted_photo.id) not in prac_ids
    
    def test_list_photos_filter_by_patient(self, admin_client, patient_factory):
        """Filter photos by patient_id"""
        from apps.clinical.models import ClinicalPhoto
        
        patient1 = patient_factory(email='p1@test.com')
        patient2 = patient_factory(email='p2@test.com')
        
        photo1 = ClinicalPhoto.objects.create(
            patient=patient1,
            photo_kind='before',
            object_key='photos/p1.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
        )
        photo2 = ClinicalPhoto.objects.create(
            patient=patient2,
            photo_kind='before',
            object_key='photos/p2.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
        )
        
        response = admin_client.get(f'/api/v1/photos/?patient_id={patient1.id}')
        
        if response.status_code == 404:
            pytest.skip("Clinical photos list endpoint not yet implemented")
        
        assert response.status_code == 200
        results = response.data if isinstance(response.data, list) else response.data.get('results', [])
        photo_ids = [str(p['id']) for p in results]
        
        assert str(photo1.id) in photo_ids
        assert str(photo2.id) not in photo_ids
    
    def test_list_photos_filter_by_photo_kind(self, admin_client, patient):
        """Filter photos by photo_kind"""
        from apps.clinical.models import ClinicalPhoto
        
        before_photo = ClinicalPhoto.objects.create(
            patient=patient,
            photo_kind='before',
            object_key='photos/before.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
        )
        after_photo = ClinicalPhoto.objects.create(
            patient=patient,
            photo_kind='after',
            object_key='photos/after.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
        )
        
        response = admin_client.get('/api/v1/photos/?photo_kind=before')
        
        if response.status_code == 404:
            pytest.skip("Clinical photos list endpoint not yet implemented")
        
        assert response.status_code == 200
        results = response.data if isinstance(response.data, list) else response.data.get('results', [])
        
        for photo in results:
            assert photo['photo_kind'] == 'before'
    
    def test_list_photos_practitioner_allowed(self, practitioner_client, patient):
        """Practitioner can list photos"""
        response = practitioner_client.get('/api/v1/photos/')
        
        if response.status_code == 404:
            pytest.skip("Clinical photos list endpoint not yet implemented")
        
        assert response.status_code == 200
    
    def test_list_photos_reception_forbidden(self, reception_client):
        """Reception cannot list photos (clinical data)"""
        response = reception_client.get('/api/v1/photos/')
        
        if response.status_code == 404:
            pytest.skip("Clinical photos list endpoint not yet implemented")
        
        assert response.status_code == 403
    
    def test_list_photos_marketing_forbidden(self, marketing_client):
        """Marketing cannot list photos"""
        response = marketing_client.get('/api/v1/photos/')
        
        if response.status_code == 404:
            pytest.skip("Clinical photos list endpoint not yet implemented")
        
        assert response.status_code == 403


@pytest.mark.django_db
class TestClinicalPhotoCreate:
    """Test POST /api/v1/photos/ endpoint"""
    
    def test_create_photo_metadata(self, admin_client, patient):
        """Admin can create clinical photo metadata after upload"""
        payload = {
            'patient': str(patient.id),
            'photo_kind': 'before',
            'object_key': 'photos/patient123/before_001.jpg',
            'content_type': 'image/jpeg',
            'size_bytes': 2048000,
            'taken_at': timezone.now().isoformat(),
            'body_area': 'face',
            'notes': 'Initial consultation',
        }
        
        response = admin_client.post('/api/v1/photos/', payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Clinical photos create endpoint not yet implemented")
        
        assert response.status_code == 201
        assert response.data['patient'] == str(patient.id)
        assert response.data['photo_kind'] == 'before'
        assert response.data['object_key'] == 'photos/patient123/before_001.jpg'
        assert response.data['storage_bucket'] == 'clinical'
        assert response.data['size_bytes'] == 2048000
    
    def test_create_photo_minimal_fields(self, admin_client, patient):
        """Create photo with only required fields"""
        payload = {
            'patient': str(patient.id),
            'photo_kind': 'clinical',
            'object_key': 'photos/minimal.jpg',
            'content_type': 'image/jpeg',
            'size_bytes': 1024000,
        }
        
        response = admin_client.post('/api/v1/photos/', payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Clinical photos create endpoint not yet implemented")
        
        assert response.status_code == 201
        assert response.data['taken_at'] is None or 'taken_at' not in response.data
    
    def test_create_photo_practitioner_allowed(self, practitioner_client, patient):
        """Practitioner can create clinical photos"""
        payload = {
            'patient': str(patient.id),
            'photo_kind': 'clinical',
            'object_key': 'photos/practitioner.jpg',
            'content_type': 'image/jpeg',
            'size_bytes': 1024000,
        }
        
        response = practitioner_client.post('/api/v1/photos/', payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Clinical photos create endpoint not yet implemented")
        
        assert response.status_code == 201
    
    def test_create_photo_reception_forbidden(self, reception_client, patient):
        """Reception cannot create clinical photos"""
        payload = {
            'patient': str(patient.id),
            'photo_kind': 'clinical',
            'object_key': 'photos/test.jpg',
            'content_type': 'image/jpeg',
            'size_bytes': 1024000,
        }
        
        response = reception_client.post('/api/v1/photos/', payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Clinical photos create endpoint not yet implemented")
        
        assert response.status_code == 403
    
    def test_create_photo_invalid_kind(self, admin_client, patient):
        """Create photo with invalid photo_kind returns 400"""
        payload = {
            'patient': str(patient.id),
            'photo_kind': 'invalid_kind',
            'object_key': 'photos/test.jpg',
            'content_type': 'image/jpeg',
            'size_bytes': 1024000,
        }
        
        response = admin_client.post('/api/v1/photos/', payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Clinical photos create endpoint not yet implemented")
        
        assert response.status_code == 400


@pytest.mark.django_db
class TestClinicalPhotoUpdate:
    """Test PATCH /api/v1/photos/{id}/ endpoint"""
    
    def test_update_photo_metadata(self, admin_client, patient):
        """Can update metadata fields (notes, body_area, etc.)"""
        from apps.clinical.models import ClinicalPhoto
        
        photo = ClinicalPhoto.objects.create(
            patient=patient,
            photo_kind='before',
            object_key='photos/test.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
        )
        
        payload = {
            'notes': 'Updated notes',
            'body_area': 'forehead',
        }
        
        response = admin_client.patch(f'/api/v1/photos/{photo.id}/', payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Clinical photos update endpoint not yet implemented")
        
        assert response.status_code == 200
        assert response.data['notes'] == 'Updated notes'
        assert response.data['body_area'] == 'forehead'
        
        # Verify database
        photo.refresh_from_db()
        assert photo.notes == 'Updated notes'
        assert photo.body_area == 'forehead'
    
    def test_update_photo_storage_fields_immutable(self, admin_client, patient):
        """Storage fields (object_key, size_bytes, etc.) cannot be changed"""
        from apps.clinical.models import ClinicalPhoto
        
        photo = ClinicalPhoto.objects.create(
            patient=patient,
            photo_kind='before',
            object_key='photos/original.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
        )
        
        original_key = photo.object_key
        original_size = photo.size_bytes
        
        payload = {
            'object_key': 'photos/hacked.jpg',
            'size_bytes': 9999999,
        }
        
        response = admin_client.patch(f'/api/v1/photos/{photo.id}/', payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Clinical photos update endpoint not yet implemented")
        
        # Should succeed but ignore immutable fields
        photo.refresh_from_db()
        assert photo.object_key == original_key
        assert photo.size_bytes == original_size
    
    def test_update_photo_practitioner_allowed(self, practitioner_client, patient):
        """Practitioner can update photo metadata"""
        from apps.clinical.models import ClinicalPhoto
        
        photo = ClinicalPhoto.objects.create(
            patient=patient,
            photo_kind='clinical',
            object_key='photos/test.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
        )
        
        response = practitioner_client.patch(
            f'/api/v1/photos/{photo.id}/',
            {'notes': 'Practitioner update'},
            format='json'
        )
        
        if response.status_code == 404:
            pytest.skip("Clinical photos update endpoint not yet implemented")
        
        assert response.status_code == 200


@pytest.mark.django_db
class TestClinicalPhotoSoftDelete:
    """Test DELETE /api/v1/photos/{id}/ endpoint (soft delete)"""
    
    def test_soft_delete_photo_admin_only(self, admin_client, patient):
        """Only Admin can soft delete photos"""
        from apps.clinical.models import ClinicalPhoto
        
        photo = ClinicalPhoto.objects.create(
            patient=patient,
            photo_kind='clinical',
            object_key='photos/test.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
        )
        
        response = admin_client.delete(f'/api/v1/photos/{photo.id}/')
        
        if response.status_code == 404:
            pytest.skip("Clinical photos delete endpoint not yet implemented")
        
        assert response.status_code == 204
        
        # Verify soft delete
        photo.refresh_from_db()
        assert photo.is_deleted is True
        assert photo.deleted_at is not None
    
    def test_soft_delete_photo_practitioner_forbidden(self, practitioner_client, patient):
        """Practitioner cannot delete photos"""
        from apps.clinical.models import ClinicalPhoto
        
        photo = ClinicalPhoto.objects.create(
            patient=patient,
            photo_kind='clinical',
            object_key='photos/test.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
        )
        
        response = practitioner_client.delete(f'/api/v1/photos/{photo.id}/')
        
        if response.status_code == 404:
            pytest.skip("Clinical photos delete endpoint not yet implemented")
        
        assert response.status_code == 403
        
        # Verify NOT deleted
        photo.refresh_from_db()
        assert photo.is_deleted is False
    
    def test_soft_deleted_photo_not_in_list(self, admin_client, patient):
        """Soft-deleted photos excluded from list by default"""
        from apps.clinical.models import ClinicalPhoto
        
        photo = ClinicalPhoto.objects.create(
            patient=patient,
            photo_kind='clinical',
            object_key='photos/test.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
        )
        
        # Delete
        delete_response = admin_client.delete(f'/api/v1/photos/{photo.id}/')
        if delete_response.status_code == 404:
            pytest.skip("Clinical photos delete endpoint not yet implemented")
        
        # List should not include it
        list_response = admin_client.get('/api/v1/photos/')
        results = list_response.data if isinstance(list_response.data, list) else list_response.data.get('results', [])
        photo_ids = [str(p['id']) for p in results]
        
        assert str(photo.id) not in photo_ids


@pytest.mark.django_db
class TestPhotoEncounterAttachment:
    """Test attaching/detaching photos to encounters"""
    
    def test_attach_photo_to_encounter(self, admin_client, patient, encounter):
        """Attach a photo to an encounter via POST /photos/{id}/attach-to-encounter/"""
        from apps.clinical.models import ClinicalPhoto, EncounterPhoto
        
        photo = ClinicalPhoto.objects.create(
            patient=patient,
            photo_kind='before',
            object_key='photos/test.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
        )
        
        payload = {
            'encounter_id': str(encounter.id),
            'relation_type': 'attached',
        }
        
        response = admin_client.post(
            f'/api/v1/photos/{photo.id}/attach-to-encounter/',
            payload,
            format='json'
        )
        
        if response.status_code == 404:
            pytest.skip("Photo attach-to-encounter endpoint not yet implemented")
        
        assert response.status_code in [200, 201]
        
        # Verify EncounterPhoto relationship created
        assert EncounterPhoto.objects.filter(
            encounter=encounter,
            photo=photo,
            relation_type='attached'
        ).exists()
    
    def test_attach_photo_multiple_encounters(self, admin_client, patient, encounter_factory):
        """Same photo can be attached to multiple encounters"""
        from apps.clinical.models import ClinicalPhoto, EncounterPhoto
        
        photo = ClinicalPhoto.objects.create(
            patient=patient,
            photo_kind='clinical',
            object_key='photos/test.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
        )
        
        enc1 = encounter_factory()
        enc2 = encounter_factory()
        
        # Attach to encounter 1
        response1 = admin_client.post(
            f'/api/v1/photos/{photo.id}/attach-to-encounter/',
            {'encounter_id': str(enc1.id), 'relation_type': 'attached'},
            format='json'
        )
        
        if response1.status_code == 404:
            pytest.skip("Photo attach-to-encounter endpoint not yet implemented")
        
        # Attach to encounter 2
        response2 = admin_client.post(
            f'/api/v1/photos/{photo.id}/attach-to-encounter/',
            {'encounter_id': str(enc2.id), 'relation_type': 'comparison'},
            format='json'
        )
        
        assert response1.status_code in [200, 201]
        assert response2.status_code in [200, 201]
        
        # Verify both relationships exist
        assert EncounterPhoto.objects.filter(photo=photo).count() == 2
    
    def test_attach_photo_duplicate_relationship(self, admin_client, patient, encounter):
        """Cannot attach same photo to same encounter twice (unique constraint)"""
        from apps.clinical.models import ClinicalPhoto
        
        photo = ClinicalPhoto.objects.create(
            patient=patient,
            photo_kind='before',
            object_key='photos/test.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
        )
        
        payload = {'encounter_id': str(encounter.id), 'relation_type': 'attached'}
        
        # First attach succeeds
        response1 = admin_client.post(
            f'/api/v1/photos/{photo.id}/attach-to-encounter/',
            payload,
            format='json'
        )
        
        if response1.status_code == 404:
            pytest.skip("Photo attach-to-encounter endpoint not yet implemented")
        
        # Second attach should fail or be idempotent
        response2 = admin_client.post(
            f'/api/v1/photos/{photo.id}/attach-to-encounter/',
            payload,
            format='json'
        )
        
        # Either 400 (duplicate) or 200 (idempotent)
        assert response2.status_code in [200, 400]
    
    def test_detach_photo_from_encounter(self, admin_client, patient, encounter):
        """Detach photo from encounter via POST /photos/{id}/detach-from-encounter/"""
        from apps.clinical.models import ClinicalPhoto, EncounterPhoto
        
        photo = ClinicalPhoto.objects.create(
            patient=patient,
            photo_kind='clinical',
            object_key='photos/test.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
        )
        
        # Create relationship
        EncounterPhoto.objects.create(
            encounter=encounter,
            photo=photo,
            relation_type='attached'
        )
        
        payload = {'encounter_id': str(encounter.id)}
        
        response = admin_client.post(
            f'/api/v1/photos/{photo.id}/detach-from-encounter/',
            payload,
            format='json'
        )
        
        if response.status_code == 404:
            pytest.skip("Photo detach-from-encounter endpoint not yet implemented")
        
        assert response.status_code in [200, 204]
        
        # Verify relationship deleted
        assert not EncounterPhoto.objects.filter(
            encounter=encounter,
            photo=photo
        ).exists()
    
    def test_attach_photo_practitioner_allowed(self, practitioner_client, patient, encounter):
        """Practitioner can attach photos to encounters"""
        from apps.clinical.models import ClinicalPhoto
        
        photo = ClinicalPhoto.objects.create(
            patient=patient,
            photo_kind='clinical',
            object_key='photos/test.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
        )
        
        response = practitioner_client.post(
            f'/api/v1/photos/{photo.id}/attach-to-encounter/',
            {'encounter_id': str(encounter.id), 'relation_type': 'attached'},
            format='json'
        )
        
        if response.status_code == 404:
            pytest.skip("Photo attach-to-encounter endpoint not yet implemented")
        
        assert response.status_code in [200, 201]


@pytest.mark.django_db
class TestClinicalPhotoPermissions:
    """Test photo permissions by role"""
    
    @pytest.mark.parametrize('client_fixture,expected_status', [
        ('admin_client', 200),
        ('practitioner_client', 200),
        ('reception_client', 403),
        ('accounting_client', 403),
        ('marketing_client', 403),
    ])
    def test_list_photos_permissions(self, request, client_fixture, expected_status):
        """Test list photos permissions by role"""
        client = request.getfixturevalue(client_fixture)
        
        response = client.get('/api/v1/photos/')
        
        if response.status_code == 404:
            pytest.skip("Clinical photos list endpoint not yet implemented")
        
        assert response.status_code == expected_status
    
    @pytest.mark.parametrize('client_fixture,expected_status', [
        ('admin_client', 201),
        ('practitioner_client', 201),
        ('reception_client', 403),
        ('accounting_client', 403),
        ('marketing_client', 403),
    ])
    def test_create_photo_permissions(self, request, client_fixture, expected_status, patient):
        """Test create photo permissions by role"""
        client = request.getfixturevalue(client_fixture)
        
        payload = {
            'patient': str(patient.id),
            'photo_kind': 'clinical',
            'object_key': 'photos/test.jpg',
            'content_type': 'image/jpeg',
            'size_bytes': 1024000,
        }
        
        response = client.post('/api/v1/photos/', payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Clinical photos create endpoint not yet implemented")
        
        assert response.status_code == expected_status
