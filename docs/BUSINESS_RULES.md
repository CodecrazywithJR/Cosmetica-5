# REGLAS DE NEGOCIO - Capa 1 ERP Clínico

## Estado: Implementadas ✅
Fecha: 15 de diciembre de 2025

---

## 1. Citas Requieren Paciente

**Regla:** No se permite crear una cita sin paciente (sin excepciones).

**Implementación:**
- Campo `patient` en modelo `Appointment` es NOT NULL (required)
- Validación en `Appointment.clean()`
- Validación en `AppointmentWriteSerializer.validate_patient_id()`
- Migración: `0002_business_rules_appointment_status_and_patient_required.py`

**Endpoints afectados:**
- `POST /api/v1/appointments/`
- `PATCH /api/v1/appointments/{id}/`
- `POST /api/v1/appointments/calendly/sync/`

**Código de Error:**
```json
{
  "patient": ["La cita requiere un paciente asignado"]
}
```

---

## 2. No Solapamientos por Profesional

**Regla:** Un mismo profesional no puede tener dos citas con rangos de tiempo solapados.

**Estados Activos (bloquean agenda):**
- `draft`
- `confirmed`
- `checked_in`

**Estados Terminales (NO bloquean):**
- `cancelled`
- `no_show`
- `completed`

**Implementación:**
- Método `Appointment._check_practitioner_overlap()`
- Validación en `Appointment.clean()`
- Detección de solapamiento: `(start1 < end2) AND (start2 < end1)`
- Protección contra race conditions: transacción atómica en creación

**Código de Error:**
```json
{
  "scheduled_start": [
    "El profesional ya tiene una cita en este horario. Estados que bloquean: draft, confirmed, checked_in"
  ]
}
```

---

## 3. Estados de Cita y Transiciones Permitidas

**Estados Oficiales:**
```
draft → confirmed | cancelled
confirmed → checked_in | cancelled | no_show
checked_in → completed | cancelled
completed → [terminal]
cancelled → [terminal]
no_show → [terminal]
```

**Implementación:**
- Enum `AppointmentStatusChoices` en `models.py`
- Método `Appointment.transition_status()`
- Endpoint dedicado: `POST /api/v1/appointments/{id}/transition/`
- Status es read-only en PATCH/PUT (debe usar /transition/)

**Uso del Endpoint:**
```bash
POST /api/v1/appointments/{id}/transition/
{
  "status": "confirmed",
  "reason": "Motivo opcional para cancel/no_show"
}
```

**Código de Error (transición inválida):**
```json
{
  "error": "Transición no permitida: Draft → Completed. Transiciones válidas: confirmed, cancelled"
}
```

**Código de Error (estado terminal):**
```json
{
  "error": "El estado 'Completed' es terminal y no puede cambiarse"
}
```

---

## 4. no_show Solo Después de scheduled_start

**Regla:** `no_show` solo debe permitirse si `scheduled_start` ya pasó (comparado con timezone-aware now).

**Implementación:**
- Validación en `Appointment.transition_status()`
- Compara `timezone.now()` con `appointment.scheduled_start`

**Código de Error:**
```json
{
  "error": "No se puede marcar como 'No Show' antes de la hora de inicio de la cita"
}
```

---

## 5. Sin Depósito/Señal

**Regla:** No introducir dependencias de pago para confirmar o completar cita.

**Implementación:**
- No hay validaciones de pago en transiciones de estado
- No hay FK a `Payment` o `Deposit` en modelo `Appointment`
- Estados `confirmed` y `completed` se permiten sin restricciones financieras

---

## 6. Historia Clínica Editable

**Regla:** Mantener editable (no implementar locking), pero añadir auditoría básica.

**Implementación:**
- Modelos clínicos (`Encounter`, `ClinicalPhoto`) NO tienen row-level locking
- Campos de auditoría existentes: `created_at`, `updated_at`, `created_by_user_id`
- No se implementa versionado de contenido clínico

**Nota:** Si en el futuro se requiere historial de cambios, implementar mediante:
- Tabla de auditoría separada
- Signals `pre_save`/`post_save`
- Django Simple History

