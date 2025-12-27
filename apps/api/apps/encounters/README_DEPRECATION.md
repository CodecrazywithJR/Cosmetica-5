# ⚠️ DEPRECATION NOTICE - apps/encounters/

**Date**: 2025-12-25  
**Status**: ⛔ PARTIALLY DEPRECATED  

---

## 🚨 What's Deprecated

### ❌ Legacy Encounter Model
- **File**: `models.py` → `Encounter` class
- **Reason**: Replaced by `apps.clinical.models.Encounter`
- **DO NOT USE**: This model for new code

### ❌ Legacy Endpoint
- **URL**: `/api/encounters/`
- **Status**: Commented out in `config/urls.py`
- **Replacement**: `/api/v1/clinical/encounters/`

### ❌ Legacy Views/Serializers
- **Files**: `views.py`, `serializers.py`, `urls.py`
- **Status**: Not used by frontend
- **Action**: Do not import or extend

---

## ✅ What's ACTIVE (Keep Using)

### ✅ ClinicalMedia Model
- **File**: `models_media.py` → `ClinicalMedia` class
- **Status**: **ACTIVE** - Production model
- **Purpose**: Clinical photos/documents for encounters
- **Import**: `from apps.encounters.models import ClinicalMedia`
- **API**: `/api/v1/clinical/media/`

### ✅ ClinicalMedia API
- **Files**: `api/views_media.py`, `api/serializers_media.py`, `api/urls_media.py`
- **Status**: **ACTIVE** - Used in production
- **Endpoint**: `/api/v1/clinical/media/`

---

## 🔄 Migration Guide

### Before (Legacy ❌)
```python
from apps.encounters.models import Encounter  # DEPRECATED
from apps.encounters.serializers import EncounterSerializer  # DEPRECATED

# Frontend
fetch('/api/encounters/')  # DEPRECATED
```

### After (Modern ✅)
```python
from apps.clinical.models import Encounter  # CORRECT
from apps.clinical.serializers import EncounterSerializer  # CORRECT

# Frontend
fetch('/api/v1/clinical/encounters/')  # CORRECT
```

### ClinicalMedia (Still Active ✅)
```python
from apps.encounters.models import ClinicalMedia  # STILL CORRECT
# OR
from apps.encounters.models_media import ClinicalMedia  # ALSO CORRECT
```

---

## 📊 Deprecation Rationale

### Why Deprecate Legacy Encounter?

1. **Incorrect Foreign Key**: Points to `User` instead of `Practitioner`
2. **No Appointment Link**: Not integrated with scheduling workflow
3. **Poor Clinical Integration**: Lacks proper SOAP notes structure
4. **Unused by Frontend**: No code references `/api/encounters/`
5. **Better Alternative Exists**: `apps.clinical.Encounter` is complete

### Why Keep ClinicalMedia Here?

1. **Production Data**: Contains real clinical photos/documents
2. **Active API**: `/api/v1/clinical/media/` is used by frontend
3. **No Duplication**: No equivalent model in `apps.clinical`
4. **Clean Separation**: Media management is distinct from encounter logic

---

## 🗓️ Deprecation Timeline

| Date | Action | Status |
|------|--------|--------|
| 2025-12-25 | Mark Encounter model as DEPRECATED | ✅ DONE |
| 2025-12-25 | Remove `/api/encounters/` from urls | ✅ DONE |
| 2025-12-25 | Add deprecation warnings to code | ✅ DONE |
| 2026-01-XX | Add Django system check warnings | ⏳ TODO |
| 2026-03-XX | Migrate any residual data to clinical.Encounter | ⏳ TODO |
| 2026-06-XX | Remove legacy models.py, views.py, serializers.py | ⏳ TODO |

---

## 🔧 Maintenance Notes

- ✅ **ClinicalMedia API** - Actively maintained
- ❌ **Legacy Encounter** - No new features, bug fixes only
- ❌ **Legacy endpoint** - Removed from routing

**Questions?** See `docs/PROJECT_DECISIONS.md` §12.20 for full context.
