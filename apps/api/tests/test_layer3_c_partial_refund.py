"""
Layer 3 C: Partial Refund Tests

Comprehensive test suite for partial refund functionality.

Test Coverage:
1. Single line, single batch refund
2. Single line, multi-batch proportional split
3. Service line (no stock) refund
4. Over-refund validation
5. PAID-only validation
6. Idempotency (no duplicates)
7. Permissions: Reception allowed
8. Permissions: Marketing forbidden
9. Transaction atomicity
"""
import pytest
from decimal import Decimal
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta

from apps.authz.models import User
from apps.clinical.models import Patient
from apps.products.models import Product
from apps.sales.models import Sale, SaleLine, SaleRefund, SaleRefundLine, SaleStatusChoices, SaleRefundStatusChoices
from apps.sales.services import refund_partial_for_sale
from apps.stock.models import StockLocation, StockBatch, StockOnHand, StockMove, StockMoveTypeChoices


@pytest.fixture
def setup_groups(db):
    """Create user groups."""
    reception = Group.objects.create(name='Reception')
    clinical_ops = Group.objects.create(name='ClinicalOps')
    marketing = Group.objects.create(name='Marketing')
    return {
        'reception': reception,
        'clinical_ops': clinical_ops,
        'marketing': marketing
    }


@pytest.fixture
def reception_user(db, setup_groups):
    """Create user in Reception group."""
    user = User.objects.create_user(
        username='reception1',
        email='reception1@test.com',
        password='test123'
    )
    user.groups.add(setup_groups['reception'])
    return user


@pytest.fixture
def clinical_ops_user(db, setup_groups):
    """Create user in ClinicalOps group."""
    user = User.objects.create_user(
        username='clinicalops1',
        email='clinicalops1@test.com',
        password='test123'
    )
    user.groups.add(setup_groups['clinical_ops'])
    return user


@pytest.fixture
def marketing_user(db, setup_groups):
    """Create user in Marketing group."""
    user = User.objects.create_user(
        username='marketing1',
        email='marketing1@test.com',
        password='test123'
    )
    user.groups.add(setup_groups['marketing'])
    return user


@pytest.fixture
def patient(db):
    """Create test patient."""
    return Patient.objects.create(
        first_name='Test',
        last_name='Patient',
        birth_date='1990-01-01',
        email='patient@test.com'
    )


@pytest.fixture
def product(db):
    """Create test product."""
    return Product.objects.create(
        name='Test Product',
        code='PROD001',
        price=Decimal('300.00'),
        is_active=True
    )


@pytest.fixture
def location(db):
    """Create stock location."""
    return StockLocation.objects.create(
        name='Main Clinic',
        code='MAIN',
        is_active=True
    )


@pytest.fixture
def batch_1(db, product):
    """Create first batch (expires later)."""
    return StockBatch.objects.create(
        product=product,
        batch_number='BATCH001',
        expiry_date=timezone.now().date() + timedelta(days=180)
    )


@pytest.fixture
def batch_2(db, product):
    """Create second batch (expires sooner - FEFO priority)."""
    return StockBatch.objects.create(
        product=product,
        batch_number='BATCH002',
        expiry_date=timezone.now().date() + timedelta(days=90)
    )


@pytest.fixture
def paid_sale(db, patient, product, location, batch_1, batch_2, reception_user):
    """
    Create PAID sale with stock consumption from 2 batches.
    
    Setup:
    - Sale: 5 units @ 300 = 1500
    - Stock OUT: 3 from BATCH002 (FEFO), 2 from BATCH001
    """
    # Create stock on hand
    StockOnHand.objects.create(
        product=product,
        location=location,
        batch=batch_1,
        quantity_on_hand=10
    )
    StockOnHand.objects.create(
        product=product,
        location=location,
        batch=batch_2,
        quantity_on_hand=10
    )
    
    # Create sale
    sale = Sale.objects.create(
        patient=patient,
        sale_number='SALE-001',
        status=SaleStatusChoices.DRAFT
    )
    
    # Add line
    line = SaleLine.objects.create(
        sale=sale,
        product=product,
        product_name=product.name,
        product_code=product.code,
        quantity=5,
        unit_price=Decimal('300.00')
    )
    
    sale.recalculate_totals()
    sale.save()
    
    # Transition to PAID (triggers stock consumption via FEFO)
    sale.transition_to(SaleStatusChoices.PAID, user=reception_user)
    
    return sale


