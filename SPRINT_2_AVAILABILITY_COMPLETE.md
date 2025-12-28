# SPRINT 2 COMPLETADO: Availability Calculation (Free Slots)

**Fecha**: 2024-12-28  
**Estado**: ✅ COMPLETADO  
**Tipo**: Read-Only, Informativo  

---

## 🎯 OBJETIVO

Implementar cálculo de slots libres para un practitioner basado en datos reales del ERP (appointments + blocks), sin crear citas. El resultado es informativo para recepción y futuro booking.

---

## 📋 RESUMEN DE IMPLEMENTACIÓN

### ✅ Completado

1. **Servicio de disponibilidad** (`AvailabilityService`)
   - Cálculo de slots libres basado en jornada laboral (09:00-17:00 UTC)
   - Resta appointments activos (draft, scheduled, confirmed, checked_in)
   - Resta PractitionerBlocks (vacation, blocked, personal, training)
   - Genera slots de duración configurable (default: 30 minutos)
   - NO devuelve slots en el pasado
   - NO devuelve slots solapados
   - Timezone-aware (todos los datetimes en UTC)

2. **Endpoint API**
   ```
   GET /api/v1/clinical/practitioners/{id}/availability/
   ```
   - Query params: `date_from` (required), `date_to` (required), `slot_duration` (optional, default 30), `timezone` (optional, default UTC)
   - RBAC implementado (mismo criterio que calendar endpoint)
   - Validación de parámetros
   - Manejo de errores

3. **Tests unitarios** (8 tests, todos ✅ pasados)
   - Servicio: jornada completa sin appointments
   - Servicio: slots partidos con appointment en medio
   - Servicio: sin slots con PractitionerBlock
   - Endpoint: Marketing role → 403
   - Endpoint: Practitioner ve su propia disponibilidad → 200
   - Endpoint: Practitioner NO puede ver otro → 403
   - Endpoint: Admin puede ver cualquier practitioner → 200
   - Endpoint: Parámetros faltantes → 400

---

## 🏗️ ARQUITECTURA

### Archivos Modificados

1. **apps/api/apps/clinical/services.py** (líneas 714-936)
   - Clase `AvailabilityService` con métodos estáticos
   - `calculate_availability()`: Método principal de cálculo
   - `_calculate_free_slots()`: Algoritmo de slots libres

2. **apps/api/apps/clinical/views.py** (líneas 1759-1909)
   - Clase `PractitionerAvailabilityView(APIView)`
   - RBAC: Admin/Reception → cualquiera, Practitioner → solo propio, Marketing/Accounting → 403
   - Validación de params: date_from, date_to, slot_duration (5-240 minutos)

3. **apps/api/apps/clinical/urls.py** (líneas 9, 34)
   - Import de `PractitionerAvailabilityView`
   - Routing: `practitioners/<uuid:practitioner_id>/availability/`

### Archivos Nuevos

4. **tests/test_availability.py** (14634 bytes)
   - 8 tests unitarios para service y endpoint
   - Fixtures: `create_user_with_role()`, `test_patient`, `test_location`, `api_client`

---

## 🔧 DECISIONES TÉCNICAS

### 1. Jornada Laboral por Defecto

**Decisión**: Usar horario fijo 09:00-17:00 (UTC) como default.

**Razón**:
- NO existe modelo de schedule/working_hours para practitioners
- Documentar asunción explícitamente en código y docs
- Sprint futuro puede implementar modelo de horarios personalizados

**Implementación**:
```python
class AvailabilityService:
    DEFAULT_START_TIME = "09:00"
    DEFAULT_END_TIME = "17:00"
    DEFAULT_SLOT_DURATION = 30  # minutes
```

**Próxima iteración**: Crear modelo `PractitionerSchedule` con horarios por día de semana.

---

### 2. Estados de Appointment que Bloquean

**Decisión**: Solo appointments activos bloquean slots: `draft`, `scheduled`, `confirmed`, `checked_in`.

**Razón**:
- Estados terminales (`cancelled`, `no_show`, `completed`) ya NO ocupan la agenda
- Consistente con lógica de overlaps en Sprint 1

**Implementación**:
```python
appointments = Appointment.objects.filter(
    practitioner_id=practitioner_id,
    is_deleted=False,
    status__in=['draft', 'scheduled', 'confirmed', 'checked_in']
)
```

