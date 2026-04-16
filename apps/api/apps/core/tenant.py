"""
Tenant context resolution — System Plane / Business Plane helpers.

Architecture
────────────
SUPERUSER
  - legal_entity is NULL
  - must select an active LegalEntity context before accessing business modules
  - frontend sends: X-Legal-Entity-ID header on every business request

NORMAL USER
  - legal_entity is NOT NULL (enforced at DB level)
  - tenant context comes from request.user.legal_entity automatically

Public API
──────────
    entity = get_active_legal_entity(request)

Returns the resolved LegalEntity instance.
Raises PermissionDenied when tenant context cannot be resolved.

Mixin
─────
    class MyView(TenantQuerySetMixin, viewsets.ModelViewSet):
        def get_queryset(self):
            entity = self.get_tenant()          # raises if missing
            return MyModel.objects.filter(legal_entity=entity)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rest_framework.exceptions import PermissionDenied

if TYPE_CHECKING:
    from rest_framework.request import Request
    from apps.legal.models import LegalEntity

logger = logging.getLogger(__name__)

# Request header the frontend sends when impersonating a tenant context
TENANT_HEADER = "HTTP_X_LEGAL_ENTITY_ID"
# DRF normalises headers to kebab-case for META lookups:
TENANT_HEADER_META = "HTTP_X_LEGAL_ENTITY_ID"


# ──────────────────────────────────────────────────────────────────────────────
# Core function
# ──────────────────────────────────────────────────────────────────────────────

def get_active_legal_entity(request: "Request") -> "LegalEntity":
    """
    Resolve the active LegalEntity for the current request.

    Header rules
    ────────────
    • Superusers: X-Legal-Entity-ID is MANDATORY.
      - Missing/malformed → HTTP 400 (ValidationError)
      - Unknown/inactive  → HTTP 403 (PermissionDenied)

    • Normal users: X-Legal-Entity-ID is OPTIONAL.
      - If absent  → tenant derived from user.legal_entity (always set).
      - If present → validated against user.legal_entity_id (must match).
      - Mismatch   → HTTP 403 (PermissionDenied)

    In both cases, after this function returns, the caller is guaranteed a
    non-None LegalEntity — tenant=None can never reach ORM queries issued
    within an authenticated HTTP request.

    Raises
    ──────
    ValidationError  — header missing for superuser or malformed (HTTP 400).
    PermissionDenied — entity invalid or user not authorised (HTTP 403).
    """
    from rest_framework.exceptions import ValidationError

    user = request.user

    if not user or not user.is_authenticated:
        raise PermissionDenied("Authentication required.")

    # ── Read header ────────────────────────────────────────────────────
    raw_id = (
        request.META.get(TENANT_HEADER_META)
        or request.META.get("HTTP_X_LEGAL_ENTITY_ID")
    )

    # ── No header supplied ─────────────────────────────────────────────
    if not raw_id:
        if user.is_superuser:
            raise ValidationError(
                {"X-Legal-Entity-ID": "Superusers must supply this header on every business request."}
            )
        # Normal user — legal_entity is guaranteed non-null at DB level.
        entity = getattr(user, "legal_entity", None)
        if entity is None:
            logger.error(
                "User %s has no legal_entity despite not being a superuser.",
                user.pk,
            )
            raise PermissionDenied(
                "Your account is not associated with a legal entity. "
                "Contact an administrator."
            )
        return entity

    # ── Header supplied — parse and validate for all users ────────────
    import uuid as _uuid
    try:
        entity_id = _uuid.UUID(str(raw_id).strip())
    except (ValueError, AttributeError):
        raise ValidationError(
            {"X-Legal-Entity-ID": f"'{raw_id}' is not a valid UUID."}
        )

    from apps.legal.models import LegalEntity  # local import avoids circular
    try:
        entity = LegalEntity.objects.get(id=entity_id, is_active=True)
    except LegalEntity.DoesNotExist:
        raise PermissionDenied(
            f"Legal entity '{entity_id}' does not exist or is inactive."
        )

    # Normal users are bound to exactly one tenant.
    if not user.is_superuser and user.legal_entity_id != entity.id:
        raise PermissionDenied(
            "You do not have access to this legal entity."
        )

    return entity


# ──────────────────────────────────────────────────────────────────────────────
# Convenience mixin for ViewSets / APIViews
# ──────────────────────────────────────────────────────────────────────────────

class TenantQuerySetMixin:
    """
    Mixin that resolves and caches the active LegalEntity for the request.

    Also sets the thread-local tenant context so that TenantManager
    auto-filters ORM querysets.  This is essential for JWT-authenticated
    requests where the user is not yet available at middleware time.

    Usage
    ─────
        class PatientViewSet(TenantQuerySetMixin, viewsets.ModelViewSet):
            def get_queryset(self):
                entity = self.get_tenant()
                return Patient.objects.filter(legal_entity=entity)

    The resolved entity is cached on the request object under
    ``_active_legal_entity`` so it is resolved only once per request cycle
    even if ``get_tenant()`` is called multiple times.
    """

    def initial(self, request, *args, **kwargs):
        """
        After DRF authenticates the user, resolve tenant and push to
        thread-local so TenantManager can auto-filter.

        Raises ValidationError (400) if the X-Legal-Entity-ID header is
        absent on an authenticated request.  Public/AllowAny views are
        skipped automatically because their users are unauthenticated.
        """
        super().initial(request, *args, **kwargs)  # type: ignore[misc]

        from apps.core.tenant_context import get_current_tenant, set_current_tenant

        # If middleware already resolved (session-auth), skip.
        if get_current_tenant() is not None:
            return

        if not request.user or not request.user.is_authenticated:
            # AllowAny / public endpoints — no tenant needed.
            return

        # Resolve tenant — raises ValidationError (400) or PermissionDenied
        # (403) on failure; let DRF propagate the response naturally.
        entity = get_active_legal_entity(request)
        request.tenant = entity
        request._active_legal_entity = entity
        set_current_tenant(entity)

    def get_tenant(self) -> "LegalEntity":
        request = self.request  # type: ignore[attr-defined]
        cached = getattr(request, "_active_legal_entity", None)
        if cached is not None:
            return cached
        entity = get_active_legal_entity(request)
        request._active_legal_entity = entity

        # Also push to thread-local
        from apps.core.tenant_context import set_current_tenant
        set_current_tenant(entity)

        return entity
