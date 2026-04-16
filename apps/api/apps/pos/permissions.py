"""POS-specific permissions."""
from rest_framework import permissions
from apps.authz.models import RoleChoices


class IsPOSUser(permissions.BasePermission):
    """
    Permission for POS operations.

    Allows access to users with Admin or Reception role.
    Replaces the former Reception+ClinicalOps group check.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        user_roles = set(request.user.user_roles.values_list('role__name', flat=True))
        return bool(user_roles & {RoleChoices.ADMIN, RoleChoices.RECEPTION})
