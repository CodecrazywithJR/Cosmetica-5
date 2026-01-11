"""
Sales service layer - Business logic for sales operations.

Layer 3 A: Sales-Stock Integration
- Automatic stock consumption on payment
- FEFO allocation
- Idempotency
- Transaction safety
"""
from django.db import transaction
from django.db import models
from django.core.exceptions import ValidationError
from typing import List, Optional
import time

from apps.stock.models import StockLocation, StockMove, StockMoveTypeChoices
from apps.stock.services import (
    create_stock_out_fefo,
    InsufficientStockError,
    ExpiredBatchError,
)
from apps.core.observability import metrics, log_domain_event, get_sanitized_logger
from apps.core.observability.events import (
    log_stock_consumed,
    log_refund_created,
    log_over_refund_blocked,
    log_idempotency_conflict,
    log_consistency_checkpoint,
)
from apps.core.observability.tracing import trace_span

logger = get_sanitized_logger(__name__)


# Default location for automatic sales stock consumption
DEFAULT_STOCK_LOCATION_CODE = 'MAIN-WAREHOUSE'


def get_default_stock_location() -> StockLocation:
    """
    Get the default stock location for sales consumption.
    
    Returns:
        StockLocation instance for MAIN-WAREHOUSE
        
    Raises:
        ValidationError: If MAIN-WAREHOUSE location doesn't exist
    """
    try:
        return StockLocation.objects.get(code=DEFAULT_STOCK_LOCATION_CODE, is_active=True)
    except StockLocation.DoesNotExist:
        raise ValidationError(
            f"Default stock location '{DEFAULT_STOCK_LOCATION_CODE}' not found or inactive. "
            f"Please create it before processing sales."
        )


