# Clinical Core v1 (EMR) - Implementation Guide

**Version**: 1.0  
**Last Updated**: 2024-12-22  
**Status**: ✅ **PRODUCTION READY**

---

## Overview

The **Clinical Core v1** provides a minimal Electronic Medical Record (EMR) system for tracking:
- Patient encounters (consultations, procedures, visits)
- Treatments performed during encounters
- Clinical documentation (chief complaint, assessment, plan, notes)
- Practitioner involvement

This is a **backend-only** implementation with DRF APIs and RBAC permissions.

---

## Architecture

### Domain Model

```
┌─────────────┐
│   Patient   │ (existing model in apps.clinical)
└──────┬──────┘
       │
       │ 1:N
       ▼
┌─────────────┐       ┌──────────────┐
│ Appointment │ N:1   │ Practitioner │ (existing model in apps.authz)
└──────┬──────┘ ───── └──────────────┘
       │
       │ 1:1 (optional)
       ▼
┌─────────────┐       ┌──────────────┐
│  Encounter  │ N:1   │ Practitioner │
└──────┬──────┘ ───── └──────────────┘
       │
       │ N:M (via EncounterTreatment)
       ▼
┌─────────────┐       ┌──────────────┐
│  Treatment  │◄──────│EncounterTreat│
└─────────────┘       └──────────────┘
```

### Key Relationships

1. **Patient → Appointment** (1:N): A patient can have multiple appointments
2. **Appointment → Encounter** (1:1 optional): An appointment MAY result in an encounter
3. **Encounter → Patient** (N:1): An encounter belongs to one patient
4. **Encounter → Practitioner** (N:1): An encounter is performed by one practitioner
5. **Encounter ↔ Treatment** (N:M): An encounter can have multiple treatments, via `EncounterTreatment`

---

## Models

### 1. Treatment (Catalog)

**Purpose**: Master catalog of all available treatments/procedures.

**Fields**:
| Field          | Type             | Constraints        | Description                                    |
|----------------|------------------|--------------------|------------------------------------------------|
| `id`           | UUID             | Primary Key        | Unique identifier                              |
| `name`         | CharField(255)   | Unique, NOT NULL   | Treatment name (e.g., "Botox Injection")       |
| `description`  | TextField        | Nullable           | Detailed description                           |
| `is_active`    | BooleanField     | Default=True       | Soft disable inactive treatments               |
| `default_price`| Decimal(10,2)    | Nullable           | Default price in EUR (nullable for flexibility)|
| `requires_stock`| BooleanField    | Default=False      | If true, check stock availability (future)     |
| `created_at`   | DateTimeField    | Auto              | Creation timestamp                             |
| `updated_at`   | DateTimeField    | Auto              | Last update timestamp                          |

**Indexes**:
- `idx_treatment_active` on `is_active`
- `idx_treatment_name` on `name`

**Business Rules**:
- Cannot delete treatments with encounter references (PROTECT constraint)
- Soft-disable via `is_active=false` (no hard deletes)
- `default_price` is nullable (allows per-encounter custom pricing)

**Example Records**:
```python
Treatment(name="Consultation - Dermatology", default_price=100.00)
Treatment(name="Botox Injection", default_price=300.00, requires_stock=True)
Treatment(name="Chemical Peel", default_price=250.00)
Treatment(name="Hyaluronic Acid Filler", default_price=450.00, requires_stock=True)
```

---

### 2. EncounterTreatment (Linking Table)

**Purpose**: Links encounters to treatments with metadata (quantity, price, notes).

**Fields**:
| Field        | Type             | Constraints            | Description                                   |
|--------------|------------------|------------------------|-----------------------------------------------|
| `id`         | UUID             | Primary Key            | Unique identifier                             |
| `encounter`  | FK(Encounter)    | CASCADE, NOT NULL      | The encounter this treatment belongs to       |
| `treatment`  | FK(Treatment)    | PROTECT, NOT NULL      | The treatment catalog reference               |
| `quantity`   | PositiveIntField | Default=1, >=1         | Number of units (e.g., 2 vials of filler)     |
| `unit_price` | Decimal(10,2)    | Nullable               | Overrides Treatment.default_price             |
| `notes`      | TextField        | Nullable               | Practitioner notes (e.g., "Applied to forehead")|
| `created_at` | DateTimeField    | Auto                   | Creation timestamp                            |
| `updated_at` | DateTimeField    | Auto                   | Last update timestamp                         |

**Constraints**:
- **Unique**: `(encounter, treatment)` - No duplicate treatments per encounter
- **CASCADE on Encounter**: Delete links when encounter is deleted
- **PROTECT on Treatment**: Cannot delete treatments referenced by encounters

**Computed Properties**:
```python
@property
def effective_price(self) -> Decimal:
    """Returns unit_price if set, else Treatment.default_price."""
    return self.unit_price if self.unit_price else self.treatment.default_price

@property
def total_price(self) -> Decimal:
    """Returns quantity * effective_price."""
    return self.quantity * self.effective_price if self.effective_price else None
```

**Example**:
```python
EncounterTreatment(
    encounter=encounter_123,
    treatment=botox_treatment,
    quantity=2,
    unit_price=350.00,  # Override default 300.00
    notes="Forehead and glabella"
)
# total_price = 2 * 350.00 = 700.00
```

---

### 3. Encounter (Existing Model - Extended)

**Purpose**: Clinical visit/consultation/procedure record.

