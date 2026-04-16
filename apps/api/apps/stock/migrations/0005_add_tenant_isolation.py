"""Tenant isolation: add legal_entity FK to stock models.

Adds a nullable legal_entity FK to every stock model for tenant isolation.
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
        ("stock", "0004_add_partial_refund_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="stockbatch",
            name="legal_entity",
            field=_FIELD,
        ),
        migrations.AddField(
            model_name="stocklocation",
            name="legal_entity",
            field=_FIELD,
        ),
        migrations.AddField(
            model_name="stockmove",
            name="legal_entity",
            field=_FIELD,
        ),
        migrations.AddField(
            model_name="stockonhand",
            name="legal_entity",
            field=_FIELD,
        ),
    ]
