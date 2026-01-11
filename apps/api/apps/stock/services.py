"""
Stock services - Business logic for stock operations.

Layer 2 A3: FEFO allocation, batch management, stock commit operations.
"""
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from typing import List, Tuple, Optional
from decimal import Decimal

from .models import (
    StockBatch,
    StockMove,
    StockOnHand,
    StockLocation,
    StockMoveTypeChoices,
)


class InsufficientStockError(ValidationError):
    """Raised when there's not enough stock available."""
    pass


class ExpiredBatchError(ValidationError):
    """Raised when attempting to use an expired batch."""
    pass


def allocate_batch_fefo(
    product,
    location: StockLocation,
    quantity_needed: int,
    allow_expired: bool = False
) -> List[Tuple[StockBatch, int]]:
    """
    Allocate batches using FEFO (First Expired, First Out) strategy.
    
    Args:
        product: Product instance
        location: StockLocation instance
        quantity_needed: Total quantity to allocate
        allow_expired: If True, allow allocation from expired batches
    
    Returns:
        List of (batch, quantity) tuples allocated
        
    Raises:
        InsufficientStockError: Not enough stock available
        ExpiredBatchError: Only expired batches available and allow_expired=False
    
    Algorithm:
        1. Get all batches with stock on hand at location for product
        2. Filter out expired batches (unless allow_expired=True)
        3. Sort by expiry_date ASC (earliest first - FEFO)
        4. Allocate from batches sequentially until quantity_needed is met
        5. Return list of (batch, qty) allocations
    """
    if quantity_needed <= 0:
        raise ValueError("quantity_needed must be positive")
    
    # Get available stock on hand, ordered by expiry date (FEFO)
    stock_records = StockOnHand.objects.filter(
        product=product,
        location=location,
        quantity_on_hand__gt=0
    ).select_related('batch').order_by('batch__expiry_date', 'batch__batch_number')
    
    # Filter expired batches unless explicitly allowed
    today = timezone.now().date()
    available_stock = []
    
    for record in stock_records:
        batch = record.batch
        
        # Skip expired batches unless allowed
        if not allow_expired and batch.expiry_date and batch.expiry_date < today:
            continue
        
        available_stock.append((batch, record.quantity_on_hand))
    
    # Check if we have enough total stock
    total_available = sum(qty for _, qty in available_stock)
    
    if total_available < quantity_needed:
        # Check if we have stock but it's all expired
        total_stock_including_expired = sum(
            record.quantity_on_hand
            for record in StockOnHand.objects.filter(
                product=product,
                location=location,
                quantity_on_hand__gt=0
            )
        )
        
        if total_stock_including_expired >= quantity_needed and not allow_expired:
            raise ExpiredBatchError(
                f"Sufficient stock available ({total_stock_including_expired}) but all batches are expired. "
                f"Available non-expired: {total_available}, needed: {quantity_needed}"
            )
        
        raise InsufficientStockError(
            f"Insufficient stock for {product.sku} at {location.code}. "
            f"Available: {total_available}, needed: {quantity_needed}"
        )
    
    # Allocate from batches (FEFO)
    allocations = []
    remaining = quantity_needed
    
    for batch, available_qty in available_stock:
        if remaining <= 0:
            break
        
        # Allocate from this batch
        allocated_qty = min(available_qty, remaining)
        allocations.append((batch, allocated_qty))
        remaining -= allocated_qty
    
    return allocations


@transaction.atomic
def create_stock_move(
    product,
    location: StockLocation,
    batch: Optional[StockBatch],
    move_type: StockMoveTypeChoices,
    quantity: int,
    reference_type: str = '',
    reference_id: str = '',
    reason: str = '',
    created_by=None
) -> StockMove:
    """
    Create a stock move and update stock on hand.
    
    Args:
        product: Product instance
        location: StockLocation instance
        batch: StockBatch instance (required for OUT moves)
        move_type: StockMoveTypeChoices value
        quantity: Signed quantity (positive for IN, negative for OUT)
        reference_type: Type of originating document
        reference_id: ID of originating document
        reason: Reason for movement
        created_by: User creating the move
    
    Returns:
        Created StockMove instance
        
    Raises:
        ValidationError: If move violates business rules
    """
    # Create the move
    move = StockMove(
        product=product,
        location=location,
        batch=batch,
        move_type=move_type,
        quantity=quantity,
        reference_type=reference_type,
        reference_id=reference_id,
        reason=reason,
        created_by=created_by
    )
    
    # Validate before saving
    move.full_clean()
    move.save()
    
    # Update stock on hand
    if batch:
        stock_on_hand, created = StockOnHand.objects.get_or_create(
            product=product,
            location=location,
            batch=batch,
            defaults={'quantity_on_hand': 0}
        )
        
        stock_on_hand.quantity_on_hand += quantity
        
        # Validate non-negative stock
        if stock_on_hand.quantity_on_hand < 0:
            raise InsufficientStockError(
                f"Cannot reduce stock below zero. "
                f"Product: {product.sku}, Batch: {batch.batch_number}, "
                f"Current: {stock_on_hand.quantity_on_hand - quantity}, "
                f"Attempted change: {quantity}"
            )
        
        stock_on_hand.save()
    
    return move


