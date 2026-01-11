# Layer 2 A3: Stock/Inventory Domain Integrity with Batch and Expiry Support

## Overview

This document describes the stock/inventory domain integrity implementation with full batch tracking, expiry date management, and FEFO (First Expired, First Out) allocation strategy.

**Implementation Date:** December 16, 2025  
**Migration:** `0001_layer2_a3_stock_batch_expiry.py`  
**Related Docs:** `LAYER2_A1_DOMAIN_INTEGRITY.md` (clinical), `LAYER2_A2_SALES_INTEGRITY.md` (sales)

## Table of Contents

1. [Models](#models)
2. [Domain Invariants](#domain-invariants)
3. [FEFO Allocation Strategy](#fefo-allocation-strategy)
4. [Services](#services)
5. [API Endpoints](#api-endpoints)
6. [Migration Strategy](#migration-strategy)
7. [Test Coverage](#test-coverage)
8. [Use Cases](#use-cases)

---

## Models

### StockLocation

Physical locations where stock is stored.

```python
class StockLocation(models.Model):
    id = UUIDField
    name = CharField  # "Main Warehouse", "Treatment Room 1"
    code = CharField (unique)  # "MAIN-WH", "ROOM-01"
    location_type = ChoiceField  # warehouse, cabinet, clinic_room, other
    is_active = BooleanField
    created_at, updated_at
```

**Constraints:**
- `code` unique
- Indexes: code, is_active

### StockBatch

Batch/lot tracking with expiry dates.

```python
class StockBatch(models.Model):
    id = UUIDField
    product = FK to Product
    batch_number = CharField  # Unique per product
    expiry_date = DateField (nullable)
    received_at = DateField
    metadata = JSONField  # Supplier, quality checks, etc.
    created_at, updated_at
    
    @property is_expired -> bool
    @property days_until_expiry -> int
```

**Constraints:**
- UniqueConstraint(product, batch_number)
- Indexes: (product, expiry_date), expiry_date, batch_number

**Business Rules:**
- batch_number unique per product (same batch number OK for different products)
- expiry_date optional (for non-expirable products), but recommended
- FEFO uses expiry_date for allocation

### StockMove

Auditable stock movements (IN/OUT transactions).

```python
class StockMove(models.Model):
    id = UUIDField
    product = FK to Product
    location = FK to StockLocation
    batch = FK to StockBatch (nullable)
    move_type = ChoiceField  # purchase_in, adjustment_in, transfer_in,
                             # sale_out, adjustment_out, waste_out, transfer_out
    quantity = IntegerField  # Signed: positive for IN, negative for OUT
    reference_type = CharField  # "Sale", "SaleLine", "Adjustment"
    reference_id = CharField
    reason = TextField
    created_at
    created_by = FK to AUTH_USER_MODEL (nullable)
    
    @property is_inbound -> bool
    @property is_outbound -> bool
```

**Constraints:**
- CheckConstraint: quantity != 0
- Indexes: (product, -created_at), (location, -created_at), (batch, -created_at), (move_type, -created_at), (reference_type, reference_id)

**Business Rules:**
- quantity != 0 (cannot have zero movement)
- IN movements (purchase_in, adjustment_in, transfer_in): quantity > 0
- OUT movements (sale_out, adjustment_out, waste_out, transfer_out): quantity < 0
- batch required for OUT movements (enforced at service level)
- Cannot consume from expired batch (unless allow_expired=True)

### StockOnHand

Current stock levels per product/location/batch (calculated/cached).

```python
class StockOnHand(models.Model):
    id = UUIDField
    product = FK to Product
    location = FK to StockLocation
    batch = FK to StockBatch
    quantity_on_hand = IntegerField  # Current available quantity
    updated_at
```

**Constraints:**
- UniqueConstraint(product, location, batch)
- CheckConstraint: quantity_on_hand >= 0 (no negative stock)
- Indexes: (product, location), (location, product), batch

**Business Rules:**
- Updated automatically by StockMove operations
- quantity_on_hand >= 0 (enforced at database and service level)
- Read-only via API (updated by stock moves only)

---

## Domain Invariants

### StockMove Invariants

```python
# INVARIANT 1: Quantity non-zero
StockMove.quantity != 0

# INVARIANT 2: IN movements positive
if StockMove.move_type in [purchase_in, adjustment_in, transfer_in]:
    StockMove.quantity > 0

# INVARIANT 3: OUT movements negative
if StockMove.move_type in [sale_out, adjustment_out, waste_out, transfer_out]:
    StockMove.quantity < 0

# INVARIANT 4: Cannot consume from expired batch
if StockMove.batch.is_expired and StockMove.quantity < 0:
    raise ValidationError('Cannot consume from expired batch')

# INVARIANT 5: Batch required for OUT movements
if StockMove.move_type in [sale_out, ...] and not StockMove.batch:
    raise ValidationError('Batch required for OUT movements')
```

### StockBatch Invariants

```python
# INVARIANT 1: Batch number unique per product
UniqueConstraint(product, batch_number)

# INVARIANT 2: Expiry date validation (informational)
if StockBatch.expiry_date < today:
    # Warning: batch is expired (allowed for historical data)
    pass
```

### StockOnHand Invariants

```python
# INVARIANT 1: Non-negative stock
StockOnHand.quantity_on_hand >= 0

# INVARIANT 2: Unique per (product, location, batch)
UniqueConstraint(product, location, batch)
```

### Enforcement Levels

```
┌──────────────────────────┬──────────────┬──────────────┬──────────────┐
│ Invariant                │ Database     │ Model        │ Service      │
│                          │ Constraint   │ clean()      │ Layer        │
├──────────────────────────┼──────────────┼──────────────┼──────────────┤
│ quantity != 0            │ CHECK        │ ✓            │ ✓            │
│ IN qty > 0               │ -            │ ✓            │ ✓            │
│ OUT qty < 0              │ -            │ ✓            │ ✓            │
│ batch unique per product │ UNIQUE       │ -            │ -            │
│ on_hand >= 0             │ CHECK        │ ✓            │ ✓            │
│ on_hand unique           │ UNIQUE       │ -            │ -            │
│ cannot consume expired   │ -            │ ✓            │ ✓            │
│ FEFO allocation          │ -            │ -            │ ✓            │
└──────────────────────────┴──────────────┴──────────────┴──────────────┘
```

---

## FEFO Allocation Strategy

### Algorithm

**FEFO (First Expired, First Out):** Consume batches with nearest expiry date first.

```python
def allocate_batch_fefo(product, location, quantity_needed, allow_expired=False):
    """
    1. Get all batches with stock > 0 at location for product
    2. Filter out expired batches (unless allow_expired=True)
    3. Sort by expiry_date ASC (earliest first)
    4. Allocate from batches sequentially until quantity_needed met
    5. Return list of (batch, qty) allocations
    """
```

### Example

```
Stock at MAIN-WH for Product SKU-001:
- BATCH-A: 10 units, expires 2025-12-20 (5 days)
- BATCH-B: 50 units, expires 2026-01-15 (30 days)
- BATCH-C: 100 units, expires 2026-03-01 (75 days)

Allocate 15 units using FEFO:
→ Result: [(BATCH-A, 10), (BATCH-B, 5)]

Explanation:
- First consume BATCH-A (10 units, expiring soonest)
- Then consume 5 from BATCH-B (to reach 15 total)
- BATCH-C untouched (furthest expiry)
```

### Edge Cases

**1. Expired Batches**

```python
# Default behavior: skip expired batches
allocate_batch_fefo(product, location, 10)
→ Skips expired batches, uses fresh ones

# If only expired stock available
allocate_batch_fefo(product, location, 10)
→ Raises ExpiredBatchError

# Allow expired batches explicitly
allocate_batch_fefo(product, location, 10, allow_expired=True)
→ Uses expired batches (for disposal/quality control)
```

**2. Insufficient Stock**

```python
# Available: 5 units, Needed: 10 units
allocate_batch_fefo(product, location, 10)
→ Raises InsufficientStockError
```

**3. Multi-Batch Split**

```python
# BATCH-A: 3 units, BATCH-B: 20 units
# Need: 10 units
allocate_batch_fefo(product, location, 10)
→ [(BATCH-A, 3), (BATCH-B, 7)]
```

---

## Services

### Core Service Functions

#### `allocate_batch_fefo()`

```python
def allocate_batch_fefo(
    product,
    location: StockLocation,
    quantity_needed: int,
    allow_expired: bool = False
) -> List[Tuple[StockBatch, int]]:
    """
    Allocate batches using FEFO strategy.
    
    Returns: [(batch, qty), ...]
    Raises: InsufficientStockError, ExpiredBatchError
    """
```

#### `create_stock_move()`

```python
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
    Create stock move and update StockOnHand.
    
    Validates business rules and updates stock levels atomically.
    """
```

#### `create_stock_out_fefo()`

```python
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
    
    This is the recommended way to consume stock.
    Returns list of StockMove instances created.
    """
```

#### `get_stock_summary()`

```python
def get_stock_summary(product, location=None) -> dict:
    """
    Get stock summary for a product.
    
    Returns:
    {
        'total': 150,
        'by_location': {'MAIN-WH': 100, 'ROOM-01': 50},
        'by_batch': {
            'BATCH-A': {'quantity': 10, 'expiry_date': '2025-12-20', ...},
            'BATCH-B': {'quantity': 50, 'expiry_date': '2026-01-15', ...},
        },
        'expired_batches': [
            {'batch': 'BATCH-OLD', 'quantity': 5, 'expiry_date': '2025-12-01', ...}
        ]
    }
    """
```

---

## API Endpoints

### Stock Locations

```http
GET    /api/stock/locations/              - List locations
POST   /api/stock/locations/              - Create location
GET    /api/stock/locations/{id}/         - Get location
PATCH  /api/stock/locations/{id}/         - Update location
DELETE /api/stock/locations/{id}/         - Delete location
```

### Stock Batches

```http
GET    /api/stock/batches/                - List batches
POST   /api/stock/batches/                - Create batch
GET    /api/stock/batches/{id}/           - Get batch
PATCH  /api/stock/batches/{id}/           - Update batch
DELETE /api/stock/batches/{id}/           - Delete batch

GET    /api/stock/batches/expiring-soon/  - Get batches expiring soon (?days=30)
GET    /api/stock/batches/expired/        - Get expired batches with stock
```

### Stock Moves

```http
GET    /api/stock/moves/                  - List moves
POST   /api/stock/moves/                  - Create move (manual)
GET    /api/stock/moves/{id}/             - Get move

POST   /api/stock/moves/consume-fefo/     - Consume stock using FEFO
```

**Example: Consume Stock Using FEFO**

```http
POST /api/stock/moves/consume-fefo/
Content-Type: application/json

{
  "product": "uuid-product-id",
  "location": "uuid-location-id",
  "quantity": 10,
  "move_type": "sale_out",
  "reason": "Sale #INV-2025-001",
  "reference_type": "Sale",
  "reference_id": "uuid-sale-id",
  "allow_expired": false
}
```

**Response (201 Created):**

```json
[
  {
    "id": "uuid-move-1",
    "product": "uuid-product-id",
    "product_sku": "SKU-001",
    "location": "uuid-location-id",
    "batch": "uuid-batch-a",
    "batch_number": "BATCH-A",
    "move_type": "sale_out",
    "quantity": -10,
    "is_outbound": true,
    "created_at": "2025-12-16T10:30:00Z"
  }
]
```

**Error (400 Bad Request - Insufficient Stock):**

```json
{
  "error": "Insufficient stock for SKU-001 at MAIN-WH. Available: 5, needed: 10",
  "error_type": "insufficient_stock"
}
```

**Error (400 Bad Request - Expired Batch):**

```json
{
  "error": "Sufficient stock available (10) but all batches are expired. Available non-expired: 0, needed: 10",
  "error_type": "expired_batch"
}
```

### Stock On Hand

```http
GET    /api/stock/on-hand/                       - List stock levels
GET    /api/stock/on-hand/{id}/                  - Get specific stock level
GET    /api/stock/on-hand/by-product/{product_id}/ - Get stock summary for product
```

**Example: Get Stock Summary**

```http
GET /api/stock/on-hand/by-product/uuid-product-id/
```

**Response:**

```json
{
  "summary": {
    "total": 150,
    "by_location": {
      "MAIN-WH": 100,
      "ROOM-01": 50
    },
    "by_batch": {
      "BATCH-A": {
        "quantity": 10,
        "expiry_date": "2025-12-20",
        "is_expired": false,
        "location": "MAIN-WH"
      },
      "BATCH-B": {
        "quantity": 50,
        "expiry_date": "2026-01-15",
        "is_expired": false,
        "location": "MAIN-WH"
      }
    },
    "expired_batches": []
  },
  "records": [
    {
      "id": "uuid-onhand-1",
      "product_sku": "SKU-001",
      "location_code": "MAIN-WH",
      "batch_number": "BATCH-A",
      "batch_expiry_date": "2025-12-20",
      "batch_is_expired": false,
      "quantity_on_hand": 10
    }
  ]
}
```

---

## Migration Strategy

### Migration File: `0001_layer2_a3_stock_batch_expiry.py`

**Steps:**

1. **Create Models** - StockLocation, StockBatch, StockMove (expanded), StockOnHand
2. **Data Migration** - Migrate existing Product.stock_quantity to batch-based system
   - Create default location "MAIN-WAREHOUSE"
   - For each product with stock > 0:
     - Create batch "UNKNOWN-INITIAL-{sku}"
     - Set expiry_date to 10 years in future (to avoid FEFO issues)
     - Create StockOnHand record
   - Log migration metadata in batch.metadata
3. **Add Constraints** - CHECK constraints, UniqueConstraints
4. **Add Indexes** - Performance indexes

### Data Migration Logic

```python
def migrate_existing_stock_to_batches(apps, schema_editor):
    """
    Strategy:
    - Create MAIN-WAREHOUSE location
    - For each Product with stock_quantity > 0:
      - Create batch "UNKNOWN-INITIAL-{sku}"
      - expiry_date = today + 10 years (far future)
      - Create StockOnHand(product, MAIN-WAREHOUSE, batch, quantity=stock_quantity)
    - Keep Product.stock_quantity unchanged (backward compatibility)
    """
```

**Rationale:**
- Uses far-future expiry to avoid FEFO issues with unknown batches
- Preserves existing stock data
- Allows gradual migration to batch-based system
- Product.stock_quantity can be deprecated later

### Rollback Strategy

```python
def reverse_stock_migration(apps, schema_editor):
    """
    - Delete all StockOnHand records
    - Delete UNKNOWN-INITIAL batches
    - Delete MAIN-WAREHOUSE location
    """
```

---

## Test Coverage

### Test File: `test_layer2_a3_stock_batch_expiry.py`

**12 Test Classes, 25+ Test Cases:**

1. **TestStockMoveQuantityConstraint** (3 tests)
   - quantity cannot be zero
   - positive quantity succeeds
   - negative quantity succeeds

2. **TestStockMoveTypeSignConstraint** (2 tests)
   - IN movement must have positive quantity
   - OUT movement must have negative quantity

3. **TestBatchUniquePerProduct** (2 tests)
   - duplicate batch number same product fails
   - same batch number different products succeeds

4. **TestCannotConsumeExpiredBatch** (2 tests)
   - cannot consume from expired batch
   - can add to expired batch (IN allowed)

5. **TestCannotConsumeMoreThanOnHand** (2 tests)
   - cannot consume more than available
   - can consume exact amount available

6. **TestFEFOPicksEarliestExpiry** (1 test)
   - FEFO picks expiring soon over fresh

7. **TestFEFOSkipsExpiredBatches** (3 tests)
   - FEFO skips expired batch by default
   - FEFO raises error if only expired stock
   - FEFO allows expired if flag set

8. **TestFEFOMultiBatchAllocation** (1 test)
   - FEFO allocates from multiple batches

9. **TestStockOnHandNonNegative** (2 tests)
   - stock on hand cannot be negative
   - stock on hand zero succeeds

10. **TestCreateStockOutFEFO** (2 tests)
    - creates stock moves correctly
    - stores reference info

11. **TestBatchExpiryProperties** (4 tests)
    - is_expired property
    - days_until_expiry calculation

12. **TestStockOnHandUniqueConstraint** (1 test)
    - enforces unique (product, location, batch)

### Running Tests

```bash
# Run all stock tests
pytest apps/api/tests/test_layer2_a3_stock_batch_expiry.py -v

# Run specific test class
pytest apps/api/tests/test_layer2_a3_stock_batch_expiry.py::TestFEFOPicksEarliestExpiry -v

# Run with coverage
pytest apps/api/tests/test_layer2_a3_stock_batch_expiry.py --cov=apps.stock --cov-report=html
```

---

## Use Cases

### Use Case 1: Receive Stock (Purchase In)

```python
from apps.stock.models import StockLocation, StockBatch, StockMoveTypeChoices
from apps.stock.services import create_stock_move
from apps.products.models import Product

# Get product and location
product = Product.objects.get(sku='BOTOX-100')
location = StockLocation.objects.get(code='MAIN-WH')

# Create batch for new shipment
batch = StockBatch.objects.create(
    product=product,
    batch_number='LOT-2025-001',
    expiry_date='2026-12-31',
    received_at='2025-12-16',
    metadata={
        'supplier': 'MedSupply Inc',
        'po_number': 'PO-12345'
    }
)

# Record purchase
move = create_stock_move(
    product=product,
    location=location,
    batch=batch,
    move_type=StockMoveTypeChoices.PURCHASE_IN,
    quantity=50,  # Positive for IN
    reason='Purchase order PO-12345',
    created_by=request.user
)

# Stock automatically updated
# StockOnHand(product=BOTOX-100, location=MAIN-WH, batch=LOT-2025-001, quantity_on_hand=50)
```

### Use Case 2: Consume Stock for Sale (FEFO)

```python
from apps.stock.services import create_stock_out_fefo

# Consume 10 units using FEFO
moves = create_stock_out_fefo(
    product=product,
    location=location,
    quantity=10,
    move_type=StockMoveTypeChoices.SALE_OUT,
    reference_type='Sale',
    reference_id=str(sale.id),
    reason=f'Sale {sale.sale_number}',
    created_by=request.user
)

# FEFO automatically:
# 1. Selected batch(es) with earliest expiry
# 2. Created StockMove record(s)
# 3. Updated StockOnHand
# 4. Returned list of moves created

for move in moves:
    print(f"Consumed {abs(move.quantity)} from batch {move.batch.batch_number}")
```

### Use Case 3: Check Stock Availability

```python
from apps.stock.services import get_stock_summary

# Get stock summary
summary = get_stock_summary(product)

print(f"Total stock: {summary['total']}")
print(f"By location: {summary['by_location']}")

# Check for expired stock
if summary['expired_batches']:
    print("Warning: Expired batches found:")
    for exp_batch in summary['expired_batches']:
        print(f"  - {exp_batch['batch']}: {exp_batch['quantity']} units")
```

### Use Case 4: Transfer Stock Between Locations

```python
# OUT from source location
out_moves = create_stock_out_fefo(
    product=product,
    location=source_location,
    quantity=20,
    move_type=StockMoveTypeChoices.TRANSFER_OUT,
    reference_type='Transfer',
    reference_id='XFER-001',
    reason='Transfer to Treatment Room 1'
)

# IN to destination location (use same batch)
batch = out_moves[0].batch
in_move = create_stock_move(
    product=product,
    location=dest_location,
    batch=batch,
    move_type=StockMoveTypeChoices.TRANSFER_IN,
    quantity=20,
    reference_type='Transfer',
    reference_id='XFER-001',
    reason='Transfer from Main Warehouse'
)
```

### Use Case 5: Dispose of Expired Stock

```python
from apps.stock.models import StockOnHand

# Find expired batches with stock
expired_stocks = StockOnHand.objects.filter(
    quantity_on_hand__gt=0,
    batch__expiry_date__lt=timezone.now().date()
).select_related('product', 'batch', 'location')

# Dispose each expired batch
for stock in expired_stocks:
    create_stock_out_fefo(
        product=stock.product,
        location=stock.location,
        quantity=stock.quantity_on_hand,
        move_type=StockMoveTypeChoices.WASTE_OUT,
        reason=f'Expired on {stock.batch.expiry_date}',
        allow_expired=True  # Required to consume expired batches
    )
```

### Use Case 6: Stock Adjustment (Inventory Count)

```python
# After physical inventory count
physical_count = 45
current_stock = StockOnHand.objects.get(
    product=product,
    location=location,
    batch=batch
)

difference = physical_count - current_stock.quantity_on_hand

if difference != 0:
    move_type = (
        StockMoveTypeChoices.ADJUSTMENT_IN if difference > 0
        else StockMoveTypeChoices.ADJUSTMENT_OUT
    )
    
    create_stock_move(
        product=product,
        location=location,
        batch=batch,
        move_type=move_type,
        quantity=difference,  # Can be positive or negative
        reason=f'Physical inventory count: {physical_count} units',
        created_by=request.user
    )
```

---

## Integration Notes

### Integration with Sales (Layer 2 A2)

**Future Enhancement:** Add `product` FK to `SaleLine`:

```python
class SaleLine(models.Model):
    sale = FK to Sale
    product = FK to Product (nullable)  # NEW
    product_name = CharField  # Fallback for services
    # ...
```

Then implement automatic stock commit:

```python
from apps.stock.services import create_stock_out_fefo

@receiver(post_save, sender=Sale)
def commit_stock_on_sale_paid(sender, instance, **kwargs):
    if instance.status == SaleStatusChoices.PAID:
        # Check if already committed (idempotent)
        existing = StockMove.objects.filter(
            reference_type='Sale',
            reference_id=str(instance.id)
        ).exists()
        
        if not existing:
            location = StockLocation.objects.get(code='MAIN-WH')
            
            for line in instance.lines.all():
                if line.product:  # Skip service lines
                    create_stock_out_fefo(
                        product=line.product,
                        location=location,
                        quantity=int(line.quantity),
                        move_type=StockMoveTypeChoices.SALE_OUT,
                        reference_type='SaleLine',
                        reference_id=str(line.id)
                    )
```

### Products Without Batches

Some products may not require batch tracking (e.g., services, consumables).

**Option 1:** Create a single "NO-BATCH" batch per product  
**Option 2:** Make `StockMove.batch` nullable and handle accordingly

Current implementation: Batch is nullable but recommended for all physical products.

---

## Comparison with Previous Layers

| Aspect | Layer 2 A1 (Clinical) | Layer 2 A2 (Sales) | Layer 2 A3 (Stock) |
|--------|----------------------|-------------------|-------------------|
| **Primary Models** | Encounter, Appointment | Sale, SaleLine | StockLocation, StockBatch, StockMove, StockOnHand |
| **Key Invariant** | Encounter-Appointment-Patient coherence | Sale total consistency | Stock non-negative, FEFO allocation |
| **State Machine** | Appointment status | Sale status | Move type (IN/OUT) |
| **Immutability** | N/A | Closed sales | Historical moves (append-only) |
| **Financial Logic** | N/A | Total calculation | N/A |
| **Expiry Logic** | N/A | N/A | Batch expiry + FEFO |
| **Tests** | 12 tests | 20+ tests | 25+ tests |
| **Lines Added** | ~200 | ~850 | ~1200 |

---

## References

- **DOMAIN_MODEL.md** - Overall domain structure
- **LAYER2_A1_DOMAIN_INTEGRITY.md** - Clinical domain integrity
- **LAYER2_A2_SALES_INTEGRITY.md** - Sales domain integrity
- **Django Check Constraints:** https://docs.djangoproject.com/en/4.2/ref/models/constraints/
- **FEFO Strategy:** https://en.wikipedia.org/wiki/FIFO_and_LIFO_accounting#FEFO

---

## Changelog

**December 16, 2025 - Initial Implementation**
- Created StockLocation, StockBatch, StockOnHand models
- Expanded StockMove with location, batch, new move types
- Implemented FEFO allocation service
- Added database constraints (quantity != 0, on_hand >= 0, uniqueness)
- Added 13 performance indexes
- Created data migration (UNKNOWN-INITIAL batches)
- Created 25+ comprehensive tests (12 test classes)
- Created complete API endpoints
- Documentation complete

---

**End of Documentation**
