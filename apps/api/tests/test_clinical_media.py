"""
ClinicalPhoto API Tests

Tests for the clinical photo upload, listing, download, and deletion endpoints.
Endpoints tested:
    POST   /api/v1/clinical/encounters/{id}/photos/
    GET    /api/v1/clinical/encounters/{id}/photos/
    DELETE /api/v1/clinical/photos/{id}/
    GET    /api/v1/clinical/photos/{id}/download/
"""
import io
import pytest
from unittest.mock import patch
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status as http_status

from apps.authz.models import User, Role, UserRole, Practitioner, RoleChoices
from apps.clinical.models import Patient, Encounter, ClinicalPhoto, EncounterPhoto
from tests.conftest import TEST_PASSWORD


def create_test_image():
    """Create a valid JPEG test image."""
    buf = io.BytesIO()
    image = Image.new('RGB', (100, 100), color='red')
    image.save(buf, 'JPEG')
    buf.seek(0)
    return SimpleUploadedFile(
        "test_photo.jpg",
        buf.getvalue(),
        content_type="image/jpeg",
    )


def _make_user(email, role_name, is_staff=False):
    """Create a user with the given role via UserRole."""
    user = User.objects.create_user(email=email, password=TEST_PASSWORD, is_staff=is_staff)
    role, _ = Role.objects.get_or_create(name=role_name)
    UserRole.objects.create(user=user, role=role)
    return user


def _make_practitioner(user, display_name='Dr Test'):
    """Create a Practitioner linked to a user."""
    prac, _ = Practitioner.objects.get_or_create(
        user=user,
        defaults={'display_name': display_name, 'specialty': 'general'},
    )
    return prac


# --- Mocks applied to all tests: MinIO functions ---
MINIO_MOCKS = {
    'apps.clinical.views_photos.generate_presigned_put_url': lambda **kw: 'https://minio.local/upload',
    'apps.clinical.views_photos.get_clinical_photo_url': lambda photo: 'https://minio.local/download',
    'apps.clinical.views_photos.generate_object_key': lambda prefix, name: f'{prefix}/test-key',
    'apps.clinical.views_photos.delete_object': lambda **kw: None,
}


@pytest.fixture(autouse=True)
def _mock_minio():
    """Auto-mock all MinIO/S3 calls for every test."""
    patches = [patch(target, side_effect=fn) for target, fn in MINIO_MOCKS.items()]
    mocks = [p.start() for p in patches]
    yield mocks
    for p in patches:
        p.stop()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def practitioner_user():
    return _make_user('drsmith@clinic.com', RoleChoices.PRACTITIONER)


@pytest.fixture
def other_practitioner_user():
    return _make_user('drjones@clinic.com', RoleChoices.PRACTITIONER)


@pytest.fixture
def reception_user():
    return _make_user('reception@clinic.com', RoleChoices.RECEPTION)


@pytest.fixture
def admin_user():
    return _make_user('admin@clinic.com', RoleChoices.ADMIN, is_staff=True)


def _get_test_legal_entity():
    from apps.legal.models import LegalEntity
    le, _ = LegalEntity.objects.get_or_create(
        siret='00000000000001',
        defaults={
            'trade_name': 'Fixture Clinic',
            'legal_name': 'Fixture Clinic SRL',
            'country_code': 'FR',
            'is_active': True,
        },
    )
    return le


@pytest.fixture
def patient():
    return Patient.objects.create(
        first_name='John', last_name='Doe', email='john@example.com',
        legal_entity=_get_test_legal_entity(),
    )


@pytest.fixture
def encounter(patient, practitioner_user):
    prac = _make_practitioner(practitioner_user, 'Dr Smith')
    return Encounter.objects.create(
        patient=patient,
        practitioner=prac,
        type='consultation',
        status='draft',
        occurred_at=timezone.now(),
        legal_entity=_get_test_legal_entity(),
    )


@pytest.fixture
def encounter_other(patient, other_practitioner_user):
    prac = _make_practitioner(other_practitioner_user, 'Dr Jones')
    return Encounter.objects.create(
        patient=patient,
        practitioner=prac,
        type='consultation',
        status='draft',
        occurred_at=timezone.now(),
        legal_entity=_get_test_legal_entity(),
    )


