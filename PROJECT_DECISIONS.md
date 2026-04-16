# PROJECT_DECISIONS.md
ERP Clínico – Documento Canónico de Decisiones

## 0. PROPÓSITO DE ESTE DOCUMENTO

Este documento define qué es el ERP clínico y cómo debe comportarse, tanto a nivel funcional como técnico.

Es la fuente única de verdad para:
- decisiones de producto
- reglas de negocio
- modelo clínico
- principios de UX
- stack técnico
- límites y alcance del sistema

Regla absoluta:
- NO contiene código
- NO contiene comandos
- NO explica cómo se arregló nada
- NO es un diario de desarrollo

Las decisiones aquí descritas están cerradas, no se reabren y prevalecen sobre cualquier otro documento o conversación.

---

## 1. CONTEXTO GENERAL DEL PROYECTO

Estamos construyendo un ERP clínico serio para una doctora.

### Uso previsto
- Uso local en el ordenador de la doctora
- Ejecución mediante contenedores Docker en local
- Funcionamiento offline-first
- Ordenador principal: PC ACER con Windows
- Entrega prevista en USB instalable (conceptual)

No existe despliegue cloud productivo ni acceso remoto para pacientes.

### Usuario final
- La doctora NO es técnica
- No quiere ver código ni tecnicismos
- Quiere un sistema claro, rápido y predecible
- Todo debe poder explicarse en lenguaje normal

---

## 2. PRINCIPIOS FUNDAMENTALES

### Multilenguaje
Idiomas obligatorios:
- Español (es)
- Ruso (ru)
- Ucraniano (uk)
- Francés (fr)
- Inglés (en)
- Armenio (hy)

Todo el sistema es multilenguaje:
- interfaz
- textos
- estados
- mensajes
- PDFs
- emails

Nunca se hardcodea texto en un solo idioma.

### Simplicidad mental
- Menos es más
- Evitar formularios administrativos
- Evitar sensación de ERP pesado
- Priorizar claridad y flujo clínico natural

---

## 3. METODOLOGÍA

1. Primero se documenta
2. Luego se decide
3. Solo después se programa

Las decisiones no se reabren.

Roles:
- El usuario protege el foco clínico
- ChatGPT detecta incoherencias y redacta decisiones
- Claude Sonnet programa solo lo decidido

---

## 4. PACIENTES

Un Paciente es una entidad longitudinal.

- Puede crearse automáticamente desde una cita o manualmente
- No hay campos obligatorios en UX
- Un paciente tiene múltiples Encounters
- El histórico clínico se consulta por Encounters

Documentos del paciente:
- Administrativos (ej. consentimientos)
- No son fotos clínicas
- No pertenecen a Encounters

---

## 5. AGENDA Y CITAS

Calendly es la única fuente de verdad.

No se pueden crear citas manuales en el ERP.

Appointment:
- Representa una cita de agenda
- No es clínico
- No contiene diagnóstico ni fotos

Flujo:
Calendly → Webhook → Appointment idempotente

Si el ERP está apagado:
- Se implementa sincronización periódica con Calendly

Un Appointment nunca es una consulta.
El Encounter se crea cuando la doctora atiende.

---

## 6. MODELO CLÍNICO CENTRAL

### Encounter
El Encounter representa una consulta médica real.

Estados:
- draft
- finalized
- cancelled

El único estado clínico real es finalized.

No existen estados administrativos ni de venta.

---

## 7. UX DEL ENCOUNTER

- El Encounter no es un formulario
- Bloques clínicos
- Escritura natural
- Sin campos obligatorios

Finalizar consulta:
- Botón siempre visible en draft
- Se puede pulsar en cualquier momento
- No valida contenido

---

## 8. FOTOS CLÍNICAS

- Las fotos siempre pertenecen a un Encounter
- Nunca se suben desde la ficha del paciente
- No se arrastran fotos a nuevos Encounters

Almacenamiento:
- MinIO (bucket derma-photos)
- Nunca en base de datos

Invariante:
- photo.patient_id = encounter.patient_id

UX:
- Drag & drop múltiple
- Área de drop no fija
- Eliminación siempre con confirmación

Metadatos v1:
- fecha
- autor
- relación con Encounter

---

## 9. PRACTITIONERS Y RECEPCIÓN

- Cada practitioner tiene su calendly_url
- Recepción elige doctor/a y se usa su Calendly

---

## 10. MODELO CONCEPTUAL GENERAL

Agenda
→ Appointment
→ Encounter
→ Proposal
→ (opcional) Venta
→ (opcional) Salida de almacén

---

## 11. STACK TÉCNICO (CERRADO)

### Sistema y despliegue
- Docker + Docker Compose
- macOS, Windows 10+, Linux
- Modos DEV y PROD_LOCAL

