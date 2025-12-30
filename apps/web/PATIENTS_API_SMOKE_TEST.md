# Patients API - Smoke Test Manual

## Objetivo
Verificar que la función `updatePatient()` funciona correctamente con los 9 campos nuevos del modelo Patient.

## Pre-requisitos
- Backend corriendo en `http://localhost:8000`
- Frontend corriendo en `http://localhost:3000`
- Usuario autenticado con rol Admin/Practitioner

## Test 1: Update con campos de identificación

```typescript
import { fetchPatientById, updatePatient } from '@/lib/api/patients';

// 1. Obtener un patient existente
const patient = await fetchPatientById('PATIENT_UUID_HERE');
console.log('Patient actual:', patient);
console.log('row_version actual:', patient.row_version);

// 2. Actualizar con nuevos campos de identificación
const updated = await updatePatient(patient.id, {
  row_version: patient.row_version, // OBLIGATORIO
  document_type: 'passport',
  document_number: 'AB1234567',
  nationality: 'Spanish',
});

console.log('Patient actualizado:', updated);
console.log('row_version nuevo:', updated.row_version); // Debe ser row_version + 1
console.log('document_type:', updated.document_type);    // Debe ser 'passport'
```

**Resultado esperado**:
- ✅ `updated.row_version === patient.row_version + 1`
- ✅ `updated.document_type === 'passport'`
- ✅ `updated.document_number === 'AB1234567'`
- ✅ `updated.nationality === 'Spanish'`

---

## Test 2: Update con contacto de emergencia

```typescript
const updated2 = await updatePatient(patient.id, {
  row_version: updated.row_version, // Usar el row_version del update anterior
  emergency_contact_name: 'Maria García',
  emergency_contact_phone: '+34611223344',
});

console.log('Emergency contact:', {
  name: updated2.emergency_contact_name,
  phone: updated2.emergency_contact_phone,
});
```

**Resultado esperado**:
- ✅ `updated2.emergency_contact_name === 'Maria García'`
- ✅ `updated2.emergency_contact_phone === '+34611223344'`
- ✅ `updated2.row_version === updated.row_version + 1`

---

## Test 3: Update con consentimientos legales

```typescript
const now = new Date().toISOString();

const updated3 = await updatePatient(patient.id, {
  row_version: updated2.row_version,
  privacy_policy_accepted: true,
  privacy_policy_accepted_at: now,
  terms_accepted: true,
  terms_accepted_at: now,
});

console.log('Consentimientos:', {
  privacy: updated3.privacy_policy_accepted,
  privacy_at: updated3.privacy_policy_accepted_at,
  terms: updated3.terms_accepted,
  terms_at: updated3.terms_accepted_at,
});
```

**Resultado esperado**:
- ✅ `updated3.privacy_policy_accepted === true`
- ✅ `updated3.privacy_policy_accepted_at !== null`
- ✅ `updated3.terms_accepted === true`
- ✅ `updated3.terms_accepted_at !== null`

---

## Test 4: Error si row_version no coincide (Optimistic Locking)

```typescript
try {
  // Usar un row_version viejo (debe fallar)
  await updatePatient(patient.id, {
    row_version: 1, // row_version incorrecto
    document_type: 'dni',
  });
  console.error('❌ NO DEBERÍA LLEGAR AQUÍ');
} catch (error: any) {
  console.log('✅ Error esperado:', error.response?.data);
  // Backend debe devolver 400 con mensaje de row_version mismatch
}
```

**Resultado esperado**:
- ✅ Error 400
- ✅ Mensaje: "El paciente fue modificado por otro usuario"

---

## Test 5: Error si row_version no se provee

```typescript
try {
  // @ts-expect-error Testing missing row_version
  await updatePatient(patient.id, {
    document_type: 'dni',
  });
  console.error('❌ NO DEBERÍA LLEGAR AQUÍ');
} catch (error: any) {
  console.log('✅ Error esperado:', error.message);
  // Debe fallar en validación local antes de llamar al backend
}
```

**Resultado esperado**:
- ✅ Error local: "row_version is required for patient updates"

---

## Verificación de persistencia

Después de cualquier update:

```typescript
// Re-fetch del backend para confirmar persistencia
const refreshed = await fetchPatientById(patient.id);

console.log('Verificación de persistencia:');
console.log('document_type:', refreshed.document_type);
console.log('emergency_contact_name:', refreshed.emergency_contact_name);
console.log('privacy_policy_accepted:', refreshed.privacy_policy_accepted);
```

**Resultado esperado**:
- ✅ Los valores coinciden con el último `updatePatient()`
- ✅ Confirmación: datos persisten en BD, no solo en response

---

## Cómo ejecutar estos tests

### Opción A: Console del navegador
1. Abrir DevTools en página de Patients
2. Copiar y pegar cada test
3. Reemplazar `PATIENT_UUID_HERE` con un UUID real

### Opción B: Script de test (desarrollo)
```bash
# Crear archivo temporal
touch apps/web/src/lib/api/__test_patients.ts

# Ejecutar en consola del navegador o Node.js con fetch polyfill
```

### Opción C: Verificación manual en UI
1. Ir a `/patients/{id}/edit` (cuando exista)
2. Editar campos de identificación
3. Guardar
4. Recargar página
5. Confirmar que los valores persisten

---

## Checklist de validación

- [ ] `updatePatient()` devuelve Patient con row_version incrementado
- [ ] Campos de identificación (document_type, document_number, nationality) persisten
- [ ] Campos de emergencia (emergency_contact_name, emergency_contact_phone) persisten
- [ ] Campos de consentimientos (privacy_policy_accepted, terms_accepted) persisten
- [ ] Optimistic locking funciona (error si row_version no coincide)
- [ ] Validación local funciona (error si row_version no se provee)
- [ ] Re-fetch confirma persistencia en BD
- [ ] PATCH devuelve 200 (no 204)
- [ ] Response incluye todos los campos del Patient

---

## Troubleshooting

### Error: "row_version is required"
- **Causa**: No se pasó row_version en payload
- **Solución**: Siempre incluir `row_version: patient.row_version`

### Error 400: "El paciente fue modificado por otro usuario"
- **Causa**: row_version no coincide con el actual en BD
- **Solución**: Re-fetch del patient antes de update

### Error 401: "Not authenticated"
- **Causa**: Token expirado o no existe
- **Solución**: Login de nuevo

### Error 403: "No permission"
- **Causa**: Usuario no tiene rol Admin/Practitioner
- **Solución**: Usar usuario con permisos correctos

### Campos no persisten
- **Causa**: Backend no procesa los campos
- **Solución**: Verificar que backend está actualizado con los 9 campos nuevos
- **Verificación**: Ver serializer PatientDetailSerializer en backend

---

## Notas de implementación

- `updatePatient()` usa `PATCH`, no `PUT` (permite updates parciales)
- `row_version` se incrementa automáticamente en backend
- Campos opcionales pueden enviarse como `null` para limpiarlos
- Timestamps deben ser ISO 8601: `new Date().toISOString()`
- Backend valida row_version ANTES de aplicar cambios (optimistic locking)