# ---------------------------------------------------------------------------
# Upload tests
# ---------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
class TestClinicalPhotoUpload:
    """Test photo upload via POST /encounters/{id}/photos/."""

    def _upload_url(self, encounter):
        return f'/api/v1/clinical/encounters/{encounter.id}/photos/'

    def test_practitioner_can_upload_to_own_encounter(
        self, api_client, practitioner_user, encounter
    ):
        api_client.force_authenticate(user=practitioner_user)
        data = {'file': create_test_image(), 'classification': 'before'}
        resp = api_client.post(self._upload_url(encounter), data, format='multipart')
        assert resp.status_code == http_status.HTTP_201_CREATED
        assert resp.data['classification'] == 'before'
        assert ClinicalPhoto.objects.count() == 1

    def test_any_practitioner_can_upload_to_encounter(
        self, api_client, other_practitioner_user, encounter
    ):
        """Any practitioner can upload to any encounter (role-based access)."""
        api_client.force_authenticate(user=other_practitioner_user)
        data = {'file': create_test_image(), 'classification': 'before'}
        resp = api_client.post(self._upload_url(encounter), data, format='multipart')
        assert resp.status_code == http_status.HTTP_201_CREATED

    def test_reception_cannot_upload(
        self, api_client, reception_user, encounter
    ):
        api_client.force_authenticate(user=reception_user)
        data = {'file': create_test_image(), 'classification': 'before'}
        resp = api_client.post(self._upload_url(encounter), data, format='multipart')
        assert resp.status_code == http_status.HTTP_403_FORBIDDEN

    def test_admin_can_upload_to_any_encounter(
        self, api_client, admin_user, encounter
    ):
        api_client.force_authenticate(user=admin_user)
        data = {'file': create_test_image(), 'classification': 'clinical'}
        resp = api_client.post(self._upload_url(encounter), data, format='multipart')
        assert resp.status_code == http_status.HTTP_201_CREATED

    def test_cannot_upload_without_classification(
        self, api_client, practitioner_user, encounter
    ):
        api_client.force_authenticate(user=practitioner_user)
        data = {'file': create_test_image()}
        resp = api_client.post(self._upload_url(encounter), data, format='multipart')
        assert resp.status_code == http_status.HTTP_400_BAD_REQUEST
        assert 'classification' in str(resp.data).lower()

    def test_file_type_validation_rejects_pdf(
        self, api_client, practitioner_user, encounter
    ):
        api_client.force_authenticate(user=practitioner_user)
        pdf = SimpleUploadedFile("doc.pdf", b"fake", content_type="application/pdf")
        data = {'file': pdf, 'classification': 'before'}
        resp = api_client.post(self._upload_url(encounter), data, format='multipart')
        assert resp.status_code == http_status.HTTP_400_BAD_REQUEST
        assert 'type' in str(resp.data).lower()

    def test_upload_without_file_rejected(
        self, api_client, practitioner_user, encounter
    ):
        api_client.force_authenticate(user=practitioner_user)
        data = {'classification': 'before'}
        resp = api_client.post(self._upload_url(encounter), data, format='multipart')
        assert resp.status_code == http_status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_upload_blocked(
        self, api_client, encounter
    ):
        data = {'file': create_test_image(), 'classification': 'before'}
        resp = api_client.post(self._upload_url(encounter), data, format='multipart')
        assert resp.status_code == http_status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# List tests
