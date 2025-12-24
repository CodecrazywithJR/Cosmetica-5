"""
Layer 3 A: Sales-Stock Integration Tests

Test coverage:
1. Sale transition to paid consumes stock using FEFO
2. Sale transition fails if insufficient stock (sale not marked paid)
3. Idempotency: repeated transition calls don't duplicate stock consumption
4. Reception user can mark sale as paid (triggers automatic consumption)
5. Reception user CANNOT call manual stock consume endpoints (403)
6. ClinicalOps user CAN call manual stock consume endpoints (200)

Run: DATABASE_HOST=localhost pytest apps/api/tests/test_layer3_a_sales_stock.py -v
"""
import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status

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
from apps.stock.services import InsufficientStockError
from apps.sales.services import consume_stock_for_sale, get_default_stock_location

User = get_user_model()


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def patient():
    """Create a test patient."""
    return Patient.objects.create(
        first_name='John',
        last_name='Doe',
        birth_date='1990-01-01'
    )


@pytest.fixture
def product():
    """Create a test product (assumes Product model exists)."""
    try:
        return Product.objects.create(
            sku='BOTOX-50U',
            name='Botox 50 Units',
            description='Botulinum toxin type A',
            price=Decimal('250.00')
        )
    except Exception:
        # If Product model doesn't have these fields, create minimal
        return Product.objects.create(
            sku='BOTOX-50U',
            name='Botox 50 Units'
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
def batch_fresh(product):
    """Create a fresh batch (expires in 60 days)."""
    return StockBatch.objects.create(
        product=product,
        batch_number='BATCH-FRESH-001',
        expiry_date=timezone.now().date() + timedelta(days=60),
        received_at=timezone.now().date()
    )


@pytest.fixture
def batch_expiring_soon(product):
    """Create a batch expiring soon (5 days)."""
    return StockBatch.objects.create(
        product=product,
        batch_number='BATCH-EXPIRING-001',
        expiry_date=timezone.now().date() + timedelta(days=5),
        received_at=timezone.now().date() - timedelta(days=30)
    )


@pytest.fixture
def reception_user():
    """Create a Reception group user."""
    from django.contrib.auth.models import Group
    user = User.objects.create_user(
        email='reception@test.com',
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
        email='clinicalops@test.com',
        password='testpass123'
    )
    clinicalops_group, _ = Group.objects.get_or_create(name='ClinicalOps')
    user.groups.add(clinicalops_group)
    return user


# ============================================================================
# Test Class 1: Paid Transition Consumes Stock FEFO
# ============================================================================

@pytest.mark.django_db
class TestSalePaidConsumesStockFEFO:
    """Test that transitioning sale to paid automatically consumes stock using FEFO."""
    
    def test_sale_paid_consumes_stock_fefo_allocation(
        self, patient, product, main_warehouse, batch_expiring_soon, batch_fresh
    ):
        """
        GIVEN a sale with product line and stock in multiple batches
        WHEN sale transitions to paid
        THEN stock is consumed using FEFO (expiring batch first)
        """
        # Add stock to both batches
        StockOnHand.objects.create(
            product=product,
            location=main_warehouse,
            batch=batch_expiring_soon,
            quantity_on_hand=10
        )
        StockOnHand.objects.create(
            product=product,
            location=main_warehouse,
            batch=batch_fresh,
            quantity_on_hand=50
        )
        
        # Create sale with product line
        sale = Sale.objects.create(
            patient=patient,
            status=SaleStatusChoices.PENDING,
            subtotal=Decimal('250.00'),
            tax=Decimal('0.00'),
            discount=Decimal('0.00'),
            total=Decimal('250.00')
        )
        
        line = SaleLine.objects.create(
            sale=sale,
            product=product,  # Link to actual product
            product_name='Botox 50 Units',
            quantity=Decimal('5.00'),
            unit_price=Decimal('50.00'),
            discount=Decimal('0.00'),
            line_total=Decimal('250.00')
        )
        
        # Transition to paid (should trigger stock consumption)
        sale.transition_to(SaleStatusChoices.PAID, user=None)
        
        # Verify sale is paid
        assert sale.status == SaleStatusChoices.PAID
        assert sale.paid_at is not None
        
        # Verify stock moves created
        moves = StockMove.objects.filter(sale=sale)
        assert moves.count() == 1  # One move (all from expiring batch)
        
        move = moves.first()
        assert move.batch == batch_expiring_soon  # FEFO: expiring batch first
        assert move.quantity == -5  # OUT movement
        assert move.move_type == StockMoveTypeChoices.SALE_OUT
        assert move.sale == sale
        assert move.sale_line == line
        
        # Verify stock on hand updated
        stock_expiring = StockOnHand.objects.get(
            product=product,
            location=main_warehouse,
            batch=batch_expiring_soon
        )
        assert stock_expiring.quantity_on_hand == 5  # 10 - 5
        
        stock_fresh = StockOnHand.objects.get(
            product=product,
            location=main_warehouse,
            batch=batch_fresh
        )
        assert stock_fresh.quantity_on_hand == 50  # Untouched (FEFO)
    
    def test_sale_paid_consumes_from_multiple_batches_when_needed(
        self, patient, product, main_warehouse, batch_expiring_soon, batch_fresh
    ):
        """
        GIVEN stock in multiple batches, first batch has insufficient quantity
        WHEN sale requires more than first batch has
        THEN FEFO allocates from multiple batches (expiring first)
        """
        # Add stock: expiring has 3, fresh has 50
        StockOnHand.objects.create(
            product=product,
            location=main_warehouse,
            batch=batch_expiring_soon,
            quantity_on_hand=3
        )
        StockOnHand.objects.create(
            product=product,
            location=main_warehouse,
            batch=batch_fresh,
            quantity_on_hand=50
        )
        
        # Create sale needing 10 units (more than expiring batch has)
        sale = Sale.objects.create(
            patient=patient,
            status=SaleStatusChoices.PENDING,
            subtotal=Decimal('500.00'),
            tax=Decimal('0.00'),
            discount=Decimal('0.00'),
            total=Decimal('500.00')
        )
        
        SaleLine.objects.create(
            sale=sale,
            product=product,
            product_name='Botox 50 Units',
            quantity=Decimal('10.00'),
            unit_price=Decimal('50.00'),
            line_total=Decimal('500.00')
        )
        
        # Transition to paid
        sale.transition_to(SaleStatusChoices.PAID, user=None)
        
        # Verify 2 stock moves created (split across batches)
        moves = StockMove.objects.filter(sale=sale).order_by('batch__expiry_date')
        assert moves.count() == 2
        
        # First move from expiring batch (3 units)
        move1 = moves[0]
        assert move1.batch == batch_expiring_soon
        assert move1.quantity == -3
        
        # Second move from fresh batch (7 units)
        move2 = moves[1]
        assert move2.batch == batch_fresh
        assert move2.quantity == -7
        
        # Verify stock on hand
        assert StockOnHand.objects.get(
            product=product, location=main_warehouse, batch=batch_expiring_soon
        ).quantity_on_hand == 0  # All consumed
        
        assert StockOnHand.objects.get(
            product=product, location=main_warehouse, batch=batch_fresh
        ).quantity_on_hand == 43  # 50 - 7
    
    def test_sale_with_service_lines_skips_stock_consumption(
        self, patient, main_warehouse
    ):
        """
        GIVEN a sale with lines that have no product FK (services)
        WHEN sale transitions to paid
        THEN no stock is consumed (no StockMoves created)
        """
        sale = Sale.objects.create(
            patient=patient,
            status=SaleStatusChoices.PENDING,
            subtotal=Decimal('100.00'),
            tax=Decimal('0.00'),
            total=Decimal('100.00')
        )
        
        # Line without product FK (service)
        SaleLine.objects.create(
            sale=sale,
            product=None,  # No product link
            product_name='Consultation',
            quantity=Decimal('1.00'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('100.00')
        )
        
        # Transition to paid
        sale.transition_to(SaleStatusChoices.PAID, user=None)
        
        # Verify sale is paid but no stock consumed
        assert sale.status == SaleStatusChoices.PAID
        assert StockMove.objects.filter(sale=sale).count() == 0


# ============================================================================
# Test Class 2: Insufficient Stock Prevents Payment
# ============================================================================

@pytest.mark.django_db
class TestInsufficientStockPreventsPaid:
    """Test that insufficient stock prevents sale from being marked as paid."""
    
    def test_sale_paid_fails_without_sufficient_stock(
        self, patient, product, main_warehouse, batch_fresh
    ):
        """
        GIVEN a sale with product line but insufficient stock
        WHEN attempting to transition to paid
        THEN InsufficientStockError is raised and sale status NOT changed
        """
        # Add only 2 units of stock
        StockOnHand.objects.create(
            product=product,
            location=main_warehouse,
            batch=batch_fresh,
            quantity_on_hand=2
        )
        
        # Create sale needing 10 units
        sale = Sale.objects.create(
            patient=patient,
            status=SaleStatusChoices.PENDING,
            subtotal=Decimal('500.00'),
            tax=Decimal('0.00'),
            total=Decimal('500.00')
        )
        
        SaleLine.objects.create(
            sale=sale,
            product=product,
            product_name='Botox 50 Units',
            quantity=Decimal('10.00'),  # Need 10, have 2
            unit_price=Decimal('50.00'),
            line_total=Decimal('500.00')
        )
        
        # Attempt to transition to paid
        with pytest.raises(InsufficientStockError) as exc_info:
            sale.transition_to(SaleStatusChoices.PAID, user=None)
        
        assert 'Insufficient stock' in str(exc_info.value)
        assert 'BOTOX-50U' in str(exc_info.value)
        
        # Verify sale status NOT changed
        sale.refresh_from_db()
        assert sale.status == SaleStatusChoices.PENDING
        assert sale.paid_at is None
        
        # Verify NO stock moves created
        assert StockMove.objects.filter(sale=sale).count() == 0
        
        # Verify stock on hand unchanged
        assert StockOnHand.objects.get(
            product=product, location=main_warehouse, batch=batch_fresh
        ).quantity_on_hand == 2  # Unchanged
    
    def test_sale_paid_fails_without_any_stock(
        self, patient, product, main_warehouse
    ):
        """
        GIVEN a sale with product line but zero stock
        WHEN attempting to transition to paid
        THEN InsufficientStockError is raised
        """
        # No stock at all (no StockOnHand records)
        
        sale = Sale.objects.create(
            patient=patient,
            status=SaleStatusChoices.PENDING,
            subtotal=Decimal('250.00'),
            tax=Decimal('0.00'),
            total=Decimal('250.00')
        )
        
        SaleLine.objects.create(
            sale=sale,
            product=product,
            product_name='Botox 50 Units',
            quantity=Decimal('5.00'),
            unit_price=Decimal('50.00'),
            line_total=Decimal('250.00')
        )
        
        # Attempt to transition
        with pytest.raises(InsufficientStockError):
            sale.transition_to(SaleStatusChoices.PAID, user=None)
        
        # Verify no changes
        sale.refresh_from_db()
        assert sale.status == SaleStatusChoices.PENDING
        assert StockMove.objects.filter(sale=sale).count() == 0


# ============================================================================
# Test Class 3: Idempotency
# ============================================================================

@pytest.mark.django_db
class TestStockConsumptionIdempotency:
    """Test that stock consumption is idempotent - no duplicates on repeated calls."""
    
    def test_repeated_transition_to_paid_does_not_duplicate_stock_consumption(
        self, patient, product, main_warehouse, batch_fresh
    ):
        """
        GIVEN a sale already transitioned to paid (stock consumed)
        WHEN transition_to(paid) called again (idempotency scenario)
        THEN no additional stock moves created
        """
        # Add stock
        StockOnHand.objects.create(
            product=product,
            location=main_warehouse,
            batch=batch_fresh,
            quantity_on_hand=50
        )
        
        # Create sale
        sale = Sale.objects.create(
            patient=patient,
            status=SaleStatusChoices.PENDING,
            subtotal=Decimal('250.00'),
            tax=Decimal('0.00'),
            total=Decimal('250.00')
        )
        
        SaleLine.objects.create(
            sale=sale,
            product=product,
            product_name='Botox 50 Units',
            quantity=Decimal('5.00'),
            unit_price=Decimal('50.00'),
            line_total=Decimal('250.00')
        )
        
        # First transition to paid
        sale.transition_to(SaleStatusChoices.PAID, user=None)
        
        # Verify stock consumed
        assert StockMove.objects.filter(sale=sale).count() == 1
        assert StockOnHand.objects.get(
            product=product, location=main_warehouse, batch=batch_fresh
        ).quantity_on_hand == 45  # 50 - 5
        
        # Attempt second transition (state machine should prevent, but test idempotency)
        # Since paid is terminal, transition_to(paid) from paid should fail
        # But consume_stock_for_sale itself is idempotent
        
        # Directly call service to test idempotency
        from apps.sales.services import consume_stock_for_sale
        moves = consume_stock_for_sale(sale=sale, created_by=None)
        
        # Should return existing moves, not create new ones
        assert len(moves) == 1  # Same count
        assert StockMove.objects.filter(sale=sale).count() == 1  # Still 1
        
        # Stock on hand unchanged
        assert StockOnHand.objects.get(
            product=product, location=main_warehouse, batch=batch_fresh
        ).quantity_on_hand == 45  # Still 45


# ============================================================================
# Test Class 4: Reception User Can Mark Sale Paid
# ============================================================================

@pytest.mark.django_db
class TestReceptionCanMarkSalePaid:
    """Test that Reception users can mark sales as paid (which triggers stock consumption)."""
    
    def test_reception_user_can_transition_sale_to_paid_via_api(
        self, patient, product, main_warehouse, batch_fresh, reception_user
    ):
        """
        GIVEN a reception user and a sale with sufficient stock
        WHEN reception user calls /sales/{id}/transition/ with new_status=paid
        THEN sale is marked paid AND stock is consumed automatically
        """
        # Add stock
        StockOnHand.objects.create(
            product=product,
            location=main_warehouse,
            batch=batch_fresh,
            quantity_on_hand=50
        )
        
        # Create sale
        sale = Sale.objects.create(
            patient=patient,
            status=SaleStatusChoices.PENDING,
            subtotal=Decimal('250.00'),
            tax=Decimal('0.00'),
            total=Decimal('250.00')
        )
        
        SaleLine.objects.create(
            sale=sale,
            product=product,
            product_name='Botox 50 Units',
            quantity=Decimal('5.00'),
            unit_price=Decimal('50.00'),
            line_total=Decimal('250.00')
        )
        
        # Reception user calls API
        client = APIClient()
        client.force_authenticate(user=reception_user)
        
        response = client.post(
            f'/api/sales/sales/{sale.id}/transition/',
            data={'new_status': 'paid'},
            format='json'
        )
        
        # Verify success
        assert response.status_code == status.HTTP_200_OK
        
        # Verify sale is paid
        sale.refresh_from_db()
        assert sale.status == SaleStatusChoices.PAID
        assert sale.paid_at is not None
        
        # Verify stock consumed
        moves = StockMove.objects.filter(sale=sale)
        assert moves.count() == 1
        assert moves.first().created_by == reception_user
        
        # Verify stock on hand updated
        assert StockOnHand.objects.get(
            product=product, location=main_warehouse, batch=batch_fresh
        ).quantity_on_hand == 45


# ============================================================================
# Test Class 5: Reception CANNOT Call Manual Stock Endpoints
# ============================================================================

@pytest.mark.django_db
class TestReceptionCannotCallManualStockEndpoints:
    """Test that Reception users CANNOT directly call stock consume endpoints."""
    
    def test_reception_user_cannot_consume_fefo_endpoint(
        self, product, main_warehouse, batch_fresh, reception_user
    ):
        """
        GIVEN a reception user
        WHEN attempting to call POST /api/stock/moves/consume-fefo/
        THEN request is denied with 403 Forbidden
        """
        # Add stock
        StockOnHand.objects.create(
            product=product,
            location=main_warehouse,
            batch=batch_fresh,
            quantity_on_hand=50
        )
        
        client = APIClient()
        client.force_authenticate(user=reception_user)
        
        response = client.post(
            '/api/stock/moves/consume-fefo/',
            data={
                'product': str(product.id),
                'location': str(main_warehouse.id),
                'quantity': 5,
                'move_type': 'sale_out',
                'reason': 'Manual consumption attempt'
            },
            format='json'
        )
        
        # Verify 403 Forbidden (IsClinicalOpsOrAdmin permission)
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# Test Class 6: ClinicalOps CAN Call Manual Stock Endpoints
# ============================================================================

@pytest.mark.django_db
class TestClinicalOpsCanCallManualStockEndpoints:
    """Test that ClinicalOps users CAN call manual stock consume endpoints."""
    
    def test_clinicalops_user_can_consume_fefo_endpoint(
        self, product, main_warehouse, batch_fresh, clinicalops_user
    ):
        """
        GIVEN a clinicalops user
        WHEN calling POST /api/stock/moves/consume-fefo/
        THEN request succeeds with 201 Created
        """
        # Add stock
        StockOnHand.objects.create(
            product=product,
            location=main_warehouse,
            batch=batch_fresh,
            quantity_on_hand=50
        )
        
        client = APIClient()
        client.force_authenticate(user=clinicalops_user)
        
        response = client.post(
            '/api/stock/moves/consume-fefo/',
            data={
                'product': str(product.id),
                'location': str(main_warehouse.id),
                'quantity': 5,
                'move_type': 'sale_out',
                'reason': 'Manual consumption by clinical ops'
            },
            format='json'
        )
        
        # Verify success
        assert response.status_code == status.HTTP_201_CREATED
        
        # Verify stock consumed
        assert StockOnHand.objects.get(
            product=product, location=main_warehouse, batch=batch_fresh
        ).quantity_on_hand == 45


# ============================================================================
# Summary
# ============================================================================

# Test coverage:
# ✅ Sale paid consumes stock FEFO (expiring batch first)
# ✅ Sale paid consumes from multiple batches when needed
# ✅ Sale with services skips stock consumption
# ✅ Insufficient stock prevents sale from being paid
# ✅ Zero stock prevents sale from being paid
# ✅ Idempotency: repeated calls don't duplicate consumption
# ✅ Reception user can mark sale as paid (triggers consumption)
# ✅ Reception user CANNOT call manual stock endpoints (403)
# ✅ ClinicalOps user CAN call manual stock endpoints (200)
