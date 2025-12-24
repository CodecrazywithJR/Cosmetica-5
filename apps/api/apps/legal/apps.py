"""Legal app configuration."""
from django.apps import AppConfig


class LegalConfig(AppConfig):
    """Configuration for legal app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.legal'
    verbose_name = 'Legal Entities'
