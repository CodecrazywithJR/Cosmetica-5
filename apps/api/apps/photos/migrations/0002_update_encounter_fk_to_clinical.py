# Generated manually to remove dependency on dropped encounters table
# and update FK to clinical.Encounter

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("photos", "0001_update_patient_fk_to_clinical"),
        ("clinical", "0007_add_medical_fields_to_patient"),
    ]

    operations = [
        # Remove old FK constraint
        migrations.RunSQL(
            sql='ALTER TABLE "skin_photos" DROP CONSTRAINT IF EXISTS "skin_photos_encounter_id_7bcc3d6c_fk_encounters_id";',
            reverse_sql=migrations.RunSQL.noop
        ),
        
        # Remove old index if exists
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS "skin_photos_encount_43cfa4_idx";',
            reverse_sql=migrations.RunSQL.noop
        ),
        
        # Set all encounter_id to NULL since old encounters table was dropped
        migrations.RunSQL(
            sql='UPDATE "skin_photos" SET "encounter_id" = NULL;',
            reverse_sql=migrations.RunSQL.noop
        ),
        
        # Drop the old encounter_id column (bigint referencing deleted table)
        migrations.RunSQL(
            sql='ALTER TABLE "skin_photos" DROP COLUMN IF EXISTS "encounter_id";',
            reverse_sql=migrations.RunSQL.noop
        ),
        
        # Add new encounter_id column as UUID
        migrations.RunSQL(
            sql='ALTER TABLE "skin_photos" ADD COLUMN "encounter_id" uuid NULL;',
            reverse_sql=migrations.RunSQL.noop
        ),
        
        # Add FK constraint to clinical.encounter
        migrations.RunSQL(
            sql='''
                ALTER TABLE "skin_photos" 
                ADD CONSTRAINT "skin_photos_encounter_id_fk_clinical" 
                FOREIGN KEY ("encounter_id") REFERENCES "encounter" ("id") 
                ON DELETE SET NULL;
            ''',
            reverse_sql=migrations.RunSQL.noop
        ),
        
        # Recreate index with correct reference
        migrations.RunSQL(
            sql='CREATE INDEX "skin_photos_enc_clinical_idx" ON "skin_photos" ("encounter_id");',
            reverse_sql=migrations.RunSQL.noop
        ),
    ]