### Backend
- Python 3.11
- Django 4.2.8
- Django REST Framework
- Gunicorn en producción local

### Base de datos
- PostgreSQL 15
- Base única
- Volúmenes Docker

### Cache y tareas
- Redis
- Celery

### Autenticación
- JWT (Simple JWT)
- Usuario custom authz.User

### Almacenamiento de objetos
- MinIO (S3 compatible)
- Buckets:
  - derma-photos
  - marketing
  - documents

### API
- REST
- OpenAPI (drf-spectacular)
- Paginación, throttling, CORS

### Email
- SMTP Gmail
- Envío en nombre de la doctora

### Frontend
- Next.js
- React
- TypeScript
- Tailwind
- next-intl (6 idiomas)

### Calendly
- Webhooks verificados
- Token API
- Fuente única de verdad

### Infraestructura Docker
Servicios:
- postgres
- redis
- minio
- api
- web
- celery

### Reglas técnicas relevantes
- UUIDs como PK
- Soft delete
- Auditoría básica
- FEFO en stock
- Invariantes clínicos

### No existe en el stack
- PDFs automáticos implementados
- Empaquetado USB real
- Modo completamente offline sin Docker
- Cloud
- GraphQL
- WebSockets
- CI/CD
- Monitoring externo

---

## 20. PROPOSALS

Una Proposal es la propuesta médica tras un Encounter.

Puede incluir:
- cuidados
- tratamientos
- productos

No es una venta.
Solo hay venta tras aceptación explícita.

Estados:
Sin productos:
- draft
- given

Con productos:
- draft
- sent
- pending_acceptance
- accepted
- declined
- expired

---

## 21. FUERA DE ALCANCE (v1)

- Pagos
- Facturación
- TPV
- UX de almacén
- Firma digital
- Portal de paciente

---

## 22. RESUMEN DE DECISIONES  
Agenda · Encounters · Proposals · Roles · UX Clínica

---

## 1. AGENDA · PRINCIPIOS GENERALES

- **Calendly es la única fuente de verdad de la agenda**
- Todas las citas:
  - vienen de Calendly, o
  - se crean desde el ERP **sincronizando con Calendly**
- No existen citas “solo locales”
- El ERP **no reinventa**:
  - cancelaciones
  - reprogramaciones
  - políticas de agenda
- El ERP refleja lo que Calendly permite

---

## 2. ROLES Y CONFIDENCIALIDAD

### 2.1 Doctora / Practitioner

- Ve **solo su propia agenda**
- Puede:
  - crear citas (solo para sí misma)
  - abrir citas
  - entrar en Encounters
  - crear y trabajar Encounters
  - finalizar Encounters
  - crear y enviar Proposals
- No puede:
  - ver la agenda de otras doctoras
  - gestionar citas de otras doctoras

---

### 2.2 Recepcionista

- Ve la agenda de **todas las doctoras**
- Puede:
  - confirmar que el paciente ha acudido
  - marcar no-show
  - crear o completar fichas de paciente
  - crear citas en el ERP **sincronizadas con Calendly**
  - asignar una doctora concreta
- No puede:
  - crear Encounters
  - acceder a Encounters
  - ver clínica
  - finalizar consultas
  - crear Proposals

---

## 3. CITAS (APPOINTMENTS)

- Una cita:
  - organiza tiempo
  - no es clínica
- Desde una cita:
  - la doctora puede entrar al Encounter
  - la recepción solo accede a datos administrativos
- Estados visibles de cita (UX):
  - Programada
  - No apareció
  - Cancelada
  - Reprogramada

---

## 4. NO-SHOW, CANCELACIÓN Y REAGENDAR

### No-show
- Si el paciente no se presenta:
  - la cita se marca como “no aparecido”
  - no se crea Encounter
  - no se envía nada
  - no se modifica Calendly

### Cancelar / Reprogramar
- Todo se hace en Calendly
- El ERP se sincroniza vía webhook
- La recepción usa Calendly, no lógica propia

---

## 5. PACIENTE NUEVO VS CONOCIDO

- **Paciente nuevo**:
  - no tiene ningún Encounter finalizado
- **Paciente conocido**:
  - tiene al menos un Encounter finalizado
- No se usa:
  - fecha de alta
  - citas previas
  - no-shows
- Solo cuentan Encounters `finalized`

---

## 6. MODELO CLÍNICO

### Encounter

- El Encounter representa una **consulta médica real**
- Estados:
  - draft
  - finalized
  - cancelled
- El único estado clínico real es `finalized`
- No existen estados administrativos ni de venta

---

## 7. UX · LISTA DE ENCOUNTERS

- Vive dentro de la ficha del paciente
- Orden cronológico inverso
- Muestra solo:
  - fecha
  - estado visual
  - indicador de fotos
  - indicador de Proposal pendiente (si aplica)
- Es historia clínica navegable, no panel de acciones

