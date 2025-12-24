# IMPLEMENTACIÓN DE REGLAS DE NEGOCIO - RESUMEN

## 📋 Objetivo Completado

Se implementaron las 9 reglas de negocio de Capa 1 para el ERP de consultorio dermatológico, garantizando que el backend valide estas reglas incluso sin frontend.

---

## ✅ Reglas Implementadas

| # | Regla | Estado | Archivos Modificados |
|---|-------|--------|---------------------|
| 1 | Citas requieren paciente | ✅ | `models.py`, migración `0002` |
| 2 | No solapamientos por profesional | ✅ | `models.py`, `serializers.py` |
| 3 | Estados y transiciones permitidas | ✅ | `models.py`, `views.py` |
| 4 | no_show solo después de start_at | ✅ | `models.py` |
| 5 | Sin depósito/señal | ✅ | No se agregaron validaciones |
| 6 | Historia clínica editable | ✅ | Sin locking implementado |
| 7 | Fotos clínicas siempre permitidas | ✅ | Sin validación de consentimiento |
| 8 | Recepción no ve diagnósticos | ✅ | `permissions.py`, `serializers.py`, `views.py` |
| 9 | Venta-Cita relación opcional | ✅ | Verificado (sin cambios) |

---

## 📁 Archivos Modificados

### Modelos (`apps/clinical/models.py`)
**Cambios:**
- `AppointmentStatusChoices`: Actualizado de `(scheduled, confirmed, attended, no_show, cancelled)` a `(draft, confirmed, checked_in, completed, cancelled, no_show)`
- `Appointment.patient`: Cambiado de nullable a **required (NOT NULL)**
- **Nuevos métodos:**
  - `Appointment.clean()`: Valida patient required, time range, overlaps
  - `Appointment.transition_status()`: Valida transiciones de estado con reglas de negocio
  - `Appointment._check_practitioner_overlap()`: Detecta solapamientos en estados activos

**Líneas modificadas:** ~150 líneas agregadas

---

### Migración (`apps/clinical/migrations/0002_business_rules_*.py`)
**Cambios:**
- Migración de datos: `scheduled → draft`, `attended → completed`
- Schema change: `patient_id NOT NULL`
- Reverse migration incluida

**IMPORTANTE:** Requiere que todas las citas existentes tengan paciente asignado.

---

### Serializers (`apps/clinical/serializers.py`)
**Cambios:**
- `AppointmentWriteSerializer`:
  - `validate_status()`: Bloquea cambio directo de status en update (debe usar `/transition/`)
  - `validate_patient_id()`: Valida que patient es requerido
  - `validate()`: Llama a `instance.clean()` para validaciones de modelo
- `PatientDetailSerializer`:
  - `to_representation()`: Oculta campo `notes` para usuarios con rol Reception

**Líneas modificadas:** ~80 líneas agregadas/modificadas

---

### ViewSets (`apps/clinical/views.py`)
**Cambios:**
- `AppointmentViewSet`:
  - **Nuevo endpoint:** `POST /appointments/{id}/transition/`
  - Usa `transaction.atomic()` + `select_for_update()` para prevenir race conditions
  - Retorna 400 si transición es inválida

**Líneas modificadas:** ~65 líneas agregadas

---

### Permissions (`apps/clinical/permissions.py`)
**Cambios:**
- **Nueva clase:** `IsClinicalStaff`
  - Permite acceso solo a Admin y Practitioner
  - Bloquea explícitamente a Reception, Accounting, Marketing

**Líneas modificadas:** ~30 líneas agregadas

---

### Encounters ViewSet (`apps/encounters/views.py`)
**Cambios:**
- `EncounterViewSet.permission_classes`: Agregado `IsClinicalStaff`
- Reception ahora bloqueada de acceder a encounters

**Líneas modificadas:** ~10 líneas modificadas

---

