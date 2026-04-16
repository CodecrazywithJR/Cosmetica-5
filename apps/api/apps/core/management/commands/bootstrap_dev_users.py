"""
Management command to bootstrap development users with roles and practitioner profiles.

This command is designed EXCLUSIVELY for DEV environments to populate the database
with test users after a reset. It is idempotent and safe to run multiple times.

Environment Variables:
    DEV_BOOTSTRAP_ENABLED: Set to "1" to enable (default: disabled)
    DEV_BOOTSTRAP_USERS: JSON array of user definitions

Example DEV_BOOTSTRAP_USERS format:
[
  {
    "email": "admin@example.com",
    "password": "admin123",
    "first_name": "Admin",
    "last_name": "User",
    "roles": ["admin"],
    "is_practitioner": true,
    "practitioner_data": {
      "display_name": "Dr. Admin",
      "specialty": "Dermatology"
    }
  }
]

Safety guarantees:
- Idempotent: Safe to run multiple times
- Non-destructive: Never deletes or overwrites existing data
- Transactional: Uses database transactions per user
- Password protection: Never changes existing user passwords
"""
import json
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

# Import models directly to avoid circular dependencies
from apps.authz.models import Role, UserRole, Practitioner


class Command(BaseCommand):
    help = 'Bootstrap development users with roles and practitioner profiles (DEV ONLY)'

    def handle(self, *args, **options):
        # Check if bootstrap is enabled
        if os.environ.get('DEV_BOOTSTRAP_ENABLED', '0') != '1':
            self.stdout.write(
                self.style.WARNING('⏭️  DEV_BOOTSTRAP_ENABLED is not set to "1". Skipping bootstrap.')
            )
            return

        # Get users JSON from environment
        users_json = os.environ.get('DEV_BOOTSTRAP_USERS', '')
        if not users_json:
            self.stdout.write(
                self.style.WARNING('⏭️  DEV_BOOTSTRAP_USERS is empty. Nothing to bootstrap.')
            )
            return

        # Parse JSON
        try:
            users_data = json.loads(users_json)
        except json.JSONDecodeError as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Invalid JSON in DEV_BOOTSTRAP_USERS: {e}')
            )
            self.stdout.write(
                self.style.ERROR('   Please check your .env.dev file for JSON syntax errors.')
            )
            return

        if not isinstance(users_data, list):
            self.stdout.write(
                self.style.ERROR('❌ DEV_BOOTSTRAP_USERS must be a JSON array')
            )
            return

        self.stdout.write(self.style.SUCCESS('\n🚀 Starting DEV users bootstrap...'))
        self.stdout.write(self.style.SUCCESS(f'   Found {len(users_data)} user(s) to process\n'))

        User = get_user_model()

        for idx, user_def in enumerate(users_data, 1):
            self.stdout.write(self.style.SUCCESS(f'[{idx}/{len(users_data)}] Processing user: {user_def.get("email", "unknown")}'))
            
            try:
                self._process_user(User, user_def)
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'   ❌ Error processing user: {e}')
                )
                # Continue with next user instead of failing completely
                continue

        self.stdout.write(self.style.SUCCESS('\n✅ DEV users bootstrap completed\n'))

    def _process_user(self, User, user_def):
        """
        Process a single user definition: create user, assign roles, create practitioner.
        
        This method is wrapped in a transaction per user to ensure atomicity.
        """
        email = user_def.get('email')
        if not email:
            self.stdout.write(self.style.ERROR('   ❌ Missing "email" field, skipping'))
            return

        password = user_def.get('password')
        if not password:
            self.stdout.write(self.style.ERROR('   ❌ Missing "password" field, skipping'))
            return

        with transaction.atomic():
            # 1. Create or get user
            user, user_created = self._create_or_get_user(
                User,
                email=email,
                password=password,
                first_name=user_def.get('first_name', ''),
                last_name=user_def.get('last_name', ''),
                is_active=user_def.get('is_active', True),
            )

            if user_created:
                self.stdout.write(self.style.SUCCESS(f'   ✅ User created: {email}'))
            else:
                self.stdout.write(self.style.WARNING(f'   ⏭️  User already exists: {email}'))

            # 2. Assign roles
            roles = user_def.get('roles', [])
            if roles:
                self._assign_roles(user, roles)

            # 3. Create practitioner profile if requested
            is_practitioner = user_def.get('is_practitioner', False)
            if is_practitioner:
                practitioner_data = user_def.get('practitioner_data', {})
                self._create_practitioner(user, practitioner_data)

    def _create_or_get_user(self, User, email, password, first_name='', last_name='', is_active=True):
        """
        Create user if it doesn't exist, or return existing user.
        
        NEVER changes password of existing users for security.
        """
        try:
            user = User.objects.get(email=email)
            return user, False
        except User.DoesNotExist:
            # User doesn't exist, create it
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=is_active,
            )
            return user, True

    def _assign_roles(self, user, role_names):
        """
        Assign roles to user. Creates Role if it doesn't exist.
        Idempotent: won't duplicate UserRole assignments.
        """
        for role_name in role_names:
            # Create or get role
            role, role_created = Role.objects.get_or_create(
                name=role_name,
                defaults={'name': role_name}
            )

            if role_created:
                self.stdout.write(self.style.SUCCESS(f'      ✅ Role created: {role_name}'))

            # Create UserRole if it doesn't exist
            user_role, ur_created = UserRole.objects.get_or_create(
                user=user,
                role=role
            )

            if ur_created:
                self.stdout.write(self.style.SUCCESS(f'      ✅ Role assigned: {role_name}'))
            else:
                self.stdout.write(self.style.WARNING(f'      ⏭️  Role already assigned: {role_name}'))

    def _create_practitioner(self, user, practitioner_data):
        """
        Create Practitioner profile for user if it doesn't exist.
        Idempotent: won't create duplicate practitioner.
        """
        # Check if practitioner already exists
        if hasattr(user, 'practitioner'):
            self.stdout.write(
                self.style.WARNING(f'      ⏭️  Practitioner profile already exists for {user.email}')
            )
            return

        # Extract practitioner fields with defaults
        display_name = practitioner_data.get('display_name')
        if not display_name:
            # Generate from user's name or email
            if user.first_name or user.last_name:
                display_name = f"{user.first_name} {user.last_name}".strip()
            else:
                display_name = user.email.split('@')[0]

        specialty = practitioner_data.get('specialty', 'Dermatology')
        role_type = practitioner_data.get('role_type', 'practitioner')

        # Create practitioner
        Practitioner.objects.create(
            user=user,
            display_name=display_name,
            specialty=specialty,
            role_type=role_type,
            is_active=True,
        )

        self.stdout.write(
            self.style.SUCCESS(f'      ✅ Practitioner profile created: {display_name}')
        )