# ---------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
class TestClinicalPhotoList:
    """Test photo listing via GET /encounters/{id}/photos/."""

    def _list_url(self, encounter):
        return f'/api/v1/clinical/encounters/{encounter.id}/photos/'

    def _create_photo(self, encounter, user, kind='before'):
        photo = ClinicalPhoto.objects.create(
            patient=encounter.patient,
            photo_kind=kind,
            storage_bucket='test-bucket',
            object_key='photos/test-key',
            content_type='image/jpeg',
            size_bytes=1024,
            sha256='abc123',
            created_by_user=user,
        )
        EncounterPhoto.objects.create(encounter=encounter, photo=photo, relation_type='attached')
        return photo

    def test_practitioner_lists_own_encounter_photos(
        self, api_client, practitioner_user, encounter
    ):
        self._create_photo(encounter, practitioner_user, 'before')
        api_client.force_authenticate(user=practitioner_user)
        resp = api_client.get(self._list_url(encounter))
        assert resp.status_code == http_status.HTTP_200_OK
        assert len(resp.data) == 1

    def test_any_practitioner_can_list_encounter_photos(
        self, api_client, practitioner_user, encounter_other
    ):
        """Any practitioner can list photos from any encounter (role-based access)."""
        api_client.force_authenticate(user=practitioner_user)
        resp = api_client.get(self._list_url(encounter_other))
        assert resp.status_code == http_status.HTTP_200_OK

    def test_deleted_photos_are_excluded(
        self, api_client, practitioner_user, encounter
    ):
        photo = self._create_photo(encounter, practitioner_user)
        photo.is_deleted = True
        photo.save(update_fields=['is_deleted'])
        api_client.force_authenticate(user=practitioner_user)
        resp = api_client.get(self._list_url(encounter))
        assert resp.status_code == http_status.HTTP_200_OK
        assert len(resp.data) == 0


# ---------------------------------------------------------------------------
# Delete tests
# ---------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
class TestClinicalPhotoDelete:
    """Test photo deletion via DELETE /photos/{id}/."""

    def _create_photo(self, encounter, user, kind='before'):
        photo = ClinicalPhoto.objects.create(
            patient=encounter.patient,
            photo_kind=kind,
            storage_bucket='test-bucket',
            object_key='photos/test-key',
            content_type='image/jpeg',
            size_bytes=1024,
            sha256='abc123',
            created_by_user=user,
        )
        EncounterPhoto.objects.create(encounter=encounter, photo=photo, relation_type='attached')
        return photo

    def test_practitioner_can_delete_own_photo(
        self, api_client, practitioner_user, encounter
    ):
        photo = self._create_photo(encounter, practitioner_user)
        api_client.force_authenticate(user=practitioner_user)
        resp = api_client.delete(f'/api/v1/clinical/photos/{photo.id}/')
        assert resp.status_code == http_status.HTTP_204_NO_CONTENT
        assert not ClinicalPhoto.objects.filter(id=photo.id).exists()

    def test_any_practitioner_can_delete_encounter_photo(
        self, api_client, other_practitioner_user, encounter
    ):
        """Any practitioner can delete photos from any encounter (role-based access)."""
        photo = self._create_photo(encounter, other_practitioner_user)
        other_user = _make_user('outsider@clinic.com', RoleChoices.PRACTITIONER)
        api_client.force_authenticate(user=other_user)
        resp = api_client.delete(f'/api/v1/clinical/photos/{photo.id}/')
        assert resp.status_code == http_status.HTTP_204_NO_CONTENT


# ---------------------------------------------------------------------------
# Download tests
# ---------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
class TestClinicalPhotoDownload:
    """Test photo download via GET /photos/{id}/download/."""

    def _create_photo(self, encounter, user):
        photo = ClinicalPhoto.objects.create(
            patient=encounter.patient,
            photo_kind='before',
            storage_bucket='test-bucket',
            object_key='photos/test-key',
            content_type='image/jpeg',
            size_bytes=1024,
            sha256='abc123',
            created_by_user=user,
        )
        EncounterPhoto.objects.create(encounter=encounter, photo=photo, relation_type='attached')
        return photo

    def test_authenticated_download(
        self, api_client, practitioner_user, encounter
    ):
        photo = self._create_photo(encounter, practitioner_user)
        api_client.force_authenticate(user=practitioner_user)
        resp = api_client.get(f'/api/v1/clinical/photos/{photo.id}/download/')
        assert resp.status_code == http_status.HTTP_200_OK
        assert 'url' in resp.data

    def test_unauthenticated_download_blocked(
        self, api_client, practitioner_user, encounter
    ):
        photo = self._create_photo(encounter, practitioner_user)
        resp = api_client.get(f'/api/v1/clinical/photos/{photo.id}/download/')
        assert resp.status_code == http_status.HTTP_401_UNAUTHORIZED
