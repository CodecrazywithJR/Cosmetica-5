# Saneamiento Prioritario #1 — Evidence Pack

## A. Unified diff completo

```
$ git diff -- apps/api/apps/stock/models.py
```

```diff
diff --git a/apps/api/apps/stock/models.py b/apps/api/apps/stock/models.py
index cff589a..c94a2d1 100644
--- a/apps/api/apps/stock/models.py
+++ b/apps/api/apps/stock/models.py
@@ -15,6 +15,14 @@ from django.utils import timezone
 from decimal import Decimal
 import uuid
 
+from apps.core.tenant_model import TenantModel
+from apps.core.managers import TenantManager
+
+# Reusable verbose_name / FK reference constants (avoid S1192)
+LABEL_CREATED_AT = _('Created At')
+LABEL_UPDATED_AT = _('Updated At')
+FK_PRODUCT = 'products.Product'
+
 
 class StockLocationTypeChoices(models.TextChoices):
     """Location type choices."""
@@ -42,7 +50,7 @@ class StockMoveTypeChoices(models.TextChoices):
     TRANSFER_OUT = 'transfer_out', _('Transfer Out')
 
 
-class StockLocation(models.Model):
+class StockLocation(TenantModel):
     """
     Physical location where stock is stored.
     
@@ -60,8 +68,8 @@ class StockLocation(models.Model):
     )
     is_active = models.BooleanField(_('Active'), default=True)
     
-    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
-    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
+    created_at = models.DateTimeField(LABEL_CREATED_AT, auto_now_add=True)
+    updated_at = models.DateTimeField(LABEL_UPDATED_AT, auto_now=True)
     
     class Meta:
         db_table = 'stock_locations'
@@ -77,7 +85,7 @@ class StockLocation(models.Model):
         return f"{self.name} ({self.code})"
 
 
-class StockBatch(models.Model):
+class StockBatch(TenantModel):
     """
     Batch/Lot tracking for products with expiry dates.
     
@@ -89,7 +97,7 @@ class StockBatch(models.Model):
     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
     
     product = models.ForeignKey(
-        'products.Product',
+        FK_PRODUCT,
         on_delete=models.CASCADE,
         related_name='batches',
         verbose_name=_('Product')
@@ -117,8 +125,8 @@ class StockBatch(models.Model):
         help_text=_('Additional batch information (supplier, quality checks, etc.)')
     )
     
-    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
-    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
+    created_at = models.DateTimeField(LABEL_CREATED_AT, auto_now_add=True)
+    updated_at = models.DateTimeField(LABEL_UPDATED_AT, auto_now=True)
     
     class Meta:
         db_table = 'stock_batches'
@@ -167,7 +175,7 @@ class StockBatch(models.Model):
         return delta.days
 
 
-class StockMove(models.Model):
+class StockMove(TenantModel):
     """
     Stock movement - auditable transactions.
     
@@ -182,7 +190,7 @@ class StockMove(models.Model):
     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
     
     product = models.ForeignKey(
-        'products.Product',
+        FK_PRODUCT,
         on_delete=models.CASCADE,
         related_name='stock_moves',
         verbose_name=_('Product')
@@ -279,7 +287,7 @@ class StockMove(models.Model):
     
     reason = models.TextField(_('Reason'), blank=True)
     
-    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
+    created_at = models.DateTimeField(LABEL_CREATED_AT, auto_now_add=True)
     created_by = models.ForeignKey(
         settings.AUTH_USER_MODEL,
         on_delete=models.SET_NULL,
@@ -304,6 +312,17 @@ class StockMove(models.Model):
                 )
             self.full_clean()
         super().save(*args, **kwargs)
+
+    def delete(self, *args, **kwargs):
+        """
+        Block physical deletion of stock moves.
+
+        SECURITY: Stock movements are the financial and inventory audit trail.
+        Deleting a move would break StockOnHand consistency and cannot be undone.
+        """
+        raise ValidationError(
+            'Stock movements are immutable and cannot be deleted.'
+        )
     
     class Meta:
         db_table = 'stock_moves'
@@ -392,7 +411,7 @@ class StockMove(models.Model):
         return self.quantity < 0
 
 
-class StockOnHand(models.Model):
+class StockOnHand(TenantModel):
     """
     Current stock level per product/location/batch.
     
@@ -406,7 +425,7 @@ class StockOnHand(models.Model):
     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
     
     product = models.ForeignKey(
-        'products.Product',
+        FK_PRODUCT,
         on_delete=models.CASCADE,
         related_name='stock_on_hand',
         verbose_name=_('Product')
@@ -430,7 +449,7 @@ class StockOnHand(models.Model):
         help_text=_('Current available quantity')
     )
     
-    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
+    updated_at = models.DateTimeField(LABEL_UPDATED_AT, auto_now=True)
     
     class Meta:
         db_table = 'stock_on_hand'
```

