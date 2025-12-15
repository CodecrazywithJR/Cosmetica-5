"""
Clinical permissions for API endpoints.
Based on API_CONTRACTS.md permission matrix.
"""
from rest_framework import permissions


class PatientPermission(permissions.BasePermission):
    """
    Permission for Patient endpoints based on role.
    
    - Admin: Full access (read, write, soft-delete, see deleted)
    - Practitioner: Read, create, update (no delete, no see deleted)
    - Reception: Read, create, update (no delete, no see deleted)
    - Accounting: Read only (no create, update, delete)
    - Marketing: No access
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get user roles
        user_roles = set(
            request.user.user_roles.values_list('role__name', flat=True)
        )
        
        # Marketing has NO access
        if 'Marketing' in user_roles:
            return False
        
        # Safe methods (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            # Admin, Practitioner, Reception, Accounting can read
            allowed_roles = {'Admin', 'Practitioner', 'Reception', 'Accounting'}
            return bool(user_roles & allowed_roles)
        
        # Create/Update (POST, PATCH, PUT)
        if request.method in ['POST', 'PATCH', 'PUT']:
            # Admin, Practitioner, Reception can write
            allowed_roles = {'Admin', 'Practitioner', 'Reception'}
            return bool(user_roles & allowed_roles)
        
        # Delete (soft-delete)
        if request.method == 'DELETE':
            # Only Admin can delete
            return 'Admin' in user_roles
        
        return False
    
    def has_object_permission(self, request, view, obj):
        """Object-level permission (same as has_permission for patients)"""
        return self.has_permission(request, view)


class GuardianPermission(permissions.BasePermission):
    """
    Permission for PatientGuardian endpoints.
    
    - Admin: Full access
    - Practitioner: Full access
    - Reception: Full access
    - Accounting: No access
    - Marketing: No access
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get user roles
        user_roles = set(
            request.user.user_roles.values_list('role__name', flat=True)
        )
        
        # Marketing and Accounting have NO access
        if user_roles & {'Marketing', 'Accounting'}:
            return False
        
        # Admin, Practitioner, Reception have full access
        allowed_roles = {'Admin', 'Practitioner', 'Reception'}
        return bool(user_roles & allowed_roles)


class AppointmentPermission(permissions.BasePermission):
    """
    Permission for Appointment endpoints based on role.
    
    - Admin: Full access (read, write, delete, see deleted)
    - Practitioner: Read, create, update (no delete, no include_deleted)
    - Reception: Read, create, update (no delete, no include_deleted)
    - Accounting: Read only
    - Marketing: No access
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get user roles
        user_roles = set(
            request.user.user_roles.values_list('role__name', flat=True)
        )
        
        # Marketing has NO access
        if 'Marketing' in user_roles:
            return False
        
        # Safe methods (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            # Admin, Practitioner, Reception, Accounting can read
            allowed_roles = {'Admin', 'Practitioner', 'Reception', 'Accounting'}
            return bool(user_roles & allowed_roles)
        
        # Create/Update (POST, PATCH, PUT)
        if request.method in ['POST', 'PATCH', 'PUT']:
            # Admin, Practitioner, Reception can write
            allowed_roles = {'Admin', 'Practitioner', 'Reception'}
            return bool(user_roles & allowed_roles)
        
        # Delete
        if request.method == 'DELETE':
            # Only Admin can delete
            return 'Admin' in user_roles
        
        return False
    
    def has_object_permission(self, request, view, obj):
        """Object-level permission (same as has_permission for appointments)"""
        return self.has_permission(request, view)
