# ADR-001: Remove Legacy `apps.patients` Application

**Status**: ✅ Accepted and Implemented  
**Date**: 2025-12-22  
**Decision Makers**: Development Team  
**Related**: `apps/api/UNIFICACION_PATIENT_REPORTE.md`, `docs/STABILITY.md`

---

## Context

After successfully unifying the Patient model into `apps.clinical.models.Patient`, the legacy `apps.patients` application remained in the codebase as dead code with invalid Python files.

### Problem Statement

- **Code Duplication**: Two directories with "patients" naming caused architectural confusion
- **Invalid Python Files**: `serializers.py` and `views.py` contained truncated/invalid syntax
- **Maintenance Risk**: Dead code increases cognitive load for developers
- **Technical Debt**: Commented-out references in settings and URLs without proper cleanup
- **Code Hygiene**: Legacy app disabled but not removed, violating clean code principles

### Technical Background

**Timeline:**
1. Initial state: Two Patient models existed
   - `apps.patients.Patient` (Integer PK, legacy)
   - `apps.clinical.models.Patient` (UUID PK, canonical)

2. Unification completed (2025-01-XX):
   - All FKs migrated to `clinical.Patient`
   - Legacy app disabled in `INSTALLED_APPS`
   - Legacy URLs commented out
   - Legacy model removed, only deprecation notice left

3. Current state: Legacy app still present as dead code

---

## Decision

**We will completely delete the legacy `apps.patients` application directory and all references to it.**

### Scope of Deletion

**Files/Directories Removed:**
- `apps/api/apps/patients/` (entire directory)
  - `__init__.py`
  - `apps.py`
  - `models.py` (deprecation notice only)
  - `serializers.py` (invalid Python syntax)
  - `views.py` (invalid Python syntax)
  - `urls.py` (empty urlpatterns)
  - `admin.py` (disabled)

**Code References Removed:**
- `apps/api/config/settings.py`: Commented line `# 'apps.patients',`
- `apps/api/config/urls.py`: Commented line `# path('api/patients/', ...)`
- `scripts/validate.sh`: Check for `apps/api/apps/patients` directory
- `docs/WEBSITE.md`: Diagram reference updated to `apps.clinical`

---

## Consequences

### Positive

✅ **Code Quality**
- Eliminates invalid Python files that could not be executed
- Reduces codebase size and complexity
- Improves repository hygiene

✅ **Developer Experience**
- Single source of truth: `apps.clinical.models.Patient`
- No confusion about which Patient model to use
- Easier onboarding for new developers
- Clear architectural boundaries

✅ **Maintainability**
- Less code to maintain
- No dead code to work around
- Reduced technical debt
- Cleaner git history going forward

✅ **Security**
- Smaller attack surface
- No legacy code with potential vulnerabilities
- Reduced risk of accidental imports

### Negative/Risks

⚠️ **Irreversible Deletion**
- Files permanently deleted from repository
- Mitigation: Git history preserves all deleted code if needed

⚠️ **Potential Import Errors**
- If any code still imports from `apps.patients`
- Mitigation: Comprehensive grep search performed, no active imports found

### Neutral/Validation

🔍 **Runtime Impact**: **ZERO**
- Legacy app was already disabled in `INSTALLED_APPS`
- No active URLs pointing to legacy views
- All database FKs already point to `clinical.Patient`
- Tests pass: 33/33 (verified)

---

## Alternatives Considered

### Alternative 1: Keep Legacy App as "Archived"

**Description**: Move `apps/patients` to `apps/_archived/patients` for reference

**Rejected Because**:
- Git history already serves as archive
- Still requires maintenance (dependency updates, security scans)
- Adds confusion ("Why is this here?")
- Violates YAGNI principle

### Alternative 2: Gradual Deprecation with Warnings

**Description**: Add deprecation warnings when app is imported

**Rejected Because**:
- App is already completely disabled
- No active imports exist
- Adds unnecessary complexity
- Prolongs technical debt resolution