### Photos ViewSet (`apps/photos/views.py`)
**Cambios:**
- `SkinPhotoViewSet.permission_classes`: Agregado `IsClinicalStaff`
- Reception ahora bloqueada de acceder a fotos clínicas

**Líneas modificadas:** ~10 líneas modificadas

---

### Tests (`apps/api/tests/test_business_rules.py`) ✨ NUEVO
**10 tests implementados:**
1. `test_cannot_create_appointment_without_patient`
2. `test_cannot_overlap_appointments_for_same_professional_active_states`
3. `test_cancelled_or_no_show_does_not_block_slot`
4. `test_invalid_status_transition_is_rejected`
5. `test_draft_to_confirmed_transition_allowed`
6. `test_no_show_only_after_start_time`
7. `test_reception_cannot_access_clinical_endpoints`
8. `test_reception_cannot_see_diagnosis_fields_in_patient_payload`
9. `test_sale_can_exist_without_appointment_and_link_is_optional`
10. `test_appointment_model_validates_patient_required`

**Líneas:** 380 líneas de tests

---

### Documentación (`docs/BUSINESS_RULES.md`) ✨ NUEVO
**Contenido:**
- Descripción detallada de cada regla
- Implementación técnica
- Endpoints afectados
- Códigos de error
- Notas de migración
- Decisiones de producto pendientes

**Líneas:** 450 líneas de documentación

---

## 🔧 Cambios Totales

| Métrica | Valor |
|---------|-------|
| Archivos modificados | 7 |
| Archivos nuevos | 3 |
| Líneas agregadas | ~1,100 |
| Tests nuevos | 10 |
| Endpoints nuevos | 1 (`/appointments/{id}/transition/`) |
| Migraciones | 1 |

---

## 🚀 Cómo Usar

### 1. Aplicar Migración
```bash
cd apps/api
python manage.py migrate clinical 0002
```

### 2. Ejecutar Tests
```bash
pytest tests/test_business_rules.py -v
```

### 3. Usar Nuevo Endpoint de Transición
```bash
# Transición de estado
POST /api/v1/appointments/{id}/transition/
{
  "status": "confirmed",
  "reason": "Motivo opcional"
}
```

### 4. Verificar Permisos
```bash
# Reception NO puede acceder a:
GET /api/v1/encounters/  # → 403 Forbidden
GET /api/v1/photos/      # → 403 Forbidden

# Reception SÍ puede acceder a:
GET /api/v1/patients/    # → 200 OK (sin campo 'notes')
GET /api/v1/appointments/ # → 200 OK
```

---

## 🎯 Validaciones Implementadas

### A Nivel de Modelo (Django)
- ✅ Patient required (`Appointment.clean()`)
- ✅ Time range validation (`scheduled_end > scheduled_start`)
- ✅ Overlap detection (`_check_practitioner_overlap()`)
- ✅ Status transition rules (`transition_status()`)

### A Nivel de Serializer (DRF)
- ✅ Patient required validation
- ✅ Status change blocked in update
- ✅ External ID uniqueness
- ✅ Field-level enum validation

### A Nivel de ViewSet (DRF)
- ✅ Transaction atomicity for transitions
- ✅ Row locking (`select_for_update()`)
- ✅ Permission-based access control

### A Nivel de Base de Datos
- ✅ NOT NULL constraint on `patient_id`
- ✅ UNIQUE constraint on `external_id`
- ✅ FK constraint on `patient → Patient`

---

## 🔐 Seguridad y Concurrencia

### Race Conditions Prevenidas
1. **Overlapping appointments:** 
   - `Appointment.clean()` + validación en serializer
   - Para mayor robustez: considerar PostgreSQL ExclusionConstraint

2. **Status transitions:**
   - `transaction.atomic()` + `select_for_update()`
   - Previene dos requests simultáneos cambiando estado

