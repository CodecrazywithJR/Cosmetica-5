"""
Layer 3 B: Sales Refund with Stock Restoration Tests

Test coverage:
1. Refund paid sale creates REFUND_IN moves matching original batches
2. Refund non-paid sale is rejected with clear error
3. Idempotency: repeated refund calls don't duplicate reversals
4. Rollback: if error during refund, status unchanged, no partial moves
5. Reception user can execute refund via transition endpoint
6. StockOnHand restored to pre-sale levels after refund

Run: DATABASE_HOST=localhost pytest apps/api/tests/test_layer3_b_refund_stock.py -v
"""
import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status as http_status

from apps.sales.models import Sale, SaleLine, SaleStatusChoices
from apps.clinical.models import Patient
from apps.products.models import Product
from apps.stock.models import (
    StockLocation,
    StockBatch,
    StockMove,
    StockOnHand,
    StockMoveTypeChoices,
)
from apps.sales.services import refund_stock_for_sale, consume_stock_for_sale

User = get_user_model()


# ============================================================================
# Fixtures (reuse from Layer 3 A tests)
# ============================================================================

@pytest.fixture
def patient():
    """Create a test patient."""
    return Patient.objects.create(
        first_name='Jane',
        last_name='Smith',
        birth_date='1985-05-15'
    )


@pytest.fixture
def product():
    """Create a test product."""
    try:
        return Product.objects.create(
            sku='FILLER-1ML',
            name='Dermal Filler 1ml',
            description='Hyaluronic acid filler',
            price=Decimal('300.00')
        )
    except Exception:
        return Product.objects.create(
            sku='FILLER-1ML',
            name='Dermal Filler 1ml'
        )


@pytest.fixture
def main_warehouse():
    """Create MAIN-WAREHOUSE location."""
    location, _ = StockLocation.objects.get_or_create(
        code='MAIN-WAREHOUSE',
        defaults={
            'name': 'Main Warehouse',
            'is_active': True
        }
    )
    return location


@pytest.fixture
def batch_a(product):
    """Create batch A (expires in 30 days)."""
    return StockBatch.objects.create(
        product=product,
        batch_number='BATCH-A-001',
        expiry_date=timezone.now().date() + timedelta(days=30),
        received_at=timezone.now().date()
    )


@pytest.fixture
def batch_b(product):
    """Create batch B (expires in 60 days)."""
    return StockBatch.objects.create(
        product=product,
        batch_number='BATCH-B-002',
        expiry_date=timezone.now().date() + timedelta(days=60),
        received_at=timezone.now().date()
    )


@pytest.fixture
def reception_user():
    """Create a Reception group user."""
    from django.contrib.auth.models import Group
    user = User.objects.create_user(
        email='reception2@test.com',
        password='testpass123'
    )
    reception_group, _ = Group.objects.get_or_create(name='Reception')
    user.groups.add(reception_group)
    return user


@pytest.fixture
def clinicalops_user():
    """Create a ClinicalOps group user."""
    from django.contrib.auth.models import Group
    user = User.objects.create_user(
        email='clinicalops2@test.com',
        password='testpass123'
    )
    clinicalops_group, _ = Group.objects.get_or_create(name='ClinicalOps')
    user.groups.add(clinicalops_group)
    return user


# ============================================================================
# Test Class 1: Refund Creates REFUND_IN Moves Matching Batches
# ============================================================================

