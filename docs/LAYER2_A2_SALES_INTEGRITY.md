# Layer 2 A2: Sales Domain Integrity

## Overview

This document describes the sales domain integrity implementation, which enforces business rules for `Sale` and `SaleLine` models through database constraints, model validations, serializer validations, and comprehensive tests.

**Implementation Date:** December 15, 2025  
**Migration:** `0001_layer2_a2_sales_integrity.py`  
**Related Docs:** `LAYER2_A1_DOMAIN_INTEGRITY.md` (clinical domain)

## Table of Contents

1. [Sale Status State Machine](#sale-status-state-machine)
2. [Domain Invariants](#domain-invariants)
3. [Model Implementation](#model-implementation)
4. [Serializer Validations](#serializer-validations)
5. [API Endpoints](#api-endpoints)
6. [Migration Strategy](#migration-strategy)
7. [Test Coverage](#test-coverage)
8. [Use Cases](#use-cases)

---

## Sale Status State Machine

### Status Definitions

```python
class SaleStatusChoices(models.TextChoices):
    DRAFT = 'draft'          # Initial state, fully modifiable
    PENDING = 'pending'      # Awaiting payment, modifiable
    PAID = 'paid'            # Payment received (terminal)
    CANCELLED = 'cancelled'  # Sale cancelled (terminal)
    REFUNDED = 'refunded'    # Payment refunded (terminal)
```

### Valid Transitions

```
┌─────────┐
│  DRAFT  │ ─┐
└─────────┘  │
     │       │
     │       ├──────────────┐
     ▼       │              │
┌─────────┐  │              │
│ PENDING │ ─┘              │
└─────────┘                 │
     │                      │
     │                      │
     ▼                      ▼
┌─────────┐            ┌───────────┐
│  PAID   │            │ CANCELLED │
└─────────┘            └───────────┘
     │                      │
     │                      │ (terminal)
     ▼                      │
┌─────────┐                 │
│REFUNDED │                 │
└─────────┘                 │
     │                      │
     │ (terminal)           │
     └──────────────────────┘
```

### Transition Rules

| Current Status | Allowed Next States | Notes |
|----------------|---------------------|-------|
| `draft` | `pending`, `cancelled` | Initial state |
| `pending` | `paid`, `cancelled` | Awaiting payment |
| `paid` | `refunded` | Terminal unless refund |
| `cancelled` | (none) | Terminal state |
| `refunded` | (none) | Terminal state |

### Modifiability Rules

- **Modifiable**: `draft`, `pending` - can add/edit/delete lines, change prices
- **Closed**: `paid`, `cancelled`, `refunded` - **cannot** modify lines or financial fields
- **Exceptions**: Status transitions and reason fields can be updated even when closed

---

## Domain Invariants

### SaleLine Invariants

```python
# INVARIANT 1: Quantity must be positive
SaleLine.quantity > 0

# INVARIANT 2: Unit price must be non-negative
SaleLine.unit_price >= 0

# INVARIANT 3: Discount must be non-negative
SaleLine.discount >= 0

# INVARIANT 4: Discount cannot exceed line subtotal
SaleLine.discount <= (SaleLine.quantity * SaleLine.unit_price)

# INVARIANT 5: Line total calculation
SaleLine.line_total = (SaleLine.quantity * SaleLine.unit_price) - SaleLine.discount

# INVARIANT 6: Cannot modify line if sale is closed
if Sale.status in ['paid', 'cancelled', 'refunded']:
    raise ValidationError('Cannot modify line: sale is closed')
```

### Sale Invariants

```python
# INVARIANT 1: Total calculation
Sale.total = Sale.subtotal + Sale.tax - Sale.discount

# INVARIANT 2: Subtotal equals sum of line totals
Sale.subtotal = sum(line.line_total for line in Sale.lines.all())

# INVARIANT 3: All financial fields non-negative
Sale.subtotal >= 0
Sale.tax >= 0
Sale.discount >= 0
Sale.total >= 0

# INVARIANT 4: Appointment-Patient coherence
if Sale.appointment and Sale.patient:
    Sale.appointment.patient_id == Sale.patient_id
```

### Enforcement Levels

```
┌──────────────────────┬──────────────┬──────────────┬──────────────┐
│ Invariant            │ Database     │ Model        │ Serializer   │
│                      │ Constraint   │ clean()      │ validate()   │
├──────────────────────┼──────────────┼──────────────┼──────────────┤
│ quantity > 0         │ CHECK        │ ✓            │ ✓            │
│ unit_price >= 0      │ CHECK        │ ✓            │ ✓            │
│ discount >= 0        │ CHECK        │ ✓            │ ✓            │
│ line_total >= 0      │ CHECK        │ ✓            │ -            │
│ total >= 0           │ CHECK        │ ✓            │ -            │
│ total calculation    │ -            │ ✓            │ ✓            │
│ appointment-patient  │ -            │ ✓            │ ✓            │
│ immutability         │ -            │ ✓            │ ✓            │
│ discount <= subtotal │ -            │ ✓            │ ✓            │
└──────────────────────┴──────────────┴──────────────┴──────────────┘
```

---

## Model Implementation

### Sale Model

```python
class Sale(models.Model):
    # Relationships
    patient = FK to Patient (nullable - cosmetic sales without patient)
    appointment = FK to Appointment (nullable)
    
    # Identification
    sale_number = CharField (unique, e.g., "INV-2025-001")
    status = SaleStatusChoices (default='draft')
    
    # Financial
    subtotal = DecimalField (calculated from lines)
    tax = DecimalField
    discount = DecimalField
    total = DecimalField (subtotal + tax - discount)
    currency = CharField (ISO 4217, default='USD')
    
    # Notes
    notes = TextField
    cancellation_reason = TextField
    refund_reason = TextField
    
    # Timestamps
    created_at, updated_at, paid_at
    
    # Methods
    def clean(self):
        # Validate appointment-patient coherence
        # Validate total calculation
    
    def recalculate_totals(self):
        # Recalculate subtotal from lines
        # Recalculate total from subtotal + tax - discount
    
    def is_modifiable(self) -> bool:
        # Returns True if status in [draft, pending]
    
    def can_transition_to(self, new_status) -> bool:
        # Check if transition is valid
    
    def transition_to(self, new_status, reason=None):
        # Perform status transition with validation
```

### SaleLine Model

```python
class SaleLine(models.Model):
    sale = FK to Sale (CASCADE)
    
    # Product
    product_name = CharField
    product_code = CharField (nullable)
    description = TextField (nullable)
    
    # Pricing
    quantity = DecimalField (> 0)
    unit_price = DecimalField (>= 0)
    discount = DecimalField (>= 0, default=0)
    line_total = DecimalField (calculated, >= 0)
    
    # Timestamps
    created_at, updated_at
    
    # Methods
    def clean(self):
        # Validate quantity > 0
        # Validate unit_price >= 0
        # Validate discount >= 0 and <= line subtotal
        # Validate line_total calculation
        # Validate sale is modifiable
    
    def calculate_line_total(self):
        # Calculate quantity * unit_price - discount
    
    def save(self, *args, **kwargs):
        # Auto-calculate line_total
        # Trigger sale.recalculate_totals()
```

### Database Constraints

```sql
-- SaleLine constraints
ALTER TABLE sale_lines ADD CONSTRAINT sale_line_quantity_positive
    CHECK (quantity > 0);

ALTER TABLE sale_lines ADD CONSTRAINT sale_line_unit_price_non_negative
    CHECK (unit_price >= 0);

ALTER TABLE sale_lines ADD CONSTRAINT sale_line_discount_non_negative
    CHECK (discount >= 0);

ALTER TABLE sale_lines ADD CONSTRAINT sale_line_total_non_negative
    CHECK (line_total >= 0);

-- Sale constraints
ALTER TABLE sales ADD CONSTRAINT sale_subtotal_non_negative
    CHECK (subtotal >= 0);

ALTER TABLE sales ADD CONSTRAINT sale_tax_non_negative
    CHECK (tax >= 0);

ALTER TABLE sales ADD CONSTRAINT sale_discount_non_negative
    CHECK (discount >= 0);

ALTER TABLE sales ADD CONSTRAINT sale_total_non_negative
    CHECK (total >= 0);
```

---

## Serializer Validations

### SaleLineSerializer

```python
class SaleLineSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        # 1. quantity > 0
        # 2. unit_price >= 0
        # 3. discount >= 0
        # 4. discount <= quantity * unit_price
        # 5. sale must be modifiable
        
        return attrs
```

### SaleSerializer

```python
class SaleSerializer(serializers.ModelSerializer):
    lines = SaleLineSerializer(many=True, read_only=True)
    
    def validate(self, attrs):
        # 1. Appointment-patient coherence
        # 2. Total consistency
        # 3. Cannot modify closed sales (except status transitions)
        # 4. Status transitions must be valid
        
        return attrs
```

### SaleTransitionSerializer

```python
class SaleTransitionSerializer(serializers.Serializer):
    new_status = ChoiceField(choices=SaleStatusChoices.choices)
    reason = CharField(required=False)
    
    def validate(self, attrs):
        # 1. Transition must be valid
        # 2. Reason required for cancellation/refund
        
        return attrs
```

---

## API Endpoints

### Sale Endpoints

#### Create Sale

```http
POST /api/sales/sales/
Content-Type: application/json

{
  "patient": "uuid-patient-id",
  "appointment": "uuid-appointment-id",  // optional
  "sale_number": "INV-2025-001",         // optional
  "status": "draft",
  "tax": "10.00",
  "discount": "0.00",
  "notes": "Customer requested express shipping"
}
```

#### Transition Sale Status

```http
POST /api/sales/sales/{id}/transition/
Content-Type: application/json

{
  "new_status": "paid",
  "reason": "Payment received via credit card"  // optional, required for cancel/refund
}
```

**Response (200 OK):**

```json
{
  "id": "uuid-sale-id",
  "patient": "uuid-patient-id",
  "status": "paid",
  "status_display": "Paid",
  "is_modifiable": false,
  "is_closed": true,
  "paid_at": "2025-01-15T14:30:00Z",
  ...
}
```

**Error (400 Bad Request):**

```json
{
  "new_status": [
    "Invalid transition from draft to paid. Valid transitions: pending, cancelled"
  ]
}
```

#### Recalculate Totals

```http
POST /api/sales/sales/{id}/recalculate/
```

Recalculates `subtotal` from line totals and `total` from `subtotal + tax - discount`.

**Note:** Only allowed for modifiable sales (draft/pending).

### SaleLine Endpoints

#### Create Line

```http
POST /api/sales/lines/
Content-Type: application/json

{
  "sale": "uuid-sale-id",
  "product_name": "Botox Treatment - Forehead",
  "product_code": "BTX-FH-001",
  "quantity": "1.00",
  "unit_price": "250.00",
  "discount": "25.00"
}
```

**Auto-calculated:**
- `line_total = 1.00 * 250.00 - 25.00 = 225.00`
- Sale's `subtotal` and `total` are auto-recalculated

**Error (400 Bad Request - closed sale):**

```json
{
  "non_field_errors": [
    "Cannot modify line: sale is in Paid status. Only draft and pending sales can be modified."
  ]
}
```

---

## Migration Strategy

### Migration File: `0001_layer2_a2_sales_integrity.py`

**Steps:**

1. **Create Models** - Sale, SaleLine
2. **Data Migration** - Clean invalid data BEFORE constraints
   - Fix negative financial values → set to 0
   - Mark sales with invalid data as `cancelled`
   - Clear `appointment` if `appointment.patient != sale.patient`
   - Log all corrections to `ClinicalAuditLog`
3. **Add Constraints** - CHECK constraints on quantities, prices, totals
4. **Add Indexes** - Performance indexes on common queries

### Data Migration Functions

```python
def clean_invalid_sales(apps, schema_editor):
    """
    Fix sales with negative values or inconsistent data.
    Actions:
    - Set negative values to 0
    - Mark as cancelled with reason
    - Log to ClinicalAuditLog
    """
    
def clean_sale_appointment_patient_coherence(apps, schema_editor):
    """
    Clear appointment if appointment.patient != sale.patient.
    """
```

### Rollback Strategy

1. Remove constraints
2. Drop indexes
3. Drop `sale_lines` table (CASCADE)
4. Drop `sales` table

**Note:** Data migration is **irreversible** - corrections are logged but cannot be automatically undone.

---

## Test Coverage

### Test File: `test_layer2_a2_sales_integrity.py`

**10 Test Classes, 20+ Test Cases:**

#### Test Class 1: SaleLine Quantity Constraints (3 tests)
- ✓ `test_sale_line_quantity_must_be_positive_model_level`
- ✓ `test_sale_line_negative_quantity_fails_model`
- ✓ `test_sale_line_positive_quantity_succeeds`

#### Test Class 2: SaleLine Unit Price Constraints (2 tests)
- ✓ `test_sale_line_negative_unit_price_fails_model`
- ✓ `test_sale_line_zero_unit_price_succeeds` (free items)

#### Test Class 3: SaleLine Discount Constraints (2 tests)
- ✓ `test_sale_line_negative_discount_fails`
- ✓ `test_sale_line_discount_exceeds_subtotal_fails`

#### Test Class 4: Sale Total Calculation (2 tests)
- ✓ `test_sale_total_consistency_validation`
- ✓ `test_sale_total_calculation_correct`

#### Test Class 5: Sale Total Equals Sum of Lines (1 test)
- ✓ `test_recalculate_totals_from_lines`

#### Test Class 6: Immutability of Closed Sales (2 tests)
- ✓ `test_cannot_add_line_to_paid_sale_model`
- ✓ `test_can_add_line_to_draft_sale`

#### Test Class 7: Sale-Appointment-Patient Coherence (2 tests)
- ✓ `test_sale_appointment_patient_mismatch_fails_model`
- ✓ `test_sale_with_matching_appointment_patient_succeeds`

#### Test Class 8: Sale Status Transitions (3 tests)
- ✓ `test_valid_transition_draft_to_pending`
- ✓ `test_valid_transition_pending_to_paid`
- ✓ `test_valid_transition_paid_to_refunded`

#### Test Class 9: Invalid Transitions (2 tests)
- ✓ `test_invalid_transition_draft_to_paid_fails`
- ✓ `test_cannot_transition_from_cancelled` (terminal state)

#### Test Class 10: Transition Reason Requirements (2 tests)
- ✓ `test_cancellation_requires_reason_via_endpoint`
- ✓ `test_cancellation_with_reason_succeeds`

### Running Tests

```bash
# Run all sales integrity tests
pytest apps/api/tests/test_layer2_a2_sales_integrity.py -v

# Run specific test class
pytest apps/api/tests/test_layer2_a2_sales_integrity.py::TestSaleStatusTransitions -v

# Run with coverage
pytest apps/api/tests/test_layer2_a2_sales_integrity.py --cov=apps.sales --cov-report=html
```

---

## Use Cases

### Use Case 1: Create Sale with Lines

```python
# 1. Create draft sale
sale = Sale.objects.create(
    patient=patient,
    status=SaleStatusChoices.DRAFT,
    tax=Decimal('10.00'),
    discount=Decimal('0.00'),
)

# 2. Add lines (auto-calculates line_total)
SaleLine.objects.create(
    sale=sale,
    product_name='Botox - Forehead',
    quantity=Decimal('1.00'),
    unit_price=Decimal('250.00'),
    discount=Decimal('25.00'),
    # line_total = 225.00 (auto-calculated)
)

# 3. Recalculate sale totals
sale.recalculate_totals()
sale.save()

# Result:
# sale.subtotal = 225.00
# sale.tax = 10.00
# sale.discount = 0.00
# sale.total = 235.00
```

### Use Case 2: Process Payment

```python
# Validate sale can be paid
assert sale.status == SaleStatusChoices.PENDING
assert sale.total > 0

# Transition to paid
sale.transition_to(SaleStatusChoices.PAID)

# Result:
# sale.status = 'paid'
# sale.paid_at = now()
# sale.is_modifiable() = False (locked)
```

### Use Case 3: Handle Refund

```python
# Only paid sales can be refunded
assert sale.status == SaleStatusChoices.PAID

# Transition with reason
sale.transition_to(
    SaleStatusChoices.REFUNDED,
    reason='Customer not satisfied with treatment results'
)

# Result:
# sale.status = 'refunded'
# sale.refund_reason = 'Customer not satisfied...'
# sale.is_closed() = True
```

### Use Case 4: Sale with Appointment

```python
# Create sale linked to appointment
sale = Sale.objects.create(
    patient=patient,
    appointment=appointment,  # appointment.patient == patient
    status=SaleStatusChoices.DRAFT,
    # ... other fields
)

# Validation ensures coherence
sale.full_clean()  # Passes: same patient

# Invalid case:
sale_invalid = Sale(
    patient=another_patient,
    appointment=appointment,  # appointment.patient != another_patient
)
sale_invalid.full_clean()  # Raises ValidationError
```

### Use Case 5: Modify Draft Sale

```python
# Can modify draft sale
assert sale.is_modifiable() == True

# Add/update/delete lines
SaleLine.objects.create(sale=sale, ...)  # ✓ Allowed

# Change prices
sale.tax = Decimal('15.00')
sale.save()  # ✓ Allowed

# Transition to pending
sale.transition_to(SaleStatusChoices.PENDING)
```

### Use Case 6: Cannot Modify Paid Sale

```python
# Cannot modify paid sale
assert sale.status == SaleStatusChoices.PAID
assert sale.is_modifiable() == False

# Try to add line
line = SaleLine(sale=sale, ...)
line.full_clean()  # ✗ Raises ValidationError: "Cannot modify line: sale is in Paid status"

# Try to change price
sale.tax = Decimal('20.00')
sale.save()  # Saved but validation will fail in serializer

# Only allowed: status transitions (to refunded)
sale.transition_to(SaleStatusChoices.REFUNDED, reason='...')  # ✓ Allowed
```

---

## Comparison with Layer 2 A1 (Clinical Integrity)

| Aspect | Layer 2 A1 (Clinical) | Layer 2 A2 (Sales) |
|--------|----------------------|-------------------|
| **Primary Models** | Encounter, Appointment, SkinPhoto | Sale, SaleLine |
| **Key Invariant** | Encounter.appointment.patient == Encounter.patient | Sale.appointment.patient == Sale.patient |
| **State Machine** | Appointment status transitions | Sale status transitions |
| **Immutability** | N/A | Closed sales (paid/cancelled/refunded) |
| **Financial Logic** | N/A | Total calculation, line totals |
| **Timeline Indexes** | (patient, -created_at) | (patient, -created_at), (status, -created_at) |
| **Tests** | 12 tests | 20+ tests |
| **Migration** | 0004_layer2_a1_clinical_domain_integrity | 0001_layer2_a2_sales_integrity |

---

## References

- **DOMAIN_MODEL.md** - Overall domain structure
- **LAYER2_A1_DOMAIN_INTEGRITY.md** - Clinical domain integrity (parallel implementation)
- **AUDIT_SECURITY.md** - Audit logging security (used by migration)
- **Django Check Constraints:** https://docs.djangoproject.com/en/4.2/ref/models/constraints/
- **DRF Validation:** https://www.django-rest-framework.org/api-guide/validators/

---

## Changelog

**December 15, 2025 - Initial Implementation**
- Created Sale and SaleLine models with full business logic
- Implemented SaleStatusChoices state machine
- Added database constraints (CHECK constraints on quantities, prices, totals)
- Added performance indexes (created_at, status+created_at, patient+created_at)
- Implemented multi-layer validations (model clean(), serializer validate())
- Created transition endpoint POST /sales/{id}/transition/
- Created data migration with audit trail
- Created 20+ comprehensive tests (10 test classes)
- Documentation complete

---

**End of Documentation**
