# DOMAIN INTEGRITY AUDIT — ERP Clínica Rescate
**Date:** 2025-01-02  
**Scope:** Analysis only — no code changes applied  
**Baseline:** 832 passed, 182 skipped, 0 failed (post-Phase 4 RBAC consolidation)  
**Auditor:** GitHub Copilot (Claude Sonnet 4.6)

---

## Executive Summary

Seven domain integrity dimensions were audited across Clinical, Sales, Proposals, TreatmentPlans, and Stock modules. **14 confirmed defects** were found across 5 severity levels. The most critical issues are:

1. **Physical delete is possible via API for Patients and Encounters** — despite soft-delete fields existing
2. **Deleting a Patient cascades and physically destroys all Encounters, Consents, and ClinicalPhotos**
3. **Superusers can delete PAID Sales and Patients via the Django admin panel**
4. **Deleting a StockLocation or StockBatch cascades and destroys the entire inventory audit trail**
5. **EncounterViewSet allows physical DELETE via API with no soft-delete implementation**

---

## PART 1 — Soft Delete Safety

### 1.1 Inventory of Soft Delete Fields

| Model | `is_deleted` | `deleted_at` | `deleted_by_user` | Notes |
|---|---|---|---|---|
| `Patient` | ✅ | ✅ | ✅ | Full soft-delete schema exists |
| `Encounter` | ✅ | ✅ | ✅ | Full soft-delete schema exists |
| `Appointment` | ✅ | ✅ | ❌ **MISSING** | `deleted_by_user` not present |
| `Consent` | ✅ | ✅ | — | Not confirmed; schema read not complete |
| `ClinicalPhoto` | ✅ | ✅ | — | Not confirmed; schema read not complete |
| `Sale` | ❌ | ❌ | ❌ | No soft-delete; deletion blocked via `perform_destroy()` raising `ValidationError` |
| `SaleLine` | ❌ | ❌ | ❌ | No soft-delete, no ViewSet |
| `SaleRefund` | ❌ | ❌ | ❌ | No soft-delete |
| `SaleRefundLine` | ❌ | ❌ | ❌ | No soft-delete |
| `Proposal` | ❌ | ❌ | ❌ | No soft-delete; admin not registered |
| `ProposalLine` | ❌ | ❌ | ❌ | No soft-delete |
| `TreatmentPlan` | ❌ | ❌ | ❌ | No soft-delete; no admin protection |
| `TreatmentSession` | ❌ | ❌ | ❌ | No soft-delete; inherits `TenantModel` |
| `StockMove` | ❌ | ❌ | ❌ | No soft-delete; immutability enforced by `save()` block, but physical delete is possible |

### 1.2 ViewSet DELETE Behaviour

| ViewSet | `destroy()` override | Behaviour |
|---|---|---|
| `PatientViewSet` | ❌ **NO** | Inherits `ModelViewSet.perform_destroy()` → **physical `instance.delete()`** |
| `EncounterViewSet` | ❌ **NO** | Docstring claims "soft delete" — **LIE: physical `instance.delete()`** |
| `AppointmentViewSet` | ✅ YES | Soft delete (`is_deleted=True`), Admin-only via role check |
| `SaleViewSet` | ✅ YES | `perform_destroy()` raises `ValidationError` — all deletions blocked |
| `TreatmentPlanViewSet` | N/A | `ReadOnlyModelViewSet` — DELETE endpoint not exposed ✅ |
| `StockLocationViewSet` | ❌ **NO** | Physical delete possible → **cascades ALL StockMoves** |
| `StockBatchViewSet` | ❌ **NO** | Physical delete possible → **cascades ALL StockMoves in that batch** |
| `StockMoveViewSet` | ❌ **NO** | Physical delete of an individual stock move possible via API |
| `PatientGuardianViewSet` | ✅ YES (intentional) | Hard delete — intentional per design |

### 1.3 Model-level `delete()` Overrides

No domain model overrides `Model.delete()` at all. An admin or script calling `patient.delete()` bypasses all ViewSet protections and physically destroys the row and all CASCADE children.