**NOTA:** Este diff incluye TODOS los cambios no commiteados de `stock/models.py` (SonarQube Phase 2 + este fix). El cambio quirúrgico de este saneamiento son las 3 constantes L22-24 que pasaron de auto-referenciadas a literales. El resto son cambios previos del SonarQube Phase 2 que nunca se commitearon.

---

## B. Lista exacta de archivos tocados

- `/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/apps/api/apps/stock/models.py` — Corregir constantes auto-referenciadas en líneas 22-24 (LABEL_CREATED_AT, LABEL_UPDATED_AT, FK_PRODUCT) para eliminar NameError bloqueante

---

## C. Output real de comandos

### C.1 git diff --name-only

```
$ git diff --name-only
```

```
Makefile
PROJECT_DECISIONS.md
apps/api/apps/authz/management/commands/ensure_demo_user_roles.py
apps/api/apps/authz/migrations/0007_system_plane_legal_entity.py
apps/api/apps/authz/models.py
apps/api/apps/authz/permissions.py
apps/api/apps/authz/serializers.py
apps/api/apps/authz/serializers_users.py
apps/api/apps/authz/views.py
apps/api/apps/authz/views_users.py
apps/api/apps/clinical/admin.py
apps/api/apps/clinical/attachment_counters.py
apps/api/apps/clinical/management/commands/recalc_encounter_attachment_counters.py
apps/api/apps/clinical/models.py
apps/api/apps/clinical/permissions.py
apps/api/apps/clinical/serializers.py
apps/api/apps/clinical/serializers_proposals.py
apps/api/apps/clinical/services.py
apps/api/apps/clinical/tests/test_encounter_smoke.py
apps/api/apps/clinical/urls.py
apps/api/apps/clinical/utils_storage.py
apps/api/apps/clinical/views.py
apps/api/apps/clinical/views_consents.py
apps/api/apps/clinical/views_documents.py
apps/api/apps/clinical/views_photos.py
apps/api/apps/core/admin.py
apps/api/apps/core/management/commands/bootstrap_dev_users.py
apps/api/apps/core/middleware.py
apps/api/apps/core/models.py
apps/api/apps/core/observability/correlation.py
apps/api/apps/core/observability/tracing.py
apps/api/apps/core/serializers.py
apps/api/apps/core/urls.py
apps/api/apps/core/views.py
apps/api/apps/documents/models.py
apps/api/apps/integrations/urls.py
apps/api/apps/integrations/views.py
apps/api/apps/legal/migrations/0003_system_plane_legal_entity.py
apps/api/apps/legal/models.py
apps/api/apps/legal/serializers.py
apps/api/apps/legal/urls.py
apps/api/apps/legal/views.py
apps/api/apps/ops/admin.py
apps/api/apps/ops/models.py
apps/api/apps/photos/models.py
apps/api/apps/photos/views.py
apps/api/apps/pos/permissions.py
apps/api/apps/products/models.py
apps/api/apps/products/views.py
apps/api/apps/sales/admin.py
apps/api/apps/sales/models.py
apps/api/apps/sales/permissions.py
apps/api/apps/sales/services.py
apps/api/apps/sales/views.py
apps/api/apps/social/views.py
apps/api/apps/stock/management/commands/create_stock_groups.py
apps/api/apps/stock/models.py
apps/api/apps/stock/permissions.py
apps/api/apps/stock/views.py
apps/api/apps/website/views.py
apps/api/config/settings.py
apps/api/config/urls.py
apps/api/tests/conftest.py
apps/api/tests/test_admin_bypass_protection.py
apps/api/tests/test_appointment_creation_blocked.py
apps/api/tests/test_appointments_api.py
apps/api/tests/test_appointments_attend.py
apps/api/tests/test_appointments_link_encounter.py
apps/api/tests/test_appointments_practitioners.py
apps/api/tests/test_availability.py
apps/api/tests/test_booking.py
apps/api/tests/test_business_rules.py
apps/api/tests/test_calendly_webhook.py
apps/api/tests/test_clinical_audit.py
apps/api/tests/test_clinical_media.py
apps/api/tests/test_clinical_sales_integration.py
apps/api/tests/test_consents_api.py
apps/api/tests/test_encounter_cleanup.py
apps/api/tests/test_encounters_api.py
apps/api/tests/test_integer_quantities.py
apps/api/tests/test_layer2_a1_domain_integrity.py
apps/api/tests/test_layer2_a2_sales_integrity.py
apps/api/tests/test_layer3_a_sales_stock.py
apps/api/tests/test_layer3_b_refund_stock.py
apps/api/tests/test_layer3_c_partial_refund.py
apps/api/tests/test_observability.py
apps/api/tests/test_observability_flows.py
apps/api/tests/test_patient_merge.py
apps/api/tests/test_patient_merge_OLD.py
apps/api/tests/test_patient_patch_bug.py
apps/api/tests/test_patients_api.py
apps/api/tests/test_permissions_smoke.py
apps/api/tests/test_pos_happy_path.py
apps/api/tests/test_pos_patient_fuzzy_search.py
apps/api/tests/test_public_throttling.py
apps/api/tests/test_refund_failure_rollback.py
apps/api/tests/test_refund_idempotency.py
apps/api/tests/test_role_bootstrap.py
apps/api/tests/test_stock_permissions.py
apps/api/tests/test_tenant_mandatory.py
apps/api/tests/test_timeline_api.py
apps/api/tests/test_user_profile_api.py
apps/api/tests/test_yo_usuario.py
apps/api/update_user_email.py
apps/web/messages/en.json
apps/web/messages/es.json
apps/web/messages/fr.json
apps/web/messages/hy.json
apps/web/messages/ru.json
apps/web/messages/uk.json
apps/web/src/app/[locale]/admin/users/[id]/edit/page.tsx
apps/web/src/app/[locale]/admin/users/new/page.tsx
apps/web/src/app/[locale]/booking/page.tsx
apps/web/src/app/[locale]/debug/auth/page.tsx
apps/web/src/app/[locale]/encounters/[id]/page.tsx
apps/web/src/app/[locale]/globals.css
apps/web/src/app/[locale]/page.tsx
apps/web/src/app/[locale]/patients/[id]/layout.tsx
apps/web/src/app/[locale]/patients/page.tsx
apps/web/src/app/[locale]/proposals/page.tsx
apps/web/src/app/[locale]/schedule/page.tsx
apps/web/src/app/globals.css
apps/web/src/components/calendly-embed.tsx
apps/web/src/components/calendly-not-configured.tsx
apps/web/src/components/layout/app-layout.tsx
apps/web/src/components/legal-entity-selector.tsx
apps/web/src/components/superuser-header-bar.tsx
apps/web/src/components/system-plane-guard.tsx
apps/web/src/lib/active-legal-entity-context.tsx
apps/web/src/lib/api-client.ts
apps/web/src/lib/api/api-client.ts
apps/web/src/lib/auth-context.tsx
apps/web/src/lib/hooks/use-attachments.ts
apps/web/src/lib/hooks/use-calendly-config.ts
apps/web/src/lib/hooks/use-encounters.ts
apps/web/src/lib/hooks/use-proposals.ts
apps/web/src/lib/providers.tsx
apps/web/src/lib/routing.ts
apps/web/src/lib/types.ts
conftest.py
docs/ALERTING.md
docs/API_CONTRACTS.md
docs/ARCHITECTURE.md
docs/AUDIT_SECURITY.md
docs/BACKUP_STRATEGY.md
docs/BUSINESS_RULES.md
docs/DOMAIN_MODEL.md
docs/FRONTEND_I18N.md
docs/OBSERVABILITY_DASHBOARDS.md
docs/PROJECT_DECISIONS.md
docs/RUNBOOK.md
docs/SLO.md
docs/decisions/ADR-001-remove-legacy-patients-app.md
docs/decisions/ADR-002-legal-entity-minimal.md
docs/decisions/ADR-003-clinical-core-v1.md
docs/decisions/ADR-004-appointments-practitioner.md
scripts/demo_admin_user_creation.py
tests/test_availability.py
tests/test_booking.py
tests/test_clinical_core.py
tests/test_patient_patch_bug.py
```

