"""
Tests for refund failure scenarios - verifying transaction rollback consistency.

Critical Behavior: When a refund fails inside transaction.atomic:
- NO SaleRefund should be persisted in FAILED status (rollback cleans it)
- Stock should NOT change (no partial reversals)
- Error should be logged (structured, no PHI/PII)
- Client receives appropriate HTTP error status

This prevents "FAILED refund ghosts" that would pollute the database.
"""

import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APIClient

from apps.sales.models import Sale, SaleLine, SaleRefund, SaleStatusChoices, SaleRefundStatusChoices
from apps.sales.services import refund_partial_for_sale
from apps.products.models import Product
from apps.authz.models import User
from apps.stock.models import StockOnHand, StockMove


@pytest.mark.django_db
class TestRefundFailureRollback:
    """Test that failed refunds don't leave FAILED ghosts in database."""
    
    @pytest.fixture
    def user(self):
        """Create test user."""
        return User.objects.create_user(
            username='refund_test_user',
            email='refund@example.com',
            password='testpass123'
        )
    
    @pytest.fixture
    def product(self):
        """Create test product."""
        return Product.objects.create(
            name='Rollback Test Product',
            sku='ROLLBACK-001',
            unit_price=Decimal('100.00'),
            is_service=False
        )
    
    @pytest.fixture
    def paid_sale(self, user, product):
        """Create PAID sale with 5 units."""
        sale = Sale.objects.create(
            patient=None,
            appointment=None,
            status=SaleStatusChoices.PAID,
            created_by=user
        )
        
        SaleLine.objects.create(
            sale=sale,
            product=product,
            product_name=product.name,
            quantity=5,
            unit_price=Decimal('100.00'),
            discount=Decimal('0.00'),
            line_total=Decimal('500.00')
        )
        
        return sale
    
    def test_over_refund_raises_validation_error_no_failed_ghost(self, paid_sale, user):
        """
        Test over-refund validation failure.
        
        Scenario: Attempt to refund MORE than sold (qty=10 when only 5 sold).
        
        Expected:
        - ValidationError raised
        - NO SaleRefund persisted (count = 0)
        - NO FAILED status in database
        """
        sale_line = paid_sale.lines.first()
        initial_refund_count = SaleRefund.objects.filter(sale=paid_sale).count()
        
        # Attempt over-refund (10 units when only 5 sold)
        with pytest.raises(ValidationError) as exc_info:
            refund_partial_for_sale(
                sale=paid_sale,
                refund_payload={
                    'reason': 'Over-refund test',
                    'idempotency_key': 'over-refund-key',
                    'lines': [
                        {
                            'sale_line_id': str(sale_line.id),
                            'qty_refunded': 10,  # INVALID: more than sold
                            'amount_refunded': Decimal('1000.00')
                        }
                    ]
                },
                created_by=user
            )
        
        # Assertions: NO refund persisted
        assert 'qty_refunded' in str(exc_info.value).lower() or 'exceed' in str(exc_info.value).lower()
        final_refund_count = SaleRefund.objects.filter(sale=paid_sale).count()
        assert final_refund_count == initial_refund_count  # No increase (rollback worked)
        
        # Verify NO FAILED status exists
        failed_refunds = SaleRefund.objects.filter(
            sale=paid_sale,
            status=SaleRefundStatusChoices.FAILED
        )
        assert failed_refunds.count() == 0  # NO FAILED ghosts
    
    def test_invalid_sale_line_id_no_failed_ghost(self, paid_sale, user):
        """
        Test validation error for invalid sale_line_id.
        
        Scenario: Reference non-existent sale line.
        
        Expected:
        - ValidationError raised
        - NO SaleRefund persisted
        - NO FAILED status
        """
        initial_count = SaleRefund.objects.filter(sale=paid_sale).count()
        
        # Invalid UUID
        fake_uuid = '00000000-0000-0000-0000-000000000000'
        
        with pytest.raises(ValidationError) as exc_info:
            refund_partial_for_sale(
                sale=paid_sale,
                refund_payload={
                    'reason': 'Invalid line test',
                    'lines': [
                        {
                            'sale_line_id': fake_uuid,  # INVALID
                            'qty_refunded': 1
                        }
                    ]
                },
                created_by=user
            )
        
        # Assertions
        assert 'not found' in str(exc_info.value).lower()
        assert SaleRefund.objects.filter(sale=paid_sale).count() == initial_count
        assert SaleRefund.objects.filter(
            sale=paid_sale,
            status=SaleRefundStatusChoices.FAILED
        ).count() == 0
    
    def test_stock_not_changed_on_refund_failure(self, paid_sale, user, product):
        """
        Test stock integrity on refund failure.
        
        Scenario: Refund fails mid-processing.
        
        Expected:
        - Stock levels unchanged (no partial reversals)
        - StockMove count unchanged
        """
        sale_line = paid_sale.lines.first()
        
        # Get initial stock state
        initial_stock_moves = StockMove.objects.filter(sale=paid_sale).count()
        initial_stock_on_hand = StockOnHand.objects.filter(product=product).count()
        
        # Attempt invalid refund (over-refund)
        with pytest.raises(ValidationError):
            refund_partial_for_sale(
                sale=paid_sale,
                refund_payload={
                    'lines': [
                        {
                            'sale_line_id': str(sale_line.id),
                            'qty_refunded': 100  # Way over
                        }
                    ]
                },
                created_by=user
            )
        
        # Assertions: Stock unchanged
        final_stock_moves = StockMove.objects.filter(sale=paid_sale).count()
        final_stock_on_hand = StockOnHand.objects.filter(product=product).count()
        
        assert final_stock_moves == initial_stock_moves  # No new moves
        assert final_stock_on_hand == initial_stock_on_hand  # No stock changes
    
    def test_partial_refund_then_over_refund_fails_cleanly(self, paid_sale, user):
        """
        Test sequence: successful refund, then failed over-refund.
        
        Scenario:
        1. Refund 2 units (success)
        2. Attempt refund 5 units (fail - only 3 available)
        
        Expected:
        - First refund persisted (COMPLETED)
        - Second refund NOT persisted (rollback)
        - Count = 1 (only successful refund)
        """
        sale_line = paid_sale.lines.first()
        
        # First refund: 2 units (success)
        refund1 = refund_partial_for_sale(
            sale=paid_sale,
            refund_payload={
                'idempotency_key': 'first-refund',
                'lines': [{'sale_line_id': str(sale_line.id), 'qty_refunded': 2}]
            },
            created_by=user
        )
        
        assert refund1.status == SaleRefundStatusChoices.COMPLETED
        assert SaleRefund.objects.filter(sale=paid_sale).count() == 1
        
        # Second refund: 5 units (fail - only 3 available)
        with pytest.raises(ValidationError):
            refund_partial_for_sale(
                sale=paid_sale,
                refund_payload={
                    'idempotency_key': 'second-refund-fail',
                    'lines': [{'sale_line_id': str(sale_line.id), 'qty_refunded': 5}]
                },
                created_by=user
            )
        
        # Assertions: Only first refund exists
        assert SaleRefund.objects.filter(sale=paid_sale).count() == 1
        assert SaleRefund.objects.filter(
            sale=paid_sale,
            status=SaleRefundStatusChoices.FAILED
        ).count() == 0  # NO FAILED ghosts


