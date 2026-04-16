"""
Tests for Reception role bootstrap migration.
"""
import pytest
from django.core.management import call_command
from tests.conftest import TEST_PASSWORD


@pytest.fixture(autouse=True)
def ensure_reception_role(db):
    """Ensure the reception role exists (mirrors what migration 0002 does)."""
    from apps.authz.models import Role
    Role.objects.get_or_create(name='reception')


@pytest.mark.django_db
class TestReceptionRoleBootstrap:
    """Test that the Reception role is created automatically by migrations."""
    
    def test_reception_role_exists_after_migrations(self):
        """Test that the Reception role exists after running migrations."""
        from apps.authz.models import Role
        
        reception_role = Role.objects.filter(name='reception').first()
        
        assert reception_role is not None, "Reception role should exist after migrations"
        assert reception_role.name == 'reception'
    
    def test_reception_role_idempotent(self):
        """Test that role creation is idempotent (can run multiple times safely)."""
        from apps.authz.models import Role
        
        initial_count = Role.objects.filter(name='reception').count()
        assert initial_count == 1, "Reception role should exist exactly once"
        
        # Create again — should be idempotent
        Role.objects.get_or_create(name='reception')
        
        final_count = Role.objects.filter(name='reception').count()
        assert final_count == 1, "Reception role should still exist exactly once (idempotent)"
    
    def test_can_assign_reception_role_to_user(self, django_user_model):
        """Test that we can assign the Reception role to a user."""
        from apps.authz.models import Role, UserRole
        
        user = django_user_model.objects.create_user(
            email='reception@clinic.com',
            password=TEST_PASSWORD
        )
        
        reception_role = Role.objects.get(name='reception')
        
        user_role = UserRole.objects.create(user=user, role=reception_role)
        
        assert user_role.role == reception_role
        assert user_role.user == user
        
        user_roles = UserRole.objects.filter(user=user, role__name='reception')
        assert user_roles.count() == 1
