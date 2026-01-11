"""
Management command to create stock RBAC groups.

Usage:
    python manage.py create_stock_groups

Creates (idempotently):
- Reception: No stock access
- ClinicalOps: Full stock access
- Marketing: No stock access
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group


class Command(BaseCommand):
    help = 'Create stock RBAC groups (Reception, ClinicalOps, Marketing)'

    def handle(self, *args, **options):
        """Create groups if they don't exist."""
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
