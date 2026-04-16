"""
DEPRECATED: Management command to create stock RBAC groups.

This command is no longer needed. RBAC is now handled entirely via
RoleChoices + UserRole (apps.authz.models). Django Groups are no longer
used in business logic.

Kept for backward-compatibility only — do NOT use in new deployments.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group


class Command(BaseCommand):
    help = '[DEPRECATED] Create stock RBAC groups — use RoleChoices + UserRole instead'

    def handle(self, *args, **options):
        """Create groups if they don't exist."""
        self.stdout.write(
            self.style.WARNING(
                'WARNING: create_stock_groups is DEPRECATED.\n'
                'RBAC is now managed via RoleChoices + UserRole in apps.authz.\n'
                'This command will be removed in a future release.\n'
            )
        )
        groups = [
            ('Reception', 'Reception staff - no stock access'),
            ('ClinicalOps', 'Clinical operations - full stock access'),
            ('Marketing', 'Marketing staff - no stock access'),
        ]
        
        created_count = 0
        existing_count = 0
        
        for group_name, description in groups:
            group, created = Group.objects.get_or_create(name=group_name)
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created group: {group_name}')
                )
            else:
                existing_count += 1
                self.stdout.write(
                    self.style.WARNING(f'→ Group already exists: {group_name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSummary: {created_count} created, {existing_count} existing'
            )
        )
