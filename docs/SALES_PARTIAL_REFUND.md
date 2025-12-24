# Layer 3 C: Sales Partial Refund with Stock Restoration

## Overview

**Layer 3 C** implements a **partial refund system** for paid sales, allowing multiple refunds to be created for the same sale while maintaining precise stock tracking and business rule enforcement.

**Key Capabilities:**
- Create multiple partial refunds for a single PAID sale
- Refund individual line items with precise quantities
- Automatic proportional stock restoration using exact batch/location reversal
- Idempotent operations via unique constraints and optional API keys
- Transaction-safe with full rollback on any error
- RBAC enforcement (Reception and ClinicalOps only, Marketing blocked)

**Related Layers:**
- **Layer 3 A**: Sales-Stock integration (auto-consume on PAID)
- **Layer 3 B**: Full refund with total stock restoration
- **Layer 3 C**: Partial refund with proportional stock restoration (this layer)

---

## Business Rules

### 1. Sale Status Requirements
- **Only PAID sales can be refunded**
- Draft, pending, cancelled, or already-refunded sales are rejected
- Status validation enforced in `refund_partial_for_sale()` service

### 2. Refund Quantity Limits
- `qty_refunded` per line must be > 0
- `sum(qty_refunded)` across all refunds for a line ≤ original `line.quantity`
- Validation enforced in `SaleRefundLine.clean()` method
- Example: Sold 5 units → Refund 3 → Can refund max 2 more

### 3. Stock Restoration Strategy
- **Exact Batch/Location Reversal**: Stock restored to same batch and location as original SALE_OUT
- **NO FEFO Recalculation**: Unlike sales consumption, refunds reverse exactly
- **Proportional Allocation**: Multi-batch sales split refunds proportionally
- **Deterministic Order**: OUT moves processed by `created_at, id` for consistency

### 4. Idempotency
- **Database Level**: `UniqueConstraint(refund, source_move)` prevents duplicate stock moves
- **API Level**: Optional `idempotency_key` in `metadata` prevents duplicate refund creation
- Retry-safe: Calling with same key returns existing refund without side effects

### 5. Permissions (RBAC)
- **Allowed**: Reception, ClinicalOps, Superusers
- **Blocked**: Marketing
- Permission class: `IsReceptionOrClinicalOpsOrAdmin`
- Enforced at API endpoint level

### 6. Service Lines (No Stock)
- Lines with `product=None` are refunded without stock moves
- Only financial reversal, no inventory impact

---

## Data Model

### SaleRefund

Tracks each partial (or full) refund attempt for a sale.

```python
class SaleRefund(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    sale = models.ForeignKey(Sale, related_name='refunds')
    status = models.CharField(choices=SaleRefundStatusChoices.choices)
        # DRAFT → COMPLETED (success) or FAILED (error)
    reason = models.TextField(blank=True)
    created_by = models.ForeignKey(User, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict)
        # Optional: {'idempotency_key': 'unique-key-123'}
    
    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['sale'],
                condition=Q(metadata__has_key='idempotency_key'),
                name='unique_sale_refund_idempotency_key'
            )
        ]
```

**Fields:**
- `status`: Workflow state (draft → completed/failed)
- `metadata.idempotency_key`: Optional API-level deduplication
- `created_by`: Tracks which user initiated refund

**Properties:**
- `total_amount`: Sum of all refund line amounts

### SaleRefundLine

Granular tracking of what was refunded per original sale line.

```python
class SaleRefundLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    refund = models.ForeignKey(SaleRefund, related_name='lines')
    sale_line = models.ForeignKey(SaleLine, related_name='refund_lines')
    qty_refunded = models.DecimalField(max_digits=10, decimal_places=2)
    amount_refunded = models.DecimalField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def clean(self):
        # Validate qty_refunded > 0
        # Validate sum(qty_refunded) <= sale_line.quantity
```

**Validation:**
- `qty_refunded > 0` enforced via `CheckConstraint`
- Over-refund prevention in `clean()` method via aggregation
- Checks all `COMPLETED` refunds to calculate available quantity

