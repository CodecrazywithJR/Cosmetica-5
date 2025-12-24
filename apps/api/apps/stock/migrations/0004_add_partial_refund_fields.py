# Generated migration for Layer 3 C: Partial Refunds (stock app)

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0003_add_refund_support'),
        ('sales', '0003_add_partial_refund_models'),
    ]

    operations = [
        # Add refund FK to StockMove
        migrations.AddField(
            model_name='stockmove',
            name='refund',
            field=models.ForeignKey(
                blank=True,
                help_text='Partial refund that generated this stock movement',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='stock_moves',
                to='sales.salerefund',
                verbose_name='Refund'
            ),
        ),
        
        # Add source_move FK to StockMove (for partial refund tracking)
        migrations.AddField(
            model_name='stockmove',
            name='source_move',
            field=models.ForeignKey(
                blank=True,
                help_text='Original SALE_OUT move being partially reversed (for partial refunds)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='partial_reversals',
                to='stock.stockmove',
                verbose_name='Source Move'
            ),
        ),
        
        # Add unique constraint for idempotency
        migrations.AddConstraint(
            model_name='stockmove',
            constraint=models.UniqueConstraint(
                condition=models.Q(('refund__isnull', False), ('source_move__isnull', False)),
                fields=('refund', 'source_move'),
                name='uq_stockmove_refund_source_move',
                violation_error_message='Duplicate stock move for refund and source move combination'
            ),
        ),
        
        # Add indexes for performance
        migrations.AddIndex(
            model_name='stockmove',
            index=models.Index(fields=['refund', '-created_at'], name='idx_stock_move_refund'),
        ),
        migrations.AddIndex(
            model_name='stockmove',
            index=models.Index(fields=['source_move'], name='idx_stock_move_source'),
        ),
    ]
