"""
Regression test: SkinPhoto list endpoint must NOT return photos for soft-deleted patients.

Gap closed: apps/photos/views.py queryset now filters patient__is_deleted=False.
"""
import pytest
from unittest.mock import patch
from django.utils import timezone
from rest_framework import status

from apps.photos.models import SkinPhoto
from tests.conftest import TEST_PASSWORD


def _create_skin_photo(patient, legal_entity):
    """
    Create a SkinPhoto via ORM without triggering actual file upload or Celery task.
    ImageField accepts a plain path string at ORM level (no form validation).
    """
    with patch('apps.photos.tasks.generate_thumbnail.delay'):
        photo = SkinPhoto.objects.create(
            patient=patient,
            body_part='face',
            image='photos/fake_hardening_test.jpg',
            description='hardening regression test photo',
            legal_entity=legal_entity,
        )
    return photo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def legal_entity(db):
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
def admin_user(db):
    from apps.authz.models import User, Role, UserRole, RoleChoices
    user = User.objects.create_user(
        email='admin_photos_test@test.com',
        password=TEST_PASSWORD,
        is_staff=True,
        is_superuser=True,
        is_active=True,
    )
    role, _ = Role.objects.get_or_create(name=RoleChoices.ADMIN)
    UserRole.objects.create(user=user, role=role)
    return user


@pytest.fixture
def admin_api_client(admin_user, legal_entity):
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=admin_user)
    client.credentials(HTTP_X_LEGAL_ENTITY_ID=str(legal_entity.id))
    return client


@pytest.fixture
def patient(db, admin_user, legal_entity):
    from apps.clinical.models import Patient
    return Patient.objects.create(
        first_name='Soft',
        last_name='Delete',
        full_name_normalized='soft delete',
        birth_date='1990-01-01',
        sex='female',
        email='soft.delete.photos@test.com',
        phone='+33600000001',
        phone_e164='+33600000001',
        country_code='FR',
        identity_confidence='medium',
        created_by_user=admin_user,
        legal_entity=legal_entity,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

PHOTOS_LIST_URL = '/api/photos/'


class TestSkinPhotoSoftDeletedPatientBlocked:
    """
    Verify that photos linked to soft-deleted patients are invisible
    in the SkinPhotoViewSet list and retrieve endpoints.
    """

    def test_photo_visible_before_soft_delete(self, db, admin_api_client, patient, legal_entity):
        """Baseline: photo is returned when patient is NOT deleted."""
        photo = _create_skin_photo(patient, legal_entity)

        response = admin_api_client.get(PHOTOS_LIST_URL)

        assert response.status_code == status.HTTP_200_OK
        ids = [str(item['id']) for item in response.data['results']]
        assert str(photo.id) in ids, "Photo should be visible for non-deleted patient"

    def test_photo_invisible_after_soft_delete(self, db, admin_api_client, patient, legal_entity):
        """
        Core regression: after soft-deleting the patient, the photo must
        NOT appear in the list endpoint.
        """
        photo = _create_skin_photo(patient, legal_entity)

        # Soft-delete the patient (mirrors AppointmentViewSet.destroy pattern)
        patient.is_deleted = True
        patient.deleted_at = timezone.now()
        patient.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])

        response = admin_api_client.get(PHOTOS_LIST_URL)

        assert response.status_code == status.HTTP_200_OK
        ids = [str(item['id']) for item in response.data['results']]
        assert str(photo.id) not in ids, (
            "Photo for soft-deleted patient must NOT appear in list"
        )

    def test_retrieve_photo_returns_404_after_soft_delete(self, db, admin_api_client, patient, legal_entity):
        """
        Retrieve a specific photo after soft-deleting its patient — must return 404,
        not 200 (get_object() uses the filtered queryset).
        """
        photo = _create_skin_photo(patient, legal_entity)

        patient.is_deleted = True
        patient.deleted_at = timezone.now()
        patient.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])

        response = admin_api_client.get(f'{PHOTOS_LIST_URL}{photo.id}/')

        assert response.status_code == status.HTTP_404_NOT_FOUND, (
            "Retrieving a photo for a soft-deleted patient must return 404"
        )

    def test_two_patients_only_active_photos_returned(self, db, admin_api_client, patient, legal_entity, admin_user):
        """
        With two patients (one active, one soft-deleted), only photos from
        the active patient appear in the list.
        """
        from apps.clinical.models import Patient

        active_patient = Patient.objects.create(
            first_name='Active',
            last_name='Patient',
            full_name_normalized='active patient',
            birth_date='1985-06-15',
            sex='male',
            email='active.patient.photos@test.com',
            phone='+33600000002',
            phone_e164='+33600000002',
            country_code='FR',
            identity_confidence='medium',
            created_by_user=admin_user,
            legal_entity=legal_entity,
        )

        photo_active = _create_skin_photo(active_patient, legal_entity)
        photo_deleted = _create_skin_photo(patient, legal_entity)

        # Soft-delete the second patient
        patient.is_deleted = True
        patient.deleted_at = timezone.now()
        patient.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])

        response = admin_api_client.get(PHOTOS_LIST_URL)

        assert response.status_code == status.HTTP_200_OK
        ids = [str(item['id']) for item in response.data['results']]
        assert str(photo_active.id) in ids, "Active patient photo must be visible"
        assert str(photo_deleted.id) not in ids, "Soft-deleted patient photo must be hidden"
