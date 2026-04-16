# Repair migration — align DB schema with current model field names.
#
# Background: The database was originally built by an older set of migrations
# that used 'legal_'-prefixed column names (legal_city, legal_address_line_1,
# default_currency, etc.) and a different set of field names than the current
# model uses. The file-system migrations were later replaced but the database
# columns were never renamed, causing a ProgrammingError when Django generates
# SELECT statements against column names that no longer exist.
#
# Strategy: RunSQL with IF EXISTS / IF NOT EXISTS guards so this migration is
# idempotent and safe to re-run or apply to environments in varying states.
# We only touch the database layer (state is already correct in existing
# migration files).

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("legal", "0003_system_plane_legal_entity"),
    ]

    operations = [
        # ── 1. Rename columns: old legacy name → model field name ──────────
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='legal_legalentity' AND column_name='legal_address_line_1'
                ) THEN
                    ALTER TABLE "legal_legalentity"
                        RENAME COLUMN "legal_address_line_1" TO "address_line_1";
                END IF;
            END $$;
            """,
            reverse_sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='legal_legalentity' AND column_name='address_line_1'
                ) THEN
                    ALTER TABLE "legal_legalentity"
                        RENAME COLUMN "address_line_1" TO "legal_address_line_1";
                END IF;
            END $$;
            """,
        ),
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='legal_legalentity' AND column_name='legal_address_line_2'
                ) THEN
                    ALTER TABLE "legal_legalentity"
                        RENAME COLUMN "legal_address_line_2" TO "address_line_2";
                END IF;
            END $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='legal_legalentity' AND column_name='legal_postal_code'
                ) THEN
                    ALTER TABLE "legal_legalentity"
                        RENAME COLUMN "legal_postal_code" TO "postal_code";
                END IF;
            END $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='legal_legalentity' AND column_name='legal_city'
                ) THEN
                    ALTER TABLE "legal_legalentity"
                        RENAME COLUMN "legal_city" TO "city";
                END IF;
            END $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='legal_legalentity' AND column_name='default_currency'
                ) THEN
                    ALTER TABLE "legal_legalentity"
                        RENAME COLUMN "default_currency" TO "currency";
                END IF;
            END $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='legal_legalentity' AND column_name='legal_phone'
                ) AND NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='legal_legalentity' AND column_name='phone'
                ) THEN
                    ALTER TABLE "legal_legalentity"
                        RENAME COLUMN "legal_phone" TO "phone";
                END IF;
            END $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),

        # ── 2. Add missing columns that the model defines but DB lacks ─────
        migrations.RunSQL(
            sql="""
            ALTER TABLE "legal_legalentity"
                ADD COLUMN IF NOT EXISTS "siren"
                    VARCHAR(9) NULL;
            """,
            reverse_sql='ALTER TABLE "legal_legalentity" DROP COLUMN IF EXISTS "siren";',
        ),
        migrations.RunSQL(
            sql="""
            ALTER TABLE "legal_legalentity"
                ADD COLUMN IF NOT EXISTS "siret"
                    VARCHAR(14) NULL;
            """,
            reverse_sql='ALTER TABLE "legal_legalentity" DROP COLUMN IF EXISTS "siret";',
        ),
        migrations.RunSQL(
            sql="""
            ALTER TABLE "legal_legalentity"
                ADD COLUMN IF NOT EXISTS "vat_number"
                    VARCHAR(20) NULL;
            """,
            reverse_sql='ALTER TABLE "legal_legalentity" DROP COLUMN IF EXISTS "vat_number";',
        ),
        migrations.RunSQL(
            sql="""
            ALTER TABLE "legal_legalentity"
                ADD COLUMN IF NOT EXISTS "timezone"
                    VARCHAR(50) NOT NULL DEFAULT 'Europe/Paris';
            """,
            reverse_sql='ALTER TABLE "legal_legalentity" DROP COLUMN IF EXISTS "timezone";',
        ),
        migrations.RunSQL(
            sql="""
            ALTER TABLE "legal_legalentity"
                ADD COLUMN IF NOT EXISTS "invoice_footer_text"
                    TEXT NOT NULL DEFAULT '';
            """,
            reverse_sql='ALTER TABLE "legal_legalentity" DROP COLUMN IF EXISTS "invoice_footer_text";',
        ),

        # ── 3. Add unique indexes for the nullable identifier fields ────────
        #    Use partial indexes (WHERE value IS NOT NULL) so multiple NULL
        #    rows are permitted (NULL != NULL in SQL).
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE tablename='legal_legalentity' AND indexname='legal_legalentity_siren_unique'
                ) THEN
                    CREATE UNIQUE INDEX legal_legalentity_siren_unique
                        ON "legal_legalentity" ("siren")
                        WHERE "siren" IS NOT NULL AND "siren" <> '';
                END IF;
            END $$;
            """,
            reverse_sql='DROP INDEX IF EXISTS "legal_legalentity_siren_unique";',
        ),
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE tablename='legal_legalentity' AND indexname='legal_legalentity_siret_unique'
                ) THEN
                    CREATE UNIQUE INDEX legal_legalentity_siret_unique
                        ON "legal_legalentity" ("siret")
                        WHERE "siret" IS NOT NULL AND "siret" <> '';
                END IF;
            END $$;
            """,
            reverse_sql='DROP INDEX IF EXISTS "legal_legalentity_siret_unique";',
        ),
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE tablename='legal_legalentity' AND indexname='legal_legalentity_vat_unique'
                ) THEN
                    CREATE UNIQUE INDEX legal_legalentity_vat_unique
                        ON "legal_legalentity" ("vat_number")
                        WHERE "vat_number" IS NOT NULL AND "vat_number" <> '';
                END IF;
            END $$;
            """,
            reverse_sql='DROP INDEX IF EXISTS "legal_legalentity_vat_unique";',
        ),

        # ── 4. Drop legacy columns that exist in DB but not in the model ───
        migrations.RunSQL(
            sql='ALTER TABLE "legal_legalentity" DROP COLUMN IF EXISTS "legal_country_code";',
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql='ALTER TABLE "legal_legalentity" DROP COLUMN IF EXISTS "legal_region";',
            reverse_sql=migrations.RunSQL.noop,
        ),

        # ── 5. Fix legal_email nullability to match model (blank=True) ─────
        #    Model: blank=True (NOT NULL, empty string default)
        #    DB:    nullable=YES → set default and drop nullable
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                -- Only update if the column is currently nullable
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='legal_legalentity'
                      AND column_name='legal_email'
                      AND is_nullable = 'YES'
                ) THEN
                    -- Fill any NULLs with empty string first
                    UPDATE "legal_legalentity" SET "legal_email" = '' WHERE "legal_email" IS NULL;
                    ALTER TABLE "legal_legalentity"
                        ALTER COLUMN "legal_email" SET NOT NULL,
                        ALTER COLUMN "legal_email" SET DEFAULT '';
                END IF;
                -- Same for phone
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='legal_legalentity'
                      AND column_name='phone'
                      AND is_nullable = 'YES'
                ) THEN
                    UPDATE "legal_legalentity" SET "phone" = '' WHERE "phone" IS NULL;
                    ALTER TABLE "legal_legalentity"
                        ALTER COLUMN "phone" SET NOT NULL,
                        ALTER COLUMN "phone" SET DEFAULT '';
                END IF;
            END $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