@transaction.atomic
def consume_stock_for_sale(sale, location: Optional[StockLocation] = None, created_by=None) -> List[StockMove]:
    """
    Consume stock for a sale using FEFO allocation.
    
    IDEMPOTENT: Safe to call multiple times - checks if stock already consumed.
    TRANSACTION: All-or-nothing - if any line fails, entire sale fails.
    
    Args:
        sale: Sale instance (should be transitioning to PAID)
        location: StockLocation to consume from (default: MAIN-WAREHOUSE)
        created_by: User performing the operation
    
    Returns:
        List of created StockMove instances
        
    Raises:
        InsufficientStockError: Not enough stock for any line
        ExpiredBatchError: Only expired stock available
        ValidationError: Invalid state or configuration
    
    Business Rules:
        1. Only process sales with status='paid' (or transitioning to paid)
        2. Only consume stock for lines with product FK (skip services)
        3. Use FEFO allocation (earliest expiry first)
        4. Idempotent: Skip if stock already consumed for this sale
        5. Atomic: All lines succeed or none (transaction.atomic)
        6. Traceability: Link StockMove to Sale and SaleLine
    
    Idempotency Strategy:
        - Check if StockMoves with sale=this_sale already exist
        - If yes, return existing moves (no-op)
        - If no, proceed with consumption
    """
    start_time = time.time()
    
    with trace_span('consume_stock_for_sale', attributes={
        'sale_id': str(sale.id),
        'sale_number': sale.sale_number or 'N/A',
        'location_code': location.code if location else 'default'
    }):
        # Get default location if not provided
        if location is None:
            location = get_default_stock_location()
        
        # Idempotency check: Has stock already been consumed for this sale?
        existing_moves = StockMove.objects.filter(sale=sale)
        if existing_moves.exists():
            # Stock already consumed - return existing moves (idempotent)
            duration_ms = int((time.time() - start_time) * 1000)
            
            metrics.sales_paid_stock_consume_total.labels(result='idempotent').inc()
            
            logger.info(
                'Stock consumption idempotent - already processed',
                extra={
                    'sale_id': str(sale.id),
                    'existing_moves_count': existing_moves.count(),
                    'duration_ms': duration_ms
                }
            )
            
            return list(existing_moves)
        
        # Collect all product lines that require stock
        product_lines = sale.lines.filter(product__isnull=False).select_related('product')
        
        if not product_lines.exists():
            # No product lines - sale is all services, nothing to consume
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                'No stock consumption needed - all service lines',
                extra={'sale_id': str(sale.id), 'duration_ms': duration_ms}
            )
            return []
        
        # Validate all lines have sufficient stock BEFORE consuming any
        # This allows us to fail fast with a clear error message
        for line in product_lines:
            # We'll let create_stock_out_fefo handle the actual availability check
            # Just ensure quantity is valid
            if line.quantity <= 0:
                raise ValidationError(
                    f"Invalid quantity {line.quantity} for line {line.product_name}"
                )
        
        # Consume stock for each product line using FEFO
        moves = []
        
        for line in product_lines:
            try:
                # Use FEFO to allocate and create stock movements
                line_moves = create_stock_out_fefo(
                    product=line.product,
                    location=location,
                    quantity=int(line.quantity),  # Convert Decimal to int
                    move_type=StockMoveTypeChoices.SALE_OUT,
                    reference_type='Sale',
                    reference_id=str(sale.id),
                    reason=f'Sale {sale.sale_number or sale.id} - {line.product_name}',
                    created_by=created_by,
                    allow_expired=False  # Never use expired stock for sales
                )
                
                # Link moves to sale and sale_line for traceability
                for move in line_moves:
                    move.sale = sale
                    move.sale_line = line
                    move.save(update_fields=['sale', 'sale_line'])
                
                moves.extend(line_moves)
                
            except InsufficientStockError as e:
                # Emit error metrics
                metrics.sales_paid_stock_consume_total.labels(result='insufficient_stock').inc()
                metrics.exceptions_total.labels(
                    exception_type='InsufficientStockError',
                    location='consume_stock_for_sale'
                ).inc()
                
                # Log error (no PHI)
                logger.error(
                    'Stock consumption failed - insufficient stock',
                    extra={
                        'sale_id': str(sale.id),
                        'product_name': line.product_name,
                        'error': str(e)
                    }
                )
                
                # Re-raise with more context
                raise InsufficientStockError(
                    f"Cannot complete sale {sale.sale_number or sale.id}: "
                    f"Insufficient stock for {line.product_name} (SKU: {line.product.sku}). "
                    f"{str(e)}"
                )
            except ExpiredBatchError as e:
                # Emit error metrics
                metrics.sales_paid_stock_consume_total.labels(result='expired_batch').inc()
                metrics.exceptions_total.labels(
                    exception_type='ExpiredBatchError',
                    location='consume_stock_for_sale'
                ).inc()
                
                # Log error (no PHI)
                logger.error(
                    'Stock consumption failed - only expired batches',
                    extra={
                        'sale_id': str(sale.id),
                        'product_name': line.product_name,
                        'error': str(e)
                    }
                )
                
                # Re-raise with more context
                raise ExpiredBatchError(
                    f"Cannot complete sale {sale.sale_number or sale.id}: "
                    f"Only expired stock available for {line.product_name}. "
                    f"{str(e)}"
                )
        
        # SUCCESS: Calculate metrics and emit events
        duration_ms = int((time.time() - start_time) * 1000)
        total_quantity = sum(abs(m.quantity) for m in moves)
        
        # Emit success metrics
        metrics.sales_paid_stock_consume_total.labels(result='success').inc()
        metrics.sales_paid_stock_consume_duration_seconds.observe(
            (time.time() - start_time)
        )
        
        # Emit domain event (PHI-safe)
        log_stock_consumed(
            sale=sale,
            stock_moves_count=len(moves),
            total_quantity=total_quantity,
            duration_ms=duration_ms
        )
        
        # Consistency checkpoint
        log_consistency_checkpoint(
            checkpoint='stock_consumed_for_sale',
            checks={
                'moves_created': len(moves) > 0,
                'all_lines_processed': len(moves) == len(product_lines)
            },
            entity_type='Sale',
            entity_id=str(sale.id),
            metadata={'location': location.code}
        )
        
        return moves


def check_stock_availability_for_sale(sale, location: Optional[StockLocation] = None) -> dict:
    """
    Check if sufficient stock exists for all product lines in a sale.
    
    NON-DESTRUCTIVE: Does not consume stock, just checks availability.
    
    Args:
        sale: Sale instance
        location: StockLocation to check (default: MAIN-WAREHOUSE)
    
    Returns:
        dict with:
            - 'available': bool - True if all lines have stock
            - 'lines': list of dicts with line-level availability
            - 'errors': list of error messages if any
    
    Example:
        >>> result = check_stock_availability_for_sale(sale)
        >>> if result['available']:
        >>>     # Safe to transition to paid
        >>>     sale.transition_to('paid')
        >>> else:
        >>>     # Show errors to user
        >>>     for error in result['errors']:
        >>>         print(error)
    """
    if location is None:
        location = get_default_stock_location()
    
    product_lines = sale.lines.filter(product__isnull=False).select_related('product')
    
    result = {
        'available': True,
        'lines': [],
        'errors': []
    }
    
    for line in product_lines:
        # Get available stock for this product at location
        from apps.stock.models import StockOnHand
        from django.db import models
        
        total_available = StockOnHand.objects.filter(
            product=line.product,
            location=location,
            quantity_on_hand__gt=0
        ).aggregate(
            total=models.Sum('quantity_on_hand')
        )['total'] or 0
        
        needed = int(line.quantity)
        line_available = total_available >= needed
        
        line_result = {
            'line_id': str(line.id),
            'product_name': line.product_name,
            'product_sku': line.product.sku,
            'quantity_needed': needed,
            'quantity_available': total_available,
            'available': line_available
        }
        
        result['lines'].append(line_result)
        
        if not line_available:
            result['available'] = False
            result['errors'].append(
                f"{line.product_name} (SKU: {line.product.sku}): "
                f"need {needed}, available {total_available}"
            )
    
    return result


