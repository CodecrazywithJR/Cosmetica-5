"""
System Plane — LegalEntity API permission tests.

Covers section 1 of the Permission Matrix:
- Superuser can: LIST, CREATE, RETRIEVE, UPDATE, ACTIVATE, DEACTIVATE
- Admin (non-superuser) → 403
- Normal user (practitioner) → 403
- Unauthenticated → 401
- DELETE → 405 (disabled)
"""
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.authz.models import Role, RoleChoices, User, UserRole
from apps.legal.models import LegalEntity
from tests.conftest import TEST_PASSWORD


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def roles(db):
    """Ensure all required roles exist."""
    created = {}
    for rc in RoleChoices:
        role, _ = Role.objects.get_or_create(name=rc.value)
        created[rc.value] = role
    return created


@pytest.fixture
def legal_entity(db):
    """A default active LegalEntity."""
    return LegalEntity.objects.create(
        legal_name='Test Clinic SAS',
        trade_name='Test Clinic',
        address_line_1='1 Rue de Test',
        city='Paris',
        postal_code='75001',
        country_code='FR',
        legal_email='clinic@test.com',
        is_active=True,
    )


@pytest.fixture
def superuser_client(db):
    """Authenticated client with is_superuser=True."""
    user = User.objects.create_superuser(
        email='superuser@test.com',
        password=TEST_PASSWORD,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    client.force_login(user)
    return client


@pytest.fixture
def admin_client_non_super(db, roles, legal_entity):
    """Authenticated client with admin role but NOT superuser."""
    user = User.objects.create_user(
        email='admin_nosuperuser@test.com',
        password=TEST_PASSWORD,
        is_active=True,
        legal_entity=legal_entity,
    )
    UserRole.objects.create(user=user, role=roles['admin'])
    client = APIClient()
    client.force_authenticate(user=user)
    client.force_login(user)
    return client


@pytest.fixture
def practitioner_client(db, roles, legal_entity):
    """Authenticated client with practitioner role."""
    user = User.objects.create_user(
        email='practitioner_sp@test.com',
        password=TEST_PASSWORD,
        is_active=True,
        legal_entity=legal_entity,
    )
    UserRole.objects.create(user=user, role=roles['practitioner'])
    client = APIClient()
    client.force_authenticate(user=user)
    client.force_login(user)
    return client


@pytest.fixture
def anon_client():
    """Unauthenticated client."""
    return APIClient()


# ============================================================================
# URLs
# ============================================================================

SYSTEM_LE_LIST_URL = '/api/v1/system/legal-entities/'


def detail_url(le_id):
    return f'/api/v1/system/legal-entities/{le_id}/'


def activate_url(le_id):
    return f'/api/v1/system/legal-entities/{le_id}/activate/'


def deactivate_url(le_id):
    return f'/api/v1/system/legal-entities/{le_id}/deactivate/'


# ============================================================================
# 1. Superuser — full access
# ============================================================================

class TestSuperuserFullAccess:
    """Superuser can perform all System Plane operations."""

    def test_list_legal_entities(self, superuser_client, legal_entity):
        resp = superuser_client.get(SYSTEM_LE_LIST_URL)
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data.get('results', resp.data)
        assert len(results) >= 1

    def test_create_legal_entity(self, superuser_client, roles):
        data = {
            'legal_name': 'New Clinic SAS',
            'country_code': 'FR',
            'legal_email': 'new@clinic.fr',
            'admin_email': 'newadmin@clinic.fr',
            'admin_first_name': 'Admin',
            'admin_last_name': 'New',
        }
        resp = superuser_client.post(SYSTEM_LE_LIST_URL, data, format='json')
        assert resp.status_code == status.HTTP_201_CREATED
        assert 'legal_entity_id' in resp.data
        assert 'admin_user_id' in resp.data
        assert 'temporary_password' in resp.data

    def test_retrieve_legal_entity(self, superuser_client, legal_entity):
        resp = superuser_client.get(detail_url(legal_entity.id))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data['legal_name'] == legal_entity.legal_name

    def test_update_legal_entity(self, superuser_client, legal_entity):
        resp = superuser_client.patch(
            detail_url(legal_entity.id),
            {'trade_name': 'Updated Trade'},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK
        legal_entity.refresh_from_db()
        assert legal_entity.trade_name == 'Updated Trade'

    def test_activate_legal_entity(self, superuser_client, legal_entity):
        # First deactivate
        legal_entity.is_active = False
        legal_entity.save(update_fields=['is_active'])

        resp = superuser_client.post(activate_url(legal_entity.id))
        assert resp.status_code == status.HTTP_200_OK
        legal_entity.refresh_from_db()
        assert legal_entity.is_active is True

    def test_deactivate_legal_entity(self, superuser_client, legal_entity):
        resp = superuser_client.post(deactivate_url(legal_entity.id))
        assert resp.status_code == status.HTTP_200_OK
        legal_entity.refresh_from_db()
        assert legal_entity.is_active is False

    def test_delete_returns_405(self, superuser_client, legal_entity):
        """DELETE is disabled for all users including superusers."""
        resp = superuser_client.delete(detail_url(legal_entity.id))
        assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


# ============================================================================
# 2. Admin (non-superuser) → 403
# ============================================================================

class TestAdminNonSuperuserDenied:
    """Admin role without is_superuser cannot access System Plane."""

    def test_list_denied(self, admin_client_non_super):
        resp = admin_client_non_super.get(SYSTEM_LE_LIST_URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_create_denied(self, admin_client_non_super, roles):
        data = {
            'legal_name': 'Denied Clinic',
            'country_code': 'FR',
            'legal_email': 'denied@clinic.fr',
            'admin_email': 'denied_admin@clinic.fr',
        }
        resp = admin_client_non_super.post(SYSTEM_LE_LIST_URL, data, format='json')
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_retrieve_denied(self, admin_client_non_super, legal_entity):
        resp = admin_client_non_super.get(detail_url(legal_entity.id))
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_update_denied(self, admin_client_non_super, legal_entity):
        resp = admin_client_non_super.patch(
            detail_url(legal_entity.id),
            {'trade_name': 'Hack'},
            format='json',
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_activate_denied(self, admin_client_non_super, legal_entity):
        legal_entity.is_active = False
        legal_entity.save(update_fields=['is_active'])
        resp = admin_client_non_super.post(activate_url(legal_entity.id))
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_deactivate_denied(self, admin_client_non_super, legal_entity):
        resp = admin_client_non_super.post(deactivate_url(legal_entity.id))
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# 3. Normal user (practitioner) → 403
# ============================================================================

class TestNormalUserDenied:
    """Non-admin roles cannot access System Plane."""

    def test_list_denied(self, practitioner_client):
        resp = practitioner_client.get(SYSTEM_LE_LIST_URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_create_denied(self, practitioner_client, roles):
        data = {
            'legal_name': 'Hack Clinic',
            'country_code': 'FR',
            'legal_email': 'hack@clinic.fr',
            'admin_email': 'hack_admin@clinic.fr',
        }
        resp = practitioner_client.post(SYSTEM_LE_LIST_URL, data, format='json')
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_retrieve_denied(self, practitioner_client, legal_entity):
        resp = practitioner_client.get(detail_url(legal_entity.id))
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_update_denied(self, practitioner_client, legal_entity):
        resp = practitioner_client.patch(
            detail_url(legal_entity.id),
            {'trade_name': 'Hack'},
            format='json',
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_activate_denied(self, practitioner_client, legal_entity):
        resp = practitioner_client.post(activate_url(legal_entity.id))
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_deactivate_denied(self, practitioner_client, legal_entity):
        resp = practitioner_client.post(deactivate_url(legal_entity.id))
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# 4. Unauthenticated → 401
# ============================================================================

class TestUnauthenticatedDenied:
    """Unauthenticated clients get 401 on all System Plane endpoints."""

    def test_list_unauthenticated(self, anon_client):
        resp = anon_client.get(SYSTEM_LE_LIST_URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_unauthenticated(self, anon_client):
        resp = anon_client.post(SYSTEM_LE_LIST_URL, {}, format='json')
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_retrieve_unauthenticated(self, anon_client, legal_entity):
        resp = anon_client.get(detail_url(legal_entity.id))
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_unauthenticated(self, anon_client, legal_entity):
        resp = anon_client.patch(detail_url(legal_entity.id), {}, format='json')
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_activate_unauthenticated(self, anon_client, legal_entity):
        resp = anon_client.post(activate_url(legal_entity.id))
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_deactivate_unauthenticated(self, anon_client, legal_entity):
        resp = anon_client.post(deactivate_url(legal_entity.id))
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ============================================================================
# 5. Idempotency & edge cases
# ============================================================================

class TestEdgeCases:
    """Edge-case validations for System Plane."""

    def test_activate_already_active(self, superuser_client, legal_entity):
        resp = superuser_client.post(activate_url(legal_entity.id))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_deactivate_already_inactive(self, superuser_client, legal_entity):
        legal_entity.is_active = False
        legal_entity.save(update_fields=['is_active'])
        resp = superuser_client.post(deactivate_url(legal_entity.id))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_duplicate_admin_email(self, superuser_client, roles, legal_entity):
        """Cannot create LE with an admin_email that already exists."""
        # Create first user with that email
        User.objects.create_user(
            email='dupe@clinic.fr',
            password=TEST_PASSWORD,
            legal_entity=legal_entity,
        )
        data = {
            'legal_name': 'Dupe Clinic',
            'country_code': 'FR',
            'legal_email': 'dupe_le@clinic.fr',
            'admin_email': 'dupe@clinic.fr',
        }
        resp = superuser_client.post(SYSTEM_LE_LIST_URL, data, format='json')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_filter_by_is_active(self, superuser_client, legal_entity):
        # Create an inactive LE
        inactive_le = LegalEntity.objects.create(
            legal_name='Inactive Clinic',
            address_line_1='x',
            city='Paris',
            postal_code='75001',
            country_code='FR',
            legal_email='inactive@clinic.fr',
            is_active=False,
        )
        resp = superuser_client.get(SYSTEM_LE_LIST_URL, {'is_active': 'false'})
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data.get('results', resp.data)
        ids = [item['id'] for item in results]
        assert str(inactive_le.id) in ids
        assert str(legal_entity.id) not in ids

    def test_search_by_q(self, superuser_client, legal_entity):
        resp = superuser_client.get(SYSTEM_LE_LIST_URL, {'q': 'Test Clinic'})
        assert resp.status_code == status.HTTP_200_OK
        results = resp.data.get('results', resp.data)
        assert len(results) >= 1