@pytest.mark.django_db
class TestRefundCreatesMatchingReversalMoves:
    """Test that refund creates REFUND_IN moves reversing exact batches consumed."""
    
    def test_refund_paid_sale_creates_refund_in_moves_matching_batches(
        self, patient, product, main_warehouse, batch_a, batch_b
    ):
        """
        GIVEN a paid sale that consumed stock from 2 batches (FEFO)
        WHEN sale transitions to refunded
        THEN REFUND_IN moves created for same batches with positive quantities
        """
        # Add stock to both batches (batch_a expires first -> FEFO picks it first)
        StockOnHand.objects.create(
            product=product,
            location=main_warehouse,
            batch=batch_a,
            quantity_on_hand=3  # Only 3 units in expiring batch
        )
        StockOnHand.objects.create(
            product=product,
            location=main_warehouse,
            batch=batch_b,
            quantity_on_hand=50
        )
        
        # Create sale needing 10 units (3 from batch_a, 7 from batch_b)
        sale = Sale.objects.create(
            patient=patient,
            status=SaleStatusChoices.PENDING,
            subtotal=Decimal('3000.00'),
            tax=Decimal('0.00'),
            total=Decimal('3000.00')
        )
        
        SaleLine.objects.create(
            sale=sale,
            product=product,
            product_name='Dermal Filler 1ml',
            quantity=Decimal('10.00'),
            unit_price=Decimal('300.00'),
            line_total=Decimal('3000.00')
        )
        
        # Transition to paid (consumes stock via FEFO)
        sale.transition_to(SaleStatusChoices.PAID, user=None)
        
        # Verify stock consumed from both batches
        out_moves = StockMove.objects.filter(
            sale=sale,
            move_type=StockMoveTypeChoices.SALE_OUT
        ).order_by('batch__expiry_date')
        
        assert out_moves.count() == 2
        assert out_moves[0].batch == batch_a
        assert out_moves[0].quantity == -3  # Consumed 3 from expiring batch
        assert out_moves[1].batch == batch_b
        assert out_moves[1].quantity == -7  # Consumed 7 from fresh batch
        
        # Verify StockOnHand updated
        assert StockOnHand.objects.get(
            product=product, location=main_warehouse, batch=batch_a
        ).quantity_on_hand == 0  # All consumed
        
        assert StockOnHand.objects.get(
            product=product, location=main_warehouse, batch=batch_b
        ).quantity_on_hand == 43  # 50 - 7
        
        # NOW REFUND THE SALE
        sale.transition_to(SaleStatusChoices.REFUNDED, reason='Customer request', user=None)
        
        # Verify sale is refunded
        assert sale.status == SaleStatusChoices.REFUNDED
        assert sale.refund_reason == 'Customer request'
        
        # Verify REFUND_IN moves created
        refund_moves = StockMove.objects.filter(
            sale=sale,
            move_type=StockMoveTypeChoices.REFUND_IN
        ).order_by('batch__expiry_date')
        
        assert refund_moves.count() == 2
        
        # First refund: batch_a gets 3 units back
        refund_a = refund_moves[0]
        assert refund_a.batch == batch_a
        assert refund_a.quantity == 3  # Positive (reversing -3)
        assert refund_a.reversed_move == out_moves[0]  # Linked to original OUT
        assert refund_a.sale == sale
        assert refund_a.reference_type == 'SaleRefund'
        
        # Second refund: batch_b gets 7 units back
        refund_b = refund_moves[1]
        assert refund_b.batch == batch_b
        assert refund_b.quantity == 7  # Positive (reversing -7)
        assert refund_b.reversed_move == out_moves[1]
        
        # Verify StockOnHand restored
        assert StockOnHand.objects.get(
            product=product, location=main_warehouse, batch=batch_a
        ).quantity_on_hand == 3  # Restored
        
        assert StockOnHand.objects.get(
            product=product, location=main_warehouse, batch=batch_b
        ).quantity_on_hand == 50  # Restored
    
    def test_refund_sale_with_single_batch_consumption(
        self, patient, product, main_warehouse, batch_a
    ):
        """
        GIVEN a paid sale that consumed from single batch
        WHEN refunded
        THEN single REFUND_IN move created
        """
        StockOnHand.objects.create(
            product=product,
            location=main_warehouse,
            batch=batch_a,
            quantity_on_hand=20
        )
        
        sale = Sale.objects.create(
            patient=patient,
            status=SaleStatusChoices.PENDING,
            subtotal=Decimal('1500.00'),
            tax=Decimal('0.00'),
            total=Decimal('1500.00')
        )
        
        SaleLine.objects.create(
            sale=sale,
            product=product,
            product_name='Dermal Filler 1ml',
            quantity=Decimal('5.00'),
            unit_price=Decimal('300.00'),
            line_total=Decimal('1500.00')
        )
        
        # Pay and refund
        sale.transition_to(SaleStatusChoices.PAID, user=None)
        sale.transition_to(SaleStatusChoices.REFUNDED, user=None)
        
        # Verify single refund move
        refund_moves = StockMove.objects.filter(
            sale=sale,
            move_type=StockMoveTypeChoices.REFUND_IN
        )
        
        assert refund_moves.count() == 1
        assert refund_moves.first().batch == batch_a
        assert refund_moves.first().quantity == 5
        
        # Stock restored
        assert StockOnHand.objects.get(
            product=product, location=main_warehouse, batch=batch_a
        ).quantity_on_hand == 20


# ============================================================================
# Test Class 2: Refund Non-Paid Sale is Rejected
# ============================================================================

