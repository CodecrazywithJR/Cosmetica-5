"""Tenant isolation: add legal_entity FK to clinical models.

Adds a nullable legal_entity FK to every clinical model for tenant
isolation.  All models use a standard AddField so the column is created
in both production and fresh test databases.
"""

from django.db import migrations, models
import django.db.models.deletion

_FIELD = models.ForeignKey(
    blank=True,
    help_text="Owning legal entity (tenant isolation).",
    null=True,
    on_delete=django.db.models.deletion.PROTECT,
    related_name="%(app_label)s_%(class)s_set",
    to="legal.legalentity",
)


class Migration(migrations.Migration):
    dependencies = [
        ("legal", "0004_fix_legacy_schema"),
        ("clinical", "0105_patient_insurance"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="legal_entity",
            field=_FIELD,
        ),
        migrations.AddField(
            model_name="encounter",
            name="legal_entity",
            field=_FIELD,
        ),
        migrations.AddField(
            model_name="patient",
            name="legal_entity",
            field=_FIELD,
        ),
        migrations.AddField(
            model_name="treatment",
            name="legal_entity",
            field=_FIELD,
        ),
        migrations.AddField(
            model_name="clinicalmedia",
            name="legal_entity",
            field=_FIELD,
        ),
        migrations.AddField(
            model_name="clinicalphoto",
            name="legal_entity",
            field=_FIELD,
        ),
        migrations.AddField(
            model_name="consent",
            name="legal_entity",
            field=_FIELD,
        ),
        migrations.AddField(
            model_name="practitionerblock",
            name="legal_entity",
            field=_FIELD,
        ),
        migrations.AddField(
            model_name="referralsource",
            name="legal_entity",
            field=_FIELD,
        ),
    ]
