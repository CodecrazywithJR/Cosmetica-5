"""
Core middleware — Legal Entity enforcement & tenant context.

TenantMiddleware
━━━━━━━━━━━━━━━━
Resolves the active LegalEntity for each request and stores it in:
- ``request.tenant``  (per-request)
- thread-local via ``set_current_tenant()``  (for TenantManager ORM filtering)

For session-auth users the tenant is resolved immediately.
For JWT-auth users ``request.user`` is Anonymous at middleware time;
the TenantQuerySetMixin.initial() re-sets the thread-local after DRF
authenticates the user.

InactiveLegalEntityMiddleware
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Blocks ALL write operations (POST/PUT/PATCH/DELETE) when the authenticated
user's LegalEntity.is_active == False.

Applies globally — no per-view patching required.

Exempt:
- Safe methods (GET, HEAD, OPTIONS)
- Unauthenticated requests (handled by DRF auth layer)
- Superusers (is_superuser=True)
- Django admin paths (/admin/)
- Users without a legal_entity (legacy data — enforced at model level on
  new saves, not by this middleware)
"""
import logging
import uuid as _uuid

from django.http import JsonResponse

from apps.core.tenant_context import set_current_tenant, clear_current_tenant

logger = logging.getLogger(__name__)

SAFE_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS'})

# Paths where the middleware will NOT apply the freeze.
# Django admin uses HTML, not JSON; system-plane is superuser-only anyway
# but we short-circuit on is_superuser first.
EXEMPT_PATH_PREFIXES = (
    '/admin/',
)


class InactiveLegalEntityMiddleware:
    """
    Centralized freeze when LegalEntity.is_active == False.

    Runs AFTER AuthenticationMiddleware, which populates request.user
    for session-authenticated requests.  For JWT requests the user is
    resolved later by DRF, so request.user is AnonymousUser at this
    stage — the middleware simply lets those through, and the DRF view
    layer will authenticate and then enforce via the same user model.

    Write operations → 403 if LE inactive (non-superuser).
    Read operations  → always allowed.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Safe methods → pass through
        if request.method in SAFE_METHODS:
            return self.get_response(request)

        # 2. Exempt paths
        if any(request.path.startswith(p) for p in EXEMPT_PATH_PREFIXES):
            return self.get_response(request)

        # 3. Use request.user set by AuthenticationMiddleware
        user = getattr(request, 'user', None)

        if user is None or not user.is_authenticated:
            # Not authenticated — let DRF handle 401
            return self.get_response(request)

        # 4. Superusers bypass everything
        if user.is_superuser:
            return self.get_response(request)

        # 5. Check legal entity
        le_id = getattr(user, 'legal_entity_id', None)
        if le_id is None:
            # Legacy user without LE — middleware does not block.
            # Model-level validation prevents CREATING such users going
            # forward.
            return self.get_response(request)

        # Lazy-load the related LegalEntity (single query, cached)
        le = user.legal_entity
        if le is not None and not le.is_active:
            logger.warning(
                'Write blocked: inactive legal entity',
                extra={
                    'event': 'le_freeze_block',
                    'user_id': str(user.pk),
                    'legal_entity_id': str(le_id),
                    'method': request.method,
                    'path': request.path,
                },
            )
            return JsonResponse(
                {
                    'detail': (
                        'Your legal entity is inactive. '
                        'Write operations are not permitted.'
                    ),
                },
                status=403,
            )

        return self.get_response(request)


# ============================================================================
# TenantMiddleware — resolve active LegalEntity per request
# ============================================================================

TENANT_HEADER_KEY = "HTTP_X_LEGAL_ENTITY_ID"

# Paths where tenant resolution is skipped entirely (system-plane, admin).
TENANT_EXEMPT_PREFIXES = (
    '/admin/',
    '/api/v1/system/',
    '/api/v1/auth/',
    '/health',
)


class TenantMiddleware:
    """
    Resolve the active tenant once per request and store it in:

    * ``request.tenant``            — per-request attribute
    * thread-local (tenant_context) — for TenantManager ORM filtering

    Session-auth users are resolved here.
    JWT users are resolved later by ``TenantQuerySetMixin.initial()``
    because DRF performs authentication inside the view layer.

    On response (or exception) the thread-local is always cleared.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = self._try_resolve(request)
        request.tenant = tenant
        set_current_tenant(tenant)

        try:
            response = self.get_response(request)
        finally:
            clear_current_tenant()

        return response

    # ------------------------------------------------------------------

    def _try_resolve(self, request):
        """
        Best-effort tenant resolution.

        Returns LegalEntity instance or None.
        Does NOT raise — views/permissions handle auth errors.
        """
        # Skip exempt paths (system-plane, admin, auth)
        if any(request.path.startswith(p) for p in TENANT_EXEMPT_PREFIXES):
            return None

        user = getattr(request, 'user', None)
        if not user or not getattr(user, 'is_authenticated', False):
            return None

        if user.is_superuser:
            return self._from_header(request)

        return getattr(user, 'legal_entity', None)

    @staticmethod
    def _from_header(request):
        """Parse X-Legal-Entity-ID header. Returns entity or None."""
        raw = request.META.get(TENANT_HEADER_KEY)
        if not raw:
            return None

        try:
            entity_id = _uuid.UUID(str(raw).strip())
        except (ValueError, AttributeError):
            return None

        from apps.legal.models import LegalEntity  # local import

        try:
            return LegalEntity.objects.get(id=entity_id, is_active=True)
        except LegalEntity.DoesNotExist:
            return None