---

## 7. Fotos Clínicas Siempre Permitidas

**Regla:** No bloquear subida/guardado por consentimiento.

**Implementación:**
- Modelo `ClinicalPhoto` NO valida consentimiento en `clean()`
- Endpoint `POST /api/v1/photos/` permite upload sin validar `Consent`
- Campo `consent_id` es nullable y opcional

**Nota:** El consentimiento se gestiona separadamente para fines legales/marketing, pero NO bloquea operaciones clínicas.

---

## 8. Recepción No Ve Diagnósticos ni Notas Clínicas

**Regla:** Un usuario con rol "recepción" NO puede:
- Acceder a endpoints clínicos (diagnósticos, notas, tratamientos, fotos)
- Ver campos clínicos embebidos en respuestas (serializers los ocultan)

**Puede ver:**
- Datos administrativos del paciente (nombre, contacto, dirección)
- Agenda (appointments)

**Implementación:**
- Permission class `IsClinicalStaff` en:
  - `EncounterViewSet`
  - `SkinPhotoViewSet`
- Método `PatientDetailSerializer.to_representation()` oculta campo `notes` para Reception
- Endpoints bloqueados para Reception:
  - `GET/POST /api/v1/encounters/`
  - `GET/POST /api/v1/photos/`

**Código de Error (acceso denegado):**
```json
{
  "detail": "No tiene permiso para realizar esta acción."
}
```

**Ejemplo de respuesta (Reception):**
```json
// GET /api/v1/patients/{id}/
{
  "id": "uuid",
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  // "notes" campo NO presente
}
```

**Ejemplo de respuesta (Admin/Practitioner):**
```json
// GET /api/v1/patients/{id}/
{
  "id": "uuid",
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "notes": "Historial clínico confidencial..."
}
```

---

## 9. Venta Asociada a Cita Opcional

**Regla:**
- La venta puede existir sin cita
- La cita puede existir sin venta
- Si existe relación, no debe ser obligatoria

**Implementación:**
- Modelo `Sale` NO tiene FK a `Appointment`
- Modelo `Appointment` NO tiene FK a `Sale`
- Relación se gestiona mediante:
  - Campo `patient` (común en ambos modelos)
  - Campo `encounter_id` en `Appointment` (nullable)
  - Ventas pueden vincularse a encounters, no directamente a appointments

**Nota:** Si en el futuro se requiere vincular ventas a citas:
- Agregar FK nullable `appointment_id` en `Sale`
- O tabla intermedia `SaleAppointment` para m2m

---

## Archivos Modificados

### Modelos
- `apps/clinical/models.py`
  - `AppointmentStatusChoices`: Estados actualizados (draft, confirmed, checked_in, completed, cancelled, no_show)
  - `Appointment.patient`: Cambio de nullable a required
  - `Appointment.clean()`: Validación de patient, time range, overlaps
  - `Appointment.transition_status()`: Método de transición con validación
  - `Appointment._check_practitioner_overlap()`: Detección de solapamientos

### Migraciones
- `apps/clinical/migrations/0002_business_rules_appointment_status_and_patient_required.py`
  - Migración de datos: scheduled→draft, attended→completed
  - Schema change: patient NOT NULL

### Serializers
- `apps/clinical/serializers.py`
  - `AppointmentWriteSerializer.validate_status()`: Bloquea cambio directo en update
  - `AppointmentWriteSerializer.validate()`: Llama a `instance.clean()`
  - `PatientDetailSerializer.to_representation()`: Oculta `notes` para Reception

### ViewSets
- `apps/clinical/views.py`
  - `AppointmentViewSet.transition_status()`: Endpoint `POST /appointments/{id}/transition/`
  - Uso de `transaction.atomic()` y `select_for_update()` para race conditions

- `apps/encounters/views.py`
  - `EncounterViewSet.permission_classes`: Agregado `IsClinicalStaff`

- `apps/photos/views.py`
  - `SkinPhotoViewSet.permission_classes`: Agregado `IsClinicalStaff`