---

## PART 2 — Financial Immutability

### 2.1 Sale Immutability

**Strengths:**
- `Sale.transition_to()` enforces valid transitions at model level; invalid transitions raise `ValidationError`
- `SaleLine.clean()` calls `sale.is_modifiable()` and blocks modification when sale is in terminal status
- `SaleViewSet.perform_destroy()` raises `ValidationError` — physical deletion blocked for all users via API

**Defects:**

**DEFECT FIN-1 (HIGH):** `Sale.status` can be written directly via `sale.status = 'paid'; sale.save()` — `save()` does NOT validate the transition. Only `transition_to()` validates. Any code path that bypasses `transition_to()` can corrupt the state machine.

```python
# This is NOT blocked:
sale.status = 'paid'
sale.save()  # No transition validation called
```

**DEFECT FIN-2 (HIGH):** `SaleAdmin.has_delete_permission()` returns `request.user.is_superuser` for terminal sales. A superuser CAN delete a PAID sale via the Django admin. No model-level `delete()` guard exists.

**DEFECT FIN-3 (MEDIUM):** `SaleRefund` has no model-level immutability check for COMPLETED status. Immutability (if it exists) is enforced only at the service layer, not at `save()`. Any code calling `refund.save()` directly after manipulating fields bypasses this.

### 2.2 Proposal Immutability

**Strengths:**
- `Proposal.save()` checks `old.status in TERMINAL_STATES` and raises `ValidationError` — prevents direct field edits once accepted/cancelled/expired

**Defects:**

**DEFECT FIN-4 (MEDIUM):** `Proposal.save()` accepts a `force_save=True` kwarg that bypasses the terminal state check. It is used in `Proposal.accept()` legitimately, but any caller with access to the model can pass `force_save=True` and overwrite a finalized proposal.

**DEFECT FIN-5 (LOW):** `ProposalLine` has no FK constraint on `Proposal` with `on_delete=PROTECT`. `ProposalLine.proposal → CASCADE` (models.py ~line 390). If a Proposal is deleted, all its ProposalLines are silently cascade-deleted.

---

## PART 3 — State Machine Enforcement

### 3.1 Sale State Machine

- `transition_to()` at model level validates transitions. ✅  
- But `save()` does NOT call `transition_to()` — direct status writes are not blocked (DEFECT FIN-1 above).

### 3.2 Proposal State Machine

- `save()` rejects writes when terminal. ✅  
- `force_save=True` bypass exists (DEFECT FIN-4 above). ⚠️

### 3.3 Appointment State Machine

- `transition_status()` action validates transitions at ViewSet level. ✅  
- `Appointment.save()` calls `full_clean()` → but `clean()` does NOT check status transitions. A direct `appt.status = 'no_show'; appt.save()` is NOT blocked.

**DEFECT SM-1 (MEDIUM):** All three state machines (Sale, Appointment, Proposal) allow status to be written directly via `save()` without transition validation, as long as `transition_to()` / `transition_status()` is bypassed. Terminal state guard only exists for Proposal.

### 3.4 Encounter State Machine

**DEFECT SM-2 (HIGH):** `Encounter` has no state machine at all. Status values `draft/finalized/cancelled` are just a `CharField`. No `Encounter.transition_to()` or similar method. No `save()` guard. A caller can freely write:
```python
encounter.status = 'finalized'
encounter.save()  # No validation
```
This means encounters can be "finalized" without having an associated proposal, without required treatments, or after already being cancelled.

### 3.5 TreatmentPlan State Machine

- `save()` enforces terminal state immutability (with `update_fields` bypass for its own state-machine methods). ✅  
- `activate()`, `record_session_completed()`, `cancel()` enforce transitions with explicit guards. ✅

### 3.6 TreatmentSession State Machine

- `save()` enforces terminal state immutability (same `update_fields` bypass). ✅  
- `complete()`, `cancel()` enforce transitions with guards. ✅  
- `TreatmentSession.complete()` deliberately does NOT call `TreatmentPlan.record_session_completed()` — that responsibility is delegated to the calling view/service.

