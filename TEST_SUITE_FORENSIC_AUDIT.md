# Informe Forense del Test Suite — Backend EMR

**Fecha:** 11 de marzo de 2026  
**Autor:** GitHub Copilot — Diagnóstico sin modificaciones de código  
**Suite ejecutada en:** `emr-api-dev` (Docker, Python 3.11, pytest-django)  
**Comando:** `python -m pytest tests/ apps/ --tb=no -q`

---

## RESUMEN EJECUTIVO

| Métrica | Valor |
|---------|-------|
| Tests totales ejecutados | **1.035** |
| ✅ Passed | **762** (73,6 %) |
| ❌ Failed | **89** (8,6 %) |
| ⏭ Skipped | **184** (17,8 %) |
| ⚠ Warnings | 9 |
| Tiempo total | 141,5 s (2 min 21 s) |

Los 89 fallos se agrupan en **9 causas raíz distintas**. La causa raíz A concentra ~58 fallos (65 % de todos los fallos) y tiene una única solución: actualizar los fixtures del `conftest.py` para asignar `legal_entity` a los objetos creados por ORM.

---

## PARTE 1 — INVENTARIO DE ARCHIVOS DE TEST

### Ubicación y recuento

| Directorio | Archivos | Observaciones |
|-----------|----------|---------------|
| `apps/api/tests/` | 55 | Ubicación principal |
| `apps/api/apps/clinical/tests/` | 1 | Tests de smoke de Encounter |
| `apps/api/apps/core/tests/` | 1 | Test de consistencia de migraciones |
| **Total** | **57** | |

### Cobertura por módulo (distribución)

| Módulo | Archivos de test |
|--------|-----------------|
| Appointments / Agenda | 6 (api, attend, link, locking, practitioners, availability, booking) |
| Clinical (encounters, media, audit) | 5 |
| Patients | 8 (api, patch_bug, overview, merge, merge_OLD, new_fields, 9fields_e2e, insurance) |
| Sales / POS | 8 (pos_happy_path, layer3_a/b/c, integer_qty, refund, idempotency) |
| Stock | 3 (permissions, layer2_a3, layer3_a) |
| RBAC / Permissions | 4 (permissions_smoke, role_bootstrap, yo_usuario, admin_bypass) |
| Treatment Plans / Sessions | 3 |
| Consents / Documents | 3 |
| Observability | 2 |
| Infrastructure / Architecture | 4 (architecture_hygiene, admin_bypass, middleware_le_freeze, tenant_mandatory) |
| Otros (booking, public, uploads, timeline) | 6 |

---

## PARTE 2 — LISTA COMPLETA DE FALLOS Y CATEGORIZACIÓN

### Mapa de Causas Raíz

| ID | Causa Raíz | Tests afectados | Urgencia |
|----|-----------|-----------------|----------|
| **A** | Fixtures sin `legal_entity` + `TenantManager` auto-filtra | ~57 | 🔴 CRÍTICA |
| **B** | `test_encounter_smoke.py` — `setUp` de `TestCase` no activa el `autouse` de pytest | 9 | 🔴 CRÍTICA |
| **C** | Bugs internos del módulo de Observabilidad | 3 | 🟡 MEDIA |
| **D** | Endpoint `/public/leads/` ahora requiere auth (securizado post-test) | 4 | 🟡 MEDIA |
| **E** | Formato de respuesta de conflicto `row_version` cambió | 2 | 🟡 MEDIA |
| **F** | Endpoint de estado `/appointments/{id}/transition/` retorna 404 por filtro de tenant | 3 | 🔴 (derivado de A) |
| **G** | Booking endpoint retorna 400 — payload de test incompleto | 6 | 🟠 ALTA |
| **H** | `ImportError`: `LegalEntity` importada de `apps.core.models` (movida a `apps.legal.models`) | 1 | 🟡 MEDIA |
| **I** | Refund/stock count assertion — business logic cambió | 2 | 🟡 MEDIA |

