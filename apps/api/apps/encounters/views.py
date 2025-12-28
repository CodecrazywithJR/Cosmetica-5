"""
Encounter views - DEPRECATED

⚠️ THIS ENDPOINT IS DEPRECATED AND REMOVED ⚠️

All operations return HTTP 410 Gone.
Use /api/v1/clinical/encounters/ instead.

This file is kept only for explicit deprecation responses.
"""
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated


class EncounterViewSet(viewsets.ViewSet):
    """
    DEPRECATED ViewSet - Returns 410 Gone for all operations.
    
    This endpoint has been removed. Use /api/v1/clinical/encounters/ instead.
    """
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """GET /api/encounters/ - DEPRECATED"""
        return Response(
            {
                'error': 'ENDPOINT_DEPRECATED',
                'message': 'This endpoint has been removed. Use /api/v1/clinical/encounters/ instead.',
                'deprecated_endpoint': '/api/encounters/',
                'replacement_endpoint': '/api/v1/clinical/encounters/',
                'documentation': 'https://docs.example.com/api/v1/clinical/encounters/'
            },
            status=status.HTTP_410_GONE
        )
    
    def create(self, request):
        """POST /api/encounters/ - DEPRECATED"""
        return Response(
            {
                'error': 'ENDPOINT_DEPRECATED',
                'message': 'This endpoint has been removed. Use /api/v1/clinical/encounters/ instead.',
                'deprecated_endpoint': '/api/encounters/',
                'replacement_endpoint': '/api/v1/clinical/encounters/',
                'documentation': 'https://docs.example.com/api/v1/clinical/encounters/'
            },
            status=status.HTTP_410_GONE
        )
    
    def retrieve(self, request, pk=None):
        """GET /api/encounters/{id}/ - DEPRECATED"""
        return Response(
            {
                'error': 'ENDPOINT_DEPRECATED',
                'message': 'This endpoint has been removed. Use /api/v1/clinical/encounters/ instead.',
                'deprecated_endpoint': f'/api/encounters/{pk}/',
                'replacement_endpoint': f'/api/v1/clinical/encounters/{pk}/',
                'documentation': 'https://docs.example.com/api/v1/clinical/encounters/'
            },
            status=status.HTTP_410_GONE
        )
    
    def update(self, request, pk=None):
        """PUT /api/encounters/{id}/ - DEPRECATED"""
        return Response(
            {
                'error': 'ENDPOINT_DEPRECATED',
                'message': 'This endpoint has been removed. Use /api/v1/clinical/encounters/ instead.',
                'deprecated_endpoint': f'/api/encounters/{pk}/',
                'replacement_endpoint': f'/api/v1/clinical/encounters/{pk}/',
                'documentation': 'https://docs.example.com/api/v1/clinical/encounters/'
            },
            status=status.HTTP_410_GONE
        )
    
    def partial_update(self, request, pk=None):
        """PATCH /api/encounters/{id}/ - DEPRECATED"""
        return Response(
            {
                'error': 'ENDPOINT_DEPRECATED',
                'message': 'This endpoint has been removed. Use /api/v1/clinical/encounters/ instead.',
                'deprecated_endpoint': f'/api/encounters/{pk}/',
                'replacement_endpoint': f'/api/v1/clinical/encounters/{pk}/',
                'documentation': 'https://docs.example.com/api/v1/clinical/encounters/'
            },
            status=status.HTTP_410_GONE
        )
    
    def destroy(self, request, pk=None):
        """DELETE /api/encounters/{id}/ - DEPRECATED"""
        return Response(
            {
                'error': 'ENDPOINT_DEPRECATED',
                'message': 'This endpoint has been removed. Use /api/v1/clinical/encounters/ instead.',
                'deprecated_endpoint': f'/api/encounters/{pk}/',
                'replacement_endpoint': f'/api/v1/clinical/encounters/{pk}/',
                'documentation': 'https://docs.example.com/api/v1/clinical/encounters/'
            },
            status=status.HTTP_410_GONE
        )
