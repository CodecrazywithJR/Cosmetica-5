"""
Patient models - Core patient demographic and medical record data.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _


class Patient(models.Model):
    """
    Patient model - stores demographic and contact information.
    """
    GENDER_CHOICES = [
        ('M', _('Male')),
        ('F', _('Female')),
        ('O', _('Other')),
        ('U', _('Prefer not to say')),
    ]
    
    # Demographics
    first_name = models.CharField(_('First Name'), max_length=100)
    last_name = models.CharField(_('Last Name'), max_length=100)
    middle_name = models.CharField(_('Middle Name'), max_length=100, blank=True)
    date_of_birth = models.DateField(_('Date of Birth'))
    gender = models.CharField(_('Gender'), max_length=1, choices=GENDER_CHOICES, default='U')
    
    # Contact
    phone = models.CharField(_('Phone'), max_length=20, blank=True)
    email = models.EmailField(_('Email'), blank=True)
    address = models.TextField(_('Address'), blank=True)
    city = models.CharField(_('City'), max_length=100, blank=True)
    postal_code = models.CharField(_('Postal Code'), max_length=20, blank=True)
    country = models.CharField(_('Country'), max_length=100, blank=True, default='')
    
    # Medical
    blood_type = models.CharField(_('Blood Type'), max_length=5, blank=True)
    allergies = models.TextField(_('Allergies'), blank=True, help_text=_('Known allergies'))
    medical_history = models.TextField(_('Medical History'), blank=True)
    current_medications = models.TextField(_('Current Medications'), blank=True)
    
    # Notes
    notes = models.TextField(_('Notes'), blank=True)
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    is_active = models.BooleanField(_('Active'), default=True)
    
    class Meta:
        db_table = 'patients'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['last_name', 'first_name']),
            models.Index(fields=['phone']),
            models.Index(fields=['email']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name = _('Patient')
        verbose_name_plural = _('Patients')
    
    def __str__(self):
        return f"{self.last_name}, {self.first_name}"
    
    @property
    def full_name(self):
        """Return full name."""
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.last_name)
        return ' '.join(parts)
    
    @property
    def age(self):
        """Calculate age from date of birth."""
        from datetime import date
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )
