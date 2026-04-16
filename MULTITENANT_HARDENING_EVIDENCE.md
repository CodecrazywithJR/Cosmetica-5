# Multi-Tenant Hardening — Evidence Pack

**Branch:** MEDICAL  
**Base commit:** 66b109f  
**Date:** 2025-07-11  
**Engineer:** Copilot autonomous agent  
**Outcome:** 841 passed, 182 skipped, 0 failed — no regressions  

---

## 1. Scope

All 8 audit findings from the multi-tenant security audit (`MULTITENANT_AUDIT_REPORT.md`) have been remediated in this session.

---

## 2. Code Changes (8 files)

### 2.1 `apps/api/apps/sales/views.py` — UNSAFE fixed
**Finding:** `SaleLineViewSet` had a class-level `queryset = SaleLine.objects.all()` that bypassed tenant filtering (SaleLine has no top-level `legal_entity`; tenant traversal requires `sale__legal_entity`).

**Fix:** Replaced with `get_queryset()` that explicitly filters `sale__legal_entity=tenant`.

```python
def get_queryset(self):
    from apps.core.tenant_context import get_current_tenant
    tenant = get_current_tenant()
    qs = SaleLine.objects.select_related('sale')
    if tenant is not None:
        qs = qs.filter(sale__legal_entity=tenant)
    return qs
```

---

### 2.2 `apps/api/apps/clinical/models.py` — UNSAFE fixed (ClinicalMediaManager)
**Finding:** `ClinicalMediaManager.get_queryset()` had a broken `super()` call that bypassed the tenant filter entirely — it returned the raw `ClinicalMediaQuerySet` without filtering.

**Fix:** Explicitly instantiate the queryset and apply `filter(legal_entity=tenant)`.

```python
def get_queryset(self):
    from apps.core.tenant_context import get_current_tenant
    qs = ClinicalMediaQuerySet(self.model, using=self._db)
    tenant = get_current_tenant()
    if tenant is not None:
        return qs.filter(legal_entity=tenant)
    return qs
```

---

### 2.3 `apps/api/apps/authz/views.py` — REQUIRES_REVIEW fixed (PractitionerViewSet)
**Finding:** `PractitionerViewSet.get_queryset()` filtered by `clinic_location__legal_entity` (an indirect, nullable path) instead of the primary `user__legal_entity` field.

**Fix:** Added `filter(user__legal_entity=tenant)` as the primary filter.

```python
if tenant is not None:
    queryset = queryset.filter(user__legal_entity=tenant)
```

---

### 2.4 `apps/api/apps/authz/views_users.py` — REQUIRES_REVIEW fixed (UserAdminViewSet)
**Finding:** `UserAdminViewSet.get_queryset()` had no tenant filter — it exposed all users across tenants to any authenticated admin.

**Fix:** Added `filter(legal_entity=tenant)`.

```python
if tenant is not None:
    queryset = queryset.filter(legal_entity=tenant)
```

---

### 2.5 `apps/api/apps/clinical/views.py` — REQUIRES_REVIEW fixed (Patient.unfiltered branch)
**Finding:** `PatientViewSet.get_queryset()` had a superuser bypass that returned `Patient.unfiltered.select_related(...)` without any `legal_entity` filter when `_tenant is None`, leaking all patients across tenants to superuser requests without a tenant header.

**Fix:** Raise `PermissionDenied` when `_tenant is None`.

```python
if include_deleted and is_admin:
    from apps.core.tenant_context import get_current_tenant as _get_tenant
    from rest_framework.exceptions import PermissionDenied as _PermissionDenied
    _tenant = _get_tenant()
    if _tenant is None:
        raise _PermissionDenied(
            "X-Legal-Entity-ID header is required when using include_deleted."
        )
    queryset = Patient.unfiltered.select_related('referral_source').filter(
        legal_entity=_tenant
    )
```

---

### 2.6 `apps/api/apps/clinical/models.py` — REQUIRES_REVIEW fixed (_check_practitioner_overlap)
**Finding:** `Appointment._check_practitioner_overlap()` used `Appointment.objects.filter(...)` with no explicit `legal_entity` constraint. In Celery/background contexts where the tenant thread-local may be unset, this could return or check appointments across tenants.

**Fix:** Uses `Appointment.unfiltered` with explicit `legal_entity=self.legal_entity` constraint.

```python
qs = Appointment.unfiltered.filter(
    practitioner_id=self.practitioner_id,
    legal_entity=self.legal_entity,
    status__in=self._ACTIVE_STATUSES,
    is_deleted=False
)
```

