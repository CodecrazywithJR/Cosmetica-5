CLINICAL DOMAIN & AUDIT LOG CONTEXT
1. Objetivo
Este documento resume las decisiones de arquitectura tomadas para:
clinical audit log
appointments
encounters
proposals
treatments
analytics taxonomy
Sirve para continuar el desarrollo en una nueva conversación sin perder contexto.
2. Clinical Audit Log
El sistema necesita registrar eventos clínicos y comerciales relevantes para:
trazabilidad médica
auditoría legal
debug clínico
analytics futuros
Se implementará una tabla genérica:
AuditLog
Modelo conceptual:
id
timestamp
user
legal_entity
entity_type
entity_id
event_type
payload_json
Características:
multi-tenant
inmutable
ordenado por timestamp
No se usarán signals.
Los eventos se registrarán explícitamente en:
services
viewsets
state machines
3. Eventos auditados
Eventos clínicos:
PATIENT_CREATED
PATIENT_UPDATED
PATIENT_SOFT_DELETED

APPOINTMENT_CREATED
APPOINTMENT_UPDATED
APPOINTMENT_CANCELLED
APPOINTMENT_NO_SHOW
APPOINTMENT_CHECKED_IN

ENCOUNTER_CREATED
ENCOUNTER_FINALIZED
ENCOUNTER_CANCELLED

CONSENT_SIGNED
CLINICAL_PHOTO_UPLOADED
Eventos comerciales:
PROPOSAL_CREATED
PROPOSAL_SENT
PROPOSAL_ACCEPTED
PROPOSAL_CANCELLED

SALE_CREATED
REFUND_CREATED

TREATMENT_SESSION_COMPLETED
Las proposals registrarán todas las transiciones.
4. Flujo del dominio clínico
El flujo completo del sistema es:
Appointment
      ↓ check_in
Encounter
      ↓
Proposal
      ↓
Sale
      ↓
TreatmentPlan
      ↓
TreatmentSession
Separación clave:
Appointment = agenda
Encounter = acto médico
5. Appointment
Appointment representa una cita en la agenda.
Campos principales:
patient
practitioner
location
appointment_type
start_datetime
end_datetime
duration_planned
duration_real
status
notes
6. AppointmentType
Las citas se clasifican mediante:
AppointmentType
Tabla configurable por clínica.
Ejemplos:
INITIAL_CONSULT
FOLLOW_UP
TREATMENT
CHECKUP
EMERGENCY
ESTHETIC_EVALUATION
Campos:
name
default_duration_minutes
color
is_active
7. Estados de Appointment
Estados permitidos:
scheduled
confirmed
checked_in
completed
cancelled
no_show
Flujo típico:
scheduled
   ↓
confirmed
   ↓
checked_in
   ↓
completed
o
scheduled → cancelled
scheduled → no_show
8. Creación automática de Encounter
Regla definida:
Appointment checked_in → crea Encounter automáticamente
Restricción:
1 appointment → máximo 1 encounter
Esto garantiza que el acto médico queda registrado.
9. Encounter
Encounter representa el acto médico documentado.
Contiene:
notas clínicas
tratamientos realizados
diagnóstico
fotos clínicas
consentimientos
Desde un encounter se pueden generar:
proposals
10. Proposal
Una proposal es una recomendación terapéutica/comercial para un paciente.
Relación:
Encounter 1 → N Proposal
Estados:
draft
sent
accepted
cancelled
11. ProposalLine
Las proposals contienen tratamientos.
Modelo:
Proposal
   ↓
ProposalLine
Cada línea referencia un treatment del catálogo.
Pero guarda snapshot:
treatment_id
treatment_name_snapshot
price_snapshot
duration_snapshot
Esto protege el histórico.
12. Treatment
Treatment es catálogo de procedimientos médicos.
Ejemplos:
Botox
Laser CO2
Chemical Peeling
PRP
Campos:
name
category
duration
default_price
is_active
13. Product
Product representa consumibles.
Ejemplo:
Botox vial
filler syringe
peeling chemical
Relación:
Treatment
   ↓
TreatmentProduct
   ↓
Product
Esto permite calcular consumo de stock.
14. Sale
Cuando una proposal se acepta se generan:
Sale
TreatmentPlan
Sale representa la transacción económica.
15. TreatmentPlan
TreatmentPlan representa el plan clínico ejecutable.
Ejemplo:
Laser → 3 sesiones
Botox → 1 sesión
Modelo:
TreatmentPlan
   ↓
TreatmentSession
16. TreatmentSession
Cada sesión realizada.
Al ejecutarse:
consume productos
genera movimientos de stock
17. Taxonomía analítica
Para soportar dashboards futuros se crearán tablas de clasificación:
AppointmentType
EncounterType
TreatmentCategory
ProposalCategory
ProductCategory
Todas:
tenant-scoped
configurables por clínica
Esto permitirá medir:
tratamientos más vendidos
conversion rate de proposals
actividad clínica
ratio no-show
revenue por categoría
18. Orden de implementación
Orden recomendado:
1. Clinical Audit Log
2. Taxonomía (AppointmentType / TreatmentCategory / etc.)
3. Rediseño completo del módulo Appointments
4. Integración con Encounter
5. Proposals + pipeline comercial
19. Principio rector
Separación clara entre:
agenda
acto médico
pipeline comercial
ejecución clínica
Esto mantiene el ERP mantenible y analizable.
Conclusión
El sistema quedará estructurado en cuatro capas claras:
Agenda → Appointment
Clínico → Encounter
Comercial → Proposal / Sale
Ejecución → TreatmentPlan / TreatmentSession
AuditLog registrará eventos de todas ellas.