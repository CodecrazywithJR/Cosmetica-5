"""
Photo views.
"""
from rest_framework import filters, parsers, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import SkinPhoto
from .serializers import SkinPhotoListSerializer, SkinPhotoSerializer


class SkinPhotoViewSet(viewsets.ModelViewSet):
    """
    ViewSet for SkinPhoto CRUD operations.
    Supports multipart file uploads.
    """
    queryset = SkinPhoto.objects.select_related('patient', 'encounter').all()
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['patient__first_name', 'patient__last_name', 'body_part', 'tags']
    ordering_fields = ['taken_at', 'created_at']
    ordering = ['-taken_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return SkinPhotoListSerializer
        return SkinPhotoSerializer
