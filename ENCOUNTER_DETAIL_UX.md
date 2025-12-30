
ENCOUNTER_DETAIL_UX.md

---

1. Objetivo de la pantalla
Describe que Encounter Detail representa una visita clínica real.
Indica que es el núcleo clínico del ERP.
Enumera como objetivos:
- Documentar la visita médica
- Separar voz del paciente, criterio médico, tratamiento propuesto y propuesta económica
- Adjuntar fotos y documentos clínicos
- Finalizar la consulta de forma consciente y trazable
Aclara explícitamente que NO es una pantalla administrativa ni comercial.
Define la UX como rápida, clara y sin ruido.

---

2. Reglas generales (contrato)
Incluye explícitamente:
- No se inventan campos, flujos ni acciones
- Backend v1 existente
- Sistema multiidioma (i18n)
- Comportamiento según estado: draft / finalized / cancelled
- finalized y cancelled son estados terminales
- Encounter es el origen clínico de Proposed Treatment y Charge Proposal

---

3. Estructura general de la pantalla
Define que la pantalla se compone EXCLUSIVAMENTE de estas seis secciones,
en este orden fijo:

1. Encounter Header
2. Chief Complaint
3. Clinical Notes
4. Proposed Treatment
5. Charge Proposal
6. Attachments

Indica explícitamente:
- No existen otras secciones en UX v1
- No se subdividen
- El orden no es modificable

---

4. Secciones

4.1 Encounter Header
- Función: contexto inmediato
- Contenido: nombre del paciente, fecha/hora, estado
- Características: siempre visible, no editable, sin acciones

4.2 Chief Complaint
- Función: registrar lo que cuenta el paciente
- Contenido: síntomas, molestias, motivo de consulta
- Características: texto libre, voz del paciente
- No incluye: diagnóstico, juicio clínico, tratamiento
- Comportamiento: editable solo en draft, read-only en finalized/cancelled

4.3 Clinical Notes
- Función: razonamiento clínico de la doctora
- Contenido: observaciones, hipótesis, diagnóstico
- Características: texto interno
- No incluye: tratamiento, proposal, adjuntos
- Comportamiento: editable solo en draft, read-only en finalized/cancelled

4.4 Proposed Treatment
- Función: tratamiento propuesto desde punto de vista clínico
- Contenido: descripción y detalles clínicos
- Relación con Proposal:
	- puede dar lugar a Charge Proposal
	- no crea proposal automáticamente
	- puede existir sin proposal
	- no puede existir proposal sin Proposed Treatment
- No incluye: precios, venta, facturación
- Comportamiento: editable solo en draft, read-only en finalized/cancelled

4.5 Charge Proposal
- Función: representar la ClinicalChargeProposal si existe
- Estados posibles:
	- no existe
	- draft
	- converted
	- cancelled
- Reglas:
	- solo puede existir si el encounter está finalized
	- solo una proposal por encounter
	- no editable
- Contenido conceptual:
	- estado
	- resumen económico
	- relación con Sale
	- fechas relevantes
- No incluye edición ni lógica de cobro

4.6 Attachments
- Función: adjuntos clínicos del encounter

Clinical Photos:
- clasificación: before / after / progress / clinical / other
- soporte before/after
- pensado para iPhone
- apertura en navegador
- hard delete definitivo

Documents:
- tipos: PDF, Word, Excel, TXT
- apertura en navegador
- hard delete definitivo

Comportamiento:
- subida y eliminación solo en draft
- read-only en finalized y cancelled

---

5. Estados del Encounter
Incluye una tabla con:
- draft: editable, consulta en curso
- finalized: read-only, consulta cerrada
- cancelled: read-only, estado terminal

---

6. Relación con otros dominios
Incluye:
- Patient
- Charge Proposal
- Sale
- Attachments

---

7. Fuera de alcance (UX v1)
Incluye explícitamente:
- UX completa de Proposal
- Facturación
- Agenda ↔ Encounter automática
- Versionado clínico
- OCR
- Thumbnails
- IA

---

8. Estado final del documento
Marca explícitamente:
- Alcance cerrado
- Secciones canónicas
- Sin invenciones
- Alineado con backend v1
- Listo para implementación frontend
