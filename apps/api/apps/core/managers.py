"""
TenantManager — automatic tenant filtering at ORM level.

Every model that uses ``TenantManager`` as its default manager will have
its querysets automatically filtered by the current thread-local tenant.

When no tenant is set (management commands, migrations, superuser
system-level queries), querysets are returned unfiltered.
"""
from __future__ import annotations

from django.db import models

from apps.core.tenant_context import get_current_tenant


class TenantQuerySet(models.QuerySet):
    """
    QuerySet with tenant-aware helpers.

    The automatic filtering happens in TenantManager.get_queryset(), not
    here.  This class exists so custom QuerySet methods (e.g.
    ``.active()``) can be chained on top of the pre-filtered base.
    """
    pass


class TenantManager(models.Manager):
    """
    Default manager that auto-filters by the active tenant.

    Behaviour:
    ──────────
    • ``get_current_tenant()`` returns a LegalEntity → filter applied.
    • ``get_current_tenant()`` returns None         → no filter (full table).

    This is safe because:
    • Normal users: TenantMiddleware / TenantQuerySetMixin always sets the
      tenant from ``user.legal_entity``.
    • Superusers: tenant is set when ``X-Legal-Entity-ID`` header is
      present; otherwise None (superuser sees all — correct for
      system-plane operations).
    • Management commands / migrations: no tenant set → full table.

    An ``unfiltered`` manager is available on TenantModel for the rare
    cases where code explicitly needs cross-tenant access.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = get_current_tenant()
        if tenant is not None:
            return qs.filter(legal_entity=tenant)
        return qs
