"""
Add database-level overbooking protection for appointments.

1. Enable btree_gist extension (required for ExclusionConstraint with mixed types).
2. Add ExclusionConstraint 'prevent_practitioner_overbooking' on the appointment table:
   - Same practitioner_id (equality via =)
   - Overlapping tstzrange(scheduled_start, scheduled_end) (overlap via &&)
   - Only for active statuses: scheduled, confirmed, checked_in
   - Only for non-deleted rows: is_deleted = false
"""

from django.db import migrations
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import RangeOperators


class Migration(migrations.Migration):

    dependencies = [
        ("clinical", "0115_rename_encounter_location_to_clinic"),
    ]

    operations = [
        # Step 1: Enable btree_gist extension.
        # reverse_sql is intentionally a no-op: extensions are shared database
        # capabilities and must not be removed on rollback — they may be used
        # by other constraints, indexes, or future modules.
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS btree_gist;",
            reverse_sql=migrations.RunSQL.noop,
        ),

        # Step 2: Add the exclusion constraint using raw SQL.
        # Django's ExclusionConstraint requires RangeField on the model,
        # but we use plain DateTimeField columns and build tstzrange() inline.
        #
        # We wrap the range in a CASE to avoid DataError when invalid data
        # (end <= start) is saved with skip_validation=True — tstzrange()
        # throws if lower > upper, so we substitute an empty range '[,)' for
        # those rows, which cannot overlap anything.
        migrations.RunSQL(
            sql="""
                ALTER TABLE appointment
                ADD CONSTRAINT prevent_practitioner_overbooking
                EXCLUDE USING gist (
                    practitioner_id WITH =,
                    (CASE WHEN scheduled_start < scheduled_end
                          THEN tstzrange(scheduled_start, scheduled_end)
                          ELSE 'empty'::tstzrange
                     END) WITH &&
                )
                WHERE (
                    status IN ('scheduled', 'confirmed', 'checked_in')
                    AND is_deleted = false
                );
            """,
            reverse_sql="""
                ALTER TABLE appointment
                DROP CONSTRAINT IF EXISTS prevent_practitioner_overbooking;
            """,
        ),
    ]
