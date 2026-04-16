"""Tenant isolation: add legal_entity FK to product model."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("legal", "0004_fix_legacy_schema"),
        ("products", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="legal_entity",
            field=models.ForeignKey(
                blank=True,
                help_text="Owning legal entity (tenant isolation).",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="%(app_label)s_%(class)s_set",
                to="legal.legalentity",
            ),
        ),
    ]