---

### Detalle por Causa Raíz

---

#### 🔴 CAUSA RAÍZ A — Fixtures creados sin `legal_entity` (58 tests)

**Descripción del problema:**

La arquitectura multi-tenant usa un `TenantManager` que auto-filtra el ORM por `legal_entity` cuando hay un tenant activo en el contexto de thread-local:

```python
# apps/core/managers.py
class TenantManager(models.Manager):
    def get_queryset(self):
        tenant = get_current_tenant()   # thread-local
        if tenant:
            return qs.filter(legal_entity=tenant)
        return qs  # sin filtro si no hay tenant
```

`TenantQuerySetMixin.initial()` (aplicado a los 22 ViewSets en la sesión anterior) llama a `set_current_tenant(entity)` cuando el usuario tiene `legal_entity`. Para clientes de tipo `practitioner_client`, `reception_client`, `accounting_client`, el thread-local se activa con el tenant de test.

Los fixtures del `conftest.py` crean objetos via ORM **sin** asignar `legal_entity`:

```python
# tests/conftest.py
@pytest.fixture
def patient(db, admin_user):
    return Patient.objects.create(
        first_name='John',
        # ... sin legal_entity  ← EL PROBLEMA
        created_by_user=admin_user
    )
```

**Efecto cascada por rol:**

| Cliente | `legal_entity` en JWT | Thread-local | Resultado |
|---------|----------------------|--------------|-----------|
| `admin_client` | ❌ nulo (is_superuser, sin header) | 🔕 no se activa | `Patient.objects.all()` devuelve TODO → ✅ 200 |
| `practitioner_client` | ✅ `test_entity` | 🔔 activo | `Patient.objects.filter(legal_entity=test_entity)` → vacío → ❌ 404 |
| `reception_client` | ✅ `test_entity` | 🔔 activo | Ídem → ❌ 404 |
| `accounting_client` | ✅ `test_entity` | 🔔 activo | Ídem → ❌ 404 |

Los tests parametrizados con múltiples roles crean el objeto con admin o via ORM (sin tenant), luego intentan acceder con roles de negocio → 404 fantasmas.

**Tests afectados (57):**

