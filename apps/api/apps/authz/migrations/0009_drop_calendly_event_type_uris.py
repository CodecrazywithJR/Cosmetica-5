"""
Drop rogue column practitioner.calendly_event_type_uris.

This column exists in PostgreSQL but not in the Django model.
It was leftover drift from an earlier prototype.  IF EXISTS makes
this migration idempotent.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("authz", "0008_add_legal_entity_constraint"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE practitioner DROP COLUMN IF EXISTS calendly_event_type_uris;",
            reverse_sql="ALTER TABLE practitioner ADD COLUMN IF NOT EXISTS calendly_event_type_uris jsonb NOT NULL DEFAULT '[]'::jsonb;",
        ),
    ]
