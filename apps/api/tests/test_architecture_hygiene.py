"""
Architecture Hygiene Tests

Tests to prevent re-introduction of legacy code and maintain architectural cleanliness.

These tests enforce architectural decisions documented in:
- docs/decisions/ADR-001-remove-legacy-patients-app.md
- apps/api/UNIFICACION_PATIENT_REPORTE.md (Section 9)
"""
import os
import re
from pathlib import Path

import pytest
from django.conf import settings


class TestLegacyPatientsAppRemoved:
    """
    Ensure legacy apps.patients app remains deleted.
    
    Context: apps.patients was unified into apps.clinical.models.Patient
    and completely removed on 2025-12-22. These tests prevent accidental
    re-introduction.
    
    See: docs/decisions/ADR-001-remove-legacy-patients-app.md
    """
    
    def test_patients_not_in_installed_apps(self):
        """apps.patients must not be in INSTALLED_APPS."""
        installed_apps = settings.INSTALLED_APPS
        
        # Check for exact match
        assert 'apps.patients' not in installed_apps, (
            "❌ Legacy app 'apps.patients' found in INSTALLED_APPS. "
            "Use 'apps.clinical.models.Patient' instead. "
            "See: docs/decisions/ADR-001-remove-legacy-patients-app.md"
        )
        
        # Check for any variant
        patients_apps = [app for app in installed_apps if 'patients' in app.lower()]
        invalid_apps = [app for app in patients_apps if app != 'apps.clinical']
        
        assert not invalid_apps, (
            f"❌ Suspicious 'patients' app(s) found in INSTALLED_APPS: {invalid_apps}. "
            f"Only 'apps.clinical' should contain patient models. "
            f"See: docs/decisions/ADR-001-remove-legacy-patients-app.md"
        )
    
    def test_patients_directory_does_not_exist(self):
        """apps/patients directory must not exist in the filesystem."""
        base_dir = Path(settings.BASE_DIR)
        patients_dir = base_dir / 'apps' / 'patients'
        
        assert not patients_dir.exists(), (
            f"❌ Legacy directory '{patients_dir}' found. "
            f"This directory was deleted on 2025-12-22. "
            f"Patient model unified in apps.clinical.models.Patient. "
            f"See: docs/decisions/ADR-001-remove-legacy-patients-app.md"
        )
    
    def test_no_imports_from_apps_patients(self):
        """
        No Python files should import from apps.patients.
        
        Scans all .py files in apps/ directory (excluding venv, migrations, __pycache__).
        """
        base_dir = Path(settings.BASE_DIR)
        apps_dir = base_dir / 'apps'
        
        if not apps_dir.exists():
            pytest.skip("apps/ directory not found")
        
        # Pattern to match: from apps.patients OR import apps.patients
        legacy_import_pattern = re.compile(
            r'(?:from\s+apps\.patients|import\s+apps\.patients)',
            re.IGNORECASE
        )
        
        violations = []
        
        for py_file in apps_dir.rglob('*.py'):
            # Skip migrations, __pycache__, venv, test files
            if any(skip in py_file.parts for skip in ['migrations', '__pycache__', '.venv', 'venv']):
                continue
            
            try:
                content = py_file.read_text(encoding='utf-8')
                
                # Search for legacy imports
                matches = legacy_import_pattern.findall(content)
                if matches:
                    violations.append(f"{py_file.relative_to(base_dir)}: {matches}")
            
            except (UnicodeDecodeError, PermissionError):
                # Skip files that can't be read
                continue
        
        assert not violations, (
            f"❌ Found {len(violations)} file(s) importing from legacy 'apps.patients':\n"
            + "\n".join(violations) +
            "\n\nUse 'from apps.clinical.models import Patient' instead. "
            "See: docs/decisions/ADR-001-remove-legacy-patients-app.md"
        )
    
    def test_settings_file_has_no_commented_patients(self):
        """
        settings.py should not have commented references to apps.patients.
        
        Even commented code can be confusing. Legacy references should be
        completely removed, not just commented out.
        """
        settings_file = Path(settings.BASE_DIR) / 'config' / 'settings.py'
        
        if not settings_file.exists():
            pytest.skip("config/settings.py not found")
        
        content = settings_file.read_text(encoding='utf-8')
        
        # Look for commented lines with apps.patients
        commented_patients = [
            line.strip() for line in content.split('\n')
            if line.strip().startswith('#') and 'apps.patients' in line.lower()
        ]
        
        assert not commented_patients, (
            f"❌ Found commented references to 'apps.patients' in settings.py:\n"
            + "\n".join(commented_patients) +
            "\n\nRemove these lines completely. "
            "See: docs/decisions/ADR-001-remove-legacy-patients-app.md"
        )
    
    def test_urls_file_has_no_commented_patients(self):
        """
        urls.py should not have commented references to apps.patients.
        
        URLs should be clean without legacy commented-out paths.
        """
        urls_file = Path(settings.BASE_DIR) / 'config' / 'urls.py'
        
        if not urls_file.exists():
            pytest.skip("config/urls.py not found")
        
        content = urls_file.read_text(encoding='utf-8')
        
        # Look for commented lines with patients URLs
        commented_patients_urls = [
            line.strip() for line in content.split('\n')
            if line.strip().startswith('#') and 'patients' in line.lower() and 'path(' in line
        ]
        
        assert not commented_patients_urls, (
            f"❌ Found commented patient URL patterns in config/urls.py:\n"
            + "\n".join(commented_patients_urls) +
            "\n\nRemove these lines completely. "
            "Patient endpoints are in apps.clinical.urls. "
            "See: docs/decisions/ADR-001-remove-legacy-patients-app.md"
        )


