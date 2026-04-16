"""
Tenant-scope ClinicLocation: add legal_entity FK, backfill, enforce NOT NULL.

Three-phase migration:
  1. AddField  – nullable legal_entity FK (safe, zero downtime)
  2. RunPython – backfill every existing row with the first LegalEntity
  3. AlterField – drop NULL, enforce FK constraint
"""
import django.db.models.deletion
from django.db import migrations, models


def backfill_legal_entity(apps, schema_editor):
    """Assign every ClinicLocation to the first (and usually only) LegalEntity."""
    LegalEntity = apps.get_model("legal", "LegalEntity")
    ClinicLocation = apps.get_model("core", "ClinicLocation")

    default_le = LegalEntity.objects.order_by("created_at").first()
    if default_le is None:
        # No LegalEntity yet → nothing to backfill (table should be empty)
        if ClinicLocation.objects.exists():
            raise RuntimeError(
                "Cannot backfill clinic_location.legal_entity_id: "
                "no LegalEntity rows exist. Create one first."
            )
        return

    updated = ClinicLocation.objects.filter(legal_entity__isnull=True).update(
        legal_entity=default_le,
    )
    if updated:
        print(f"\n  → Backfilled {updated} ClinicLocation row(s) with "
              f"LegalEntity '{default_le}' (id={default_le.pk})")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("legal", "0001_create_legal_entity"),  # LegalEntity must exist
    ]

    operations = [
        # Phase 1 — add nullable FK
        migrations.AddField(
            model_name="cliniclocation",
            name="legal_entity",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="clinics",
                to="legal.legalentity",
                help_text="Owning legal entity (tenant isolation).",
            ),
        ),
        # Phase 2 — backfill
        migrations.RunPython(
            backfill_legal_entity,
            reverse_code=migrations.RunPython.noop,
        ),
        # Phase 3 — enforce NOT NULL
        migrations.AlterField(
            model_name="cliniclocation",
            name="legal_entity",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="clinics",
                to="legal.legalentity",
                help_text="Owning legal entity (tenant isolation).",
            ),
        ),
    ]