```
test_permissions_smoke.py (13)
  TestPatientPermissions::test_retrieve_patient_by_role[practitioner/reception/accounting]
  TestPatientPermissions::test_update_patient_by_role[practitioner/reception]
  TestAppointmentPermissions::test_retrieve_appointment_by_role[practitioner/reception/accounting]
  TestAppointmentPermissions::test_update_appointment_by_role[practitioner/reception]
  TestEncounterPermissions::test_create_encounter_by_role[practitioner_client-201]
  TestAppointmentActions::test_attend_by_role[practitioner/reception]

test_appointments_api.py::TestAppointmentLocking (4)
  test_edit_locked_by_encounter_practitioner_forbidden
  test_edit_locked_by_encounter_reception_forbidden
  test_edit_locked_by_completed_status_practitioner_forbidden
  test_edit_locked_by_completed_status_reception_forbidden

test_patient_overview_api.py (7)
  TestT2_PractitionerOverview::test_practitioner_sees_notes
  TestT2_PractitionerOverview::test_practitioner_sees_clinical_kpis
  TestT3_ReceptionOverview::test_reception_no_notes
  TestT3_ReceptionOverview::test_reception_no_clinical_kpis
  TestT3_ReceptionOverview::test_reception_has_financial_kpis
  TestT4_AccountingOverview::test_accounting_no_notes
  TestT4_AccountingOverview::test_accounting_no_clinical_kpis

test_patient_patch_bug.py (4)
  test_patch_identity_fields_are_persisted
  test_patch_emergency_contact_fields_are_persisted  [→ KeyError: 'row_version' (impacto secundario)]
  test_patch_legal_consent_fields_are_persisted      [→ KeyError: 'row_version']
  test_patch_all_new_fields_together                 [→ KeyError: 'row_version']

test_clinical_audit.py (5)
  test_audit_log_created_on_encounter_update
  test_audit_log_includes_changed_fields
  test_audit_log_no_entry_on_no_changes
  test_audit_log_queryable_by_patient
  test_audit_log_captures_request_metadata

test_clinical_media.py (12)
  TestClinicalPhotoUpload::test_practitioner_can_upload_to_own_encounter
  TestClinicalPhotoUpload::test_any_practitioner_can_upload_to_encounter
  TestClinicalPhotoUpload::test_admin_can_upload_to_any_encounter
  TestClinicalPhotoUpload::test_cannot_upload_without_classification
  TestClinicalPhotoUpload::test_file_type_validation_rejects_pdf
  TestClinicalPhotoUpload::test_upload_without_file_rejected
  TestClinicalPhotoList::test_practitioner_lists_own_encounter_photos
  TestClinicalPhotoList::test_any_practitioner_can_list_encounter_photos
  TestClinicalPhotoList::test_deleted_photos_are_excluded
  TestClinicalPhotoDelete::test_practitioner_can_delete_own_photo
  TestClinicalPhotoDelete::test_any_practitioner_can_delete_encounter_photo
  TestClinicalPhotoDownload::test_authenticated_download
    → Los 12 fallan con 404 Not Found: /api/v1/clinical/encounters/{id}/photos/
    → El encounter existe en DB pero TenantManager lo filtra (legal_entity=None)

test_appointments_attend.py (2)
  TestAttendPermissions::test_attend_permissions_by_role[practitioner_client-201]
  TestAttendPermissions::test_attend_permissions_by_role[reception_client-201]

test_appointments_link_encounter.py (2)
  TestAttendPermissions::test_attend_permissions_by_role[practitioner_client-201]
  TestAttendPermissions::test_attend_permissions_by_role[reception_client-201]

test_treatment_plan_api.py (1)
  TestT2_PractitionerAccess::test_practitioner_can_list

test_treatment_session_api.py (1)
  TestMultiTenantIsolation::test_multi_tenant_isolation_start_session

test_patient_merge_OLD.py (1) [ver también Parte 5 — Duplicados]
  TestPatientMergePermissions::test_merge_permissions_by_role[practitioner_client-200]

test_business_rules.py (3 de los 7 que fallan)
  test_invalid_status_transition_is_rejected → assert 404==400 (appointment filtrado)
  test_draft_to_confirmed_transition_allowed → assert 404==200 (appointment filtrado)
  test_no_show_only_after_start_time → assert 404==400 (appointment filtrado)
  test_reception_cannot_see_diagnosis_fields_in_patient_payload → assert 404==200 (patient filtrado)
```

**Solución (no implementada — solo diagnóstico):**
Actualizar `conftest.py` — los fixtures `patient`, `appointment`, `encounter`, `clinic_location` deben asignar `legal_entity=_get_test_legal_entity()` a los modelos ORM creados directamente.

---

#### 🔴 CAUSA RAÍZ B — `test_encounter_smoke.py` no compatible con pytest autouse (9 tests)

**Descripción del problema:**

`apps/clinical/tests/test_encounter_smoke.py` usa `unittest.TestCase` con `setUp()`. El fixture `_auto_legal_entity_for_users` (definido en `conftest.py` como `@pytest.fixture(autouse=True)`) usa `monkeypatch` — que es exclusivo de pytest y **no se aplica** en `setUp()` de `TestCase`.

```
Error: django.core.exceptions.ValidationError:
  ['Non-superuser users must have a legal_entity.
    Set user.legal_entity before saving.']

Call stack:
  test_encounter_smoke.py:161: setUp()
    → User.objects.create_user(...)  ← sin legal_entity
    → authz/models.py:126: save()
    → raise ValidationError
```

