"""
Encounter models - Patient visits and consultations.

⚠️ DEPRECATION NOTICE ⚠️
Date: 2025-12-25
Status: DEPRECATED - DO NOT USE

The Encounter model in this module is LEGACY and has been replaced by:
- apps.clinical.models.Encounter (modern, production model)

Reasons for deprecation:
1. Incorrect FK to User (should be Practitioner)
2. Not linked with Appointment model
3. Lacks proper clinical workflow integration
4. Legacy endpoint /api/encounters/ not used by frontend

Migration Path:
- ✅ Use apps.clinical.models.Encounter for all new code
- ✅ Use /api/v1/clinical/encounters/ endpoint
- ❌ DO NOT import from apps.encounters.models.Encounter

Note: ClinicalMedia in this module is ACTIVE and should continue to be used.
Import from apps.encounters.models_media.ClinicalMedia or via this module's __all__.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

# Import ClinicalMedia for unified access
from .models_media import ClinicalMedia

__all__ = ['Encounter', 'ClinicalMedia']  # Encounter kept for backward compatibility only


class Encounter(models.Model):
    """
    ⚠️ DEPRECATED - DO NOT USE ⚠️
    
    This is a LEGACY Encounter model. Use apps.clinical.models.Encounter instead.
    
    Encounter/Visit model - represents a patient visit or consultation.
    """
    ENCOUNTER_TYPE_CHOICES = [
        ('initial', _('Initial Consultation')),
        ('followup', _('Follow-up')),
        ('emergency', _('Emergency')),
        ('routine', _('Routine Check-up')),
    ]
    
    STATUS_CHOICES = [
        ('scheduled', _('Scheduled')),
        ('in_progress', _('In Progress')),
        ('completed', _('Completed')),
        ('cancelled', _('Cancelled')),
        ('no_show', _('No Show')),
    ]
    
    # Relationships
    patient = models.ForeignKey(
        'clinical.Patient',
        on_delete=models.CASCADE,
        related_name='legacy_encounters',
        verbose_name=_('Patient')
    )
    practitioner = models.ForeignKey(
        'authz.User',
        on_delete=models.PROTECT,
        related_name='encounters',
        verbose_name=_('Practitioner'),
        help_text=_('Practitioner responsible for this encounter'),
        null=True,  # Allow null for backward compatibility
        blank=True
    )
    
    # Visit details
    encounter_type = models.CharField(
        _('Type'),
        max_length=20,
        choices=ENCOUNTER_TYPE_CHOICES,
        default='routine'
    )
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='scheduled'
    )
    scheduled_at = models.DateTimeField(_('Scheduled At'))
    started_at = models.DateTimeField(_('Started At'), null=True, blank=True)
    completed_at = models.DateTimeField(_('Completed At'), null=True, blank=True)
    
    # SOAP Notes
    subjective = models.TextField(_('Subjective (S)'), blank=True, help_text=_('Patient symptoms, concerns'))
    objective = models.TextField(_('Objective (O)'), blank=True, help_text=_('Observations, measurements'))
    assessment = models.TextField(_('Assessment (A)'), blank=True, help_text=_('Diagnosis, clinical impression'))
    plan = models.TextField(_('Plan (P)'), blank=True, help_text=_('Treatment plan, next steps'))
    
    # Additional
    chief_complaint = models.CharField(_('Chief Complaint'), max_length=500, blank=True)
    diagnosis = models.TextField(_('Diagnosis'), blank=True)
    prescriptions = models.TextField(_('Prescriptions'), blank=True)
    notes = models.TextField(_('Additional Notes'), blank=True)
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'encounters'
        ordering = ['-scheduled_at']
        indexes = [
            models.Index(fields=['patient', '-scheduled_at']),
            models.Index(fields=['status']),
            models.Index(fields=['-scheduled_at']),
        ]
        verbose_name = _('Encounter')
        verbose_name_plural = _('Encounters')
    
    def __str__(self):
        return f"{self.patient} - {self.scheduled_at.strftime('%Y-%m-%d')}"
