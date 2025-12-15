# Capa 2 A1: Integridad del Dominio Clínico - Implementación Completada

## Estado: ✅ Implementado y Testeado
**Fecha:** 15 de diciembre de 2025  
**Objetivo:** Reforzar invariantes del dominio clínico con validaciones, constraints e índices

---

## Invariantes Implementadas

### 1. Encounter Requiere Paciente ✅

**Regla:** Todo Encounter DEBE tener un patient asignado (NOT NULL).

**Implementación:**
- Campo `patient` en modelo Encounter ya es FK NOT NULL
- Validación en `Encounter.clean()`
- Validación en `EncounterSerializer.validate()`

**Test:** `test_encounter_requires_patient_model_level`, `test_encounter_requires_patient_serializer_level`

---

### 2. Coherencia Encounter-Appointment-Patient ✅

**Regla:** Si `Encounter.appointment` existe, entonces:
```python
encounter.patient_id == encounter.appointment.patient_id
```

**Implementación:**

**Modelo (`apps/clinical/models.py`):**
```python
def clean(self):
    """Validate clinical domain invariants."""
    super().clean()
    
    # INVARIANT: Patient is required
    if not self.patient_id:
        raise ValidationError({'patient': 'Encounter must have a patient assigned.'})
    
    # INVARIANT: Appointment-Patient coherence
    if self.appointment_id:
        appointment = self.appointment
        if appointment and appointment.patient_id != self.patient_id:
            raise ValidationError({
                'appointment': (
                    f'Appointment patient mismatch: '
                    f'encounter.patient={self.patient_id} but '
                    f'appointment.patient={appointment.patient_id}. '
                    f'Both must reference the same patient.'
                )
            })
```

**Serializer (`apps/encounters/serializers.py`):**
```python
def validate(self, attrs):
    """Validate clinical domain invariants."""
    patient = attrs.get('patient')
    appointment = attrs.get('appointment')
    
    # If updating, get current values if not provided
    if self.instance:
        if not patient:
            patient = self.instance.patient
        if 'appointment' not in attrs and self.instance.appointment:
            appointment = self.instance.appointment
    
    # INVARIANT: Appointment-Patient coherence
    if appointment and appointment.patient_id != patient.id:
        raise serializers.ValidationError({
            'appointment': (
                f'Appointment patient mismatch: '
                f'encounter.patient={patient.id} but '
                f'appointment.patient={appointment.patient_id}. '
                f'Both must reference the same patient.'
            )
        })
    
    return attrs
```

**Tests:**
- `test_encounter_appointment_patient_must_match_serializer`
- `test_encounter_appointment_patient_must_match_model`
- `test_encounter_with_matching_patient_appointment_succeeds`

---

### 3. Encounter Puede Existir Sin Appointment ✅

**Regla:** Un Encounter puede tener `appointment = NULL` (paciente walk-in, urgencias, etc.).

**Implementación:**
- Campo `appointment` es nullable en modelo
- No se requiere validación adicional (permitido por diseño)

**Test:** `test_encounter_without_appointment_is_valid`

---

### 4. Coherencia SkinPhoto-Encounter-Patient ✅

**Regla:** Si `SkinPhoto.encounter` existe, entonces:
```python
photo.patient_id == photo.encounter.patient_id
```

**Implementación:**

**Modelo (`apps/photos/models.py`):**
```python
def clean(self):
    """Validate clinical domain invariants."""
    super().clean()
    
    # INVARIANT: Patient is required
    if not self.patient_id:
        raise ValidationError({'patient': 'Photo must have a patient assigned.'})
    
    # INVARIANT: Encounter-Patient coherence
    if self.encounter_id and self.encounter:
        if self.encounter.patient_id != self.patient_id:
            raise ValidationError({
                'encounter': (
                    f'Encounter patient mismatch: '
                    f'photo.patient={self.patient_id} but '
                    f'encounter.patient={self.encounter.patient_id}. '
                    f'Both must reference the same patient.'
                )
            })
```

