"""
Consent REST API endpoints for Patient consent management.
Handles consent CRUD and document attachment (upload, download, delete).
"""
import os
import hashlib
from django.conf import settings
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated

from apps.clinical.models import Patient, Consent
from apps.documents.models import Document
from apps.clinical.permissions import ConsentPermission
from apps.clinical.utils_storage import (
    generate_presigned_put_url,
    get_document_url,
    generate_object_key,
    delete_object
)
from apps.clinical.serializers_consents import (
    ConsentListSerializer,
    ConsentDetailSerializer,
    ConsentUpdateSerializer,
)


# File validation constants for consent documents
# Per PATIENT_CONSENT_DOCUMENTS.md: PDF, JPG, PNG, HEIC/HEIF
ALLOWED_CONSENT_DOCUMENT_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png', 'heic', 'heif']
ALLOWED_CONSENT_DOCUMENT_MIMES = [
    'application/pdf',
    'image/jpeg',
    'image/png',
    'image/heic',
    'image/heif',
]
MAX_CONSENT_DOCUMENT_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB per PATIENT_CONSENT_DOCUMENTS.md


class ConsentViewSet(viewsets.ViewSet):
    """
    ViewSet for managing patient consents and their document attachments.
    
    Endpoints:
    - GET /patients/{patient_id}/consents/ - List consents
    - POST /patients/{patient_id}/consents/ - Create consent
    - PATCH /consents/{consent_id}/ - Update consent status
    - POST /consents/{consent_id}/document/ - Attach document
    - GET /consents/{consent_id}/document/download/ - Download document
    - DELETE /consents/{consent_id}/document/ - Delete document
    
    BUSINESS RULES (per PATIENT_CONSENT_DOCUMENTS.md):
    - Reception can manage consent documents (administrative)
    - Reception CANNOT access encounter documents (clinical)
    - Document upload uses presigned URLs (direct to MinIO)
    - Max file size: 25 MB
    - Allowed types: PDF, JPG, PNG, HEIC/HEIF
    """
    permission_classes = [IsAuthenticated, ConsentPermission]
    parser_classes = [MultiPartParser, FormParser]
    
    def list(self, request, patient_id=None):
        """
        List all consents for a patient.
        
        GET /patients/{patient_id}/consents/
        """
        try:
            patient = Patient.objects.get(id=patient_id, is_deleted=False)
        except Patient.DoesNotExist:
            return Response(
                {'error': 'Patient not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        if not self._has_access(request.user, patient):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get consents
        consents = Consent.objects.filter(patient=patient).select_related('document').order_by('-created_at')
        serializer = ConsentListSerializer(consents, many=True)
        return Response(serializer.data)
    
    def create(self, request, patient_id=None):
        """
        Create a new consent for a patient.
        
        POST /patients/{patient_id}/consents/
        
        Request body:
        - consent_type: string (required) - clinical_photos|marketing_photos|newsletter|marketing_messages
        - status: string (required) - granted|revoked
        - granted_at: datetime (required if status=granted)
        - revoked_at: datetime (required if status=revoked)
        
        Response:
        - Consent object with detail serializer
        """
        try:
            patient = Patient.objects.get(id=patient_id, is_deleted=False)
        except Patient.DoesNotExist:
            return Response(
                {'error': 'Patient not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        if not self._has_write_access(request.user, patient):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Create consent
        serializer = ConsentDetailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consent = serializer.save(patient=patient)
        
        # Return detail
        return Response(
            ConsentDetailSerializer(consent).data,
            status=status.HTTP_201_CREATED
        )
    
    def partial_update(self, request, pk=None):
        """
        Update consent status (PATCH only).
        
        PATCH /consents/{consent_id}/
        
        BUSINESS RULE: Only status, granted_at, revoked_at can be updated.
        Documents are managed via separate endpoints.
        
        Request body:
        - status: string (optional) - granted|revoked
        - granted_at: datetime (optional)
        - revoked_at: datetime (optional)
        """
        try:
            consent = Consent.objects.get(id=pk)
        except Consent.DoesNotExist:
            return Response(
                {'error': 'Consent not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        if not self._has_write_access(request.user, consent.patient):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Update
        serializer = ConsentUpdateSerializer(consent, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Return full detail
        return Response(ConsentDetailSerializer(consent).data)
    
    @action(detail=True, methods=['post'], url_path='document')
    def attach_document(self, request, pk=None):
        """
        Attach a document to a consent.
        
        POST /consents/{consent_id}/document/
        
        Request body (multipart/form-data):
        - file: Document file (required)
        
        Response:
        - document_id: Document UUID
        - upload_url: Presigned PUT URL for direct upload to MinIO
        - object_key: MinIO object key
        
        BUSINESS RULE: Uses presigned URL pattern (same as EncounterDocument).
        Frontend must PUT file to upload_url after receiving response.
        """
        try:
            consent = Consent.objects.get(id=pk)
        except Consent.DoesNotExist:
            return Response(
                {'error': 'Consent not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        if not self._has_write_access(request.user, consent.patient):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if consent already has document
        if consent.document and not consent.document.is_deleted:
            return Response(
                {'error': 'Consent already has a document attached. Delete existing document first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate file
        file = request.FILES.get('file')
        if not file:
            return Response(
                {'error': 'file is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check file size (25 MB max per PATIENT_CONSENT_DOCUMENTS.md)
        if file.size > MAX_CONSENT_DOCUMENT_SIZE_BYTES:
            return Response(
                {'error': f'File size exceeds maximum of {MAX_CONSENT_DOCUMENT_SIZE_BYTES / (1024 * 1024)}MB'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check file extension
        filename = file.name.lower()
        file_extension = filename.split('.')[-1] if '.' in filename else ''
        if file_extension not in ALLOWED_CONSENT_DOCUMENT_EXTENSIONS:
            return Response(
                {'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_CONSENT_DOCUMENT_EXTENSIONS)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check MIME type
        content_type = file.content_type
        if content_type not in ALLOWED_CONSENT_DOCUMENT_MIMES:
            return Response(
                {'error': f'Invalid MIME type. Allowed: {", ".join(ALLOWED_CONSENT_DOCUMENT_MIMES)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate object key
        object_key = generate_object_key('consents', file.name)
        
        # Calculate SHA256
        file.seek(0)
        sha256_hash = hashlib.sha256(file.read()).hexdigest()
        file.seek(0)
        
        # Create Document record and link to consent atomically
        with transaction.atomic():
            document = Document.objects.create(
                storage_bucket=settings.MINIO_DOCUMENTS_BUCKET,
                object_key=object_key,
                content_type=content_type,
                size_bytes=file.size,
                sha256=sha256_hash,
                title=f"Consent {consent.consent_type}",
                created_by_user=request.user
            )
            
            # Link to consent
            consent.document = document
            consent.save(update_fields=['document'])
        
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
            consent.document = None
            consent.save(update_fields=['document'])
            return Response(
                {'error': f'Failed to generate upload URL: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        return Response({
            'document_id': str(document.id),
            'upload_url': upload_url,
            'object_key': object_key,
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'], url_path='document/download')
    def download_document(self, request, pk=None):
        """
        Get presigned download URL for consent document.
        
        GET /consents/{consent_id}/document/download/
        
        Response:
        - url: Presigned GET URL (expires in 1 hour)
        """
        try:
            consent = Consent.objects.get(id=pk)
        except Consent.DoesNotExist:
            return Response(
                {'error': 'Consent not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        if not self._has_access(request.user, consent.patient):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if consent has document
        if not consent.document or consent.document.is_deleted:
            return Response(
                {'error': 'Consent has no document attached'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Generate presigned URL
        try:
            url = get_document_url(consent.document)
        except Exception as e:
            return Response(
                {'error': f'Failed to generate download URL: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        return Response({'url': url})
    
    @action(detail=True, methods=['delete'], url_path='document')
    def delete_document(self, request, pk=None):
        """
        Delete document attached to consent (hard delete).
        
        DELETE /consents/{consent_id}/document/
        
        BUSINESS RULE: Removes document from MinIO and database.
        Does NOT delete the consent record itself.
        """
        try:
            consent = Consent.objects.get(id=pk)
        except Consent.DoesNotExist:
            return Response(
                {'error': 'Consent not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        if not self._has_write_access(request.user, consent.patient):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if consent has document
        if not consent.document or consent.document.is_deleted:
            return Response(
                {'error': 'Consent has no document attached'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        document = consent.document
        
        # Hard delete from database and storage atomically
        with transaction.atomic():
            # Delete from MinIO
            try:
                delete_object(
                    bucket_name=document.storage_bucket,
                    object_key=document.object_key
                )
            except Exception:
                pass  # Continue even if MinIO delete fails
            
            # Unlink from consent
            consent.document = None
            consent.save(update_fields=['document'])
            
            # Hard delete from database
            document.delete()
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    def _has_access(self, user, patient):
        """
        Check if user has read access to patient consents.
        
        BUSINESS RULE (per PATIENT_CONSENT_DOCUMENTS.md):
        - Admin: Full access
        - Practitioner: Full access (administrative consent documents)
        - Reception: Full access (administrative consent documents)
        - Accounting: NO ACCESS
        - Marketing: NO ACCESS
        """
        from apps.authz.models import RoleChoices
        
        # Get user roles
        user_roles = set(
            user.user_roles.values_list('role__name', flat=True)
        )
        
        # Admin, Practitioner, Reception have access
        allowed_roles = {RoleChoices.ADMIN, RoleChoices.PRACTITIONER, RoleChoices.RECEPTION}
        return bool(user_roles & allowed_roles)
    
    def _has_write_access(self, user, patient):
        """
        Check if user has write access to patient consents.
        
        BUSINESS RULE: Same as read access for patient consents.
        """
        return self._has_access(user, patient)
