TECHNICAL_DESIGN_DOCUMENT.md
ERP Clínico — Diseño Técnico
1. VISIÓN GENERAL DE ARQUITECTURA
1.1 Tipo de sistema
Backend: Django + DRF
Frontend: Next.js
Base de datos relacional
Arquitectura modular por apps
Separación dominio clínico / financiero
1.2 Separación de dominios
Dominio	Responsabilidad
clinical	Encounter, lógica médica
proposals	Oferta contractual
sales	Documento contable
treatments	Catálogo de servicios
treatment_plans	Ejecución clínica
appointments	Agenda
pos	Cobro
inventory	Stock
authz	Usuarios y roles
2. MODELO DE DOMINIO
2.1 Encounter
Responsabilidad
Acto clínico.
Relaciones
1:1 → Proposal
N:1 → Patient
N:1 → Practitioner
Reglas
Solo puede generar una Proposal.
No editable tras generar Proposal.
No ligado aún a LegalEntity.
2.2 Proposal
Responsabilidad
Documento contractual clínico-económico.
Relaciones
1:1 → Encounter
1:N → ProposalLine
1:1 → Sale (opcional)
N:1 → Patient
N:1 → Practitioner
N:1 → User (created_by)
N:1 → User (accepted_by)
Estados
draft
sent
accepted
cancelled
expired
Máquina de estados
draft
→ sent
→ cancelled
→ expired
sent
→ accepted
→ cancelled
→ expired
accepted
Terminal
cancelled
Terminal
expired
Terminal
Reglas técnicas
accepted es inmutable.
No se puede editar ProposalLine tras accepted.
valid_until = created_at + 30 días.
Expiración automática (cron o signal).
No regenerable desde mismo Encounter.
create_sale() solo permitido desde estado sent.
accept() encapsula transición + creación de Sale.
2.3 ProposalLine
Responsabilidad
Snapshot económico de un servicio ofertado.
Relaciones
N:1 → Proposal
N:1 → Treatment (catálogo)
1:1 → TreatmentPlan (si full_package)
Campos clave
quantity
unit_price (snapshot)
line_total
treatment_name (snapshot)
description (snapshot)
Reglas
quantity > 0
unit_price ≥ 0
line_total calculado automáticamente
Inmutable tras Proposal.accepted
2.4 Treatment (Catálogo)
Tipos
per_session
full_package
Campos clave
name
description
price
currency
planned_sessions (si full_package)
images (MINIO)
Reglas
Precio puede cambiar en el tiempo.
No afecta a Proposals ya creadas.
No afecta a TreatmentPlans activos.
2.5 TreatmentPlan
Responsabilidad
Ejecución clínica de un paquete vendido.
Relaciones
N:1 → Patient
N:1 → Practitioner
N:1 → Proposal
N:1 → ProposalLine
N:1 → Sale
1:N → Appointment
Campos snapshot
package_name
planned_sessions
completed_sessions
total_price_snapshot
currency
Estados
draft
active
completed
cancelled
Máquina de estados
draft
→ active (al crear primera Appointment)
active
→ completed (completed_sessions >= planned_sessions)
→ cancelled (manual)
completed
Terminal
cancelled
Terminal
Reglas técnicas
No editable estructuralmente tras active.
completed_sessions incrementa solo con Appointment.completed.
No gestiona pagos.
Cancel no permitido si estado completed.
2.6 Appointment
Relaciones
N:1 → Patient
N:1 → Practitioner
N:1 → TreatmentPlan (opcional)
Reglas
Si vinculado a TreatmentPlan:
Primera cita activa plan.
completed incrementa contador.
Cancelled no incrementa.
Agenda no tiene lógica financiera.
2.7 Sale
Responsabilidad
Documento contable.
Relaciones
N:1 → LegalEntity
N:1 → Patient
1:N → SaleLine
1:N → Payment
1:N → Refund
Reglas
Creado automáticamente al aceptar Proposal.
SaleLine snapshot de ProposalLine.
No depende del estado del TreatmentPlan.
2.8 POS
Punto único de cobro.
Permite pagos parciales.
No modifica Proposal.
No modifica TreatmentPlan.
3. EVENTOS DE DOMINIO
Proposal.accept()
Acciones:
Validar estado == sent
Crear Sale
Crear SaleLines
Crear TreatmentPlans (para líneas full_package)
Actualizar estado → accepted
Guardar accepted_at, accepted_by
Transacción atómica.
Appointment.complete()
Acciones:
Incrementar completed_sessions
Si completed_sessions >= planned_sessions → plan.completed()
4. INVARIANTES CRÍTICOS
Proposal.accepted es inmutable.
ProposalLine no editable tras aceptación.
TreatmentPlan.active no puede cambiar estructura.
TreatmentPlan.completed es terminal.
No se puede aceptar Proposal expirada.
No se puede generar segunda Proposal para mismo Encounter.
5. MULTI-TENANT (ACTUAL)
Sale ligada a LegalEntity.
Superuser usa X-Active-Legal-Entity header.
Encounter y Proposal aún no ligados.
Evolución futura: añadir legal_entity a Encounter y Proposal.
6. CONTROL DE CONSISTENCIA
transaction.atomic en Proposal.accept
Validaciones en modelo, no solo serializer
Métodos de transición en modelo (no en view)
No cambio directo de status via update()
7. EXTENSIBILIDAD FUTURA
Posibles extensiones:
Portal paciente
Firma digital
Pago online
Versionado de Proposal
Multi-tenant completo
IVA detallado
Renovación automática de planes
Suspensión temporal de plan
8. FLUJO GLOBAL
Encounter
   ↓ generate
Proposal (draft → sent → accepted)
   ↓
Sale
   ↓
TreatmentPlan(s)
   ↓
Appointments manuales
   ↓
Completed automático
Este documento es coherente con lo que ya hemos implementado.