@pytest.mark.django_db
class TestRefundNonPaidSaleRejected:
    """Test that refund rejects sales not in PAID status."""
    
    def test_refund_draft_sale_raises_validation_error(
        self, patient, product
    ):
        """
        GIVEN a sale in DRAFT status
        WHEN attempting to transition to REFUNDED
        THEN ValidationError raised (invalid transition)
        """
        sale = Sale.objects.create(
            patient=patient,
            status=SaleStatusChoices.DRAFT,
            subtotal=Decimal('300.00'),
            tax=Decimal('0.00'),
            total=Decimal('300.00')
        )
        
        with pytest.raises(ValidationError) as exc_info:
            sale.transition_to(SaleStatusChoices.REFUNDED, reason='Test')
        
        assert 'Invalid transition from draft to refunded' in str(exc_info.value)
    
    def test_refund_pending_sale_raises_validation_error(
        self, patient, product
    ):
        """
        GIVEN a sale in PENDING status (not yet paid)
        WHEN attempting to transition to REFUNDED
        THEN ValidationError raised
        """
        sale = Sale.objects.create(
            patient=patient,
            status=SaleStatusChoices.PENDING,
            subtotal=Decimal('300.00'),
            tax=Decimal('0.00'),
            total=Decimal('300.00')
        )
        
        with pytest.raises(ValidationError) as exc_info:
            sale.transition_to(SaleStatusChoices.REFUNDED, reason='Test')
        
        assert 'Invalid transition from pending to refunded' in str(exc_info.value)
    
    def test_refund_cancelled_sale_raises_validation_error(
        self, patient
    ):
        """
        GIVEN a sale in CANCELLED status
        WHEN attempting to transition to REFUNDED
        THEN ValidationError raised (terminal state)
        """
        sale = Sale.objects.create(
            patient=patient,
            status=SaleStatusChoices.CANCELLED,
            subtotal=Decimal('300.00'),
            tax=Decimal('0.00'),
            total=Decimal('300.00'),
            cancellation_reason='Customer cancelled'
        )
        
        with pytest.raises(ValidationError) as exc_info:
            sale.transition_to(SaleStatusChoices.REFUNDED, reason='Test')
        
        assert 'Invalid transition' in str(exc_info.value)


# ============================================================================
# Test Class 3: Idempotency
# ============================================================================

@pytest.mark.django_db
class TestRefundIdempotency:
    """Test that refund is idempotent - no duplicate reversals."""
    
    def test_repeated_refund_does_not_duplicate_refund_in_moves(
        self, patient, product, main_warehouse, batch_a
    ):
        """
        GIVEN a sale already refunded
        WHEN refund_stock_for_sale() called again
        THEN returns existing refund moves, no duplicates created
        """
        StockOnHand.objects.create(
            product=product,
            location=main_warehouse,
            batch=batch_a,
            quantity_on_hand=10
        )
        
        sale = Sale.objects.create(
            patient=patient,
            status=SaleStatusChoices.PENDING,
            subtotal=Decimal('600.00'),
            tax=Decimal('0.00'),
            total=Decimal('600.00')
        )
        
        SaleLine.objects.create(
            sale=sale,
            product=product,
            product_name='Dermal Filler 1ml',
            quantity=Decimal('2.00'),
            unit_price=Decimal('300.00'),
            line_total=Decimal('600.00')
        )
        
        # Pay sale
        sale.transition_to(SaleStatusChoices.PAID, user=None)
        
        # Verify stock consumed
        assert StockOnHand.objects.get(
            product=product, location=main_warehouse, batch=batch_a
        ).quantity_on_hand == 8  # 10 - 2
        
        # First refund
        refund_moves_1 = refund_stock_for_sale(sale=sale, created_by=None)
        assert len(refund_moves_1) == 1
        
        # Verify stock restored
        assert StockOnHand.objects.get(
            product=product, location=main_warehouse, batch=batch_a
        ).quantity_on_hand == 10  # Restored
        
        # Second refund (idempotent call)
        refund_moves_2 = refund_stock_for_sale(sale=sale, created_by=None)
        
        # Should return same moves, not create new ones
        assert len(refund_moves_2) == 1
        assert refund_moves_2[0].id == refund_moves_1[0].id  # Same instance
        
        # Total REFUND_IN moves should still be 1
        total_refund_moves = StockMove.objects.filter(
            sale=sale,
            move_type=StockMoveTypeChoices.REFUND_IN
        ).count()
        assert total_refund_moves == 1
        
        # Stock on hand unchanged (not doubled)
        assert StockOnHand.objects.get(
            product=product, location=main_warehouse, batch=batch_a
        ).quantity_on_hand == 10


