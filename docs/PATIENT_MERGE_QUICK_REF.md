# Patient Merge System - Quick Reference

**Version**: 1.0  
**Last Updated**: January 2025

---

## 🎯 Overview

The patient merge system consolidates duplicate patient records while preserving complete audit trails. All merges are **irreversible** and **manual-only** (no automatic merging).

---

## 📊 Prometheus Metrics

### Success Counter
```promql
patient_merge_total{strategy="manual"}
patient_merge_total{strategy="phone_exact"}
patient_merge_total{strategy="email_exact"}
patient_merge_total{strategy="name_trgm"}
patient_merge_total{strategy="other"}
```

### Failure Counter
```promql
patient_merge_failed_total{reason="patient_not_found"}
patient_merge_failed_total{reason="self_merge"}
patient_merge_failed_total{reason="source_already_merged"}
patient_merge_failed_total{reason="target_already_merged"}
patient_merge_failed_total{reason="circular_merge"}
patient_merge_failed_total{reason="validation_error"}
```

### Example Queries
```promql
# Merge rate by strategy (last 24h)
rate(patient_merge_total[24h])

# Failure rate
rate(patient_merge_failed_total[24h])

# Total merges today
increase(patient_merge_total[1d])

# Failed merges by reason
sum by (reason) (patient_merge_failed_total)
```

---

## 🔔 Django Signal

### Signal Name
`apps.clinical.signals.patient_merged`

### Payload (All UUIDs, NO PHI)
```python
{
    'sender': Patient,                      # Sender class
    'source_patient_id': str,               # UUID of merged patient
    'target_patient_id': str,               # UUID of surviving patient
    'strategy': str,                        # Merge strategy used
    'merged_by_user_id': str | None,        # UUID of user (if authenticated)
    'merge_log_id': str                     # UUID of PatientMergeLog entry
}
```

### Example Listener
```python
from django.dispatch import receiver
from django.db import transaction
from apps.clinical.signals import patient_merged

@receiver(patient_merged)
def on_merge(sender, source_patient_id, target_patient_id, 
             strategy, merged_by_user_id, merge_log_id, **kwargs):
    
    def _post_merge():
        # Your logic here (runs only if transaction commits)
        pass
    
    transaction.on_commit(_post_merge)
```

---

## 🔍 Merge Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `manual` | Clinical review by staff | **Recommended default** - human verification |
| `phone_exact` | Exact phone match | Same number during different visits |
| `email_exact` | Exact email match | Online booking duplicates |
| `name_trgm` | Fuzzy name match | Typos, maiden/married name variations |
| `other` | Complex scenario | Requires manual investigation |

---

## 🔐 PHI Protection

**Guaranteed NO PHI in**:
- ✅ Prometheus metrics (only counts + labels)
- ✅ Django signals (only UUIDs)
- ✅ Log aggregations

**PHI Available Only Via**:
- 🔒 `PatientMergeLog.id` → Full audit trail
- 🔒 Database queries with proper authentication
- 🔒 Admin interface (restricted access)

---

## 🚀 API Endpoints

### Find Candidates
```http
GET /api/v1/clinical/patients/merge-candidates/?patient_id=<uuid>
```

**Response Example**:
```json
{
  "candidates": [
    {
      "patient_id": "550e8400-e29b-41d4-a716-446655440001",
      "confidence": 0.92,
      "match_reasons": [
        "phone_exact: +1-212-555-0123",
        "name_similarity: 0.89"
      ],
      "suggested_strategy": "phone_exact"
    }
  ]
}
```

---

### Execute Merge
```http
POST /api/v1/clinical/patients/merge
Content-Type: application/json

{
  "source_patient_id": "550e8400-...",
  "target_patient_id": "660e9411-...",
  "strategy": "manual",
  "notes": "Confirmed by clinical ops during chart review"
}
```

**Response**: `200 OK` with target patient details

---

## 📋 Validation Rules

| Rule | Check |
|------|-------|
| **Both exist** | Source and target must be active patients |
| **Not same** | `source_patient_id ≠ target_patient_id` |
| **Source not merged** | Source has not been merged before |
| **Target not merged** | Target has not been merged before |
| **No circular merge** | Target is not a previous source of current source |

---

## 🗂️ Audit Trail

### Model: `PatientMergeLog`

**Fields**:
- `id`: UUID (use as reference in logs)
- `source_patient`: FK to merged patient
- `target_patient`: FK to surviving patient
- `strategy`: Choice field
- `merged_by`: FK to User
- `merged_at`: Timestamp
- `notes`: Optional text
- `relationships_snapshot`: JSON (all transferred relations)

**Query Example**:
```python
from apps.clinical.models import PatientMergeLog

# Get merge history for patient
merges = PatientMergeLog.objects.filter(
    target_patient_id='<uuid>'
).order_by('-merged_at')

# Get specific merge details
log = PatientMergeLog.objects.get(id='<merge_log_id>')
print(log.relationships_snapshot)  # See all transferred data
```

---

## ⚠️ Important Notes

1. **No Automatic Merging**: All merges require explicit API call
2. **Irreversible**: No undo functionality (by design)
3. **Atomic**: All-or-nothing transaction
4. **Manual Strategy Preferred**: Always use `strategy="manual"` unless specific automation approved
5. **Test in Staging**: Never test merge logic in production

---

## 🧪 Testing

```bash
# Run merge tests
pytest tests/test_patient_merge.py -v

# Test signal emission
pytest tests/test_patient_merge.py::TestPatientMergeSignals -v

# Check for regressions
pytest tests/test_pos_*.py -v
```

---

## 📚 Full Documentation

See `docs/API_CONTRACTS.md` section "Patient Merge & Identity Resolution" for:
- Complete request/response schemas
- Clinical use cases
- Error handling
- Integration patterns

---

## 🆘 Troubleshooting

### Metric not incrementing?
Check if `prometheus_client` installed:
```bash
pip list | grep prometheus
```

### Signal not firing?
Verify transaction commits successfully - use `transaction.on_commit()`

### Merge fails silently?
Check validation in response - likely duplicate prevention rule triggered

---

**For Production Incidents**: Contact Clinical Ops Lead  
**For Development**: See `OBSERVABILITY_ENHANCEMENT.md`
