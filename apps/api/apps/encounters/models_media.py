"""
ClinicalMedia models - Clinical photos and media associated with encounters.
Phase 1: Local filesystem storage with audit trail.
"""
import uuid
from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _


def clinical_media_upload_path(instance, filename):
    """
    Generate secure upload path for clinical media.
    Pattern: clinical_media/encounter_{uuid}/media_{uuid}.{ext}
    """
    ext = filename.split('.')[-1].lower()
    media_filename = f"media_{uuid.uuid4()}.{ext}"
    return f"clinical_media/encounter_{instance.encounter.id}/{media_filename}"


class ClinicalMedia(models.Model):
    """
    Clinical media (photos/images) associated with encounters.
    
    Design Decisions:
    - Associated with Encounter (not Patient) for temporal context
    - Soft delete (deleted_at) for audit trail
    - Local storage (Phase 1), prepared for S3 migration
    - No public URLs - authentication required
    """
    
    MEDIA_TYPE_CHOICES = [
        ('photo', _('Photo')),
        # Future: video, document, etc.
    ]
    
    CATEGORY_CHOICES = [
        ('before', _('Before Treatment')),
        ('after', _('After Treatment')),
        ('progress', _('Progress Photo')),
        ('other', _('Other')),
    ]
    
    # Core relationships
    encounter = models.ForeignKey(
        'clinical.Encounter',
        on_delete=models.CASCADE,
        related_name='clinical_media',
        verbose_name=_('Encounter'),
        help_text=_('Clinical encounter this media is associated with')
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_media',
        verbose_name=_('Uploaded By'),
        help_text=_('Practitioner who uploaded this media')
    )
    
    # Media details
    media_type = models.CharField(
        _('Media Type'),
        max_length=20,
        choices=MEDIA_TYPE_CHOICES,
        default='photo'
    )
    category = models.CharField(
        _('Category'),
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='other',
        help_text=_('Clinical category for this media')
    )
    file = models.ImageField(
        _('File'),
        upload_to=clinical_media_upload_path,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['jpg', 'jpeg', 'png', 'webp'],
                message=_('Only JPEG, PNG, and WebP images are allowed')
            )
        ],
        help_text=_('Clinical photo file')
    )
    
    # Optional metadata
    notes = models.TextField(
        _('Notes'),
        blank=True,
        help_text=_('Clinical notes about this media (optional)')
    )
    
    # Audit trail
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        db_index=True
    )
    deleted_at = models.DateTimeField(
        _('Deleted At'),
        null=True,
        blank=True,
        help_text=_('Soft delete timestamp for audit trail')
    )
    
    class Meta:
        db_table = 'clinical_media'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['encounter', '-created_at']),
            models.Index(fields=['uploaded_by', '-created_at']),
            models.Index(fields=['deleted_at']),  # For filtering out soft-deleted
        ]
        verbose_name = _('Clinical Media')
        verbose_name_plural = _('Clinical Media')
    
    def __str__(self):
        return f"{self.get_media_type_display()} - {self.encounter} ({self.created_at.strftime('%Y-%m-%d')})"
    
    def soft_delete(self):
        """
        Soft delete media (preserves file and audit trail).
        File remains on disk but is hidden from queries.
        """
        from django.utils import timezone
        if not self.deleted_at:
            self.deleted_at = timezone.now()
            self.save(update_fields=['deleted_at'])
    
    @property
    def is_deleted(self):
        """Check if media is soft-deleted."""
        return self.deleted_at is not None
    
    @property
    def file_size_mb(self):
        """Get file size in MB (if file exists)."""
        try:
            return round(self.file.size / (1024 * 1024), 2)
        except (AttributeError, FileNotFoundError):
            return None


class ClinicalMediaQuerySet(models.QuerySet):
    """Custom queryset for filtering soft-deleted media."""
    
    def active(self):
        """Return only active (not deleted) media."""
        return self.filter(deleted_at__isnull=True)
    
    def deleted(self):
        """Return only soft-deleted media."""
        return self.filter(deleted_at__isnull=False)


# Attach custom manager
ClinicalMedia.objects = ClinicalMediaQuerySet.as_manager()
