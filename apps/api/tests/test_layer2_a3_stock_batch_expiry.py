"""
Layer 2 A3: Stock/Inventory Domain Integrity Tests

Test coverage:
1. StockMove quantity != 0 (model + serializer)
2. StockMove IN movements: quantity > 0
3. StockMove OUT movements: quantity < 0
4. StockBatch unique per product
5. Cannot consume from expired batch
6. Cannot consume more than on hand (insufficient stock)
7. FEFO picks earliest expiry with stock
8. FEFO skips expired batches (unless allow_expired=True)
9. FEFO handles multi-batch allocation
10. StockOnHand non-negative constraint
"""
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from apps.stock.models import (
    StockLocation,
    StockBatch,
    StockMove,
    StockOnHand,
    StockMoveTypeChoices,
)
from apps.stock.services import (
    allocate_batch_fefo,
    create_stock_move,
    create_stock_out_fefo,
    InsufficientStockError,
    ExpiredBatchError,
)
from apps.products.models import Product


@pytest.fixture
def location(db):
    """Create test stock location."""
    return StockLocation.objects.create(
        name='Main Warehouse',
        code='MAIN-WH',
        location_type='warehouse',
        is_active=True
    )


@pytest.fixture
def product(db):
    """Create test product."""
    return Product.objects.create(
        sku='TEST-001',
        name='Test Product',
        price=Decimal('100.00'),
        cost=Decimal('50.00'),
        stock_quantity=0
    )


@pytest.fixture
def another_product(db):
    """Create another test product."""
    return Product.objects.create(
        sku='TEST-002',
        name='Another Product',
        price=Decimal('150.00'),
        cost=Decimal('75.00'),
        stock_quantity=0
    )


@pytest.fixture
def batch_fresh(db, product):
    """Create fresh batch (expires in 60 days)."""
    return StockBatch.objects.create(
        product=product,
        batch_number='BATCH-FRESH',
        expiry_date=timezone.now().date() + timedelta(days=60),
        received_at=timezone.now().date()
    )


@pytest.fixture
def batch_expiring_soon(db, product):
    """Create batch expiring soon (expires in 10 days)."""
    return StockBatch.objects.create(
        product=product,
        batch_number='BATCH-SOON',
        expiry_date=timezone.now().date() + timedelta(days=10),
        received_at=timezone.now().date()
    )


@pytest.fixture
def batch_expired(db, product):
    """Create expired batch (expired 5 days ago)."""
    return StockBatch.objects.create(
        product=product,
        batch_number='BATCH-EXPIRED',
        expiry_date=timezone.now().date() - timedelta(days=5),
        received_at=timezone.now().date() - timedelta(days=100)
    )


# ============================================================================
# Test Class 1: StockMove Quantity Constraints
# ============================================================================

@pytest.mark.django_db
class TestStockMoveQuantityConstraint:
    """Test that StockMove.quantity != 0."""
    
    def test_stock_move_quantity_cannot_be_zero_model(self, product, location, batch_fresh):
        """StockMove with quantity=0 should fail model validation."""
        move = StockMove(
            product=product,
            location=location,
            batch=batch_fresh,
            move_type=StockMoveTypeChoices.ADJUSTMENT_IN,
            quantity=0  # Invalid
        )
        
        with pytest.raises(ValidationError) as exc_info:
            move.full_clean()
        
        assert 'quantity' in exc_info.value.message_dict
        assert 'zero' in str(exc_info.value).lower()
    
    def test_stock_move_positive_quantity_succeeds(self, product, location, batch_fresh):
        """StockMove with positive quantity should succeed for IN movements."""
        move = StockMove(
            product=product,
            location=location,
            batch=batch_fresh,
            move_type=StockMoveTypeChoices.PURCHASE_IN,
            quantity=10
        )
        
        move.full_clean()  # Should not raise
        move.save()
        assert move.id is not None
    
    def test_stock_move_negative_quantity_succeeds(self, product, location, batch_fresh):
        """StockMove with negative quantity should succeed for OUT movements."""
        # First add stock
        StockOnHand.objects.create(
            product=product,
            location=location,
            batch=batch_fresh,
            quantity_on_hand=10
        )
        
        move = StockMove(
            product=product,
            location=location,
            batch=batch_fresh,
            move_type=StockMoveTypeChoices.SALE_OUT,
            quantity=-5
        )
        
        move.full_clean()  # Should not raise
        move.save()
        assert move.id is not None