### Permisos por Rol
| Rol | Patients | Appointments | Encounters | Photos |
|-----|----------|--------------|------------|--------|
| Admin | Full | Full | Full | Full |
| Practitioner | Full | Full | Full | Full |
| Reception | Full (sin notes) | Full | ❌ Bloqueado | ❌ Bloqueado |
| Accounting | Read | Read | ❌ Bloqueado | ❌ Bloqueado |
| Marketing | ❌ Bloqueado | ❌ Bloqueado | ❌ Bloqueado | ❌ Bloqueado |

---

## ⚠️ IMPORTANTE: Notas de Migración

### Antes de Ejecutar Migración 0002:

1. **Backup de base de datos**
   ```bash
   pg_dump -U postgres -d cosmetica5 > backup_pre_migration.sql
   ```

2. **Verificar appointments sin paciente**
   ```sql
   SELECT COUNT(*) FROM appointment WHERE patient_id IS NULL;
   ```

3. **Si existen appointments huérfanas:**
   - Opción A: Crear paciente "Unknown" y asignar
   - Opción B: Soft-delete appointments sin paciente
   - Opción C: Cancelar migración y limpiar datos manualmente

4. **Ejecutar migración**
   ```bash
   python manage.py migrate clinical 0002
   ```

---

## 📊 Estado del Proyecto

### ✅ Completado
- [x] Modelo de datos actualizado
- [x] Validaciones de negocio implementadas
- [x] Endpoint de transición de estado
- [x] Permisos por rol (Reception bloqueado)
- [x] Tests de reglas de negocio (10 tests)
- [x] Documentación completa
- [x] Migración de datos

### 🔄 Opcional (Mejoras Futuras)
- [ ] PostgreSQL ExclusionConstraint para overlaps
- [ ] Django Simple History para auditoría completa
- [ ] Webhooks para Calendly
- [ ] Rate limiting en `/transition/`

---

## 📚 Documentación Relacionada

- **Reglas de negocio detalladas:** `docs/BUSINESS_RULES.md`
- **Modelo de dominio:** `docs/DOMAIN_MODEL.md`
- **Contratos de API:** `docs/API_CONTRACTS.md`
- **Tests:** `apps/api/tests/test_business_rules.py`

---

## 🤝 Contribuciones

**Implementado por:** GitHub Copilot (Senior Backend Engineer mode)  
**Fecha:** 15 de diciembre de 2025  
**Versión:** 1.0  
**Framework:** Django 4.2 + DRF + PostgreSQL

---

## 📝 Checklist de Implementación

- [x] Auditoría del código actual
- [x] Actualización de modelos
- [x] Creación de migraciones
- [x] Validaciones en serializers
- [x] Endpoint de transición de estado
- [x] Permisos clínicos por rol
- [x] Ocultamiento de campos clínicos
- [x] Suite de tests completa
- [x] Documentación exhaustiva
- [x] Commit y push a GitHub

---

## 🏛️ Legal and Fiscal Rules – Deferred by Design

### Context

The clinic is located in **France** and will need to issue legal invoices compliant with French regulations in the future. However, fiscal logic is **explicitly deferred** to avoid blocking current development.

### What IS Implemented (2025-12-22)

✅ **Legal Entity Master Data** (`apps.legal.models.LegalEntity`):
- Legal identification (raison sociale, nom commercial)
- Address fields (required for future invoices)
- French business identifiers (SIREN, SIRET, VAT number) as nullable fields
- Operational settings (currency EUR, timezone Europe/Paris)
- Relationship: `Sale.legal_entity` (ForeignKey, required)

**Purpose**: Single source of truth for "who issues the document"

### What is EXPLICITLY Not Implemented

❌ **Fiscal Calculation Rules**:
- TVA/VAT rates (20%, 10%, 5.5%, 0%)
- Tax exemptions for medical services (Article 261-4 CGI)
- Fiscal rate management by product/service type

❌ **Invoice Numbering Rules**:
- Sequential chronological numbering
- Gap detection and validation
- Fiscal year reset logic

❌ **Legal Invoice Generation**:
- PDF templates with legally required fields
- Invoice line items with TVA breakdown
- Total HT, TVA, TTC calculation
- Archiving for 10 years

