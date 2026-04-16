"""
Clinical permissions for API endpoints.
Based on API_CONTRACTS.md permission matrix.

BUSINESS RULE: Reception role cannot access clinical data (diagnoses, notes, clinical photos, encounters).
"""
from rest_framework import permissions
from apps.authz.models import RoleChoices


class IsClinicalStaff(permissions.BasePermission):
    """
    Permission for clinical endpoints (encounters, clinical photos, diagnoses).
    
    BUSINESS RULE: Only Admin and Practitioner can access clinical data.
    Reception is explicitly blocked from clinical endpoints.
    
    - Admin: Full access
    - Practitioner: Full access
    - Reception: NO ACCESS (business rule)
    - Accounting: NO ACCESS
    - Marketing: NO ACCESS
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get user roles
        user_roles = set(
            request.user.user_roles.values_list('role__name', flat=True)
        )
        
        # BUSINESS RULE: Only Admin and Practitioner can access clinical data
        allowed_roles = {RoleChoices.ADMIN, RoleChoices.PRACTITIONER}
        return bool(user_roles & allowed_roles)


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
        if RoleChoices.MARKETING in user_roles:
            return False
        
        # Safe methods (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            # Admin, Practitioner, Reception, Accounting can read
            allowed_roles = {RoleChoices.ADMIN, RoleChoices.PRACTITIONER, RoleChoices.RECEPTION, RoleChoices.ACCOUNTING}
            return bool(user_roles & allowed_roles)
        
        # Create/Update (POST, PATCH, PUT)
        if request.method in ['POST', 'PATCH', 'PUT']:
            # Admin, Practitioner, Reception can write
            allowed_roles = {RoleChoices.ADMIN, RoleChoices.PRACTITIONER, RoleChoices.RECEPTION}
            return bool(user_roles & allowed_roles)
        
        # Delete (soft-delete)
        if request.method == 'DELETE':
            # Only Admin can delete
            return RoleChoices.ADMIN in user_roles
        
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
        if user_roles & {RoleChoices.MARKETING, RoleChoices.ACCOUNTING}:
            return False
        
        # Admin, Practitioner, Reception have full access
        allowed_roles = {RoleChoices.ADMIN, RoleChoices.PRACTITIONER, RoleChoices.RECEPTION}
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
        if RoleChoices.MARKETING in user_roles:
            return False
        
        # Safe methods (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            # Admin, Practitioner, Reception, Accounting can read
            allowed_roles = {RoleChoices.ADMIN, RoleChoices.PRACTITIONER, RoleChoices.RECEPTION, RoleChoices.ACCOUNTING}
            return bool(user_roles & allowed_roles)
        
        # Create/Update (POST, PATCH, PUT)
        if request.method in ['POST', 'PATCH', 'PUT']:
            # Admin, Practitioner, Reception can write
            allowed_roles = {RoleChoices.ADMIN, RoleChoices.PRACTITIONER, RoleChoices.RECEPTION}
            return bool(user_roles & allowed_roles)
        
        # Delete
        if request.method == 'DELETE':
            # Only Admin can delete
            return RoleChoices.ADMIN in user_roles
        
        return False
    
    def has_object_permission(self, request, view, obj):
        """Object-level permission (same as has_permission for appointments)"""
        return self.has_permission(request, view)


class IsClinicalOpsOrAdmin(permissions.BasePermission):
    """
    Permission for elevated clinical operations (patient merge, etc).

    Allows:
    - Admin role
    - Practitioner role  [replaces ClinicalOps + Practitioner group checks]

    Denies:
    - Marketing role (explicit block)
    - Reception role
    - Unauthenticated users
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        user_roles = set(request.user.user_roles.values_list('role__name', flat=True))

        # Explicitly deny Marketing
        if RoleChoices.MARKETING in user_roles:
            return False

        return bool(user_roles & {RoleChoices.ADMIN, RoleChoices.PRACTITIONER})


# ============================================================================
# Clinical Core v1: Encounter and Treatment Permissions
# ============================================================================

