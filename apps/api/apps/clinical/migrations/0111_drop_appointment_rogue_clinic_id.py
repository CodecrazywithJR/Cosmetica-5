"""
Drop rogue clinic_id column from appointment table.

The Django model uses `location` (→ location_id) for the FK to
ClinicLocation.  A rogue NOT NULL `clinic_id` column existed in the DB
without a corresponding model field, blocking ORM inserts.

Safe / reversible.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('clinical', '0110_scheduling_phase3_practitioner_schedule'),
    ]

    operations = [
        migrations.RunSQL(
            sql='ALTER TABLE appointment DROP COLUMN IF EXISTS clinic_id;',
            reverse_sql=(
                "ALTER TABLE appointment "
                "ADD COLUMN IF NOT EXISTS clinic_id uuid;"
            ),
        ),
    ]
