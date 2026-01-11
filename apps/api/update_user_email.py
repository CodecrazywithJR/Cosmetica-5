"""
Update test user email from yo@ejemplo.com to ricardoparlon@gmail.com
for real Calendly integration testing.

Usage:
    docker compose exec api python manage.py shell < update_user_email.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.authz.models import User

def update_user_email():
    """Update existing test user email for real Calendly integration."""
    
    old_email = "yo@ejemplo.com"
    new_email = "ricardoparlon@gmail.com"
    
    try:
        # Check if new email already exists
        if User.objects.filter(email=new_email).exists():
            print(f"❌ ERROR: User with email {new_email} already exists!")
            print("   Cannot proceed. Please resolve conflict manually.")
            return False
        
        # Find existing user
        user = User.objects.get(email=old_email)
        print(f"✓ Found user: {user.email}")
        print(f"  - ID: {user.id}")
        print(f"  - First name: {user.first_name}")
        print(f"  - Last name: {user.last_name}")
        print(f"  - Is staff: {user.is_staff}")
        print(f"  - Is superuser: {user.is_superuser}")
        
        # Check Practitioner
        if hasattr(user, 'practitioner'):
            print(f"  - Practitioner ID: {user.practitioner.id}")
            print(f"  - Calendly URL: {user.practitioner.calendly_url}")
        else:
            print("  - No practitioner associated")
        
        # Update email
        user.email = new_email
        user.save()
        
        print(f"\n✅ SUCCESS: Email updated from {old_email} to {new_email}")
        print(f"   Password remains: Libertad (unchanged)")
        print(f"   All other fields preserved")
        
        # Verify update
        updated_user = User.objects.get(email=new_email)
        print(f"\n✓ Verification:")
        print(f"  - New email: {updated_user.email}")
        print(f"  - User ID: {updated_user.id}")
        print(f"  - Can authenticate: {updated_user.check_password('Libertad')}")
        
        return True
        
    except User.DoesNotExist:
        print(f"❌ ERROR: User with email {old_email} not found!")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    update_user_email()
