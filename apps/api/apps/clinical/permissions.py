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
    - Superuser
    - Users in 'ClinicalOps' group
    - Users in 'Practitioner' group
    
    Denies:
    - Marketing users (even if staff)
    - Reception users (unless also in ClinicalOps)
    - Unauthenticated users
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check user groups
        user_groups = set(request.user.groups.values_list('name', flat=True))
        
        # Explicitly deny Marketing (even if staff/superuser)
        if 'Marketing' in user_groups:
            return False
        
        # Superuser always have access (unless Marketing)
        if request.user.is_superuser:
            return True
        
        allowed_groups = {'ClinicalOps', 'Practitioner'}
        
        # Allow if user is in any allowed group
        if user_groups & allowed_groups:
            return True
        
        return False


# ============================================================================
# Clinical Core v1: Encounter and Treatment Permissions
# ============================================================================

class TreatmentPermission(permissions.BasePermission):
    """
    Permission for Treatment catalog endpoints.
    
    RBAC Matrix:
    - Admin: Full access (CRUD)
    - ClinicalOps: Full access (CRUD)
    - Practitioner: Read only
    - Reception: Read only
    - Accounting: No access
    - Marketing: No access
    
    Use case:
    - Reception needs to see treatment catalog when booking appointments
    - ClinicalOps needs to create/edit treatments in catalog
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
            # Admin, ClinicalOps, Practitioner, Reception can read
            # Note: ClinicalOps is not in RoleChoices (legacy), using string literal
            allowed_roles = {RoleChoices.ADMIN, 'ClinicalOps', RoleChoices.PRACTITIONER, RoleChoices.RECEPTION}
            return bool(user_roles & allowed_roles)
        
        # Create/Update/Delete (POST, PATCH, PUT, DELETE)
        # Only Admin and ClinicalOps can write
        allowed_roles = {RoleChoices.ADMIN, 'ClinicalOps'}
        return bool(user_roles & allowed_roles)
    
    def has_object_permission(self, request, view, obj):
        """Object-level permission (same as has_permission)"""
        return self.has_permission(request, view)


class EncounterPermission(permissions.BasePermission):
    """
    Permission for Encounter endpoints.
    
    RBAC Matrix:
    - Admin: Full access (CRUD all fields)
    - ClinicalOps: Full access (CRUD all fields including clinical_notes)
    - Practitioner: Full access (CRUD all fields including clinical_notes)
    - Reception: NO ACCESS (business rule: clinical data is restricted)
    - Accounting: Read only (for billing integration)
    - Marketing: NO ACCESS
    
    BUSINESS RULE:
    - clinical_notes, assessment, plan, internal_notes require ClinicalOps/Practitioner/Admin
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
            # Admin, ClinicalOps, Practitioner, Accounting can read
            allowed_roles = {RoleChoices.ADMIN, 'ClinicalOps', RoleChoices.PRACTITIONER, RoleChoices.ACCOUNTING}
            return bool(user_roles & allowed_roles)
        
        # Create/Update/Delete (POST, PATCH, PUT, DELETE)
        # Only Admin, ClinicalOps, Practitioner can write
        allowed_roles = {RoleChoices.ADMIN, 'ClinicalOps', RoleChoices.PRACTITIONER}
        return bool(user_roles & allowed_roles)
    
    def has_object_permission(self, request, view, obj):
        """Object-level permission (same as has_permission)"""
        return self.has_permission(request, view)


class ClinicalChargeProposalPermission(permissions.BasePermission):
    """
    Permission for ClinicalChargeProposal endpoints.
    
    RBAC Matrix:
    - Admin: Full access (read, create-sale action, cancel)
    - ClinicalOps: Full access (read, create-sale action, cancel)
    - Practitioner: Generate proposals (via Encounter endpoint), Read own proposals
    - Reception: Read all proposals, create-sale action (convert to Sale)
    - Accounting: Read only (for billing review)
    - Marketing: NO ACCESS
    
    BUSINESS RULES:
    1. Proposals are generated via POST /encounters/{id}/generate-proposal/ (EncounterPermission controls this)
    2. Reception converts proposals to sales (POST /proposals/{id}/create-sale/)
    3. Accounting can review proposals but cannot convert to sales
    4. Practitioner can only see proposals for their own encounters
    
    Use cases:
    - Practitioner finalizes encounter → generates proposal (via Encounter endpoint)
    - Reception reviews proposal → converts to sale (draft) → collects payment
    - Accounting reviews proposals for billing audits
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
            # Admin, ClinicalOps, Practitioner, Reception, Accounting can read
            allowed_roles = {RoleChoices.ADMIN, 'ClinicalOps', RoleChoices.PRACTITIONER, RoleChoices.RECEPTION, RoleChoices.ACCOUNTING}
            return bool(user_roles & allowed_roles)
        
        # POST to create-sale action
        # Reception, Admin, ClinicalOps can convert proposals to sales
        if view.action == 'create_sale':
            allowed_roles = {RoleChoices.ADMIN, 'ClinicalOps', RoleChoices.RECEPTION}
            return bool(user_roles & allowed_roles)
        
        # Other write operations (cancel, etc.)
        # Only Admin and ClinicalOps
        allowed_roles = {RoleChoices.ADMIN, 'ClinicalOps'}
        return bool(user_roles & allowed_roles)
    
    def has_object_permission(self, request, view, obj):
        """
        Object-level permission for proposals.
        
        BUSINESS RULE: Practitioner can only see their own proposals.
        """
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get user roles
        user_roles = set(
            request.user.user_roles.values_list('role__name', flat=True)
        )
        
        # Admin, ClinicalOps, Reception, Accounting can see all proposals
        if user_roles & {RoleChoices.ADMIN, 'ClinicalOps', RoleChoices.RECEPTION, RoleChoices.ACCOUNTING}:
            return self.has_permission(request, view)
        
        # Practitioner can only see their own proposals
        if RoleChoices.PRACTITIONER in user_roles:
            # Check if user is the practitioner for this proposal
            return obj.practitioner == request.user
        
        return False
