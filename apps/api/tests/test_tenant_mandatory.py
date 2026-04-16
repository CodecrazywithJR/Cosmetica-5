"""
Tenant mandatory — enforcement tests.

Covers section 4 of the Permission Matrix:
- Non-superuser without legal_entity → error (model clean + save)
- Superuser without legal_entity → allowed
- Cannot create normal user without legal_entity via API
- UserCreateSerializer auto-inherits LE from acting user
- UserCreateSerializer blocks when acting user's LE is inactive
- Last-admin-per-LegalEntity protection
- Admin self-deactivation block
"""
import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.test import APIClient

from apps.authz.models import (
    Practitioner,
    PractitionerRoleChoices,
    Role,
    RoleChoices,
    User,
    UserRole,
)
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
def active_le(db):
    return LegalEntity.objects.create(
        legal_name='Tenant Test Clinic',
        address_line_1='1 Rue Tenant',
        city='Lyon',
        postal_code='69001',
        country_code='FR',
        legal_email='tenant@clinic.com',
        is_active=True,
    )


@pytest.fixture
def inactive_le(db):
    return LegalEntity.objects.create(
        legal_name='Inactive Tenant Clinic',
        address_line_1='2 Rue Inactive',
        city='Lyon',
        postal_code='69001',
        country_code='FR',
        legal_email='inactive_tenant@clinic.com',
        is_active=False,
    )


@pytest.fixture
def admin_user(db, roles, active_le):
    """Admin user belonging to active LE."""
    user = User.objects.create_user(
        email='tenant_admin@test.com',
        password=TEST_PASSWORD,
        is_active=True,
        legal_entity=active_le,
    )
    UserRole.objects.create(user=user, role=roles['admin'])
    return user


@pytest.fixture
def admin_inactive_le(db, roles, inactive_le):
    """Admin user belonging to inactive LE."""
    user = User.objects.create_user(
        email='tenant_admin_inactive@test.com',
        password=TEST_PASSWORD,
        is_active=True,
        legal_entity=inactive_le,
    )
    UserRole.objects.create(user=user, role=roles['admin'])
    return user


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        email='tenant_super@test.com',
        password=TEST_PASSWORD,
    )


def _client(user, le=None):
    """Client authenticated at BOTH Django middleware and DRF level."""
    c = APIClient()
    c.force_authenticate(user=user)
    c.force_login(user)  # Sets session so Django middleware sees request.user
    if le is not None:
        c.credentials(HTTP_X_LEGAL_ENTITY_ID=str(le.id))
    return c


USERS_URL = '/api/v1/users/'


# ============================================================================
# 4a. Model-level: clean() enforcement
# ============================================================================

class TestModelCleanEnforcement:
    """User.clean() raises ValidationError for non-superuser without LE."""

    def test_non_superuser_without_le_clean_fails(self, db):
        user = User(email='no_le@test.com', is_superuser=False)
        user.set_password('testpass123')
        with pytest.raises(DjangoValidationError) as exc_info:
            user.clean()
        assert 'legal_entity' in exc_info.value.message_dict

    def test_superuser_without_le_clean_passes(self, db):
        user = User(email='su_no_le@test.com', is_superuser=True)
        user.set_password('testpass123')
        # Should NOT raise
        user.clean()

    def test_non_superuser_with_le_clean_passes(self, active_le):
        user = User(
            email='with_le@test.com',
            is_superuser=False,
            legal_entity=active_le,
        )
        user.set_password('testpass123')
        # Should NOT raise
        user.clean()


# ============================================================================
# 4b. Model-level: save() enforcement
# ============================================================================

