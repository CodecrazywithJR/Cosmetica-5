"""
Authz views for Practitioner.
"""
from rest_framework import viewsets, status
from rest_framework.response import Response
from apps.authz.models import Practitioner
from apps.authz.serializers import (
    PractitionerListSerializer,
    PractitionerDetailSerializer,
    PractitionerWriteSerializer,
)
from apps.authz.permissions import PractitionerPermission


class PractitionerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Practitioner endpoints.
    
    Endpoints:
    - GET /api/v1/practitioners/ - List practitioners (filtered by is_active)
    - GET /api/v1/practitioners/{id}/ - Get practitioner detail
    - POST /api/v1/practitioners/ - Create practitioner (Admin only)
    - PATCH /api/v1/practitioners/{id}/ - Update practitioner (Admin only)
    
    Query parameters:
    - ?include_inactive=true - Include inactive practitioners (default: false)
    - ?role_type=practitioner|assistant|clinical_manager - Filter by role
    - ?q=search_term - Search by display_name
    
    RBAC:
    - Reception: Read-only (view active practitioners for appointment booking)
    - ClinicalOps: Read-only (view practitioners for encounter assignment)
    - Practitioner: Read-only (view colleagues)
    - Admin: Full CRUD
    """
    permission_classes = [PractitionerPermission]
    
    def get_queryset(self):
        """Filter by is_active, role_type, and search."""
        queryset = Practitioner.objects.select_related('user').all()
        
        # Filter by is_active (default: only active)
        include_inactive = self.request.query_params.get('include_inactive', 'false').lower() == 'true'
        if not include_inactive:
            queryset = queryset.filter(is_active=True)
        
        # Filter by role_type
        role_type = self.request.query_params.get('role_type')
        if role_type:
            queryset = queryset.filter(role_type=role_type)
        
        # Search by display_name
        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(display_name__icontains=q)
        
        return queryset.order_by('display_name')
    
    def get_serializer_class(self):
        """Use different serializers for list/detail/write."""
        if self.action == 'list':
            return PractitionerListSerializer
        elif self.action == 'retrieve':
            return PractitionerDetailSerializer
        else:  # create, update, partial_update
            return PractitionerWriteSerializer