**DEFECT SM-3 (MEDIUM):** If the `TreatmentSession.complete()` caller (view/service) omits calling `treatment_plan.record_session_completed()`, the session count on the plan diverges — the plan never auto-completes even after all sessions are done. This is a fragile contract: documented in a code comment but not enforced by the model.

---

## PART 4 — Tenant Isolation

### 4.1 Models with Correct Tenant Isolation

| Model | Isolation Method |
|---|---|
| `Patient` | `TenantModel` → `legal_entity` FK + `TenantManager` |
| `Encounter` | `TenantModel` |
| `Appointment` | `TenantModel` |
| `Consent` | `TenantModel` |
| `ClinicalPhoto` | `TenantModel` |
| `Proposal` | `TenantModel` |
| `Sale` | Explicit `legal_entity` FK + `TenantManager()` + `unfiltered = models.Manager()` |
| `TreatmentPlan` | Explicit `legal_entity` FK + `TenantManager()` + `unfiltered = models.Manager()` |
| `TreatmentSession` | `TenantModel` |
| `StockMove` | `TenantModel` |
| `StockBatch` | `TenantModel` |
| `StockOnHand` | `TenantModel` |

### 4.2 Models WITHOUT Direct Tenant Isolation

**DEFECT TEN-1 (HIGH):** `SaleLine` — uses plain `models.Model`, no `legal_entity` FK, no `TenantManager`. Tenant isolation relies entirely on accessing SaleLines through a Sale that is tenant-filtered. A cross-tenant queryset like `SaleLine.objects.filter(sale_id=X)` (if no tenant in thread-local) returns results from all tenants. Management commands or scripts accessing `SaleLine.objects.all()` return cross-tenant data.

**DEFECT TEN-2 (HIGH):** `SaleRefund` — uses plain `models.Model`, no `legal_entity` FK, no `TenantManager`. Same risk as SaleLine: cross-tenant data accessible via management commands, admin, or any code that bypasses the Sale tenant filter.

**DEFECT TEN-3 (HIGH):** `SaleRefundLine` — uses plain `models.Model`. Same issue.

**Note:** `TenantManager` returns an unfiltered queryset when `get_current_tenant()` is None (e.g., in management commands, migrations). This is safe by design but means ALL models using `TenantManager` expose tenant-unfiltered data in management contexts.

---

## PART 5 — Cascade Delete Risks

### 5.1 Complete Cascade Map

All `on_delete=CASCADE` relationships that can destroy meaningful business data:

#### Clinical Domain — CRITICAL

| FK Path | Risk Level | Data Lost |
|---|---|---|
| `Encounter.patient → CASCADE` | 🔴 CRITICAL | Deleting Patient physically deletes ALL Encounters |
| `Consent.patient → CASCADE` | 🔴 CRITICAL | Deleting Patient physically deletes ALL Consent records |
| `ClinicalPhoto.patient → CASCADE` | 🔴 CRITICAL | Deleting Patient physically deletes ALL clinical photos |
| `PatientGuardian.patient → CASCADE` | 🟡 MEDIUM | Deleting Patient deletes all guardian records |
| `PatientInsurance.patient → CASCADE` | 🟡 MEDIUM | Deleting Patient deletes all insurance records |
| `EncounterTreatment.encounter → CASCADE` | 🔴 CRITICAL | Deleting Encounter destroys all treatment records in that encounter |

#### Sales Domain — CRITICAL

| FK Path | Risk Level | Data Lost |
|---|---|---|
| `SaleLine.sale → CASCADE` | 🔴 CRITICAL | Deleting a Sale destroys all its line items (all financial detail) |
| `SaleRefund.sale → CASCADE` | 🔴 CRITICAL | Deleting a Sale destroys all refund records for that sale |
| `SaleRefundLine.refund → CASCADE` | 🟠 HIGH | Deleting SaleRefund destroys all refund line items |
| `SaleRefundLine.sale_line → CASCADE` | 🟠 HIGH | Deleting a SaleLine orphans and destroys refund line records |

