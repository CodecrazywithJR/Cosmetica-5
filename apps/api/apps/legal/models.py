"""
Legal entity models.

⚠️ CRITICAL: NO FISCAL LOGIC HERE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This module contains ONLY legal entity data structures.
DO NOT add:
- TVA/VAT calculation logic
- Tax exemption rules
- Invoice numbering schemes
- PDF generation logic
- Fiscal reporting logic

See: docs/decisions/ADR-002-legal-entity-minimal.md
See: LEGAL_READINESS.md

The purpose of this model is to establish the "legal fact" of who issues
documents (invoices, receipts), leaving fiscal behavior explicitly out of scope.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
import uuid


class LegalEntity(models.Model):
    """
    Represents a legal entity (establishment) that can issue commercial documents.
    
    This is a DATA MODEL ONLY - no fiscal logic included.
    
    Purpose:
    --------
    - Single source of truth for legal entity information
    - Will be referenced by Sale, Invoice (future), Receipt (future)
    - Prepared for future French invoicing compliance WITHOUT implementing it now
    
    What this IS:
    - Legal entity master data (raison sociale, SIRET, address)
    - Issuer identification for commercial documents
    
    What this IS NOT:
    - Tax calculation engine (deferred)
    - Invoice numbering system (deferred)
    - PDF generator (deferred)
    - Fiscal compliance engine (deferred)
    
    French Context:
    ---------------
    Fields like SIREN, SIRET, VAT number are modeled for future compliance
    with French invoicing regulations (Code Général des Impôts), but no
    validation or business logic is implemented yet.
    
    Design Decisions:
    -----------------
    - Single entity assumed initially (multi-entity is possible future extension)
    - Nullable fields for SIREN/SIRET/VAT to allow gradual data entry
    - No automatic numbering or sequence management
    - No relationship to fiscal periods or accounting periods
    
    See ADR-002 for full architectural context.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # Legal identification
    legal_name = models.CharField(
        max_length=255,
        verbose_name=_('Legal name (Raison sociale)'),
        help_text=_('Official registered business name')
    )
    
    trade_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Trade name (Nom commercial)'),
        help_text=_('Commercial name used for public-facing documents')
    )
    
    # Address (required for French invoicing)
    address_line_1 = models.CharField(
        max_length=255,
        verbose_name=_('Address line 1'),
        help_text=_('Street number and name')
    )
    
    address_line_2 = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Address line 2'),
        help_text=_('Complement (building, floor, etc.)')
    )
    
    postal_code = models.CharField(
        max_length=10,
        verbose_name=_('Postal code'),
        help_text=_('Format: 75001 for France')
    )
    
    city = models.CharField(
        max_length=100,
        verbose_name=_('City')
    )
    
    country_code = models.CharField(
        max_length=2,
        default='FR',
        verbose_name=_('Country code'),
        help_text=_('ISO 3166-1 alpha-2 code (e.g., FR, BE, CH)')
    )
    
    # French business identifiers (nullable - may not be available initially)
    siren = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        unique=True,
        verbose_name=_('SIREN'),
        help_text=_('9-digit company identification number (France)'),
        validators=[
            RegexValidator(
                regex=r'^\d{9}$',
                message=_('SIREN must be exactly 9 digits')
            )
        ]
    )
    
    siret = models.CharField(
        max_length=14,
        blank=True,
        null=True,
        unique=True,
        verbose_name=_('SIRET'),
        help_text=_('14-digit establishment identification number (France)'),
        validators=[
            RegexValidator(
                regex=r'^\d{14}$',
                message=_('SIRET must be exactly 14 digits')
            )
        ]
    )
    
    vat_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        unique=True,
        verbose_name=_('VAT number (Numéro TVA)'),
        help_text=_('Intra-community VAT number (e.g., FR12345678901)')
    )
    
    # Operational settings
    currency = models.CharField(
        max_length=3,
        default='EUR',
        verbose_name=_('Currency'),
        help_text=_('ISO 4217 currency code (EUR, USD, etc.)')
    )
    
    timezone = models.CharField(
        max_length=50,
        default='Europe/Paris',
        verbose_name=_('Timezone'),
        help_text=_('IANA timezone database name (Europe/Paris, America/New_York, etc.)')
    )
    
    # Document customization
    invoice_footer_text = models.TextField(
        blank=True,
        verbose_name=_('Invoice footer text'),
        help_text=_('Optional text to appear at bottom of invoices (payment terms, legal notices, etc.)')
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active'),
        help_text=_('Whether this entity can be used for new sales/invoices')
    )
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Legal entity')
        verbose_name_plural = _('Legal entities')
        ordering = ['-is_active', 'legal_name']
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['country_code']),
        ]
    
    def __str__(self):
        """Return legal name with SIRET if available."""
        if self.siret:
            return f"{self.legal_name} (SIRET: {self.siret})"
        return self.legal_name
    
    def clean(self):
        """
        Validate model data.
        
        Note: This is STRUCTURAL validation only, not fiscal validation.
        """
        super().clean()
        
        # Ensure SIREN is prefix of SIRET if both provided
        if self.siren and self.siret:
            if not self.siret.startswith(self.siren):
                from django.core.exceptions import ValidationError
                raise ValidationError({
                    'siret': _('SIRET must start with SIREN (first 9 digits)')
                })
    
    @property
    def full_address(self):
        """Return formatted full address."""
        lines = [self.address_line_1]
        if self.address_line_2:
            lines.append(self.address_line_2)
        lines.append(f"{self.postal_code} {self.city}")
        if self.country_code != 'FR':
            lines.append(self.get_country_display())
        return '\n'.join(lines)
    
    @property
    def display_name(self):
        """Return trade name if available, otherwise legal name."""
        return self.trade_name or self.legal_name
    
    def get_country_display(self):
        """Return country name from code."""
        # Simple mapping for common countries
        countries = {
            'FR': 'France',
            'BE': 'Belgique',
            'CH': 'Suisse',
            'DE': 'Allemagne',
            'IT': 'Italie',
            'ES': 'Espagne',
            'GB': 'Royaume-Uni',
            'US': 'États-Unis',
        }
        return countries.get(self.country_code, self.country_code)
