"""
ClinicalMedia API Views
"""
import logging
from rest_framework import viewsets, status, parsers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

from apps.encounters.models import ClinicalMedia, Encounter
from apps.encounters.api.serializers_media import (
    ClinicalMediaSerializer,
    ClinicalMediaUploadSerializer,
    ClinicalMediaListSerializer
)
from apps.clinical.permissions import IsClinicalStaff

logger = logging.getLogger(__name__)


class ClinicalMediaViewSet(viewsets.ModelViewSet):
    """
    ViewSet for ClinicalMedia management.
    
    Endpoints:
    - POST /api/v1/clinical/encounters/{encounter_id}/media/ - Upload media
    - GET /api/v1/clinical/encounters/{encounter_id}/media/ - List media for encounter
    - DELETE /api/v1/clinical/media/{id}/ - Soft delete media
    - GET /api/v1/clinical/media/{id}/download/ - Download file (authenticated)
    
    RBAC:
    - Practitioner: Can upload/view media for their own encounters
    - ClinicalOps: Full access to all media
    - Admin: Full access
    - Reception: NO ACCESS (enforced by IsClinicalStaff)
    """
    permission_classes = [IsAuthenticated, IsClinicalStaff]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    
    def get_queryset(self):
        """
        Filter queryset based on user role.
        - Admin/ClinicalOps: See all media
        - Practitioner: See only media from their encounters
        """
        user = self.request.user
        queryset = ClinicalMedia.objects.active()  # Exclude soft-deleted
        
        if user.role in ['Admin', 'ClinicalOps']:
            return queryset
        elif user.role == 'Practitioner':
            # Only media from encounters where user is practitioner
            return queryset.filter(encounter__practitioner=user)
        else:
            # Shouldn't reach here (IsClinicalStaff should block)
            return queryset.none()
    
    def get_serializer_class(self):
        """Choose serializer based on action."""
        if self.action == 'create':
            return ClinicalMediaUploadSerializer
        elif self.action == 'list':
            return ClinicalMediaListSerializer
        return ClinicalMediaSerializer
    
    def create(self, request, *args, **kwargs):
        """
        Upload media to encounter.
        POST /api/v1/clinical/encounters/{encounter_id}/media/
        """
        encounter_id = kwargs.get('encounter_id')
        encounter = get_object_or_404(Encounter, id=encounter_id)
        
        # RBAC check: Can user upload to this encounter?
        if request.user.role == 'Practitioner':
            if encounter.practitioner != request.user:
                logger.warning(
                    "media_upload_denied",
                    user_id=request.user.id,
                    encounter_id=encounter.id,
                    reason="not_practitioner"
                )
                raise PermissionDenied("You can only upload media to your own encounters.")
        
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request, 'encounter': encounter}
        )
        serializer.is_valid(raise_exception=True)
        media = serializer.save()
        
        logger.info(
            "media_uploaded",
            media_id=media.id,
            encounter_id=encounter.id,
            user_id=request.user.id,
            category=media.category,
            file_size_mb=media.file_size_mb
        )
        
        # Return full representation
        response_serializer = ClinicalMediaSerializer(
            media,
            context={'request': request}
        )
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    def list(self, request, *args, **kwargs):
        """
        List media for encounter.
        GET /api/v1/clinical/encounters/{encounter_id}/media/
        """
        encounter_id = kwargs.get('encounter_id')
        encounter = get_object_or_404(Encounter, id=encounter_id)
        
        # RBAC check
        if request.user.role == 'Practitioner':
            if encounter.practitioner != request.user:
                raise PermissionDenied("You can only view media from your own encounters.")
        
        queryset = self.get_queryset().filter(encounter=encounter)
        serializer = self.get_serializer(queryset, many=True)
        
        logger.info(
            "media_listed",
            encounter_id=encounter.id,
            user_id=request.user.id,
            count=queryset.count()
        )
        
        return Response(serializer.data)
    
    def destroy(self, request, *args, **kwargs):
        """
        Soft delete media.
        DELETE /api/v1/clinical/media/{id}/
        """
        media = self.get_object()
        
        # RBAC check: Can user delete this media?
        if request.user.role == 'Practitioner':
            if media.encounter.practitioner != request.user:
                logger.warning(
                    "media_delete_denied",
                    user_id=request.user.id,
                    media_id=media.id,
                    reason="not_practitioner"
                )
                raise PermissionDenied("You can only delete media from your own encounters.")
        
        # Soft delete
        media.soft_delete()
        
        logger.info(
            "media_deleted",
            media_id=media.id,
            encounter_id=media.encounter.id,
            user_id=request.user.id
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """
        Download media file (authenticated).
        GET /api/v1/clinical/media/{id}/download/
        """
        media = self.get_object()
        
        # RBAC check
        if request.user.role == 'Practitioner':
            if media.encounter.practitioner != request.user:
                raise PermissionDenied("You can only download media from your own encounters.")
        
        # Serve file
        try:
            response = FileResponse(
                media.file.open('rb'),
                content_type='image/jpeg'  # Could detect from file
            )
            response['Content-Disposition'] = f'inline; filename="{media.file.name.split("/")[-1]}"'
            
            logger.info(
                "media_downloaded",
                media_id=media.id,
                user_id=request.user.id
            )
            
            return response
        except FileNotFoundError:
            logger.error(
                "media_file_not_found",
                media_id=media.id,
                file_path=media.file.name
            )
            raise Http404("Media file not found on disk.")
