"""POS-specific permissions."""
from rest_framework import permissions


class IsPOSUser(permissions.BasePermission):
    """
    Permission for POS operations.
    
    Allows access only to users in 'Reception' or 'ClinicalOps' groups,
    as these are the roles that handle POS operations.
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user belongs to Reception or ClinicalOps groups
        user_groups = request.user.groups.values_list('name', flat=True)
        allowed_groups = {'Reception', 'ClinicalOps'}
        
        return bool(set(user_groups) & allowed_groups) or request.user.is_staff
