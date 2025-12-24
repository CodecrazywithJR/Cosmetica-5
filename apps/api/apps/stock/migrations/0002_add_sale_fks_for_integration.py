# Generated migration for Layer 3 A: Sales-Stock Integration

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0001_layer2_a3_stock_batch_expiry'),
        ('sales', '0002_add_product_fk_for_stock_integration'),
    ]

    operations = [
        # Add FK to Sale for traceability (nullable - not all moves are from sales)
        migrations.AddField(
            model_name='stockmove',
            name='sale',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='stock_moves',
                to='sales.sale',
                verbose_name='Sale',
                help_text='Sale that triggered this stock movement (if applicable)'
            ),
        ),
        
        # Add FK to SaleLine for line-level traceability (nullable)
        migrations.AddField(
            model_name='stockmove',
            name='sale_line',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='stock_moves',
                to='sales.saleline',
                verbose_name='Sale Line',
                help_text='Specific sale line that triggered this movement (if applicable)'
            ),
        ),
        
        # Add indexes for Sale queries
        migrations.AddIndex(
            model_name='stockmove',
            index=models.Index(fields=['sale'], name='idx_stock_move_sale'),
        ),
        migrations.AddIndex(
            model_name='stockmove',
            index=models.Index(fields=['sale_line'], name='idx_stock_move_sale_line'),
        ),
    ]
