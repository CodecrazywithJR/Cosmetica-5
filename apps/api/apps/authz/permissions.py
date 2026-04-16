"""
Authz permissions for Practitioner and User Administration endpoints.
"""
from rest_framework import permissions
from apps.authz.models import RoleChoices


class IsAdmin(permissions.BasePermission):
    """
    Permission class that only allows Admin role users or superusers.
    
    Used for user administration endpoints.
    
    Decision (see PROJECT_DECISIONS.md Section 21):
    - Django superusers (is_superuser=True) have full access
    - Users with 'admin' or 'ADMIN' role have full access
    - Case-insensitive role comparison to handle data inconsistencies
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers bypass all checks (Django convention)
        if request.user.is_superuser:
            return True
        
        # Check if user has admin role (case-insensitive)
        user_roles = {
            role.upper() for role in 
            request.user.user_roles.values_list('role__name', flat=True)
        }
        
        # Support both 'admin' and 'ADMIN' in database
        return 'ADMIN' in user_roles


class PractitionerPermission(permissions.BasePermission):
    """
    Permission for Practitioner endpoints based on role.
    
    - Admin: Full CRUD
    - ClinicalOps: Read-only
    - Practitioner: Read-only
    - Reception: Read-only (for appointment booking)
    - Accounting: No access
    - Marketing: No access
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get user roles (lowercase from RoleChoices)
        user_roles = set(
            request.user.user_roles.values_list('role__name', flat=True)
        )
        
        # Marketing and Accounting have NO access
        if user_roles & {RoleChoices.MARKETING, RoleChoices.ACCOUNTING}:
            return False
        
        # Safe methods (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            # Admin, Practitioner, Reception can read
            allowed_roles = {
                RoleChoices.ADMIN,
                RoleChoices.PRACTITIONER,
                RoleChoices.RECEPTION,
            }
            return bool(user_roles & allowed_roles)
        
        # Create/Update/Delete (POST, PATCH, PUT, DELETE)
        # Only Admin can write
        return RoleChoices.ADMIN in user_roles
    
    def has_object_permission(self, request, view, obj):
        """Object-level permission (same as has_permission for practitioners)"""
        return self.has_permission(request, view)
