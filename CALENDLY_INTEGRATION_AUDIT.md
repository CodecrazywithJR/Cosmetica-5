# 🔍 AUDITORÍA EXHAUSTIVA: INTEGRACIÓN CALENDLY

**Fecha**: 2026-01-09  
**Contexto**: Análisis de TODO lo existente relacionado con Calendly  
**Fuente de verdad**: PROJECT_DECISIONS.md Sección 17

---

## 📋 RESUMEN EJECUTIVO

### ✅ Qué existe hoy

1. **Webhook funcional** que recibe eventos de Calendly → ERP
2. **Modelos y campos** preparados para Calendly (external_id, source, practitioner.calendly_url)
3. **Frontend para booking** con Calendly embed (react-calendly InlineWidget)
4. **Lógica de sincronización** que crea/actualiza Appointments desde webhooks
5. **Matching de pacientes** por email y teléfono en _process_calendly_sync()

### ⚠️ Qué está incompleto o a medias

1. **NO EXISTE código que CREE citas en Calendly desde el ERP** (recepción → Calendly)
   - Solo existe endpoint de booking LOCAL (`/practitioners/{id}/book/`) que NO integra con Calendly
   - PROJECT_DECISIONS.md §17.3 define este flujo pero NO está implementado

2. **NO EXISTE sincronización periódica** (daemon/cron)
   - Solo webhook reactivo (depende 100% de notificaciones de Calendly)

3. **NO EXISTE endpoint manual de sync** para reintentar eventos perdidos

4. **Configuración CALENDLY_API_TOKEN** definida pero sin uso en código
   - Variable existe en settings.py pero ningún código la consume

### ❌ Decisiones antiguas que ya no encajan

1. **Sistema de booking local (`/book/`) contradice decisión §17.1**
   - Endpoint `/practitioners/{id}/book/` crea citas EN LOCAL sin tocar Calendly
   - Viola principio: "Calendly es el único motor de agenda"
   
2. **Appointment.source='calendly'** vs PROJECT_DECISIONS.md §17.2
   - Código permite crear Appointments con source='manual' sin external_id
   - Contradice: "Toda cita debe existir en Calendly"

### 🚨 Riesgos reales detectados

1. **HUECOS FANTASMA**: Sistema booking local (`/book/`) puede crear citas que NO existen en Calendly
2. **PÉRDIDA DE EVENTOS**: Sin sync periódico, eventos perdidos (webhook fallido) nunca se recuperan
3. **DUPLICADOS**: Si webhook llega tarde y recepción crea manual, pueden existir 2 citas para el mismo slot
4. **ESTADO INCONSISTENTE**: Cancelaciones en Calendly pueden no propagarse si webhook falla

---

## 1️⃣ PUNTOS DE ENTRADA DE CALENDLY

### 1.1 URLs/Endpoints

#### Backend

| Endpoint | Archivo | Propósito real | Estado |
|----------|---------|----------------|--------|
| `POST /api/integrations/calendly/webhook/` | apps/integrations/views.py:84 | Recibe eventos de Calendly (invitee.created, invitee.canceled) | ✅ FUNCIONAL |
| ~~`POST /api/v1/clinical/appointments/{id}/calendly-sync/`~~ | ❌ NO EXISTE | Comentado en código como endpoint manual | ❌ NO IMPLEMENTADO |
| `POST /api/v1/clinical/practitioners/{id}/book/` | apps/web/src/lib/api/booking.ts:93 | **BOOKING LOCAL** (NO integra Calendly) | ⚠️ CONTRADICE §17 |

**Análisis crítico**:
- **Webhook funciona**: Recibe invitee.created → crea Appointment en ERP
- **NO hay endpoint para crear en Calendly**: Función `bookAppointment()` en frontend llama a `/book/` local
- **AppointmentViewSet NO tiene action calendly_sync**: Comentario en código menciona este endpoint pero no existe

#### Frontend

| Ruta | Archivo | Propósito real | Estado |
|------|---------|----------------|--------|
| `/schedule` | ~~NO EXISTE~~ | Mencionado en navegación como "Calendly booking" | ❌ RUTA INEXISTENTE |
| `/booking` | apps/web/src/app/[locale]/booking/ (asumido) | Sistema booking local con availability | ✅ FUNCIONAL |

**Componentes Calendly**:

| Componente | Archivo | Propósito |
|------------|---------|-----------|
| `CalendlyEmbed` | apps/web/src/components/calendly-embed.tsx | Wrapper para react-calendly InlineWidget |
| `CalendlyNotConfigured` | apps/web/src/components/calendly-not-configured.tsx | Mensaje cuando practitioner.calendly_url es null |
| `useCalendlyConfig()` | ❌ NO ENCONTRADO | Hook mencionado en documentación pero NO existe |

### 1.2 Servicios

