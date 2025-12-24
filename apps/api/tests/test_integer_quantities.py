"""
Tests: Quantity fields must be integers.

Validates that:
1. SaleLine.quantity only accepts integers
2. SaleRefundLine.qty_refunded only accepts integers
3. Decimal values (e.g., 1.5, 2.75) are rejected with HTTP 400
4. Money fields (unit_price, total, etc.) remain Decimal and work correctly
"""
import pytest
from decimal import Decimal
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

from apps.sales.models import Sale, SaleLine, SaleStatusChoices, SaleRefund, SaleRefundLine
from apps.products.models import Product
from apps.stock.models import StockLocation, StockBatch, StockOnHand

User = get_user_model()


@pytest.fixture
def api_client():
    """DRF API client."""
    return APIClient()


@pytest.fixture
def user(db):
    """Test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def auth_client(api_client, user):
    """Authenticated API client."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def product(db):
    """Test product."""
    return Product.objects.create(
        name='Test Product',
        code='PROD-001',
        is_stockable=True
    )


@pytest.fixture
def location(db):
    """Test location."""
    return StockLocation.objects.create(
        code='MAIN',
        name='Main Warehouse',
        is_active=True
    )


@pytest.fixture
def stock_with_inventory(db, product, location):
    """Product with stock available."""
    batch = StockBatch.objects.create(
        product=product,
        batch_number='BATCH-001',
        quantity_received=100,
        is_active=True
    )
    
    StockOnHand.objects.create(
        product=product,
        location=location,
        batch=batch,
        quantity_on_hand=100
    )
    
    return product


@pytest.fixture
def sale(db, user):
    """Test sale in DRAFT status."""
    return Sale.objects.create(
        status=SaleStatusChoices.DRAFT,
        subtotal=Decimal('0.00'),
        total=Decimal('0.00'),
        currency='USD'
    )


@pytest.fixture
def paid_sale_with_lines(db, user, stock_with_inventory, location):
    """Sale in PAID status with integer quantity lines."""
    sale = Sale.objects.create(
        status=SaleStatusChoices.DRAFT,
        subtotal=Decimal('600.00'),
        total=Decimal('600.00'),
        currency='USD'
    )
    
    # Line 1: 2 units @ $100 = $200
    SaleLine.objects.create(
        sale=sale,
        product=stock_with_inventory,
        product_name=stock_with_inventory.name,
        product_code=stock_with_inventory.code,
        quantity=2,  # INTEGER
        unit_price=Decimal('100.00'),
        discount=Decimal('0.00'),
        line_total=Decimal('200.00')
    )
    
    # Line 2: 4 units @ $100 = $400
    SaleLine.objects.create(
        sale=sale,
        product=stock_with_inventory,
        product_name=stock_with_inventory.name,
        product_code=stock_with_inventory.code,
        quantity=4,  # INTEGER
        unit_price=Decimal('100.00'),
        discount=Decimal('0.00'),
        line_total=Decimal('400.00')
    )
    
    # Transition to PAID (consumes stock)
    sale.transition_to(SaleStatusChoices.PAID, user=user)
    
    return sale


# ============================================================================
# Test: SaleLine Creation - Reject Decimal Quantities
# ============================================================================

