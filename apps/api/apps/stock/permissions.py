"""
DRF Permission classes for stock module RBAC.

Roles:
- Reception: NO stock access
- ClinicalOps: Full stock access (read + write)
- Marketing: NO stock access
- Superuser: Full access
"""
from rest_framework import permissions


class IsClinicalOpsOrAdmin(permissions.BasePermission):
    """
    Allow access only to users in ClinicalOps group or superusers.
    
    Used for all stock endpoints to enforce strict RBAC.
    """
    
    message = 'Access to stock module requires ClinicalOps role or admin privileges.'
    
    def has_permission(self, request, view):
        """Check if user is superuser or in ClinicalOps group."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers have full access
        if request.user.is_superuser:
            return True
        
        # Check if user is in ClinicalOps group
        return request.user.groups.filter(name='ClinicalOps').exists()


class IsReception(permissions.BasePermission):
    """
    Check if user is in Reception group.
    
    Used primarily for testing - Reception should NOT have stock access.
    """
    
    def has_permission(self, request, view):
        """Check if user is in Reception group."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        return request.user.groups.filter(name='Reception').exists()


class IsMarketing(permissions.BasePermission):
    """
    Check if user is in Marketing group.
    
    Used primarily for testing - Marketing should NOT have stock access.
    """
    
    def has_permission(self, request, view):
        """Check if user is in Marketing group."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        return request.user.groups.filter(name='Marketing').exists()
