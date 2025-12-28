"""
Photo models - Skin photography with MinIO storage.
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _


def photo_upload_path(instance, filename):
    """Generate upload path for photos."""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return f"photos/{instance.patient.id}/{filename}"


class SkinPhoto(models.Model):
    """
    Skin photo model - stores dermatology photos with metadata.
    """
    BODY_PART_CHOICES = [
        ('face', _('Face')),
        ('scalp', _('Scalp')),
        ('neck', _('Neck')),
        ('chest', _('Chest')),
        ('back', _('Back')),
        ('arms', _('Arms')),
        ('hands', _('Hands')),
        ('legs', _('Legs')),
        ('feet', _('Feet')),
        ('other', _('Other')),
    ]
    
    # Relationships
    patient = models.ForeignKey(
        'clinical.Patient',
        on_delete=models.CASCADE,
        related_name='legacy_photos',
        verbose_name=_('Patient')
    )
    encounter = models.ForeignKey(
        'clinical.Encounter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='legacy_photos_link',
        verbose_name=_('Encounter')
    )
    
    # Photo details
    image = models.ImageField(_('Image'), upload_to=photo_upload_path)
    thumbnail = models.ImageField(_('Thumbnail'), upload_to='thumbnails/', blank=True, null=True)
    body_part = models.CharField(_('Body Part'), max_length=20, choices=BODY_PART_CHOICES)
    tags = models.CharField(_('Tags'), max_length=500, blank=True, help_text=_('Comma-separated tags'))
    description = models.TextField(_('Description'), blank=True)
    
    # Metadata
    taken_at = models.DateTimeField(_('Taken At'), auto_now_add=True)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    # Processing status
    thumbnail_generated = models.BooleanField(_('Thumbnail Generated'), default=False)
    
    class Meta:
        db_table = 'skin_photos'
        ordering = ['-taken_at']
        indexes = [
            models.Index(fields=['patient', '-taken_at']),
            models.Index(fields=['encounter']),
            models.Index(fields=['body_part']),
        ]
        verbose_name = _('Skin Photo')
        verbose_name_plural = _('Skin Photos')
    
    def __str__(self):
        return f"Photo of {self.patient} - {self.body_part} ({self.taken_at.strftime('%Y-%m-%d')})"
    
    def clean(self):
        """
        Validate clinical domain invariants.
        
        CRITICAL: If photo references an encounter, both must share the same patient.
        """
        from django.core.exceptions import ValidationError
        
        super().clean()
        
        # INVARIANT: Patient is required (already enforced by FK NOT NULL)
        if not self.patient_id:
            raise ValidationError({
                'patient': 'Photo must have a patient assigned.'
            })
        
        # INVARIANT: Encounter-Patient coherence
        # If photo has an encounter, both must reference the same patient
        if self.encounter_id and self.encounter:
            if self.encounter.patient_id != self.patient_id:
                raise ValidationError({
                    'encounter': (
                        f'Encounter patient mismatch: '
                        f'photo.patient={self.patient_id} but '
                        f'encounter.patient={self.encounter.patient_id}. '
                        f'Both must reference the same patient.'
                    )
                })