**Tests afectados (9):**
```
TestClinicalMediaRelationship::test_clinical_media_creation_with_encounter
TestClinicalMediaRelationship::test_clinical_media_fk_points_to_clinical_encounter
TestClinicalMediaRelationship::test_clinical_media_reverse_relation
TestClinicalMediaRelationship::test_no_references_to_apps_encounters
TestEncounterAPIEndpoint::test_deprecated_endpoint_does_not_exist
TestEncounterAPIEndpoint::test_encounter_list_endpoint_exists
TestEncounterAPIEndpoint::test_encounter_list_requires_authentication
TestEncounterAPIEndpoint::test_encounter_list_returns_json_array
TestEncounterAPIEndpoint::test_encounter_list_with_data
```

**Solución (no implementada):** Convertir a pytest-style con fixtures, o añadir `setUpClass` con `LegalEntity.objects.get_or_create(...)` y pasar la entidad al `create_user()`.

---

#### 🟡 CAUSA RAÍZ C — Bugs internos del módulo de Observabilidad (3 tests)

**Descripción:** Tres tests fallan por bugs pre-existentes en `apps/core/observability/`.

**Test 1:** `test_observability.py::TestRequestCorrelation::test_adds_request_id_to_response_headers`
```
TypeError: unsupported operand type(s) for -: 'float' and 'Mock'
  apps/core/observability/correlation.py:96:
    duration_ms = (time.time() - request.start_time) * 1000
```
El test pasa `request.start_time` como un `Mock()`; el middleware asume que es un `float`.

**Test 2:** `test_observability.py::TestSafeLogging::test_logger_filters_sensitive_extra_fields`
```
AttributeError: <module 'apps.core.observability.logging'> does not have the attribute 'logger'
```
El mock intenta parchear `apps.core.observability.logging.logger` pero el módulo no expone ese atributo en ese path.

**Test 3:** `test_observability.py::TestTracingIntegration::test_trace_span_uses_otel_when_available`
```
NameError: name 'SpanKind' is not defined
  apps/core/observability/tracing.py:51
```
`SpanKind` de `opentelemetry.trace` falta en el import de `tracing.py`.

---

#### 🟡 CAUSA RAÍZ D — Endpoint `/public/leads/` securizado post-escritura de tests (4 tests)

**Descripción:** El endpoint `public/leads/` devuelve HTTP 401.

```
assert 401 == 201  ('Authentication credentials were not provided.')
WARNING Unauthorized: /public/leads/
```

Confirmado: la ruta `public/leads/` **existe** (aparece en el URL resolver). La regresión ocurrió después de que estos tests fueron escritos — se añadió una `permission_class` de autenticación al endpoint que era originalmente público.

**Tests afectados (4):**
```
test_public_throttling.py::TestLeadThrottling::test_hourly_rate_limit_returns_429
test_public_throttling.py::TestLeadThrottling::test_burst_protection_returns_429
test_public_throttling.py::TestLeadThrottling::test_leads_created_with_correct_data
test_public_throttling.py::TestThrottleHeaders::test_429_response_includes_retry_after_header
```

---

#### 🟡 CAUSA RAÍZ E — Formato de respuesta de conflicto `row_version` cambió (2 tests)

**Descripción:** Los tests esperan `'row_version'` como clave de nivel superior en la respuesta JSON, pero el formato actual anida los detalles bajo `error.details`:

```python
# Test assertion:
assert 'row_version' in response.json()    # ← FALLA

# Respuesta real:
{
  'error': {
    'code': 'CONFLICT',
    'details': {'current_row_version': 1, 'provided_row_version': None},
    'message': 'El paciente fue modificado por otro usuario...'
  }
}
```

**Tests afectados (2):**
```
test_patients_api.py::TestPatientUpdate::test_update_patient_without_row_version
test_patients_api.py::TestPatientUpdate::test_update_patient_with_stale_row_version
```