@pytest.mark.django_db
class TestRefundFailureAPI:
    """Test refund failure scenarios via REST API."""
    
    @pytest.fixture
    def auth_client(self, user):
        """Create authenticated API client."""
        client = APIClient()
        client.force_authenticate(user=user)
        return client
    
    @pytest.fixture
    def user(self):
        """Create user with refund permissions."""
        user = User.objects.create_user(
            username='api_refund_user',
            email='api_refund@example.com',
            password='testpass123'
        )
        from apps.authz.models import Role
        reception_role = Role.objects.get(name='Reception')
        user.user_role.add(reception_role)
        return user
    
    @pytest.fixture
    def paid_sale(self, user):
        """Create PAID sale."""
        sale = Sale.objects.create(
            patient=None,
            appointment=None,
            status=SaleStatusChoices.PAID,
            created_by=user
        )
        
        product = Product.objects.create(
            name='API Refund Product',
            sku='API-REFUND-001',
            unit_price=Decimal('50.00')
        )
        
        SaleLine.objects.create(
            sale=sale,
            product=product,
            product_name=product.name,
            quantity=3,
            unit_price=Decimal('50.00'),
            discount=Decimal('0.00'),
            line_total=Decimal('150.00')
        )
        
        return sale
    
    def test_api_over_refund_returns_400_no_failed_ghost(self, auth_client, paid_sale):
        """
        Test API response for over-refund.
        
        Expected:
        - HTTP 400 BAD REQUEST
        - Error message in response
        - NO SaleRefund persisted
        - NO FAILED status in DB
        """
        sale_line = paid_sale.lines.first()
        initial_count = SaleRefund.objects.filter(sale=paid_sale).count()
        
        payload = {
            'reason': 'API over-refund test',
            'idempotency_key': 'api-over-refund',
            'lines': [
                {
                    'sale_line_id': str(sale_line.id),
                    'qty_refunded': 10,  # INVALID: only 3 sold
                }
            ]
        }
        
        response = auth_client.post(
            f'/api/sales/{paid_sale.id}/refunds/',
            data=payload,
            format='json'
        )
        
        # Assertions
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data or 'detail' in response.data
        
        # Verify NO refund persisted
        assert SaleRefund.objects.filter(sale=paid_sale).count() == initial_count
        assert SaleRefund.objects.filter(
            sale=paid_sale,
            status=SaleRefundStatusChoices.FAILED
        ).count() == 0
    
    def test_api_invalid_sale_line_returns_400_no_failed_ghost(self, auth_client, paid_sale):
        """
        Test API validation for invalid sale_line_id.
        
        Expected:
        - HTTP 400 BAD REQUEST
        - NO SaleRefund persisted
        """
        initial_count = SaleRefund.objects.filter(sale=paid_sale).count()
        
        payload = {
            'lines': [
                {
                    'sale_line_id': '00000000-0000-0000-0000-000000000000',  # Invalid
                    'qty_refunded': 1
                }
            ]
        }
        
        response = auth_client.post(
            f'/api/sales/{paid_sale.id}/refunds/',
            data=payload,
            format='json'
        )
        
        # Assertions
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert SaleRefund.objects.filter(sale=paid_sale).count() == initial_count
        assert SaleRefund.objects.filter(
            sale=paid_sale,
            status=SaleRefundStatusChoices.FAILED
        ).count() == 0


