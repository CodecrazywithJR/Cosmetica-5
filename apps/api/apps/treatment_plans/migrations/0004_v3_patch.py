# Generated manually — TreatmentSession v3 patch.
#
# Changes:
#   1. TreatmentPlan: add legal_entity FK (nullable, PROTECT) + index
#   2. TreatmentSession: remove redundant UniqueConstraint ts_unique_appointment
#      (OneToOneField on `appointment` already enforces uniqueness at DB level)
#   3. Backfill legal_entity from sale.legal_entity or practitioner.user.legal_entity

from django.db import migrations, models
import django.db.models.deletion


def backfill_legal_entity(apps, schema_editor):
    """
    Populate TreatmentPlan.legal_entity from related models:
      1st priority: sale.legal_entity  (Sale always has legal_entity NOT NULL)
      2nd priority: practitioner.user.legal_entity
    """
    TreatmentPlan = apps.get_model('treatment_plans', 'TreatmentPlan')

    for plan in TreatmentPlan.objects.filter(legal_entity__isnull=True).select_related(
        'sale', 'practitioner__user',
    ):
        le_id = None

        # Priority 1: from sale
        if plan.sale_id and plan.sale and plan.sale.legal_entity_id:
            le_id = plan.sale.legal_entity_id

        # Priority 2: from practitioner → user
        if not le_id and plan.practitioner_id:
            try:
                le_id = plan.practitioner.user.legal_entity_id
            except Exception:
                pass

        if le_id:
            plan.legal_entity_id = le_id
            plan.save(update_fields=['legal_entity_id'])


class Migration(migrations.Migration):
    dependencies = [
        ("treatment_plans", "0003_treatment_session_v2_patch"),
        ("legal", "0001_create_legal_entity"),
    ]

    operations = [
        # ── 1) Add legal_entity FK to TreatmentPlan ───────────────────
        migrations.AddField(
            model_name="treatmentplan",
            name="legal_entity",
            field=models.ForeignKey(
                blank=True,
                help_text="Owning legal entity for multi-tenant isolation",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="treatment_plans",
                to="legal.legalentity",
            ),
        ),

        # ── 2) Add index on legal_entity ──────────────────────────────
        migrations.AddIndex(
            model_name="treatmentplan",
            index=models.Index(
                fields=["legal_entity"],
                name="idx_tp_legal_entity",
            ),
        ),

        # ── 3) Backfill legal_entity from sale or practitioner ────────
        migrations.RunPython(
            backfill_legal_entity,
            reverse_code=migrations.RunPython.noop,
        ),

        # ── 4) Remove redundant UniqueConstraint on TreatmentSession ──
        #    OneToOneField(appointment) already creates a UNIQUE index.
        migrations.RemoveConstraint(
            model_name="treatmentsession",
            name="ts_unique_appointment",
        ),
    ]
