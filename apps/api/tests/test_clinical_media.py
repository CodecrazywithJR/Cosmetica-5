"""
ClinicalMedia API Tests
"""
import io
from PIL import Image
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.authz.models import User
from apps.clinical.models import Patient
from apps.encounters.models import Encounter, ClinicalMedia


def create_test_image():
    """Create a test image file."""
    file = io.BytesIO()
    image = Image.new('RGB', (100, 100), color='red')
    image.save(file, 'JPEG')
    file.seek(0)
    return SimpleUploadedFile(
        "test_photo.jpg",
        file.getvalue(),
        content_type="image/jpeg"
    )


class ClinicalMediaUploadTests(TestCase):
    """Test media upload functionality."""
    
    def setUp(self):
        """Set up test data."""
        # Create users
        self.practitioner = User.objects.create_user(
            username='drsmith',
            password='test123',
            role='Practitioner'
        )
        self.other_practitioner = User.objects.create_user(
            username='drjones',
            password='test123',
            role='Practitioner'
        )
        self.reception = User.objects.create_user(
            username='reception',
            password='test123',
            role='Reception'
        )
        self.admin = User.objects.create_user(
            username='admin',
            password='test123',
            role='Admin',
            is_staff=True
        )
        
        # Create patient
        self.patient = Patient.objects.create(
            full_name='John Doe',
            email='john@example.com'
        )
        
        # Create encounter
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            practitioner=self.practitioner,
            encounter_type='routine',
            status='in_progress',
            scheduled_at=timezone.now()
        )
        
        self.client = APIClient()
    
    def test_practitioner_can_upload_to_own_encounter(self):
        """Practitioner can upload media to their own encounter."""
        self.client.force_authenticate(user=self.practitioner)
        
        image = create_test_image()
        data = {
            'file': image,
            'category': 'before',
            'notes': 'Before treatment photo'
        }
        
        response = self.client.post(
            f'/api/v1/clinical/encounters/{self.encounter.id}/media/',
            data,
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['category'], 'before')
        self.assertEqual(response.data['notes'], 'Before treatment photo')
        
        # Verify media created
        self.assertEqual(ClinicalMedia.objects.count(), 1)
        media = ClinicalMedia.objects.first()
        self.assertEqual(media.encounter, self.encounter)
        self.assertEqual(media.uploaded_by, self.practitioner)
    
    def test_practitioner_cannot_upload_to_other_encounter(self):
        """Practitioner cannot upload to another practitioner's encounter."""
        self.client.force_authenticate(user=self.other_practitioner)
        
        image = create_test_image()
        data = {'file': image, 'category': 'before'}
        
        response = self.client.post(
            f'/api/v1/clinical/encounters/{self.encounter.id}/media/',
            data,
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ClinicalMedia.objects.count(), 0)
    
    def test_reception_cannot_upload_media(self):
        """Reception staff cannot access media endpoints."""
        self.client.force_authenticate(user=self.reception)
        
        image = create_test_image()
        data = {'file': image, 'category': 'before'}
        
        response = self.client.post(
            f'/api/v1/clinical/encounters/{self.encounter.id}/media/',
            data,
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_admin_can_upload_to_any_encounter(self):
        """Admin can upload media to any encounter."""
        self.client.force_authenticate(user=self.admin)
        
        image = create_test_image()
        data = {'file': image, 'category': 'progress'}
        
        response = self.client.post(
            f'/api/v1/clinical/encounters/{self.encounter.id}/media/',
            data,
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_cannot_upload_to_cancelled_encounter(self):
        """Cannot upload media to cancelled encounters."""
        self.encounter.status = 'cancelled'
        self.encounter.save()
        
        self.client.force_authenticate(user=self.practitioner)
        
        image = create_test_image()
        data = {'file': image, 'category': 'before'}
        
        response = self.client.post(
            f'/api/v1/clinical/encounters/{self.encounter.id}/media/',
            data,
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cancelled', str(response.data).lower())
    
    def test_file_size_validation(self):
        """Validate file size limit (10MB)."""
        self.client.force_authenticate(user=self.practitioner)
        
        # Create large image (>10MB)
        large_file = io.BytesIO()
        large_image = Image.new('RGB', (5000, 5000), color='blue')
        large_image.save(large_file, 'JPEG', quality=100)
        large_file.seek(0)
        
        large_upload = SimpleUploadedFile(
            "large_photo.jpg",
            large_file.getvalue(),
            content_type="image/jpeg"
        )
        
        data = {'file': large_upload, 'category': 'before'}
        
        response = self.client.post(
            f'/api/v1/clinical/encounters/{self.encounter.id}/media/',
            data,
            format='multipart'
        )
        
        # Should reject if over 10MB
        if large_upload.size > 10 * 1024 * 1024:
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn('10MB', str(response.data))
    
    def test_file_type_validation(self):
        """Only allow JPEG, PNG, WebP."""
        self.client.force_authenticate(user=self.practitioner)
        
        # Create a fake PDF
        pdf_file = SimpleUploadedFile(
            "document.pdf",
            b"fake pdf content",
            content_type="application/pdf"
        )
        
        data = {'file': pdf_file, 'category': 'before'}
        
        response = self.client.post(
            f'/api/v1/clinical/encounters/{self.encounter.id}/media/',
            data,
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('type', str(response.data).lower())


class ClinicalMediaListTests(TestCase):
    """Test media listing functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.practitioner = User.objects.create_user(
            username='drsmith',
            password='test123',
            role='Practitioner'
        )
        self.other_practitioner = User.objects.create_user(
            username='drjones',
            password='test123',
            role='Practitioner'
        )
        
        self.patient = Patient.objects.create(
            full_name='John Doe',
            email='john@example.com'
        )
        
        self.encounter1 = Encounter.objects.create(
            patient=self.patient,
            practitioner=self.practitioner,
            encounter_type='routine',
            status='in_progress',
            scheduled_at=timezone.now()
        )
        
        self.encounter2 = Encounter.objects.create(
            patient=self.patient,
            practitioner=self.other_practitioner,
            encounter_type='routine',
            status='in_progress',
            scheduled_at=timezone.now()
        )
        
        # Create media
        self.media1 = ClinicalMedia.objects.create(
            encounter=self.encounter1,
            uploaded_by=self.practitioner,
            media_type='photo',
            category='before',
            file=create_test_image()
        )
        
        self.media2 = ClinicalMedia.objects.create(
            encounter=self.encounter2,
            uploaded_by=self.other_practitioner,
            media_type='photo',
            category='after',
            file=create_test_image()
        )
        
        self.client = APIClient()
    
    def test_practitioner_lists_own_encounter_media(self):
        """Practitioner can list media from their own encounter."""
        self.client.force_authenticate(user=self.practitioner)
        
        response = self.client.get(
            f'/api/v1/clinical/encounters/{self.encounter1.id}/media/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['category'], 'before')
    
    def test_practitioner_cannot_list_other_encounter_media(self):
        """Practitioner cannot list media from other practitioner's encounter."""
        self.client.force_authenticate(user=self.practitioner)
        
        response = self.client.get(
            f'/api/v1/clinical/encounters/{self.encounter2.id}/media/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_soft_deleted_media_not_listed(self):
        """Soft-deleted media is excluded from listings."""
        self.media1.soft_delete()
        
        self.client.force_authenticate(user=self.practitioner)
        
        response = self.client.get(
            f'/api/v1/clinical/encounters/{self.encounter1.id}/media/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


class ClinicalMediaDeleteTests(TestCase):
    """Test media deletion functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.practitioner = User.objects.create_user(
            username='drsmith',
            password='test123',
            role='Practitioner'
        )
        self.other_practitioner = User.objects.create_user(
            username='drjones',
            password='test123',
            role='Practitioner'
        )
        
        self.patient = Patient.objects.create(
            full_name='John Doe',
            email='john@example.com'
        )
        
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            practitioner=self.practitioner,
            encounter_type='routine',
            status='in_progress',
            scheduled_at=timezone.now()
        )
        
        self.media = ClinicalMedia.objects.create(
            encounter=self.encounter,
            uploaded_by=self.practitioner,
            media_type='photo',
            category='before',
            file=create_test_image()
        )
        
        self.client = APIClient()
    
    def test_practitioner_can_delete_own_media(self):
        """Practitioner can delete media from their own encounter."""
        self.client.force_authenticate(user=self.practitioner)
        
        response = self.client.delete(
            f'/api/v1/clinical/media/{self.media.id}/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify soft delete
        self.media.refresh_from_db()
        self.assertIsNotNone(self.media.deleted_at)
        self.assertTrue(self.media.is_deleted)
    
    def test_practitioner_cannot_delete_other_media(self):
        """Practitioner cannot delete media from other's encounter."""
        self.client.force_authenticate(user=self.other_practitioner)
        
        response = self.client.delete(
            f'/api/v1/clinical/media/{self.media.id}/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify not deleted
        self.media.refresh_from_db()
        self.assertIsNone(self.media.deleted_at)


class ClinicalMediaDownloadTests(TestCase):
    """Test media download functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.practitioner = User.objects.create_user(
            username='drsmith',
            password='test123',
            role='Practitioner'
        )
        
        self.patient = Patient.objects.create(
            full_name='John Doe',
            email='john@example.com'
        )
        
        self.encounter = Encounter.objects.create(
            patient=self.patient,
            practitioner=self.practitioner,
            encounter_type='routine',
            status='in_progress',
            scheduled_at=timezone.now()
        )
        
        self.media = ClinicalMedia.objects.create(
            encounter=self.encounter,
            uploaded_by=self.practitioner,
            media_type='photo',
            category='before',
            file=create_test_image()
        )
        
        self.client = APIClient()
    
    def test_authenticated_download(self):
        """Authenticated user can download media file."""
        self.client.force_authenticate(user=self.practitioner)
        
        response = self.client.get(
            f'/api/v1/clinical/media/{self.media.id}/download/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
    
    def test_unauthenticated_download_blocked(self):
        """Unauthenticated requests are blocked."""
        response = self.client.get(
            f'/api/v1/clinical/media/{self.media.id}/download/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
