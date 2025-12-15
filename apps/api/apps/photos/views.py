"""
Photo views.

BUSINESS RULE: Clinical photos are clinical data. Only Admin and Practitioner can access.
Reception is explicitly blocked.
NOTE: Photos can always be uploaded/saved regardless of consent (business rule).
"""
from rest_framework import filters, parsers, viewsets
from rest_framework.permissions import IsAuthenticated
from apps.clinical.permissions import IsClinicalStaff

from .models import SkinPhoto
from .serializers import SkinPhotoListSerializer, SkinPhotoSerializer


class SkinPhotoViewSet(viewsets.ModelViewSet):
    """
    ViewSet for SkinPhoto CRUD operations.
    Supports multipart file uploads.
    
    BUSINESS RULE: Only clinical staff (Admin, Practitioner) can access clinical photos.
    Reception cannot view or edit clinical photos.
    """
    queryset = SkinPhoto.objects.select_related('patient', 'encounter').all()
    permission_classes = [IsAuthenticated, IsClinicalStaff]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['patient__first_name', 'patient__last_name', 'body_part', 'tags']
    ordering_fields = ['taken_at', 'created_at']
    ordering = ['-taken_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return SkinPhotoListSerializer
        return SkinPhotoSerializer
