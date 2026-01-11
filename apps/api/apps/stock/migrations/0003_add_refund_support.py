# Generated migration for Layer 3 B: Refund stock support

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0002_add_sale_fks_for_integration'),
    ]

    operations = [
        # Add REFUND_IN to StockMoveTypeChoices
        migrations.AlterField(
            model_name='stockmove',
            name='move_type',
            field=models.CharField(
                choices=[
                    ('purchase_in', 'Purchase In'),
                    ('adjustment_in', 'Adjustment In'),
                    ('transfer_in', 'Transfer In'),
                    ('refund_in', 'Refund In'),
                    ('sale_out', 'Sale Out'),
                    ('adjustment_out', 'Adjustment Out'),
                    ('waste_out', 'Waste Out'),
                    ('transfer_out', 'Transfer Out')
                ],
                max_length=20,
                verbose_name='Move Type'
            ),
        ),
        # Add reversed_move field (OneToOneField to self)
        migrations.AddField(
            model_name='stockmove',
            name='reversed_move',
            field=models.OneToOneField(
                blank=True,
                help_text='For REFUND_IN moves: the original SALE_OUT move being reversed',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reversal',
                to='stock.stockmove',
                verbose_name='Reversed Move'
            ),
        ),
        # Add index for reversed_move lookups
        migrations.AddIndex(
            model_name='stockmove',
            index=models.Index(fields=['reversed_move'], name='idx_stock_move_reversed'),
        ),
    ]