❌ **French Compliance**:
- Electronic invoicing (Chorus Pro integration)
- Fiscal declarations (TVA, annual reports)
- Professional status validation
- Medical exemption eligibility checks

### Design Decision

**Rationale**: Separate "legal fact" (who issues) from "fiscal behavior" (how to calculate taxes).

**Benefits**:
1. **No Blocking**: Clinical and sales domains can advance without waiting for complex fiscal implementation
2. **Clean Architecture**: Legal entity data model separated from fiscal calculation engine
3. **Flexibility**: Can implement French fiscal rules when accountant requirements are clarified
4. **Prevent Refactoring**: Sale → LegalEntity relationship established now (avoids touching 1000+ sales later)

### When Fiscal Rules WILL Be Implemented

**Phase 2: Fiscal Logic** (future work, estimated 2-3 weeks):
- Create `apps.fiscal` module
- Implement `TaxRate` model with date-based rates
- Implement `TaxExemption` model with medical service rules
- Build `TaxCalculator` service with unit tests
- **Prerequisite**: Accountant meeting to clarify exemptions

**Phase 3: Legal Invoicing** (future work, estimated 3-4 weeks):
- Create `apps.invoicing` module
- Implement `InvoiceSequence` with gap detection
- Implement `Invoice` model with legally required fields
- Build PDF generator with approved template
- **Prerequisite**: Phase 2 complete + template design approval

### Documentation References

- **ADR-002**: `docs/decisions/ADR-002-legal-entity-minimal.md` (full architectural decision)
- **LEGAL_READINESS.md**: Implementation guide explaining what IS and IS NOT ready
- **STABILITY.md**: `docs/STABILITY.md` (Legal Layer section)
- **PROJECT_DECISIONS.md**: `docs/PROJECT_DECISIONS.md` (Currency Strategy, Data Immutability)

### Business Rule Summary

**Current State**:
- Every sale MUST reference a legal entity (enforced at DB level)
- Legal entity data can be managed via Django Admin
- NO fiscal calculations performed (intentional)

**Future State** (when Phase 2/3 implemented):
- Sales will generate legal invoices with TVA breakdown
- Invoice numbers will be sequential and chronological
- Medical services MAY be exempt from TVA (based on accountant input)
- Invoices will be archived for 10 years (French legal requirement)

---

## 💰 Currency and Financial Data Integrity

### Currency Snapshot Pattern

**Implementation**: All financial models (Proposal, Sale, Refund) include a `currency` field that captures the currency at transaction time.

**Why Snapshot Instead of Foreign Key?**

1. **Immutability**: Historical records must preserve currency at time of transaction
2. **Audit Trail**: Cannot be changed retroactively by changing legal entity configuration
3. **Data Independence**: Future currency changes don't cascade to past transactions
4. **Legal Compliance**: Financial records must be tamper-proof

**Example**:
```python
class Sale(models.Model):
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.PROTECT)
    currency = models.CharField(max_length=3, default='EUR')  # Snapshot
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    def save(self, *args, **kwargs):
        if not self.currency:
            self.currency = self.legal_entity.currency  # Capture at creation time
        super().save(*args, **kwargs)
```

**Current Implementation**:
- ✅ Currency field exists in Proposal, Sale, Refund models
- ✅ Default currency: EUR (system operates in France)
- ✅ Currency is immutable after record creation
- ✅ All financial calculations use Decimal for precision
- ❌ Multi-currency NOT supported (single-currency system: EUR only)

**Future Considerations** (NOT implemented):
- If multi-currency is activated, exchange rate would be stored alongside currency
- Base currency conversion would be required for aggregated reporting
- Currency validation would be added to API serializers

**See**: `docs/PROJECT_DECISIONS.md` - Currency Strategy for full architectural decision and rationale

---

**¡Implementación Completa! 🎉**

El backend ahora garantiza todas las reglas de negocio de Capa 1 sin depender del frontend.