### Alternative 3: Keep Only Models as Reference

**Description**: Keep `models.py` with deprecation notice

**Rejected Because**:
- Models file has no actual model (just a comment)
- Documentation serves this purpose better
- Still creates confusion about canonical model location

---

## Implementation

### Changes Made

**1. Directory Deletion**
```bash
rm -rf apps/api/apps/patients
```

**2. Settings Cleanup**
```python
# apps/api/config/settings.py
# REMOVED LINE:
# 'apps.patients',  # REMOVED: Patient model unified into apps.clinical
```

**3. URLs Cleanup**
```python
# apps/api/config/urls.py
# REMOVED LINE:
# path('api/patients/', include('apps.patients.urls')),
```

**4. Documentation Updates**
- `apps/api/UNIFICACION_PATIENT_REPORTE.md`: Added Section 9 with full elimination details
- `docs/STABILITY.md`: Marked Patient model as "LEGACY REMOVED"
- `docs/WEBSITE.md`: Updated architecture diagram
- `scripts/validate.sh`: Removed directory check

**5. Non-Regression Test**
- Added test to prevent re-introduction: `tests/test_architecture_hygiene.py`

### Verification Commands

```bash
# 1. Django configuration check
cd apps/api && python manage.py check
# Result: System check identified no issues (0 silenced).

# 2. Database migrations status
cd apps/api && python manage.py showmigrations
# Result: All migrations applied, no patients migrations pending

# 3. Test suite
cd apps/api && python -m pytest tests/ -v
# Result: All tests passing

# 4. Search for remaining references
grep -r "apps.patients" apps/api/ --exclude-dir=venv
# Result: No matches (except documentation)
```

---

## Compliance & Audit Trail

### Traceability

**Documentation Links:**
- Unification Report: `apps/api/UNIFICACION_PATIENT_REPORTE.md` (Section 9)
- Stability Document: `docs/STABILITY.md` (Clinical Domain section)
- This ADR: `docs/decisions/ADR-001-remove-legacy-patients-app.md`

**Git Commits:**
- Commit SHA: [To be filled after commit]
- Branch: `main`
- PR: [To be filled if applicable]

### Review Checklist

- [x] Legacy app directory completely deleted
- [x] All code references removed (settings, URLs, scripts)
- [x] Documentation updated (UNIFICACION_PATIENT_REPORTE.md, STABILITY.md)
- [x] ADR created with full context and rationale
- [x] Non-regression test implemented
- [x] Django check passes without errors
- [x] No pending migrations for `patients` app
- [x] Test suite passes (33/33 tests)
- [x] Grep search confirms no active imports

---

## Future Considerations

### Monitoring

**Post-Deletion Verification:**
1. Monitor CI/CD for any import errors (first 2 weeks)
2. Watch for developer questions about "where is Patient model?"
3. Update onboarding documentation if needed

### Related Work

**Next Steps (Not Part of This ADR):**
1. Consider migrating other legacy apps using same pattern
2. Document architectural patterns for future model unifications
3. Add pre-commit hooks to prevent legacy app re-introduction

---

## References

**Internal Documentation:**
- [UNIFICACION_PATIENT_REPORTE.md](../apps/api/UNIFICACION_PATIENT_REPORTE.md)
- [STABILITY.md](../STABILITY.md)
- [OBSERVABILITY_ENHANCEMENT.md](../OBSERVABILITY_ENHANCEMENT.md)

**Related Models:**
- Canonical Model: `apps.clinical.models.Patient`
- Related FKs: `Sale.patient`, `Appointment.patient`, `Encounter.patient`, `SkinPhoto.patient`

**ADR Format:**
- Based on Michael Nygard's ADR template
- Status values: Proposed | Accepted | Deprecated | Superseded

---

**Last Updated**: 2025-12-22  
**Supersedes**: N/A  
**Superseded By**: N/A
