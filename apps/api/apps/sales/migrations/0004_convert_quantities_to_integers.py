"""
Migration: Change quantity fields from Decimal to Integer.

SAFETY:
- Converts existing .00 decimal values to integers without data loss
- FAILS with RuntimeError if any record has non-zero decimal part (e.g., 1.50)
- This prevents silent data corruption

Business Rule Enforcement:
- Quantities (units) must be integers (e.g., 5 units, not 5.75 units)
- Money fields remain Decimal (e.g., $5.75 is valid)
"""
from django.db import migrations, models
from decimal import Decimal


def validate_no_fractional_quantities(apps, schema_editor):
    """
    Validate that no existing data has fractional quantities.
    
    Raises RuntimeError if any SaleLine.quantity or SaleRefundLine.qty_refunded
    has a non-zero fractional part (e.g., 1.5, 2.75).
    
    Allows values like 1.00, 5.00 (will be converted to 1, 5).
    """
    SaleLine = apps.get_model('sales', 'SaleLine')
    SaleRefundLine = apps.get_model('sales', 'SaleRefundLine')
    
    # Check SaleLine.quantity
    invalid_sale_lines = []
    for line in SaleLine.objects.all():
        qty = Decimal(str(line.quantity))
        if qty % 1 != 0:  # Has fractional part
            invalid_sale_lines.append({
                'id': str(line.id),
                'sale_id': str(line.sale_id),
                'product_name': line.product_name,
                'quantity': str(qty)
            })
    
    if invalid_sale_lines:
        error_details = "\n".join([
            f"  - SaleLine {item['id']}: {item['product_name']} "
            f"(Sale {item['sale_id']}) has quantity={item['quantity']}"
            for item in invalid_sale_lines[:10]  # Show first 10
        ])
        
        raise RuntimeError(
            f"\n\n"
            f"❌ MIGRATION ABORTED: Found {len(invalid_sale_lines)} SaleLine records "
            f"with fractional quantities.\n\n"
            f"Quantities must be integers (e.g., 5 units, not 5.75 units).\n"
            f"Money fields remain Decimal (e.g., $5.75 is valid).\n\n"
            f"Invalid records:\n{error_details}\n"
            f"{f'... and {len(invalid_sale_lines) - 10} more' if len(invalid_sale_lines) > 10 else ''}\n\n"
            f"ACTION REQUIRED:\n"
            f"1. Review these records in production database\n"
            f"2. Correct fractional quantities manually (or delete if invalid data)\n"
            f"3. Re-run migration\n"
        )
    
    # Check SaleRefundLine.qty_refunded
    invalid_refund_lines = []
    for line in SaleRefundLine.objects.all():
        qty = Decimal(str(line.qty_refunded))
        if qty % 1 != 0:  # Has fractional part
            invalid_refund_lines.append({
                'id': str(line.id),
                'refund_id': str(line.refund_id),
                'sale_line_id': str(line.sale_line_id),
                'qty_refunded': str(qty)
            })
    
    if invalid_refund_lines:
        error_details = "\n".join([
            f"  - SaleRefundLine {item['id']}: qty_refunded={item['qty_refunded']} "
            f"(Refund {item['refund_id']}, SaleLine {item['sale_line_id']})"
            for item in invalid_refund_lines[:10]
        ])
        
        raise RuntimeError(
            f"\n\n"
            f"❌ MIGRATION ABORTED: Found {len(invalid_refund_lines)} SaleRefundLine records "
            f"with fractional quantities.\n\n"
            f"Refund quantities must be integers.\n\n"
            f"Invalid records:\n{error_details}\n"
            f"{f'... and {len(invalid_refund_lines) - 10} more' if len(invalid_refund_lines) > 10 else ''}\n\n"
            f"ACTION REQUIRED:\n"
            f"1. Review these records in production database\n"
            f"2. Correct fractional quantities manually\n"
            f"3. Re-run migration\n"
        )


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0003_add_partial_refund_models'),
    ]

    operations = [
        # Step 1: Validate no fractional quantities exist
        migrations.RunPython(
            validate_no_fractional_quantities,
            reverse_code=migrations.RunPython.noop,
        ),
        
        # Step 2: Convert SaleLine.quantity from DecimalField to PositiveIntegerField
        migrations.AlterField(
            model_name='saleline',
            name='quantity',
            field=models.PositiveIntegerField(
                help_text='Must be greater than 0',
                verbose_name='Quantity'
            ),
        ),
        
        # Step 3: Convert SaleRefundLine.qty_refunded from DecimalField to PositiveIntegerField
        migrations.AlterField(
            model_name='salerefundline',
            name='qty_refunded',
            field=models.PositiveIntegerField(
                help_text='Quantity being refunded for this line',
                verbose_name='Quantity Refunded'
            ),
        ),
    ]
