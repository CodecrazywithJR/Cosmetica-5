"""
Proposal permissions — moved from apps.clinical.permissions.

Structural refactor: ClinicalChargeProposalPermission → ProposalPermission.
No behavioral changes.
"""
from rest_framework import permissions
from apps.authz.models import RoleChoices


class ProposalPermission(permissions.BasePermission):
    """
    Permission for Proposal endpoints.

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
            # Admin, Practitioner, Reception, Accounting can read
            allowed_roles = {RoleChoices.ADMIN, RoleChoices.PRACTITIONER, RoleChoices.RECEPTION, RoleChoices.ACCOUNTING}
            return bool(user_roles & allowed_roles)

        # POST to create-sale action
        # Reception, Admin, Practitioner can convert proposals to sales
        if view.action == 'create_sale':
            allowed_roles = {RoleChoices.ADMIN, RoleChoices.PRACTITIONER, RoleChoices.RECEPTION}
            return bool(user_roles & allowed_roles)

        # State-machine transitions (send, accept, cancel)
        # Admin, Practitioner, Reception can transition proposals
        if view.action in ('send_proposal', 'accept_proposal', 'cancel_proposal'):
            allowed_roles = {RoleChoices.ADMIN, RoleChoices.RECEPTION, RoleChoices.PRACTITIONER}
            return bool(user_roles & allowed_roles)

        # Other write operations
        # Only Admin and Practitioner
        allowed_roles = {RoleChoices.ADMIN, RoleChoices.PRACTITIONER}
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

        # Admin, Practitioner, Reception, Accounting can see all proposals
        if user_roles & {RoleChoices.ADMIN, RoleChoices.PRACTITIONER, RoleChoices.RECEPTION, RoleChoices.ACCOUNTING}:
            return self.has_permission(request, view)

        # Practitioner can only see their own proposals
        if RoleChoices.PRACTITIONER in user_roles:
            # Check if user is the practitioner for this proposal
            return obj.practitioner == request.user

        return False


# Backward-compatible alias (will be removed in a future cleanup)
ClinicalChargeProposalPermission = ProposalPermission
