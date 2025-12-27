"""
FASE 4.2: Tests for /api/auth/me/ endpoint with first_name and last_name.

Tests:
- User profile returns first_name and last_name
- Practitioner includes calendly_url
- Empty name fields handled correctly
- Roles included in response
"""
import uuid
from django.test import TestCase
from rest_framework.test import APIClient
from apps.authz.models import User, Practitioner, Role, UserRole


class UserProfileAPITestCase(TestCase):
    """Test suite for /api/auth/me/ endpoint (CurrentUserView)."""

    def setUp(self):
        """Create test users and client."""
        self.client = APIClient()
        
        # Create regular user with name
        self.regular_user = User.objects.create_user(
            email='user@test.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )
        
        # Create practitioner user with name and calendly_url
        self.practitioner_user = User.objects.create_user(
            email='practitioner@test.com',
            password='testpass123',
            first_name='Jane',
            last_name='Smith'
        )
        
        self.practitioner = Practitioner.objects.create(
            user=self.practitioner_user,
            display_name='Dr. Jane Smith',
            role_type='physician',
            calendly_url='https://calendly.com/drsmith'
        )
        
        # Create user without names (blank fields)
        self.user_no_name = User.objects.create_user(
            email='noname@test.com',
            password='testpass123',
            first_name='',
            last_name=''
        )
        
        # Create roles
        self.admin_role = Role.objects.create(name='admin')
        self.manager_role = Role.objects.create(name='manager')

    def test_profile_includes_first_name_and_last_name(self):
        """GET /api/auth/me/ should return first_name and last_name."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/api/auth/me/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data['email'], 'user@test.com')
        self.assertEqual(data['first_name'], 'John')
        self.assertEqual(data['last_name'], 'Doe')
        self.assertTrue('id' in data)
        self.assertTrue('is_active' in data)
        self.assertTrue('roles' in data)

    def test_practitioner_includes_calendly_url(self):
        """Practitioner profile should include calendly_url."""
        self.client.force_authenticate(user=self.practitioner_user)
        response = self.client.get('/api/auth/me/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data['first_name'], 'Jane')
        self.assertEqual(data['last_name'], 'Smith')
        self.assertEqual(data['practitioner_calendly_url'], 'https://calendly.com/drsmith')

    def test_regular_user_no_calendly_url(self):
        """Regular user should have practitioner_calendly_url as None (not a practitioner)."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/api/auth/me/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Regular users get None for practitioner_calendly_url because they're not practitioners
        # Note: Field is present in schema but value is None
        self.assertIsNone(data.get('practitioner_calendly_url'))

    def test_blank_names_returned_as_empty_strings(self):
        """Users with blank first_name/last_name should return empty strings."""
        self.client.force_authenticate(user=self.user_no_name)
        response = self.client.get('/api/auth/me/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data['first_name'], '')
        self.assertEqual(data['last_name'], '')
        self.assertEqual(data['email'], 'noname@test.com')

    def test_roles_included_in_response(self):
        """User with roles should have roles list in response."""
        # Assign roles to regular user
        UserRole.objects.create(user=self.regular_user, role=self.admin_role)
        UserRole.objects.create(user=self.regular_user, role=self.manager_role)
        
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/api/auth/me/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('roles', data)
        self.assertIsInstance(data['roles'], list)
        self.assertIn('admin', data['roles'])
        self.assertIn('manager', data['roles'])
        self.assertEqual(len(data['roles']), 2)

    def test_unauthenticated_request_returns_401(self):
        """Unauthenticated request should return 401."""
        response = self.client.get('/api/auth/me/')
        self.assertEqual(response.status_code, 401)

    def test_practitioner_without_calendly_url(self):
        """Practitioner with null calendly_url should return None."""
        # Create practitioner without calendly_url
        user = User.objects.create_user(
            email='doc@test.com',
            password='testpass123',
            first_name='Michael',
            last_name='Johnson'
        )
        Practitioner.objects.create(
            user=user,
            display_name='Dr. Johnson',
            role_type='physician',
            calendly_url=None
        )
        
        self.client.force_authenticate(user=user)
        response = self.client.get('/api/auth/me/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data['first_name'], 'Michael')
        self.assertEqual(data['last_name'], 'Johnson')
        self.assertIsNone(data['practitioner_calendly_url'])

    def test_profile_response_structure(self):
        """Verify complete response structure for regular user."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/api/auth/me/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Required fields
        required_fields = ['id', 'email', 'first_name', 'last_name', 'is_active', 'roles']
        for field in required_fields:
            self.assertIn(field, data)
        
        # Type checks
        self.assertIsInstance(data['id'], str)  # UUID as string
        self.assertIsInstance(data['email'], str)
        self.assertIsInstance(data['first_name'], str)
        self.assertIsInstance(data['last_name'], str)
        self.assertIsInstance(data['is_active'], bool)
        self.assertIsInstance(data['roles'], list)

    def test_profile_response_structure_practitioner(self):
        """Verify complete response structure for practitioner."""
        self.client.force_authenticate(user=self.practitioner_user)
        response = self.client.get('/api/auth/me/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Required fields (including practitioner_calendly_url)
        required_fields = [
            'id', 'email', 'first_name', 'last_name', 
            'is_active', 'roles', 'practitioner_calendly_url'
        ]
        for field in required_fields:
            self.assertIn(field, data)
        
        # Practitioner-specific checks
        self.assertIsInstance(data['practitioner_calendly_url'], str)
        self.assertTrue(data['practitioner_calendly_url'].startswith('https://'))