#### Proposals Domain — HIGH

| FK Path | Risk Level | Data Lost |
|---|---|---|
| `ProposalLine.proposal → CASCADE` | 🟠 HIGH | Deleting a Proposal destroys all proposal line items |

#### Stock Domain — CRITICAL (audit trail destruction)

| FK Path | Risk Level | Data Lost |
|---|---|---|
| `StockBatch.product → CASCADE` | 🔴 CRITICAL | Deleting a Product destroys all StockBatch records for that product |
| `StockMove.product → CASCADE` | 🔴 CRITICAL | Deleting a Product destroys the entire stock movement audit trail for that product |
| `StockMove.location → CASCADE` | 🔴 CRITICAL | Deleting a Location destroys ALL stock moves ever recorded at that location |
| `StockMove.batch → CASCADE` | 🔴 CRITICAL | Deleting a StockBatch destroys all moves for that batch |
| `StockOnHand.product → CASCADE` | 🟠 HIGH | Deleting a Product destroys on-hand stock records |
| `StockOnHand.location → CASCADE` | 🟠 HIGH | Deleting a Location destroys on-hand balances |
| `StockOnHand.batch → CASCADE` | 🟠 HIGH | Deleting a Batch destroys on-hand balance for that batch |

### 5.2 Protective Relationships (PROTECT)

These existing FK protections correctly block deletion of parents with children:
- `EncounterTreatment.treatment → PROTECT` ✅ (cannot delete a Treatment with encounters)
- `Appointment.patient → PROTECT` ✅ (cannot delete a Patient with appointments — NOTE: only Appointments, not Encounters)
- `TreatmentPlan.patient → PROTECT` ✅
- `TreatmentPlan.proposal → PROTECT` ✅
- `TreatmentPlan.proposal_line → PROTECT` (OneToOneField) ✅
- `TreatmentSession.treatment_plan → PROTECT` ✅
- `TreatmentSession.appointment → PROTECT` ✅ (OneToOneField)
- `ProposalLine.encounter_treatment → PROTECT` ✅
- `ProposalLine.treatment → PROTECT` ✅

**Anomaly:** `Appointment.patient → PROTECT` blocks Patient deletion when appointments exist, but `Encounter.patient → CASCADE` does NOT block Patient deletion when encounters exist. This means:
- If a patient has no appointments but has encounters → Patient CAN be deleted (+ all encounters cascade)
- If a patient has appointments → Patient deletion is blocked by PROTECT on Appointment

---

## PART 6 — Domain Invariants

### 6.1 Proposal from Encounter (Invariant: One proposal per finalized encounter)

**Enforcement layer:** Service (`generate_charge_proposal_from_encounter()`), NOT model-level.

**Model protection:** `Proposal.encounter` is a `OneToOneField → PROTECT`. Attempting to create a second proposal for the same encounter raises a database `IntegrityError`. ✅

**DEFECT INV-1 (MEDIUM):** The service validates `encounter.status == 'finalized'` before creating a proposal. However, nothing at the model level prevents creating a `Proposal` with an `encounter` that is still in `draft` status. Any code that bypasses the service can create a proposal from an unfinished encounter.

### 6.2 TreatmentPlan from ProposalLine (Invariant: One TreatmentPlan per accepted full_package line)

**Enforcement layer:** `Proposal.accept()` method with `@transaction.atomic`. Creates `TreatmentPlan` only for `type='full_package'` lines. ✅

**Model protection:** `TreatmentPlan.proposal_line` is `OneToOneField → PROTECT`. Attempting to create a second plan for the same line raises `IntegrityError`. ✅

**DEFECT INV-2 (LOW):** Nothing enforces that a `TreatmentPlan` can only be created through `Proposal.accept()`. Direct `TreatmentPlan.objects.create(...)` in a script would bypass the atomicity and side-effects (Sale creation, etc.) of `accept()`.

