"""
Encounter models - Patient visits and consultations.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _


class Encounter(models.Model):
    """
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
        'patients.Patient',
        on_delete=models.CASCADE,
        related_name='encounters',
        verbose_name=_('Patient')
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