class TestPatientModelUnification:
    """
    Verify Patient model unification is complete and correct.
    
    Context: Patient model must only exist in apps.clinical, not in any legacy app.
    
    See: apps/api/UNIFICACION_PATIENT_REPORTE.md
    """
    
    def test_patient_model_only_in_clinical(self):
        """Patient model must only be defined in apps.clinical.models."""
        from django.apps import apps as django_apps
        
        patient_models = []
        
        for model in django_apps.get_models():
            if model.__name__ == 'Patient':
                app_label = model._meta.app_label
                module = model.__module__
                patient_models.append({
                    'app_label': app_label,
                    'module': module,
                    'full_name': f"{app_label}.{model.__name__}"
                })
        
        # Should only have ONE Patient model from clinical app
        assert len(patient_models) == 1, (
            f"❌ Expected exactly 1 Patient model (from apps.clinical), "
            f"but found {len(patient_models)}: {patient_models}"
        )
        
        clinical_patient = patient_models[0]
        assert clinical_patient['app_label'] == 'clinical', (
            f"❌ Patient model found in wrong app: {clinical_patient['app_label']}. "
            f"Must be in 'clinical' app only."
        )
        
        assert 'apps.clinical.models' in clinical_patient['module'], (
            f"❌ Patient model not in expected module. "
            f"Found: {clinical_patient['module']}, "
            f"Expected: apps.clinical.models"
        )
    
    def test_patient_model_uses_uuid_pk(self):
        """Canonical Patient model must use UUID primary key."""
        from apps.clinical.models import Patient
        
        pk_field = Patient._meta.pk
        
        assert pk_field.get_internal_type() == 'UUIDField', (
            f"❌ Patient primary key must be UUID. "
            f"Found: {pk_field.get_internal_type()}. "
            f"This indicates legacy model may have been reintroduced."
        )
    
    def test_patient_model_has_medical_fields(self):
        """
        Unified Patient model must have medical fields.
        
        This verifies the unification is complete (demographic + medical fields).
        """
        from apps.clinical.models import Patient
        
        medical_fields = ['blood_type', 'allergies', 'medical_history', 'current_medications']
        model_fields = [f.name for f in Patient._meta.get_fields()]
        
        missing_fields = [f for f in medical_fields if f not in model_fields]
        
        assert not missing_fields, (
            f"❌ Patient model missing medical fields: {missing_fields}. "
            f"Unification may be incomplete. "
            f"See: apps/api/UNIFICACION_PATIENT_REPORTE.md"
        )


class TestArchitecturalBoundaries:
    """
    Enforce architectural boundaries and prevent legacy patterns.
    
    These tests maintain clean architecture by preventing patterns that
    led to the apps.patients technical debt.
    """
    
    def test_no_duplicate_patient_models(self):
        """
        Prevent creation of duplicate Patient models in other apps.
        
        This is the core issue that led to technical debt.
        """
        from django.apps import apps as django_apps
        
        patient_like_models = []
        
        for model in django_apps.get_models():
            model_name = model.__name__.lower()
            if 'patient' in model_name and model_name != 'patient':
                # Allow PatientMergeLog, PatientGuardian, etc. (related models)
                continue
            
            if model.__name__ == 'Patient':
                patient_like_models.append({
                    'app': model._meta.app_label,
                    'name': model.__name__
                })
        
        # Should only have clinical.Patient
        assert len(patient_like_models) <= 1, (
            f"❌ Multiple Patient models detected: {patient_like_models}. "
            f"Only apps.clinical.models.Patient is allowed. "
            f"DO NOT create duplicate Patient models in other apps."
        )
    
    def test_no_orphaned_patients_migrations(self):
        """
        Ensure no orphaned 'patients' app migrations exist.
        
        Old migrations from apps.patients should not exist.
        """
        base_dir = Path(settings.BASE_DIR)
        apps_dir = base_dir / 'apps'
        
        if not apps_dir.exists():
            pytest.skip("apps/ directory not found")
        
        # Search for migrations directories named 'patients'
        orphaned_migrations = []
        
        for migrations_dir in apps_dir.rglob('migrations'):
            if migrations_dir.is_dir() and migrations_dir.parent.name == 'patients':
                orphaned_migrations.append(str(migrations_dir.relative_to(base_dir)))
        
        assert not orphaned_migrations, (
            f"❌ Found orphaned migrations for 'patients' app: {orphaned_migrations}. "
            f"These should be deleted. "
            f"See: docs/decisions/ADR-001-remove-legacy-patients-app.md"
        )


# Mark for easy identification
pytest.mark.architecture_hygiene = pytest.mark.architecture_hygiene