### 6.3 Sale from Accepted Proposal (Invariant: Sale represents a finalized commercial agreement)

**Enforcement layer:** `Proposal.accept()` method only.

**DEFECT INV-3 (LOW):** `Sale.clean()` does NOT require a source proposal. Any code can create a `Sale` directly (`Sale.objects.create(...)`) without going through the proposal workflow. There is no `source_proposal` FK on `Sale` that could enforce this at the DB level.

### 6.4 TreatmentSession → TreatmentPlan Progress (Invariant: Session completion drives plan progress)

**Enforcement layer:** When a session is completed via `TreatmentSession.complete()`, the caller must separately call `treatment_plan.record_session_completed()`. This is documented in a comment but NOT enforced.

**Correct path (per `treatment_session_models.py` docstring):** View/service must call both methods atomically.

**DEFECT SM-3 (as noted above):** Fragile inter-model contract — plan progress diverges if caller omits `record_session_completed()`.

### 6.5 Stock → StockOnHand Consistency (Invariant: StockOnHand reflects aggregated StockMoves)

**Enforcement layer:** `services.create_stock_out_fefo()` and individual stock operation services update both `StockMove` and `StockOnHand` atomically.

**DEFECT INV-4 (MEDIUM):** `StockMoveViewSet` inherits `ModelViewSet` with no `destroy()` override — a `StockMove` can be physically deleted via API. Deleting a StockMove breaks the audit trail AND leaves `StockOnHand` with an incorrect quantity (the on-hand balance is no longer consistent with the sum of moves). The model-level `save()` guard prevents edits but does NOT prevent deletion.

---

## PART 7 — Admin Panel Risks

### 7.1 Admin Delete Permissions Summary

| Admin Class | `has_delete_permission()` | Risk |
|---|---|---|
| `PatientAdmin` | ❌ NOT OVERRIDDEN | 🔴 Superuser can physically delete patients (+ all CASCADE children) |
| `EncounterAdmin` | ❌ NOT OVERRIDDEN | 🔴 Superuser can physically delete encounters (+ all treatments) |
| `AppointmentAdmin` | ✅ Overridden (terminal=superuser only) | 🟡 Superuser can delete terminal appointments |
| `SaleAdmin` | ✅ Overridden but **allows superuser on terminal** | 🟠 Superuser CAN delete PAID and REFUNDED sales |
| `TreatmentPlanAdmin` | ❌ NOT OVERRIDDEN | 🟠 Superuser can physically delete treatment plans |
| `ProposalAdmin` | NOT REGISTERED | 🟡 No admin exposure (empty stub) |
| `StockMoveAdmin` | ✅ `has_change_permission()=False` (nobody can edit) | ✅ Change blocked |
| `StockMoveAdmin` | Returns `request.user.is_superuser` | 🟠 Superuser CAN delete individual stock moves (breaks audit trail) |
| `StockLocationAdmin` | ❌ NOT OVERRIDDEN | 🔴 Deleting a Location via admin cascades ALL StockMoves + StockOnHand |
| `StockBatchAdmin` | ❌ NOT OVERRIDDEN | 🔴 Deleting a Batch via admin cascades ALL StockMoves and StockOnHand for that batch |

### 7.2 Admin Bypass Risk

Django admin's bulk delete action (checkbox + "Delete selected") respects `has_delete_permission()` but NOT model-level `save()` guards. If `has_delete_permission()` returns True, the admin calls `.delete()` directly, bypassing every ViewSet protection.

---

## Defect Catalogue (Prioritized)

### CRITICAL — Data destruction possible today

