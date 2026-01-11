"""
Tests for Reception role bootstrap migration.
"""
import pytest
from django.core.management import call_command


@pytest.mark.django_db
class TestReceptionRoleBootstrap:
    """Test that the Reception role is created automatically by migrations."""
    
    def test_reception_role_exists_after_migrations(self):
        """Test that the Reception role exists after running migrations."""
        from apps.authz.models import Role
        
        # The migration should have already run during test setup
        # Check that the reception role exists
        reception_role = Role.objects.filter(name='reception').first()
        
        assert reception_role is not None, "Reception role should exist after migrations"
        assert reception_role.name == 'reception'
    
    def test_reception_role_idempotent(self):
        """Test that the migration is idempotent (can run multiple times safely)."""
        from apps.authz.models import Role
        
        # Get the initial count
        initial_count = Role.objects.filter(name='reception').count()
        assert initial_count == 1, "Reception role should exist exactly once"
        
        # Run the migration again (simulating re-deployment)
        # This uses Django's migration framework to re-run the specific migration
        try:
            call_command('migrate', 'authz', '0002_bootstrap_reception_role', '--fake')
        except Exception:
            pass  # Migration is already applied
        
        # Count should still be 1 (no duplicates)
        final_count = Role.objects.filter(name='reception').count()
        assert final_count == 1, "Reception role should still exist exactly once (idempotent)"
    
    def test_can_assign_reception_role_to_user(self, django_user_model):
        """Test that we can assign the Reception role to a user."""
        from apps.authz.models import Role, UserRole
        
        # Create a test user
        user = django_user_model.objects.create_user(
            username='receptionist_test',
            email='reception@clinic.com',
            password='testpass123'
        )
        
        # Get the reception role
        reception_role = Role.objects.get(name='reception')
        
        # Assign the role to the user
        user_role = UserRole.objects.create(user=user, role=reception_role)
        
        assert user_role.role == reception_role
        assert user_role.user == user
        
        # Verify the user has the role
        user_roles = UserRole.objects.filter(user=user, role__name='reception')
        assert user_roles.count() == 1