**Key Fields** (for reference):
- `patient`: FK to Patient (CASCADE)
- `practitioner`: FK to Practitioner (SET_NULL)
- `location`: FK to ClinicLocation (SET_NULL)
- `type`: Enum (medical_consult, cosmetic_consult, aesthetic_procedure, follow_up, sale_only)
- `status`: Enum (draft, finalized, cancelled)
- `occurred_at`: DateTime
- `chief_complaint`, `assessment`, `plan`, `internal_notes`: TextField (nullable)

**New Relationship**:
- `encounter_treatments`: Reverse FK to EncounterTreatment (many-to-many via linking table)

**State Transitions**:
```
draft → finalized (normal closure)
draft → cancelled (abandoned)
finalized → [TERMINAL] (immutable)
cancelled → [TERMINAL] (immutable)
```

---

## API Endpoints

### Treatment Endpoints

**Base URL**: `/api/v1/clinical/treatments/`

#### List Treatments
```http
GET /api/v1/clinical/treatments/
Authorization: Bearer <token>

Query Parameters:
- include_inactive=true  # Include inactive treatments (default: false)
- q=search_term          # Search by name (case-insensitive)

Response: 200 OK
[
  {
    "id": "uuid",
    "name": "Botox Injection",
    "description": "Botulinum toxin...",
    "is_active": true,
    "default_price": "300.00",
    "requires_stock": true,
    "created_at": "2024-12-22T10:00:00Z",
    "updated_at": "2024-12-22T10:00:00Z"
  }
]
```

#### Create Treatment
```http
POST /api/v1/clinical/treatments/
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "name": "Botox Injection",
  "description": "Botulinum toxin for wrinkles",
  "default_price": "300.00",
  "requires_stock": true
}

Response: 201 Created
{
  "id": "uuid",
  "name": "Botox Injection",
  ...
}
```

#### Update Treatment
```http
PATCH /api/v1/clinical/treatments/{id}/
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "default_price": "350.00"
}

Response: 200 OK
```

---

### Encounter Endpoints

**Base URL**: `/api/v1/clinical/encounters/`

#### List Encounters
```http
GET /api/v1/clinical/encounters/
Authorization: Bearer <practitioner_token>

Query Parameters:
- patient_id=uuid         # Filter by patient
- practitioner_id=uuid    # Filter by practitioner
- status=draft|finalized  # Filter by status
- date_from=YYYY-MM-DD    # Filter by occurred_at >= date_from
- date_to=YYYY-MM-DD      # Filter by occurred_at <= date_to

Response: 200 OK
[
  {
    "id": "uuid",
    "patient": "uuid",
    "patient_name": "John Doe",
    "practitioner": "uuid",
    "practitioner_name": "Dr. Jane Smith",
    "type": "aesthetic_procedure",
    "status": "draft",
    "occurred_at": "2024-12-22T14:00:00Z",
    "treatment_count": 2,
    "created_at": "2024-12-22T14:00:00Z"
  }
]
```

#### Get Encounter Detail
```http
GET /api/v1/clinical/encounters/{id}/
Authorization: Bearer <practitioner_token>

Response: 200 OK
{
  "id": "uuid",
  "patient": {
    "id": "uuid",
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com",
    "phone": "+33612345678"
  },
  "practitioner": {
    "id": "uuid",
    "display_name": "Dr. Jane Smith",
    "specialty": "Dermatology"
  },
  "location": "uuid",
  "type": "aesthetic_procedure",
  "status": "draft",
  "occurred_at": "2024-12-22T14:00:00Z",
  "chief_complaint": "Wrinkles on forehead",
  "assessment": "Dynamic wrinkles suitable for botulinum toxin",
  "plan": "Botox 20 units forehead",
  "internal_notes": "Patient has no contraindications",
  "encounter_treatments": [
    {
      "id": "uuid",
      "treatment_id": "uuid",
      "treatment": {
        "id": "uuid",
        "name": "Consultation - Dermatology",
        "default_price": "100.00"
      },
      "quantity": 1,
      "unit_price": null,
      "notes": "Initial consultation",
      "effective_price": "100.00",
      "total_price": "100.00",
      "created_at": "2024-12-22T14:00:00Z",
      "updated_at": "2024-12-22T14:00:00Z"
    },
    {
      "id": "uuid",
      "treatment_id": "uuid",
      "treatment": {
        "id": "uuid",
        "name": "Botox Injection",
        "default_price": "300.00"
      },
      "quantity": 2,
      "unit_price": "350.00",
      "notes": "Forehead and glabella",
      "effective_price": "350.00",
      "total_price": "700.00",
      "created_at": "2024-12-22T14:00:00Z",
      "updated_at": "2024-12-22T14:00:00Z"
    }
  ],
  "signed_at": null,
  "signed_by_user": null,
  "row_version": 1,
  "created_at": "2024-12-22T14:00:00Z",
  "updated_at": "2024-12-22T14:00:00Z"
}
```

#### Create Encounter
```http
POST /api/v1/clinical/encounters/
Authorization: Bearer <practitioner_token>
Content-Type: application/json

{
  "patient": "patient_uuid",
  "practitioner": "practitioner_uuid",
  "location": "location_uuid",
  "type": "aesthetic_procedure",
  "status": "draft",
  "occurred_at": "2024-12-22T14:00:00Z",
  "chief_complaint": "Wrinkles on forehead",
  "assessment": "Dynamic wrinkles suitable for botulinum toxin",
  "plan": "Botox 20 units forehead",
  "encounter_treatments": [
    {
      "treatment_id": "treatment_uuid_1",
      "quantity": 1,
      "notes": "Initial consultation"
    },
    {
      "treatment_id": "treatment_uuid_2",
      "quantity": 2,
      "unit_price": "350.00",
      "notes": "Forehead and glabella"
    }
  ]
}

Response: 201 Created
{
  "id": "uuid",
  ...
}
```