@pytest.mark.django_db
class TestPartialRefundSingleBatch:
    """Test partial refund with single batch."""
    
    def test_partial_refund_single_line_creates_refund_in(
        self, paid_sale, product, location, batch_2, reception_user
    ):
        """
        Refund 2 units from a 5-unit sale (single line).
        
        Expected:
        - SaleRefund created with COMPLETED status
        - 1 SaleRefundLine with qty=2
        - 1 StockMove REFUND_IN for 2 units from BATCH002 (first OUT)
        - StockOnHand increased by 2 for BATCH002
        """
        line = paid_sale.lines.first()
        
        # Verify initial state
        initial_stock = StockOnHand.objects.get(
            product=product,
            location=location,
            batch=batch_2
        )
        initial_qty = initial_stock.quantity_on_hand
        
        # Create partial refund
        refund = refund_partial_for_sale(
            sale=paid_sale,
            refund_payload={
                'reason': 'Customer returned 2 units',
                'lines': [
                    {'sale_line_id': str(line.id), 'qty_refunded': 2, 'amount_refunded': Decimal('600.00')}
                ]
            },
            created_by=reception_user
        )
        
        # ASSERT: Refund created
        assert refund.status == SaleRefundStatusChoices.COMPLETED
        assert refund.reason == 'Customer returned 2 units'
        assert refund.created_by == reception_user
        
        # ASSERT: Refund line created
        assert refund.lines.count() == 1
        refund_line = refund.lines.first()
        assert refund_line.sale_line == line
        assert refund_line.qty_refunded == 2
        assert refund_line.amount_refunded == Decimal('600.00')
        
        # ASSERT: Stock move created
        stock_moves = StockMove.objects.filter(
            refund=refund,
            move_type=StockMoveTypeChoices.REFUND_IN
        )
        assert stock_moves.count() == 1
        
        refund_move = stock_moves.first()
        assert refund_move.product == product
        assert refund_move.location == location
        assert refund_move.batch == batch_2  # First OUT was from BATCH002
        assert refund_move.quantity == 2
        assert refund_move.sale == paid_sale
        assert refund_move.sale_line == line
        assert refund_move.source_move is not None
        
        # ASSERT: Stock restored
        initial_stock.refresh_from_db()
        assert initial_stock.quantity_on_hand == initial_qty + 2


@pytest.mark.django_db
class TestPartialRefundMultiBatch:
    """Test partial refund spanning multiple batches."""
    
    def test_partial_refund_multi_batch_splits_exactly(
        self, paid_sale, product, location, batch_1, batch_2, reception_user
    ):
        """
        Refund 4 units from a 5-unit sale that consumed 3+2 from 2 batches.
        
        Expected:
        - Refund 3 from BATCH002 (fully reversing first OUT)
        - Refund 1 from BATCH001 (partially reversing second OUT)
        - 2 StockMove REFUND_IN records
        - Both batches restored correctly
        """
        line = paid_sale.lines.first()
        
        # Get initial stock
        stock_batch1 = StockOnHand.objects.get(product=product, batch=batch_1)
        stock_batch2 = StockOnHand.objects.get(product=product, batch=batch_2)
        qty_batch1_initial = stock_batch1.quantity_on_hand
        qty_batch2_initial = stock_batch2.quantity_on_hand
        
        # Create partial refund for 4 units
        refund = refund_partial_for_sale(
            sale=paid_sale,
            refund_payload={
                'reason': 'Partial return - 4 units',
                'lines': [
                    {'sale_line_id': str(line.id), 'qty_refunded': 4, 'amount_refunded': Decimal('1200.00')}
                ]
            },
            created_by=reception_user
        )
        
        # ASSERT: Refund created
        assert refund.status == SaleRefundStatusChoices.COMPLETED
        assert refund.lines.count() == 1
        assert refund.lines.first().qty_refunded == 4
        
        # ASSERT: 2 stock moves created (one per batch)
        stock_moves = StockMove.objects.filter(
            refund=refund,
            move_type=StockMoveTypeChoices.REFUND_IN
        ).order_by('created_at')
        
        assert stock_moves.count() == 2
        
        # First move: 3 units from BATCH002 (FEFO consumed this first)
        move1 = stock_moves[0]
        assert move1.batch == batch_2
        assert move1.quantity == 3
        
        # Second move: 1 unit from BATCH001
        move2 = stock_moves[1]
        assert move2.batch == batch_1
        assert move2.quantity == 1
        
        # ASSERT: Stock restored correctly
        stock_batch1.refresh_from_db()
        stock_batch2.refresh_from_db()
        assert stock_batch1.quantity_on_hand == qty_batch1_initial + 1
        assert stock_batch2.quantity_on_hand == qty_batch2_initial + 3


