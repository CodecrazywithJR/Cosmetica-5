# Generated manually — TreatmentSession v2 patch.
#
# Changes:
#   1. practitioner: nullable → NOT NULL + on_delete PROTECT
#   2. Add named UniqueConstraint on appointment (ts_unique_appointment)

from django.db import migrations, models
import django.db.models.deletion


def backfill_practitioner(apps, schema_editor):
    """
    If any TreatmentSession rows exist with NULL practitioner,
    copy practitioner from the linked appointment.
    """
    TreatmentSession = apps.get_model('treatment_plans', 'TreatmentSession')
    for session in TreatmentSession.objects.filter(practitioner__isnull=True):
        if session.appointment and session.appointment.practitioner_id:
            session.practitioner_id = session.appointment.practitioner_id
            session.save(update_fields=['practitioner'])


class Migration(migrations.Migration):
    dependencies = [
        ("treatment_plans", "0002_add_treatment_session"),
    ]

    operations = [
        # Step 1: Backfill any NULL practitioner values
        migrations.RunPython(
            backfill_practitioner,
            reverse_code=migrations.RunPython.noop,
        ),

        # Step 2: AlterField to NOT NULL + PROTECT
        migrations.AlterField(
            model_name="treatmentsession",
            name="practitioner",
            field=models.ForeignKey(
                help_text="Practitioner who performed the session",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="treatment_sessions",
                to="authz.practitioner",
            ),
        ),

        # Step 3: Add explicit named UniqueConstraint on appointment
        migrations.AddConstraint(
            model_name="treatmentsession",
            constraint=models.UniqueConstraint(
                fields=["appointment"],
                name="ts_unique_appointment",
            ),
        ),
    ]