# ============================================================================
# Test Class 2: StockMove Type Sign Constraints
# ============================================================================

@pytest.mark.django_db
class TestStockMoveTypeSignConstraint:
    """Test that IN movements have positive qty, OUT movements have negative qty."""
    
    def test_in_movement_must_have_positive_quantity(self, product, location, batch_fresh):
        """PURCHASE_IN with negative quantity should fail."""
        move = StockMove(
            product=product,
            location=location,
            batch=batch_fresh,
            move_type=StockMoveTypeChoices.PURCHASE_IN,
            quantity=-10  # Invalid for IN
        )
        
        with pytest.raises(ValidationError) as exc_info:
            move.full_clean()
        
        assert 'quantity' in exc_info.value.message_dict
        assert 'positive' in str(exc_info.value).lower()
    
    def test_out_movement_must_have_negative_quantity(self, product, location, batch_fresh):
        """SALE_OUT with positive quantity should fail."""
        move = StockMove(
            product=product,
            location=location,
            batch=batch_fresh,
            move_type=StockMoveTypeChoices.SALE_OUT,
            quantity=10  # Invalid for OUT
        )
        
        with pytest.raises(ValidationError) as exc_info:
            move.full_clean()
        
        assert 'quantity' in exc_info.value.message_dict
        assert 'negative' in str(exc_info.value).lower()


# ============================================================================
# Test Class 3: StockBatch Unique Per Product
# ============================================================================

@pytest.mark.django_db
class TestBatchUniquePerProduct:
    """Test that batch_number is unique per product."""
    
    def test_duplicate_batch_number_same_product_fails(self, product):
        """Duplicate batch number for same product should fail."""
        StockBatch.objects.create(
            product=product,
            batch_number='BATCH-001',
            expiry_date=timezone.now().date() + timedelta(days=30)
        )
        
        with pytest.raises(ValidationError) as exc_info:
            duplicate_batch = StockBatch(
                product=product,
                batch_number='BATCH-001',  # Duplicate
                expiry_date=timezone.now().date() + timedelta(days=60)
            )
            duplicate_batch.full_clean()
        
        # Should fail at database level (UniqueConstraint)
        # or serializer validation level
    
    def test_same_batch_number_different_products_succeeds(self, product, another_product):
        """Same batch number for different products should succeed."""
        batch1 = StockBatch.objects.create(
            product=product,
            batch_number='BATCH-001',
            expiry_date=timezone.now().date() + timedelta(days=30)
        )
        
        batch2 = StockBatch.objects.create(
            product=another_product,
            batch_number='BATCH-001',  # Same number, different product
            expiry_date=timezone.now().date() + timedelta(days=30)
        )
        
        assert batch1.id != batch2.id


# ============================================================================
# Test Class 4: Cannot Consume Expired Batch
# ============================================================================