#### Add Treatment to Encounter
```http
POST /api/v1/clinical/encounters/{id}/add_treatment/
Authorization: Bearer <practitioner_token>
Content-Type: application/json

{
  "treatment_id": "treatment_uuid",
  "quantity": 1,
  "unit_price": "120.00",  # Optional override
  "notes": "Follow-up consultation"
}

Response: 201 Created
{
  "id": "uuid",
  "treatment_id": "uuid",
  "treatment": {...},
  "quantity": 1,
  "unit_price": "120.00",
  "notes": "Follow-up consultation",
  "effective_price": "120.00",
  "total_price": "120.00"
}
```

---

## RBAC Permissions

### Role Matrix

| Role          | Patients | Appointments | Treatments | Encounters | clinical_notes |
|---------------|----------|--------------|------------|------------|----------------|
| **Admin**     | CRUD     | CRUD         | CRUD       | CRUD       | ✅ Read/Write  |
| **ClinicalOps** | CRUD   | CRUD         | CRUD       | CRUD       | ✅ Read/Write  |
| **Practitioner** | CRUD  | CRUD         | Read       | CRUD       | ✅ Read/Write  |
| **Reception** | CRUD     | CRUD         | Read       | ❌ NO ACCESS | ❌ NO ACCESS  |
| **Accounting** | Read    | Read         | ❌ NO ACCESS | Read      | ❌ NO ACCESS   |
| **Marketing** | ❌ NO ACCESS | ❌ NO ACCESS | ❌ NO ACCESS | ❌ NO ACCESS | ❌ NO ACCESS |

### Key Rules

1. **Reception CANNOT access clinical data**:
   - Blocked from Encounter endpoints
   - Cannot read `clinical_notes`, `assessment`, `plan`, `internal_notes`
   - Can view Treatment catalog (for appointment booking)

2. **Clinical_notes require elevated privileges**:
   - Only ClinicalOps, Practitioner, Admin can read/write
   - Enforced at serializer level (field-level RBAC)

3. **Treatment catalog is read-only for Reception/Practitioner**:
   - Use case: Reception books appointments, needs to see available treatments
   - Only Admin/ClinicalOps can create/edit treatments

4. **Accounting can read encounters**:
   - Future billing integration use case
   - No write access to clinical data

---

## Business Rules

### Treatment Catalog

1. **Unique Names**: Treatment names must be unique (enforced by DB constraint)
2. **Soft Delete Only**: Use `is_active=false` instead of hard deletes (preserve history)
3. **Cannot Delete Referenced Treatments**: PROTECT constraint prevents deletion if used in encounters

### Encounter-Treatment Linking

1. **Quantity Validation**: Quantity must be >= 1 (enforced by serializer)
2. **No Duplicate Treatments**: Same treatment cannot be added twice to one encounter (DB unique constraint)
3. **Draft-Only Edits**: Treatments can only be added to `draft` encounters (enforced by API)
4. **Pricing Hierarchy**: `unit_price` overrides `Treatment.default_price` (computed via `effective_price` property)

### Encounter Status Transitions

```
Allowed transitions:
- draft → finalized
- draft → cancelled
- finalized → [TERMINAL] (immutable)
- cancelled → [TERMINAL] (immutable)

Forbidden transitions:
- finalized → draft  ❌ (audit requirement)
- cancelled → draft  ❌ (business rule)
```

**Enforcement**: Validated in `EncounterWriteSerializer.validate()` method.

---

## Example Workflow

### Complete Clinical Flow (E2E)

**Step 1: Reception creates patient**
```bash
curl -X POST /api/v1/clinical/patients/ \
  -H "Authorization: Bearer $RECEPTION_TOKEN" \
  -d '{"first_name": "Alice", "last_name": "Johnson", "email": "alice@example.com"}'
```

**Step 2: Reception books appointment**
```bash
curl -X POST /api/v1/clinical/appointments/ \
  -H "Authorization: Bearer $RECEPTION_TOKEN" \
  -d '{
    "patient": "patient_uuid",
    "practitioner": "practitioner_uuid",
    "status": "confirmed",
    "scheduled_start": "2024-12-22T14:00:00Z",
    "scheduled_end": "2024-12-22T15:00:00Z"
  }'
```

**Step 3: Reception checks in patient**
```bash
curl -X PATCH /api/v1/clinical/appointments/{appointment_id}/ \
  -H "Authorization: Bearer $RECEPTION_TOKEN" \
  -d '{"status": "checked_in"}'
```

**Step 4: Practitioner creates encounter**
```bash
curl -X POST /api/v1/clinical/encounters/ \
  -H "Authorization: Bearer $PRACTITIONER_TOKEN" \
  -d '{
    "patient": "patient_uuid",
    "practitioner": "practitioner_uuid",
    "type": "aesthetic_procedure",
    "status": "draft",
    "occurred_at": "2024-12-22T14:05:00Z",
    "chief_complaint": "Wrinkles on forehead",
    "encounter_treatments": [
      {"treatment_id": "botox_uuid", "quantity": 2}
    ]
  }'
```