# ============================================================================
# Test Class 4: Rollback on Error
# ============================================================================

@pytest.mark.django_db
class TestRefundRollbackOnError:
    """Test that refund rolls back on error - no partial state changes."""
    
    def test_refund_rolls_back_if_error_during_processing(
        self, patient, product, main_warehouse, batch_a, monkeypatch
    ):
        """
        GIVEN a paid sale
        WHEN refund encounters error mid-processing
        THEN status NOT changed, no refund moves created
        """
        StockOnHand.objects.create(
            product=product,
            location=main_warehouse,
            batch=batch_a,
            quantity_on_hand=10
        )
        
        sale = Sale.objects.create(
            patient=patient,
            status=SaleStatusChoices.PENDING,
            subtotal=Decimal('300.00'),
            tax=Decimal('0.00'),
            total=Decimal('300.00')
        )
        
        SaleLine.objects.create(
            sale=sale,
            product=product,
            product_name='Dermal Filler 1ml',
            quantity=Decimal('1.00'),
            unit_price=Decimal('300.00'),
            line_total=Decimal('300.00')
        )
        
        # Pay sale
        sale.transition_to(SaleStatusChoices.PAID, user=None)
        
        # Mock StockOnHand.save() to raise error during refund
        original_save = StockOnHand.save
        
        def failing_save(self, *args, **kwargs):
            if hasattr(self, '_test_fail_on_refund'):
                raise RuntimeError("Simulated database error")
            return original_save(self, *args, **kwargs)
        
        monkeypatch.setattr(StockOnHand, 'save', failing_save)
        
        # Mark stock to fail on next save
        stock = StockOnHand.objects.get(
            product=product, location=main_warehouse, batch=batch_a
        )
        stock._test_fail_on_refund = True
        
        # Attempt refund (should fail and rollback)
        with pytest.raises(RuntimeError) as exc_info:
            sale.transition_to(SaleStatusChoices.REFUNDED, reason='Test', user=None)
        
        assert "Simulated database error" in str(exc_info.value)
        
        # Verify rollback: sale status NOT changed
        sale.refresh_from_db()
        assert sale.status == SaleStatusChoices.PAID  # Still paid
        assert sale.refund_reason is None or sale.refund_reason == ''
        
        # Verify no refund moves created
        refund_moves = StockMove.objects.filter(
            sale=sale,
            move_type=StockMoveTypeChoices.REFUND_IN
        )
        assert refund_moves.count() == 0
        
        # Stock on hand unchanged (still consumed)
        stock.refresh_from_db()
        assert stock.quantity_on_hand == 9  # Still 10 - 1


# ============================================================================
# Test Class 5: Reception User Can Execute Refund
# ============================================================================

@pytest.mark.django_db
class TestReceptionCanExecuteRefund:
    """Test that Reception users can execute refund via API."""
    
    def test_reception_user_can_refund_paid_sale_via_api(
        self, patient, product, main_warehouse, batch_a, reception_user
    ):
        """
        GIVEN a reception user and a paid sale
        WHEN reception user calls /sales/{id}/transition/ with new_status=refunded
        THEN sale refunded, stock restored, 200 OK
        """
        StockOnHand.objects.create(
            product=product,
            location=main_warehouse,
            batch=batch_a,
            quantity_on_hand=10
        )
        
        sale = Sale.objects.create(
            patient=patient,
            status=SaleStatusChoices.PENDING,
            subtotal=Decimal('600.00'),
            tax=Decimal('0.00'),
            total=Decimal('600.00')
        )
        
        SaleLine.objects.create(
            sale=sale,
            product=product,
            product_name='Dermal Filler 1ml',
            quantity=Decimal('2.00'),
            unit_price=Decimal('300.00'),
            line_total=Decimal('600.00')
        )
        
        # Pay sale first
        sale.transition_to(SaleStatusChoices.PAID, user=reception_user)
        
        # Verify stock consumed
        assert StockOnHand.objects.get(
            product=product, location=main_warehouse, batch=batch_a
        ).quantity_on_hand == 8
        
        # Reception user calls API to refund
        client = APIClient()
        client.force_authenticate(user=reception_user)
        
        response = client.post(
            f'/api/sales/sales/{sale.id}/transition/',
            data={
                'new_status': 'refunded',
                'reason': 'Customer changed mind'
            },
            format='json'
        )
        
        # Verify success
        assert response.status_code == http_status.HTTP_200_OK
        
        # Verify sale refunded
        sale.refresh_from_db()
        assert sale.status == SaleStatusChoices.REFUNDED
        assert sale.refund_reason == 'Customer changed mind'
        
        # Verify stock restored
        assert StockOnHand.objects.get(
            product=product, location=main_warehouse, batch=batch_a
        ).quantity_on_hand == 10  # Restored
        
        # Verify refund moves created
        refund_moves = StockMove.objects.filter(
            sale=sale,
            move_type=StockMoveTypeChoices.REFUND_IN
        )
        assert refund_moves.count() == 1
        assert refund_moves.first().created_by == reception_user