**Qué demuestra:** `apps/api/apps/stock/models.py` aparece en la lista. Los demás son cambios previos no commiteados (SonarQube Phase 2, frontend, docs).

---

### C.2 cd apps/api && python3 -m pytest --co -q

```
$ cd apps/api && python3 -m pytest --co -q
```

```
tests/test_appointments_api.py: 31
tests/test_appointments_attend.py: 20
tests/test_appointments_link_encounter.py: 28
tests/test_appointments_practitioners.py: 13
tests/test_architecture_hygiene.py: 10
tests/test_audit_log.py: 15
tests/test_availability.py: 9
tests/test_clinical_sales_integration.py: 25
tests/test_consents_api.py: 37
tests/test_documents_api.py: 44
tests/test_encounters_api.py: 30
tests/test_layer2_a3_stock_batch_expiry.py: 25
tests/test_layer3_c_partial_refund.py: 10
tests/test_middleware_le_freeze.py: 18
tests/test_observability.py: 30
tests/test_patient_9fields_e2e.py: 7
tests/test_patient_insurance_api.py: 18
tests/test_patient_merge_OLD.py: 19
tests/test_patient_new_fields.py: 10
tests/test_patients_api.py: 25
tests/test_permissions_smoke.py: 73
tests/test_photos_api.py: 34
tests/test_proposal_state_machine.py: 26
tests/test_system_plane_legal_entity.py: 30
tests/test_tenant_mandatory.py: 16
tests/test_timeline_api.py: 23
tests/test_treatment_plan.py: 24
tests/test_treatment_plan_api.py: 13
tests/test_treatment_session_api.py: 40
tests/test_uploads_presign.py: 35
tests/test_user_profile_api.py: 9
tests/test_yo_usuario.py: 2

==================================== ERRORS ====================================
[... 24 bloques de error idénticos, todos IndentationError: unexpected indent ...]

=========================== short test summary info ============================
ERROR tests/test_admin_bypass_protection.py
ERROR tests/test_booking.py
ERROR tests/test_business_rules.py
ERROR tests/test_clinical_audit.py
ERROR tests/test_clinical_media.py
ERROR tests/test_encounter_cleanup.py
ERROR tests/test_integer_quantities.py
ERROR tests/test_layer2_a1_domain_integrity.py
ERROR tests/test_layer2_a2_sales_integrity.py
ERROR tests/test_layer3_a_sales_stock.py
ERROR tests/test_layer3_b_refund_stock.py
ERROR tests/test_observability_flows.py
ERROR tests/test_patient_merge.py
ERROR tests/test_patient_overview_api.py
ERROR tests/test_patient_patch_bug.py
ERROR tests/test_pos_happy_path.py
ERROR tests/test_pos_patient_fuzzy_search.py
ERROR tests/test_public_booking.py
ERROR tests/test_public_throttling.py
ERROR tests/test_refund_failure_rollback.py
ERROR tests/test_refund_idempotency.py
ERROR tests/test_role_bootstrap.py
ERROR tests/test_skin_photo_soft_deleted_patient.py
ERROR tests/test_stock_permissions.py
!!!!!!!!!!!!!!!!!!! Interrupted: 24 errors during collection !!!!!!!!!!!!!!!!!!!
exit:2
```