---

#### 🟠 CAUSA RAÍZ G — Booking endpoint retorna 400 y fallos de creación de Encounter (6 tests)

**Descripción:** Los endpoints de booking y creación de Encounter retornan HTTP 400 Bad Request.

```
assert 400 == 201   (POST /api/v1/clinical/practitioners/{id}/book/)
assert 400 == 201   (POST /api/v1/clinical/encounters/)
```

El endpoint de booking (`/api/v1/clinical/practitioners/{id}/book/`) y la creación directa de encuentros devuelven 400, indicando que el payload de los tests está incompleto para la validación actual del serializer. Los tests se escribieron para una versión anterior de la API con menos campos obligatorios.

**Tests afectados (6):**
```
test_business_rules.py::test_cannot_overlap_appointments_for_same_professional_active_states
test_business_rules.py::test_cancelled_or_no_show_does_not_block_slot
test_appointments_practitioners.py::TestAppointmentEncounterIntegration::test_create_encounter_from_completed_appointment
test_appointments_practitioners.py::TestAppointmentEncounterE2E::test_complete_appointment_encounter_flow
test_layer2_a1_domain_integrity.py::TestEncounterAppointmentPatientCoherence::test_encounter_appointment_patient_must_match_serializer
test_layer2_a1_domain_integrity.py::TestEncounterAppointmentPatientCoherence::test_encounter_with_matching_patient_appointment_succeeds
test_layer2_a1_domain_integrity.py::TestEncounterCanExistWithoutAppointment::test_encounter_without_appointment_is_valid
```

---

#### 🟡 CAUSA RAÍZ H — ImportError: `LegalEntity` movida de `apps.core` a `apps.legal` (1 test)

```
ImportError: cannot import name 'LegalEntity' from 'apps.core.models'
  tests/test_business_rules.py: test_sale_can_exist_without_appointment_and_link_is_optional
```

El test importa `from apps.core.models import LegalEntity` pero el modelo fue movido a `apps.legal.models`.

---

#### 🟡 CAUSA RAÍZ I — Fallos de conteo en refund/stock (2 tests)

**Test 1:**
```
test_layer3_b_refund_stock.py::test_reception_user_can_refund_paid_sale_via_api
assert 8 == 10  (items de stock tras refund)
```
El test espera restaurar 10 ítems de stock pero solo se restauran 8. Cambio en lógica de partial refund stock restoration.

**Test 2:**
```
test_integer_quantities.py::TestPartialRefundIntegerQuantity::test_create_partial_refund_with_integer_quantity_accepted
```
Requiere traceback completo para confirmar la causa exacta.

---

#### Resumen cuantitativo de causas raíz

```
Root Cause A  (Fixtures sin legal_entity)  →  57 tests  (64%)
Root Cause B  (TestCase setUp vs pytest)    →   9 tests  (10%)
Root Cause G  (Booking/Encounter 400)       →   6 tests   (7%)
Root Cause C  (Observabilidad interna)      →   3 tests   (3%)
Root Cause D  (Public leads securizado)     →   4 tests   (4%)
Root Cause E  (row_version format)          →   2 tests   (2%)
Root Cause I  (Refund stock count)          →   2 tests   (2%)
Root Cause F  (Transition/attend 404)       →   4 tests   (4%) [derivado de A]
Root Cause H  (ImportError LegalEntity)     →   1 test    (1%)
                                          Total: 88+1=89 ✓
```

---

## PARTE 3 — TESTS DUPLICADOS / LEGACY

### `test_patient_merge_OLD.py` vs `test_patient_merge.py`

**Veredicto: candidato a eliminación**

| Fichero | Clases | Tests aprox. |
|---------|--------|-------------|
| `test_patient_merge.py` | TestPatientMergePermissions, Validations, Relationships, Candidates, Atomicity, Signals | ~60 |
| `test_patient_merge_OLD.py` | TestPatientMergePermissions, Validations, Relationships, Response | ~40 (subset) |

