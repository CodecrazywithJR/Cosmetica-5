"""
Patient views.
"""
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Patient
from .serializers import PatientListSerializer, PatientSerializer


class PatientViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Patient CRUD operations.
    
    Supports:
    - List (with search and pagination)
    - Create
    - Retrieve
    - Update
    - Partial Update
    - Delete (soft delete - sets is_active=False)
    
    Search fields: first_name, last_name, phone, email
    Ordering: -created_at (newest first)
    """
    queryset = Patient.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'phone', 'email']
    ordering_fields = ['created_at', 'last_name', 'first_name']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Use lightweight serializer for list view."""
        if self.action == 'list':
            return PatientListSerializer
        return PatientSerializer
    
    def perform_destroy(self, instance):
        """Soft delete - set is_active to False instead of deleting."""
        instance.is_active = False
        instance.save()