**Qué demuestra:** 32 archivos coleccionados correctamente (749 tests). 24 archivos con `IndentationError: unexpected indent` preexistente. El `NameError: name 'LABEL_CREATED_AT' is not defined` ya NO aparece.

---

### C.3 cd apps/api && python3 manage.py check

```
$ cd apps/api && python3 manage.py check
```

```
prometheus_client not available, using no-op metrics
/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl' module is compiled with 'LibreSSL 2.8.3'. See: https://github.com/urllib3/urllib3/issues/3020
  warnings.warn(
Traceback (most recent call last):
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/apps/api/manage.py", line 22, in <module>
    main()
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/apps/api/manage.py", line 18, in main
    execute_from_command_line(sys.argv)
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/core/management/__init__.py", line 442, in execute_from_command_line
    utility.execute()
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/core/management/__init__.py", line 436, in execute
    self.fetch_command(subcommand).run_from_argv(self.argv)
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/core/management/base.py", line 412, in run_from_argv
    self.execute(*args, **cmd_options)
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/core/management/base.py", line 458, in execute
    output = self.handle(*args, **options)
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/core/management/commands/check.py", line 76, in handle
    self.check(
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/core/management/base.py", line 485, in check
    all_issues = checks.run_checks(
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/core/checks/registry.py", line 88, in run_checks
    new_errors = check(app_configs=app_configs, databases=databases)
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/core/checks/urls.py", line 14, in check_url_config
    return check_resolver(resolver)
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/core/checks/urls.py", line 24, in check_resolver
    return check_method()
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/urls/resolvers.py", line 494, in check
    for pattern in self.url_patterns:
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/utils/functional.py", line 57, in __get__
    res = instance.__dict__[self.name] = self.func(instance)
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/urls/resolvers.py", line 715, in url_patterns
    patterns = getattr(self.urlconf_module, "urlpatterns", self.urlconf_module)
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/utils/functional.py", line 57, in __get__
    res = instance.__dict__[self.name] = self.func(instance)
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/urls/resolvers.py", line 708, in urlconf_module
    return import_module(self.urlconf_name)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/importlib/__init__.py", line 127, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
  File "<frozen importlib._bootstrap>", line 1030, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1007, in _find_and_load
  File "<frozen importlib._bootstrap>", line 986, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 680, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 850, in exec_module
  File "<frozen importlib._bootstrap>", line 228, in _call_with_frames_removed
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/apps/api/config/urls.py", line 30, in <module>
    path('api/v1/clinical/', include('apps.clinical.urls')),  # Clinical API (patients, appointments, encounters, treatments)
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/urls/conf.py", line 38, in include
    urlconf_module = import_module(urlconf_module)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/importlib/__init__.py", line 127, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
  File "<frozen importlib._bootstrap>", line 1030, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1007, in _find_and_load
  File "<frozen importlib._bootstrap>", line 986, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 680, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 850, in exec_module
  File "<frozen importlib._bootstrap>", line 228, in _call_with_frames_removed
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/apps/api/apps/clinical/urls.py", line 7, in <module>
    from .views import (
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/apps/api/apps/clinical/views.py", line 56, in <module>
    from apps.core.audit import log_clinical_access
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/apps/api/apps/core/audit.py", line 25, in <module>
    def _get_client_ip(request) -> str | None:
TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
exit:1
```

