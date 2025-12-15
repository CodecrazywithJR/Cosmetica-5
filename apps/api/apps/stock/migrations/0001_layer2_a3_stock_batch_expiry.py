"""
Layer 2 A3: Stock/Inventory Domain Integrity with Batch and Expiry Support

This migration:
1. Creates StockLocation, StockBatch, StockOnHand models
2. Expands StockMove with location, batch, and new move types
3. Migrates existing Product.stock_quantity to StockOnHand with UNKNOWN-INITIAL batch
4. Adds constraints and indexes for data integrity

Business Rules Enforced:
- StockMove.quantity != 0
- IN movements: quantity > 0
- OUT movements: quantity < 0
- StockOnHand.quantity_on_hand >= 0
- Batch number unique per product
- Cannot consume from expired batches
- FEFO allocation strategy

Generated manually on 2025-12-16
"""
from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion
from django.utils import timezone
import uuid


def migrate_existing_stock_to_batches(apps, schema_editor):
    """
    Migrate existing Product.stock_quantity to batch-based system.
    
    Strategy:
    1. Create default location "MAIN-WAREHOUSE" if no locations exist
    2. For each product with stock_quantity > 0:
       - Create batch "UNKNOWN-INITIAL-{product_sku}"
       - Set expiry_date to 10 years in future (to avoid FEFO issues)
       - Create StockOnHand record
    3. Log migration to audit if available
    """
    Product = apps.get_model('products', 'Product')
    StockLocation = apps.get_model('stock', 'StockLocation')
    StockBatch = apps.get_model('stock', 'StockBatch')
    StockOnHand = apps.get_model('stock', 'StockOnHand')
    
    # Create default location
    default_location, created = StockLocation.objects.get_or_create(
        code='MAIN-WAREHOUSE',
        defaults={
            'name': 'Main Warehouse',
            'location_type': 'warehouse',
            'is_active': True,
        }
    )
    
    print(f"\n✓ Default location: {default_location.name} ({default_location.code})")
    
    # Migrate products with stock
    products_with_stock = Product.objects.filter(stock_quantity__gt=0)
    migrated_count = 0
    
    from datetime import timedelta
    future_expiry = timezone.now().date() + timedelta(days=3650)  # 10 years
    
    for product in products_with_stock:
        # Create initial batch
        batch, batch_created = StockBatch.objects.get_or_create(
            product=product,
            batch_number=f'UNKNOWN-INITIAL-{product.sku}',
            defaults={
                'expiry_date': future_expiry,
                'received_at': timezone.now().date(),
                'metadata': {
                    'migration': 'Layer 2 A3 - Initial stock migration',
                    'source': 'Product.stock_quantity',
                    'migrated_at': str(timezone.now()),
                }
            }
        )
        
        # Create stock on hand
        stock_on_hand, soh_created = StockOnHand.objects.get_or_create(
            product=product,
            location=default_location,
            batch=batch,
            defaults={
                'quantity_on_hand': product.stock_quantity
            }
        )
        
        if soh_created:
            migrated_count += 1
            print(f"  ✓ Migrated {product.sku}: {product.stock_quantity} units")
    
    print(f"\n✅ Migrated {migrated_count} products to batch-based stock")
    
    # Note: We don't zero out Product.stock_quantity here to maintain backward compatibility
    # In future, Product.stock_quantity can be deprecated in favor of StockOnHand