| Función | Archivo | Propósito | Llamado por |
|---------|---------|-----------|-------------|
| `_process_calendly_sync()` | apps/clinical/views.py:882 | **CORE**: Crea/actualiza Appointment desde payload Calendly | Webhook |
| `verify_calendly_webhook_signature()` | apps/integrations/views.py:12 | Valida firma HMAC-SHA256 de webhook | calendly_webhook() |

**Análisis**:
- `_process_calendly_sync()` es la función central (162 líneas)
- **NO EXISTE servicio/cliente para API de Calendly** (crear/consultar eventos)
- **NO EXISTE lógica de retry** si webhook falla

### 1.3 Tasks / Daemons

**Estado**: ❌ **NO EXISTEN**

- No hay tareas Celery para sync periódico
- No hay cron jobs configurados
- No hay workers de fondo para Calendly

### 1.4 Settings / Environment Variables

| Variable | Archivo | Valor por defecto | Uso real |
|----------|---------|-------------------|----------|
| `CALENDLY_DEFAULT_URL` | config/settings.py:245 | URL admin config de Calendly | Fallback cuando practitioner.calendly_url=null |
| `CALENDLY_WEBHOOK_SECRET` | config/settings.py:333 | 'dev-webhook-secret' | ✅ USADO en verificación de firma |
| `CALENDLY_API_TOKEN` | config/settings.py:334 | '' (vacío) | ❌ **NUNCA USADO** en código |

**Análisis crítico**:
```python
# settings.py
CALENDLY_API_TOKEN = os.environ.get('CALENDLY_API_TOKEN', '')
```
↑ **Esta variable existe pero NINGÚN archivo Python la importa o usa**

### 1.5 Configuración en Modelos

#### Practitioner.calendly_url

```python
# apps/authz/models.py:267
calendly_url = models.URLField(
    max_length=500,
    blank=True,
    null=True,
    help_text='Personal Calendly scheduling URL for this practitioner. If null, system uses CALENDLY_DEFAULT_URL from settings.'
)
```