---

## 8. UX · DETALLE DEL ENCOUNTER

- El Encounter **no es un formulario**
- Bloques clínicos:
  - notas
  - fotos
  - proposal
- Sin campos obligatorios
- Sin pasos guiados
- Todo editable mientras está en `draft`

---

## 9. PROPOSAL (MODELO FINAL)

- La Proposal es el **output natural del razonamiento clínico**
- Vive dentro del Encounter
- No es obligatoria
- No es un paso posterior

### Proposal diferida
- Caso excepcional y explícito
- Permite cerrar el Encounter sin enviar nada
- No es el camino por defecto

---

## 10. FINALIZAR ENCOUNTER

Al pulsar **Finalizar consulta**:

### Sin Proposal
- El Encounter se finaliza
- No se envía nada

### Con Proposal (normal)
- El Encounter se finaliza
- La Proposal se envía automáticamente por email
- Estados:
  - sin productos → `given`
  - con productos → `sent` (pendiente de aceptación)

### Proposal diferida
- El Encounter se finaliza
- No se envía email

---

## 11. EMAILS (DECISIÓN CLAVE)

- Toda Proposal no diferida:
  - se envía automáticamente al cerrar el Encounter
- El email:
  - se envía **desde la cuenta del practitioner**
  - se envía al email del paciente
- No hay:
  - confirmaciones
  - wizards
  - envíos manuales

### Invariantes
- El paciente **siempre tiene email**
- El practitioner **siempre tiene email**
- El único error posible es un fallo técnico de envío

Regla:
> O se cierra todo correctamente, o no se cierra nada.

---

## 12. MODELO MENTAL GLOBAL

Agenda  
→ Cita  
→ Encounter  
→ Proposal  
→ (opcional) Venta  
→ (opcional) Salida de almacén

---

## 13. REGLA DE ORO FINAL

> El ERP se adapta al día de la doctora.  
> Cada paciente se cierra completamente al finalizar la consulta,  
> salvo decisión consciente de dejar algo pendiente.

---

## 14. ESTADO DEL DOCUMENTO

- Estas decisiones están **cerradas**
- No se reabren
- Son la base para UX, backend y prompts a Claude



## 99. CIERRE

Este documento define completamente el ERP clínico.
Es la referencia única y definitiva del proyecto.

---

## 15. Treatment Session Detail UX v1

**Decided: 2026-03-03**

### Rules

- **Completed sessions are immutable.** Once completed, no edits allowed.
- **No reopen logic.** There is no path from completed/cancelled back to draft.
- **Draft sessions autosave** notes with 1.5s debounce.
- **Photos are optional** — UI-only local state until a backend upload endpoint is implemented.
- **Treatment sessions are NOT linked to Encounters.** They are a separate workflow under Treatment Plans.
- **All UI strings use next-intl** namespace `"treatmentSession"` across all 6 locale files (en, es, fr, ru, uk, hy).

### Page location

`/[locale]/clinical/treatment-sessions/[id]/`

### Hooks

`use-treatment-sessions.ts` provides:
- `useTreatmentSession(id)` — fetch single session
- `useUpdateTreatmentSession()` — PATCH notes/performed_at (draft only)
- `useCompleteTreatmentSession()` — POST complete action
- `useCancelTreatmentSession()` — POST cancel action

### State transitions

```
draft → completed  (irreversible)
draft → cancelled  (irreversible)
```

No other transitions exist.

---

## 16. Admin Panel — Legal Entity Management

**Date**: 2025-01-XX
**Status**: Implemented

### Architecture

The admin panel lives under `/[locale]/admin/` and is visible in the sidebar only for users with `is_superuser` or `ADMIN` role.

The `SuperuserHeaderBar` (tenant-plane switcher) is **kept** — it is infrastructure, not redundant with the admin panel.

### Sidebar

A new "Administración" section appears below the main navigation with a visual separator. First item: **Legal Entities**.

### Pages

| Route | Purpose |
|---|---|
| `/admin/legal-entities` | List all legal entities (table with status badges) |
| `/admin/legal-entities/new` | Create form — generates admin user + temp password |
| `/admin/legal-entities/[id]/edit` | Edit form — update entity fields + toggle active |

### Hooks

`use-legal-entities.ts` provides:
- `useLegalEntities()` — GET list
- `useLegalEntity(id)` — GET detail
- `useCreateLegalEntity()` — POST (returns `temporary_password`)
- `useUpdateLegalEntity()` — PATCH

### Access Control

- **Sidebar visibility**: `user.is_superuser || hasRole(ROLES.ADMIN)`
- **Page guard**: Same check; redirects to home if unauthorized
- **Backend**: Endpoints restricted to superuser via Django permissions

### i18n

All strings under `admin.legalEntities` namespace across 6 locales (en, es, fr, ru, uk, hy).

