# Patient Merge Observability Enhancement

**Completed**: January 2025  
**Objective**: Enhance observability and documentation of patient merge system WITHOUT changing business logic

---

## ✅ Changes Completed

### 1. Prometheus Metrics (Renamed)

**File**: `apps/clinical/services.py`

#### Before:
```python
MERGE_COUNTER = Counter('patient_merge_success_total', ...)
MERGE_FAILED_COUNTER = Counter('patient_merge_failure_total', ...)
```

#### After:
```python
MERGE_COUNTER = Counter('patient_merge_total', ...)
MERGE_FAILED_COUNTER = Counter('patient_merge_failed_total', ...)
```

**Impact**: Metric names now follow standard Prometheus naming conventions (state-focused rather than action-focused)

**Labels**:
- `patient_merge_total{strategy}`: Tracks successful merges by strategy
  - `strategy`: `manual`, `phone_exact`, `email_exact`, `name_trgm`, `other`
  
- `patient_merge_failed_total{reason}`: Tracks failures by reason
  - `reason`: `patient_not_found`, `self_merge`, `source_already_merged`, `target_already_merged`, `circular_merge`, `validation_error`

---

### 2. Django Signal Enhancement

**File**: `apps/clinical/services.py` (Line ~169)

#### Added Parameter:
```python
patient_merged.send(
    sender=Patient,
    source_patient_id=str(source.id),
    target_patient_id=str(target.id),
    strategy=strategy,
    merged_by_user_id=str(merged_by.id) if merged_by else None,
    merge_log_id=str(merge_log.id)  # ← NEW: Link to audit trail
)
```

**Benefit**: Listeners can now access the complete audit log entry directly via `merge_log_id`

---

### 3. Signal Documentation

**File**: `apps/clinical/signals.py`

#### Enhanced Docstring:
- Complete payload documentation (all 6 parameters)
- Example listener with `transaction.on_commit()` pattern
- Emphasis on UUID-only payload (NO PHI)

#### Example Listener Added:
```python
@receiver(patient_merged)
def notify_merge(sender, source_patient_id, target_patient_id, 
                 strategy, merged_by_user_id, merge_log_id, **kwargs):
    # Use on_commit to guarantee execution only after successful transaction
    transaction.on_commit(
        lambda: send_notification(target_patient_id, merge_log_id, strategy)
    )
```

---

### 4. API Documentation Enhancement

**File**: `docs/API_CONTRACTS.md`

#### Section Renamed:
- **Before**: "Patient Merge Operations"
- **After**: "Patient Merge & Identity Resolution"

#### Improvements Made:

**A) Overview Section**:
- Added functional description emphasizing manual-only approach
- Clear irreversibility warning
- Explained atomic transaction guarantees

**B) GET `/api/v1/patients/merge-candidates/` Section**:
- Enhanced example with realistic clinical scenario:
  - "Duplicate from different reception shifts"
  - Confidence scores explained
  - Real-world names and contact info patterns
- Added strategy suggestions with clinical rationale

**C) POST `/api/v1/patients/merge/` Section**:
- ⚠️ **CRITICAL** warning about manual-only execution
- Each strategy documented with clinical use case:
  - `manual`: Clinical review by practitioner (recommended)
  - `phone_exact`: Same phone number identified during intake
  - `email_exact`: Email match from online booking system
  - `name_trgm`: Fuzzy match for typos or name variations (maiden/married)
  - `other`: Complex cases requiring manual review
- Enhanced field definitions with clinical context

**D) Prometheus Metrics Section**:
- Updated metric names: `patient_merge_total`, `patient_merge_failed_total`
- Example queries with realistic counts
- Emphasized all strategies and failure reasons

**E) PHI Protection Subsection** (NEW):
```markdown
#### PHI Protection
- Metrics contain NO PHI (only aggregated counts)
- Signal payload contains only UUIDs
- Logs must use `merge_log_id` for audit trail queries
```

**F) Django Signal Documentation**:
- All 6 parameters documented
- Example listener with `transaction.on_commit()` pattern
- Multiple integration examples (notifications, CRM sync, analytics)

---

## 🔒 Business Logic Guarantees

**NO CHANGES MADE TO**:
- ✅ Merge algorithm
- ✅ Validation rules
- ✅ Database constraints
- ✅ Transaction boundaries
- ✅ Audit trail creation
- ✅ Related entity transfers
- ✅ Error handling logic

**ONLY CHANGED**:
- ✅ Metric names (cosmetic)
- ✅ Signal payload (additive, non-breaking)
- ✅ Documentation (clarity and clinical context)

---

## ✅ Verification Results

### Django Check
```bash
$ python manage.py check
System check identified no issues (0 silenced).
```

### Test Suite
```bash
$ python -m pytest tests/test_patient_merge.py -v
============== 11 passed in 4.37s ===============

$ python -m pytest tests/test_pos_*.py -v
============== 22 passed in 4.77s ===============

$ python -m pytest tests/test_patient_merge.py::TestPatientMergeSignals -v
=============== 1 passed in 0.71s ===============
  (Verified merge_log_id parameter in signal payload)
```

**Total**: 33/33 tests passing

**Signal Test Update**: Added assertion to verify `merge_log_id` is present in signal payload

---

## 📊 Observability Stack

### Current State:
1. **Prometheus Metrics**: Optional (with NO_OP fallback)
   - `patient_merge_total{strategy}`
   - `patient_merge_failed_total{reason}`

2. **Django Signals**: Active
   - `patient_merged` signal with 6 parameters
   - Example listener documented

3. **Audit Trail**: PostgreSQL-based
   - `PatientMergeLog` model
   - Complete history with relationship snapshots

4. **Documentation**: Production-ready
   - Clinical context in all examples
   - PHI protection emphasized
   - Integration patterns documented

---

## 🚀 Next Steps (Optional Future Work)

### Potential Additions:
1. **Grafana Dashboards**:
   - Merge volume by strategy
   - Failure rate trends
   - Candidate detection accuracy

2. **Integration Listeners**:
   - CRM sync (if external system exists)
   - Clinical ops notifications
   - Analytics pipeline

3. **UI Enhancements** (as documented in API_CONTRACTS.md):
   - Batch merge confirmation modal
   - Undo warning dialog
   - Merge history timeline

---

## 📝 Files Modified

| File | Lines Changed | Purpose |
|------|---------------|---------|
| `apps/clinical/services.py` | 19-26, ~169 | Rename metrics, add `merge_log_id` to signal |
| `apps/clinical/signals.py` | Complete rewrite | Enhanced docstring + example listener |
| `docs/API_CONTRACTS.md` | Multiple sections | Clinical context, strategy definitions, PHI protection |
| `tests/test_patient_merge.py` | Line 469 | Verify `merge_log_id` in signal payload |

---

## 🎯 Summary

This enhancement provides **production-grade observability** for the patient merge system:

- **Metrics**: Standardized naming with comprehensive labels
- **Signals**: Complete payload with audit trail reference
- **Documentation**: Clinical context throughout, ready for stakeholder review
- **Security**: Explicit PHI protection guarantees

**Business logic remains untouched**, with all 33 tests passing.

The system is now ready for:
- Prometheus/Grafana integration
- Custom listener development
- Clinical operations review
- External system integration

---

**Enhancement Completed**: ✅  
**Business Logic Unchanged**: ✅  
**Tests Passing**: ✅ 33/33  
**Documentation Production-Ready**: ✅
