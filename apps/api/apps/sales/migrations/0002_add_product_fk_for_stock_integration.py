# Generated migration for Layer 3 A: Sales-Stock Integration

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0001_layer2_a2_sales_integrity'),
        ('products', '0001_initial'),  # Assumes products app exists
    ]

    operations = [
        # Add product FK to SaleLine (nullable for services)
        migrations.AddField(
            model_name='saleline',
            name='product',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='sale_lines',
                to='products.product',
                verbose_name='Product',
                help_text='Product if product sale, null for service/custom line'
            ),
        ),
        
        # Add index for product lookups
        migrations.AddIndex(
            model_name='saleline',
            index=models.Index(fields=['product'], name='idx_sale_line_product'),
        ),
    ]