**Step 5: Practitioner finalizes encounter**
```bash
curl -X PATCH /api/v1/clinical/encounters/{encounter_id}/ \
  -H "Authorization: Bearer $PRACTITIONER_TOKEN" \
  -d '{"status": "finalized"}'
```

**Step 6: Reception marks appointment completed**
```bash
curl -X PATCH /api/v1/clinical/appointments/{appointment_id}/ \
  -H "Authorization: Bearer $RECEPTION_TOKEN" \
  -d '{"status": "completed"}'
```

---

## Testing

### Run Tests
```bash
# Run all clinical core tests
pytest tests/test_clinical_core.py -v

# Run specific test class
pytest tests/test_clinical_core.py::TestTreatmentModel -v

# Run E2E flow only
pytest tests/test_clinical_core.py::TestClinicalE2E -v
```

### Test Coverage

**Model Tests** (10 tests):
- Treatment creation (minimal, full, unique constraint, soft disable)
- EncounterTreatment creation
- Effective price calculation
- Total price calculation
- Unique treatment per encounter constraint

**Permission Tests** (6 tests):
- TreatmentPermission: Admin/ClinicalOps CRUD, Reception/Practitioner read-only
- EncounterPermission: Reception blocked, Practitioner/ClinicalOps full access

**E2E Flow** (1 test):
- Complete clinical flow: patient → appointment → encounter → treatments → finalize
- Verifies RBAC, state transitions, price calculations

---

## 4. Billing Integration (Non-Fiscal)

**Fase 3 - COMPLETED ✅** (2025-01-XX)

### Overview

The **Clinical → Sales Integration** provides an explicit, auditable workflow for converting finalized clinical encounters into billable sales via an intermediate **ClinicalChargeProposal** model.

