"""
DRF Permission classes for sales module RBAC.

Partial Refund Permissions (Layer 3 C):
- Reception: CAN create partial refunds
- ClinicalOps: CAN create partial refunds
- Marketing: CANNOT create partial refunds
- Superuser: Full access
"""
from rest_framework import permissions


class IsReceptionOrClinicalOpsOrAdmin(permissions.BasePermission):
    """
    Allow access to users in Reception or ClinicalOps groups, or superusers.
    
    Used for partial refund endpoints.
    Marketing is explicitly blocked from creating refunds.
    """
    
    message = 'Access to refund operations requires Reception or ClinicalOps role, or admin privileges.'
    
    def has_permission(self, request, view):
        """Check if user is superuser or in allowed groups."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers have full access
        if request.user.is_superuser:
            return True
        
        # Check if user is in Reception or ClinicalOps group
        allowed_groups = ['Reception', 'ClinicalOps']
        return request.user.groups.filter(name__in=allowed_groups).exists()