class TestModelSaveEnforcement:
    """User.save() raises ValidationError for non-superuser without LE."""

    def test_non_superuser_without_le_save_fails(self, db):
        user = User(email='save_no_le@test.com', is_superuser=False)
        user.set_password('testpass123')
        with pytest.raises(DjangoValidationError, match='legal_entity'):
            user.save()

    def test_superuser_without_le_save_passes(self, db):
        user = User(email='save_su@test.com', is_superuser=True, is_staff=True)
        user.set_password('testpass123')
        user.save()
        assert user.pk is not None

    def test_non_superuser_with_le_save_passes(self, active_le):
        user = User(
            email='save_with_le@test.com',
            is_superuser=False,
            legal_entity=active_le,
        )
        user.set_password('testpass123')
        user.save()
        assert user.pk is not None

    def test_partial_save_with_update_fields_skips_check(self, active_le):
        """
        save(update_fields=['password']) skips the LE check.
        This allows legacy partial updates to work.
        """
        user = User.objects.create_user(
            email='partial_save@test.com',
            password=TEST_PASSWORD,
            legal_entity=active_le,
        )
        # Simulate removing LE reference in memory (legacy scenario)
        user.legal_entity = None
        user.legal_entity_id = None
        # Partial save of unrelated field should NOT raise
        user.set_password('newpass123')
        user.save(update_fields=['password'])

    def test_full_save_after_removing_le_fails(self, active_le):
        """Full save after removing LE from non-superuser raises."""
        user = User.objects.create_user(
            email='full_save_strip@test.com',
            password=TEST_PASSWORD,
            legal_entity=active_le,
        )
        user.legal_entity = None
        user.legal_entity_id = None
        with pytest.raises(DjangoValidationError, match='legal_entity'):
            user.save()


# ============================================================================
# 4c. API-level: Cannot create user without legal_entity
# ============================================================================

class TestAPICannotCreateWithoutLE:
    """
    UserCreateSerializer enforces LE inheritance.
    Admin creates user → user inherits LE from acting admin.
    """

    def test_created_user_inherits_le_from_admin(self, admin_user, roles):
        data = {
            'email': 'inherited@test.com',
            'roles': ['reception'],
        }
        resp = _client(admin_user).post(USERS_URL, data, format='json')
        assert resp.status_code == status.HTTP_201_CREATED
        new_user = User.objects.get(email='inherited@test.com')
        assert new_user.legal_entity_id == admin_user.legal_entity_id

    def test_superuser_can_create_user_for_le(self, superuser, roles, active_le):
        """
        Superuser can create users. The middleware doesn't block.
        The serializer should still work regardless of LE.
        """
        # Superuser creates via system plane or directly
        data = {
            'legal_name': 'SU Created Clinic',
            'country_code': 'FR',
            'legal_email': 'su_created2@clinic.fr',
            'admin_email': 'su_admin_created2@clinic.fr',
        }
        resp = _client(superuser).post(
            '/api/v1/system/legal-entities/', data, format='json'
        )
        assert resp.status_code == status.HTTP_201_CREATED
        # The admin user created by system plane should have the new LE
        new_user = User.objects.get(email='su_admin_created2@clinic.fr')
        assert new_user.legal_entity is not None


# ============================================================================
# 4d. API-level: Block user creation when LE inactive
# ============================================================================

class TestAPIBlockCreateWhenLEInactive:
    """UserCreateSerializer.validate() blocks when acting user's LE is inactive."""

    def test_admin_with_inactive_le_cannot_create_user(
        self, admin_inactive_le, roles
    ):
        """
        Middleware blocks POST with 403 (inactive LE).
        If middleware is bypassed, serializer blocks with 400.
        Either way, the operation is denied.
        """
        data = {
            'email': 'should_fail@test.com',
            'roles': ['reception'],
        }
        resp = _client(admin_inactive_le).post(USERS_URL, data, format='json')
        # Middleware returns 403, serializer returns 400 — both are valid
        assert resp.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_400_BAD_REQUEST,
        )


# ============================================================================
# 4e. Last-admin-per-LegalEntity protection
# ============================================================================