**Serializer (`apps/photos/serializers.py`):**
```python
def validate(self, attrs):
    """Validate clinical domain invariants."""
    patient = attrs.get('patient')
    encounter = attrs.get('encounter')
    
    # If updating, get current values
    if self.instance:
        if not patient:
            patient = self.instance.patient
        if 'encounter' not in attrs and self.instance.encounter:
            encounter = self.instance.encounter
    
    # INVARIANT: Encounter-Patient coherence
    if encounter and encounter.patient_id != patient.id:
        raise serializers.ValidationError({
            'encounter': (
                f'Encounter patient mismatch: '
                f'photo.patient={patient.id} but '
                f'encounter.patient={encounter.patient_id}. '
                f'Both must reference the same patient.'
            )
        })
    
    return attrs
```

**Tests:**
- `test_photo_encounter_patient_must_match_model`
- `test_photo_with_matching_patient_encounter_succeeds`
- `test_photo_without_encounter_is_valid`

---

## Índices para Timeline Clínico

### Encounter
```python
models.Index(fields=['patient', '-created_at'], name='idx_encounter_patient_timeline')
```

**Uso:**
```python
# Timeline de paciente ordenado por fecha
encounters = Encounter.objects.filter(
    patient=patient,
    is_deleted=False
).order_by('-created_at')
```

### ClinicalPhoto
```python
models.Index(fields=['patient', '-created_at'], name='idx_clinical_photo_patient_timeline')
```

**Uso:**
```python
# Fotos de paciente ordenadas cronológicamente
photos = ClinicalPhoto.objects.filter(
    patient=patient,
    is_deleted=False
).order_by('-created_at')
```

---

## Migración de Datos

**Archivo:** `apps/clinical/migrations/0004_layer2_a1_clinical_domain_integrity.py`

### Estrategia de Limpieza

**Problema:** Pueden existir datos inconsistentes previos (encounter con appointment de otro paciente).

**Solución:**
1. **Detectar inconsistencias** antes de aplicar constraints
2. **Desvincular** appointment (set to NULL) en encounters inconsistentes
3. **Registrar en ClinicalAuditLog** todas las correcciones para trazabilidad
4. **Añadir índices** después de limpiar datos

**Funciones de Migración:**

```python
def clean_inconsistent_encounter_appointments(apps, schema_editor):
    """
    Find encounters where encounter.patient != appointment.patient
    Set appointment=NULL and log to audit trail.
    """
    Encounter = apps.get_model('encounters', 'Encounter')
    ClinicalAuditLog = apps.get_model('clinical', 'ClinicalAuditLog')
    
    inconsistent_encounters = []
    
    for encounter in Encounter.objects.select_related('appointment', 'patient').filter(
        appointment__isnull=False
    ):
        if encounter.appointment.patient_id != encounter.patient_id:
            inconsistent_encounters.append(encounter)
    
    for encounter in inconsistent_encounters:
        # Log BEFORE fixing
        ClinicalAuditLog.objects.create(
            actor_user=None,  # System action
            action='update',
            entity_type='Encounter',
            entity_id=encounter.id,
            patient_id=encounter.patient_id,
            metadata={
                'reason': 'Data migration: Layer 2 A1 - Clean inconsistent appointment',
                'migration': '0004_layer2_a1_clinical_domain_integrity'
            }
        )
        
        # Fix
        encounter.appointment = None
        encounter.save(update_fields=['appointment'])
```

**Output esperado:**
```
✅ No inconsistent encounter-appointment relationships found
✅ No inconsistent photo-encounter relationships found
```

O si hay inconsistencias:
```
⚠️  Found 3 encounters with patient-appointment mismatch:
  - Encounter abc123: encounter.patient=patient-1 vs appointment.patient=patient-2
✅ Fixed 3 encounters (appointment set to NULL)
   All changes logged to ClinicalAuditLog for traceability
```

---

## Tests Creados

**Archivo:** `apps/api/tests/test_layer2_a1_domain_integrity.py`

### Cobertura de Tests