@pytest.mark.django_db
class TestCannotConsumeExpiredBatch:
    """Test that expired batches cannot be consumed."""
    
    def test_cannot_consume_from_expired_batch_model(self, product, location, batch_expired):
        """OUT movement from expired batch should fail at model level."""
        # Add stock to expired batch (for testing)
        StockOnHand.objects.create(
            product=product,
            location=location,
            batch=batch_expired,
            quantity_on_hand=10
        )
        
        move = StockMove(
            product=product,
            location=location,
            batch=batch_expired,
            move_type=StockMoveTypeChoices.SALE_OUT,
            quantity=-5
        )
        
        with pytest.raises(ValidationError) as exc_info:
            move.full_clean()
        
        assert 'batch' in exc_info.value.message_dict
        assert 'expired' in str(exc_info.value).lower()
    
    def test_can_add_to_expired_batch(self, product, location, batch_expired):
        """IN movement to expired batch should succeed (receiving old stock)."""
        move = StockMove(
            product=product,
            location=location,
            batch=batch_expired,
            move_type=StockMoveTypeChoices.ADJUSTMENT_IN,
            quantity=10
        )
        
        move.full_clean()  # Should not raise (only OUT is blocked)
        move.save()


# ============================================================================
# Test Class 5: Cannot Consume More Than On Hand
# ============================================================================

@pytest.mark.django_db
class TestCannotConsumeMoreThanOnHand:
    """Test that cannot consume more stock than available."""
    
    def test_cannot_consume_more_than_available(self, product, location, batch_fresh):
        """Consuming more than on hand should raise InsufficientStockError."""
        # Add 10 units
        StockOnHand.objects.create(
            product=product,
            location=location,
            batch=batch_fresh,
            quantity_on_hand=10
        )
        
        # Try to consume 15 units
        with pytest.raises(InsufficientStockError):
            create_stock_move(
                product=product,
                location=location,
                batch=batch_fresh,
                move_type=StockMoveTypeChoices.SALE_OUT,
                quantity=-15  # More than available
            )
    
    def test_can_consume_exact_amount_available(self, product, location, batch_fresh):
        """Consuming exactly the available amount should succeed."""
        # Add 10 units
        StockOnHand.objects.create(
            product=product,
            location=location,
            batch=batch_fresh,
            quantity_on_hand=10
        )
        
        # Consume exactly 10 units
        move = create_stock_move(
            product=product,
            location=location,
            batch=batch_fresh,
            move_type=StockMoveTypeChoices.SALE_OUT,
            quantity=-10
        )
        
        assert move.quantity == -10
        
        # Check stock is now 0
        stock = StockOnHand.objects.get(
            product=product,
            location=location,
            batch=batch_fresh
        )
        assert stock.quantity_on_hand == 0


# ============================================================================
# Test Class 6: FEFO Picks Earliest Expiry
# ============================================================================

@pytest.mark.django_db
class TestFEFOPicksEarliestExpiry:
    """Test that FEFO allocation picks batch with earliest expiry date."""
    
    def test_fefo_picks_expiring_soon_over_fresh(
        self, product, location, batch_fresh, batch_expiring_soon
    ):
        """FEFO should pick expiring_soon batch before fresh batch."""
        # Add stock to both batches
        StockOnHand.objects.create(
            product=product,
            location=location,
            batch=batch_fresh,
            quantity_on_hand=100
        )
        StockOnHand.objects.create(
            product=product,
            location=location,
            batch=batch_expiring_soon,
            quantity_on_hand=50
        )
        
        # Allocate 10 units using FEFO
        allocations = allocate_batch_fefo(
            product=product,
            location=location,
            quantity_needed=10
        )
        
        # Should allocate from expiring_soon batch
        assert len(allocations) == 1
        batch, qty = allocations[0]
        assert batch.batch_number == 'BATCH-SOON'
        assert qty == 10


# ============================================================================
# Test Class 7: FEFO Skips Expired Batches
# ============================================================================

