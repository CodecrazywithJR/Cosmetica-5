# Generated migration for Layer 3 C: Partial Refunds (sales app)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0002_add_product_fk_for_stock_integration'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Create SaleRefund model
        migrations.CreateModel(
            name='SaleRefund',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('status', models.CharField(
                    choices=[
                        ('draft', 'Draft'),
                        ('completed', 'Completed'),
                        ('failed', 'Failed')
                    ],
                    default='draft',
                    max_length=20,
                    verbose_name='Status'
                )),
                ('reason', models.TextField(blank=True, help_text='Reason for the refund', verbose_name='Reason')),
                ('metadata', models.JSONField(
                    blank=True,
                    default=dict,
                    help_text='Additional metadata including idempotency_key',
                    verbose_name='Metadata'
                )),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('created_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Created By'
                )),
                ('sale', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='refunds',
                    to='sales.sale',
                    verbose_name='Sale'
                )),
            ],
            options={
                'verbose_name': 'Sale Refund',
                'verbose_name_plural': 'Sale Refunds',
                'db_table': 'sale_refunds',
                'ordering': ['-created_at'],
            },
        ),
        
        # Create SaleRefundLine model
        migrations.CreateModel(
            name='SaleRefundLine',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('qty_refunded', models.DecimalField(
                    decimal_places=2,
                    help_text='Quantity being refunded for this line',
                    max_digits=10,
                    verbose_name='Quantity Refunded'
                )),
                ('amount_refunded', models.DecimalField(
                    blank=True,
                    decimal_places=2,
                    help_text='Amount refunded (can be proportional or custom)',
                    max_digits=10,
                    null=True,
                    verbose_name='Amount Refunded'
                )),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('refund', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='lines',
                    to='sales.salerefund',
                    verbose_name='Refund'
                )),
                ('sale_line', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='refund_lines',
                    to='sales.saleline',
                    verbose_name='Sale Line'
                )),
            ],
            options={
                'verbose_name': 'Sale Refund Line',
                'verbose_name_plural': 'Sale Refund Lines',
                'db_table': 'sale_refund_lines',
                'ordering': ['refund', 'sale_line'],
            },
        ),
        
        # Add constraints and indexes
        migrations.AddConstraint(
            model_name='salerefund',
            constraint=models.UniqueConstraint(
                condition=models.Q(('metadata__has_key', 'idempotency_key')),
                fields=('sale',),
                name='unique_sale_refund_idempotency_key',
                violation_error_message='Refund with this idempotency key already exists for this sale'
            ),
        ),
        migrations.AddIndex(
            model_name='salerefund',
            index=models.Index(fields=['sale', '-created_at'], name='idx_refund_sale'),
        ),
        migrations.AddIndex(
            model_name='salerefund',
            index=models.Index(fields=['status'], name='idx_refund_status'),
        ),
        migrations.AddIndex(
            model_name='salerefund',
            index=models.Index(fields=['created_by'], name='idx_refund_created_by'),
        ),
        
        migrations.AddConstraint(
            model_name='salerefundline',
            constraint=models.CheckConstraint(
                check=models.Q(qty_refunded__gt=0),
                name='refund_line_qty_positive'
            ),
        ),
        migrations.AddIndex(
            model_name='salerefundline',
            index=models.Index(fields=['refund'], name='idx_refund_line_refund'),
        ),
        migrations.AddIndex(
            model_name='salerefundline',
            index=models.Index(fields=['sale_line'], name='idx_refund_line_sale_line'),
        ),
    ]
