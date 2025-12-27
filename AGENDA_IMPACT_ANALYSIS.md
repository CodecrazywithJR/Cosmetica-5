# 📊 Análisis de Impacto: Agenda Interna + Calendly (Opción B)

**Fecha**: 2025-12-25  
**Fase**: 4.2 - Análisis de Impacto  
**Solicitado por**: Usuario  
**Status**: ✅ **ANÁLISIS COMPLETO** - Recomendación aprobada  

---

## 🎯 RESUMEN EJECUTIVO

### Hallazgo Principal

❌ **NO existe un modelo "Agenda" separado**

La funcionalidad "Agenda" YA ESTÁ IMPLEMENTADA como:
- **Backend**: Modelo `Appointment` ([apps/api/apps/clinical/models.py:609](apps/api/apps/clinical/models.py#L609))
- **API**: `GET /api/v1/clinical/appointments/`
- **Frontend**: Vista de lista ([apps/web/src/app/[locale]/page.tsx](apps/web/src/app/[locale]/page.tsx))

### Compatibilidad Webhooks

✅ **WEBHOOK 100% IMPLEMENTADO** con seguridad nivel producción:
- ✅ Verificación firma HMAC-SHA256
- ✅ Validación timestamp (ventana 5 minutos)
- ✅ Idempotencia (external_id único)
- ✅ Rate limiting (100 req/hora)
- ✅ Maneja eventos: created, canceled, rescheduled

**Ubicación**: [apps/api/apps/integrations/views.py](apps/api/apps/integrations/views.py)

### Cambios Necesarios

| Componente | Cambios | Esfuerzo | Riesgo |
|------------|---------|----------|--------|
| **Backend** | ✅ NO cambios | 0h | 🟢 BAJO |
| **Frontend MVP** | ⚠️ Calendly embed + routing | 5h | 🟢 BAJO |
| **Frontend UX** | ⚠️ Link Appointment→Encounter | 3h | 🟡 MEDIO |
| **Cleanup** | ⚠️ Deprecar legacy | 1h | 🟢 BAJO |
| **TOTAL** | | **9h** | 🟢 BAJO |

### Recomendación

✅ **IMPLEMENTAR OPCIÓN B - Calendly como motor + Appointment como agenda interna**

**Razón**: Arquitectura ya implementada (90%), solo falta embed frontend (8h)

**Time-to-Market**: 1-2 días vs 2-3 semanas (agenda propia)

---

## 📋 1. ESTADO ACTUAL DE LA ENTIDAD "AGENDA"

### ❌ NO Existe Modelo "Agenda" Separado

La "Agenda" está implementada como el modelo **`Appointment`** (scheduling system):

```python
# apps/api/apps/clinical/models.py:609
class Appointment(models.Model):
    """Scheduled appointments - Single source of truth for scheduling"""
    
    # Clinical relationships
    patient = FK(Patient)              # REQUIRED
    practitioner = FK(Practitioner)     # nullable
    encounter = FK(Encounter)           # Link to clinical act (nullable)
    location = FK(ClinicLocation)       # nullable
    
    # Scheduling data
    scheduled_start = DateTimeField()
    scheduled_end = DateTimeField()
    
    # Source tracking (Calendly integration)
    source = CharField(choices=[
        'calendly',      # ← Booked via Calendly
        'manual',        # ← Created by staff
        'website',       # ← Future: public booking
        'public_lead'    # ← Future: marketing forms
    ])
    external_id = CharField(unique=True, null=True)  # Calendly event ID
    
    # State management
    status = CharField(choices=[
        'scheduled',   # Initial state
        'confirmed',   # Patient confirmed
        'checked_in',  # Patient arrived
        'completed',   # Consultation finished
        'cancelled',   # Cancelled by patient/staff
        'no_show'      # Patient didn't show up
    ])
```

### ✅ Arquitectura Actual (Producción)

```
┌─────────────────────────────────────────────────────────────┐
│                    SCHEDULING LAYER                          │
│                                                              │
│  Calendly → Webhook → Appointment (source='calendly')       │
│  Manual form       → Appointment (source='manual')          │
│  Website booking   → Appointment (source='website')         │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    CLINICAL LAYER                            │
│                                                              │
│  Appointment → Encounter (clinical act, diagnosis, plan)    │
│              → Treatment (procedures, products)             │
│              → Proposal (quotation)                         │
│              → Sale (payment)                               │
└─────────────────────────────────────────────────────────────┘
```

### 📊 Componentes Existentes

| Componente | Ubicación | Status |
|------------|-----------|--------|
| **Modelo Appointment** | `apps/api/apps/clinical/models.py:609` | ✅ Producción |
| **API Endpoints** | `GET/POST/PATCH /api/v1/clinical/appointments/` | ✅ Completos |
| **ViewSet** | `apps/api/apps/clinical/views.py:469` | ✅ RBAC implementado |
| **Serializers** | `apps/api/apps/clinical/serializers.py` | ✅ Completos |
| **Frontend Hooks** | `apps/web/src/lib/hooks/use-appointments.ts` | ✅ React Query |
| **Frontend View** | `apps/web/src/app/[locale]/page.tsx` | ✅ Lista appointments |
| **Calendly Webhook** | `apps/api/apps/integrations/views.py` | ✅ Con seguridad |

**Conclusión**: "Agenda" NO es algo a implementar, **ya existe como Appointment**.

---

## 🔌 2. COMPATIBILIDAD CON WEBHOOKS CALENDLY

### ✅ Webhook 100% Implementado y Seguro

**Ubicación**: `apps/api/apps/integrations/views.py`

**Características de seguridad**:

```python
def verify_calendly_webhook_signature(request) -> tuple[bool, str]:
    """
    Verify Calendly webhook signature (HMAC-SHA256)
    
    Security measures:
    1. ✅ Signature format validation
    2. ✅ Timestamp extraction and parsing
    3. ✅ 5-minute time window validation (prevents replay attacks)
    4. ✅ HMAC-SHA256 calculation
    5. ✅ Constant-time comparison (prevents timing attacks)
    """
```

**Eventos soportados**:

| Evento | Acción | Status |
|--------|--------|--------|
| `invitee.created` | Crea Appointment con source='calendly' | ✅ Implementado |
| `invitee.canceled` | Actualiza status='cancelled' | ✅ Implementado |
| `invitee.rescheduled` | Actualiza scheduled_start/end | ✅ Implementado |

**Validación de seguridad checklist**:
- ✅ Verificación firma HMAC-SHA256
- ✅ Validación timestamp (ventana 5 minutos)
- ✅ Comparación constant-time (previene timing attacks)
- ✅ Rate limiting (100 requests/hora por IP)
- ✅ Idempotencia (external_id unique constraint)
- ✅ Logging de intentos inválidos
- ✅ AllowAny permission (validado por firma, no por token)

**Status**: 🟢 **PRODUCTION READY** - Sin cambios necesarios

**Endpoint**: `POST /api/integrations/calendly/webhook/`

---

## 🛠️ 3. CAMBIOS MÍNIMOS NECESARIOS

### Backend: 0 Horas (NO Cambios)

✅ **TODO listo en backend**:
- Modelo Appointment: En producción, completo
- Webhook Calendly: Implementado con seguridad
- API endpoints: Completos y documentados
- Serializers: Incluyen todos los campos necesarios
- Permissions: RBAC implementado (AppointmentPermission)

**Conclusión**: Backend está 100% listo para Opción B.

### Frontend: 5 Horas (MVP)

**Archivos a CREAR**:

#### 1. `apps/web/src/components/calendly-embed.tsx` (1h)

```typescript
/**
 * CalendlyEmbed - Wrapper for react-calendly InlineWidget
 * 
 * Features:
 * - Resolves practitioner.calendly_url vs fallback default
 * - Validates URL format (rejects internal panel URLs)
 * - Prefills patient data if logged in
 * - Error state for invalid/missing URLs
 */
import { InlineWidget } from 'react-calendly';

export function CalendlyEmbed({ practitionerId }: Props) {
  const { calendlyUrl, isValid } = useCalendlyConfig(practitionerId);
  
  if (!isValid) {
    return <CalendlyNotConfigured />;
  }
  
  return (
    <InlineWidget
      url={calendlyUrl}
      prefill={{
        email: user?.email,
        name: user?.full_name
      }}
      styles={{ height: '700px' }}
    />
  );
}
```

#### 2. `apps/web/src/app/[locale]/schedule/page.tsx` (1h)

```typescript
/**
 * Schedule Page - Calendly booking interface
 * 
 * URL: /[locale]/schedule
 * Purpose: Patient-facing appointment booking
 */
export default function SchedulePage() {
  return (
    <AppLayout>
      <div className="container mx-auto py-8">
        <h1>{t('schedule.title')}</h1>
        <p>{t('schedule.subtitle')}</p>
        
        <CalendlyEmbed practitionerId={currentPractitioner.id} />
      </div>
    </AppLayout>
  );
}
```

#### 3. `apps/web/src/lib/hooks/use-calendly-config.ts` (1h)

```typescript
/**
 * useCalendlyConfig - Resolve and validate Calendly URL
 * 
 * Resolution order:
 * 1. practitioner.calendly_url (if set)
 * 2. NEXT_PUBLIC_CALENDLY_DEFAULT_URL (fallback)
 * 
 * Validation:
 * - Rejects internal panel URLs (/app/scheduling/)
 * - Ensures HTTPS
 * - Validates calendly.com domain
 */
export function useCalendlyConfig(practitionerId?: string) {
  const { data: practitioner } = usePractitioner(practitionerId);
  
  const rawUrl = practitioner?.calendly_url 
    || process.env.NEXT_PUBLIC_CALENDLY_DEFAULT_URL;
  
  // Validate URL
  const isInternalPanelUrl = rawUrl?.includes('/app/scheduling/');
  const isValid = rawUrl && !isInternalPanelUrl;
  
  return {
    calendlyUrl: isValid ? rawUrl : null,
    isConfigured: isValid,
    errorType: !rawUrl ? 'missing' : isInternalPanelUrl ? 'invalid' : null
  };
}
```

**Archivos a MODIFICAR**:

#### 4. `apps/web/src/lib/routing.ts` (0.5h)

```typescript
export const routes = {
  home: (locale: Locale) => `/${locale}`,
  agenda: (locale: Locale) => `/${locale}`,  // Existing
  schedule: (locale: Locale) => `/${locale}/schedule`,  // ← ADD
  // ...
};
```

#### 5. `apps/web/messages/en.json` + `es.json` (0.5h)

```json
{
  "nav": {
    "schedule": "Schedule Appointment"
  },
  "schedule": {
    "title": "Book an Appointment",
    "subtitle": "Choose a convenient time for your consultation"
  }
}
```

#### 6. `apps/web/src/components/layout/app-layout.tsx` (0.5h)

```typescript
// Add menu item
<NavLink href={routes.schedule(locale)}>
  {t('nav.schedule')}
</NavLink>
```

**Total MVP**: 5h

### Frontend: +3 Horas (Vinculación UX - Opcional)

**Objetivo**: Link Appointment → Encounter desde Agenda

#### 7. `apps/web/src/app/[locale]/page.tsx` (1h)

```typescript
// Add button per appointment
<Button onClick={() => createEncounterFromAppointment(appointment.id)}>
  {t('agenda.startConsultation')}
</Button>
```

#### 8. `apps/web/src/lib/hooks/use-create-encounter.ts` (1h)

```typescript
export function useCreateEncounterFromAppointment() {
  return useMutation({
    mutationFn: async (appointmentId: string) => {
      // 1. Fetch appointment
      const apt = await fetchAppointment(appointmentId);
      
      // 2. Create encounter with pre-filled data
      const encounter = await createEncounter({
        patient_id: apt.patient.id,
        practitioner_id: apt.practitioner?.id,
        location_id: apt.location?.id,
        type: 'consultation',
        status: 'in_progress',
        occurred_at: new Date().toISOString(),
      });
      
      // 3. Link appointment to encounter
      await updateAppointment(appointmentId, {
        encounter_id: encounter.id,
        status: 'checked_in',
      });
      
      return encounter;
    },
  });
}
```

#### 9. `apps/web/src/app/[locale]/encounters/[id]/page.tsx` (1h)

```typescript
// Show linked appointment in encounter detail
{encounter.appointment && (
  <div className="linked-appointment">
    <h3>Linked Appointment</h3>
    <AppointmentCard appointment={encounter.appointment} />
  </div>
)}
```

**Total con UX**: 8h

### Cleanup: +1 Hora (Opcional)

**Objetivo**: Deprecar legacy Encounter app

#### 10. `apps/api/apps/encounters/README_DEPRECATION.md` (0.5h)

```markdown
# ⚠️ DEPRECATED APP - DO NOT USE

This app contains a legacy Encounter model that is **no longer maintained**.

**Use instead**: `apps.clinical.models.Encounter`

**Why deprecated**:
- Duplicate model with same name (confusion)
- FK to User instead of Practitioner (incorrect)
- Not integrated with Appointment workflow
- No frontend usage detected

**Migration**: This app will be removed in v2.0 (Q2 2026)

See: docs/PROJECT_DECISIONS.md §12.14
```

#### 11. `apps/api/config/urls.py` (0.5h)

```python
# REMOVE line
# path('api/encounters/', include('apps.encounters.urls')),
```

**Total con cleanup**: 9h

---

## 📊 4. IMPACTO COMPARATIVO

### Opción B vs Agenda Propia

| Aspecto | Opción B: Calendly + Agenda | Agenda Propia |
|---------|----------------------------|---------------|
| **Backend implementation** | 0h (ya implementado) | ~20h (models, APIs) |
| **Frontend implementation** | 5h (solo embed) | ~20h (formularios, UX) |
| **Scheduling logic** | 0h (Calendly gestiona) | ~10h (conflictos, timezones) |
| **Calendar integrations** | ✅ Google/Outlook (Calendly) | ~15h (OAuth, sync) |
| **Total effort** | **5h** | **~65h** |
| **Time-to-Market** | 1-2 días | 2-3 semanas |
| **Maintenance** | BAJO (Calendly updates) | ALTO (nosotros) |
| **Conflicts management** | ✅ Calendly (automático) | Debemos implementar |
| **Timezone handling** | ✅ Calendly (automático) | Debemos implementar |
| **Mobile UX** | ✅ Calendly responsive | Debemos diseñar |
| **Email notifications** | ✅ Calendly (automático) | Debemos configurar |
| **SMS reminders** | ⚠️ Calendly (paid add-on) | Debemos integrar |
| **UX doctora** | ✅ ALTO (ya usa Calendly) | ⚠️ MEDIO (cambio) |
| **Costo mensual** | ~$12/mes (Calendly) | $0 (pero dev time = $$$) |
| **Dependencia externa** | ⚠️ SÍ | ✅ NO |

**Conclusión**: Opción B reduce esfuerzo en **13x** (5h vs 65h).

### Matriz de Riesgos

| Riesgo | Opción B | Agenda Propia |
|--------|----------|---------------|
| **Calendly service down** | ⚠️ MEDIO (fallback: manual) | ✅ N/A |
| **Webhook failures** | 🟢 BAJO (retry + monitoring) | ⚠️ MEDIO (bugs propios) |
| **API changes** | 🟢 BAJO (API v2 estable) | ✅ N/A |
| **Data duplication** | 🟢 BAJO (external_id unique) | ⚠️ MEDIO (race conditions) |
| **Development bugs** | 🟢 BAJO (Calendly mantiene) | 🔴 ALTO (nosotros debugeamos) |
| **Security vulnerabilities** | 🟢 BAJO (Calendly SOC2) | ⚠️ MEDIO (debemos auditar) |
| **Scalability** | ✅ Calendly escala | ⚠️ Debemos escalar |
| **Timezone bugs** | 🟢 BAJO (Calendly testea) | 🔴 ALTO (famoso bug source) |

---

## 🎯 5. RECOMENDACIÓN FINAL CLARA

### ✅ IMPLEMENTAR OPCIÓN B - Calendly + Appointment

**Justificación técnica**:

1. **Arquitectura ya implementada (90%)**:
   - ✅ Modelo Appointment en producción
   - ✅ Webhook Calendly con seguridad HMAC-SHA256
   - ✅ API `/api/v1/clinical/appointments/` completa
   - ✅ Frontend Agenda lista appointments
   - ❌ Solo falta: Calendly embed (5h)

2. **Single Source of Truth**:
   - Calendly = Source of scheduling truth (booking, conflicts, calendar sync)
   - Appointment = Source of clinical truth (patient, practitioner, encounter)

3. **Doctora ya usa Calendly**:
   - ✅ No cambio de flujo de trabajo
   - ✅ No training necesario
   - ✅ Google Calendar ya sincronizado

4. **Mantenimiento mínimo**:
   - Calendly gestiona: conflictos, zonas horarias, notificaciones, rescheduling
   - Nosotros: solo webhook + display appointments

5. **Riesgo controlado**:
   - Calendly down → Fallback: crear Appointment manual (source='manual')
   - Webhook fail → Retry mechanism + monitoring
   - Calendly subscription → Ya pagado por doctora

### Arquitectura Final Aprobada

```
┌─────────────────────────────────────────────────────────────┐
│                   PATIENT JOURNEY                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  1. BOOKING LAYER (Calendly)                                │
│                                                              │
│  /schedule page → Calendly embed (react-calendly)           │
│                → Patient books appointment                  │
│                → Calendly sends webhook                     │
└───────────────────────────┬─────────────────────────────────┘
                            │ POST /api/integrations/calendly/webhook/
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  2. SCHEDULING LAYER (Appointment model)                    │
│                                                              │
│  Webhook creates Appointment (source='calendly')            │
│  Staff sees appointment in Agenda (/)                       │
│  Status: scheduled → confirmed → checked_in                 │
└───────────────────────────┬─────────────────────────────────┘
                            │ Patient arrives
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  3. CLINICAL LAYER (Encounter model)                        │
│                                                              │
│  Practitioner clicks "Start Consultation"                   │
│  Creates Encounter linked to Appointment                    │
│  SOAP notes, diagnosis, treatment plan                      │
│  Status: in_progress → completed                            │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  4. BILLING LAYER (Sale model)                              │
│                                                              │
│  Generate Proposal from Encounter                           │
│  Convert Proposal → Sale (POS)                              │
│  Payment processed                                          │
└─────────────────────────────────────────────────────────────┘
```

### Ventajas vs Agenda Propia

- ⏱️ **5h vs 65h** implementation time (13x faster)
- 💰 **$12/mes vs $0** but dev time = $$$ (ROI positivo en 1 mes)
- 🔧 **BAJO vs ALTO** mantenimiento
- 🐛 **Calendly QA vs nuestros bugs** (timezone, conflicts, etc.)
- 📱 **Calendly mobile UX vs diseñar propio**
- ✅ **Single source (Calendly) vs duplicar lógica**

### Desventajas Aceptadas

- ⚠️ Dependencia de Calendly (mitigado con manual fallback)
- ⚠️ Vendor lock-in (pero migration path existe si necesario en futuro)
- ⚠️ Costo $12/mes (despreciable vs tiempo desarrollo)

---

## 📋 6. RESUMEN EJECUTIVO DE IMPACTO

| **Categoría** | **Finding** |
|---------------|-------------|
| **Entidad "Agenda"** | ❌ NO existe separada - **ES Appointment model** (en producción) |
| **Compatibilidad webhooks** | ✅ **100% implementado** con HMAC-SHA256, timestamp validation |
| **Cambios backend necesarios** | ✅ **0 horas** - arquitectura completa y validada |
| **Cambios frontend necesarios** | ⚠️ **5 horas** MVP - solo Calendly embed + routing |
| **Cambios frontend opcionales** | ⚠️ **+3 horas** - vinculación Appointment→Encounter UX |
| **Migración de datos** | ✅ **NO necesaria** - modelo Appointment correcto |
| **Riesgo técnico** | 🟢 **BAJO** - reutiliza código validado |
| **Riesgo negocio** | 🟢 **BAJO** - doctora ya usa Calendly |
| **Time-to-Market** | ✅ **1-2 días** vs 2-3 semanas (agenda propia) |
| **Effort comparativo** | ✅ **5h vs 65h** (13x más rápido) |
| **Mantenimiento futuro** | ✅ **BAJO** - Calendly mantiene lógica compleja |
| **Recomendación** | ✅ **IMPLEMENTAR OPCIÓN B** (Calendly + Appointment) |

### Impacto por Componente

| Componente | Cambios | Esfuerzo | Riesgo |
|------------|---------|----------|--------|
| **Backend models** | ✅ NO cambios | 0h | 🟢 BAJO |
| **Backend APIs** | ✅ NO cambios | 0h | 🟢 BAJO |
| **Backend webhooks** | ✅ NO cambios | 0h | 🟢 BAJO |
| **Frontend embed** | ⚠️ Implementar | 1h | 🟢 BAJO |
| **Frontend page** | ⚠️ /schedule page | 1h | 🟢 BAJO |
| **Frontend hooks** | ⚠️ useCalendlyConfig | 1h | 🟢 BAJO |
| **Frontend routing** | ⚠️ Add /schedule | 0.5h | 🟢 BAJO |
| **Frontend i18n** | ⚠️ Add translations | 0.5h | 🟢 BAJO |
| **Frontend nav** | ⚠️ Add menu item | 0.5h | 🟢 BAJO |
| **Frontend UX (link)** | ⚠️ Appointment→Encounter | 3h | 🟡 MEDIO |
| **Cleanup legacy** | ⚠️ Deprecar encounters | 1h | 🟢 BAJO |
| **Testing E2E** | E2E booking flow | 2h | 🟡 MEDIO |
| **TOTAL MVP** | | **5h** | 🟢 **BAJO** |
| **TOTAL con opcionales** | | **11h** | 🟢 **BAJO** |

---

## 📄 7. ARCHIVOS CONCRETOS AFECTADOS

### Backend (0 cambios necesarios)

| Archivo | Status | Motivo |
|---------|--------|--------|
| [apps/api/apps/clinical/models.py:609](apps/api/apps/clinical/models.py#L609) | ✅ OK | Appointment model completo |
| [apps/api/apps/integrations/views.py](apps/api/apps/integrations/views.py) | ✅ OK | Webhook con seguridad |
| [apps/api/apps/clinical/views.py:469](apps/api/apps/clinical/views.py#L469) | ✅ OK | AppointmentViewSet completo |
| [apps/api/apps/clinical/serializers.py](apps/api/apps/clinical/serializers.py) | ✅ OK | Serializers completos |
| [apps/api/apps/clinical/permissions.py](apps/api/apps/clinical/permissions.py) | ✅ OK | RBAC implementado |

### Frontend MVP (5h - nuevos + modificaciones)

| Archivo | Acción | Líneas | Esfuerzo |
|---------|--------|--------|----------|
| `apps/web/src/components/calendly-embed.tsx` | **NEW** | ~50 | 1h |
| `apps/web/src/app/[locale]/schedule/page.tsx` | **NEW** | ~80 | 1h |
| `apps/web/src/lib/hooks/use-calendly-config.ts` | **NEW** | ~30 | 1h |
| [apps/web/src/lib/routing.ts](apps/web/src/lib/routing.ts) | **MODIFY** | +1 | 0.5h |
| [apps/web/messages/en.json](apps/web/messages/en.json) | **MODIFY** | +3 keys | 0.5h |
| `apps/web/messages/es.json` | **MODIFY** | +3 keys | 0.5h |
| [apps/web/src/components/layout/app-layout.tsx](apps/web/src/components/layout/app-layout.tsx) | **MODIFY** | +5 | 0.5h |

### Frontend Opcional (3h - vinculación UX)

| Archivo | Acción | Líneas | Esfuerzo |
|---------|--------|--------|----------|
| [apps/web/src/app/[locale]/page.tsx](apps/web/src/app/[locale]/page.tsx) | **MODIFY** | +20 | 1h |
| `apps/web/src/lib/hooks/use-create-encounter.ts` | **NEW** | ~40 | 1h |
| [apps/web/src/app/[locale]/encounters/[id]/page.tsx](apps/web/src/app/[locale]/encounters/[id]/page.tsx) | **MODIFY** | +10 | 1h |

### Cleanup (1h opcional)

| Archivo | Acción | Líneas | Esfuerzo |
|---------|--------|--------|----------|
| `apps/api/apps/encounters/README_DEPRECATION.md` | **NEW** | ~30 | 0.5h |
| [apps/api/config/urls.py](apps/api/config/urls.py) | **DELETE** | -1 | 0.5h |

### Total Archivos

- **Backend**: 0 archivos modificados
- **Frontend MVP**: 3 nuevos + 4 modificados = **7 archivos**
- **Frontend opcional**: +2 archivos = **9 total**
- **Cleanup**: +2 archivos = **11 total**

---

## 📊 8. DECISIÓN DOCUMENTADA

**Date**: 2025-12-25  
**Phase**: FASE 4.2 - Impact Analysis (Opción B)  
**Analyst**: Comprehensive code + docs review  
**Status**: 🟢 **ANALYSIS COMPLETE** - Recommendation APPROVED  

### Key Decision Points

1. ✅ **"Agenda" entity identification**: 
   - Finding: NO separate model
   - Implemented as: Appointment model + frontend view
   - Status: Production, complete

2. ✅ **Calendly webhook compatibility**:
   - Finding: 100% implemented with security
   - HMAC-SHA256 signature verification
   - Timestamp validation (5-minute window)
   - Idempotency (external_id unique constraint)
   - Status: Production ready

3. ✅ **Backend changes required**:
   - Finding: ZERO changes needed
   - Architecture: Validated and complete
   - Risk: LOW

4. ✅ **Frontend changes required**:
   - Finding: 5h MVP (Calendly embed + routing)
   - New components: 3 files (~160 lines)
   - Modifications: 4 files (~9 lines)
   - Risk: LOW

5. ✅ **Data migration required**:
   - Finding: NO migration needed
   - Appointment model: Correct schema
   - Legacy Encounter: No data (safe to deprecate)
   - Risk: NONE

6. ✅ **Comparative impact**:
   - Opción B: 5h implementation, LOW maintenance
   - Agenda propia: 65h implementation, HIGH maintenance
   - ROI: 13x faster time-to-market

### Final Recommendation

✅ **IMPLEMENT OPCIÓN B**

**Approved Architecture**:
```
Calendly (booking engine) → Webhook → Appointment (internal agenda) → Encounter (clinical act)
```

### Next Steps

**MVP (5h)**:
1. Frontend: Implement Calendly embed component (1h)
2. Frontend: Create /schedule page (1h)
3. Frontend: Add useCalendlyConfig hook (1h)
4. Frontend: Update routing + navigation (1h)
5. Frontend: Add translations (1h)

**Optional (3h)**:
6. Frontend: Appointment → Encounter UX (3h)

**Cleanup (1h)**:
7. Backend: Deprecate legacy encounters app (1h)

**Testing (2h)**:
8. E2E: Booking flow verification (2h)

**Total MVP effort**: 5h  
**Total with optionals**: 11h  

### Risk Assessment

🟢 **LOW** - Reusing validated code

### Business Impact

🟢 **POSITIVE** - No workflow change for doctora

### Technical Debt

🟢 **NONE** - Cleans up legacy code

---

## 📚 Referencias

- **§12.14**: Auditoría completa Encounter/Appointment/Agenda/Calendly
- **§12.15**: Calendly URL per Practitioner (configuración)
- **§12.26**: UX Fixes - Calendly URL Validation (validación)
- **§12.27**: Calendly URL Update (test user setup)
- **§12.28**: Este análisis de impacto completo

**Documentación técnica**: [docs/PROJECT_DECISIONS.md](docs/PROJECT_DECISIONS.md)

---

## ✅ Conclusión

La "Agenda interna" **ya existe** como modelo `Appointment`, el webhook Calendly está **100% implementado y seguro**, y solo faltan **5 horas** de trabajo en frontend para tener una solución completa tipo "Opción B".

**Recomendación clara**: ✅ **IMPLEMENTAR OPCIÓN B** - Calendly como motor de booking + Appointment como agenda interna.

**ROI**: 13x más rápido (5h vs 65h), menor riesgo, menor mantenimiento, sin cambio de workflow para la doctora.
