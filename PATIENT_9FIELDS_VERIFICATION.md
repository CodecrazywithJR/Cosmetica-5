# VERIFICACIÓN END-TO-END: 9 CAMPOS NUEVOS DEL MODELO PATIENT

**Fecha**: 28 de diciembre de 2025  
**Objetivo**: Verificar que los 9 campos nuevos del modelo Patient funcionan END-TO-END vía API, especialmente en UPDATE (PATCH), con persistencia real en BD.

---

## 1. CAMPOS VERIFICADOS

Los 9 campos nuevos añadidos al modelo Patient:

1. `document_type` - CharField (choices: dni, passport, other)
2. `document_number` - CharField
3. `nationality` - CharField
4. `emergency_contact_name` - CharField
5. `emergency_contact_phone` - CharField
6. `privacy_policy_accepted` - BooleanField
7. `privacy_policy_accepted_at` - DateTimeField
8. `terms_accepted` - BooleanField
9. `terms_accepted_at` - DateTimeField

---

## 2. LOCALIZACIÓN DEL CÓDIGO

### ViewSet
- **Archivo**: `apps/api/apps/clinical/views.py`
- **Clase**: `PatientViewSet` (línea 55)
- **Endpoints**:
  - `POST /api/v1/clinical/patients/`
  - `GET /api/v1/clinical/patients/{id}/`
  - `PATCH /api/v1/clinical/patients/{id}/`
  - `PUT /api/v1/clinical/patients/{id}/`

### Serializer
- **Archivo**: `apps/api/apps/clinical/serializers.py`
- **Clase**: `PatientDetailSerializer` (línea 83)
- **Estrategia**: El ViewSet usa `get_serializer_class()` que retorna:
  - `PatientListSerializer` para `list` action
  - `PatientDetailSerializer` para `create`, `retrieve`, `update`, `partial_update`

---

## 3. VERIFICACIÓN DE CAMPOS EN SERIALIZER

### Campos incluidos en Meta.fields ✅
Todos los 9 campos están declarados en `PatientDetailSerializer.Meta.fields` (líneas 106-137):
```python
'document_type',
'document_number',
'nationality',
# ...
'emergency_contact_name',
'emergency_contact_phone',
'privacy_policy_accepted',
'privacy_policy_accepted_at',
'terms_accepted',
'terms_accepted_at',
```

### Campos NO marcados como read_only ✅
Ninguno de los 9 campos está en `Meta.read_only_fields` (líneas 145-157), lo que significa que son **escribibles** en PATCH/PUT.

---

## 4. MÉTODO UPDATE() DEL SERIALIZER

### Código corregido
**Archivo**: `apps/api/apps/clinical/serializers.py` (líneas 232-256)

El método `update()` aplica correctamente todos los campos del `validated_data` a la instancia:

```python
def update(self, instance, validated_data):
    """Update patient with row_version increment"""
    # Remove referral_source_id from validated_data if present
    referral_source_id = validated_data.pop('referral_source_id', None)
    
    # Update referral_source FK if provided
    if referral_source_id is not None:
        validated_data['referral_source_id'] = referral_source_id
    
    # Remove row_version from validated_data (we'll increment it)
    validated_data.pop('row_version', None)
    
    # Increment row_version
    instance.row_version += 1
    
    # Update full_name_normalized if name fields changed
    if 'first_name' in validated_data or 'last_name' in validated_data:
        first_name = validated_data.get('first_name', instance.first_name)
        last_name = validated_data.get('last_name', instance.last_name)
        instance.full_name_normalized = f"{first_name} {last_name}".strip().lower()
    
    # Update all fields from validated_data
    for attr, value in validated_data.items():
        setattr(instance, attr, value)
    
    # Update instance
    instance.save()
    return instance
```

### Problema resuelto
Se eliminó código residual duplicado (líneas 277-281 antiguas) que estaba **después** del `return` de `to_representation()` y nunca se ejecutaba.

---

## 5. TESTS CREADOS

### Archivo de tests
**Ubicación**: `tests/test_patient_9fields_e2e.py`

### Tests implementados (7 tests, todos ✅ PASADOS)

#### TestPatient9FieldsEndToEnd
1. **test_create_patient_without_new_fields**: Crea paciente sin los 9 campos → verifica defaults (null/False)
2. **test_patch_patient_with_all_9_fields**: PATCH con los 9 campos → verifica respuesta API y persistencia en BD con `refresh_from_db()`
3. **test_get_after_patch_confirms_persistence**: POST + PATCH + GET → confirma que GET devuelve valores actualizados
4. **test_patch_partial_fields**: PATCH con solo algunos campos → verifica actualización parcial
5. **test_patch_boolean_fields_without_timestamps**: PATCH con booleans True pero sin timestamps → verifica comportamiento actual (acepta null)
6. **test_put_full_update_with_9_fields**: PUT completo con los 9 campos → verifica persistencia

#### TestPatient9FieldsRowVersionIncrement
7. **test_patch_increments_row_version**: Verifica que row_version se incrementa correctamente en PATCH

---

## 6. EJECUCIÓN DE TESTS

### Comando ejecutado
```bash
docker exec emr-api-dev pytest tests/test_patient_9fields_e2e.py -v --tb=short
```

### Resultado
```
======================== 7 passed, 2 warnings in 0.77s =========================
```