**Propósito real**:
- Almacena la URL pública de booking del practitioner (ej: https://calendly.com/dra-smith/consulta-30min)
- Frontend la usa para mostrar widget InlineWidget de Calendly
- Backend NO la usa para crear citas (porque no hay código que llame a API Calendly)

**Migración**: `0004_add_calendly_url_to_practitioner.py`

#### Appointment.external_id

```python
# apps/clinical/models.py
external_id = models.CharField(
    max_length=255,
    unique=True,
    null=True,
    blank=True,
    help_text='External system ID (e.g., Calendly event ID)'
)
```

**Propósito real**:
- Almacena el ID de Calendly (extraído de webhook: `event.uri.split('/')[-1]`)
- Usado como clave única para idempotencia en webhook
- Permite correlacionar Appointment ERP ↔ Evento Calendly

#### Appointment.source

```python
class AppointmentSourceChoices(models.TextChoices):
    CALENDLY = 'calendly', 'Calendly'
    MANUAL = 'manual', 'Manual'
    WEBSITE = 'website', 'Website'
```

**Uso real**:
- Webhook siempre marca source='calendly'
- Booking local marca source='manual' (problema: contradice §17)
- Website NO se usa actualmente

---

## 2️⃣ FLUJO ACTUAL: CREACIÓN DE CITAS DESDE CALENDLY

### Paso a paso (ÚNICO flujo implementado)

```
1. PACIENTE EXTERNA
   ├─→ Accede a practitioner.calendly_url (publicada en Instagram/web)
   ├─→ Calendly muestra disponibilidad real
   └─→ Paciente agenda cita en Calendly

2. CALENDLY (Fuente de verdad)
   ├─→ Crea evento en su sistema
   ├─→ Genera external_id único (ej: "ABC123")
   └─→ Envía webhook a ERP: POST /api/integrations/calendly/webhook/

3. ERP RECIBE WEBHOOK
   ├─→ Verifica firma HMAC-SHA256 (verify_calendly_webhook_signature)
   ├─→ Parsea payload: invitee.created
   ├─→ Extrae datos:
   │   - external_id (desde event.uri)
   │   - scheduled_start, scheduled_end (ISO datetime)
   │   - invitee.email, invitee.name, invitee.text_reminder_number
   └─→ Llama a _process_calendly_sync(sync_data)

4. _process_calendly_sync() (ATÓMICO)
   ├─→ Busca Patient por email (prioridad 1)
   ├─→ Si no existe, busca por phone_e164 (prioridad 2)
   ├─→ Si no existe, CREA Patient mínimo:
   │   - first_name/last_name desde invitee
   │   - identity_confidence='low' (GAP: sin documentos)
   │   - email, phone desde invitee
   ├─→ Appointment.objects.get_or_create(external_id=...)
   │   - Si existe: UPDATE (scheduled_start, scheduled_end, patient)
   │   - Si no existe: CREATE
   │       * patient = patient encontrado/creado
   │       * source = 'calendly'
   │       * status = 'scheduled'
   │       * external_id = ABC123
   │       * practitioner_id, location_id = null (no vienen en webhook)
   │       * notes = "Created via Calendly webhook: {event_name}"
   └─→ Retorna (appointment, created: bool)

5. WEBHOOK RESPONDE
   └─→ Siempre HTTP 200 OK (aunque falle internamente)
       Razón: Evitar retries infinitos de Calendly
```

### Datos que se usan

| Campo | Fuente webhook | Se guarda en |
|-------|----------------|--------------|
| external_id | payload.event.uri (último segmento) | Appointment.external_id |
| scheduled_start | payload.event.start_time (ISO) | Appointment.scheduled_start |
| scheduled_end | payload.event.end_time (ISO) | Appointment.scheduled_end |
| patient email | payload.invitee.email | Patient.email |
| patient name | payload.invitee.name o first_name/last_name | Patient.first_name/last_name |
| patient phone | payload.invitee.text_reminder_number | Patient.phone / phone_e164 |
| event name | payload.event.name | Appointment.notes |

### Datos que se pierden

| Campo | Por qué se pierde | Impacto |
|-------|-------------------|---------|
| practitioner_id | Webhook NO incluye practitioner | ⚠️ Appointment.practitioner = null |
| location_id | Webhook NO incluye location | ⚠️ Appointment.location = null |
| patient.document_type/number | No vienen en webhook | ⚠️ Patient.identity_confidence='low' (no verificable) |
| patient.birth_date | No viene en webhook | ⚠️ Campo vacío (crítico para historias clínicas) |
| patient.address | No viene en webhook | ⚠️ Campo vacío |

### Decisiones asumidas (implícitas en código)

1. **Email = identidad única (prioridad 1)**
   ```python
   if patient_email:
       patient = Patient.objects.filter(email=patient_email, is_deleted=False).first()
   ```
   - ⚠️ RIESGO: Si paciente cambia email en Calendly, se crea duplicado

2. **Teléfono = identidad secundaria (prioridad 2)**
   ```python
   if not patient and patient_phone:
       phone_e164 = patient_phone.strip()
       if not phone_e164.startswith('+'): phone_e164 = f'+{phone_e164}'
       patient = Patient.objects.filter(phone_e164=phone_e164).first()
   ```
   - ⚠️ RIESGO: Normalización básica (solo agrega '+'), puede fallar con formatos extraños

3. **Paciente "fantasma" si datos incompletos**
   ```python
   patient = Patient.objects.create(
       first_name=patient_first_name or 'Calendly',  # ← Placeholder si vacío
       last_name=patient_last_name or 'Patient',     # ← Placeholder
       full_name_normalized=full_name_normalized or 'calendly patient',
       identity_confidence='low'
   )
   ```
   - ⚠️ PROBLEMA: Pacientes sin identificar llenan la base de datos

4. **Appointment sin practitioner asignado**
   - Webhook NO incluye practitioner → queda null
   - Recepción debe asignar manualmente después

---

## 3️⃣ GESTIÓN DE PACIENTES EN FLUJO CALENDLY

### Cómo se identifica al paciente

**Algoritmo de matching** (en orden):

1. **Email (prioridad 1)** - `Patient.objects.filter(email=..., is_deleted=False).first()`
2. **Teléfono (prioridad 2)** - `Patient.objects.filter(phone_e164=..., is_deleted=False).first()`
3. **Si no existe → CREAR paciente mínimo**

### Qué ocurre si...

#### Caso 1: Paciente NO existe

**Flujo**:
```python
patient = Patient.objects.create(
    first_name=patient_first_name or 'Calendly',
    last_name=patient_last_name or 'Patient',
    full_name_normalized=full_name_normalized or 'calendly patient',
    email=patient_email or None,
    phone=patient_phone or None,
    phone_e164=phone_e164 if patient_phone else None,
    identity_confidence='low',  # ← Siempre 'low' desde webhook
    created_by_user=None  # ← Webhook no tiene user asociado
)
```

**Campos que quedan vacíos**:
- ✅ document_type, document_number
- ✅ birth_date (crítico)
- ✅ nationality
- ✅ address_line1, city, postal_code
- ✅ blood_type, allergies, medical_history
- ✅ emergency_contact_name/phone
- ✅ Consents (privacy_policy_accepted, terms_accepted)

**Impacto**:
- ⚠️ Paciente queda SIN consentimientos legales
- ⚠️ NO puede tener Encounters (bloqueado por regla: "Patient debe aceptar consents antes de Encounter")
- ⚠️ Recepción debe completar datos manualmente antes de atención

#### Caso 2: Paciente existe pero con datos distintos

**Flujo**:
```python
patient = Patient.objects.filter(email=patient_email).first()
# ← Se usa el paciente existente SIN actualizar datos
```

**Problema**:
- Si paciente cambió nombre en Calendly → **ERP mantiene nombre viejo**
- Si paciente cambió teléfono en Calendly → **ERP mantiene teléfono viejo**
- **NO hay lógica de merge/actualización**

**Ejemplo real**:
```
ERP:      María López, maria@ejemplo.com, +34612345678
Calendly: María Martínez (casada), maria@ejemplo.com, +34600111222

Resultado: ERP mantiene "María López" y "+34612345678"
           (datos desactualizados)
```

### Matching: ¿Cómo funciona?

#### Por email

```python
patient = Patient.objects.filter(
    email=patient_email,
    is_deleted=False  # ← Respeta soft-delete
).first()
```

**Limitaciones**:
- Solo busca por igualdad exacta (case-sensitive en algunos DBMS)
- No normaliza email (ej: `MARIA@EJEMPLO.COM` vs `maria@ejemplo.com`)
- No detecta aliases (ej: `maria+calendly@gmail.com` vs `maria@gmail.com`)

#### Por teléfono

```python
if patient_phone:
    phone_e164 = patient_phone.strip()
    if not phone_e164.startswith('+'): phone_e164 = f'+{phone_e164}'
    
    patient = Patient.objects.filter(
        phone_e164=phone_e164,
        is_deleted=False
    ).first()
```

**Normalización básica**:
- Agrega '+' si no existe
- **NO elimina espacios internos** (ej: `+34 612 345 678` ≠ `+34612345678`)
- **NO valida formato E.164 real** (puede almacenar `+34 612` sin más validación)

#### Por nombre/apellidos

**Estado**: ❌ **NO IMPLEMENTADO**

No hay búsqueda fuzzy ni matching por nombre. Si email y teléfono no coinciden, siempre crea duplicado.

### Riesgos de duplicados

**Escenarios reales**:

1. **Paciente cambia email en Calendly**
   ```
   Cita 1: maria.lopez@gmail.com   → Patient ID: 123
   Cita 2: maria.lopez@hotmail.com → Patient ID: 456 (DUPLICADO)
   ```

2. **Paciente ingresa teléfono con/sin formato**
   ```
   Cita 1: +34612345678       → Patient ID: 123
   Cita 2: 34 612 345 678     → Patient ID: 456 (DUPLICADO)
   Cita 3: (34) 612-345-678   → Patient ID: 789 (DUPLICADO)
   ```

3. **Paciente sin email en Calendly**
   ```
   Cita 1: invitee.email=null → Patient: "Calendly Patient" ID:111
   Cita 2: invitee.email=null → Patient: "Calendly Patient" ID:222 (DUPLICADO)
   ```

**No hay mecanismo de detección automática** de duplicados.

---

## 4️⃣ SINCRONIZACIÓN Y ACTUALIZACIÓN

### Sync periódico (daemon / cron)

**Estado**: ❌ **NO EXISTE**

- No hay tareas Celery programadas
- No hay cron jobs en docker/scripts
- No hay workers de fondo

**Implicación**:
Si webhook falla (red, timeout, error 500), el evento se pierde para siempre.

### Sync on-demand

**Estado**: ⚠️ **MENCIONADO PERO NO IMPLEMENTADO**

Código menciona endpoint `calendly_sync()` pero NO existe en AppointmentViewSet:

```python
# apps/clinical/views.py:888 (comentario)
"""
This function contains the core logic for creating/updating appointments from Calendly.
It's called by both:
- AppointmentViewSet.calendly_sync() (manual endpoint)  ← NO EXISTE
- calendly_webhook() (automatic webhook)
"""
```

**Búsqueda en código**:
```bash
$ grep -r "calendly_sync" apps/clinical/views.py
# Solo aparece en comentarios y nombre de función _process_calendly_sync
# NO hay @action(detail=True, methods=['post'], url_path='calendly-sync')
```

### Webhooks de Calendly

#### invitee.created

**Estado**: ✅ **IMPLEMENTADO Y FUNCIONAL**

```python
# apps/integrations/views.py:132
if event_type == 'invitee.created':
    # Extrae datos de payload
    # Llama a _process_calendly_sync()
    # Crea/actualiza Appointment
```

**Flujo**:
1. Calendly → POST /api/integrations/calendly/webhook/ con evento
2. Verifica firma HMAC
3. Extrae external_id, start/end, invitee data
4. _process_calendly_sync() → crea/actualiza Appointment
5. Retorna 200 OK (siempre, aunque falle)

#### invitee.canceled

**Estado**: ✅ **IMPLEMENTADO Y FUNCIONAL**

```python
# apps/integrations/views.py:201
elif event_type == 'invitee.canceled':
    appointment = Appointment.objects.get(external_id=external_id)
    appointment.status = 'cancelled'
    appointment.cancellation_reason = 'Cancelled via Calendly webhook'
    appointment.save()
```

**Flujo**:
1. Calendly notifica cancelación
2. ERP busca Appointment por external_id
3. Marca status='cancelled'
4. Si no existe, log warning pero retorna 200 OK

**⚠️ LIMITACIÓN**: Si webhook nunca llegó (cita creada en Calendly pero ERP no se enteró), la cancelación también se pierde.

#### invitee.rescheduled

**Estado**: ❌ **NO IMPLEMENTADO**

```python
# apps/integrations/views.py:234
else:
    # Unknown event type - log and return 200 OK
    logger.info(f'[CALENDLY_WEBHOOK] Unknown event type: {event_type}')
```

**Implicación**:
- Si paciente reprograma cita en Calendly, **ERP mantiene horario viejo**
- Appointment queda con scheduled_start/end desactualizados
- Genera desincronización entre Calendly (fuente de verdad) y ERP

### Qué estados se sincronizan

| Evento Calendly | Estado en ERP | Sincronizado | Notas |
|-----------------|---------------|--------------|-------|
| invitee.created | scheduled | ✅ SÍ | Crea/actualiza Appointment |
| invitee.canceled | cancelled | ✅ SÍ | Marca appointment.status='cancelled' |
| invitee.rescheduled | ❌ NO ACTUALIZA | ❌ NO | Evento ignorado → ERP queda desactualizado |

### Qué NO se sincroniza

1. **Cambios de horario (reschedule)** - Evento ignorado
2. **Actualización de datos de paciente** - Si invitee cambia nombre/email en Calendly, ERP no se entera
3. **Eventos creados ANTES de configurar webhook** - No hay sync histórico
4. **Practitioner assignment** - Webhook no incluye practitioner, queda null siempre

### Qué pasa si hay inconsistencias

**Escenario 1: Webhook falla (red, timeout)**
```
Calendly: Cita creada a las 10:00
ERP:      (no recibe webhook) → Cita NO EXISTE
```
**Resultado**: Paciente ve cita en Calendly, doctora NO la ve en ERP (hueco fantasma inverso)

**Escenario 2: Webhook llega 2 veces (retry de Calendly)**
```
Webhook 1: external_id=ABC123 → Appointment.objects.get_or_create() → CREATED
Webhook 2: external_id=ABC123 → Appointment.objects.get_or_create() → FOUND (idempotente)
```
**Resultado**: ✅ Idempotencia funciona (no crea duplicados)

**Escenario 3: Paciente reprograma en Calendly**
```
Calendly: Cita movida de 10:00 → 15:00 (evento invitee.rescheduled)
ERP:      (ignora evento) → Appointment.scheduled_start sigue siendo 10:00
```
**Resultado**: ❌ **DESINCRONIZACIÓN** - ERP muestra horario viejo

**Escenario 4: Cancelación sin cita previa**
```
Calendly: Evento canceled para external_id=XYZ999
ERP:      Appointment.objects.get(external_id=XYZ999) → DoesNotExist
```
**Resultado**: ⚠️ Log warning pero retorna 200 OK (Calendly no reintenta)

---

## 5️⃣ CREACIÓN DE CITAS DESDE ERP (RECEPCIÓN)

### ¿Existe ya algún intento de crear citas en Calendly desde el ERP?

**Respuesta**: ❌ **NO EXISTE NINGÚN CÓDIGO** que llame a la API de Calendly para crear eventos.

### Análisis del endpoint `/book/`

**Archivo**: `apps/web/src/lib/api/booking.ts:93`

```typescript
export async function bookAppointment(
  practitionerId: number,
  payload: BookingPayload
): Promise<any> {
  return apiClient.post(
    `/api/v1/clinical/practitioners/${practitionerId}/book/`,
    payload
  );
}
```

**Búsqueda en backend**:
```bash
$ grep -r "def book" apps/api/
# NO HAY RESULTADOS - Endpoint /book/ NO EXISTE en backend
```

**Conclusión**:
- Frontend llama a `/practitioners/{id}/book/` 
- Backend **NO TIENE este endpoint implementado**
- Si se llama, retorna **404 NOT FOUND**

### ¿Hay código muerto o incompleto?

**Estado**: ✅ **Código muerto identificado**

1. **Frontend: bookAppointment() sin backend**
   - Archivo: `apps/web/src/lib/api/booking.ts`
   - Función existe pero endpoint backend NO
   - **NUNCA SE USÓ**: No hay llamadas a esta función en componentes

2. **Frontend: Ruta /schedule inexistente**
   ```typescript
   // apps/web/src/components/layout/app-layout.tsx:67
   {
     name: t('schedule'), // "New Appointment" - Calendly booking
     href: routes.schedule(locale), // Routes to /schedule
   }
   ```
   - Navegación apunta a /schedule
   - ❌ **Página NO EXISTE** (404 en navegador)

3. **Backend: CALENDLY_API_TOKEN sin uso**
   ```python
   # config/settings.py:334
   CALENDLY_API_TOKEN = os.environ.get('CALENDLY_API_TOKEN', '')
   ```
   - Variable definida
   - **NINGÚN archivo Python la importa**
   - **NINGÚN código la usa**

4. **Comentarios sobre endpoints no implementados**
   ```python
   # apps/clinical/views.py:888
   # - AppointmentViewSet.calendly_sync() (manual endpoint)  ← NO EXISTE
   ```

### Indica claramente el estado de cada componente

| Componente | Estado | Evidencia |
|------------|--------|-----------|
| **API Cliente Calendly (crear eventos)** | ❌ **Nunca se llegó a implementar** | No existe código con `requests.post('https://api.calendly.com/...')` ni uso de CALENDLY_API_TOKEN |
| **Endpoint backend /book/** | ❌ **Nunca se llegó a implementar** | Frontend llama, pero backend no tiene este endpoint |
| **Página /schedule** | ❌ **Nunca se llegó a implementar** | Mencionada en navegación pero 404 en runtime |
| **Sync periódico (daemon)** | ❌ **Nunca se llegó a implementar** | No hay tareas Celery ni cron jobs |
| **Endpoint manual calendly_sync** | ❌ **Nunca se llegó a implementar** | Solo existe comentario en código |
| **Webhook invitee.rescheduled** | ⚠️ **Esto está a medias** | Webhook recibe evento pero lo ignora (no procesa) |
| **Matching de pacientes por nombre** | ❌ **Nunca se llegó a usar** | Solo matching por email/teléfono |

---

## 6️⃣ ALINEACIÓN CON PROJECT_DECISIONS.MD (SECCIÓN 17)

### §17.1: Calendly como motor único de agenda

**Decisión**:
> "Calendly es el único motor de agenda y disponibilidad del sistema. El ERP no gestiona disponibilidad propia. El ERP no crea citas 'solo en local'."

**Análisis**:
- ❌ **DESALINEADO**: Endpoint `/book/` en frontend intenta crear citas en local
- ❌ **DESALINEADO**: Appointment.source='manual' permite citas sin external_id (sin Calendly)
- ✅ **ALINEADO**: Webhook funciona correctamente (Calendly → ERP)

**Riesgo**:
```
Recepción → /book/ (local) → Appointment sin external_id
                           → HUECO FANTASMA (no existe en Calendly)
                           → Doble reserva posible
```

### §17.2: Orígenes de citas soportados

**Decisión**:
> "Pacientes externas: Calendly crea, ERP sincroniza via webhook.  
> Recepción: ERP crea en Calendly via API, solo si Calendly confirma persiste Visita."

**Análisis**:

| Origen | Estado Actual | Alineación |
|--------|---------------|------------|
| **Pacientes (Instagram/web)** | ✅ Calendly → Webhook → ERP | ✅ **ALINEADO** |
| **Recepción (desde ERP)** | ❌ Endpoint /book/ no implementado | ❌ **DESALINEADO** (NO puede crear en Calendly) |

**Conclusión**: Solo funciona flujo Paciente→Calendly. Flujo Recepción→Calendly **NO EXISTE**.

### §17.3: Creación de citas desde el ERP (Recepción)

**Decisión**:
> "Recepción selecciona fecha/hora exacta → ERP crea en Calendly → Si Calendly acepta, ERP persiste Visita. Si Calendly rechaza, NO se guarda nada."

**Análisis**:
- ❌ **DESALINEADO 100%**: NINGÚN CÓDIGO implementa este flujo
- ❌ NO existe llamada a API Calendly para crear eventos
- ❌ NO existe endpoint backend que orqueste esta lógica
- ❌ CALENDLY_API_TOKEN definido pero nunca usado

**Código ausente esperado**:
```python
# Esto NO EXISTE en el código
import requests

def create_calendly_event(practitioner_calendly_url, start_time, patient_email):
    headers = {'Authorization': f'Bearer {settings.CALENDLY_API_TOKEN}'}
    payload = {
        'event_type_uri': practitioner_calendly_url,
        'invitee': {'email': patient_email},
        'start_time': start_time.isoformat()
    }
    response = requests.post('https://api.calendly.com/scheduled_events', 
                             json=payload, headers=headers)
    return response.json()
```

### §17.4: Relación Agenda → Visita → Encounter

**Decisión**:
> "Appointment proviene siempre de Calendly. Una Visita pasa a 'completed' únicamente cuando se crea un Encounter asociado."

**Análisis**:
- ⚠️ **PARCIALMENTE ALINEADO**:
  - ✅ Endpoint `POST /appointments/{id}/attend/` implementa transición atómica (AGENDA_ATTEND_ENDPOINT_COMPLETE.md)
  - ✅ Appointment.source='calendly' existe y se usa en webhook
  - ❌ PERO también permite source='manual' (contradice "siempre de Calendly")

**Contradicción en modelo**:
```python
# apps/clinical/models.py:106
class AppointmentSourceChoices(models.TextChoices):
    CALENDLY = 'calendly', 'Calendly'
    MANUAL = 'manual', 'Manual'  # ← CONTRADICE §17.4
    WEBSITE = 'website', 'Website'
```

### §17.5: Practitioner y configuración de Calendly

**Decisión**:
> "Cada usuario con perfil Practitioner dispone de una URL de Calendly. Esta URL es la que utiliza el ERP para crear citas en nombre de recepción."

**Análisis**:
- ✅ **ALINEADO**: Campo `practitioner.calendly_url` existe y funciona
- ✅ **ALINEADO**: Frontend usa esta URL para widget InlineWidget
- ❌ **DESALINEADO**: Backend NUNCA usa esta URL para crear citas (no hay código)

**Uso real**:
```python
# ACTUAL: Solo frontend para mostrar widget
<InlineWidget url={practitioner.calendly_url} />

# ESPERADO PERO NO EXISTE: Backend debería usarla para crear eventos
create_calendly_event(practitioner.calendly_url, start_time, patient_email)
```

### §17.6: Principios de diseño

**Decisión**:
> "Evitar huecos falsos. Evitar dobles reservas. Calendly agenda, ERP gestiona clínica."

**Análisis de riesgos**:

| Riesgo | Mitigado | Explicación |
|--------|----------|-------------|
| **Huecos falsos** | ❌ NO | Endpoint /book/ local puede crear citas sin validar Calendly |
| **Dobles reservas** | ⚠️ PARCIAL | Webhook es idempotente, pero si llega tarde y recepción crea manual → duplicado |
| **Calendly = fuente de verdad** | ⚠️ PARCIAL | Solo si TODO pasa por webhook. Citas manuales rompen principio |

---

## 📊 TABLA RESUMEN DE ALINEACIÓN

| Decisión PROJECT_DECISIONS.md | Implementado | Estado | Riesgo |
|--------------------------------|--------------|--------|--------|
| §17.1: Calendly único motor | ❌ NO | Endpoint /book/ local contradice | 🔴 ALTO |
| §17.2: Pacientes → Calendly → ERP | ✅ SÍ | Webhook funcional | 🟢 BAJO |
| §17.2: Recepción → ERP → Calendly | ❌ NO | Código no existe | 🔴 CRÍTICO |
| §17.3: Validar con Calendly antes de persistir | ❌ NO | No hay llamada a API | 🔴 CRÍTICO |
| §17.4: Appointment siempre de Calendly | ⚠️ PARCIAL | También permite source='manual' | 🟠 MEDIO |
| §17.5: Usar practitioner.calendly_url | ⚠️ PARCIAL | Solo frontend, backend no | 🟠 MEDIO |
| §17.6: Evitar huecos fantasma | ❌ NO | Posible con /book/ local | 🔴 ALTO |

**Leyenda**:
- ✅ **ALINEADO**: Implementación cumple decisión
- ⚠️ **PARCIALMENTE ALINEADO**: Cumple en parte, con limitaciones
- ❌ **DESALINEADO**: No implementado o contradice decisión

---

## 🔍 LISTA DE PUNTOS A REVISAR (FASE FUTURA)

### Prioridad CRÍTICA 🔴

1. **Implementar flujo Recepción → Calendly**
   - Crear cliente API Calendly (usando CALENDLY_API_TOKEN)
   - Implementar endpoint `/practitioners/{id}/book-via-calendly/`
   - Flujo: Validar slot → Crear en Calendly → Si OK, crear Appointment

2. **Eliminar o bloquear endpoint /book/ local**
   - Decisión: ¿Eliminar o hacer que llame a Calendly internamente?
   - Si se mantiene, debe llamar a API Calendly SIEMPRE

3. **Restringir Appointment.source**
   - ¿Eliminar source='manual' completamente?
   - O agregar validación: "Si source!='calendly', require external_id no nulo"

4. **Implementar sync periódico (fallback)**
   - Tarea Celery cada 15 min: consultar eventos Calendly recientes
   - Comparar con Appointments en ERP
   - Crear/actualizar los que faltan

### Prioridad ALTA 🟠

5. **Soportar evento invitee.rescheduled**
   - Actualmente ignorado
   - Debe actualizar scheduled_start/end en Appointment

6. **Implementar endpoint manual de sync**
   - `POST /appointments/{id}/sync-from-calendly/`
   - Para reintentar eventos perdidos

7. **Mejorar matching de pacientes**
   - Normalizar email (lowercase, trim)
   - Normalizar teléfono E.164 correctamente
   - Detectar duplicados potenciales

8. **Agregar validación de consentimientos**
   - Webhook crea Patient sin consents
   - Mostrar warning en ERP: "Paciente pendiente de consentimientos"

### Prioridad MEDIA 🟡

9. **Sincronizar practitioner_id desde Calendly**
   - ¿Cómo correlacionar event de Calendly con practitioner en ERP?
   - Opciones:
     a) Agregar campo personalizado en Calendly (custom_questions)
     b) Inferir desde practitioner.calendly_url (matching de URL)

10. **Actualizar datos de paciente en webhook**
    - Si invitee.name cambió, actualizar Patient.first_name/last_name
    - Agregar timestamp de última sync

11. **Crear página /schedule funcional**
    - Actualmente 404
    - Debe mostrar CalendlyEmbed con practitioner.calendly_url

12. **Agregar monitoreo de webhooks**
    - Dashboard: eventos recibidos, errores, latencia
    - Alertas si webhook no llega en X tiempo

### Prioridad BAJA 🔵

13. **Agregar tests de integración con Calendly**
    - Mock API Calendly
    - Test crear evento → webhook → Appointment creado

14. **Documentar flujo completo en diagrama**
    - Secuencia: Paciente → Calendly → Webhook → ERP
    - Secuencia: Recepción → ERP → Calendly → Webhook → ERP (cuando se implemente)

15. **Optimizar gestión de duplicados**
    - Herramienta admin: "Merge patients"
    - Detectar duplicados por fuzzy matching

---

## 🛑 ACLARACIONES EXPLÍCITAS

### Lo que NO está claro (sin suposiciones)

1. **¿Cómo se debe correlacionar practitioner_id desde webhook?**
   - Webhook de Calendly NO incluye practitioner
   - ¿Hay forma de inferirlo? ¿Custom questions en Calendly?
   - **No está claro** en código actual

2. **¿Por qué CALENDLY_API_TOKEN está definido pero nunca usado?**
   - Variable existe desde FASE 4.0
   - **No está claro** si se pensó implementar y se abandonó
   - O si es placeholder para desarrollo futuro

3. **¿Endpoint /book/ es código viejo o planeado?**
   - Frontend lo llama pero backend NO existe
   - **No está claro** si era parte de plan antiguo (pre-decisión §17)
   - O si es stub para implementación futura

4. **¿Qué hacer con Appointments sin external_id?**
   - Si source='manual' y external_id=null, ¿es válido?
   - **No está claro** si se deben permitir o bloquear

---

## 📚 ARCHIVOS DE REFERENCIA

### Backend

| Archivo | Contenido clave |
|---------|-----------------|
| `apps/integrations/views.py` | Webhook Calendly (invitee.created, invitee.canceled) |
| `apps/clinical/views.py` | _process_calendly_sync() (línea 882) |
| `apps/clinical/models.py` | Appointment, AppointmentSourceChoices |
| `apps/authz/models.py` | Practitioner.calendly_url (línea 267) |
| `config/settings.py` | CALENDLY_* variables (líneas 241-334) |
| `tests/test_calendly_webhook.py` | Tests verificación firma webhook |

### Frontend

| Archivo | Contenido clave |
|---------|-----------------|
| `apps/web/src/components/calendly-embed.tsx` | Widget InlineWidget de Calendly |
| `apps/web/src/lib/api/booking.ts` | bookAppointment() (llama a endpoint inexistente) |
| `apps/web/src/components/layout/app-layout.tsx` | Navegación a /schedule (404) |

### Documentación

| Archivo | Contenido clave |
|---------|-----------------|
| `PROJECT_DECISIONS.md` | §17: Decisiones canónicas sobre Agenda y Calendly |
| `FASE_4_0_CALENDLY_CONFIG.md` | Implementación practitioner.calendly_url |
| `AGENDA_ATTEND_ENDPOINT_COMPLETE.md` | Endpoint atómico attend() |

---

## ✅ CONCLUSIÓN

### Resumen de situación

**LO QUE FUNCIONA**:
1. ✅ Webhook Calendly → ERP (invitee.created, invitee.canceled)
2. ✅ Matching de pacientes por email/teléfono
3. ✅ Idempotencia en webhook (no duplica Appointments)
4. ✅ Campo practitioner.calendly_url funcional en frontend

**LO QUE FALTA (CRÍTICO)**:
1. ❌ Flujo Recepción → Calendly (NO EXISTE código)
2. ❌ Usar CALENDLY_API_TOKEN (definido pero nunca usado)
3. ❌ Sync periódico (sin fallback para webhooks perdidos)
4. ❌ Soporte para invitee.rescheduled (eventos ignorados)

**RIESGOS REALES**:
1. 🔴 **Huecos fantasma**: Si se implementa /book/ local sin validar Calendly
2. 🔴 **Pérdida de eventos**: Si webhook falla, no hay recovery
3. 🟠 **Desincronización**: Cambios de horario en Calendly no se propagan
4. 🟠 **Pacientes sin identificar**: Webhook crea patients con identity_confidence='low' y sin consents

### Estado vs. PROJECT_DECISIONS.md

- **50% implementado** (solo flujo Paciente → Calendly → ERP)
- **50% pendiente** (flujo Recepción → ERP → Calendly no existe)
- **Contradicciones**: Appointment.source='manual' contradice "Calendly único motor"

### Próximos pasos recomendados (solo análisis, NO soluciones)

1. Decidir si implementar flujo Recepción→Calendly o eliminarlo de decisiones
2. Evaluar si mantener/eliminar código muerto (endpoint /book/, ruta /schedule)
3. Definir estrategia para sync periódico (¿cada cuánto? ¿qué ventana temporal?)
4. Clarificar rol de CALENDLY_API_TOKEN (¿se va a usar o eliminar?)

**FIN DE AUDITORÍA** ✅
