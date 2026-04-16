"""
TenantModel — abstract base for all business-plane models.

Provides:
  1. ``legal_entity`` ForeignKey to LegalEntity (nullable for migration safety)
  2. ``objects`` = TenantManager  → auto-filtered by current tenant
  3. ``unfiltered`` = plain Manager → full table (admin, data migrations, etc.)

Usage:
    from apps.core.tenant_model import TenantModel

    class Patient(TenantModel):
        first_name = models.CharField(...)
        ...

        class Meta(TenantModel.Meta):
            db_table = 'patient'

For models that ALREADY have a ``legal_entity`` FK (e.g. Sale, TreatmentPlan):
    Don't inherit TenantModel — just add the managers directly:

        from apps.core.managers import TenantManager
        class Sale(models.Model):
            legal_entity = ...          # existing field
            objects = TenantManager()
            unfiltered = models.Manager()
"""
from __future__ import annotations

from django.db import models

from apps.core.managers import TenantManager


class TenantModel(models.Model):
    """
    Abstract base model for tenant-scoped (business-plane) data.

    Sets ``legal_entity`` as nullable to allow safe migration rollout.
    Application-level logic (middleware, mixin, ``save()`` override)
    should ensure it is always populated for new records.
    """

    legal_entity = models.ForeignKey(
        'legal.LegalEntity',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_index=True,
        related_name='%(app_label)s_%(class)s_set',
        help_text='Owning legal entity (tenant isolation).',
    )

    # Default manager — auto-filtered by current tenant
    objects = TenantManager()

    # Escape hatch — returns ALL rows regardless of tenant
    unfiltered = models.Manager()

    def save(self, *args, **kwargs):
        # Auto-populate legal_entity from the active thread-local tenant when
        # not explicitly provided.  This covers ORM .create() calls made inside
        # HTTP requests and Celery tasks that called set_current_tenant().
        if self.legal_entity_id is None:
            from apps.core.tenant_context import get_current_tenant
            tenant = get_current_tenant()
            if tenant is not None:
                self.legal_entity = tenant
        super().save(*args, **kwargs)

    class Meta:
        abstract = True
