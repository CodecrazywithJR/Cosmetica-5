"""
Social Media models - Instagram content management.

CRITICAL: Uses MARKETING bucket only.
NEVER uses clinical bucket or exposes patient data.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.postgres.fields import ArrayField
from django.conf import settings


class InstagramPost(models.Model):
    """
    Instagram post content for Manual Publish Pack workflow.
    
    Workflow:
    1. Staff creates post in admin with caption and media
    2. Media stored in marketing bucket (NEVER clinical bucket)
    3. Generate pack creates ZIP with caption.txt + images
    4. Staff downloads ZIP and manually uploads to Instagram app
    5. After publishing, staff marks as published with URL
    
    Future: Integrate Instagram Graph API for automatic posting.
    """
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('ready', _('Ready to Publish')),
        ('published', _('Published')),
        ('archived', _('Archived')),
    ]
    
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('ru', 'Русский'),
        ('fr', 'Français'),
        ('es', 'Español'),
        ('uk', 'Українська'),
        ('hy', 'Հայերեն'),
    ]
    
    # Content
    caption = models.TextField(_('Caption'), help_text=_('Instagram caption (max 2200 characters)'))
    language = models.CharField(_('Language'), max_length=5, choices=LANGUAGE_CHOICES, default='en')
    hashtags = ArrayField(
        models.CharField(max_length=100),
        default=list,
        verbose_name=_('Hashtags'),
        blank=True,
        help_text=_('Without # symbol, e.g., ["skincare", "dermatology"]')
    )
    
    # Media (MARKETING bucket only)
    media_keys = ArrayField(
        models.CharField(max_length=500),
        default=list,
        verbose_name=_('Media Keys'),
        help_text=_('MinIO object keys from MARKETING bucket (NOT clinical bucket)')
    )
    
    # Scheduling
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='draft')
    scheduled_at = models.DateTimeField(_('Scheduled For'), null=True, blank=True)
    
    # Publishing
    published_at = models.DateTimeField(_('Published At'), null=True, blank=True)
    instagram_url = models.URLField(_('Instagram URL'), blank=True, help_text=_('URL after manual publish'))
    
    # Pack generation
    pack_generated_at = models.DateTimeField(_('Pack Generated At'), null=True, blank=True)
    pack_file_path = models.CharField(_('Pack File Path'), max_length=500, blank=True, help_text=_('Path to generated ZIP'))
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='instagram_posts',
        verbose_name=_('Created By')
    )
    
    # Analytics (optional, filled after publish)
    likes_count = models.IntegerField(_('Likes'), default=0, blank=True)
    comments_count = models.IntegerField(_('Comments'), default=0, blank=True)
    
    class Meta:
        db_table = 'social_instagram_posts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-scheduled_at']),
            models.Index(fields=['-published_at']),
        ]
        verbose_name = _('Instagram Post')
        verbose_name_plural = _('Instagram Posts')
    
    def __str__(self):
        preview = self.caption[:50] + '...' if len(self.caption) > 50 else self.caption
        return f"{self.status} - {preview}"
    
    def get_full_caption(self):
        """Get caption with hashtags appended."""
        caption = self.caption
        if self.hashtags:
            hashtags_str = ' '.join([f'#{tag}' for tag in self.hashtags])
            caption = f"{caption}\n\n{hashtags_str}"
        return caption
    
    def can_generate_pack(self):
        """Check if pack can be generated."""
        return (
            self.status in ['draft', 'ready'] and
            self.media_keys and
            len(self.media_keys) > 0
        )
    
    def mark_as_ready(self):
        """Mark post as ready to publish."""
        if self.can_generate_pack():
            self.status = 'ready'
            self.save()
    
    def mark_as_published(self, instagram_url=None):
        """Mark post as published."""
        from django.utils import timezone
        self.status = 'published'
        self.published_at = timezone.now()
        if instagram_url:
            self.instagram_url = instagram_url
        self.save()


class InstagramHashtag(models.Model):
    """
    Reusable hashtag library for suggestions.
    """
    CATEGORY_CHOICES = [
        ('skincare', _('Skincare')),
        ('dermatology', _('Dermatology')),
        ('beauty', _('Beauty')),
        ('wellness', _('Wellness')),
        ('clinic', _('Clinic')),
        ('other', _('Other')),
    ]
    
    tag = models.CharField(_('Hashtag'), max_length=100, unique=True, help_text=_('Without # symbol'))
    category = models.CharField(_('Category'), max_length=20, choices=CATEGORY_CHOICES, default='other')
    usage_count = models.IntegerField(_('Usage Count'), default=0)
    
    class Meta:
        db_table = 'social_instagram_hashtags'
        ordering = ['-usage_count', 'tag']
        verbose_name = _('Instagram Hashtag')
        verbose_name_plural = _('Instagram Hashtags')
    
    def __str__(self):
        return f"#{self.tag}"