---

### 3. No Slots en el Pasado

**Decisión**: Excluir días pasados y slots ya transcurridos del día actual.

**Razón**:
- Evitar confusión en UI de booking
- Optimización: no calcular slots inútiles

**Implementación**:
```python
# Skip past dates
if current_date < now.date():
    current_date += timedelta(days=1)
    continue

# Skip past slots
if slot_end <= now:
    current_time += slot_delta
    continue
```

---

### 4. Algoritmo de Slots Libres

**Decisión**: Algoritmo iterativo con saltos en períodos ocupados.

**Razón**:
- Simple de entender y mantener
- Eficiente: O(n + m) donde n = busy_periods, m = slots_count
- No requiere estructuras de datos complejas

**Pseudocódigo**:
```
1. Ordenar busy_periods por start time
2. current_time = work_start
3. Mientras current_time + slot_duration <= work_end:
   a. Verificar overlap con busy_periods
   b. Si overlap: saltar a end de busy_period
   c. Si NO overlap: agregar slot libre, avanzar slot_duration
```

---

### 5. RBAC Consistency

**Decisión**: Reutilizar misma lógica de RBAC que `PractitionerCalendarView`.

**Razón**:
- Consistencia: mismos roles ven calendar y availability
- Seguridad: Marketing/Accounting no ven datos clínicos

**Matriz de Permisos**:

| Rol | Puede Ver Cualquier Practitioner | Puede Ver Propio | Endpoint Response |
|-----|----------------------------------|------------------|-------------------|
| **Admin** | ✅ Sí | ✅ Sí | 200 OK |
| **Reception** | ✅ Sí | N/A | 200 OK |
| **Practitioner** | ❌ No | ✅ Sí | 200 OK (propio), 403 (otro) |
| **Marketing** | ❌ No | ❌ No | 403 Forbidden |
| **Accounting** | ❌ No | ❌ No | 403 Forbidden |

---

## 📡 REQUEST/RESPONSE EXAMPLES

### Request Exitoso

```bash
GET /api/v1/clinical/practitioners/1674cca8-15e6-4991-8a84-c66b7c1e5acf/availability/?date_from=2025-12-29&date_to=2025-12-31&slot_duration=30
Authorization: Bearer <admin_token>
```

### Response 200 OK

```json
{
  "practitioner_id": "1674cca8-15e6-4991-8a84-c66b7c1e5acf",
  "date_from": "2025-12-29",
  "date_to": "2025-12-31",
  "slot_duration": 30,
  "timezone": "UTC",
  "availability": [
    {
      "date": "2025-12-29",
      "slots": [
        {"start": "09:00", "end": "09:30"},
        {"start": "09:30", "end": "10:00"},
        {"start": "10:00", "end": "10:30"},
        {"start": "12:00", "end": "12:30"},
        {"start": "12:30", "end": "13:00"},
        {"start": "15:00", "end": "15:30"},
        {"start": "15:30", "end": "16:00"},
        {"start": "16:00", "end": "16:30"},
        {"start": "16:30", "end": "17:00"}
      ]
    },
    {
      "date": "2025-12-30",
      "slots": []
    },
    {
      "date": "2025-12-31",
      "slots": [
        {"start": "09:00", "end": "09:30"},
        {"start": "09:30", "end": "10:00"}
      ]
    }
  ]
}
```

**Interpretación**:
- 2025-12-29: Disponible con gaps (appointments 10:30-12:00, 13:00-15:00)
- 2025-12-30: NO disponible (PractitionerBlock: vacation full-day)
- 2025-12-31: Disponible solo 09:00-10:00 (resto ocupado)

---

### Request con Parámetros Opcionales

```bash
GET /api/v1/clinical/practitioners/1674cca8-15e6-4991-8a84-c66b7c1e5acf/availability/?date_from=2025-12-29&date_to=2025-12-29&slot_duration=60&timezone=Europe/Madrid
Authorization: Bearer <reception_token>
```

### Response 200 OK (Slots de 60 minutos)

