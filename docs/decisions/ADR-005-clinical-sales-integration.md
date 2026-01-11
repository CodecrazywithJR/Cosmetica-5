# ADR-005: Clinical → Sales Integration (Fase 3 - Billing without Fiscal)

**Status:** Accepted  
**Date:** 2025-01-XX  
**Deciders:** Clinical + Sales + Engineering  
**Related:** ADR-003 (Clinical Core), ADR-004 (Practitioners & Appointments)

---

## Context

After completing **EMR v1** (Fase 2.1: Treatment catalog + Encounter-Treatment linking, Fase 2.2: Practitioners + Appointments), we needed to integrate the **Clinical domain** with the **Sales domain** to enable billing for clinical services performed during encounters.

### Business Requirements

**From Clinical perspective**:
- **Practitioners** finalize encounters with documented treatments performed
- Need to generate **billing proposals** from finalized encounters
- Proposal should be **reviewable** before converting to sale (not automatic)
- Practitioner should **control** when billing happens (explicit, not magic)

**From Sales perspective**:
- **Reception** receives proposals and converts them to sales (draft status)
- Sales need to capture **pricing snapshot** from clinical act (immutable)
- Need **audit trail** of clinical origin (which encounter, which treatments)
- Sales should remain in **DRAFT** status until payment received

**From Accounting perspective**:
- Need to **review proposals** for billing accuracy
- Need to **track conversion** from clinical act to sale
- Need **historical record** of pricing decisions

### Business Problems

1. **Direct Encounter → Sale is too coupled**: Clinical staff shouldn't interact with Sales domain directly
2. **Automatic conversion is dangerous**: No review workflow, hard to debug, loses practitioner control
3. **Pricing needs to be immutable**: Once proposal generated, pricing shouldn't change if treatment catalog updated
4. **Audit trail is missing**: If sale created directly, no record of review/approval workflow

### Constraints (Fase 3)

- ✅ **NO romper Sales/Stock/Refunds** (marcados como STABLE)
- ✅ **NO crear ventas automáticamente** al cerrar un Encounter
- ✅ **NO implementar impuestos, TVA, ni facturación legal** (deferred to future fiscal module)
- ✅ **Integración EXPLÍCITA y auditable** (no signals, only API actions)
- ✅ **Todo debe ser reversible** (sale in draft, can be cancelled before payment)

---

## Decision

### Core Solution: Intermediate Proposal Model

**Decision**: Create `ClinicalChargeProposal` as an **explicit intermediate step** between `Encounter` and `Sale`.

This is **NOT a Sale** (it lives in the `clinical` domain), and it's **NOT automatic** (requires explicit API calls).

### Architecture: Two-Step Explicit Flow

```
┌─────────────┐  Practitioner     ┌──────────────────────────┐  Reception        ┌──────────┐
│  Encounter  │  finalizes +      │ ClinicalChargeProposal   │  reviews +        │   Sale   │
│  (clinical) │  clicks "Bill"    │    (clinical domain)     │  clicks "Create"  │ (sales)  │
│             ├──────────────────►│                          ├──────────────────►│          │
│  FINALIZED  │  POST /generate-  │  status=DRAFT            │  POST /create-    │ status=  │
│             │   proposal/       │  (reviewable)            │   sale/           │  DRAFT   │
└─────────────┘                   └──────────────────────────┘                   └──────────┘
     │                                      │                                           │
     │ Has treatments with pricing          │ Immutable pricing snapshot                │ Ready for payment
     │ (EncounterTreatment.effective_price) │ (unit_price, quantity, line_total)        │ (can be edited before paid)
```

### Why This Design?

| Requirement | How ClinicalChargeProposal Solves It |
|-------------|--------------------------------------|
| **Explicit workflow** | Two API calls required (generate → convert), no automatic triggers |
| **Audit trail** | Proposal persists after conversion (status=CONVERTED, converted_to_sale FK) |
| **Review workflow** | Proposal sits in DRAFT until Reception/Admin converts to sale |
| **Pricing immutability** | ClinicalChargeProposalLine captures pricing at moment of proposal generation |
| **Separation of concerns** | Clinical domain owns proposal, Sales domain owns sale |
| **Practitioner control** | Practitioner triggers generation, Reception triggers conversion |
| **Idempotency** | OneToOneField (encounter → proposal), FK nullable (proposal → sale) |

---

## Alternatives Considered

### Alternative 1: Direct Encounter → Sale (NO intermediate)

**Pros**:
- Simpler (fewer models)
- Faster (one API call)

