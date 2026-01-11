"""
Website CMS models - Public website content management.

CRITICAL: These models are for PUBLIC content ONLY.
NEVER expose clinical data (patients, encounters, clinical photos) through these models.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.postgres.fields import ArrayField


class WebsiteSettings(models.Model):
    """
    Global website settings (single instance).
    """
    clinic_name = models.CharField(_('Clinic Name'), max_length=200)
    phone = models.CharField(_('Phone'), max_length=50)
    email = models.EmailField(_('Email'))
    address = models.TextField(_('Address'))
    opening_hours = models.TextField(_('Opening Hours'), help_text=_('e.g., Mon-Fri: 9am-6pm'))
    
    # Social links
    instagram_url = models.URLField(_('Instagram URL'), blank=True)
    facebook_url = models.URLField(_('Facebook URL'), blank=True)
    youtube_url = models.URLField(_('YouTube URL'), blank=True)
    
    # Languages
    default_language = models.CharField(_('Default Language'), max_length=5, default='en')
    enabled_languages = ArrayField(
        models.CharField(max_length=5),
        default=list,
        verbose_name=_('Enabled Languages'),
        help_text=_('e.g., ["en", "ru", "fr"]')
    )
    
    # Metadata
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'website_settings'
        verbose_name = _('Website Settings')
        verbose_name_plural = _('Website Settings')
    
    def __str__(self):
        return f"Website Settings - {self.clinic_name}"
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create singleton settings."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class Page(models.Model):
    """
    Static pages for public website (About, Services, etc.).
    """
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('published', _('Published')),
    ]
    
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('ru', 'Русский'),
        ('fr', 'Français'),
        ('es', 'Español'),
        ('uk', 'Українська'),
        ('hy', 'Հայերեն'),
    ]
    
    title = models.CharField(_('Title'), max_length=200)
    slug = models.SlugField(_('Slug'), max_length=200)
    language = models.CharField(_('Language'), max_length=5, choices=LANGUAGE_CHOICES, default='en')
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Content (stored as JSON or Markdown)
    content_json = models.JSONField(_('Content JSON'), null=True, blank=True, help_text=_('Rich content blocks'))
    content_markdown = models.TextField(_('Content Markdown'), blank=True)
    
    # SEO
    seo_title = models.CharField(_('SEO Title'), max_length=200, blank=True)
    seo_description = models.TextField(_('SEO Description'), blank=True, max_length=300)
    og_image_key = models.CharField(_('OG Image Key'), max_length=500, blank=True, help_text=_('MinIO object key'))
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'website_pages'
        ordering = ['language', 'title']
        unique_together = [['slug', 'language']]
        indexes = [
            models.Index(fields=['slug', 'language']),
            models.Index(fields=['status']),
        ]
        verbose_name = _('Page')
        verbose_name_plural = _('Pages')
    
    def __str__(self):
        return f"{self.title} ({self.language})"


class Post(models.Model):
    """
    Blog posts for public website.
    """
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('published', _('Published')),
    ]
    
    LANGUAGE_CHOICES = Page.LANGUAGE_CHOICES
    
    title = models.CharField(_('Title'), max_length=200)
    slug = models.SlugField(_('Slug'), max_length=200)
    language = models.CharField(_('Language'), max_length=5, choices=LANGUAGE_CHOICES, default='en')
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Content
    excerpt = models.TextField(_('Excerpt'), max_length=500, blank=True)
    content_json = models.JSONField(_('Content JSON'), null=True, blank=True)
    content_markdown = models.TextField(_('Content Markdown'), blank=True)
    
    # Media
    cover_image_key = models.CharField(_('Cover Image Key'), max_length=500, blank=True, help_text=_('MinIO object key'))
    
    # Tags
    tags = ArrayField(
        models.CharField(max_length=50),
        default=list,
        verbose_name=_('Tags'),
        blank=True
    )
    
    # SEO
    seo_title = models.CharField(_('SEO Title'), max_length=200, blank=True)
    seo_description = models.TextField(_('SEO Description'), blank=True, max_length=300)
    
    # Metadata
    published_at = models.DateTimeField(_('Published At'), null=True, blank=True)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'website_posts'
        ordering = ['-published_at', '-created_at']
        unique_together = [['slug', 'language']]
        indexes = [
            models.Index(fields=['slug', 'language']),
            models.Index(fields=['status', '-published_at']),
        ]
        verbose_name = _('Blog Post')
        verbose_name_plural = _('Blog Posts')
    
    def __str__(self):
        return f"{self.title} ({self.language})"


class Service(models.Model):
    """
    Services offered by the clinic (public display).
    """
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('published', _('Published')),
    ]
    
    LANGUAGE_CHOICES = Page.LANGUAGE_CHOICES
    
    name = models.CharField(_('Name'), max_length=200)
    slug = models.SlugField(_('Slug'), max_length=200)
    language = models.CharField(_('Language'), max_length=5, choices=LANGUAGE_CHOICES, default='en')
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='published')
    
    # Content
    description = models.TextField(_('Description'))
    price = models.DecimalField(_('Price'), max_digits=10, decimal_places=2, null=True, blank=True)
    duration_minutes = models.IntegerField(_('Duration (minutes)'), null=True, blank=True)
    
    # Display
    order_index = models.IntegerField(_('Order'), default=0, help_text=_('Display order'))
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'website_services'
        ordering = ['order_index', 'name']
        unique_together = [['slug', 'language']]
        indexes = [
            models.Index(fields=['slug', 'language']),
            models.Index(fields=['order_index']),
        ]
        verbose_name = _('Service')
        verbose_name_plural = _('Services')
    
    def __str__(self):
        return f"{self.name} ({self.language})"


class StaffMember(models.Model):
    """
    Staff/team members for public display.
    """
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('published', _('Published')),
    ]
    
    LANGUAGE_CHOICES = Page.LANGUAGE_CHOICES
    
    name = models.CharField(_('Name'), max_length=200)
    role = models.CharField(_('Role'), max_length=200)
    language = models.CharField(_('Language'), max_length=5, choices=LANGUAGE_CHOICES, default='en')
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='published')
    
    # Content
    bio = models.TextField(_('Biography'))
    photo_key = models.CharField(_('Photo Key'), max_length=500, blank=True, help_text=_('MinIO object key'))
    
    # Display
    order_index = models.IntegerField(_('Order'), default=0)
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'website_staff'
        ordering = ['order_index', 'name']
        indexes = [
            models.Index(fields=['language', 'order_index']),
        ]
        verbose_name = _('Staff Member')
        verbose_name_plural = _('Staff Members')
    
    def __str__(self):
        return f"{self.name} - {self.role} ({self.language})"


class MarketingMediaAsset(models.Model):
    """
    Media assets for marketing/website (stored in MinIO 'marketing' bucket).
    
    CRITICAL: This is SEPARATE from clinical photos.
    Clinical photos use bucket 'derma-photos'.
    Marketing assets use bucket 'marketing'.
    """
    TYPE_CHOICES = [
        ('image', _('Image')),
        ('video', _('Video')),
    ]
    
    LANGUAGE_CHOICES = Page.LANGUAGE_CHOICES
    
    # Storage (MinIO)
    bucket = models.CharField(_('Bucket'), max_length=100, default='marketing', editable=False)
    object_key = models.CharField(_('Object Key'), max_length=500, unique=True)
    
    # Metadata
    type = models.CharField(_('Type'), max_length=20, choices=TYPE_CHOICES, default='image')
    alt_text = models.CharField(_('Alt Text'), max_length=200, blank=True)
    language = models.CharField(_('Language'), max_length=5, choices=LANGUAGE_CHOICES, blank=True, null=True)
    
    # File info
    file_size = models.BigIntegerField(_('File Size (bytes)'), null=True, blank=True)
    mime_type = models.CharField(_('MIME Type'), max_length=100, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    
    class Meta:
        db_table = 'marketing_media_assets'
        ordering = ['-created_at']
        verbose_name = _('Marketing Media Asset')
        verbose_name_plural = _('Marketing Media Assets')
    
    def __str__(self):
        return f"{self.type} - {self.object_key}"


class Lead(models.Model):
    """
    Contact form submissions from public website.
    """
    STATUS_CHOICES = [
        ('new', _('New')),
        ('contacted', _('Contacted')),
        ('converted', _('Converted')),
        ('spam', _('Spam')),
    ]
    
    LANGUAGE_CHOICES = Page.LANGUAGE_CHOICES
    
    # Contact info
    name = models.CharField(_('Name'), max_length=200)
    email = models.EmailField(_('Email'))
    phone = models.CharField(_('Phone'), max_length=50, blank=True)
    message = models.TextField(_('Message'))
    
    # Metadata
    preferred_language = models.CharField(_('Preferred Language'), max_length=5, choices=LANGUAGE_CHOICES, default='en')
    source = models.CharField(_('Source'), max_length=100, blank=True, help_text=_('URL or referrer'))
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='new')
    
    # Internal notes
    notes = models.TextField(_('Internal Notes'), blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'website_leads'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['email']),
        ]
        verbose_name = _('Lead')
        verbose_name_plural = _('Leads')
    
    def __str__(self):
        return f"{self.name} - {self.email} ({self.status})"