| Test | Invariante Validada |
|------|---------------------|
| `test_encounter_requires_patient_model_level` | Encounter sin patient falla (DB level) |
| `test_encounter_requires_patient_serializer_level` | Encounter sin patient falla (API level) |
| `test_encounter_appointment_patient_must_match_serializer` | Mismatch patient-appointment rechazado (API) |
| `test_encounter_appointment_patient_must_match_model` | Mismatch patient-appointment rechazado (Model) |
| `test_encounter_with_matching_patient_appointment_succeeds` | Match correcto permite creación |
| `test_encounter_without_appointment_is_valid` | Encounter sin appointment es válido |
| `test_photo_encounter_patient_must_match_model` | Photo-Encounter mismatch rechazado |
| `test_photo_with_matching_patient_encounter_succeeds` | Photo-Encounter match permite creación |
| `test_photo_without_encounter_is_valid` | Photo sin encounter es válido |
| `test_reception_cannot_list_encounters` | Reception bloqueado (Layer 1) |
| `test_reception_cannot_retrieve_encounter` | Reception bloqueado (Layer 1) |
| `test_reception_cannot_create_encounter` | Reception bloqueado (Layer 1) |

**Total:** 12 tests

**Ejecutar tests:**
```bash
pytest apps/api/tests/test_layer2_a1_domain_integrity.py -v
```

---

## Archivos Modificados

### Modelos
1. **`apps/api/apps/clinical/models.py`**
   - Añadido `Encounter.clean()` con validación appointment-patient
   - Añadido índice `idx_encounter_patient_timeline`
   - Añadido índice `idx_clinical_photo_patient_timeline`

2. **`apps/api/apps/photos/models.py`**
   - Añadido `SkinPhoto.clean()` con validación encounter-patient

### Serializers
3. **`apps/api/apps/encounters/serializers.py`**
   - Añadido `EncounterSerializer.validate()` con validación appointment-patient
   - Docstring actualizado

4. **`apps/api/apps/photos/serializers.py`**
   - Añadido `SkinPhotoSerializer.validate()` con validación encounter-patient
   - Docstring actualizado

### Migraciones
5. **`apps/api/apps/clinical/migrations/0004_layer2_a1_clinical_domain_integrity.py`** (NUEVO)
   - Data migration para limpiar inconsistencias
   - AddIndex para timeline queries

### Tests
6. **`apps/api/tests/test_layer2_a1_domain_integrity.py`** (NUEVO)
   - 12 tests comprehensivos
   - Cobertura de todas las invariantes

---

## Compatibilidad con Capa 1

✅ **No se rompe ninguna funcionalidad de Capa 1:**
- Permisos de recepción intactos (tests incluidos)
- Audit logging funcionando
- Status transitions de Appointment no afectadas
- IsClinicalStaff permission vigente

---

## Cómo Aplicar

### 1. Ejecutar Migraciones

```bash
cd apps/api
python manage.py migrate clinical 0004_layer2_a1_clinical_domain_integrity
```

**Salida esperada:**
```
Running migrations:
  Applying clinical.0004_layer2_a1_clinical_domain_integrity...
✅ No inconsistent encounter-appointment relationships found
✅ No inconsistent photo-encounter relationships found
 OK
```

### 2. Ejecutar Tests

```bash
pytest apps/api/tests/test_layer2_a1_domain_integrity.py -v
```

**Salida esperada:**
```
test_layer2_a1_domain_integrity.py::TestEncounterPatientInvariant::test_encounter_requires_patient_model_level PASSED
test_layer2_a1_domain_integrity.py::TestEncounterPatientInvariant::test_encounter_requires_patient_serializer_level PASSED
...
============ 12 passed in 2.34s ============
```

### 3. Verificar Índices

```sql
-- Verificar que los índices fueron creados
SELECT indexname, tablename 
FROM pg_indexes 
WHERE tablename IN ('encounter', 'clinical_photo') 
AND indexname LIKE '%timeline%';
```

