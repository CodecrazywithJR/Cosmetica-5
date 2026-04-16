"""
DRF Permission classes for sales module RBAC.

Partial Refund Permissions (Layer 3 C):
- Reception: CAN create partial refunds
- ClinicalOps: CAN create partial refunds
- Marketing: CANNOT create partial refunds
- Superuser: Full access
"""
from rest_framework import permissions
from apps.authz.models import RoleChoices

class IsReceptionOrClinicalOpsOrAdmin(permissions.BasePermission):
    """
    Allow access to users with Reception, Practitioner, or Admin role.

    Used for partial refund endpoints.
    Replaces former Reception+ClinicalOps group check.
    Marketing is explicitly blocked from creating refunds.
    """

    message = 'Access to refund operations requires Reception or Practitioner role, or admin privileges.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        user_roles = set(request.user.user_roles.values_list('role__name', flat=True))
        return bool(user_roles & {RoleChoices.ADMIN, RoleChoices.RECEPTION, RoleChoices.PRACTITIONER})


class SalePermission(permissions.BasePermission):
    """
    Permission for Sale and SaleLine endpoints.

    RBAC Matrix:
    - Admin: Full access (read, create, update)
    - Reception: Full access (read, create, update)
    - Accounting: Read only
    - Practitioner: NO ACCESS
    - Marketing: NO ACCESS
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        user_roles = set(
            request.user.user_roles.values_list('role__name', flat=True)
        )

        # Practitioner and Marketing have NO access
        if user_roles & {RoleChoices.PRACTITIONER, RoleChoices.MARKETING}:
            return False

        # Safe methods (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            # Admin, Reception, Accounting can read
            allowed_roles = {RoleChoices.ADMIN, RoleChoices.RECEPTION, RoleChoices.ACCOUNTING}
            return bool(user_roles & allowed_roles)

        # Create/Update (POST, PATCH, PUT)
        # Admin and Reception can write
        allowed_roles = {RoleChoices.ADMIN, RoleChoices.RECEPTION}
        return bool(user_roles & allowed_roles)
