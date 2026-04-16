"""
Thread-local tenant context for ORM-level tenant isolation.

Stores the active LegalEntity for the current request thread so that
TenantManager can auto-filter querysets without requiring an explicit
``request`` object.

Lifecycle (managed by TenantMiddleware):
    1. Middleware resolves tenant → set_current_tenant(entity)
    2. All ORM queries via TenantManager see the tenant
    3. Response completes → clear_current_tenant()

For DRF/JWT where the user is resolved after middleware:
    TenantQuerySetMixin.initial() re-sets the thread-local after DRF
    authentication.

Usage in custom code (rare — prefer TenantManager auto-filtering):
    from apps.core.tenant_context import get_current_tenant
    tenant = get_current_tenant()
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from apps.legal.models import LegalEntity

_thread_local = threading.local()


def set_current_tenant(tenant: Optional["LegalEntity"]) -> None:
    """Store the active tenant for the current thread."""
    _thread_local.tenant = tenant


def get_current_tenant() -> Optional["LegalEntity"]:
    """
    Return the active tenant for the current thread, or None.

    None means "no tenant context" — TenantManager will return
    unfiltered results (safe for superuser system-level operations,
    management commands, and migrations).
    """
    return getattr(_thread_local, "tenant", None)


def clear_current_tenant() -> None:
    """Remove tenant context from the current thread."""
    _thread_local.tenant = None
