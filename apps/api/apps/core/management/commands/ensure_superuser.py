"""
Management command to ensure superuser exists (for Docker startup).
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create superuser if it does not exist (for Docker initialization)'

    def handle(self, *args, **options):
        User = get_user_model()
        
        # Use email as username field (custom user model)
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123dev')
        
        if not User.objects.filter(email=email).exists():
            User.objects.create_superuser(
                email=email,
                password=password
            )
            self.stdout.write(
                self.style.SUCCESS(f'Superuser "{email}" created successfully')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Superuser "{email}" already exists')
            )
