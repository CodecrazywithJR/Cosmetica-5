"""
ClinicalPhoto REST API endpoints for Encounters.
Handles photo upload, listing, download, and hard delete.
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

from apps.clinical.models import ClinicalPhoto, Encounter, EncounterPhoto, PhotoKindChoices
from apps.clinical.permissions import EncounterPermission
from apps.clinical.utils_storage import (
    generate_presigned_put_url,
    get_clinical_photo_url,
    generate_object_key,
    delete_object
)


# File validation constants
ALLOWED_PHOTO_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp']
ALLOWED_PHOTO_MIMES = ['image/jpeg', 'image/png', 'image/webp']
MAX_PHOTO_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


class ClinicalPhotoViewSet(viewsets.ViewSet):
    """
    ViewSet for managing clinical photos in encounters.
    
    Endpoints:
    - POST /encounters/{encounter_id}/photos/ - Upload photo
    - GET /encounters/{encounter_id}/photos/ - List photos
    - DELETE /photos/{id}/ - Delete photo (hard)
    - GET /photos/{id}/download/ - Get presigned download URL
    """
    permission_classes = [IsAuthenticated, EncounterPermission]
    parser_classes = [MultiPartParser, FormParser]
    
    def list(self, request, encounter_id=None):
        """List all photos for an encounter."""
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
        
        # Get photos
        photos = []
        for encounter_photo in encounter.encounter_photos.filter(clinical_photo__is_deleted=False).select_related('clinical_photo'):
            photo = encounter_photo.clinical_photo
            try:
                url = get_clinical_photo_url(photo)
            except Exception:
                url = None
            
            photos.append({
                'id': str(photo.id),
                'classification': photo.photo_kind,
                'created_at': photo.created_at.isoformat(),
                'url': url,
                'filename': photo.object_key.split('/')[-1] if photo.object_key else None,
                'mime_type': photo.content_type,
                'size_bytes': photo.size_bytes,
            })
        
        return Response(photos)
    
    def create(self, request, encounter_id=None):
        """
        Upload a photo to an encounter.
        
        Request body (multipart/form-data):
        - file: Image file (required)
        - classification: Photo kind (required) - before/after/clinical
        
        Response:
        - id: Photo UUID
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
        
        # Validate classification (required)
        classification = request.data.get('classification')
        if not classification:
            return Response(
                {'error': 'classification is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        valid_classifications = [choice[0] for choice in PhotoKindChoices.choices]
        if classification not in valid_classifications:
            return Response(
                {'error': f'Invalid classification. Must be one of: {", ".join(valid_classifications)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate file
        file = request.FILES.get('file')
        if not file:
            return Response(
                {'error': 'file is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check file size
        if file.size > MAX_PHOTO_SIZE_BYTES:
            return Response(
                {'error': f'File size exceeds maximum of {MAX_PHOTO_SIZE_BYTES / (1024 * 1024)}MB'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check file extension
        filename = file.name.lower()
        file_extension = filename.split('.')[-1] if '.' in filename else ''
        if file_extension not in ALLOWED_PHOTO_EXTENSIONS:
            return Response(
                {'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_PHOTO_EXTENSIONS)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check MIME type
        content_type = file.content_type
        if content_type not in ALLOWED_PHOTO_MIMES:
            return Response(
                {'error': f'Invalid MIME type. Allowed: {", ".join(ALLOWED_PHOTO_MIMES)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate object key
        object_key = generate_object_key('photos', file.name)
        
        # Calculate SHA256
        file.seek(0)
        sha256_hash = hashlib.sha256(file.read()).hexdigest()
        file.seek(0)
        
        # Create ClinicalPhoto record and update counters atomically
        from apps.clinical.attachment_counters import recalc_attachment_counters
        with transaction.atomic():
            clinical_photo = ClinicalPhoto.objects.create(
                patient=encounter.patient,
                photo_kind=classification,
                storage_bucket=settings.MINIO_CLINICAL_BUCKET,
                object_key=object_key,
                content_type=content_type,
                size_bytes=file.size,
                sha256=sha256_hash,
                created_by_user=request.user
            )
            # Link to encounter
            EncounterPhoto.objects.create(
                encounter=encounter,
                clinical_photo=clinical_photo
            )
            # Recalcular y persistir contadores
            recalc_attachment_counters(encounter.id)
        # Generate presigned PUT URL
        try:
            upload_url = generate_presigned_put_url(
                bucket_name=settings.MINIO_CLINICAL_BUCKET,
                object_key=object_key,
                content_type=content_type
            )
        except Exception as e:
            # Rollback photo creation if URL generation fails
            clinical_photo.delete()
            recalc_attachment_counters(encounter.id)
            return Response(
                {'error': f'Failed to generate upload URL: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        return Response({
            'id': str(clinical_photo.id),
            'upload_url': upload_url,
            'object_key': object_key,
            'classification': classification,
        }, status=status.HTTP_201_CREATED)
    
    def destroy(self, request, pk=None):
        """
        Hard delete a photo.
        Removes from database AND MinIO storage.
        """
        try:
            photo = ClinicalPhoto.objects.get(id=pk, is_deleted=False)
        except ClinicalPhoto.DoesNotExist:
            return Response(
                {'error': 'Photo not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions - user must have access to at least one encounter with this photo
        encounters = Encounter.objects.filter(
            encounter_photos__clinical_photo=photo,
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
                    bucket_name=photo.storage_bucket,
                    object_key=photo.object_key
                )
            except Exception as e:
                pass
            # Get affected encounter ids before delete
            affected_encounters = list(
                Encounter.objects.filter(encounter_photos__clinical_photo=photo, is_deleted=False).values_list('id', flat=True)
            )
            # Hard delete from database (cascade deletes EncounterPhoto links)
            photo.delete()
            # Recalcular y persistir contadores en todos los encounters afectados
            for eid in affected_encounters:
                recalc_attachment_counters(eid)
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Get presigned download URL for a photo."""
        try:
            photo = ClinicalPhoto.objects.get(id=pk, is_deleted=False)
        except ClinicalPhoto.DoesNotExist:
            return Response(
                {'error': 'Photo not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        encounters = Encounter.objects.filter(
            encounter_photos__clinical_photo=photo,
            is_deleted=False
        )
        
        if not any(self._has_access(request.user, enc) for enc in encounters):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Generate presigned URL
        try:
            url = get_clinical_photo_url(photo)
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
