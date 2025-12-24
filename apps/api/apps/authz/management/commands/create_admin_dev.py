"""
Django management command to create admin user for development.

Usage:
    python manage.py create_admin_dev

Creates user:
    Email: yo@ejemplo.com
    Password: Libertad
    Role: Admin
    Status: Active

⚠️  FOR DEVELOPMENT ONLY - DO NOT USE IN PRODUCTION
"""
from django.core.management.base import BaseCommand
from apps.authz.models import User, Role, UserRole, RoleChoices


class Command(BaseCommand):
    help = 'Create admin user for development (Ricardo / yo@ejemplo.com / Libertad)'

    def handle(self, *args, **options):
        """Create admin user for development."""
        
        email = 'yo@ejemplo.com'
        password = 'Libertad'
        
        # Check if user exists
        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(f'User "{email}" already exists'))
            user = User.objects.get(email=email)
            
            # Update password in case it was changed
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f'✓ Updated user "{email}"'))
        else:
            # Create user
            user = User.objects.create_user(
                email=email,
                password=password,
                is_staff=True,      # Required for Django admin
                is_superuser=True,  # Django superuser
                is_active=True
            )
            self.stdout.write(self.style.SUCCESS(f'✓ Created user "{email}"'))
        
        # Ensure admin role exists
        admin_role, created = Role.objects.get_or_create(
            name=RoleChoices.ADMIN,
            defaults={'name': RoleChoices.ADMIN}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created role "{admin_role.name}"'))
        
        # Assign admin role to user
        user_role, created = UserRole.objects.get_or_create(
            user=user,
            role=admin_role
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Assigned role "{admin_role.name}" to user'))
        else:
            self.stdout.write(self.style.SUCCESS(f'✓ User already has role "{admin_role.name}"'))
        
        # Summary
        self.stdout.write('')
        self.stdout.write('='*70)
        self.stdout.write(self.style.SUCCESS('✓ ADMIN USER READY FOR DEVELOPMENT'))
        self.stdout.write('='*70)
        self.stdout.write(f'  Email:    {email}')
        self.stdout.write(f'  Password: {password}')
        self.stdout.write(f'  Role:     Admin')
        self.stdout.write(f'  Status:   Active, Staff, Superuser')
        self.stdout.write('='*70)
        self.stdout.write('  Login at: http://localhost:3000/es/login')
        self.stdout.write('='*70)
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('⚠️  FOR DEVELOPMENT ONLY'))
        self.stdout.write(self.style.WARNING('   Remove or disable this user in production!'))
        self.stdout.write('')