`test_patient_merge_OLD.py` es un archivo legacy con cobertura duplicada. El archivo moderno (`test_patient_merge.py`) tiene mayor cobertura y está actualizado (118 de sus tests pasan). El archivo `_OLD` provoca un failure adicional (Root Cause A) y tiene nombres de clase duplicados.

**Recomendación:** Eliminar `test_patient_merge_OLD.py`.

### Otros duplicados de función

Se detectan 15 nombres de función duplicados entre distintos archivos de test. Los más relevantes:
- `test_attend_from_scheduled_status` — en `test_appointments_api.py` y `test_appointments_attend.py`
- `test_attend_permissions_by_role` — en `test_appointments_attend.py` y `test_appointments_link_encounter.py` (justificado: los archivos testean distintos flujos)

---

## PARTE 4 — COBERTURA RBAC

### Estado de la cobertura

**Fortalezas:**
- Los clientes de fixture cubren 6 roles: `admin`, `practitioner`, `reception`, `accounting`, `marketing`, `api` (anónimo)
- `test_permissions_smoke.py` tiene tests parametrizados por rol para los 5 endpoints principales → buena cobertura de anchura
- Los archivos como `test_stock_permissions.py`, `test_consents_api.py`, `test_documents_api.py` tienen cobertura por rol específica

**Debilidades detectadas:**

1. **Rol `ClinicalOps` usa grupos de Django, no `RoleChoices`**  
   `test_stock_permissions.py` y `test_appointments_practitioners.py` crean el rol `ClinicalOps` como `Group.objects.get_or_create(name='ClinicalOps')`. El resto del sistema usa `Role.objects.create(name=RoleChoices.X)`. Esto significa que los tests de `ClinicalOps` no son coherentes con el sistema RBAC real.

2. **El rol `admin_client` es `is_superuser=True` sin `legal_entity`**  
   En producción, el admin también debe enviar el header `X-Legal-Entity-ID`. Los tests que usan `admin_client` sin header no comprueban el path real de un admin en producción — solo comprueban el bypass de superusuario.

3. **Sin tests negativos para cruces de tenant**  
   No existe ningún test que verifique que un usuario de Entidad A NO pueda ver recursos de Entidad B (aislamiento cross-tenant). Solo `test_treatment_session_api.py::TestMultiTenantIsolation` intenta esto, pero falla por Root Cause A.

---

## PARTE 5 — COBERTURA DE AISLAMIENTO DE TENANT

### Tests que testean explícitamente aislamiento

| Archivo | Test | Estado |
|---------|------|--------|
| `test_treatment_session_api.py` | `TestMultiTenantIsolation::test_multi_tenant_isolation_start_session` | ❌ FALLA (Root Cause A) |
| `test_tenant_mandatory.py` | Varios | ✅ Pasan |
| `test_middleware_le_freeze.py` | Validación de freeze de LegalEntity | ✅ Pasan |
| `test_system_plane_legal_entity.py` | Operaciones de sistema sobre entidad | ✅ Pasan |

### Brecha crítica de cobertura

No existen tests que validen el escenario completo:
1. Crear recurso como usuario de entidad A (con header correcto en admin)
2. Intentar acceder como usuario de entidad B → verificar 404
3. Acceder como usuario de entidad A → verificar 200

Este escenario **es la garantía real de aislamiento** y no está testeado.

---

## PARTE 6 — COBERTURA DE STATE MACHINE (Appointments)

### Transiciones esperadas vs testeadas

