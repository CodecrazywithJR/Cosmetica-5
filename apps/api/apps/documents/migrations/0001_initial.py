# Generated migration for documents app - DOMAIN_MODEL.md implementation

import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Document',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('storage_bucket', models.CharField(default='documents', editable=False, help_text='Fixed bucket name for all documents', max_length=64)),
                ('object_key', models.CharField(help_text='MinIO object key (path) within the bucket', max_length=512)),
                ('content_type', models.CharField(help_text='MIME type (e.g., application/pdf, image/jpeg)', max_length=128)),
                ('size_bytes', models.BigIntegerField(help_text='File size in bytes')),
                ('sha256', models.CharField(blank=True, help_text='SHA-256 hash for integrity verification', max_length=64, null=True)),
                ('title', models.CharField(blank=True, help_text='Human-readable title', max_length=255, null=True)),
                ('is_deleted', models.BooleanField(default=False, help_text='Soft delete flag')),
                ('deleted_at', models.DateTimeField(blank=True, help_text='When the document was soft-deleted', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by_user', models.ForeignKey(
                    blank=True,
                    help_text='User who uploaded this document',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_documents',
                    to=settings.AUTH_USER_MODEL
                )),
                ('deleted_by_user', models.ForeignKey(
                    blank=True,
                    help_text='User who soft-deleted this document',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='deleted_documents',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'Document',
                'verbose_name_plural': 'Documents',
                'db_table': 'document',
            },
        ),
        migrations.AddIndex(
            model_name='document',
            index=models.Index(fields=['object_key'], name='idx_document_object_key'),
        ),
        migrations.AddIndex(
            model_name='document',
            index=models.Index(fields=['created_at'], name='idx_document_created_at'),
        ),
        migrations.AddIndex(
            model_name='document',
            index=models.Index(fields=['is_deleted'], name='idx_document_deleted'),
        ),
        migrations.AddIndex(
            model_name='document',
            index=models.Index(fields=['content_type'], name='idx_document_content_type'),
        ),
    ]
