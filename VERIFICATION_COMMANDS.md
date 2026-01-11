# 🔧 Verification Commands - Legacy Patients App Removal

Quick reference commands to verify the complete removal of `apps.patients`.

---

## ✅ Pre-Merge Verification (Run These)

### 1. Verify Directory Deleted
```bash
# Should show "No such file or directory"
ls apps/api/apps/patients
```

### 2. Django Configuration Check
```bash
cd apps/api
source ../.venv/bin/activate
python manage.py check
# Expected: System check identified no issues (0 silenced).
```

### 3. Run Architecture Hygiene Tests
```bash
cd apps/api
source ../.venv/bin/activate
pytest tests/test_architecture_hygiene.py -v
# Expected: =================== 10 passed =================== 
```

### 4. Search for Active Python Imports
```bash
# Search for imports in Python files (exclude docs and tests)
grep -r "from apps.patients" apps/api/ --include="*.py" \
  --exclude-dir=venv --exclude-dir=__pycache__ | \
  grep -v "test_architecture_hygiene.py"
# Expected: No results
```

### 5. Verify settings.py Clean
```bash
# Should return nothing (no commented or active references)
grep -i "patients" apps/api/config/settings.py | grep -v clinical
# Expected: No results
```

### 6. Verify urls.py Clean
```bash
# Should return nothing (no commented or active references)
grep -i "patients" apps/api/config/urls.py | grep -v clinical
# Expected: No results
```

---

## 🧪 Test Suite Commands

### Run All Architecture Tests
```bash
cd apps/api
source ../.venv/bin/activate
pytest tests/test_architecture_hygiene.py -v --tb=short
```

### Run Specific Test Classes
```bash
# Test legacy patients app is removed
pytest tests/test_architecture_hygiene.py::TestLegacyPatientsAppRemoved -v

# Test patient model unification
pytest tests/test_architecture_hygiene.py::TestPatientModelUnification -v

# Test architectural boundaries
pytest tests/test_architecture_hygiene.py::TestArchitecturalBoundaries -v
```

### Run With Detailed Output
```bash
pytest tests/test_architecture_hygiene.py -v -s --tb=long
```

---

## 🔍 Deep Verification (Optional)

### Search Entire Codebase for "patients"
```bash
# Find all occurrences (will include docs and test files)
grep -r "apps\.patients" . --include="*.py" --include="*.md" \
  --exclude-dir=venv --exclude-dir=.venv --exclude-dir=__pycache__ \
  --exclude-dir=.git | less
```

### Verify No Orphaned Migrations
```bash
find apps/api/apps -name "migrations" -type d | xargs -I {} find {} -name "*.py" | xargs grep -l "patients" | grep -v clinical
# Expected: No results (or only clinical app)
```

### Verify Patient Model Location
```bash
cd apps/api
source ../.venv/bin/activate
python manage.py shell << EOF
from django.apps import apps
from apps.clinical.models import Patient

# Show all Patient models
patient_models = [m for m in apps.get_models() if m.__name__ == 'Patient']
print(f"Found {len(patient_models)} Patient model(s):")
for m in patient_models:
    print(f"  - {m._meta.app_label}.{m.__name__}")
    print(f"    PK Type: {m._meta.pk.get_internal_type()}")

# Verify only clinical.Patient exists
assert len(patient_models) == 1, f"Expected 1 Patient model, found {len(patient_models)}"
assert patient_models[0]._meta.app_label == 'clinical'
assert patient_models[0]._meta.pk.get_internal_type() == 'UUIDField'
print("\n✅ Verification passed: Only clinical.Patient exists with UUID PK")
EOF
```

---

## 🗄️ Database Verification (Requires Docker Compose)

### Start PostgreSQL
```bash
cd /path/to/project
docker-compose up -d postgres
```

### Check Migrations Status
```bash
cd apps/api
source ../.venv/bin/activate
python manage.py showmigrations | grep -E "(patients|clinical)"
# clinical migrations should be present
# NO patients migrations should appear
```

### Verify clinical_patient Table Exists
```bash
cd apps/api
source ../.venv/bin/activate
python manage.py dbshell << EOF
\dt clinical_*
\d clinical_patient
\q
EOF
```