@pytest.mark.django_db
class TestFEFOSkipsExpiredBatches:
    """Test that FEFO skips expired batches by default."""
    
    def test_fefo_skips_expired_batch_by_default(
        self, product, location, batch_fresh, batch_expired
    ):
        """FEFO should skip expired batch and use fresh batch."""
        # Add stock to both batches
        StockOnHand.objects.create(
            product=product,
            location=location,
            batch=batch_fresh,
            quantity_on_hand=100
        )
        StockOnHand.objects.create(
            product=product,
            location=location,
            batch=batch_expired,
            quantity_on_hand=50
        )
        
        # Allocate using FEFO
        allocations = allocate_batch_fefo(
            product=product,
            location=location,
            quantity_needed=10
        )
        
        # Should allocate from fresh batch, skipping expired
        assert len(allocations) == 1
        batch, qty = allocations[0]
        assert batch.batch_number == 'BATCH-FRESH'
        assert qty == 10
    
    def test_fefo_raises_error_if_only_expired_stock(
        self, product, location, batch_expired
    ):
        """FEFO should raise ExpiredBatchError if only expired stock available."""
        # Add stock only to expired batch
        StockOnHand.objects.create(
            product=product,
            location=location,
            batch=batch_expired,
            quantity_on_hand=50
        )
        
        # Try to allocate
        with pytest.raises(ExpiredBatchError):
            allocate_batch_fefo(
                product=product,
                location=location,
                quantity_needed=10
            )
    
    def test_fefo_allows_expired_if_flag_set(
        self, product, location, batch_expired
    ):
        """FEFO should allow expired batch if allow_expired=True."""
        # Add stock only to expired batch
        StockOnHand.objects.create(
            product=product,
            location=location,
            batch=batch_expired,
            quantity_on_hand=50
        )
        
        # Allocate with allow_expired=True
        allocations = allocate_batch_fefo(
            product=product,
            location=location,
            quantity_needed=10,
            allow_expired=True
        )
        
        # Should allocate from expired batch
        assert len(allocations) == 1
        batch, qty = allocations[0]
        assert batch.batch_number == 'BATCH-EXPIRED'
        assert qty == 10


# ============================================================================
# Test Class 8: FEFO Multi-Batch Allocation
# ============================================================================

@pytest.mark.django_db
class TestFEFOMultiBatchAllocation:
    """Test that FEFO can allocate from multiple batches when needed."""
    
    def test_fefo_allocates_from_multiple_batches(
        self, product, location, batch_expiring_soon, batch_fresh
    ):
        """FEFO should split allocation across batches if needed."""
        # Add limited stock to expiring_soon, more to fresh
        StockOnHand.objects.create(
            product=product,
            location=location,
            batch=batch_expiring_soon,
            quantity_on_hand=5  # Not enough
        )
        StockOnHand.objects.create(
            product=product,
            location=location,
            batch=batch_fresh,
            quantity_on_hand=100
        )
        
        # Need 10 units
        allocations = allocate_batch_fefo(
            product=product,
            location=location,
            quantity_needed=10
        )
        
        # Should allocate from both batches
        assert len(allocations) == 2
        
        # First from expiring_soon (5 units)
        batch1, qty1 = allocations[0]
        assert batch1.batch_number == 'BATCH-SOON'
        assert qty1 == 5
        
        # Then from fresh (remaining 5 units)
        batch2, qty2 = allocations[1]
        assert batch2.batch_number == 'BATCH-FRESH'
        assert qty2 == 5


# ============================================================================
# Test Class 9: StockOnHand Non-Negative Constraint
# ============================================================================

@pytest.mark.django_db
class TestStockOnHandNonNegative:
    """Test that StockOnHand.quantity_on_hand cannot be negative."""
    
    def test_stock_on_hand_cannot_be_negative_model(self, product, location, batch_fresh):
        """StockOnHand with negative quantity should fail validation."""
        stock = StockOnHand(
            product=product,
            location=location,
            batch=batch_fresh,
            quantity_on_hand=-10  # Invalid
        )
        
        with pytest.raises(ValidationError) as exc_info:
            stock.full_clean()
        
        assert 'quantity_on_hand' in exc_info.value.message_dict
        assert 'negative' in str(exc_info.value).lower()
    
    def test_stock_on_hand_zero_succeeds(self, product, location, batch_fresh):
        """StockOnHand with zero quantity should succeed."""
        stock = StockOnHand(
            product=product,
            location=location,
            batch=batch_fresh,
            quantity_on_hand=0
        )
        
        stock.full_clean()  # Should not raise
        stock.save()
        assert stock.quantity_on_hand == 0