### Permissions
- `apps/clinical/permissions.py`
  - `IsClinicalStaff`: Nueva permission class (Admin + Practitioner only)

### Tests
- `apps/api/tests/test_business_rules.py` (NUEVO)
  - 10 tests cubriendo todas las reglas de negocio

---

## Notas de Migración

**IMPORTANTE:** Antes de ejecutar la migración `0002_business_rules_*`:

1. **Verificar appointments sin paciente:**
   ```sql
   SELECT COUNT(*) FROM appointment WHERE patient_id IS NULL;
   ```

2. **Si existen appointments huérfanas:**
   - Opción A: Asignar paciente "Unknown" temporal
   - Opción B: Soft-delete appointments huérfanas
   - Opción C: Cancelar migration y limpiar datos manualmente

3. **Ejecutar migración:**
   ```bash
   python manage.py migrate clinical 0002
   ```

4. **Verificar estados migrados:**
   ```sql
   SELECT status, COUNT(*) FROM appointment GROUP BY status;
   ```

---

## Tests de Reglas de Negocio

Ejecutar tests:
```bash
pytest apps/api/tests/test_business_rules.py -v
```

Tests implementados:
1. ✅ `test_cannot_create_appointment_without_patient`
2. ✅ `test_cannot_overlap_appointments_for_same_professional_active_states`
3. ✅ `test_cancelled_or_no_show_does_not_block_slot`
4. ✅ `test_invalid_status_transition_is_rejected`
5. ✅ `test_draft_to_confirmed_transition_allowed`
6. ✅ `test_no_show_only_after_start_time`
7. ✅ `test_reception_cannot_access_clinical_endpoints`
8. ✅ `test_reception_cannot_see_diagnosis_fields_in_patient_payload`
9. ✅ `test_sale_can_exist_without_appointment_and_link_is_optional`
10. ✅ `test_appointment_model_validates_patient_required`

---

## Decisiones de Producto Pendientes

Las siguientes decisiones se documentaron pero NO se bloquearon en código (permiten flexibilidad futura):

1. **Cambio de paciente en update de cita (calendly_sync)**
   - Actualmente: Permitido
   - Riesgo: Puede romper trazabilidad appointment→encounter→patient
   - Ver: `views.py` línea ~785 comentario DEFENSIVE

2. **Resurrección de citas soft-deleted (calendly_sync)**
   - Actualmente: Permitido (update actualiza incluso si is_deleted=True)
   - Riesgo: Bypasea auditoría de eliminación
   - Ver: `views.py` línea ~800 comentario DEFENSIVE

3. **Conflicto email vs phone en patient lookup (calendly_sync)**
   - Actualmente: Email tiene prioridad
   - Riesgo: Si email→Patient A y phone→Patient B, se usa Patient A
   - Ver: `views.py` línea ~723 comentario DEFENSIVE

---

## Próximos Pasos (Opcional)

Si se requiere mayor robustez:

1. **PostgreSQL ExclusionConstraint para overlaps:**
   ```python
   # En Appointment.Meta:
   constraints = [
       ExclusionConstraint(
           name='no_overlap_active_appointments',
           expressions=[
               (DateTimeRangeField(scheduled_start, scheduled_end), RangeOperators.OVERLAPS),
               ('practitioner_id', RangeOperators.EQUAL),
           ],
           condition=Q(status__in=['draft', 'confirmed', 'checked_in']),
       )
   ]
   ```

2. **Auditoría completa de historia clínica:**
   - Instalar `django-simple-history`
   - Agregar a modelos: `Encounter`, `ClinicalPhoto`

3. **Webhooks para Calendly:**
   - Endpoint dedicado: `POST /webhooks/calendly/`
   - Validación de firma HMAC
   - Procesamiento asíncrono con Celery

4. **Rate limiting en /transition/:**
   - Prevenir abuse de cambios de estado
   - DRF throttling: `UserRateThrottle`

---

**Implementado por:** GitHub Copilot  
**Revisado:** Pendiente  
**Versión:** 1.0