### StockMove Extensions

Links partial refund stock movements to original consumption.

```python
class StockMove(models.Model):
    # Existing fields...
    sale = FK(Sale)
    sale_line = FK(SaleLine)
    reversed_move = OneToOneField('self')  # Layer 3 B (full refund)
    
    # NEW Layer 3 C fields:
    refund = FK(SaleRefund, null=True)
        # Which partial refund created this move
    source_move = FK('self', null=True)
        # Which original SALE_OUT is being reversed
    
    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['refund', 'source_move'],
                name='uq_stockmove_refund_source_move'
            )
        ]
```

**Usage:**
- `refund`: Links REFUND_IN move to specific SaleRefund
- `source_move`: Points to original SALE_OUT being reversed
- Constraint ensures no duplicate reversals for same refund+source pair

---

## API Endpoints

### POST /api/sales/{sale_id}/refunds/

Create a partial (or full) refund for a paid sale.

**Permissions:** `IsReceptionOrClinicalOpsOrAdmin`

**Request:**
```json
{
  "reason": "Customer returned 2 units due to defect",
  "idempotency_key": "refund-abc-123",  // optional
  "lines": [
    {
      "sale_line_id": "550e8400-e29b-41d4-a716-446655440000",
      "qty_refunded": 2,
      "amount_refunded": 600.00  // optional, calculated if omitted
    },
    {
      "sale_line_id": "550e8400-e29b-41d4-a716-446655440001",
      "qty_refunded": 1
    }
  ]
}
```

