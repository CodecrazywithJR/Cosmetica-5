"""
Documents models: document
Based on DOMAIN_MODEL.md section 5
"""
import uuid
from django.db import models
from django.conf import settings


class Document(models.Model):
    """
    Unified document storage (PDFs, attachments, consent forms, etc.).
    
    Fields from DOMAIN_MODEL.md:
    - id: UUID PK
    - storage_bucket: fixed "documents"
    - object_key: path/key in MinIO
    - content_type: MIME type
    - size_bytes: file size
    - sha256: nullable hash for integrity
    - title: nullable human-readable title
    
    Soft delete fields:
    - is_deleted: bool default false
    - deleted_at: nullable
    - deleted_by_user_id: FK -> auth_user nullable
    
    Audit fields:
    - created_by_user_id: FK -> auth_user nullable
    - created_at, updated_at
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Storage fields
    storage_bucket = models.CharField(
        max_length=64,
        default='documents',
        editable=False,
        help_text="Fixed bucket name for all documents"
    )
    object_key = models.CharField(
        max_length=512,
        help_text="MinIO object key (path) within the bucket"
    )
    content_type = models.CharField(
        max_length=128,
        help_text="MIME type (e.g., application/pdf, image/jpeg)"
    )
    size_bytes = models.BigIntegerField(
        help_text="File size in bytes"
    )
    sha256 = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="SHA-256 hash for integrity verification"
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Human-readable title"
    )
    
    # Soft delete fields
    is_deleted = models.BooleanField(
        default=False,
        help_text="Soft delete flag"
    )
    deleted_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the document was soft-deleted"
    )
    deleted_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='deleted_documents',
        help_text="User who soft-deleted this document"
    )
    
    # Audit fields
    created_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='created_documents',
        help_text="User who uploaded this document"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'document'
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'
        indexes = [
            models.Index(fields=['object_key'], name='idx_document_object_key'),
            models.Index(fields=['created_at'], name='idx_document_created_at'),
            models.Index(fields=['is_deleted'], name='idx_document_deleted'),
            models.Index(fields=['content_type'], name='idx_document_content_type'),
        ]
    
    def __str__(self):
        return self.title or f"Document {self.object_key}"

