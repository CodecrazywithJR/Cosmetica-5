PROJECT CONTRACT — ERP COSMÉTICA
1. Objetivo del Proyecto
Construir un ERP clínico serio, escalable y multi-tenant para clínicas estéticas, con:
Arquitectura robusta
State machines formales
Multiidioma obligatorio
Roles estrictos
Separación clara entre dominio clínico y financiero
Preparado para crecimiento (no solución de clínica pequeña ad-hoc)
Este documento define reglas inmutables del sistema.
2. Reglas Inmutables del Proyecto
2.1 Multiidioma Obligatorio
El sistema es multiidioma desde su núcleo.
Idiomas soportados:
Español
Inglés
Francés
Ruso
Ucraniano
Armenio
Reglas:
❌ Prohibido introducir strings hardcodeadas visibles en JSX.
✅ Todas las etiquetas deben usar next-intl.
✅ Todas las claves nuevas deben añadirse en los 6 archivos messages/*.json.
❌ No usar status.toUpperCase() ni labels derivadas manualmente.
✅ Los estados se traducen vía proposals.status.xxx, encounters.status.xxx, etc.
2.2 Estados = Backend Source of Truth
El frontend NO define estados.
El backend es la única fuente de verdad.
Ejemplo Proposal:
draft
sent
accepted
cancelled
expired
Reglas:
❌ No inventar estados frontend.
❌ No mapear estados con nombres distintos.
❌ No saltar transiciones.
✅ Las acciones del frontend deben llamar endpoints de transición explícitos.
2.3 Transiciones Obligatorias (State Machines)
Proposal
draft → sent → accepted
draft → cancelled
sent → cancelled
sent → expired
accept() crea Sale + SaleLines + TreatmentPlans atómicamente.
accepted, cancelled, expired son estados terminales.
Proposal es inmutable en estado terminal.
Encounter
draft → finalized
draft → cancelled
Solo en draft se pueden editar tratamientos y notas.
Solo en finalized se puede generar Proposal.
TreatmentPlan
draft → active → completed
draft → cancelled
Se crea automáticamente al aceptar Proposal (según tipo de línea).
Las sesiones se agendan manualmente (NO automatización por fórmula).
Terminal states inmutables.
3. Multi-Tenant y Superuser
3.1 Legal Entity
Superuser puede operar en:
System Plane
Business Plane (con X-Active-Legal-Entity)
El header X-Active-Legal-Entity se inyecta automáticamente para endpoints de negocio.
No se inyecta en:
/api/auth/*
/api/v1/system/*
/health
3.2 Superuser
Puede ver y editar cualquier módulo.
Puede operar sobre cualquier LegalEntity.
Puede eliminar último administrador.
Puede reactivar LegalEntity inactiva.
Bypass completo de restricciones de roles.
4. Roles Oficiales del Sistema
Roles definitivos:
admin
practitioner
reception
accounting
marketing
superuser (flag, no role normal)
Reglas:
❌ No usar roles inexistentes (ej. CLINICAL_OPS eliminado).
❌ No renderizar null silencioso en RBAC.
✅ Mostrar componente Unauthorized cuando corresponda.
5. Flujo Clínico Oficial
El flujo clínico oficial es:
Appointment
 → Start Encounter
 → Add Treatments
 → Finalize Encounter
 → Generate Proposal
 → Send Proposal
 → Accept Proposal
 → Sale + TreatmentPlans creados
 → Ejecución de sesiones
Reglas:
Proposal SIEMPRE nace desde Encounter.
No se crea Proposal desde Patient directamente.
TreatmentPlan SIEMPRE nace desde Proposal.accept().
No se crean TreatmentPlans manualmente.
6. Modelado de Servicios
Actualmente:
El catálogo usa Treatment como modelo de servicio.
ProposalLine puede ser:
per_session
full_package
Para full_package:
Se crea TreatmentPlan.
Las sesiones se gestionan manualmente.
7. UX y Arquitectura Frontend
7.1 Layout
Sidebar por rol.
SuperuserHeaderBar solo visible si is_superuser.
SystemPlaneGuard bloquea negocio si no hay LegalEntity seleccionada.
7.2 Paciente
Paciente debe evolucionar hacia vista 360:
Tabs previstas:
Overview
Encounters
Proposals
Treatment Plans
Sales
Regla:
No mezclar agenda con visión financiera.
Agenda es módulo operativo independiente.
8. Prohibiciones Explícitas
❌ Hardcode de textos visibles.
❌ Crear estados frontend que no existan en backend.
❌ Saltar estados del dominio.
❌ UUID tipado como number (siempre string).
❌ Mocks si el endpoint backend ya existe.
❌ Mezclar lógica clínica con financiera sin transición formal.
❌ Formularios que pidan manualmente datos que el contexto ya conoce (ej. legalEntityId si está en ActiveLegalEntityContext).
9. Convenciones Técnicas
9.1 TypeScript
UUID siempre string.
Interfaces alineadas con backend.
No duplicar modelos con tipos inconsistentes.
9.2 Backend
Transiciones vía métodos del modelo o service layer.
Operaciones críticas dentro de transaction.atomic().
Estados terminales inmutables.
Migraciones sin pérdida de datos.
10. Principio Rector
Este ERP debe poder escalar de:
Clínica pequeña donde la doctora hace todo
a
Clínica con múltiples practitioners, recepción, administración y contabilidad.
Sin refactor estructural.
Cada decisión debe preguntarse:
¿Esto escala?
Si no escala, no se implementa.
11. Uso por LLMs
Cualquier implementación futura debe:
Respetar este contrato.
No contradecir decisiones aquí definidas.
No introducir shortcuts temporales.
Mantener coherencia con state machines y multiidioma.
FIN DEL CONTRATO