**Response (201 Created):**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "sale_id": "770e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "status_display": "Completed",
  "reason": "Customer returned 2 units due to defect",
  "total_amount": 900.00,
  "created_by": "reception1",
  "created_at": "2024-01-15T10:30:00Z",
  "lines": [
    {
      "id": "880e8400-e29b-41d4-a716-446655440000",
      "sale_line_id": "550e8400-e29b-41d4-a716-446655440000",
      "product_name": "Botox 100U",
      "qty_refunded": 2,
      "amount_refunded": 600.00,
      "created_at": "2024-01-15T10:30:00Z"
    },
    {
      "id": "990e8400-e29b-41d4-a716-446655440000",
      "sale_line_id": "550e8400-e29b-41d4-a716-446655440001",
      "product_name": "Filler 1ml",
      "qty_refunded": 1,
      "amount_refunded": 300.00,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

**Error Responses:**

**400 Bad Request - Sale not PAID:**
```json
{
  "error": "Cannot refund sale: sale must be paid. Current status: Draft"
}
```

**400 Bad Request - Over-refund:**
```json
{
  "error": "Cannot refund 3. Available: 2 (original 5 - already refunded 3)"
}
```

**403 Forbidden - Marketing user:**
```json
{
  "detail": "Access to refund operations requires Reception or ClinicalOps role, or admin privileges."
}
```

### GET /api/sales/{sale_id}/refunds/

List all refunds for a sale.

**Permissions:** `IsReceptionOrClinicalOpsOrAdmin`

**Response (200 OK):**
```json
[
  {
    "id": "660e8400-e29b-41d4-a716-446655440000",
    "sale_id": "770e8400-e29b-41d4-a716-446655440000",
    "status": "completed",
    "total_amount": 600.00,
    "reason": "First partial refund",
    "created_at": "2024-01-15T10:00:00Z",
    "lines": [...]
  },
  {
    "id": "aa0e8400-e29b-41d4-a716-446655440000",
    "sale_id": "770e8400-e29b-41d4-a716-446655440000",
    "status": "completed",
    "total_amount": 300.00,
    "reason": "Second partial refund",
    "created_at": "2024-01-15T14:00:00Z",
    "lines": [...]
  }
]
```

---

## Service Layer

### refund_partial_for_sale()

Core business logic for creating partial refunds.

**Signature:**
```python
@transaction.atomic
def refund_partial_for_sale(
    sale: Sale,
    refund_payload: dict,
    created_by: User = None
) -> SaleRefund
```

**Parameters:**
- `sale`: Sale instance (must be PAID)
- `refund_payload`: Dict with `reason`, `idempotency_key` (optional), `lines` (list)
- `created_by`: User performing refund (for audit)

**Returns:** `SaleRefund` instance with status=COMPLETED

**Raises:**
- `ValidationError`: If sale not PAID, qty exceeds available, invalid sale_line_id

**Algorithm:**

1. **Validate sale status** → Must be PAID
2. **Check idempotency** → If `idempotency_key` exists, return existing refund
3. **Create SaleRefund** (status=DRAFT initially)
4. **For each line in payload:**
   - Validate `sale_line_id` belongs to sale
   - Create `SaleRefundLine` → Triggers `clean()` validation
   - **If product line (not service):**
     - Get original SALE_OUT moves for this `sale_line` (order by `created_at`)
     - **For each OUT move:**
       - Calculate available qty to reverse (considering partial reversals)
       - Create REFUND_IN `StockMove` with:
         - `product`, `location`, `batch` = same as OUT move
         - `quantity` = proportional qty to reverse (positive)
         - `refund` = current SaleRefund
         - `source_move` = original OUT move
       - Update `StockOnHand` for batch/location (+qty)
     - Validate total reversed = qty_refunded
5. **Mark refund COMPLETED** → Commit transaction
6. **Return refund**

**Transaction Safety:**
- Wrapped in `@transaction.atomic`
- On any error → Refund marked FAILED → DB rolled back

---

## Stock Reversal Examples

### Example 1: Single Batch Refund

**Sale:**
- Line: 5 units of Product A @ $300/unit = $1500
- Stock OUT: 5 from BATCH001 at MAIN

**Refund:**
- Refund 2 units

**Result:**
- 1 StockMove REFUND_IN:
  - Product A, BATCH001, MAIN, qty=2
  - `source_move` → original OUT move
  - `refund` → SaleRefund record

**Stock:**
- BATCH001 @ MAIN: +2 units

---

### Example 2: Multi-Batch Proportional Refund

**Sale:**
- Line: 5 units of Product A @ $300/unit = $1500
- Stock OUT (FEFO):
  - 3 from BATCH002 (expires sooner)
  - 2 from BATCH001 (expires later)

**Refund:**
- Refund 4 units

**Algorithm:**
1. Process OUT moves in `created_at` order:
   - OUT1 (BATCH002, qty=3): Reverse 3 units → REFUND_IN(BATCH002, qty=3)
   - OUT2 (BATCH001, qty=2): Reverse 1 unit → REFUND_IN(BATCH001, qty=1)
2. Total reversed: 3 + 1 = 4 ✓

**Result:**
- 2 StockMove REFUND_IN:
  1. Product A, BATCH002, MAIN, qty=3, source_move=OUT1
  2. Product A, BATCH001, MAIN, qty=1, source_move=OUT2

**Stock:**
- BATCH002 @ MAIN: +3 units
- BATCH001 @ MAIN: +1 unit

---

### Example 3: Multiple Refunds on Same Sale

**Sale:**
- Line: 5 units of Product A

**Refund 1:**
- Refund 2 units → SUCCESS

**Refund 2:**
- Refund 2 units → SUCCESS (3 available)

**Refund 3:**
- Attempt to refund 2 units → **FAIL** (only 1 available)

**Validation:**
```python
# In SaleRefundLine.clean()
already_refunded = 2 + 2 = 4
available = 5 - 4 = 1
if qty_refunded (2) > available (1):
    raise ValidationError("Cannot refund 2. Available: 1")
```

---

## Idempotency Mechanics

### Database-Level Idempotency

**Constraint:** `UniqueConstraint(refund, source_move)`

Prevents creating duplicate StockMove records for the same refund reversing the same source OUT.

**Example:**
```python
# First attempt
move1 = StockMove(refund=refund1, source_move=out1, qty=2)  # OK

# Retry (network issue)
move2 = StockMove(refund=refund1, source_move=out1, qty=2)  # FAIL - duplicate
```

**Code Check:**
```python
existing_move = StockMove.objects.filter(
    refund=refund,
    source_move=out_move
).first()

if existing_move:
    # Already created, skip
    return existing_move
```

### API-Level Idempotency

**Mechanism:** `idempotency_key` in `metadata`

**Constraint:** `UniqueConstraint(sale)` with `metadata__has_key='idempotency_key'`

**Usage:**
```python
# Client sends
payload = {
    'idempotency_key': 'refund-2024-01-15-001',
    'lines': [...]
}

# Service checks
existing_refund = SaleRefund.objects.filter(
    sale=sale,
    metadata__idempotency_key='refund-2024-01-15-001'
).first()

if existing_refund:
    return existing_refund  # No side effects
```

**Best Practice:** Generate idempotency keys as `f"refund-{sale.id}-{uuid4()}"`

---

## Testing

### Test Suite: `test_layer3_c_partial_refund.py`

**Coverage: 9 Tests**

1. **test_partial_refund_single_line_creates_refund_in**
   - Refund 2 units from 5-unit sale
   - Validates SaleRefund, SaleRefundLine, StockMove REFUND_IN, StockOnHand update

2. **test_partial_refund_multi_batch_splits_exactly**
   - Refund 4 units from sale that consumed 3+2 from 2 batches
   - Validates proportional reversal (3 from BATCH002, 1 from BATCH001)

3. **test_service_line_refund_creates_no_stock_moves**
   - Refund service line (product=None)
   - Validates refund created but NO StockMove

4. **test_cannot_refund_more_than_sold**
   - Attempt to refund 6 units when only 5 sold
   - Expects ValidationError

5. **test_cannot_refund_more_than_available_after_previous_refund**
   - Create 2 refunds: 3 units → 3 units (should fail, only 2 available)
   - Validates cumulative qty checking

6. **test_refund_requires_paid_sale**
   - Attempt to refund DRAFT sale
   - Expects ValidationError

7. **test_idempotency_key_prevents_duplicate_refunds**
   - Call service twice with same idempotency_key
   - Validates second call returns existing refund

8. **test_reception_can_create_refund**
   - Reception user creates refund
   - Validates permission granted

9. **test_atomicity_rollback_on_stock_update_failure**
   - Simulate StockOnHand.save() failure
   - Validates transaction rollback (no SaleRefund/StockMove created)

**Note:** Test for Marketing permissions (`test_marketing_forbidden`) is enforced at **API endpoint level** via DRF permission classes, tested separately in integration tests.

### Run Tests

```bash
# Run partial refund tests
pytest apps/api/tests/test_layer3_c_partial_refund.py -v

# Run with coverage
pytest apps/api/tests/test_layer3_c_partial_refund.py --cov=apps.sales.services --cov-report=term-missing

# Run all sales tests
pytest apps/api/tests/test_layer3* -v
```

---

## Permissions Testing (API Level)

### Test Marketing User Blocked

```python
# In API integration tests
@pytest.mark.django_db
def test_marketing_cannot_create_refund(api_client, paid_sale, marketing_user):
    """Marketing user blocked from creating refunds."""
    api_client.force_authenticate(user=marketing_user)
    
    url = f'/api/sales/{paid_sale.id}/refunds/'
    payload = {
        'reason': 'Attempted refund',
        'lines': [...]
    }
    
    response = api_client.post(url, payload, format='json')
    
    assert response.status_code == 403
    assert 'Reception or ClinicalOps' in response.data['detail']
```

---

## Edge Cases

### 1. Fully Refunded Sale

After creating multiple partial refunds totaling original sale amount:

**Sale Properties:**
```python
sale.refunded_total_amount  # Decimal('1500.00')
sale.is_fully_refunded      # True
sale.is_partially_refunded  # False
```

**Behavior:**
- Further refund attempts raise ValidationError (no qty available)
- Sale status remains PAID (refunds don't change status)
- Full audit trail in `sale.refunds.all()`

### 2. Over-Refund Attempt

**Scenario:** Sale has 5 units, already refunded 3

**Request:** Refund 3 more units

**Validation:**
```python
already_refunded = 3
available = 5 - 3 = 2
if qty_refunded (3) > available (2):
    raise ValidationError("Cannot refund 3. Available: 2")
```

**Response:** 400 Bad Request with clear error message

### 3. Insufficient Original Stock Moves

**Scenario:** Sale marked PAID but stock moves deleted/corrupted

**Service Logic:**
```python
out_moves = StockMove.objects.filter(
    sale_line=sale_line,
    move_type=SALE_OUT
)

if not out_moves.exists():
    raise ValidationError(
        f"No stock consumption found for line '{sale_line.product_name}'. "
        f"Cannot restore stock for refund."
    )
```

**Prevention:** StockMove records are immutable and never deleted in normal operations

### 4. Batch Already Fully Reversed

**Scenario:** Original OUT of 3 units already reversed in previous refund

**Service Logic:**
```python
already_reversed = StockMove.objects.filter(
    source_move=out_move,
    move_type=REFUND_IN,
    refund__status=COMPLETED
).aggregate(Sum('quantity'))['quantity__sum'] or 0

available_to_reverse = abs(out_move.quantity) - already_reversed

if available_to_reverse <= 0:
    continue  # Skip this OUT, move to next
```

**Result:** Algorithm moves to next OUT move in sequence

---

## Migration Files

### 1. `sales/migrations/0003_add_partial_refund_models.py`

**Operations:**
- `CreateModel: SaleRefund`
- `CreateModel: SaleRefundLine`
- `AddConstraint: unique_sale_refund_idempotency_key`
- `AddConstraint: check_qty_refunded_positive`
- `AddIndex` (7 indexes for performance)

**Dependencies:**
- `sales.0002_add_product_fk_for_stock_integration`

### 2. `stock/migrations/0004_add_partial_refund_fields.py`

**Operations:**
- `AddField: StockMove.refund` (FK to SaleRefund)
- `AddField: StockMove.source_move` (FK to self)
- `AddConstraint: uq_stockmove_refund_source_move`
- `AddIndex: idx_stock_move_refund`
- `AddIndex: idx_stock_move_source`

**Dependencies:**
- `stock.0003_add_refund_support`
- `sales.0003_add_partial_refund_models`

### Run Migrations

```bash
python manage.py migrate sales 0003
python manage.py migrate stock 0004
```

---

## Curl Examples

### Create Partial Refund

```bash
curl -X POST http://localhost:8000/api/sales/770e8400-e29b-41d4-a716-446655440000/refunds/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Customer returned 2 units due to defect",
    "idempotency_key": "refund-2024-01-15-001",
    "lines": [
      {
        "sale_line_id": "550e8400-e29b-41d4-a716-446655440000",
        "qty_refunded": 2,
        "amount_refunded": 600.00
      }
    ]
  }'
```

### List Refunds for Sale

```bash
curl -X GET http://localhost:8000/api/sales/770e8400-e29b-41d4-a716-446655440000/refunds/ \
  -H "Authorization: Token YOUR_TOKEN"
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         API Layer                                │
│  POST /sales/{id}/refunds/  [IsReceptionOrClinicalOpsOrAdmin]  │
│  GET  /sales/{id}/refunds/                                       │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Service Layer                               │
│  refund_partial_for_sale(sale, payload, created_by)             │
│    ├─ Validate sale.status == PAID                              │
│    ├─ Check idempotency_key (optional)                          │
│    ├─ Create SaleRefund (DRAFT)                                 │
│    ├─ For each line:                                            │
│    │   ├─ Create SaleRefundLine (validates qty)                 │
│    │   └─ If product line:                                      │
│    │       ├─ Find original SALE_OUT moves                      │
│    │       ├─ Create REFUND_IN moves (exact batch/location)     │
│    │       └─ Update StockOnHand (+qty)                         │
│    ├─ Mark refund COMPLETED                                     │
│    └─ Return SaleRefund                                         │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Data Layer                                 │
│  SaleRefund ─┬─ SaleRefundLine ─> SaleLine                      │
│              └─ StockMove (REFUND_IN) ──┬─> source_move (OUT)   │
│                                          └─> StockOnHand         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Comparison: Full Refund vs Partial Refund

| Feature | Layer 3 B (Full Refund) | Layer 3 C (Partial Refund) |
|---------|-------------------------|----------------------------|
| **Trigger** | Sale.transition_to(REFUNDED) | API endpoint POST /refunds/ |
| **Scope** | Entire sale | Individual lines, any qty |
| **Multiple Refunds** | No (1:1 relationship) | Yes (N refunds per sale) |
| **Model** | Uses reversed_move OneToOne | Uses refund FK + source_move FK |
| **Idempotency** | Check existing reversed_move | UniqueConstraint(refund, source_move) + idempotency_key |
| **Status Change** | Sale → REFUNDED | Sale stays PAID |
| **Stock Link** | StockMove.reversed_move | StockMove.source_move |
| **Validation** | Status transition rules | SaleRefundLine.clean() |

**When to Use:**
- **Full Refund (Layer 3 B)**: Entire sale canceled/reversed after payment
- **Partial Refund (Layer 3 C)**: Customer returns some items, sale partially fulfilled

---

## Troubleshooting

### Error: "Cannot refund sale: sale must be paid"

**Cause:** Attempting to refund a sale not in PAID status

**Solution:** Ensure sale.status == PAID before calling API

### Error: "Cannot refund X. Available: Y"

**Cause:** Over-refund attempt (sum of refunds > original qty)

**Solution:** Check `sale.refunds.all()` to see existing refunds, calculate available qty

### Error: "No stock consumption found for line"

**Cause:** StockMove records missing for sale_line

**Solution:**
1. Verify sale was properly transitioned to PAID (triggers stock consumption)
2. Check StockMove.objects.filter(sale_line=line, move_type=SALE_OUT)
3. If missing, data integrity issue - investigate

### Error: "Insufficient original stock moves to reverse"

**Cause:** Original OUT moves don't cover qty_refunded (rare)

**Solution:**
1. Verify sum of OUT moves for sale_line
2. Check for orphaned/deleted StockMove records
3. Contact admin for data audit

### Permission Denied (403)

**Cause:** User not in Reception/ClinicalOps group

**Solution:** Verify user.groups.filter(name__in=['Reception', 'ClinicalOps']).exists()

---

## Future Enhancements

1. **Refund Reason Codes**: Structured reason taxonomy (defect, customer request, etc.)
2. **Partial Amount Refunds**: Refund different amount than proportional (manual adjustment)
3. **Refund Approval Workflow**: Draft → Pending Approval → Approved → Completed
4. **Payment Integration**: Auto-process payment gateway refund
5. **Notification System**: Email customer on refund completion
6. **Reporting**: Refund analytics, most refunded products, refund rate by customer

---

## Summary

Layer 3 C provides a **robust, transactional, idempotent partial refund system** that:
- ✅ Allows multiple refunds per sale with precise quantity control
- ✅ Restores stock to exact batch/location (audit-friendly)
- ✅ Enforces business rules via model validation
- ✅ Provides RBAC at API level (Reception/ClinicalOps only)
- ✅ Maintains full audit trail (who, when, why, how much)
- ✅ Handles edge cases (multi-batch, over-refund, services, idempotency)
- ✅ Tested comprehensively (9 tests covering all scenarios)

**Integration Points:**
- Sales module (SaleRefund, SaleRefundLine)
- Stock module (StockMove.refund, StockMove.source_move)
- Auth module (User, Group permissions)
- API layer (DRF viewsets, serializers, permissions)

**Related Documentation:**
- `SALES_STOCK_INTEGRATION.md` (Layer 3 A)
- `SALES_REFUND_STOCK.md` (Layer 3 B)
- API documentation (auto-generated from OpenAPI schema)
