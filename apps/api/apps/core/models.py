"""
Core models: app_settings, clinic_location
Based on DOMAIN_MODEL.md section 1
"""
import uuid
from django.db import models


class LanguageChoices(models.TextChoices):
    """Supported languages: ru|fr|en|uk|hy|es"""
    RUSSIAN = 'ru', 'Russian'
    FRENCH = 'fr', 'French'
    ENGLISH = 'en', 'English'
    UKRAINIAN = 'uk', 'Ukrainian'
    ARMENIAN = 'hy', 'Armenian'
    SPANISH = 'es', 'Spanish'


class AppSettings(models.Model):
    """
    Global application settings (single row).
    
    Fields from DOMAIN_MODEL.md:
    - id: UUID PK
    - default_country_code: CHAR(2) default FR
    - default_currency: string default EUR
    - default_language: enum default fr
    - enabled_languages: JSON array
    - timezone: string default Europe/Paris
    - created_at, updated_at
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    default_country_code = models.CharField(max_length=2, default='FR')
    default_currency = models.CharField(max_length=3, default='EUR')
    default_language = models.CharField(
        max_length=2,
        choices=LanguageChoices.choices,
        default=LanguageChoices.FRENCH
    )
    enabled_languages = models.JSONField(
        default=list,
        help_text="Array of enabled language codes"
    )
    timezone = models.CharField(max_length=64, default='Europe/Paris')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'app_settings'
        verbose_name = 'App Settings'
        verbose_name_plural = 'App Settings'

    def __str__(self):
        return f"App Settings ({self.default_country_code}/{self.default_language})"


class ClinicLocation(models.Model):
    """
    Clinic locations for multi-site support.
    
    Fields from DOMAIN_MODEL.md:
    - id: UUID PK
    - name
    - address_line1: nullable
    - city: nullable
    - postal_code: nullable
    - country_code: CHAR(2) nullable
    - timezone: default Europe/Paris
    - is_active: bool default true
    - created_at, updated_at
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    country_code = models.CharField(max_length=2, blank=True, null=True)
    timezone = models.CharField(max_length=64, default='Europe/Paris')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clinic_location'
        verbose_name = 'Clinic Location'
        verbose_name_plural = 'Clinic Locations'
        indexes = [
            models.Index(fields=['is_active'], name='idx_clinic_location_active'),
        ]

    def __str__(self):
        return self.name