class TreatmentPermission(permissions.BasePermission):
    """
    Permission for Treatment catalog endpoints.
    
    RBAC Matrix:
    - Admin: Full access (CRUD)
    - Practitioner: Full access (CRUD)
    - Reception: Read only
    - Accounting: No access
    - Marketing: No access
    
    Use case:
    - Reception needs to see treatment catalog when booking appointments
    - Practitioner can create/edit treatments in catalog
    - Practitioner can view treatments for encounter documentation
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get user roles
        user_roles = set(
            request.user.user_roles.values_list('role__name', flat=True)
        )
        
        # Accounting and Marketing have NO access
        if user_roles & {RoleChoices.ACCOUNTING, RoleChoices.MARKETING}:
            return False
        
        # Safe methods (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            # Admin, Practitioner, Reception can read
            allowed_roles = {RoleChoices.ADMIN, RoleChoices.PRACTITIONER, RoleChoices.RECEPTION}
            return bool(user_roles & allowed_roles)
        
        # Create/Update/Delete (POST, PATCH, PUT, DELETE)
        # Only Admin and Practitioner can write
        allowed_roles = {RoleChoices.ADMIN, RoleChoices.PRACTITIONER}
        return bool(user_roles & allowed_roles)
    
    def has_object_permission(self, request, view, obj):
        """Object-level permission (same as has_permission)"""
        return self.has_permission(request, view)


class EncounterPermission(permissions.BasePermission):
    """
    Permission for Encounter endpoints.
    
    RBAC Matrix:
    - Admin: Full access (CRUD all fields)
    - Practitioner: Full access (CRUD all fields including clinical_notes)
    - Reception: NO ACCESS (business rule: clinical data is restricted)
    - Accounting: Read only (for billing integration)
    - Marketing: NO ACCESS
    
    BUSINESS RULE:
    - clinical_notes, assessment, plan, internal_notes require Practitioner/Admin
    - Reception CANNOT access encounters (clinical data restriction)
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get user roles
        user_roles = set(
            request.user.user_roles.values_list('role__name', flat=True)
        )
        
        # Reception, Marketing have NO access (business rule)
        if user_roles & {RoleChoices.RECEPTION, RoleChoices.MARKETING}:
            return False
        
        # Safe methods (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            # Admin, Practitioner, Accounting can read
            allowed_roles = {RoleChoices.ADMIN, RoleChoices.PRACTITIONER, RoleChoices.ACCOUNTING}
            return bool(user_roles & allowed_roles)
        
        # Create/Update/Delete (POST, PATCH, PUT, DELETE)
        # Only Admin and Practitioner can write
        allowed_roles = {RoleChoices.ADMIN, RoleChoices.PRACTITIONER}
        return bool(user_roles & allowed_roles)
    
    def has_object_permission(self, request, view, obj):
        """Object-level permission (same as has_permission)"""
        return self.has_permission(request, view)


class ConsentPermission(permissions.BasePermission):
    """
    Permission for Patient Consent endpoints (consent documents).
    
    RBAC Matrix (per PATIENT_CONSENT_DOCUMENTS.md):
    - Admin: Full access (CRUD consents + documents)
    - Practitioner: Full access (administrative consent documents)
    - Reception: Full access (administrative consent documents)
    - Accounting: NO ACCESS
    - Marketing: NO ACCESS
    
    BUSINESS RULE:
    - Reception CAN manage consent documents (administrative)
    - Reception CANNOT manage encounter documents (clinical)
    - This permission is patient-centric, not encounter-centric
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get user roles
        user_roles = set(
            request.user.user_roles.values_list('role__name', flat=True)
        )
        
        # Accounting and Marketing have NO access
        if user_roles & {RoleChoices.ACCOUNTING, RoleChoices.MARKETING}:
            return False
        
        # Admin, Practitioner, Reception have full access
        allowed_roles = {RoleChoices.ADMIN, RoleChoices.PRACTITIONER, RoleChoices.RECEPTION}
        return bool(user_roles & allowed_roles)
    
    def has_object_permission(self, request, view, obj):
        """Object-level permission (same as has_permission for consents)"""
        return self.has_permission(request, view)


# ClinicalChargeProposalPermission moved to apps.proposals.permissions
from apps.proposals.permissions import ProposalPermission as ClinicalChargeProposalPermission  # noqa: F401