# ============================================================================
# Test Class 10: create_stock_out_fefo Integration
# ============================================================================

@pytest.mark.django_db
class TestCreateStockOutFEFO:
    """Test create_stock_out_fefo service function."""
    
    def test_create_stock_out_fefo_creates_moves(
        self, product, location, batch_fresh, django_user_model
    ):
        """create_stock_out_fefo should create StockMove records."""
        # Add stock
        StockOnHand.objects.create(
            product=product,
            location=location,
            batch=batch_fresh,
            quantity_on_hand=100
        )
        
        # Create user
        user = django_user_model.objects.create_user(
            username='testuser',
            password='testpass'
        )
        
        # Consume using FEFO
        moves = create_stock_out_fefo(
            product=product,
            location=location,
            quantity=10,
            move_type=StockMoveTypeChoices.SALE_OUT,
            reason='Test sale',
            created_by=user
        )
        
        # Should create moves
        assert len(moves) == 1
        move = moves[0]
        assert move.quantity == -10
        assert move.move_type == StockMoveTypeChoices.SALE_OUT
        assert move.created_by == user
        
        # Check stock updated
        stock = StockOnHand.objects.get(
            product=product,
            location=location,
            batch=batch_fresh
        )
        assert stock.quantity_on_hand == 90
    
    def test_create_stock_out_fefo_with_reference(
        self, product, location, batch_fresh
    ):
        """create_stock_out_fefo should store reference info."""
        # Add stock
        StockOnHand.objects.create(
            product=product,
            location=location,
            batch=batch_fresh,
            quantity_on_hand=100
        )
        
        # Consume with reference
        moves = create_stock_out_fefo(
            product=product,
            location=location,
            quantity=5,
            move_type=StockMoveTypeChoices.SALE_OUT,
            reference_type='Sale',
            reference_id='sale-123',
            reason='Sale #INV-001'
        )
        
        assert len(moves) == 1
        move = moves[0]
        assert move.reference_type == 'Sale'
        assert move.reference_id == 'sale-123'
        assert move.reason == 'Sale #INV-001'


# ============================================================================
# Test Class 11: Batch Expiry Properties
# ============================================================================

@pytest.mark.django_db
class TestBatchExpiryProperties:
    """Test StockBatch expiry-related properties."""
    
    def test_batch_is_expired_property(self, batch_expired):
        """is_expired should return True for expired batches."""
        assert batch_expired.is_expired is True
    
    def test_batch_not_expired_property(self, batch_fresh):
        """is_expired should return False for fresh batches."""
        assert batch_fresh.is_expired is False
    
    def test_batch_days_until_expiry(self, batch_expiring_soon):
        """days_until_expiry should calculate correctly."""
        days = batch_expiring_soon.days_until_expiry
        assert days >= 9 and days <= 11  # ~10 days (with some tolerance)
    
    def test_batch_days_until_expiry_expired(self, batch_expired):
        """days_until_expiry should be negative for expired batches."""
        days = batch_expired.days_until_expiry
        assert days < 0


# ============================================================================
# Test Class 12: StockOnHand Unique Constraint
# ============================================================================

@pytest.mark.django_db
class TestStockOnHandUniqueConstraint:
    """Test that StockOnHand enforces unique (product, location, batch)."""
    
    def test_duplicate_stock_on_hand_fails(self, product, location, batch_fresh):
        """Duplicate StockOnHand for same product/location/batch should fail."""
        StockOnHand.objects.create(
            product=product,
            location=location,
            batch=batch_fresh,
            quantity_on_hand=10
        )
        
        # Try to create duplicate
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            StockOnHand.objects.create(
                product=product,
                location=location,
                batch=batch_fresh,
                quantity_on_hand=20
            )