```json
{
  "practitioner_id": "1674cca8-15e6-4991-8a84-c66b7c1e5acf",
  "date_from": "2025-12-29",
  "date_to": "2025-12-29",
  "slot_duration": 60,
  "timezone": "Europe/Madrid",
  "availability": [
    {
      "date": "2025-12-29",
      "slots": [
        {"start": "09:00", "end": "10:00"},
        {"start": "10:00", "end": "11:00"},
        {"start": "15:00", "end": "16:00"},
        {"start": "16:00", "end": "17:00"}
      ]
    }
  ]
}
```

---

### Error: Parámetros Faltantes

```bash
GET /api/v1/clinical/practitioners/1674cca8-15e6-4991-8a84-c66b7c1e5acf/availability/
Authorization: Bearer <admin_token>
```

### Response 400 Bad Request

```json
{
  "error": "date_from and date_to are required",
  "details": {
    "date_from": "Required format: YYYY-MM-DD",
    "date_to": "Required format: YYYY-MM-DD"
  }
}
```

---

### Error: Marketing Intenta Acceder

```bash
GET /api/v1/clinical/practitioners/1674cca8-15e6-4991-8a84-c66b7c1e5acf/availability/?date_from=2025-12-29&date_to=2025-12-31
Authorization: Bearer <marketing_token>
```

### Response 403 Forbidden

```json
{
  "detail": "You do not have permission to view practitioner availability"
}
```

---

### Error: Practitioner Intenta Ver Otro

```bash
GET /api/v1/clinical/practitioners/OTRO-PRACTITIONER-UUID/availability/?date_from=2025-12-29&date_to=2025-12-31
Authorization: Bearer <practitioner_token>
```

### Response 403 Forbidden

```json
{
  "detail": "You can only view your own availability"
}
```

---

## 🧪 TESTS EJECUTADOS

```bash
docker exec emr-api-dev pytest /app/tests/test_availability.py -v

============================= test session starts ==============================
platform linux -- Python 3.11.13, pytest-7.4.3, pluggy-1.6.0
collected 8 items

tests/test_availability.py::TestAvailabilityService::test_full_day_available_no_appointments PASSED
tests/test_availability.py::TestAvailabilityService::test_slots_split_with_appointment PASSED
tests/test_availability.py::TestAvailabilityService::test_no_slots_with_practitioner_block PASSED
tests/test_availability.py::TestAvailabilityEndpoint::test_marketing_role_receives_403 PASSED
tests/test_availability.py::TestAvailabilityEndpoint::test_practitioner_can_view_own_availability PASSED
tests/test_availability.py::TestAvailabilityEndpoint::test_practitioner_cannot_view_other_availability PASSED
tests/test_availability.py::TestAvailabilityEndpoint::test_admin_can_view_any_availability PASSED
tests/test_availability.py::TestAvailabilityEndpoint::test_missing_date_params_returns_400 PASSED

============================== 8 passed in 1.03s ===============================
```

**Coverage**:
- ✅ Servicio: 3 tests de lógica de cálculo
- ✅ Endpoint: 5 tests de RBAC y validaciones
- ✅ Total: 8/8 tests pasados

---

## 🔍 PRUEBA MANUAL

### 1. Obtener Token

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access'])")
```

### 2. Llamar Endpoint

```bash
curl -s "http://localhost:8000/api/v1/clinical/practitioners/1674cca8-15e6-4991-8a84-c66b7c1e5acf/availability/?date_from=2025-12-29&date_to=2025-12-31&slot_duration=30" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -m json.tool
```

### 3. Verificar Respuesta

Debe devolver JSON con:
- `practitioner_id`: UUID del practitioner
- `availability`: Array de días con slots libres
- Slots NO en el pasado
- Slots NO solapan con appointments ni blocks existentes

---

## 📊 MÉTRICAS

- **Líneas de código**: ~222 líneas (service + view)
- **Tests**: 8 (100% pasados)
- **Archivos modificados**: 3
- **Archivos nuevos**: 1
- **Migraciones**: 0 (no se modificaron modelos)
- **Tiempo de implementación**: 1 día

---

## 🚀 PRÓXIMOS PASOS (Sprint 3)

### 1. Frontend - Visualización de Disponibilidad

**Objetivo**: Mostrar slots libres en UI de recepción.

**Tareas**:
- Crear componente `AvailabilityCalendar` en Next.js
- Fetch `/availability/` endpoint
- Mostrar slots libres en formato calendario semanal
- Color-coding: libre (verde), ocupado (rojo), pasado (gris)

---

### 2. Booking - Crear Appointment desde Slot

**Objetivo**: Permitir a recepción crear cita desde slot libre.

**Tareas**:
- Click en slot libre → modal de crear appointment
- Pre-llenar `scheduled_start` y `scheduled_end` desde slot
- Validar que slot siga disponible al crear (race condition)
- Refresh availability después de crear cita

---

### 3. Modelo de Horarios Personalizados

**Objetivo**: Reemplazar hardcoded 09:00-17:00 con horarios reales.

**Propuesta**:
```python
class PractitionerSchedule(models.Model):
    practitioner = models.ForeignKey(Practitioner, on_delete=models.CASCADE)
    day_of_week = models.IntegerField(choices=...)  # 0=Monday, 6=Sunday
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    
    # Ejemplo:
    # Dr. Smith: Lunes 09:00-17:00, Martes 10:00-14:00, Miércoles OFF