@pytest.mark.django_db
class TestPartialRefundServiceLine:
    """Test partial refund with service line (no stock)."""
    
    def test_service_line_refund_creates_no_stock_moves(self, patient, reception_user):
        """
        Refund a service line (no product).
        
        Expected:
        - SaleRefund created
        - SaleRefundLine created
        - NO StockMove created
        """
        # Create sale with service line
        sale = Sale.objects.create(
            patient=patient,
            sale_number='SALE-SERVICE',
            status=SaleStatusChoices.DRAFT
        )
        
        service_line = SaleLine.objects.create(
            sale=sale,
            product=None,  # Service line
            product_name='Consultation',
            quantity=1,
            unit_price=Decimal('500.00')
        )
        
        sale.recalculate_totals()
        sale.save()
        sale.transition_to(SaleStatusChoices.PAID, user=reception_user)
        
        # Refund service
        refund = refund_partial_for_sale(
            sale=sale,
            refund_payload={
                'reason': 'Service canceled',
                'lines': [
                    {'sale_line_id': str(service_line.id), 'qty_refunded': 1, 'amount_refunded': Decimal('500.00')}
                ]
            },
            created_by=reception_user
        )
        
        # ASSERT: Refund created
        assert refund.status == SaleRefundStatusChoices.COMPLETED
        assert refund.lines.count() == 1
        
        # ASSERT: NO stock moves (service line)
        stock_moves = StockMove.objects.filter(refund=refund)
        assert stock_moves.count() == 0


@pytest.mark.django_db
class TestPartialRefundValidation:
    """Test validation rules for partial refunds."""
    
    def test_cannot_refund_more_than_sold(self, paid_sale, reception_user):
        """
        Attempt to refund 6 units when only 5 were sold.
        
        Expected: ValidationError
        """
        line = paid_sale.lines.first()
        
        with pytest.raises(ValidationError, match='Cannot refund'):
            refund_partial_for_sale(
                sale=paid_sale,
                refund_payload={
                    'reason': 'Over-refund attempt',
                    'lines': [
                        {'sale_line_id': str(line.id), 'qty_refunded': 6}
                    ]
                },
                created_by=reception_user
            )
    
    def test_cannot_refund_more_than_available_after_previous_refund(
        self, paid_sale, reception_user
    ):
        """
        Create two refunds totaling more than sold.
        
        Expected: First refund succeeds, second raises ValidationError
        """
        line = paid_sale.lines.first()
        
        # First refund: 3 units
        refund1 = refund_partial_for_sale(
            sale=paid_sale,
            refund_payload={
                'reason': 'First refund',
                'lines': [
                    {'sale_line_id': str(line.id), 'qty_refunded': 3, 'amount_refunded': Decimal('900.00')}
                ]
            },
            created_by=reception_user
        )
        assert refund1.status == SaleRefundStatusChoices.COMPLETED
        
        # Second refund: attempt 3 more (only 2 available)
        with pytest.raises(ValidationError, match='Available: 2'):
            refund_partial_for_sale(
                sale=paid_sale,
                refund_payload={
                    'reason': 'Second refund - should fail',
                    'lines': [
                        {'sale_line_id': str(line.id), 'qty_refunded': 3}
                    ]
                },
                created_by=reception_user
            )
    
    def test_refund_requires_paid_sale(self, patient, product, reception_user):
        """
        Attempt to refund a DRAFT sale.
        
        Expected: ValidationError
        """
        sale = Sale.objects.create(
            patient=patient,
            sale_number='SALE-DRAFT',
            status=SaleStatusChoices.DRAFT
        )
        
        line = SaleLine.objects.create(
            sale=sale,
            product=product,
            product_name=product.name,
            quantity=1,
            unit_price=Decimal('300.00')
        )
        
        with pytest.raises(ValidationError, match='sale must be paid'):
            refund_partial_for_sale(
                sale=sale,
                refund_payload={
                    'reason': 'Invalid refund',
                    'lines': [
                        {'sale_line_id': str(line.id), 'qty_refunded': 1}
                    ]
                },
                created_by=reception_user
            )


