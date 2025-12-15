"""
Encounter views.
"""
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Encounter
from .serializers import EncounterListSerializer, EncounterSerializer


class EncounterViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Encounter CRUD operations.
    """
    queryset = Encounter.objects.select_related('patient').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['patient__first_name', 'patient__last_name', 'chief_complaint', 'diagnosis']
    ordering_fields = ['scheduled_at', 'created_at']
    ordering = ['-scheduled_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return EncounterListSerializer
        return EncounterSerializer
