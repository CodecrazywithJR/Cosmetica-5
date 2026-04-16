ARCHITECTURE_CONTEXT.md
(Documento maestro de contexto del dominio)
1. PROPÓSITO DEL SISTEMA
ERP clínico para clínica estética con:
Separación estricta entre dominio clínico y financiero.
Arquitectura escalable.
Estados formales.
Inmutabilidad contractual.
Snapshot económico en cada capa.
Multi-tenant futuro.
Sistema pensado para crecer, no para clínica unipersonal.
2. PRINCIPIOS ARQUITECTÓNICOS
Separación clínica / financiera
Encounter = clínico
Proposal = oferta contractual
Sale = documento contable
POS = dinero
TreatmentPlan = ejecución clínica
Inmutabilidad contractual
Proposal accepted es inmutable.
TreatmentPlan completed es terminal.
Snapshot económico por capa
ProposalLine congela precio ofertado.
SaleLine congela precio vendido.
TreatmentPlan guarda snapshot histórico del paquete.
Estados formales
Ningún módulo cambia estado “a mano”.
Transiciones mediante métodos explícitos.
Nada automático dependiente de disponibilidad del paciente
Las citas se crean manualmente.
No hay generación automática de agenda.
3. DOMINIO CLÍNICO
3.1 Encounter
Acto clínico.
1:1 con Proposal.
Si Proposal expira o se cancela → nuevo Encounter.
Aún no ligado a LegalEntity (fase futura).
3.2 Proposal
Documento clínico-económico derivado del Encounter.
Estados
draft
sent
accepted (terminal)
cancelled (terminal)
expired (terminal)
Reglas
1 Proposal por Encounter.
Editable solo en draft.
Solo Practitioner owner puede editar draft.
Reception y Practitioner pueden aceptar.
accepted crea:
Sale
TreatmentPlan(s)
valid_until = created_at + 30 días.
Expira automáticamente.
No regenerable desde mismo Encounter.
3.3 Catálogo de Servicios (Treatment)
Cada servicio puede ser:
per_session
full_package
Incluye:
name
description
price
currency
gallery (MINIO)
sesiones previstas (si full_package)
El precio puede cambiar en el tiempo.
Proposal congela precio.
Sale congela precio.
TreatmentPlan congela snapshot.
3.4 TreatmentPlan
Se crea automáticamente al aceptar Proposal.
Uno por cada ProposalLine full_package.
Campos clave
planned_sessions
completed_sessions
total_price_snapshot
currency
proposal_id
proposal_line_id
sale_id
Estados
draft
active
completed
cancelled
Reglas
draft → active al crear primera cita.
active → completed automáticamente cuando completed_sessions >= planned_sessions.
Cancel manual permitido si no completed.
No edición estructural tras active.
No gestiona pagos.
3.5 Appointment
Puede vincularse a TreatmentPlan.
Primera cita activa plan.
Cita completed incrementa contador.
Cancelar cita no incrementa.
Agenda ≠ Plan.
4. DOMINIO FINANCIERO
4.1 Sale
Se crea automáticamente al aceptar Proposal.
Contiene SaleLines snapshot.
Estado financiero independiente.
POS gestiona cobro.
Proposal NO gestiona dinero.
4.2 POS
Punto único de entrada de dinero.
Puede gestionar pagos parciales.
Puede gestionar devoluciones futuras.
5. ROLES Y RESPONSABILIDADES
Superuser
Acceso total.
System Plane.
Puede forzar transiciones.
Admin
Gestión operativa.
No edita contenido clínico de Proposal.
Puede ver todo.
Practitioner
Crea Encounter.
Edita Proposal draft (si owner).
Envía Proposal.
Acepta Proposal.
Cancela Proposal.
Cancela TreatmentPlan (si no completed).
Reception
Crea citas.
Acepta Proposal.
Cobra en POS.
Registra entradas de almacén.
Accounting
Solo lectura financiera.
6. FLUJO COMPLETO
Encounter
   ↓
Proposal (draft → sent → accepted)
   ↓
Sale
   ↓
TreatmentPlan(s)
   ↓
Appointments manuales
   ↓
Completed automático
7. DELIBERADAMENTE NO IMPLEMENTADO
Firma digital paciente
Pago online
Portal paciente
Multi-tenant completo
Versionado de Proposal
Generación automática de agenda
IVA avanzado
8. ESTADO ACTUAL
Proposal refactorizado con state machine formal.
TreatmentPlan implementado con estados automáticos.
Snapshot económico coherente.
Arquitectura limpia lista para escalar.