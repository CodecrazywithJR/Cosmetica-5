"""
Pytest configuration for the entire test suite.

This file configures test database to use SQLite for faster tests.
"""
import os
import django
from django.conf import settings


def pytest_configure():
    """Configure Django settings for tests."""
    # Override DATABASE settings to use SQLite for tests
    if not settings.configured:
        settings.configure()
    
    # Force SQLite for tests (faster, no Docker dependency)
    settings.DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',  # In-memory database for speed
        }
    }
    
    django.setup()