**Key Principles**:
- ✅ **Explicit, NOT automatic**: Both proposal generation and sale conversion require explicit API calls
- ✅ **Audit trail**: Proposal persists after conversion (status=CONVERTED)
- ✅ **Review workflow**: Proposal sits in DRAFT until Reception converts to sale
- ✅ **Pricing immutability**: Proposal captures pricing snapshot (won't change if catalog updated)
- ✅ **NO TAX**: Tax calculation deferred to future fiscal module (Fase 6)

### Two-Step Flow

```
┌─────────────┐  Practitioner      ┌──────────────────────────┐  Reception         ┌──────────┐
│  Encounter  │  finalizes +       │ ClinicalChargeProposal   │  reviews +         │   Sale   │
│  (clinical) │  clicks "Bill"     │    (clinical domain)     │  clicks "Create"   │ (sales)  │
│             ├───────────────────►│                          ├───────────────────►│          │
│  FINALIZED  │  POST /generate-   │  status=DRAFT            │  POST /create-     │ status=  │
│             │   proposal/        │  (reviewable)            │   sale/            │  DRAFT   │
└─────────────┘                    └──────────────────────────┘                    └──────────┘
     │                                      │                                            │
     │ Has treatments with pricing          │ Immutable pricing snapshot                 │ Ready for payment
     │ (EncounterTreatment.effective_price) │ (unit_price, quantity, line_total)         │ (can be edited before paid)
```

### Models

#### ClinicalChargeProposal (Header)

**Purpose**: Intermediate proposal between Encounter and Sale (lives in clinical domain).

**Fields**:
| Field              | Type               | Constraints         | Description                                   |
|--------------------|--------------------|---------------------|-----------------------------------------------|
| `id`               | UUID               | Primary Key         | Unique identifier                             |
| `encounter`        | OneToOneField      | CASCADE, NOT NULL   | **Idempotency**: One proposal per encounter   |
| `patient`          | FK(Patient)        | PROTECT, NOT NULL   | Copied from encounter.patient                 |
| `practitioner`     | FK(User)           | PROTECT, NOT NULL   | Copied from encounter.practitioner            |
| `status`           | CharField          | Choices, DRAFT      | DRAFT / CONVERTED / CANCELLED                 |
| `converted_to_sale`| FK(Sale)           | SET_NULL, Nullable  | **Idempotency check**: Linked sale after conversion |
| `converted_at`     | DateTimeField      | Nullable            | Timestamp of conversion to sale               |
| `total_amount`     | Decimal(10,2)      | >=0, NOT NULL       | Sum of line totals (calculated)               |
| `currency`         | CharField(3)       | Default='EUR'       | Currency code                                 |
| `notes`            | TextField          | Nullable            | Internal notes (e.g., "Insurance pre-approved") |
| `cancellation_reason` | TextField       | Nullable            | Reason if status=CANCELLED                    |
| `created_by`       | FK(User)           | PROTECT             | User who generated proposal                   |
| `created_at`       | DateTimeField      | Auto                | Creation timestamp                            |

**Indexes**:
- `idx_proposal_created` on `created_at`
- `idx_proposal_status_created` on `(status, created_at)`
- `idx_proposal_patient_created` on `(patient, created_at)`
- `idx_proposal_encounter` on `encounter`

**Methods**:
```python
def recalculate_total(self):
    """Recalculate total_amount from lines."""
    self.total_amount = sum(line.line_total for line in self.lines.all())
    self.save(update_fields=['total_amount'])
```

#### ClinicalChargeProposalLine (Detail)

**Purpose**: Pricing snapshot of each treatment performed (immutable once created).

**Fields**:
| Field                | Type               | Constraints         | Description                                   |
|----------------------|--------------------|---------------------|-----------------------------------------------|
| `id`                 | UUID               | Primary Key         | Unique identifier                             |
| `proposal`           | FK(Proposal)       | CASCADE, NOT NULL   | Parent proposal                               |
| `encounter_treatment`| FK(EncounterTreatment) | PROTECT, NOT NULL | Original encounter treatment reference    |
| `treatment`          | FK(Treatment)      | PROTECT, NOT NULL   | Treatment catalog reference                   |
| `treatment_name`     | CharField(255)     | NOT NULL            | **Snapshot**: Name at proposal time           |
| `description`        | TextField          | Nullable            | **Snapshot**: Description at proposal time    |
| `quantity`           | Decimal(10,3)      | >0, NOT NULL        | **Snapshot**: Quantity from encounter         |
| `unit_price`         | Decimal(10,2)      | >=0, NOT NULL       | **Snapshot**: Effective price at proposal time|
| `line_total`         | Decimal(10,2)      | >=0, NOT NULL       | **Auto-calculated**: quantity × unit_price    |
| `created_at`         | DateTimeField      | Auto                | Creation timestamp                            |

**Constraints**:
- `proposal_line_quantity_positive`: `quantity > 0`
- `proposal_line_unit_price_non_negative`: `unit_price >= 0`
- `proposal_line_total_non_negative`: `line_total >= 0`

**Auto-calculation**:
```python
def save(self, *args, **kwargs):
    if self.line_total is None or self.line_total == 0:
        self.line_total = self.quantity * self.unit_price
    super().save(*args, **kwargs)
```

### Service Functions

#### 1. Generate Proposal from Encounter

```python
def generate_charge_proposal_from_encounter(
    encounter: Encounter,
    created_by: User,
    notes: Optional[str] = None
) -> ClinicalChargeProposal:
    """
    Generate ClinicalChargeProposal from finalized Encounter.
    
    Validations:
    - encounter.status == 'finalized'
    - No existing proposal (OneToOne idempotency)
    - Encounter has treatments (at least 1)
    
    Creates:
    - ClinicalChargeProposal (status=DRAFT)
    - ClinicalChargeProposalLine per EncounterTreatment (with pricing snapshot)
    - Atomic transaction + structured logging
    
    Returns: ClinicalChargeProposal instance
    """
```

**Business Rules**:
- Only `FINALIZED` encounters can generate proposals
- Uses `EncounterTreatment.effective_price` (override or default)
- Skips treatments with no price (logs warning)
- Description combines `treatment.description` + `encounter_treatment.notes`
- **NO TAX**: `tax=0` (deferred to future)

**Example**:
```python
# Generate proposal after finalizing encounter
proposal = generate_charge_proposal_from_encounter(
    encounter=encounter,
    created_by=request.user,
    notes="Patient pre-paid 50%"
)
# proposal.status == 'draft'
# proposal.lines.count() == 3  (3 treatments performed)
# proposal.total_amount == Decimal('650.00')
```

#### 2. Convert Proposal to Sale

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
    - proposal.status == 'draft'
    - proposal.converted_to_sale is None (idempotency)
    - Proposal has lines
    
    Creates:
    - Sale (status='draft', tax=0, discount=0)
    - SaleLine per proposal line (product=null for services)
    - Updates proposal: status='converted', converted_to_sale, converted_at
    - Atomic transaction + structured logging
    
    Returns: Sale instance (status='draft')
    """
```

**Business Rules**:
- Only `DRAFT` proposals can be converted
- Sale created in `DRAFT` status (can be modified before payment)
- `product=null` for all lines (service charges, no stock impact)
- **NO TAX**: `tax=0`, `total=subtotal` (deferred to future fiscal module)
- Proposal → `CONVERTED` status (terminal, cannot be reconverted)

**Example**:
```python
# Convert proposal to sale
sale = create_sale_from_proposal(
    proposal=proposal,
    created_by=request.user,
    legal_entity=clinic_entity,
    notes="Patient paying in full today"
)
# sale.status == 'draft'
# sale.total == Decimal('650.00')
# sale.tax == Decimal('0.00')  # NO TAX (future)
# sale.lines.count() == 3  (matches proposal lines)

# Proposal is now converted
proposal.refresh_from_db()
# proposal.status == 'converted'
# proposal.converted_to_sale == sale
# proposal.converted_at == timezone.now()
```

### API Endpoints

| Endpoint                                             | Method | Role                       | Description                          |
|------------------------------------------------------|--------|----------------------------|--------------------------------------|
| `/api/v1/clinical/encounters/{id}/generate-proposal/`| POST   | ClinicalOps, Practitioner  | Generate proposal from finalized encounter |
| `/api/v1/clinical/proposals/`                        | GET    | All (except Marketing)     | List proposals with filters          |
| `/api/v1/clinical/proposals/{id}/`                   | GET    | All (except Marketing)     | View proposal detail with lines      |
| `/api/v1/clinical/proposals/{id}/create-sale/`       | POST   | Reception, ClinicalOps, Admin | Convert proposal to sale (draft)   |

#### Generate Proposal (POST /encounters/{id}/generate-proposal/)

**Request**:
```json
POST /api/v1/clinical/encounters/abc-123/generate-proposal/
Authorization: Bearer {practitioner_token}

{
  "notes": "Patient pre-paid 50% via bank transfer"
}
```

**Response**:
```json
{
  "proposal_id": "def-456",
  "message": "Charge proposal generated successfully",
  "total_amount": "650.00",
  "line_count": 3,
  "status": "draft"
}
```

#### List Proposals (GET /proposals/)

**Request**:
```bash
GET /api/v1/clinical/proposals/?status=draft&patient=abc-123
Authorization: Bearer {reception_token}
```

**Response**:
```json
{
  "count": 5,
  "results": [
    {
      "id": "def-456",
      "encounter_id": "abc-123",
      "patient_name": "John Doe",
      "practitioner_name": "Dr. Jane Smith",
      "status": "draft",
      "total_amount": "650.00",
      "line_count": 3,
      "created_at": "2025-01-15T14:30:00Z"
    }
  ]
}
```

#### View Proposal Detail (GET /proposals/{id}/)

**Response**:
```json
{
  "id": "def-456",
  "encounter": {
    "id": "abc-123",
    "type": "aesthetic_procedure",
    "occurred_at": "2025-01-15T10:00:00Z"
  },
  "patient": {
    "id": "patient-123",
    "full_name": "John Doe"
  },
  "practitioner": {
    "id": "practitioner-456",
    "display_name": "Dr. Jane Smith"
  },
  "status": "draft",
  "total_amount": "650.00",
  "currency": "EUR",
  "lines": [
    {
      "id": "line-1",
      "treatment_name": "Botox Injection",
      "quantity": 2,
      "unit_price": "300.00",
      "line_total": "600.00"
    },
    {
      "id": "line-2",
      "treatment_name": "Consultation",
      "quantity": 1,
      "unit_price": "50.00",
      "line_total": "50.00"
    }
  ],
  "notes": "Patient pre-paid 50% via bank transfer",
  "created_at": "2025-01-15T14:30:00Z"
}
```

#### Convert to Sale (POST /proposals/{id}/create-sale/)

**Request**:
```json
POST /api/v1/clinical/proposals/def-456/create-sale/
Authorization: Bearer {reception_token}

{
  "legal_entity_id": "entity-789",
  "notes": "Paid in full via credit card"
}
```

**Response**:
```json
{
  "sale_id": "sale-999",
  "message": "Sale created successfully from proposal",
  "sale_status": "draft",
  "sale_total": "650.00"
}
```

### RBAC Permissions

| Role           | Generate Proposal | View Proposals | Convert to Sale |
|----------------|-------------------|----------------|-----------------|
| **Admin**      | ✅                | ✅             | ✅              |
| **ClinicalOps**| ✅                | ✅             | ✅              |
| **Practitioner**| ✅ (via Encounter)| ✅ (own only)  | ❌              |
| **Reception**  | ❌                | ✅             | ✅              |
| **Accounting** | ❌                | ✅ (read-only) | ❌              |
| **Marketing**  | ❌                | ❌             | ❌              |

**Practitioner Restriction**: Practitioner can only see proposals for their own encounters (`proposal.practitioner == request.user`).

### Idempotency Guarantees

| Operation            | Mechanism                          | Validation                                  |
|----------------------|------------------------------------|--------------------------------------------|
| **Generate Proposal**| `encounter.OneToOneField(Encounter)`| Raises `ValueError` if proposal exists      |
| **Convert to Sale**  | `proposal.converted_to_sale` check | Raises `ValueError` if already converted    |

Both operations are **atomic** (wrapped in `transaction.atomic()`).

### Example Workflow

**Step 1: Practitioner finalizes encounter with treatments**
```bash
# Add treatments to draft encounter
POST /api/v1/clinical/encounters/{encounter_id}/add_treatment/
{
  "treatment_id": "botox-uuid",
  "quantity": 2,
  "unit_price": 300.00,
  "notes": "Applied to forehead and glabella"
}

# Finalize encounter
PATCH /api/v1/clinical/encounters/{encounter_id}/
{
  "status": "finalized"
}
```

**Step 2: Practitioner generates billing proposal**
```bash
POST /api/v1/clinical/encounters/{encounter_id}/generate-proposal/
{
  "notes": "Patient requested itemized billing"
}

# Response:
# {
#   "proposal_id": "proposal-uuid",
#   "total_amount": "600.00",
#   "line_count": 1,
#   "status": "draft"
# }
```

**Step 3: Reception reviews proposal**
```bash
GET /api/v1/clinical/proposals/{proposal_id}/

# Response shows:
# - Total amount: 600.00 EUR
# - Line: Botox Injection × 2 @ 300.00 = 600.00
# - Status: draft (ready to convert)
```

**Step 4: Reception converts proposal to sale**
```bash
POST /api/v1/clinical/proposals/{proposal_id}/create-sale/
{
  "legal_entity_id": "clinic-entity-uuid",
  "notes": "Patient paying by credit card"
}

# Response:
# {
#   "sale_id": "sale-uuid",
#   "sale_status": "draft",
#   "sale_total": "600.00"
# }
```

**Step 5: Reception collects payment**
```bash
# (In future: POST /api/v1/sales/{sale_id}/record-payment/)
# For now: Sale remains in draft until POS/payment integration
```

### Testing

**Run Tests**:
```bash
# Run all clinical sales integration tests
pytest tests/test_clinical_sales_integration.py -v

# Run specific test class
pytest tests/test_clinical_sales_integration.py::TestGenerateChargeProposalService -v

# Run E2E flow
pytest tests/test_clinical_sales_integration.py::TestClinicalToSaleE2E -v
```

**Test Coverage** (22 tests):
- 6 model tests: Proposal creation, OneToOne constraint, recalculate_total, line auto-calculation, status choices, idempotency
- 8 service tests: Happy path, validations, idempotency, effective_price, description combining, skip free treatments
- 6 permission tests: Reception can convert, Accounting read-only, Marketing no access, Practitioner own proposals only
- 1 E2E test: Complete flow (Encounter → Proposal → Sale) with idempotency validation
- 1 regression test: Existing Sales API not broken (no FK errors, old sales work)

### Future Evolution

#### Fase 5: Quote System (Pre-Treatment Quotes)

`ClinicalChargeProposal` can evolve into a **Quote System** for pre-treatment pricing:

**Changes needed**:
- Rename `ClinicalChargeProposal` → `ClinicalQuote`
- Add `QuoteStatusChoices`: DRAFT → APPROVED → INVOICED → CONVERTED_TO_SALE
- Add `expiry_date` (quote valid for 30 days)
- Add `approval_date`, `approved_by`
- Add `invoice_number` (if pre-treatment invoice issued)

**Benefits**:
- Smooth evolution (no breaking changes, just rename + add fields)
- Proposal workflow already tested and stable
- Audit trail already exists

#### Fase 6: Fiscal Module (Tax, VAT, Legal Invoicing)

When fiscal module implemented, `create_sale_from_proposal()` will:
- Calculate **tax** based on `legal_entity.country_code` + `treatment.tax_category`
- Generate **invoice number** (legal requirement)
- Create **fiscal entry** in accounting system
- Support **multiple tax rates** (VAT 10%, VAT 20%, exempt)

**NO changes needed to `ClinicalChargeProposal` model** (already captures pre-tax amounts correctly).

### References

- **ADR-005**: Clinical → Sales Integration (architectural decision)
- **STABILITY.md**: Clinical → Sales Integration stability markers
- **API_CONTRACTS.md**: API endpoint contracts

---

---

## Clinical Media

### Overview

Clinical photos documenting treatments before, during, and after procedures.

**Model**: `ClinicalMedia` (apps.encounters.models_media)

**Association**: Linked to `Encounter` (NOT Patient directly) for temporal context.

**Storage**: Local filesystem (Phase 1) - No public URLs, authentication required.

### Features

✅ **Photo Upload**: Upload clinical photos to specific encounters  
✅ **Soft Delete**: Audit trail preserved (files not removed from disk)  
✅ **RBAC**: Practitioner access to own encounters only  
✅ **Validations**: File type (jpg/png/webp), size limit (10MB), status checks  
✅ **Authenticated Download**: No public URLs, token/session auth required

### Model: ClinicalMedia

**Fields**:
```python
encounter: ForeignKey(Encounter)        # Associated consultation
uploaded_by: ForeignKey(User)           # Uploader (audit trail)
media_type: CharField                   # 'photo' (extensible)
category: CharField                     # before/after/progress/other
file: ImageField                        # Photo file
notes: TextField                        # Optional clinical notes
created_at: DateTimeField               # Upload timestamp
deleted_at: DateTimeField (nullable)    # Soft delete timestamp
```

**Upload Path**: `clinical_media/encounter_{uuid}/media_{uuid}.{ext}`

**Custom QuerySet**:
```python
ClinicalMedia.objects.active()     # Exclude soft-deleted
ClinicalMedia.objects.deleted()    # Only soft-deleted
```

**Methods**:
```python
media.soft_delete()        # Marks as deleted (preserves file)
media.is_deleted           # Boolean property
media.file_size_mb         # File size in MB
```

### API Endpoints

#### Upload Photo
```bash
POST /api/v1/clinical/encounters/{encounter_id}/media/
Content-Type: multipart/form-data

# Form fields:
file: [binary data]
category: "before" | "after" | "progress" | "other"
notes: "Optional clinical notes"

# Response (201):
{
  "id": 123,
  "encounter": 456,
  "media_type": "photo",
  "category": "before",
  "file_url": "/api/v1/clinical/media/123/download/",  # Authenticated endpoint
  "file_size_mb": 2.3,
  "uploaded_by_name": "Dr. Smith",
  "notes": "Pre-treatment baseline",
  "created_at": "2025-12-22T10:30:00Z"
}
```

#### List Photos for Encounter
```bash
GET /api/v1/clinical/encounters/{encounter_id}/media/

# Response (200):
[
  {
    "id": 123,
    "category": "before",
    "notes": "Pre-treatment",
    "uploaded_by_name": "Dr. Smith",
    "file_size_mb": 2.3,
    "created_at": "2025-12-22T10:30:00Z"
  }
]
```

#### Download Photo (Authenticated)
```bash
GET /api/v1/clinical/media/{id}/download/
Authorization: Token <token> | Session Cookie

# Response (200):
# Binary file data (image/jpeg, image/png, image/webp)
# Content-Disposition: inline
```

#### Delete Photo (Soft Delete)
```bash
DELETE /api/v1/clinical/media/{id}/

# Response (204 No Content)
# Note: File preserved on disk, deleted_at timestamp set
```

### RBAC Rules

**Permission Class**: `IsAuthenticated` + `IsClinicalStaff`

| Role | Upload | List | Download | Delete |
|------|--------|------|----------|--------|
| **Practitioner** | ✅ Own encounters | ✅ Own encounters | ✅ Own media | ✅ Own media |
| **ClinicalOps** | ✅ All encounters | ✅ All media | ✅ All media | ✅ All media |
| **Admin** | ✅ All encounters | ✅ All media | ✅ All media | ✅ All media |
| **Reception** | ❌ Blocked | ❌ Blocked | ❌ Blocked | ❌ Blocked |

**QuerySet Filtering**:
```python
# Practitioner: Only own encounters
queryset.filter(encounter__practitioner=request.user)

# Admin/ClinicalOps: Full access
queryset.all()

# Reception: No access (IsClinicalStaff blocks)
```

### Validations

#### File Type
- **Allowed**: `jpg`, `jpeg`, `png`, `webp`
- **Validation**: Django `FileExtensionValidator` + serializer check
- **Error**: `400 Bad Request` if invalid type

#### File Size
- **Limit**: 10MB per file
- **Validation**: Serializer `validate_file()` method
- **Error**: `400 Bad Request` "File size must be less than 10MB"

#### Encounter Status
- **Rule**: Cannot upload to `cancelled` encounters
- **Validation**: Serializer `validate_encounter()` method
- **Error**: `400 Bad Request` "Cannot upload media to cancelled encounters"

### Observability

**Structured Logging** (No PHI/PII):
```python
# ✅ Safe logging
logger.info(
    "media_uploaded",
    media_id=media.id,          # UUID
    encounter_id=encounter.id,  # UUID
    user_id=request.user.id,    # UUID
    category=media.category,     # Enum value
    file_size_mb=media.file_size_mb  # Number
)

# ❌ NEVER log:
# - patient_name
# - email
# - file content
# - clinical notes
```

**Events Logged**:
- `media_uploaded`: File upload success (media_id, encounter_id, user_id, category, file_size_mb)
- `media_listed`: Encounter media listing (encounter_id, user_id, count)
- `media_deleted`: Soft delete operation (media_id, encounter_id, user_id)
- `media_downloaded`: File download (media_id, user_id)

### Testing

**Test Suite**: `tests/test_clinical_media.py` (16 tests)

**Coverage**:
```bash
# Upload tests
- Practitioner can upload to own encounter
- Practitioner cannot upload to other's encounter
- Reception cannot upload
- Admin can upload to any encounter
- Cannot upload to cancelled encounter
- File size validation (>10MB rejected)
- File type validation (PDF rejected)

# List tests
- Practitioner lists own encounter media
- Practitioner cannot list other's media
- Soft-deleted media excluded

# Delete tests
- Practitioner can soft-delete own media
- Practitioner cannot delete other's media
- Soft delete preserves file

# Download tests
- Authenticated download succeeds
- Unauthenticated download blocked
```

**Run Tests**:
```bash
pytest tests/test_clinical_media.py -v

# Run specific test class
pytest tests/test_clinical_media.py::ClinicalMediaUploadTests -v
pytest tests/test_clinical_media.py::ClinicalMediaRBACTests -v
```

### Design Decisions

**Why Encounter Association (Not Patient)?**
- Provides temporal context (when photo taken = encounter date)
- Enables RBAC via practitioner-encounter relationship
- Aligns with clinical workflow (photos document specific consultation)

**Why Soft Delete?**
- Medical records require audit trail
- Files preserved for compliance
- Recovery possible if accidental deletion

**Why No Public URLs?**
- Security: Authentication required for all file access
- Compliance: No risk of leaked photo URLs
- Control: Can revoke access by changing token/session

**Why Local Storage (Phase 1)?**
- Simplicity: Single-clinic deployment doesn't need S3
- Cost: Avoids cloud storage fees for MVP
- Migration: Easy to switch to S3 later (change storage backend only)

### Migration to Cloud Storage (Future)

**Phase 2**: When multi-region or CDN needed

**Steps**:
1. Install `django-storages` and `boto3`
2. Configure S3 bucket
3. Update `DEFAULT_FILE_STORAGE` setting
4. No model changes required
5. Migrate existing files to S3

**No code changes needed** - Django storage abstraction handles everything.

### References

- **ADR-006**: Clinical Media architectural decision
- **PROJECT_DECISIONS.md Section 9.6**: Clinical Media documentation
- Django ImageField: https://docs.djangoproject.com/en/4.2/ref/models/fields/#imagefield
- DRF File Upload: https://www.django-rest-framework.org/api-guide/parsers/

---

## Future Enhancements

### 1. Stock Integration
When `Treatment.requires_stock=true`:
- Link Treatment to StockProduct
- Check stock availability before adding to encounter
- Deduct stock on encounter finalization

### 2. Fiscal Integration
When billing/invoicing is implemented:
- Link Encounter to Sale/Invoice
- Use `EncounterTreatment.total_price` for invoice line items
- Respect legal entity requirements (ADR-002)

### 3. Clinical Signatures
When required by regulations:
- Use `Encounter.signed_at` and `Encounter.signed_by_user` fields
- Add signature workflow (draft → signed → locked)
- Implement e-signature validation

### 4. Frontend
When UI is prioritized:
- Treatment catalog management (Admin/ClinicalOps)
- Encounter creation/editing (Practitioner)
- Appointment-encounter linking (Reception/Practitioner)

---

## References

- **ADR-003**: Clinical Core v1 architectural decision
- **DOMAIN_MODEL.md**: Patient, Encounter, Appointment specifications
- **API_CONTRACTS.md**: API endpoint contracts
- **STABILITY.md**: Stability guarantees

---

**Version History**:
- **v1.0** (2024-12-22): Initial implementation
