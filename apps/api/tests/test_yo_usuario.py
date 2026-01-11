"""
Test verification for yo@ejemplo.com test user after FASE 4.2 update.

NOTE: This test verifies the manually updated test user in development DB.
It will be skipped in CI/test environments where the user doesn't exist.
"""
import pytest
from apps.authz.models import User, Practitioner, Role, UserRole


@pytest.mark.django_db
def test_yo_usuario_updated_profile():
    """Verify yo@ejemplo.com returns correct data from /api/auth/me/ after manual update."""
    from django.test import Client
    
    # Check if user exists (dev DB only)
    user = User.objects.filter(email='yo@ejemplo.com').first()
    if not user:
        pytest.skip("Test user yo@ejemplo.com not found (expected in dev DB only)")
    
    # If user exists, verify it has correct data
    client = Client()
    client.force_login(user)
    
    response = client.get('/api/auth/me/')
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    
    # Verificar campos actualizados
    assert data['email'] == 'yo@ejemplo.com'
    assert data['first_name'] == 'Ricardo', f"Expected 'Ricardo', got '{data['first_name']}'"
    assert data['last_name'] == 'P', f"Expected 'P', got '{data['last_name']}'"
    assert data['practitioner_calendly_url'] == 'https://calendly.com/app/scheduling/meeting_types/user/me'
    assert 'admin' in data['roles'], f"Expected 'admin' in {data['roles']}"


@pytest.mark.django_db
def test_create_user_with_names_and_practitioner():
    """
    Test creating a user with first_name/last_name and practitioner with calendly_url.
    
    This tests the same pattern used to update yo@ejemplo.com.
    """
    # Create user with names
    user = User.objects.create_user(
        email='test.fase42@example.com',
        password='TestPassword123!',
        first_name='Test',
        last_name='User',
        is_active=True,
        is_staff=True,
        is_superuser=True
    )
    
    # Create practitioner with calendly_url
    practitioner = Practitioner.objects.create(
        user=user,
        display_name=f'{user.first_name} {user.last_name}',
        role_type='physician',
        calendly_url='https://calendly.com/test-user',
        is_active=True
    )
    
    # Assign admin role
    admin_role, _ = Role.objects.get_or_create(name='admin')
    UserRole.objects.create(user=user, role=admin_role)
    
    # Verify via API
    from django.test import Client
    client = Client()
    client.force_login(user)
    
    response = client.get('/api/auth/me/')
    assert response.status_code == 200
    
    data = response.json()
    assert data['email'] == 'test.fase42@example.com'
    assert data['first_name'] == 'Test'
    assert data['last_name'] == 'User'
    assert data['practitioner_calendly_url'] == 'https://calendly.com/test-user'
    assert 'admin' in data['roles']