**Qué demuestra:** `manage.py check` falla por `TypeError` en `core/audit.py:25` — sintaxis `str | None` de Python 3.10+ en Python 3.9. Problema preexistente, NO causado por este fix. El error original `NameError: name 'LABEL_CREATED_AT'` ya NO aparece.

---

### C.4 cd apps/api && python3 manage.py showmigrations --plan

```
$ cd apps/api && python3 manage.py showmigrations --plan
```

```
prometheus_client not available, using no-op metrics
/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/urllib3/__init__.py:35: NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl' module is compiled with 'LibreSSL 2.8.3'. See: https://github.com/urllib3/urllib3/issues/3020
  warnings.warn(
Traceback (most recent call last):
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/apps/api/manage.py", line 22, in <module>
    main()
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/apps/api/manage.py", line 18, in main
    execute_from_command_line(sys.argv)
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/core/management/__init__.py", line 442, in execute_from_command_line
    utility.execute()
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/core/management/__init__.py", line 436, in execute
    self.fetch_command(subcommand).run_from_argv(self.argv)
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/core/management/base.py", line 412, in run_from_argv
    self.execute(*args, **cmd_options)
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/core/management/base.py", line 453, in execute
    self.check()
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/core/management/base.py", line 485, in check
    all_issues = checks.run_checks(
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/core/checks/registry.py", line 88, in run_checks
    new_errors = check(app_configs=app_configs, databases=databases)
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/core/checks/urls.py", line 14, in check_url_config
    return check_resolver(resolver)
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/core/checks/urls.py", line 24, in check_resolver
    return check_method()
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/urls/resolvers.py", line 494, in check
    for pattern in self.url_patterns:
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/utils/functional.py", line 57, in __get__
    res = instance.__dict__[self.name] = self.func(instance)
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/urls/resolvers.py", line 715, in url_patterns
    patterns = getattr(self.urlconf_module, "urlpatterns", self.urlconf_module)
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/utils/functional.py", line 57, in __get__
    res = instance.__dict__[self.name] = self.func(instance)
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/urls/resolvers.py", line 708, in urlconf_module
    return import_module(self.urlconf_name)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/importlib/__init__.py", line 127, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
  File "<frozen importlib._bootstrap>", line 1030, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1007, in _find_and_load
  File "<frozen importlib._bootstrap>", line 986, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 680, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 850, in exec_module
  File "<frozen importlib._bootstrap>", line 228, in _call_with_frames_removed
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/apps/api/config/urls.py", line 30, in <module>
    path('api/v1/clinical/', include('apps.clinical.urls')),  # Clinical API (patients, appointments, encounters, treatments)
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/.venv/lib/python3.9/site-packages/django/urls/conf.py", line 38, in include
    urlconf_module = import_module(urlconf_module)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/importlib/__init__.py", line 127, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
  File "<frozen importlib._bootstrap>", line 1030, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1007, in _find_and_load
  File "<frozen importlib._bootstrap>", line 986, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 680, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 850, in exec_module
  File "<frozen importlib._bootstrap>", line 228, in _call_with_frames_removed
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/apps/api/apps/clinical/urls.py", line 7, in <module>
    from .views import (
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/apps/api/apps/clinical/views.py", line 56, in <module>
    from apps.core.audit import log_clinical_access
  File "/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/apps/api/apps/core/audit.py", line 25, in <module>
    def _get_client_ip(request) -> str | None:
TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
exit:1
```

**Qué demuestra:** `manage.py showmigrations --plan` falla con el mismo `TypeError` de `core/audit.py:25`. Mismo problema preexistente que C.3. NO es el NameError original.

---

### C.5 cd apps/api && python3 -c "import django; import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); print('Django setup OK')"

```
prometheus_client not available, using no-op metrics
Django setup OK
```

**Qué demuestra:** `django.setup()` completa sin error. `apps.populate(INSTALLED_APPS)` carga todos los 17 apps incluyendo `stock.models`. El NameError original está eliminado.
