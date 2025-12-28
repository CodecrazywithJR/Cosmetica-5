# Generated migration to drop legacy encounters table
# Date: 2025-12-28
# Reason: Encounter model moved to apps.clinical, legacy table no longer needed

from django.db import migrations


class Migration(migrations.Migration):
    """
    Drop legacy encounters table.
    
    The Encounter model has been moved to apps.clinical.models.Encounter.
    This migration removes the old table from the encounters app.
    
    Safe to run: Table contains 0 rows (verified 2025-12-28).
    """
    
    dependencies = [
        ('encounters', '0002_clinical_media'),
    ]
    
    operations = [
        migrations.RunSQL(
            sql='DROP TABLE IF EXISTS encounters CASCADE;',
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
