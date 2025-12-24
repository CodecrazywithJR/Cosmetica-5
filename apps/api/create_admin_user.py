#!/usr/bin/env python
"""
Create admin user for development: Ricardo (yo@ejemplo.com / Libertad)
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.authz.models import User, Role, UserRole, RoleChoices

def create_admin_user():
    """Create admin user for development."""
    
    # Check if user exists
    email = 'yo@ejemplo.com'
    if User.objects.filter(email=email).exists():
        print(f"✅ User '{email}' already exists")
        user = User.objects.get(email=email)
    else:
        # Create user
        user = User.objects.create_user(
            email=email,
            password='Libertad',
            is_staff=True,      # Required for Django admin
            is_superuser=True,  # Django superuser
            is_active=True
        )
        print(f"✅ Created user: {email}")
    
    # Ensure admin role exists
    admin_role, created = Role.objects.get_or_create(
        name=RoleChoices.ADMIN,
        defaults={'name': RoleChoices.ADMIN}
    )
    if created:
        print(f"✅ Created role: {admin_role.name}")
    
    # Assign admin role to user
    user_role, created = UserRole.objects.get_or_create(
        user=user,
        role=admin_role
    )
    if created:
        print(f"✅ Assigned role '{admin_role.name}' to user '{email}'")
    else:
        print(f"✅ User '{email}' already has role '{admin_role.name}'")
    
    print("\n" + "="*60)
    print("✅ ADMIN USER READY")
    print("="*60)
    print(f"Email:    {email}")
    print(f"Password: Libertad")
    print(f"Role:     Admin")
    print(f"Status:   Active")
    print("="*60)
    print("\nYou can now login at: http://localhost:3000/es/login")
    print("="*60)

if __name__ == '__main__':
    create_admin_user()
