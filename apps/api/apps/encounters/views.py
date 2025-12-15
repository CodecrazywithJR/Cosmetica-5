"""
Encounter views.

BUSINESS RULE: Encounters are clinical data. Only Admin and Practitioner can access.
Reception is explicitly blocked.
"""
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated
from apps.clinical.permissions import IsClinicalStaff

from .models import Encounter
from .serializers import EncounterListSerializer, EncounterSerializer


class EncounterViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Encounter CRUD operations.
    
    BUSINESS RULE: Only clinical staff (Admin, Practitioner) can access encounters.
    Reception cannot view or edit clinical data.
    """
    queryset = Encounter.objects.select_related('patient').all()
    permission_classes = [IsAuthenticated, IsClinicalStaff]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['patient__first_name', 'patient__last_name', 'chief_complaint', 'diagnosis']
    ordering_fields = ['scheduled_at', 'created_at']
    ordering = ['-scheduled_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return EncounterListSerializer
        return EncounterSerializer