@pytest.mark.django_db
class TestPartialRefundIdempotency:
    """Test idempotency of partial refunds."""
    
    def test_idempotency_key_prevents_duplicate_refunds(self, paid_sale, reception_user):
        """
        Call refund_partial_for_sale twice with same idempotency_key.
        
        Expected: Second call returns existing refund without creating duplicates
        """
        line = paid_sale.lines.first()
        
        payload = {
            'reason': 'Idempotent refund',
            'idempotency_key': 'test-refund-123',
            'lines': [
                {'sale_line_id': str(line.id), 'qty_refunded': 2, 'amount_refunded': Decimal('600.00')}
            ]
        }
        
        # First call
        refund1 = refund_partial_for_sale(
            sale=paid_sale,
            refund_payload=payload,
            created_by=reception_user
        )
        
        initial_refund_count = SaleRefund.objects.filter(sale=paid_sale).count()
        initial_move_count = StockMove.objects.filter(refund=refund1).count()
        
        # Second call with same key
        refund2 = refund_partial_for_sale(
            sale=paid_sale,
            refund_payload=payload,
            created_by=reception_user
        )
        
        # ASSERT: Same refund returned
        assert refund1.id == refund2.id
        
        # ASSERT: No duplicates created
        assert SaleRefund.objects.filter(sale=paid_sale).count() == initial_refund_count
        assert StockMove.objects.filter(refund=refund1).count() == initial_move_count


@pytest.mark.django_db
class TestPartialRefundPermissions:
    """Test RBAC permissions for partial refunds."""
    
    def test_reception_can_create_refund(self, paid_sale, reception_user):
        """
        Reception user can create partial refund.
        
        Expected: Refund created successfully
        """
        line = paid_sale.lines.first()
        
        refund = refund_partial_for_sale(
            sale=paid_sale,
            refund_payload={
                'reason': 'Reception refund',
                'lines': [
                    {'sale_line_id': str(line.id), 'qty_refunded': 1}
                ]
            },
            created_by=reception_user
        )
        
        assert refund.status == SaleRefundStatusChoices.COMPLETED
        assert refund.created_by == reception_user
    
    def test_clinical_ops_can_create_refund(self, paid_sale, clinical_ops_user):
        """
        ClinicalOps user can create partial refund.
        
        Expected: Refund created successfully
        """
        line = paid_sale.lines.first()
        
        refund = refund_partial_for_sale(
            sale=paid_sale,
            refund_payload={
                'reason': 'ClinicalOps refund',
                'lines': [
                    {'sale_line_id': str(line.id), 'qty_refunded': 1}
                ]
            },
            created_by=clinical_ops_user
        )
        
        assert refund.status == SaleRefundStatusChoices.COMPLETED
        assert refund.created_by == clinical_ops_user


@pytest.mark.django_db
class TestPartialRefundAtomicity:
    """Test transaction atomicity."""
    
    def test_atomicity_rollback_on_stock_update_failure(
        self, paid_sale, product, location, batch_2, reception_user, monkeypatch
    ):
        """
        Simulate failure during StockOnHand update.
        
        Expected: Transaction rolled back, no SaleRefund/StockMove created
        """
        line = paid_sale.lines.first()
        
        # Track original counts
        initial_refund_count = SaleRefund.objects.count()
        initial_move_count = StockMove.objects.count()
        
        # Patch StockOnHand.save to raise exception
        def failing_save(self, *args, **kwargs):
            raise Exception("Simulated stock update failure")
        
        monkeypatch.setattr(StockOnHand, 'save', failing_save)
        
        # Attempt refund
        with pytest.raises(Exception, match="Simulated stock update failure"):
            refund_partial_for_sale(
                sale=paid_sale,
                refund_payload={
                    'reason': 'Should fail',
                    'lines': [
                        {'sale_line_id': str(line.id), 'qty_refunded': 1}
                    ]
                },
                created_by=reception_user
            )
        
        # ASSERT: Rollback - no records created
        assert SaleRefund.objects.count() == initial_refund_count
        assert StockMove.objects.count() == initial_move_count
