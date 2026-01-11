"""
Document REST API endpoints for Encounters.
Handles document upload, listing, download, and hard delete.
"""
import os
import hashlib
import uuid
from django.conf import settings
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated

from apps.clinical.models import Encounter, EncounterDocument
from apps.documents.models import Document
from apps.clinical.permissions import EncounterPermission
from apps.clinical.utils_storage import (
    generate_presigned_put_url,
    get_document_url,
    generate_object_key,
    delete_object
)


# File validation constants
ALLOWED_DOCUMENT_EXTENSIONS = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt']
ALLOWED_DOCUMENT_MIMES = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain',
]
MAX_DOCUMENT_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


class DocumentViewSet(viewsets.ViewSet):
    """
    ViewSet for managing documents in encounters.
    
    Endpoints:
    - POST /encounters/{encounter_id}/documents/ - Upload document
    - GET /encounters/{encounter_id}/documents/ - List documents
    - DELETE /documents/{id}/ - Delete document (hard)
    - GET /documents/{id}/download/ - Get presigned download URL
    """
    permission_classes = [IsAuthenticated, EncounterPermission]
    parser_classes = [MultiPartParser, FormParser]
    
    def list(self, request, encounter_id=None):
        """List all documents for an encounter."""
        try:
            encounter = Encounter.objects.get(id=encounter_id, is_deleted=False)
        except Encounter.DoesNotExist:
            return Response(
                {'error': 'Encounter not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        if not self._has_access(request.user, encounter):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get documents
        documents = []
        for encounter_doc in encounter.encounter_documents.filter(document__is_deleted=False).select_related('document'):
            doc = encounter_doc.document
            try:
                url = get_document_url(doc)
            except Exception:
                url = None
            
            documents.append({
                'id': str(doc.id),
                'created_at': doc.created_at.isoformat(),
                'url': url,
                'filename': doc.object_key.split('/')[-1] if doc.object_key else None,
                'mime_type': doc.content_type,
                'size_bytes': doc.size_bytes,
                'title': doc.title,
            })
        
        return Response(documents)
    
    def create(self, request, encounter_id=None):
        """
        Upload a document to an encounter.
        
        Request body (multipart/form-data):
        - file: Document file (required)
        - title: Document title (optional)
        
        Response:
        - id: Document UUID
        - upload_url: Presigned PUT URL for direct upload to MinIO
        - object_key: MinIO object key
        """
        try:
            encounter = Encounter.objects.get(id=encounter_id, is_deleted=False)
        except Encounter.DoesNotExist:
            return Response(
                {'error': 'Encounter not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        if not self._has_write_access(request.user, encounter):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate file
        file = request.FILES.get('file')
        if not file:
            return Response(
                {'error': 'file is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check file size
        if file.size > MAX_DOCUMENT_SIZE_BYTES:
            return Response(
                {'error': f'File size exceeds maximum of {MAX_DOCUMENT_SIZE_BYTES / (1024 * 1024)}MB'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check file extension
        filename = file.name.lower()
        file_extension = filename.split('.')[-1] if '.' in filename else ''
        if file_extension not in ALLOWED_DOCUMENT_EXTENSIONS:
            return Response(
                {'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_DOCUMENT_EXTENSIONS)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check MIME type
        content_type = file.content_type
        if content_type not in ALLOWED_DOCUMENT_MIMES:
            return Response(
                {'error': f'Invalid MIME type. Allowed: {", ".join(ALLOWED_DOCUMENT_MIMES)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get optional title
        title = request.data.get('title', file.name)
        
        # Generate object key
        object_key = generate_object_key('documents', file.name)
        
        # Calculate SHA256
        file.seek(0)
        sha256_hash = hashlib.sha256(file.read()).hexdigest()
        file.seek(0)
        
        from apps.clinical.attachment_counters import recalc_attachment_counters
        # Create Document record and update counters atomically
        with transaction.atomic():
            document = Document.objects.create(
                storage_bucket=settings.MINIO_DOCUMENTS_BUCKET,
                object_key=object_key,
                content_type=content_type,
                size_bytes=file.size,
                sha256=sha256_hash,
                title=title,
                created_by_user=request.user
            )
            # Link to encounter
            EncounterDocument.objects.create(
                encounter=encounter,
                document=document
            )
            # Recalcular y persistir contadores
            recalc_attachment_counters(encounter.id)
        # Generate presigned PUT URL
        try:
            upload_url = generate_presigned_put_url(
                bucket_name=settings.MINIO_DOCUMENTS_BUCKET,
                object_key=object_key,
                content_type=content_type
            )
        except Exception as e:
            # Rollback document creation if URL generation fails
            document.delete()
            recalc_attachment_counters(encounter.id)
            return Response(
                {'error': f'Failed to generate upload URL: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        return Response({
            'id': str(document.id),
            'upload_url': upload_url,
            'object_key': object_key,
            'title': title,
        }, status=status.HTTP_201_CREATED)
    
    def destroy(self, request, pk=None):
        """
        Hard delete a document.
        Removes from database AND MinIO storage.
        """
        try:
            document = Document.objects.get(id=pk, is_deleted=False)
        except Document.DoesNotExist:
            return Response(
                {'error': 'Document not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions - user must have access to at least one encounter with this document
        encounters = Encounter.objects.filter(
            encounter_documents__document=document,
            is_deleted=False
        )
        
        if not any(self._has_write_access(request.user, enc) for enc in encounters):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        from apps.clinical.attachment_counters import recalc_attachment_counters
        # Hard delete from database and update counters atomically
        with transaction.atomic():
            # Delete from MinIO
            try:
                delete_object(
                    bucket_name=document.storage_bucket,
                    object_key=document.object_key
                )
            except Exception as e:
                pass
            # Get affected encounter ids before delete
            affected_encounters = list(
                Encounter.objects.filter(encounter_documents__document=document, is_deleted=False).values_list('id', flat=True)
            )
            # Hard delete from database (cascade deletes EncounterDocument links)
            document.delete()
            # Recalcular y persistir contadores en todos los encounters afectados
            for eid in affected_encounters:
                recalc_attachment_counters(eid)
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Get presigned download URL for a document."""
        try:
            document = Document.objects.get(id=pk, is_deleted=False)
        except Document.DoesNotExist:
            return Response(
                {'error': 'Document not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        encounters = Encounter.objects.filter(
            encounter_documents__document=document,
            is_deleted=False
        )
        
        if not any(self._has_access(request.user, enc) for enc in encounters):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Generate presigned URL
        try:
            url = get_document_url(document)
        except Exception as e:
            return Response(
                {'error': f'Failed to generate download URL: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        return Response({'url': url})
    
    def _has_access(self, user, encounter):
        """Check if user has read access to encounter."""
        role = getattr(user, 'role', None)
        if not role:
            return False
        
        # Admin, ClinicalOps, Practitioner have full access
        if role in ['admin', 'clinical_ops', 'practitioner']:
            return True
        
        # Accounting, Reception, Marketing have NO access
        return False
    
    def _has_write_access(self, user, encounter):
        """Check if user has write access to encounter."""
        # Same as read access for v1
        return self._has_access(user, encounter)