---

### 2.7 `apps/api/apps/clinical/attachment_counters.py` — REQUIRES_REVIEW fixed
**Finding:** `recalc_attachment_counters()` ran in Celery context. It called `Encounter.objects.get(id=encounter_id)` — which fails silently if the Celery worker has no tenant set (TenantManager returns empty queryset, raises `DoesNotExist`). The counter sub-queries also lacked explicit tenant scope.

**Fix:** Celery-safe pattern — fetch via `Encounter.unfiltered`, then set the tenant explicitly for the duration of the task.

```python
def recalc_attachment_counters(encounter_id):
    from apps.core.tenant_context import set_current_tenant, clear_current_tenant
    encounter = Encounter.unfiltered.select_for_update().get(id=encounter_id)
    set_current_tenant(encounter.legal_entity)
    try:
        photo_count  = EncounterPhoto.objects.filter(encounter=encounter, photo__is_deleted=False).count()
        document_count = EncounterDocument.objects.filter(encounter=encounter, document__is_deleted=False).count()
        # ... save ...
    finally:
        clear_current_tenant()
```

---

### 2.8 `apps/api/apps/social/views.py` — Documentation only
**Finding:** `InstagramPostViewSet` and `InstagramHashtagViewSet` were not tenant-scoped, with no comment explaining the intent.

**Fix:** Added `# GLOBAL MODEL — intentionally not tenant-scoped` comment to both ViewSets. No logic changed.

---

## 3. Test Updates (1 file)

### `apps/api/tests/test_patients_api.py`
Two existing tests assumed superusers could call `?include_deleted=true` without the `X-Legal-Entity-ID` header (the old cross-tenant bypass). After the fix in §2.5, a 403 is returned when the header is absent.

Both tests now pass the `legal_entity` fixture and add `HTTP_X_LEGAL_ENTITY_ID=str(legal_entity.id)` to the request — matching the real-world superuser flow.

---

## 4. pytest Results

```
841 passed, 182 skipped, 9 warnings in 137.52s (0:02:17)
```

Zero failures. Zero regressions.

---

## 5. bandit Scan (`apps/`)

```
Run metrics:
    Total issues (by severity):
        Low:    12
        Medium: 2
        High:   0
```

### Medium findings (pre-existing, not in changed files)

| ID   | File                        | Line | Description                   | Verdict             |
|------|-----------------------------|------|-------------------------------|---------------------|
| B608 | apps/social/tasks.py        | 78   | "SQL injection" false positive — f-string in a README.txt metadata block | False positive       |
| B108 | apps/social/tasks.py        | 99   | `/tmp` usage acknowledged with `# In production, use proper storage` comment | Pre-existing tech debt |

Neither finding is in any of the 8 files hardened in this session.

---

## 6. Residual `objects.all()` Audit

```
apps/products/views.py         Product.objects.all()       — TenantManager auto-filters ✅
apps/sales/views.py            Sale.objects.all()           — TenantManager auto-filters ✅
apps/website/views.py          WebsiteSettings.objects.all()— intentionally global (singleton) ✅
apps/social/views.py           InstagramPost/Hashtag        — GLOBAL MODEL (documented §2.8) ✅
apps/clinical/views.py         Treatment.objects.all()      — TenantManager auto-filters ✅
apps/legal/views.py            LegalEntity.objects.all()    — not tenant-scoped by design ✅
```

No new cross-tenant leaks found.

---

## 7. Modified Files Summary

| File | Change type |
|------|-------------|
| `apps/api/apps/sales/views.py` | SaleLineViewSet: explicit `get_queryset()` with `sale__legal_entity` filter |
| `apps/api/apps/clinical/models.py` | ClinicalMediaManager: fixed broken `super()` + `_check_practitioner_overlap` uses `unfiltered` |
| `apps/api/apps/authz/views.py` | PractitionerViewSet: `user__legal_entity` filter |
| `apps/api/apps/authz/views_users.py` | UserAdminViewSet: `legal_entity` filter |
| `apps/api/apps/clinical/views.py` | Patient.unfiltered branch: PermissionDenied when no tenant header |
| `apps/api/apps/clinical/attachment_counters.py` | Celery-safe: `unfiltered` fetch + `set_current_tenant` + `finally: clear` |
| `apps/api/apps/social/views.py` | GLOBAL MODEL comments (no logic change) |
| `apps/api/tests/test_patients_api.py` | 2 tests updated to supply X-Legal-Entity-ID header |