def reverse_stock_migration(apps, schema_editor):
    """Reverse migration - delete batch-based stock records."""
    StockOnHand = apps.get_model('stock', 'StockOnHand')
    StockBatch = apps.get_model('stock', 'StockBatch')
    StockLocation = apps.get_model('stock', 'StockLocation')
    
    # Delete all stock records (they'll be recreated on forward migration)
    StockOnHand.objects.all().delete()
    StockBatch.objects.filter(batch_number__startswith='UNKNOWN-INITIAL-').delete()
    StockLocation.objects.filter(code='MAIN-WAREHOUSE').delete()
    
    print("Reversed stock migration")


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('products', '__first__'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Step 1: Create StockLocation
        migrations.CreateModel(
            name='StockLocation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255, verbose_name='Name')),
                ('code', models.CharField(max_length=50, unique=True, verbose_name='Code')),
                ('location_type', models.CharField(
                    choices=[
                        ('warehouse', 'Warehouse'),
                        ('cabinet', 'Cabinet'),
                        ('clinic_room', 'Clinic Room'),
                        ('other', 'Other')
                    ],
                    default='warehouse',
                    max_length=20,
                    verbose_name='Location Type'
                )),
                ('is_active', models.BooleanField(default=True, verbose_name='Active')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
            ],
            options={
                'verbose_name': 'Stock Location',
                'verbose_name_plural': 'Stock Locations',
                'db_table': 'stock_locations',
                'ordering': ['name'],
            },
        ),
        
        # Step 2: Create StockBatch
        migrations.CreateModel(
            name='StockBatch',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('batch_number', models.CharField(
                    help_text='Unique batch/lot number per product',
                    max_length=100,
                    verbose_name='Batch Number'
                )),
                ('expiry_date', models.DateField(
                    blank=True,
                    help_text='Date when batch expires. Required for expirable products.',
                    null=True,
                    verbose_name='Expiry Date'
                )),
                ('received_at', models.DateField(
                    default=timezone.now,
                    help_text='Date when batch was received',
                    verbose_name='Received Date'
                )),
                ('metadata', models.JSONField(
                    blank=True,
                    default=dict,
                    help_text='Additional batch information (supplier, quality checks, etc.)',
                    verbose_name='Metadata'
                )),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='batches',
                    to='products.product',
                    verbose_name='Product'
                )),
            ],
            options={
                'verbose_name': 'Stock Batch',
                'verbose_name_plural': 'Stock Batches',
                'db_table': 'stock_batches',
                'ordering': ['expiry_date', 'batch_number'],
            },
        ),
        
        # Step 3: Create expanded StockMove
        migrations.CreateModel(
            name='StockMove',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('move_type', models.CharField(
                    choices=[
                        ('purchase_in', 'Purchase In'),
                        ('adjustment_in', 'Adjustment In'),
                        ('transfer_in', 'Transfer In'),
                        ('sale_out', 'Sale Out'),
                        ('adjustment_out', 'Adjustment Out'),
                        ('waste_out', 'Waste Out'),
                        ('transfer_out', 'Transfer Out'),
                    ],
                    max_length=20,
                    verbose_name='Move Type'
                )),
                ('quantity', models.IntegerField(
                    help_text='Positive for IN, negative for OUT',
                    verbose_name='Quantity'
                )),
                ('reference_type', models.CharField(
                    blank=True,
                    help_text='Type of document: Sale, SaleLine, Adjustment, etc.',
                    max_length=50,
                    verbose_name='Reference Type'
                )),
                ('reference_id', models.CharField(
                    blank=True,
                    help_text='ID of the referenced document',
                    max_length=255,
                    verbose_name='Reference ID'
                )),
                ('reason', models.TextField(blank=True, verbose_name='Reason')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('batch', models.ForeignKey(
                    blank=True,
                    help_text='Required for batch-tracked products',
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='stock_moves',
                    to='stock.stockbatch',
                    verbose_name='Batch'
                )),
                ('created_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Created By'
                )),
                ('location', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='stock_moves',
                    to='stock.stocklocation',
                    verbose_name='Location'
                )),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='stock_moves',
                    to='products.product',
                    verbose_name='Product'
                )),
            ],
            options={
                'verbose_name': 'Stock Move',
                'verbose_name_plural': 'Stock Moves',
                'db_table': 'stock_moves',
                'ordering': ['-created_at'],
            },
        ),
        
        # Step 4: Create StockOnHand
        migrations.CreateModel(
            name='StockOnHand',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('quantity_on_hand', models.IntegerField(
                    default=0,
                    help_text='Current available quantity',
                    verbose_name='Quantity On Hand'
                )),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('batch', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='stock_on_hand',
                    to='stock.stockbatch',
                    verbose_name='Batch'
                )),
                ('location', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='stock_on_hand',
                    to='stock.stocklocation',
                    verbose_name='Location'
                )),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='stock_on_hand',
                    to='products.product',
                    verbose_name='Product'
                )),
            ],
            options={
                'verbose_name': 'Stock On Hand',
                'verbose_name_plural': 'Stock On Hand',
                'db_table': 'stock_on_hand',
                'ordering': ['product', 'location', 'batch'],
            },
        ),
        
        # Step 5: Add constraints
        migrations.AddConstraint(
            model_name='stockbatch',
            constraint=models.UniqueConstraint(
                fields=['product', 'batch_number'],
                name='unique_batch_per_product'
            ),
        ),
        migrations.AddConstraint(
            model_name='stockmove',
            constraint=models.CheckConstraint(
                check=~models.Q(quantity=0),
                name='stock_move_quantity_non_zero'
            ),
        ),
        migrations.AddConstraint(
            model_name='stockonhand',
            constraint=models.UniqueConstraint(
                fields=['product', 'location', 'batch'],
                name='unique_stock_on_hand'
            ),
        ),
        migrations.AddConstraint(
            model_name='stockonhand',
            constraint=models.CheckConstraint(
                check=models.Q(quantity_on_hand__gte=0),
                name='stock_on_hand_non_negative'
            ),
        ),
        
        # Step 6: Add indexes
        migrations.AddIndex(
            model_name='stocklocation',
            index=models.Index(fields=['code'], name='idx_location_code'),
        ),
        migrations.AddIndex(
            model_name='stocklocation',
            index=models.Index(fields=['is_active'], name='idx_location_active'),
        ),
        migrations.AddIndex(
            model_name='stockbatch',
            index=models.Index(fields=['product', 'expiry_date'], name='idx_batch_prod_expiry'),
        ),
        migrations.AddIndex(
            model_name='stockbatch',
            index=models.Index(fields=['expiry_date'], name='idx_batch_expiry'),
        ),
        migrations.AddIndex(
            model_name='stockbatch',
            index=models.Index(fields=['batch_number'], name='idx_batch_number'),
        ),
        migrations.AddIndex(
            model_name='stockmove',
            index=models.Index(fields=['product', '-created_at'], name='idx_move_product'),
        ),
        migrations.AddIndex(
            model_name='stockmove',
            index=models.Index(fields=['location', '-created_at'], name='idx_move_location'),
        ),
        migrations.AddIndex(
            model_name='stockmove',
            index=models.Index(fields=['batch', '-created_at'], name='idx_move_batch'),
        ),
        migrations.AddIndex(
            model_name='stockmove',
            index=models.Index(fields=['move_type', '-created_at'], name='idx_move_type'),
        ),
        migrations.AddIndex(
            model_name='stockmove',
            index=models.Index(fields=['reference_type', 'reference_id'], name='idx_move_reference'),
        ),
        migrations.AddIndex(
            model_name='stockonhand',
            index=models.Index(fields=['product', 'location'], name='idx_onhand_prod_loc'),
        ),
        migrations.AddIndex(
            model_name='stockonhand',
            index=models.Index(fields=['location', 'product'], name='idx_onhand_loc_prod'),
        ),
        migrations.AddIndex(
            model_name='stockonhand',
            index=models.Index(fields=['batch'], name='idx_onhand_batch'),
        ),
        
        # Step 7: Data migration - migrate existing stock
        migrations.RunPython(
            migrate_existing_stock_to_batches,
            reverse_code=reverse_stock_migration,
        ),
    ]
