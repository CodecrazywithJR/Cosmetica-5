# Generated migration for idempotency_key field on SaleRefund
# This migration:
# 1. Adds idempotency_key CharField to SaleRefund
# 2. Migrates existing data from metadata JSON to the new field
# 3. Adds UniqueConstraint for (sale, idempotency_key)

from django.db import migrations, models
from django.db.models import Q


def migrate_idempotency_keys_from_metadata(apps, schema_editor):
    """
    Data migration: Copy idempotency_key from metadata JSON to dedicated field.
    
    LEGACY COMPATIBILITY: Only copies from metadata for existing records.
    New records will use field only (single source of truth).
    
    SAFETY CHECK: Validates no duplicate (sale, idempotency_key) pairs exist.
    If duplicates found, migration FAILS with RuntimeError.
    """
    SaleRefund = apps.get_model('sales', 'SaleRefund')
    
    # Track (sale_id, key) pairs to detect duplicates
    seen_pairs = {}
    duplicates = []
    
    # Iterate all refunds with idempotency_key in metadata (legacy records)
    refunds_with_keys = SaleRefund.objects.filter(
        metadata__has_key='idempotency_key'
    ).select_related('sale')
    
    for refund in refunds_with_keys:
        key = refund.metadata.get('idempotency_key')
        
        if not key:
            continue  # Empty key, skip
        
        sale_id = str(refund.sale_id)
        pair = (sale_id, key)
        
        # Check for duplicates
        if pair in seen_pairs:
            duplicates.append({
                'sale_id': sale_id,
                'key': key,
                'refund_ids': [seen_pairs[pair], str(refund.id)]
            })
        else:
            seen_pairs[pair] = str(refund.id)
    
    # FAIL if duplicates found
    if duplicates:
        error_details = "\n".join([
            f"  - Sale {dup['sale_id']}, key '{dup['key']}': "
            f"Refunds {', '.join(dup['refund_ids'])}"
            for dup in duplicates[:10]  # Show first 10
        ])
        
        raise RuntimeError(
            f"❌ MIGRATION ABORTED: Found {len(duplicates)} duplicate "
            f"(sale, idempotency_key) pairs.\n\n"
            f"Duplicate pairs:\n{error_details}\n\n"
            f"ACTION REQUIRED:\n"
            f"1. Review these refunds in your database\n"
            f"2. Manually resolve duplicates (delete or update keys)\n"
            f"3. Re-run migration\n\n"
            f"This migration enforces unique constraint on (sale, idempotency_key).\n"
            f"Duplicates must be resolved before proceeding."
        )
    
    # No duplicates - proceed with data migration (legacy compatibility only)
    updated_count = 0
    for refund in refunds_with_keys:
        key = refund.metadata.get('idempotency_key')
        if key and not refund.idempotency_key:  # Only if field is empty
            refund.idempotency_key = key
            refund.save(update_fields=['idempotency_key'])
            updated_count += 1
    
    print(f"✓ Migrated {updated_count} legacy idempotency keys from metadata to field")
    print(f"  New refunds will use field only (single source of truth)")


def reverse_migrate_idempotency_keys(apps, schema_editor):
    """
    Reverse migration: Copy idempotency_key back to metadata.
    
    This ensures rollback safety for legacy systems.
    """
    SaleRefund = apps.get_model('sales', 'SaleRefund')
    
    refunds_with_keys = SaleRefund.objects.filter(idempotency_key__isnull=False)
    
    for refund in refunds_with_keys:
        if 'idempotency_key' not in refund.metadata:
            refund.metadata['idempotency_key'] = refund.idempotency_key
            refund.save(update_fields=['metadata'])


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0004_convert_quantities_to_integers'),
    ]

    operations = [
        # Step 1: Add idempotency_key field (nullable initially)
        migrations.AddField(
            model_name='salerefund',
            name='idempotency_key',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Unique key to prevent duplicate refunds for the same sale',
                max_length=128,
                null=True,
                verbose_name='Idempotency Key'
            ),
        ),
        
        # Step 2: Data migration - copy from metadata to field
        migrations.RunPython(
            migrate_idempotency_keys_from_metadata,
            reverse_migrate_idempotency_keys
        ),
        
        # Step 3: Remove old UniqueConstraint (on metadata JSON field)
        migrations.RemoveConstraint(
            model_name='salerefund',
            name='unique_sale_refund_idempotency_key',
        ),
        
        # Step 4: Add new UniqueConstraint (on dedicated field)
        migrations.AddConstraint(
            model_name='salerefund',
            constraint=models.UniqueConstraint(
                condition=models.Q(('idempotency_key__isnull', False)),
                fields=('sale', 'idempotency_key'),
                name='uniq_sale_refund_idempotency_key',
                violation_error_message='Refund with this idempotency key already exists for this sale'
            ),
        ),
        
        # Step 5: Update metadata field help_text (reflects new single-source-of-truth)
        migrations.AlterField(
            model_name='salerefund',
            name='metadata',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Additional metadata (idempotency_key is NOT stored here for new records)',
                verbose_name='Metadata'
            ),
        ),
    ]