**Cons**:
- ❌ **No review workflow** (sale created immediately)
- ❌ **No audit trail** (if sale deleted, no record of clinical origin)
- ❌ **Tight coupling** (clinical staff interact with Sales domain directly)
- ❌ **Hard to reverse** (sale in paid status is hard to cancel)

**Decision**: ❌ **Rejected** - Too risky, no flexibility, loses practitioner control

---

### Alternative 2: Quote System (Proforma)

**Pros**:
- Full quote workflow (draft → approved → invoiced)
- Could handle future pre-treatment quotes
- Comprehensive billing features

**Cons**:
- ❌ **Over-engineered** for current needs (quote system is 4-6 weeks of work)
- ❌ **Scope creep** (introduces pre-treatment quoting, which is future work)
- ❌ **Delayed delivery** (Fase 3 would take 2x longer)

**Decision**: ❌ **Rejected** - YAGNI (You Aren't Gonna Need It)  
**Future Path**: ClinicalChargeProposal can evolve into Quote system in Fase 5 (fiscal module)

---

### Alternative 3: Proposal as Draft Sale

**Pros**:
- Reuses existing Sale model
- Fewer tables

**Cons**:
- ❌ **Wrong domain** (Sale belongs to Sales, not Clinical)
- ❌ **Confusing status** (draft sale vs finalized sale vs proposal)
- ❌ **Breaks separation** (clinical staff create sales directly)

**Decision**: ❌ **Rejected** - Violates domain boundaries

---

## Implementation Details

### 1. Data Model

#### ClinicalChargeProposal (Header)

```python
class ProposalStatusChoices(models.TextChoices):
    DRAFT = 'draft', 'Draft'                    # Reviewable, not converted yet
    CONVERTED = 'converted', 'Converted to Sale'  # Terminal state, cannot be reconverted
    CANCELLED = 'cancelled', 'Cancelled'        # Cancelled before conversion

class ClinicalChargeProposal(models.Model):
    # Relationships
    encounter = models.OneToOneField(Encounter, CASCADE)  # Idempotency: one proposal per encounter
    patient = models.ForeignKey(Patient, PROTECT)
    practitioner = models.ForeignKey(User, PROTECT)
    
    # Status tracking
    status = models.CharField(choices=ProposalStatusChoices.choices, default=DRAFT)
    converted_to_sale = models.ForeignKey(Sale, SET_NULL, null=True)  # Idempotency check
    converted_at = models.DateTimeField(null=True)
    
    # Financial
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)  # Calculated from lines
    currency = models.CharField(max_length=3, default='EUR')
    
    # Audit
    notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(User, PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['patient', 'created_at']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(total_amount__gte=0),
                name='proposal_total_non_negative'
            )
        ]
```

#### ClinicalChargeProposalLine (Detail)

```python
class ClinicalChargeProposalLine(models.Model):
    # Relationships
    proposal = models.ForeignKey(ClinicalChargeProposal, CASCADE, related_name='lines')
    encounter_treatment = models.ForeignKey(EncounterTreatment, PROTECT)
    treatment = models.ForeignKey(Treatment, PROTECT)
    
    # Pricing snapshot (immutable)
    treatment_name = models.CharField(max_length=255)  # Snapshot at time of proposal
    description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)  # Auto-calculated: quantity * unit_price
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        # Auto-calculate line_total if not provided
        if self.line_total is None or self.line_total == 0:
            self.line_total = self.quantity * self.unit_price
        super().save(*args, **kwargs)
    
    class Meta:
        constraints = [
            models.CheckConstraint(check=models.Q(quantity__gt=0), name='proposal_line_quantity_positive'),
            models.CheckConstraint(check=models.Q(unit_price__gte=0), name='proposal_line_unit_price_non_negative'),
            models.CheckConstraint(check=models.Q(line_total__gte=0), name='proposal_line_total_non_negative'),
        ]
```

### 2. Service Layer (Explicit Functions)

#### Service 1: Generate Proposal from Encounter

```python
def generate_charge_proposal_from_encounter(
    encounter: Encounter,
    created_by: User,
    notes: Optional[str] = None
) -> ClinicalChargeProposal:
    """
    Generate ClinicalChargeProposal from finalized Encounter.
    
    Validations:
    - encounter.status == FINALIZED
    - No existing proposal (OneToOne idempotency)
    - Encounter has treatments (at least 1)
    
    Creates:
    - ClinicalChargeProposal (status=DRAFT)
    - ClinicalChargeProposalLine per EncounterTreatment (with pricing snapshot)
    - Atomic transaction
    - Structured logging
    
    Returns: ClinicalChargeProposal instance
    """
```

**Business Rules**:
- Only `FINALIZED` encounters can generate proposals
- Uses `EncounterTreatment.effective_price` (price_override or treatment.default_price)
- Skips treatments with no price (logs warning)
- Description combines treatment.description + encounter_treatment.notes
- **NO TAX calculation** (tax=0, deferred to future)

#### Service 2: Convert Proposal to Sale

```python
def create_sale_from_proposal(
    proposal: ClinicalChargeProposal,
    created_by: User,
    legal_entity: LegalEntity,
    notes: Optional[str] = None
) -> Sale:
    """
    Convert ClinicalChargeProposal to Sale (draft).
    
    Validations:
    - proposal.status == DRAFT
    - proposal.converted_to_sale is None (idempotency)
    - Proposal has lines
    
    Creates:
    - Sale (status=DRAFT, tax=0, discount=0)
    - SaleLine per proposal line (product=null for services)
    - Updates proposal: status=CONVERTED, converted_to_sale, converted_at
    - Atomic transaction
    - Structured logging
    
    Returns: Sale instance (status=DRAFT)
    """
```

**Business Rules**:
- Only `DRAFT` proposals can be converted
- Sale created in `DRAFT` status (can be modified before payment)
- `product=null` for all lines (service charges, no stock impact)
- **NO TAX**: `tax=0`, `total=subtotal` (deferred to future fiscal module)
- Proposal → `CONVERTED` status (terminal, cannot be reconverted)

### 3. API Layer

#### Endpoints

| Endpoint | Method | Role | Description |
|----------|--------|------|-------------|
| `/api/v1/clinical/encounters/{id}/generate-proposal/` | POST | ClinicalOps, Practitioner | Generate proposal from finalized encounter |
| `/api/v1/clinical/proposals/` | GET | All (except Marketing) | List proposals with filters |
| `/api/v1/clinical/proposals/{id}/` | GET | All (except Marketing) | View proposal detail with lines |
| `/api/v1/clinical/proposals/{id}/create-sale/` | POST | Reception, ClinicalOps, Admin | Convert proposal to sale (draft) |

#### RBAC Matrix

| Role | Generate Proposal | View Proposals | Convert to Sale |
|------|-------------------|----------------|-----------------|
| **Admin** | ✅ | ✅ | ✅ |
| **ClinicalOps** | ✅ | ✅ | ✅ |
| **Practitioner** | ✅ (via Encounter) | ✅ (own only) | ❌ |
| **Reception** | ❌ | ✅ | ✅ |
| **Accounting** | ❌ | ✅ (read-only) | ❌ |
| **Marketing** | ❌ | ❌ | ❌ |

**Practitioner Restriction**: Practitioner can only see their own proposals (`proposal.practitioner == request.user`).

### 4. Idempotency Guarantees

| Operation | Idempotency Mechanism | Validation |
|-----------|----------------------|------------|
| **Generate Proposal** | `encounter.OneToOneField(Encounter)` | Raises `ValueError` if proposal exists |
| **Convert to Sale** | `proposal.converted_to_sale` check | Raises `ValueError` if already converted |

Both operations are **atomic** (wrapped in `transaction.atomic()`).

---

## Consequences

### ✅ Benefits

1. **Explicit workflow**: Practitioner decides when to bill, Reception decides when to convert to sale
2. **Audit trail**: Every proposal persists (even after conversion), full history visible
3. **Review workflow**: Proposal can be reviewed before conversion (catch errors early)
4. **Pricing immutability**: Pricing snapshot ensures billing accuracy even if catalog changes
5. **Separation of concerns**: Clinical domain owns proposal, Sales domain owns sale
6. **Idempotency**: Cannot generate duplicate proposals or convert twice
7. **Reversibility**: Sale in draft status can be edited/cancelled before payment

### ⚠️ Costs

1. **Extra table**: `ClinicalChargeProposal` + `ClinicalChargeProposalLine` (2 new tables)
2. **Two API calls**: Requires 2 actions (generate → convert) instead of 1
3. **Slightly slower**: Review workflow adds friction (intended)
4. **Not automatic**: Practitioner must remember to generate proposal (no magic trigger)

### 🔄 Reversibility

- **Proposal in DRAFT**: Can be cancelled (set status=CANCELLED, add cancellation_reason)
- **Sale in DRAFT**: Can be edited or cancelled before payment
- **After payment**: Sale cannot be reversed (requires refund flow, out of scope)

---

## Future Evolution

### Fase 5: Quote System (Pre-Treatment Quotes)

`ClinicalChargeProposal` can evolve into a **Quote System** for pre-treatment pricing:

```
┌──────────────┐  Pre-treatment    ┌───────────────┐  Patient accepts    ┌─────────┐  Treatment done    ┌──────────┐
│  Consultation│  discussion       │  Quote        │  quote              │ Invoice │  payment collected │   Sale   │
│   (draft)    ├──────────────────►│  (DRAFT)      ├────────────────────►│(ISSUED) ├───────────────────►│ (PAID)   │
└──────────────┘                   └───────────────┘                     └─────────┘                    └──────────┘
```

**Changes needed**:
- Rename `ClinicalChargeProposal` → `ClinicalQuote`
- Add `QuoteStatusChoices`: DRAFT → APPROVED → INVOICED → CONVERTED_TO_SALE
- Add `expiry_date` (quote valid for 30 days)
- Add `approval_date`, `approved_by`
- Add `invoice_number` (if pre-treatment invoice issued)

**Benefits**:
- Smooth evolution (no breaking changes, just rename + add fields)
- Proposal workflow is already tested and stable
- Audit trail already exists

### Fase 6: Fiscal Module (Tax, VAT, Legal Invoicing)

When fiscal module implemented, `create_sale_from_proposal()` will:
- Calculate **tax** based on `legal_entity.country_code` + `treatment.tax_category`
- Generate **invoice number** (legal requirement)
- Create **fiscal entry** in accounting system
- Support **multiple tax rates** (VAT 10%, VAT 20%, exempt)

**NO changes needed to `ClinicalChargeProposal` model** (already captures pre-tax amounts correctly).

---

## Validation

### Tests

Comprehensive test suite created: `tests/test_clinical_sales_integration.py` (~1200 lines)

| Test Category | Tests | Coverage |
|---------------|-------|----------|
| **Model Tests** | 6 | Proposal creation, OneToOne constraint, recalculate_total, line auto-calculation, status choices, idempotency |
| **Service Tests** | 8 | Happy path, validations, idempotency, effective_price, description combining, skip free treatments |
| **Permission Tests** | 6 | Reception can convert, Accounting read-only, Marketing no access, Practitioner own proposals only |
| **E2E Test** | 1 | Complete flow: Encounter → Proposal → Sale with idempotency validation |
| **Regression Test** | 1 | Existing Sales API not broken (no FK errors, old sales work) |

**Total**: 22 tests

### Verification Commands

```bash
# 1. Apply migration
python manage.py migrate clinical

# 2. Run new tests
DATABASE_HOST=localhost pytest tests/test_clinical_sales_integration.py -v

# 3. Run regression tests (ensure no breaking changes)
DATABASE_HOST=localhost pytest tests/test_sales.py -v

# 4. Django check
python manage.py check

# 5. Verify endpoints
python manage.py show_urls | grep -E "(proposal|encounter.*generate)"
```

---

## References

- **ADR-003**: Clinical Core v1 (Treatment catalog + Encounter-Treatment linking)
- **ADR-004**: Practitioners & Appointment Management (EMR v1 complete)
- **STABILITY.md**: Updated with "Clinical → Sales Integration: STABLE ✅"
- **CLINICAL_CORE.md**: Section 4 added - "Billing Integration (Non-Fiscal)"

---

## Decision Outcome

✅ **ACCEPTED**

**Rationale**:
- Explicit workflow aligns with business needs (practitioner control, review workflow)
- Intermediate model provides audit trail and flexibility
- Idempotency guarantees prevent billing errors
- Zero breaking changes to existing Sales/Stock/Refunds (constraint met)
- Clear evolution path to Quote system (future-proof)

**Implementation Status**: ✅ **COMPLETE** (Fase 3)

- Models: `ClinicalChargeProposal` + `ClinicalChargeProposalLine` ✅
- Services: `generate_charge_proposal_from_encounter()` + `create_sale_from_proposal()` ✅
- API: 4 endpoints with RBAC ✅
- Tests: 22 comprehensive tests ✅
- Documentation: ADR-005 + STABILITY.md + CLINICAL_CORE.md ✅

**Next Steps** (Future):
1. Fase 5: Evolve to Quote System (pre-treatment quotes)
2. Fase 6: Add fiscal module (tax, VAT, legal invoicing)
3. Monitoring: Add observability for proposal generation rate, conversion rate, avg time to convert
