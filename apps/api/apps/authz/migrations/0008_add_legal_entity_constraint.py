from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Add CheckConstraint enforcing the System Plane / Business Plane rule:

    - Superusers (is_superuser=True)  → legal_entity may be NULL
    - Normal users (is_superuser=False) → legal_entity MUST be set

    Uses a standard AddConstraint so it works on both PostgreSQL and SQLite.
    """

    dependencies = [
        ("authz", "0007_system_plane_legal_entity"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                check=models.Q(is_superuser=True) | models.Q(legal_entity__isnull=False),
                name="user_requires_legal_entity_unless_superuser",
            ),
        ),
    ]


