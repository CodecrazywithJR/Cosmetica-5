"""
Pytest configuration for the entire test suite.

Delegates database configuration to config.settings (PostgreSQL).
"""
import os
import pytest
import django
from django.conf import settings


def pytest_configure():
    """Configure Django settings for tests."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()


def _get_test_legal_entity():
    """Get or create a shared LegalEntity for test fixtures."""
    from apps.legal.models import LegalEntity
    le, _ = LegalEntity.objects.get_or_create(
        siret='00000000000001',
        defaults={
            'trade_name': 'Fixture Clinic',
            'legal_name': 'Fixture Clinic SRL',
            'country_code': 'FR',
            'is_active': True,
        },
    )
    return le


@pytest.fixture
def legal_entity(db):
    """Shared LegalEntity for tenant-aware test fixtures."""
    return _get_test_legal_entity()