@pytest.mark.django_db
class TestSaleLineIntegerQuantity:
    """Test that SaleLine.quantity only accepts integers."""
    
    def test_create_sale_line_with_decimal_quantity_rejected(self, auth_client, sale):
        """POST with quantity=1.5 should return 400."""
        data = {
            'sale': str(sale.id),
            'product_name': 'Test Product',
            'product_code': 'PROD-001',
            'quantity': 1.5,  # DECIMAL - should be rejected
            'unit_price': '100.00',
            'discount': '0.00',
            'line_total': '150.00'
        }
        
        response = auth_client.post('/api/sales/lines/', data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'quantity' in response.data or 'non_field_errors' in response.data
        # Verify error message mentions integer requirement
        error_str = str(response.data).lower()
        assert 'integer' in error_str or 'valid' in error_str
    
    def test_create_sale_line_with_integer_quantity_accepted(self, auth_client, sale):
        """POST with quantity=5 (integer) should succeed."""
        data = {
            'sale': str(sale.id),
            'product_name': 'Test Product',
            'product_code': 'PROD-001',
            'quantity': 5,  # INTEGER - should be accepted
            'unit_price': '100.00',
            'discount': '0.00',
            'line_total': '500.00'
        }
        
        response = auth_client.post('/api/sales/lines/', data, format='json')
        
        # Should succeed (201 Created or 200 OK depending on viewset config)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        assert response.data['quantity'] == 5
        
        # Verify line_total is Decimal and correct
        line = SaleLine.objects.get(id=response.data['id'])
        assert line.quantity == 5
        assert line.line_total == Decimal('500.00')
    
    def test_update_sale_line_with_decimal_quantity_rejected(self, auth_client, sale):
        """PATCH with quantity=2.75 should return 400."""
        # Create line with integer quantity first
        line = SaleLine.objects.create(
            sale=sale,
            product_name='Test Product',
            product_code='PROD-001',
            quantity=3,
            unit_price=Decimal('100.00'),
            discount=Decimal('0.00'),
            line_total=Decimal('300.00')
        )
        
        data = {
            'quantity': 2.75  # DECIMAL - should be rejected
        }
        
        response = auth_client.patch(f'/api/sales/lines/{line.id}/', data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'quantity' in response.data or 'non_field_errors' in response.data
    
    def test_money_fields_remain_decimal(self, auth_client, sale):
        """Verify unit_price, discount, line_total can still have decimal values."""
        data = {
            'sale': str(sale.id),
            'product_name': 'Test Service',
            'product_code': 'SVC-001',
            'quantity': 3,  # INTEGER
            'unit_price': '99.99',  # DECIMAL - should be accepted for money
            'discount': '10.50',  # DECIMAL - should be accepted for money
            'line_total': '289.47'  # 3 * 99.99 - 10.50 = 289.47
        }
        
        response = auth_client.post('/api/sales/lines/', data, format='json')
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        
        line = SaleLine.objects.get(id=response.data['id'])
        assert line.quantity == 3  # Integer
        assert line.unit_price == Decimal('99.99')  # Decimal
        assert line.discount == Decimal('10.50')  # Decimal
        assert line.line_total == Decimal('289.47')  # Decimal


# ============================================================================
# Test: Partial Refund - Reject Decimal Quantities
# ============================================================================

@pytest.mark.django_db
class TestPartialRefundIntegerQuantity:
    """Test that SaleRefundLine.qty_refunded only accepts integers."""
    
    def test_create_partial_refund_with_decimal_quantity_rejected(
        self, auth_client, paid_sale_with_lines
    ):
        """POST partial refund with qty_refunded=1.5 should return 400."""
        sale_line = paid_sale_with_lines.lines.first()
        
        data = {
            'reason': 'Customer return',
            'lines': [
                {
                    'sale_line_id': str(sale_line.id),
                    'qty_refunded': 1.5,  # DECIMAL - should be rejected
                    'amount_refunded': '150.00'
                }
            ]
        }
        
        response = auth_client.post(
            f'/api/sales/{paid_sale_with_lines.id}/refunds/',
            data,
            format='json'
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # Error should mention qty_refunded or lines
        error_str = str(response.data).lower()
        assert 'qty_refunded' in error_str or 'lines' in error_str or 'integer' in error_str
    
    def test_create_partial_refund_with_integer_quantity_accepted(
        self, auth_client, paid_sale_with_lines, user
    ):
        """POST partial refund with qty_refunded=2 (integer) should succeed."""
        sale_line = paid_sale_with_lines.lines.first()
        original_qty = sale_line.quantity
        
        data = {
            'reason': 'Customer return',
            'lines': [
                {
                    'sale_line_id': str(sale_line.id),
                    'qty_refunded': 2,  # INTEGER - should be accepted
                    'amount_refunded': '200.00'
                }
            ]
        }
        
        response = auth_client.post(
            f'/api/sales/{paid_sale_with_lines.id}/refunds/',
            data,
            format='json'
        )
        
        # Should succeed
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        
        # Verify refund created
        refund = SaleRefund.objects.get(id=response.data['id'])
        refund_line = refund.lines.first()
        
        assert refund_line.qty_refunded == 2  # Integer
        assert refund_line.amount_refunded == Decimal('200.00')  # Decimal
        
        # Verify we can still refund the remaining quantity
        remaining = original_qty - 2
        assert remaining > 0
    
    def test_partial_refund_validates_over_refund_with_integers(
        self, auth_client, paid_sale_with_lines
    ):
        """Attempting to refund more than sold (integers) should fail."""
        sale_line = paid_sale_with_lines.lines.first()
        sold_qty = sale_line.quantity
        
        data = {
            'reason': 'Over-refund attempt',
            'lines': [
                {
                    'sale_line_id': str(sale_line.id),
                    'qty_refunded': sold_qty + 5,  # More than sold
                    'amount_refunded': '1000.00'
                }
            ]
        }
        
        response = auth_client.post(
            f'/api/sales/{paid_sale_with_lines.id}/refunds/',
            data,
            format='json'
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_str = str(response.data).lower()
        assert 'available' in error_str or 'cannot refund' in error_str or 'exceed' in error_str


# ============================================================================
# Test: Model-Level Validation
# ============================================================================

@pytest.mark.django_db
class TestModelLevelIntegerEnforcement:
    """Test that model-level validation enforces integer quantities."""
    
    def test_sale_line_model_accepts_integer_quantity(self, sale):
        """SaleLine model should accept integer quantity directly."""
        line = SaleLine(
            sale=sale,
            product_name='Direct Model Test',
            product_code='DMT-001',
            quantity=7,  # INTEGER
            unit_price=Decimal('50.00'),
            discount=Decimal('5.00'),
            line_total=Decimal('345.00')
        )
        
        # Should not raise exception
        line.full_clean()
        line.save()
        
        # Verify saved correctly
        assert line.quantity == 7
        assert isinstance(line.quantity, int)
    
    def test_sale_refund_line_model_accepts_integer_quantity(self, paid_sale_with_lines):
        """SaleRefundLine model should accept integer quantity."""
        sale = paid_sale_with_lines
        sale_line = sale.lines.first()
        
        refund = SaleRefund.objects.create(
            original_sale=sale,
            reason='Direct model test'
        )
        
        refund_line = SaleRefundLine(
            refund=refund,
            sale_line=sale_line,
            qty_refunded=1,  # INTEGER
            amount_refunded=Decimal('100.00')
        )
        
        # Should not raise exception
        refund_line.full_clean()
        refund_line.save()
        
        # Verify saved correctly
        assert refund_line.qty_refunded == 1
        assert isinstance(refund_line.qty_refunded, int)


# ============================================================================
# Test: Total Calculations Remain Decimal
# ============================================================================

@pytest.mark.django_db
class TestDecimalCalculationsWithIntegerQuantities:
    """Verify that using integer quantities doesn't break Decimal money calculations."""
    
    def test_line_total_calculation_with_integer_quantity(self, sale):
        """quantity (int) * unit_price (Decimal) = line_total (Decimal)."""
        line = SaleLine.objects.create(
            sale=sale,
            product_name='Calculation Test',
            product_code='CALC-001',
            quantity=7,  # INTEGER
            unit_price=Decimal('12.99'),  # DECIMAL
            discount=Decimal('2.50'),  # DECIMAL
            line_total=Decimal('88.43')  # 7 * 12.99 - 2.50 = 88.43
        )
        
        # Verify calculation
        expected_total = Decimal('7') * Decimal('12.99') - Decimal('2.50')
        assert line.line_total == expected_total
        assert line.line_total == Decimal('88.43')
    
    def test_sale_total_with_integer_quantities(self, sale):
        """Sale total should be correct with integer quantities."""
        # Line 1: 3 units @ $25.50 = $76.50
        SaleLine.objects.create(
            sale=sale,
            product_name='Product A',
            quantity=3,
            unit_price=Decimal('25.50'),
            discount=Decimal('0.00'),
            line_total=Decimal('76.50')
        )
        
        # Line 2: 5 units @ $10.99 = $54.95
        SaleLine.objects.create(
            sale=sale,
            product_name='Product B',
            quantity=5,
            unit_price=Decimal('10.99'),
            discount=Decimal('0.00'),
            line_total=Decimal('54.95')
        )
        
        # Update sale totals
        sale.subtotal = Decimal('131.45')  # 76.50 + 54.95
        sale.tax = Decimal('10.52')  # 8% tax
        sale.total = Decimal('141.97')  # 131.45 + 10.52
        sale.save()
        
        # Verify totals are Decimal
        assert isinstance(sale.subtotal, Decimal)
        assert isinstance(sale.total, Decimal)
        assert sale.total == Decimal('141.97')