# ============================================================================
# Layer 3 B: Refund Stock Integration
# ============================================================================

@transaction.atomic
def refund_stock_for_sale(sale, created_by=None) -> List[StockMove]:
    """
    Restore stock for a refunded sale by reversing original consumption moves.
    
    BUSINESS RULES:
    - Sale must be in PAID status (about to transition to REFUNDED)
    - Creates REFUND_IN moves that exactly reverse the original SALE_OUT moves
    - Returns stock to the SAME batches and locations as original consumption
    - 100% refund only (no partial refunds)
    
    IDEMPOTENT: Safe to call multiple times - checks if refund already processed.
    TRANSACTION: All-or-nothing - if any reversal fails, entire refund fails.
    TRACEABILITY: Links reversal moves to original moves via reversed_move FK.
    
    Args:
        sale: Sale instance to refund (must be PAID, about to become REFUNDED)
        created_by: User performing the refund (for audit trail)
        
    Returns:
        List of StockMove instances (REFUND_IN moves created)
        Empty list if sale has no stock consumption or already refunded
        
    Raises:
        ValidationError: If sale is not PAID or has invalid state
        
    Example:
        >>> sale = Sale.objects.get(id='...')
        >>> sale.status  # 'paid'
        >>> refund_moves = refund_stock_for_sale(sale, created_by=request.user)
        >>> sale.status = SaleStatusChoices.REFUNDED
        >>> sale.save()
    """
    from apps.sales.models import SaleStatusChoices
    
    # VALIDATION: Sale must be PAID to refund
    if sale.status != SaleStatusChoices.PAID:
        raise ValidationError(
            f"Cannot refund sale: sale must be paid. Current status: {sale.get_status_display()}"
        )
    
    # Get all original SALE_OUT moves for this sale
    out_moves = StockMove.objects.filter(
        sale=sale,
        move_type=StockMoveTypeChoices.SALE_OUT,
        quantity__lt=0  # OUT moves are negative
    ).select_related('product', 'location', 'batch', 'sale_line')
    
    if not out_moves.exists():
        # Sale has no stock consumption (all services, or never consumed)
        # This is valid - just return empty list
        return []
    
    # IDEMPOTENCY CHECK: Has refund already been processed?
    # If ANY of the original OUT moves already have a reversal, consider it done
    existing_reversals = StockMove.objects.filter(
        reversed_move__in=out_moves
    ).exists()
    
    if existing_reversals:
        # Already refunded - return existing reversal moves
        return list(StockMove.objects.filter(reversed_move__in=out_moves))
    
    # CREATE REVERSAL MOVES: One REFUND_IN per original SALE_OUT
    refund_moves = []
    
    for out_move in out_moves:
        # Create exact reversal:
        # - Same product, location, batch
        # - Positive quantity (reversing the negative OUT)
        # - Link to sale and sale_line for traceability
        # - Link to original move via reversed_move
        
        refund_move = StockMove(
            product=out_move.product,
            location=out_move.location,
            batch=out_move.batch,
            move_type=StockMoveTypeChoices.REFUND_IN,
            quantity=abs(out_move.quantity),  # Reverse: negative -> positive
            sale=sale,
            sale_line=out_move.sale_line,
            reversed_move=out_move,  # Link to original OUT move
            reference_type='SaleRefund',
            reference_id=str(sale.id),
            reason=f'Refund of sale {sale.sale_number or sale.id} - {out_move.product.name}',
            created_by=created_by
        )
        
        # Validate and save
        refund_move.full_clean()
        refund_move.save()
        
        refund_moves.append(refund_move)
    
    # Update StockOnHand balances
    # StockOnHand.update_from_move() should be triggered by signal or called here
    from apps.stock.models import StockOnHand
    
    for refund_move in refund_moves:
        # Get or create StockOnHand for this batch/location
        stock, created = StockOnHand.objects.get_or_create(
            product=refund_move.product,
            location=refund_move.location,
            batch=refund_move.batch,
            defaults={'quantity_on_hand': 0}
        )
        
        # Add refunded quantity back
        stock.quantity_on_hand += refund_move.quantity
        stock.save()
    
    return refund_moves


