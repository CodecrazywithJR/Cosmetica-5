# Generated migration — Domain Hardening Patch
# Defect DI-H2: Encounter.patient was on_delete=CASCADE, meaning a Patient
# deletion would silently destroy all clinical Encounter history.
# Changed to PROTECT so Django raises ProtectedError before any deletion.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clinical', '0111_drop_appointment_rogue_clinic_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='encounter',
            name='patient',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='encounters',
                to='clinical.patient',
            ),
        ),
    ]