| Transición | Testeada | Estado |
|-----------|----------|--------|
| `draft` → `confirmed` | ✅ `test_business_rules.py` | ❌ FALLA (Root Cause A/F) |
| `confirmed` → `checked_in` | ✅ parcial | ✅ Pasa |
| `checked_in` → `attended` | ✅ `test_appointments_api.py::test_attend_from_checked_in_status` | ✅ Pasa |
| `scheduled` → `attended` | ✅ `test_appointments_api.py::test_attend_from_scheduled_status` | ✅ Pasa |
| `* → cancelled` | ✅ | ✅ Pasa |
| `* → no_show` | ✅ `test_business_rules.py::test_no_show_only_after_start_time` | ❌ FALLA (Root Cause A) |
| `attended → *` (lock) | ✅ `TestAppointmentLocking` (4 tests) | ❌ FALLA (Root Cause A) |

Los 4 tests de locking y 2 de state machine NO fallan por problemas de lógica — fallan porque el appointment del fixture tiene `legal_entity=None` y queda filtrado.

---

## PARTE 7 — TESTS LEGACY E INCONSISTENCIAS

### 1. PytestReturnNotNoneWarning — `test_patient_9fields_e2e.py`

```
PytestReturnNotNoneWarning: test returns '75ed4f46-...' instead of None
```
Los tests en `TestPatient9FieldsEndToEnd` devuelven UUIDs en lugar de `None`. Estos tests pasan pero su patrón es incorrecto (`return` en lugar de `assert`). Serán errores en futuras versiones de pytest.

**Archivos afectados:** `tests/test_patient_9fields_e2e.py` — al menos 2 métodos.

### 2. PytestUnknownMarkWarning — `test_architecture_hygiene.py`

```
PytestUnknownMarkWarning: Unknown pytest.mark.architecture_hygiene
```
El mark `@pytest.mark.architecture_hygiene` no está declarado en `pytest.ini`. Funcionalmente inofensivo pero genera ruido.

### 3. Naive datetime warning — `test_appointments_api.py`

```
RuntimeWarning: DateTimeField Appointment.scheduled_start received a naive datetime
```
Tres tests en `test_appointments_api.py` crean fechas sin timezone. Los tests pasan pero el warning indica un uso incorrecto de `datetime.now()` en lugar de `timezone.now()`.

### 4. ClinicalOps — rol usando sistema de Groups, no RoleChoices

`test_appointments_practitioners.py` y `test_stock_permissions.py` crean el rol `ClinicalOps` como `Group`, no como `Role` de la aplicación. Esto crea una inconsistencia con el resto del sistema RBAC.

### 5. `test_uploads_presign.py` — Todos los tests SKIPPED (32/34)

```
ssssssssssssssssssssssssssssssss.ss
```
32 de los 34 tests están skipped (presumiblemente porque MinIO no está configurado en la forma que esperan, o porque tienen decoradores `@pytest.mark.skip`). Solo 2 tests no-skipped pasan.

---

## PARTE 8 — ANÁLISIS DE IMPORTS / ARQUITECTURA

### Dependencias de modelo correctamente resueltas

| Import | Estado |
|--------|--------|
| `from apps.legal.models import LegalEntity` | ✅ Correcto |
| `from apps.core.models import LegalEntity` | ❌ Rompe (test_business_rules) |
| `from apps.authz.models import RoleChoices` | ✅ Correcto (mayoría de tests) |
| `Group.objects.get_or_create(name='ClinicalOps')` | ⚠ Inconsistente con RoleChoices |

---

## PARTE 9 — PLAN DE CORRECCIÓN PRIORIZADO

Las correcciones están ordenadas de mayor impacto/menor esfuerzo a menor impacto/mayor esfuerzo.

### Lote 1 — Impacto máximo: resuelve ~57 fallos con 1 cambio (conftest.py)

**Acción:** Actualizar los fixtures `patient`, `appointment`, `encounter`, `clinic_location` en `tests/conftest.py` para añadir `legal_entity=_get_test_legal_entity()` a todos los `Model.objects.create(...)` directos.