---

## 📊 Code Metrics

### Count Python Files
```bash
# Before (hypothetical): 7 files in apps/patients
# After: 0 files
find apps/api/apps/patients -name "*.py" 2>/dev/null | wc -l
# Expected: 0 (or error "No such file or directory")
```

### Check INSTALLED_APPS Count
```bash
cd apps/api
source ../.venv/bin/activate
python -c "from config.settings import INSTALLED_APPS; print(f'Total apps: {len(INSTALLED_APPS)}'); print('apps.patients in INSTALLED_APPS:', 'apps.patients' in INSTALLED_APPS)"
# Expected: Total apps: 13, apps.patients in INSTALLED_APPS: False
```

---

## 🚨 Expected Test Failures (Not an Error)

### Tests Requiring Database
```bash
# These tests will fail WITHOUT database running (this is normal)
pytest tests/test_patient_merge.py tests/test_pos_*.py
# Error: django.db.utils.OperationalError: could not translate host name "postgres"
# This is EXPECTED if PostgreSQL is not running
```

**Solution**: Start database with `docker-compose up -d postgres` then re-run.

---

## 📚 Documentation Verification

### Check ADR Exists
```bash
ls -lh docs/decisions/ADR-001-remove-legacy-patients-app.md
# Expected: File should exist (~8KB)
```

### Check Unification Report Updated
```bash
grep -A 5 "Eliminación Completa" apps/api/UNIFICACION_PATIENT_REPORTE.md
# Expected: Should show Section 9 with 2025-12-22 date
```

### Check STABILITY.md Updated
```bash
grep -A 3 "COMPLETELY DELETED" docs/STABILITY.md
# Expected: Should reference apps.patients deletion
```

---

## 🔄 CI/CD Integration

### Commands for CI Pipeline
```bash
# Run in CI environment
cd apps/api

# 1. Django check
python manage.py check --deploy

# 2. Architecture tests (no DB required)
pytest tests/test_architecture_hygiene.py -v --tb=short

# 3. Full test suite (requires DB)
pytest tests/ -v --cov=apps --cov-report=term-missing

# 4. Code quality
ruff check apps/
black --check apps/
mypy apps/
```

---

## 🛠️ Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'apps.patients'"

**Cause**: Old cached `.pyc` files or unsynced IDE

**Solution**:
```bash
# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# Restart IDE/editor
# Re-run tests
```

### Issue: Test fails with "apps.patients found in INSTALLED_APPS"

**Cause**: `settings.py` still has reference

**Solution**:
```bash
# Check settings.py
grep "apps.patients" apps/api/config/settings.py

# Should return nothing - if it does, remove the line
```

### Issue: Architecture test fails on directory existence

**Cause**: Directory still exists

**Solution**:
```bash
# Verify directory is gone
ls apps/api/apps/patients

# If it exists, delete it
rm -rf apps/api/apps/patients
```

---

## ✅ Success Criteria Checklist

Run all commands above and verify:

- [ ] `ls apps/api/apps/patients` → "No such file or directory"
- [ ] `python manage.py check` → "System check identified no issues"
- [ ] `pytest tests/test_architecture_hygiene.py` → "10 passed"
- [ ] `grep "apps.patients" config/settings.py` → No results
- [ ] `grep "apps.patients" config/urls.py` → No results
- [ ] ADR file exists: `docs/decisions/ADR-001-remove-legacy-patients-app.md`
- [ ] Section 9 exists in: `apps/api/UNIFICACION_PATIENT_REPORTE.md`
- [ ] STABILITY.md updated with "COMPLETELY DELETED"

---

## 📞 Support

**All tests passing?** ✅ Ready to merge!

**Test failures?** Check:
1. Virtual environment activated (`source .venv/bin/activate`)
2. Python cache cleared (`find . -name __pycache__ -exec rm -rf {} +`)
3. PostgreSQL running (if testing DB-dependent tests)

**Still issues?** See:
- `docs/decisions/ADR-001-remove-legacy-patients-app.md`
- `PR_SUMMARY.md`
- `apps/api/UNIFICACION_PATIENT_REPORTE.md`