@transaction.atomic
def create_stock_out_fefo(
    product,
    location: StockLocation,
    quantity: int,
    move_type: StockMoveTypeChoices,
    reference_type: str = '',
    reference_id: str = '',
    reason: str = '',
    created_by=None,
    allow_expired: bool = False
) -> List[StockMove]:
    """
    Create stock OUT movement(s) using FEFO allocation.
    
    This is the recommended way to consume stock, as it automatically
    selects the appropriate batches using FEFO strategy.
    
    Args:
        product: Product instance
        location: StockLocation instance
        quantity: Quantity to consume (positive number)
        move_type: Must be an OUT type (sale_out, waste_out, etc.)
        reference_type: Type of originating document
        reference_id: ID of originating document
        reason: Reason for movement
        created_by: User creating the move
        allow_expired: Allow using expired batches
    
    Returns:
        List of created StockMove instances
        
    Raises:
        InsufficientStockError: Not enough stock
        ExpiredBatchError: Only expired batches available
        ValidationError: Invalid move type or parameters
    """
    if quantity <= 0:
        raise ValueError("quantity must be positive for OUT movements")
    
    # Validate move_type is OUT
    out_types = [
        StockMoveTypeChoices.SALE_OUT,
        StockMoveTypeChoices.ADJUSTMENT_OUT,
        StockMoveTypeChoices.WASTE_OUT,
        StockMoveTypeChoices.TRANSFER_OUT,
    ]
    if move_type not in out_types:
        raise ValidationError(f"move_type must be an OUT type, got {move_type}")
    
    # Allocate batches using FEFO
    allocations = allocate_batch_fefo(
        product=product,
        location=location,
        quantity_needed=quantity,
        allow_expired=allow_expired
    )
    
    # Create move for each allocation
    moves = []
    for batch, allocated_qty in allocations:
        move = create_stock_move(
            product=product,
            location=location,
            batch=batch,
            move_type=move_type,
            quantity=-allocated_qty,  # Negative for OUT
            reference_type=reference_type,
            reference_id=reference_id,
            reason=reason,
            created_by=created_by
        )
        moves.append(move)
    
    return moves


@transaction.atomic
def commit_sale_to_stock(sale, location: StockLocation, created_by=None) -> List[StockMove]:
    """
    Commit a paid sale to stock (create OUT movements for sale lines).
    
    This is idempotent - if stock has already been committed for this sale,
    returns the existing moves without creating duplicates.
    
    Args:
        sale: Sale instance (must be paid)
        location: StockLocation to consume from
        created_by: User committing the stock
    
    Returns:
        List of StockMove instances created (or existing)
        
    Raises:
        ValidationError: Sale not paid, or lines reference non-Product items
    """
    from apps.sales.models import SaleStatusChoices
    
    # INVARIANT: Sale must be paid
    if sale.status != SaleStatusChoices.PAID:
        raise ValidationError(
            f"Cannot commit stock for sale in {sale.get_status_display()} status. "
            f"Sale must be paid."
        )
    
    # Check if already committed (idempotent)
    existing_moves = StockMove.objects.filter(
        reference_type='Sale',
        reference_id=str(sale.id)
    )
    
    if existing_moves.exists():
        # Already committed, return existing moves
        return list(existing_moves)
    
    # Create moves for each line
    moves = []
    
    for line in sale.lines.all():
        # Skip lines without product reference (service lines, etc.)
        # In current implementation, SaleLine has product_name/product_code
        # but no direct FK to Product. This would need to be enhanced
        # to link SaleLine -> Product for stock integration.
        
        # TODO: This requires SaleLine to have a FK to Product
        # For now, we'll document this limitation
        # In a real implementation, you'd add:
        # line.product FK -> Product (nullable for services)
        
        # Placeholder - in real implementation:
        # if not line.product:
        #     continue  # Skip service lines
        # 
        # line_moves = create_stock_out_fefo(
        #     product=line.product,
        #     location=location,
        #     quantity=int(line.quantity),
        #     move_type=StockMoveTypeChoices.SALE_OUT,
        #     reference_type='SaleLine',
        #     reference_id=str(line.id),
        #     reason=f'Sale {sale.sale_number or sale.id}',
        #     created_by=created_by
        # )
        # moves.extend(line_moves)
        
        pass
    
    # For this implementation, we document that SaleLine -> Product FK
    # needs to be added for full stock integration
    
    return moves


def get_stock_summary(product, location: Optional[StockLocation] = None):
    """
    Get stock summary for a product (optionally filtered by location).
    
    Returns:
        Dict with total, by_location, by_batch, expired_batches
    """
    filters = {'product': product}
    if location:
        filters['location'] = location
    
    stock_records = StockOnHand.objects.filter(**filters).select_related(
        'location', 'batch'
    )
    
    total = sum(record.quantity_on_hand for record in stock_records)
    
    by_location = {}
    by_batch = {}
    expired_batches = []
    
    today = timezone.now().date()
    
    for record in stock_records:
        # By location
        loc_key = record.location.code
        by_location[loc_key] = by_location.get(loc_key, 0) + record.quantity_on_hand
        
        # By batch
        batch_key = record.batch.batch_number
        by_batch[batch_key] = {
            'quantity': record.quantity_on_hand,
            'expiry_date': record.batch.expiry_date,
            'is_expired': record.batch.is_expired,
            'location': record.location.code
        }
        
        # Expired batches
        if record.batch.expiry_date and record.batch.expiry_date < today:
            expired_batches.append({
                'batch': batch_key,
                'quantity': record.quantity_on_hand,
                'expiry_date': record.batch.expiry_date,
                'location': record.location.code
            })
    
    return {
        'total': total,
        'by_location': by_location,
        'by_batch': by_batch,
        'expired_batches': expired_batches
    }
