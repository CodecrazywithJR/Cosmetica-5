"""
DRF Permission classes for stock module RBAC.

Roles:
- Reception: NO stock access
- Practitioner: Full stock access (read + write)  [replaces ClinicalOps group]
- Marketing: NO stock access
- Admin: Full access
"""
from rest_framework import permissions
from apps.authz.models import RoleChoices


class IsClinicalOpsOrAdmin(permissions.BasePermission):
    """
    Allow access only to users with Practitioner or Admin role.

    Used for all stock endpoints to enforce strict RBAC.
    Replaces the former ClinicalOps-group check.
    """

    message = 'Access to stock module requires Practitioner role or admin privileges.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        user_roles = set(request.user.user_roles.values_list('role__name', flat=True))
        return bool(user_roles & {RoleChoices.ADMIN, RoleChoices.PRACTITIONER})


class IsReception(permissions.BasePermission):
    """
    Check if user has Reception role.

    Used primarily for testing — Reception should NOT have stock access.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        user_roles = set(request.user.user_roles.values_list('role__name', flat=True))
        return RoleChoices.RECEPTION in user_roles


class IsMarketing(permissions.BasePermission):
    """
    Check if user has Marketing role.

    Used primarily for testing — Marketing should NOT have stock access.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        user_roles = set(request.user.user_roles.values_list('role__name', flat=True))
        return RoleChoices.MARKETING in user_roles
