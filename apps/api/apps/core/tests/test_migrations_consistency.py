"""
Global migrations consistency test.

PURPOSE:
Validates that ALL functional apps have up-to-date migrations.
No model changes should exist without corresponding migrations.

SCOPE:
All apps listed in PROJECT_MODEL_APPS (functional apps only).
Excludes technical apps, Django built-ins, and third-party libraries.

FAILURE:
If this test fails, it means there is model drift in one or more apps.
Run: python manage.py makemigrations <app_name> to fix.
"""
import subprocess
from io import StringIO

from django.core.management import call_command
from django.test import TestCase


# List of functional apps that must have consistent migrations
PROJECT_MODEL_APPS = [
    "clinical",
    "authz",
    "core",
    "documents",
    "photos",
    "legal",
    "products",
]


class MigrationsConsistencyTest(TestCase):
    """
    Test that all functional apps have migrations in sync with models.
    
    This is a GLOBAL test that validates the entire project's migration state.
    It is NOT specific to any single app.
    """
    
    def test_no_missing_migrations_in_any_app(self):
        """
        All functional apps must have migrations matching their models.
        
        This test uses makemigrations --check --dry-run to detect drift.
        If this fails, run: python manage.py makemigrations <app_name>
        """
        apps_with_drift = []
        
        for app_name in PROJECT_MODEL_APPS:
            # Capture output to check for "No changes detected"
            out = StringIO()
            
            try:
                # --check makes it exit with non-zero if changes needed
                # --dry-run prevents actually creating migrations
                call_command(
                    'makemigrations',
                    app_name,
                    '--check',
                    '--dry-run',
                    stdout=out,
                    stderr=out,
                )
            except SystemExit as e:
                # Non-zero exit = changes detected
                if e.code != 0:
                    apps_with_drift.append(app_name)
                    continue
        
        # Assert no apps have drift
        if apps_with_drift:
            self.fail(
                f"Model drift detected in apps: {', '.join(apps_with_drift)}. "
                f"Run 'python manage.py makemigrations <app>' to fix."
            )
    
    def test_all_project_apps_are_migrated(self):
        """
        Validates that migrations exist and are applied for all functional apps.
        """
        for app_name in PROJECT_MODEL_APPS:
            # Call showmigrations to ensure app has migrations
            out = StringIO()
            try:
                call_command(
                    'showmigrations',
                    app_name,
                    stdout=out,
                )
                output = out.getvalue()
                
                # Check output contains migration entries
                # If app has no migrations, Django shows: "<app_name>\n (no migrations)"
                self.assertNotIn(
                    '(no migrations)',
                    output,
                    f"App '{app_name}' has no migrations. Create initial migration."
                )
            except Exception as e:
                self.fail(f"Failed to check migrations for app '{app_name}': {e}")