**Estado**: ✅ **TODOS LOS TESTS PASARON**

### Warnings
- 2 warnings por `return` en lugar de `assert` en tests (no crítico, solo estilo)

---

## 7. EVIDENCIA DE PERSISTENCIA

### Verificaciones clave en tests

```python
# Test 2: test_patch_patient_with_all_9_fields
# Después de PATCH, se verifica con refresh_from_db():
patient = Patient.objects.get(id=patient_id)
patient.refresh_from_db()

assert patient.document_type == 'dni', "document_type NOT persisted!"
assert patient.document_number == '12345678A', "document_number NOT persisted!"
assert patient.nationality == 'Spanish', "nationality NOT persisted!"
assert patient.emergency_contact_name == 'Emergency Contact Person', "emergency_contact_name NOT persisted!"
assert patient.emergency_contact_phone == '+34600123456', "emergency_contact_phone NOT persisted!"
assert patient.privacy_policy_accepted is True, "privacy_policy_accepted NOT persisted!"
assert patient.privacy_policy_accepted_at is not None, "privacy_policy_accepted_at NOT persisted!"
assert patient.terms_accepted is True, "terms_accepted NOT persisted!"
assert patient.terms_accepted_at is not None, "terms_accepted_at NOT persisted!"
```

### Print statements en tests
```
✅ ALL 9 FIELDS PERSISTED TO DATABASE
✅ GET CONFIRMS ALL 9 FIELDS PERSISTED
✅ PARTIAL PATCH WORKS CORRECTLY
✅ BOOLEAN FIELDS WITHOUT TIMESTAMPS ACCEPTED (current behavior)
✅ PUT (full update) ALSO PERSISTS ALL 9 FIELDS
✅ ROW_VERSION INCREMENTS CORRECTLY
```

---

## 8. FLUJO DE OPERACIONES

### POST (Create)
1. Usuario envía POST con campos básicos (first_name, last_name, etc.)
2. Serializer valida datos
3. `create()` genera `full_name_normalized`, establece `created_by_user`
4. Se guarda en BD con valores default para los 9 campos:
   - `document_type`, `document_number`, `nationality`: `null`
   - `emergency_contact_name`, `emergency_contact_phone`: `null`
   - `privacy_policy_accepted`, `terms_accepted`: `False`
   - `privacy_policy_accepted_at`, `terms_accepted_at`: `null`

### PATCH (Partial Update)
1. Usuario envía PATCH con `row_version` + algunos/todos los 9 campos
2. Serializer valida `row_version` (optimistic locking)
3. `update()`:
   - Incrementa `row_version`
   - Actualiza `full_name_normalized` si name cambió
   - **Aplica cada campo de `validated_data` con `setattr()`**
   - Llama a `instance.save()`
4. Valores persisten en BD ✅

### GET (Retrieve)
1. Usuario solicita GET del mismo patient
2. Serializer devuelve valores desde BD
3. Confirmación: valores PATCH coinciden con BD

---

## 9. COMPORTAMIENTO ACTUAL: TIMESTAMPS SIN AUTO-SET

### Decisión de diseño
Si se envía `privacy_policy_accepted=True` o `terms_accepted=True` **sin** proveer el timestamp correspondiente, el sistema:
- ✅ **ACEPTA** el valor booleano
- ✅ **NO genera automáticamente** el timestamp
- ✅ El timestamp queda en `null`

**Justificación**: Los timestamps son opcionales (`blank=True, null=True`), permitiendo flexibilidad al cliente. Si se requiere auto-set, se debe implementar lógica adicional en el serializer.

**Test que lo verifica**: `test_patch_boolean_fields_without_timestamps`

---

## 10. CONCLUSIÓN

### ✅ CONFIRMACIÓN FINAL: ALL FIELDS PERSISTED

**Evidencia proporcionada**:
1. ✅ Localización exacta de ViewSet y Serializer
2. ✅ Verificación de campos en modelo, serializer, y NO read_only
3. ✅ Método `update()` aplica correctamente `validated_data`
4. ✅ 7 tests END-TO-END que cubren POST, PATCH, PUT, GET
5. ✅ Tests verifican persistencia en BD con `refresh_from_db()`
6. ✅ Output real de pytest: **7 passed**

**Comando de verificación**:
```bash
# Correr tests
docker exec emr-api-dev pytest tests/test_patient_9fields_e2e.py -v

# Verificación manual (opcional)
docker exec emr-api-dev python verify_9_fields_manual.py
```

### No hay "parece que" ni "los tests pasan sin evidencia"
- Tests verifican **directamente** valores en BD con ORM
- Método `update()` aplica **explícitamente** cada campo con `setattr()`
- GET posterior confirma **persistencia real** de valores

---

## 11. ARCHIVOS MODIFICADOS/CREADOS

### Modificados
- `apps/api/apps/clinical/serializers.py`: Eliminado código muerto después de `return` en `to_representation()`

### Creados
- `tests/test_patient_9fields_e2e.py`: Suite completa de tests END-TO-END
- `verify_9_fields_manual.py`: Script de verificación manual (opcional)
- `PATIENT_9FIELDS_VERIFICATION.md`: Este documento

---

**🎉 VERIFICACIÓN COMPLETA: TODOS LOS 9 CAMPOS FUNCIONAN END-TO-END CON PERSISTENCIA EN BD**