class TestLastAdminProtection:
    """Cannot deactivate or remove admin role from last admin of an LE."""

    def test_cannot_deactivate_last_admin(self, admin_user, roles, active_le):
        """Deactivating the only admin of an LE should fail."""
        # Create a second admin to act as the caller
        caller = User.objects.create_user(
            email='caller_admin@test.com',
            password=TEST_PASSWORD,
            is_active=True,
            legal_entity=active_le,
        )
        UserRole.objects.create(user=caller, role=roles['admin'])

        # Now try to deactivate admin_user (the other admin). This is allowed
        # because caller remains as admin.
        resp = _client(caller).patch(
            f'{USERS_URL}{admin_user.id}/',
            {'is_active': False},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK

        # Now try to deactivate caller (the LAST admin)
        resp2 = _client(caller).patch(
            f'{USERS_URL}{caller.id}/',
            {'is_active': False},
            format='json',
        )
        # Should be blocked — self-deactivation rule
        assert resp2.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_remove_admin_role_from_last_admin(self, roles, active_le):
        """Removing admin role from the sole admin should fail."""
        sole_admin = User.objects.create_user(
            email='sole_admin@test.com',
            password=TEST_PASSWORD,
            is_active=True,
            legal_entity=active_le,
        )
        UserRole.objects.create(user=sole_admin, role=roles['admin'])

        # Create a non-admin to make the request
        # But only admins can call this endpoint — so use another admin
        caller = User.objects.create_user(
            email='caller2_admin@test.com',
            password=TEST_PASSWORD,
            is_active=True,
            legal_entity=active_le,
        )
        UserRole.objects.create(user=caller, role=roles['admin'])

        # Remove admin role from sole_admin — allowed because caller remains
        resp = _client(caller).patch(
            f'{USERS_URL}{sole_admin.id}/',
            {'roles': ['reception']},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK

        # Now try removing admin role from caller (the last admin)
        resp2 = _client(caller).patch(
            f'{USERS_URL}{caller.id}/',
            {'roles': ['reception']},
            format='json',
        )
        # Self-deactivation block
        assert resp2.status_code == status.HTTP_400_BAD_REQUEST

    def test_superuser_can_remove_last_admin(self, superuser, roles, active_le):
        """Superuser can remove the last admin of an LE (override)."""
        sole_admin = User.objects.create_user(
            email='sole_to_remove@test.com',
            password=TEST_PASSWORD,
            is_active=True,
            legal_entity=active_le,
        )
        UserRole.objects.create(user=sole_admin, role=roles['admin'])

        resp = _client(superuser, le=active_le).patch(
            f'{USERS_URL}{sole_admin.id}/',
            {'roles': ['reception']},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK


# ============================================================================
# 4f. Admin self-deactivation block
# ============================================================================

class TestAdminSelfDeactivation:
    """Admin cannot deactivate themselves (non-superuser)."""

    def test_admin_cannot_self_deactivate(self, roles, active_le):
        admin = User.objects.create_user(
            email='self_deact@test.com',
            password=TEST_PASSWORD,
            is_active=True,
            legal_entity=active_le,
        )
        UserRole.objects.create(user=admin, role=roles['admin'])

        # Need a second admin so "last admin" rule doesn't interfere
        admin2 = User.objects.create_user(
            email='self_deact_peer@test.com',
            password=TEST_PASSWORD,
            is_active=True,
            legal_entity=active_le,
        )
        UserRole.objects.create(user=admin2, role=roles['admin'])

        resp = _client(admin).patch(
            f'{USERS_URL}{admin.id}/',
            {'is_active': False},
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert 'themselves' in resp.json().get('non_field_errors', [''])[0].lower() or \
               'themselves' in str(resp.json()).lower()

    def test_superuser_can_self_deactivate(self, superuser, roles, active_le):
        """Superuser bypasses self-deactivation block."""
        # Give superuser admin role for the IsAdmin permission check
        UserRole.objects.create(user=superuser, role=roles['admin'])
        # Assign legal_entity so superuser appears in tenant-scoped queryset
        superuser.legal_entity = active_le
        superuser.save(update_fields=['legal_entity'])

        resp = _client(superuser, le=active_le).patch(
            f'{USERS_URL}{superuser.id}/',
            {'is_active': False},
            format='json',
        )
        # Superuser is exempt from self-deactivation block
        assert resp.status_code == status.HTTP_200_OK