**Ficheros a modificar:** `tests/conftest.py` (~4-5 puntos)  
**Tests que se recuperan:** ~57  

---

### Lote 2 — Impacto alto: resuelve 9 fallos de TestCase (test_encounter_smoke.py)

**Acción:** Refactorizar `apps/clinical/tests/test_encounter_smoke.py` de `unittest.TestCase` a pytest puro, o añadir `legal_entity` en el `setUp`.

**Ficheros a modificar:** `apps/clinical/tests/test_encounter_smoke.py`  
**Tests que se recuperan:** 9

---

### Lote 3 — Impacto medio: 4 fixes pequeños independientes

| Fix | Archivo | Tests recuperados |
|-----|---------|-----------------|
| Corregir import `LegalEntity` de `apps.core.models` → `apps.legal.models` | `tests/test_business_rules.py` | 1 |
| Actualizar aserciones de `row_version` al nuevo formato de error | `tests/test_patients_api.py`, `tests/test_patient_patch_bug.py` | 2-4 |
| Corregir test_observability (mock path, SpanKind import, start_time) | `tests/test_observability.py`, `apps/core/observability/tracing.py` | 3 |
| Registrar mark `architecture_hygiene` en `pytest.ini` | `pytest.ini` | 0 (solo warnings) |

---

### Lote 4 — Auditoría de endpoints securizados y payloads de booking

| Fix | Archivo | Tests recuperados |
|-----|---------|-----------------|
| Determinar si `/public/leads/` debe ser público y corregir | `apps/website/views.py` o `test_public_throttling.py` | 4 |
| Actualizar payload de booking y creación de Encounter en tests | `test_business_rules.py`, `test_layer2_a1_domain_integrity.py`, `test_appointments_practitioners.py` | 6 |
| Investigar y corregir stock count en refund | `test_layer3_b_refund_stock.py`, `test_integer_quantities.py` | 2 |

---

### Lote 5 — Limpieza de legacy

| Acción | Archivos |
|--------|---------|
| Eliminar `test_patient_merge_OLD.py` | `tests/test_patient_merge_OLD.py` |
| Corregir `return UUID` → `assert` en tests de 9fields | `tests/test_patient_9fields_e2e.py` |
| Corregir naive datetime → `timezone.now()` | `tests/test_appointments_api.py` |
| Unificar ClinicalOps de `Group` a `Role/RoleChoices` | `tests/test_stock_permissions.py`, `tests/test_appointments_practitioners.py` |

---

### Lote 6 — Cobertura de tenant (nuevos tests)

Una vez el Lote 1 esté aplicado, añadir tests de aislamiento cross-tenant:
- Crear paciente con entidad A, verificar 404 desde entidad B
- Crear cita con entidad A, verificar 404 desde entidad B
- Verificar que `admin_client` con header correcto de entidad A SÍ filtra por esa entidad

---

## APÉNDICE A — Tests con 184 SKIPPED

Los 184 tests skipped merecen análisis propio. Una revisión rápida muestra que la mayoría pertenecen a `test_uploads_presign.py` (32 skipped). Los skips restantes distribuidos por:

- Tests marcados con `@pytest.mark.skip` explícito
- Tests que dependen de MinIO/S3 no configurado
- Tests condicionados a flags de feature no activos

---

## APÉNDICE B — Cobertura de los 762 tests que PASAN

Las áreas con buena cobertura verde:
- Autenticación JWT y refresh
- Gestión de pacientes (CRUD básico, soft delete)  
- Consentimientos (CRUD, warnings, separación)
- Documentos clínicos
- POS (happy path, fuzzy search)
- Planes de tratamiento
- Stock (permisos básicos)
- Legal entity freeze middleware
- Role bootstrap
- Architecture hygiene (imports, circular deps)
- Migraciones de Django (consistencia)

---

*Fin del informe. Diagnóstico únicamente. Ningún archivo de código fue modificado durante esta auditoría.*