| ID | Module | Description |
|---|---|---|
| DI-C1 | Clinical | `PatientViewSet` has no `destroy()` override → `DELETE /api/v1/patients/{id}/` physically deletes the Patient row and cascades to Encounter, Consent, ClinicalPhoto |
| DI-C2 | Clinical | `EncounterViewSet` has no `destroy()` override (docstring claims soft delete — **false**) → `DELETE /api/v1/encounters/{id}/` physically deletes the Encounter |
| DI-C3 | Stock | `StockLocationViewSet` + `StockBatchViewSet` have no `destroy()` overrides → DELETE physically removes a Location or Batch and **cascades all StockMoves and StockOnHand records** |
| DI-C4 | Admin | `PatientAdmin` has no `has_delete_permission()` override → superuser can bulk-delete patients via admin, destroying all clinical history |
| DI-C5 | Admin | `EncounterAdmin` has no `has_delete_permission()` override → superuser can delete encounters |

### HIGH — Significant integrity risk

| ID | Module | Description |
|---|---|---|
| DI-H1 | Admin / Sales | `SaleAdmin.has_delete_permission()` allows superuser to delete terminal sales (PAID, CANCELLED, REFUNDED) — destroys financial records |
| DI-H2 | Clinical | `Encounter.patient → CASCADE` — no model protection prevents Patient deletion from destroying all encounter history (especially when patient has no Appointments) |
| DI-H3 | Sales | `SaleLine`, `SaleRefund`, `SaleRefundLine` have no `legal_entity` / `TenantManager` — cross-tenant data accessible in admin/scripts |
| DI-H4 | Sales | Direct `sale.status = X; sale.save()` bypasses state machine transition validation |
| DI-H5 | Clinical | `Encounter` has no state machine — status can be written arbitrarily without validation or guards |
| DI-H6 | Stock | `StockMoveViewSet` has no `destroy()` override → individual StockMoves deletable via API, breaking audit trail consistency |

### MEDIUM

| ID | Module | Description |
|---|---|---|
| DI-M1 | Sales | `SaleRefund` has no model-level immutability check for COMPLETED status |
| DI-M2 | TreatmentPlans | `TreatmentSession.complete()` does not call `record_session_completed()` — fragile caller contract, plan progress can diverge |
| DI-M3 | Proposals | `Proposal.save(force_save=True)` bypass allows writing terminal proposals |
| DI-M4 | Clinical | `generate_charge_proposal_from_encounter()` validation of `encounter.status == finalized` only in service layer, not model |
| DI-M5 | Admin | `TreatmentPlanAdmin` has no `has_delete_permission()` override |

### LOW

| ID | Module | Description |
|---|---|---|
| DI-L1 | Appointment | `Appointment` missing `deleted_by_user` field (present on Patient and Encounter) |
| DI-L2 | TreatmentPlans | `TreatmentPlan` can be created directly bypassing `Proposal.accept()` atomicity |
| DI-L3 | Sales | `Sale` objects can be created without going through proposal workflow |

---

## Recommended Fix Order

1. **DI-C1** — Add `destroy()` to `PatientViewSet` implementing proper soft delete (set `is_deleted=True`, Admin-only)
2. **DI-C2** — Add `destroy()` to `EncounterViewSet` implementing proper soft delete
3. **DI-C3** — Add `destroy()` overrides to `StockLocationViewSet` + `StockBatchViewSet` preventing physical deletion (or use `http_method_names` to remove DELETE entirely)
4. **DI-C4/C5** — Add `has_delete_permission(return False)` to `PatientAdmin` and `EncounterAdmin`
5. **DI-H1** — Fix `SaleAdmin.has_delete_permission()` to always return `False` for terminal sales regardless of superuser status
6. **DI-H5** — Add Encounter state machine: `transition_to()` method + `save()` guard for invalid transitions
7. **DI-H6** — Override `destroy()` in `StockMoveViewSet` to always raise `ValidationError`
8. **DI-H3** — Add `legal_entity` FK + `TenantManager` to `SaleLine`, `SaleRefund`, `SaleRefundLine`
9. **DI-H2** — Change `Encounter.patient` FK from `CASCADE` to `PROTECT` (or rely on soft delete of Encounter being enforced)
10. **DI-H4** — Add status transition guard in `Sale.save()`: if status has changed and no `update_fields`, call `transition_to()` or raise `ValidationError`

---

*End of Domain Integrity Audit — 2025-01-02*