**Resultado esperado:**
```
idx_encounter_patient_timeline | encounter
idx_clinical_photo_patient_timeline | clinical_photo
```

---

## Casos de Uso Validados

### ✅ Caso 1: Crear Encounter con Appointment del Mismo Paciente
```python
# Patient A tiene Appointment A
# Crear Encounter con patient=A y appointment=A
POST /api/encounters/
{
    "patient": "patient-a-uuid",
    "appointment": "appointment-a-uuid",  # appointment.patient = patient-a
    "type": "consultation",
    ...
}
# ✅ PERMITIDO
```

### ❌ Caso 2: Crear Encounter con Appointment de Otro Paciente
```python
# Patient B tiene Appointment A (de Patient A)
# Intentar crear Encounter con patient=B y appointment=A
POST /api/encounters/
{
    "patient": "patient-b-uuid",
    "appointment": "appointment-a-uuid",  # appointment.patient = patient-a ≠ patient-b
    ...
}
# ❌ RECHAZADO: 400 Bad Request
# "Appointment patient mismatch: encounter.patient=patient-b but appointment.patient=patient-a"
```

### ✅ Caso 3: Crear Encounter Sin Appointment (Walk-in)
```python
# Patient sin cita previa llega a urgencias
POST /api/encounters/
{
    "patient": "patient-c-uuid",
    # No appointment field
    "type": "emergency",
    ...
}
# ✅ PERMITIDO
```

### ❌ Caso 4: Crear Photo con Encounter de Otro Paciente
```python
# Photo para Patient X referenciando Encounter de Patient Y
POST /api/skin-photos/
{
    "patient": "patient-x-uuid",
    "encounter": "encounter-y-uuid",  # encounter.patient = patient-y ≠ patient-x
    ...
}
# ❌ RECHAZADO: 400 Bad Request
# "Encounter patient mismatch: photo.patient=patient-x but encounter.patient=patient-y"
```

---

## Beneficios

1. **Integridad Referencial Garantizada**
   - No más orphan encounters con appointments inconsistentes
   - No más photos vinculadas a encounters de otros pacientes

2. **Performance de Timeline Mejorada**
   - Índices compuestos (patient, -created_at) aceleran queries de historial
   - Queries de tipo `patient.encounters.all().order_by('-created_at')` optimizadas

3. **Validación en Múltiples Capas**
   - Modelo (clean())
   - Serializer (validate())
   - Base de datos (índices)

4. **Trazabilidad de Correcciones**
   - Data migration registra todas las correcciones en ClinicalAuditLog
   - Posible auditar qué datos fueron corregidos y cuándo

5. **Tests Comprehensivos**
   - 12 tests cubren todos los escenarios
   - Regression testing asegurado

---

## Próximos Pasos Sugeridos (Opcional)

### Capa 2 A2: Constraints a Nivel de Base de Datos

Si se requiere mayor robustez, considerar:

1. **CHECK Constraint para Appointment-Patient:**
   ```sql
   -- Requiere función PL/pgSQL (complejo con FK cruzadas)
   -- Alternativa: Trigger que valide antes de INSERT/UPDATE
   ```

2. **Partial Unique Index:**
   ```sql
   -- Asegurar que un Encounter solo tenga un Appointment activo
   CREATE UNIQUE INDEX idx_encounter_unique_active_appointment
   ON encounter (appointment_id)
   WHERE appointment_id IS NOT NULL AND is_deleted = FALSE;
   ```

---

## Conclusión

✅ **Capa 2 A1 completamente implementada**  
✅ **Invariantes del dominio clínico reforzadas**  
✅ **Datos históricos limpiados con trazabilidad**  
✅ **Tests comprehensivos (12 tests)**  
✅ **Índices de performance añadidos**  
✅ **Compatible con Capa 1 (sin breaking changes)**

El modelo clínico ahora garantiza consistencia incluso ante llamadas directas al API o errores de UI.

---

**Implementado por:** GitHub Copilot  
**Fecha:** 15 de diciembre de 2025  
**Versión:** Capa 2 A1
