# CHECKLIST — Agenda, Calendly y ERP
Estado: Fuente de verdad compartida (Usuario + ChatGPT + Claude)

Objetivo:
Tener una agenda 100% consistente, sin huecos fantasma, alineada con PROJECT_DECISIONS.md §17, y preparada para crecimiento futuro.

---

## 1️⃣ PRINCIPIOS YA CERRADOS (NO REABRIR)

- [x] Calendly es el ÚNICO motor de agenda y disponibilidad
- [x] El ERP NO crea citas locales sin pasar por Calendly
- [x] Appointment sin external_id de Calendly NO es válido
- [x] Email del paciente es requisito HARD para crear citas
- [x] No se usan emails ficticios ni placeholders
- [x] Recepción NO usa embeds ni URLs de Calendly
- [x] practitioner.calendly_url es un atributo técnico, no operativo
- [x] Embed de Calendly solo para pacientes (web / Instagram)
- [x] El ERP puede estar apagado sin perder citas (sync posterior)

---

## 2️⃣ ESTADO ACTUAL CONFIRMADO

### Implementado
- [x] Webhook Calendly → ERP (invitee.created, invitee.canceled)
- [x] Idempotencia por external_id
- [x] Bloqueo total de creación local de citas en ERP
- [x] Riesgo de huecos fantasma eliminado
- [x] Campo practitioner.calendly_url operativo
- [x] Flujo Agenda → Visit → Encounter atómico (attend endpoint)

### NO implementado (pendiente)
- [ ] Crear citas en Calendly desde ERP (recepción)
- [ ] Consulta de disponibilidad real vía Calendly API
- [ ] Sync periódico (daemon / cron)
- [ ] Manejo de invitee.rescheduled
- [ ] Asignación fiable de practitioner desde webhook
- [ ] UX final de agenda para recepción

---

## 3️⃣ CHECKLIST DE IMPLEMENTACIÓN (ORDEN RECOMENDADO)

### FASE A — Infraestructura Calendly (Backend)
- [ ] Crear cliente Calendly API (usar CALENDLY_API_TOKEN)
- [ ] Endpoint: GET /calendly/available-slots/
- [ ] Endpoint: POST /calendly/create-appointment/
- [ ] Validación dura: patient.email obligatorio
- [ ] Validación: practitioner.calendly_url configurado
- [ ] Manejo explícito de errores Calendly (422, 409, etc.)

### FASE B — Consistencia y Sync
- [ ] Soportar evento invitee.rescheduled
- [ ] Implementar sync periódico (cada X minutos)
- [ ] Sync de seguridad al arrancar ERP
- [ ] Endpoint manual de sync (admin only)
- [ ] Logs visibles de eventos Calendly

### FASE C — UX Agenda (Recepción)
- [ ] Agenda única en ERP (vista calendario)
- [ ] Selector de Practitioner
- [ ] Modal “Nueva cita”
- [ ] Selección de slot exacto (sin fechas aproximadas)
- [ ] Mensajes claros cuando Calendly rechaza
- [ ] Flujo simple: pedir email y continuar

---

## 4️⃣ DECISIONES UX YA TOMADAS

- [x] Recepción pide email sin dramatizarlo
- [x] No hay workarounds si falta email
- [x] Errores de Calendly se muestran claros y accionables
- [x] No se crean citas “provisionales”
- [x] Si Calendly falla → no se guarda nada
- [x] Sistema prioriza claridad sobre automatismos mágicos

---

## 5️⃣ RIESGOS CONTROLADOS

- [x] Huecos fantasma → ELIMINADOS
- [x] Citas duplicadas → control por external_id
- [x] ERP apagado → cubierto por sync
- [x] Recepción sin contexto técnico → UX guiada

---

## 6️⃣ LO QUE VIENE DESPUÉS (NO AHORA)

- UX avanzada de Encounters
- Subida y gestión de imágenes clínicas
- Estadísticas, reporting, ML
- Multi-sede / multi-clínica
- Despliegue cloud o acceso móvil externo

---

## ESTADO GLOBAL
🟢 Base sólida  
🟡 Agenda en fase de integración API  
🔴 Nada crítico bloqueando la continuidad

Siguiente foco recomendado:
👉 UX de Encounters y gestión de imágenes clínicas