# ============================================================================
# Test Class 6: StockOnHand Restored After Refund
# ============================================================================

@pytest.mark.django_db
class TestStockOnHandRestored:
    """Test that StockOnHand balances restored to pre-sale levels."""
    
    def test_stock_on_hand_restored_to_exact_pre_sale_levels(
        self, patient, product, main_warehouse, batch_a, batch_b
    ):
        """
        GIVEN a paid sale that consumed from multiple batches
        WHEN refunded
        THEN StockOnHand for each batch restored to exact pre-sale quantity
        """
        # Initial stock
        StockOnHand.objects.create(
            product=product,
            location=main_warehouse,
            batch=batch_a,
            quantity_on_hand=15  # Initial: 15
        )
        StockOnHand.objects.create(
            product=product,
            location=main_warehouse,
            batch=batch_b,
            quantity_on_hand=30  # Initial: 30
        )
        
        # Create sale needing 20 units (15 from batch_a, 5 from batch_b via FEFO)
        sale = Sale.objects.create(
            patient=patient,
            status=SaleStatusChoices.PENDING,
            subtotal=Decimal('6000.00'),
            tax=Decimal('0.00'),
            total=Decimal('6000.00')
        )
        
        SaleLine.objects.create(
            sale=sale,
            product=product,
            product_name='Dermal Filler 1ml',
            quantity=Decimal('20.00'),
            unit_price=Decimal('300.00'),
            line_total=Decimal('6000.00')
        )
        
        # Pay sale (consumes stock)
        sale.transition_to(SaleStatusChoices.PAID, user=None)
        
        # Verify stock consumed
        stock_a = StockOnHand.objects.get(
            product=product, location=main_warehouse, batch=batch_a
        )
        stock_b = StockOnHand.objects.get(
            product=product, location=main_warehouse, batch=batch_b
        )
        
        assert stock_a.quantity_on_hand == 0   # 15 - 15
        assert stock_b.quantity_on_hand == 25  # 30 - 5
        
        # Refund sale
        sale.transition_to(SaleStatusChoices.REFUNDED, user=None)
        
        # Verify stock restored to exact initial levels
        stock_a.refresh_from_db()
        stock_b.refresh_from_db()
        
        assert stock_a.quantity_on_hand == 15  # Restored to initial
        assert stock_b.quantity_on_hand == 30  # Restored to initial
    
    def test_refund_sale_with_no_stock_moves_returns_empty_list(
        self, patient
    ):
        """
        GIVEN a paid sale with no product lines (all services)
        WHEN refunded
        THEN no refund moves created, no error
        """
        sale = Sale.objects.create(
            patient=patient,
            status=SaleStatusChoices.PENDING,
            subtotal=Decimal('100.00'),
            tax=Decimal('0.00'),
            total=Decimal('100.00')
        )
        
        # Line without product (service)
        SaleLine.objects.create(
            sale=sale,
            product=None,
            product_name='Consultation',
            quantity=Decimal('1.00'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00')
        )
        
        # Pay and refund
        sale.transition_to(SaleStatusChoices.PAID, user=None)
        sale.transition_to(SaleStatusChoices.REFUNDED, reason='Service cancelled', user=None)
        
        # Verify sale refunded successfully
        assert sale.status == SaleStatusChoices.REFUNDED
        
        # Verify no refund moves (no stock to restore)
        refund_moves = StockMove.objects.filter(
            sale=sale,
            move_type=StockMoveTypeChoices.REFUND_IN
        )
        assert refund_moves.count() == 0


# ============================================================================
# Summary
# ============================================================================

# Test coverage:
# ✅ Refund creates REFUND_IN moves matching exact batches (2 tests)
# ✅ Refund non-paid sale rejected (3 tests: draft, pending, cancelled)
# ✅ Idempotency: repeated calls don't duplicate (1 test)
# ✅ Rollback on error: no partial state changes (1 test)
# ✅ Reception user can execute refund via API (1 test)
# ✅ StockOnHand restored to exact pre-sale levels (2 tests)
# Total: 10 comprehensive tests