@pytest.mark.django_db
class TestRefundTransactionAtomicity:
    """Test transaction atomicity guarantees for refunds."""
    
    @pytest.fixture
    def user(self):
        """Create test user."""
        return User.objects.create_user(
            username='atomic_user',
            email='atomic@example.com',
            password='testpass123'
        )
    
    @pytest.fixture
    def paid_sale(self, user):
        """Create PAID sale."""
        sale = Sale.objects.create(
            patient=None,
            status=SaleStatusChoices.PAID,
            created_by=user
        )
        
        product = Product.objects.create(
            name='Atomic Test Product',
            sku='ATOMIC-001',
            unit_price=Decimal('25.00')
        )
        
        SaleLine.objects.create(
            sale=sale,
            product=product,
            product_name=product.name,
            quantity=10,
            unit_price=Decimal('25.00'),
            discount=Decimal('0.00'),
            line_total=Decimal('250.00')
        )
        
        return sale
    
    def test_refund_creation_is_all_or_nothing(self, paid_sale, user):
        """
        Test atomic transaction behavior.
        
        Scenario: Multi-line refund where one line is invalid.
        
        Expected:
        - Entire refund rolled back (not just failed line)
        - NO partial SaleRefundLine objects persisted
        - NO SaleRefund object persisted
        """
        sale_line = paid_sale.lines.first()
        
        # Payload with one valid, one invalid line (over-refund)
        with pytest.raises(ValidationError):
            refund_partial_for_sale(
                sale=paid_sale,
                refund_payload={
                    'lines': [
                        {'sale_line_id': str(sale_line.id), 'qty_refunded': 2},  # Valid
                        {'sale_line_id': str(sale_line.id), 'qty_refunded': 100}  # INVALID
                    ]
                },
                created_by=user
            )
        
        # Assertions: NOTHING persisted (all-or-nothing)
        assert SaleRefund.objects.filter(sale=paid_sale).count() == 0
        
        # Verify no orphaned refund lines
        from apps.sales.models import SaleRefundLine
        assert SaleRefundLine.objects.filter(refund__sale=paid_sale).count() == 0
