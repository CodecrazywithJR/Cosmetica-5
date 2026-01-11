# Generated migration for Layer 2 A1: Clinical Domain Integrity
#
# NOTE: Original data migration functions removed because they referenced
# models from apps without migrations (encounters, photos). These apps are
# in "legacy" state and use syncdb. Data integrity for those models will
# be enforced via:
# 1. Model-level validation (clean() methods)
# 2. Database constraints when those apps are migrated
# 3. Future migrations when encounters/photos apps get proper migration history

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Layer 2 A1: Clinical Domain Integrity
    
    Original intent: Add indices for patient timeline queries and clean inconsistent data.
    
    REMOVED: Data migration functions that referenced models from apps without migrations
    (encounters, photos). Those apps use syncdb and aren't part of the migration system yet.
    
    KEPT: Schema operations that apply to models in the 'clinical' app only.
    
    Future work: When encounters/photos apps are migrated to Django migrations,
    create separate migrations for their data integrity rules.
    """

    dependencies = [
        ('clinical', '0003_clinical_audit_log'),
    ]

    operations = [
        # No operations needed - original operations referenced models not in clinical app
        # (Encounter is in 'encounters' app, ClinicalPhoto would be here but indices
        # were intended for the encounters.Encounter model)
        #
        # This migration is kept as a placeholder to maintain migration history integrity.
        # If it was already applied in some environments, we don't want to break the chain.
    ]