```

**Migración**: Sí, crear modelo nuevo + migration.

---

### 4. Integración con Calendly (Read-Only)

**Objetivo**: Mostrar slots ocupados por Calendly en availability.

**Tareas**:
- Fetch events desde Calendly API
- Parsear como "busy periods"
- Restar de availability
- Mostrar en calendar view con distintivo "Calendly"

**Requisito**: NO modificar Calendly, solo lectura.

---

### 5. Optimización - Cache de Availability

**Objetivo**: Reducir carga de DB para requests repetidos.

**Propuesta**:
- Cache Redis con TTL 5 minutos
- Key: `availability:{practitioner_id}:{date_from}:{date_to}:{slot_duration}`
- Invalidar al crear/editar appointment o block

---

## ⚠️ LIMITACIONES CONOCIDAS

### 1. Horario Fijo

**Limitación**: Todos los practitioners tienen horario 09:00-17:00.

**Impacto**: Slots pueden aparecer en horarios que practitioner NO trabaja.

**Workaround Temporal**: Crear PractitionerBlocks para horarios no laborables.

**Fix Definitivo**: Implementar modelo PractitionerSchedule (Sprint 3).

---

### 2. Timezone Hardcoded

**Limitación**: Default timezone es UTC, no se usa timezone del practitioner.

**Impacto**: Frontend debe convertir a local timezone manualmente.

**Workaround Temporal**: Pasar `timezone=Europe/Madrid` en query param.

**Fix Definitivo**: Agregar campo `timezone` en Practitioner model.

---

### 3. No Considera Duración de Appointment

**Limitación**: Appointments con duración variable no afectan granularidad de slots.

**Ejemplo**: Si appointment dura 45 min y slots son de 30 min, puede generar slot de 15 min.

**Impacto**: Slot muy corto puede aparecer disponible pero no útil.

**Fix Futuro**: Filtrar slots con duración < `min_slot_duration`.

---

## 📚 REFERENCIAS

- **Sprint 1**: [SPRINT_1_AGENDA_READ_ONLY_COMPLETE.md](SPRINT_1_AGENDA_READ_ONLY_COMPLETE.md)
- **Verification Pack**: [SPRINT_1_VERIFICATION_PACK.md](SPRINT_1_VERIFICATION_PACK.md)
- **API Contracts**: [docs/API_CONTRACTS.md](docs/API_CONTRACTS.md)
- **Business Rules**: [docs/BUSINESS_RULES.md](docs/BUSINESS_RULES.md)

---

## ✅ CHECKLIST DE COMPLETADO

- [x] Servicio `AvailabilityService` implementado
- [x] Endpoint `/availability/` con RBAC
- [x] Tests unitarios (8/8 pasados)
- [x] Documentación completa
- [x] No crea appointments (read-only)
- [x] No modifica Calendly
- [x] No hardcodea slots
- [x] Lógica en backend (no frontend)
- [x] Timezone-aware datetimes
- [x] No devuelve slots en pasado
- [x] No devuelve slots solapados

---

**Estado Final**: ✅ Sprint 2 COMPLETADO - Listo para integración frontend (Sprint 3)

**Firmado por**: Backend Dev  
**Fecha**: 2024-12-28  
**Revisado por**: QA/Verifier Estricto
