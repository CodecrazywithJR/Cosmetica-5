"""
Management command to ensure demo users have correct roles assigned.

Usage:
    python manage.py ensure_demo_user_roles

This command is idempotent and safe to run multiple times.
Creates demo users if they don't exist, and ensures they have correct roles.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.authz.models import Role, UserRole, RoleChoices, Practitioner, PractitionerRoleChoices


class Command(BaseCommand):
    help = 'Ensure demo/seed users exist and have correct roles assigned'

    def handle(self, *args, **options):
        User = get_user_model()
        
        # Ensure roles exist
        self.stdout.write("Ensuring roles exist...")
        for role_choice in [RoleChoices.ADMIN, RoleChoices.PRACTITIONER, RoleChoices.RECEPTION, 
                           RoleChoices.MARKETING, RoleChoices.ACCOUNTING]:
            role, created = Role.objects.get_or_create(name=role_choice)
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created role: {role.name}'))
            else:
                self.stdout.write(f'  - Role exists: {role.name}')
        
        # Define demo users with their roles
        demo_users = [
            {
                'email': 'admin@example.com',
                'password': 'admin123dev',
                'first_name': 'Admin',
                'last_name': 'User',
                'role': RoleChoices.ADMIN,
                'is_staff': True,
                'create_practitioner': True,  # Admin needs practitioner for testing
                # DO NOT hardcode calendly_url - leave null for manual configuration
            },
            {
                'email': 'ricardoparlon@gmail.com',
                'password': 'Libertad',
                'first_name': 'Ricardo',
                'last_name': 'Parlon',
                'role': RoleChoices.ADMIN,
                'is_staff': True,
                'create_practitioner': True,
                'calendly_url': 'https://calendly.com/ricardoparlon',
            },
        ]
        
        self.stdout.write("\nEnsuring demo users exist with correct roles...")
        
        for user_data in demo_users:
            email = user_data['email']
            role_name = user_data['role']
            
            try:
                # Get or create user
                user, user_created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        'first_name': user_data.get('first_name', ''),
                        'last_name': user_data.get('last_name', ''),
                        'is_active': True,
                        'is_staff': user_data.get('is_staff', False),
                    }
                )
                
                if user_created:
                    user.set_password(user_data['password'])
                    user.save()
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Created user: {email}'))
                else:
                    # Update existing user to ensure all fields are current
                    user.first_name = user_data.get('first_name', '')
                    user.last_name = user_data.get('last_name', '')
                    user.set_password(user_data['password'])
                    user.save()
                    self.stdout.write(f'  - User exists: {email} (updated)')
                
                # Create or update Practitioner record if needed
                if user_data.get('create_practitioner'):
                    practitioner, prac_created = Practitioner.objects.get_or_create(
                        user=user,
                        defaults={
                            'display_name': f"{user.first_name} {user.last_name}",
                            'role_type': PractitionerRoleChoices.PRACTITIONER,
                            'specialty': 'Dermatology',
                            'calendly_url': user_data.get('calendly_url'),
                            'is_active': True,
                        }
                    )
                    
                    if prac_created:
                        self.stdout.write(self.style.SUCCESS(
                            f'    ✓ Created practitioner record (calendly_url: {practitioner.calendly_url or "not configured"})'
                        ))
                    else:
                        # CRITICAL: Do NOT overwrite existing calendly_url
                        # Only update display_name to reflect current user name
                        practitioner.display_name = f"{user.first_name} {user.last_name}"
                        practitioner.save(update_fields=['display_name', 'updated_at'])
                        self.stdout.write(
                            f'    - Practitioner exists (calendly_url: {practitioner.calendly_url or "not configured"}, display_name updated)'
                        )
                
                # Ensure role assignment
                role = Role.objects.get(name=role_name)
                user_role, role_created = UserRole.objects.get_or_create(
                    user=user,
                    role=role
                )
                
                if role_created:
                    self.stdout.write(self.style.SUCCESS(
                        f'    ✓ Assigned {role.name} role to {email}'
                    ))
                else:
                    self.stdout.write(
                        f'    - User {email} already has {role.name} role'
                    )
                
                # Verify
                roles = list(user.user_roles.values_list('role__name', flat=True))
                self.stdout.write(f'    Current roles: {roles}')
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'  ✗ Error processing {email}: {str(e)}'
                ))
        
        self.stdout.write(self.style.SUCCESS('\n✓ Done'))