# ============================================================================
# Layer 3 C: Partial Refund Integration
# ============================================================================

@transaction.atomic
def refund_partial_for_sale(sale, refund_payload: dict, created_by=None):
    """
    Create a partial (or full) refund for a sale with proportional stock restoration.
    
    BUSINESS RULES:
    - Sale must be PAID
    - Each line qty_refunded <= (line.quantity - already_refunded_for_line)
    - Stock restored uses EXACT batch/location from original SALE_OUT moves (NO FEFO)
    - Partial refunds: multiple refunds can exist for same sale
    - Service lines: no stock moves created
    
    IDEMPOTENT: Uses unique constraint on (refund, source_move) to prevent duplicates.
    TRANSACTION: All-or-nothing - if any validation fails, entire refund fails.
    TRACEABILITY: Links StockMove to SaleRefund and source SALE_OUT move.
    
    Args:
        sale: Sale instance to refund (must be PAID)
        refund_payload: dict with:
            - reason: str (optional)
            - idempotency_key: str (optional, stored in metadata)
            - lines: list of dicts:
                - sale_line_id: UUID
                - qty_refunded: Decimal
                - amount_refunded: Decimal (optional)
        created_by: User performing the refund
        
    Returns:
        SaleRefund instance with lines and stock_moves populated
        
    Raises:
        ValidationError: If sale not PAID, qty exceeds available, etc.
        
    Example:
        >>> refund = refund_partial_for_sale(
        ...     sale=sale,
        ...     refund_payload={
        ...         'reason': 'Partial return - customer dissatisfied',
        ...         'idempotency_key': 'refund-123-abc',
        ...         'lines': [
        ...             {'sale_line_id': line1.id, 'qty_refunded': 2, 'amount_refunded': 600.00},
        ...             {'sale_line_id': line2.id, 'qty_refunded': 1, 'amount_refunded': 300.00}
        ...         ]
        ...     },
        ...     created_by=request.user
        ... )
    """
    from apps.sales.models import Sale, SaleLine, SaleRefund, SaleRefundLine, SaleRefundStatusChoices, SaleStatusChoices
    from apps.stock.models import StockMove, StockMoveTypeChoices, StockOnHand
    from decimal import Decimal
    
    # VALIDATION 1: Sale must be PAID
    if sale.status != SaleStatusChoices.PAID:
        raise ValidationError(
            f"Cannot refund sale: sale must be paid. Current status: {sale.get_status_display()}"
        )
    
    # Extract payload
    reason = refund_payload.get('reason', '')
    lines_data = refund_payload.get('lines', [])
    
    # Resolve idempotency_key with priority:
    # 1. Explicit key in payload (new standard)
    # 2. Legacy: metadata.idempotency_key (compatibility)
    idempotency_key = refund_payload.get('idempotency_key')
    if not idempotency_key:
        # Legacy fallback: check if metadata contains key
        metadata_from_payload = refund_payload.get('metadata', {})
        if isinstance(metadata_from_payload, dict):
            idempotency_key = metadata_from_payload.get('idempotency_key')
    
    if not lines_data:
        raise ValidationError("Refund must have at least one line")
    
    # IDEMPOTENCY CHECK: If idempotency_key resolved, check if refund already exists
    if idempotency_key:
        existing_refund = SaleRefund.objects.filter(
            sale=sale,
            idempotency_key=idempotency_key
        ).first()
        
        if existing_refund:
            return existing_refund  # Already processed - idempotent behavior
    
    # CREATE REFUND (draft initially)
    # SINGLE SOURCE OF TRUTH: idempotency_key field only (no metadata duplication)
    refund = SaleRefund(
        sale=sale,
        status=SaleRefundStatusChoices.DRAFT,
        reason=reason,
        created_by=created_by,
        idempotency_key=idempotency_key,  # Single source of truth
        metadata=refund_payload.get('metadata', {})  # Preserve other metadata (no key)
    )
    refund.save()
    
    try:
        # VALIDATE AND CREATE REFUND LINES
        refund_lines = []
        stock_moves = []
        
        for line_data in lines_data:
            sale_line_id = line_data.get('sale_line_id')
            qty_refunded = Decimal(str(line_data.get('qty_refunded', 0)))
            amount_refunded = line_data.get('amount_refunded')
            
            if amount_refunded is not None:
                amount_refunded = Decimal(str(amount_refunded))
            
            # Get sale line
            try:
                sale_line = SaleLine.objects.get(id=sale_line_id, sale=sale)
            except SaleLine.DoesNotExist:
                raise ValidationError(f"Sale line {sale_line_id} not found in this sale")
            
            # Create refund line (validation happens in clean())
            refund_line = SaleRefundLine(
                refund=refund,
                sale_line=sale_line,
                qty_refunded=qty_refunded,
                amount_refunded=amount_refunded
            )
            refund_line.full_clean()  # Validates qty_refunded <= available
            refund_line.save()
            refund_lines.append(refund_line)
            
            # STOCK RESTORATION: Only for product lines (not services)
            if sale_line.product is None:
                continue  # Service line - skip stock moves
            
            # Get original SALE_OUT moves for this sale_line (ordered deterministically)
            out_moves = StockMove.objects.filter(
                sale_line=sale_line,
                move_type=StockMoveTypeChoices.SALE_OUT,
                quantity__lt=0  # OUT moves are negative
            ).order_by('created_at', 'id')  # Deterministic order
            
            if not out_moves.exists():
                raise ValidationError(
                    f"No stock consumption found for line '{sale_line.product_name}'. "
                    f"Cannot restore stock for refund."
                )
            
            # Reverse stock proportionally from original OUT moves
            qty_to_reverse = int(qty_refunded)
            qty_reversed = 0
            
            for out_move in out_moves:
                if qty_reversed >= qty_to_reverse:
                    break  # Already reversed enough
                
                # Check if this out_move already has partial reversals
                already_reversed = StockMove.objects.filter(
                    source_move=out_move,
                    move_type=StockMoveTypeChoices.REFUND_IN,
                    refund__status=SaleRefundStatusChoices.COMPLETED
                ).aggregate(total=models.Sum('quantity'))['total'] or 0
                
                available_to_reverse = abs(out_move.quantity) - already_reversed
                
                if available_to_reverse <= 0:
                    continue  # This move fully reversed already
                
                # Calculate how much to reverse from this move
                qty_from_this_move = min(qty_to_reverse - qty_reversed, available_to_reverse)
                
                # Check idempotency: does this refund already have a move for this source?
                existing_move = StockMove.objects.filter(
                    refund=refund,
                    source_move=out_move
                ).first()
                
                if existing_move:
                    # Already created (shouldn't happen in normal flow, but idempotency)
                    qty_reversed += existing_move.quantity
                    stock_moves.append(existing_move)
                    continue
                
                # Create REFUND_IN move (exact reversal of OUT move)
                refund_move = StockMove(
                    product=out_move.product,
                    location=out_move.location,
                    batch=out_move.batch,  # EXACT batch (NO FEFO)
                    move_type=StockMoveTypeChoices.REFUND_IN,
                    quantity=qty_from_this_move,  # Positive
                    sale=sale,
                    sale_line=sale_line,
                    refund=refund,  # Link to refund
                    source_move=out_move,  # Link to original OUT
                    reference_type='PartialRefund',
                    reference_id=str(refund.id),
                    reason=f'Partial refund {refund.id} - {sale_line.product_name} ({qty_from_this_move} units)',
                    created_by=created_by
                )
                refund_move.full_clean()
                refund_move.save()
                stock_moves.append(refund_move)
                
                # Update StockOnHand
                stock, created = StockOnHand.objects.get_or_create(
                    product=refund_move.product,
                    location=refund_move.location,
                    batch=refund_move.batch,
                    defaults={'quantity_on_hand': 0}
                )
                stock.quantity_on_hand += refund_move.quantity
                stock.save()
                
                qty_reversed += qty_from_this_move
            
            # VALIDATION: Ensure we reversed the full quantity
            if qty_reversed < qty_to_reverse:
                raise ValidationError(
                    f"Insufficient original stock moves to reverse {qty_to_reverse} units "
                    f"for line '{sale_line.product_name}'. Only {qty_reversed} units available."
                )
        
        # Mark refund as COMPLETED
        refund.status = SaleRefundStatusChoices.COMPLETED
        refund.save()
        
        return refund
    
    except Exception as e:
        # LOG FAILURE (no FAILED status - transaction.atomic will rollback everything)
        # Structured logging without PHI/PII
        logger.error(
            "refund_partial_for_sale_failed",
            extra={
                'sale_id': str(sale.id),
                'idempotency_key': idempotency_key,
                'error_type': type(e).__name__,
                'error_message': str(e)[:200],  # Truncate to avoid huge messages
                'refund_id': str(refund.id) if refund.id else None,
            }
        )
        # Re-raise to trigger transaction rollback (no FAILED refund persisted)
        raise
