"""Product permissions."""
from rest_framework import permissions
from apps.authz.models import RoleChoices


class ProductPermission(permissions.BasePermission):
    """
    Permission for Product catalog endpoints.

    RBAC Matrix:
    - Admin: Full access (read, write)
    - Practitioner: Full access (read, write)
    - Reception: Read only
    - Accounting: NO ACCESS
    - Marketing: NO ACCESS
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

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
