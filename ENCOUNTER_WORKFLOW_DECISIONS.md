ENCOUNTER_WORKFLOW_DECISIONS.md
Propósito
Este documento define de forma definitiva el modelo conceptual, funcional y de UX del flujo
Agenda → Visita → Paciente → Encounter → Proposals → Venta,
con especial foco en simplicidad clínica, rigor de ERP y mínima fricción para la doctora.
1. Entidades y responsabilidades (modelo mental)
1.1 Visita
Representa una cita administrativa.
Puede existir:
con paciente asociado
sin paciente asociado (Calendly, llamadas, datos incompletos).
Estados típicos:
scheduled
cancelled
no_show
completed
Nunca se marca manualmente como completed.
1.2 Paciente
Representa la identidad clínica real.
NO se crea automáticamente desde Calendly.
Se crea solo cuando es necesario atender clínicamente.
Datos mínimos obligatorios para crear paciente:
Nombre
Apellido
Teléfono
El resto de datos son opcionales y no bloquean la atención.
1.3 Encounter (Consulta médica)
Es la entidad clínica principal y definitiva.
Vive exclusivamente en apps.clinical.models.Encounter.
No existe ningún otro modelo duplicado o alternativo.
Un Encounter:
SIEMPRE tiene paciente
puede o no estar asociado a una Visita
Representa una consulta médica realizada, independientemente de ventas.
1.4 Proposal (Propuesta de tratamiento)
Entidad separada del Encounter.
Puede incluir:
recomendaciones
tratamientos
productos
precios
Estados posibles:
borrador
aceptada
rechazada
convertida en venta
Una proposal NO implica venta automática.
1.5 Venta / Almacén
La venta es un proceso posterior e independiente.
Solo cuando una proposal se convierte en venta:
se genera la venta
se descuenta stock
se registra salida de almacén
2. Flujo canónico “Atender paciente”
2.1 Principio fundamental
La doctora no gestiona visitas.
La doctora atiende pacientes.
El sistema se encarga del resto.
2.2 Atender paciente con Visita + Paciente existente
La doctora pulsa “Atender paciente” desde la Agenda.
El sistema:
crea un Encounter
asocia Visita → Encounter
marca la Visita como completed
Se abre el detalle del Encounter.
2.3 Atender paciente con Visita SIN paciente (Calendly típico)
La doctora pulsa “Atender paciente”.
El sistema detecta que no hay paciente.
Se abre flujo de alta rápida de paciente.
Se crea el paciente con datos mínimos.
Automáticamente:
se crea el Encounter
la Visita se marca como completed
se abre el Encounter.
2.4 Atender paciente SIN Visita
La doctora puede iniciar una consulta:
desde la ficha del paciente
desde un botón de “Nueva consulta”.
El Encounter se crea sin Visita asociada.
(Opcional interno) El sistema puede crear una Visita ad-hoc marcada como completed.
3. Detección de pacientes duplicados (Calendly)
3.1 Coincidencia total (no mostrar aviso)
Se considera coincidencia total si coincide al menos uno de:
Email exacto
Teléfono exacto
Nombre + Apellido exactos (normalizados)
En ese caso:
el sistema reutiliza automáticamente el paciente
no muestra ningún aviso.
3.2 Coincidencia parcial (mostrar aviso)
Si NO hay coincidencia total pero hay similitudes:
nombre parecido
apellido parecido
datos incompletos
El sistema:
muestra un modal
lista todas las coincidencias encontradas
permite búsqueda fuzzy por nombre/apellido
3.3 Modal de decisión
En el modal, la doctora puede:
seleccionar un paciente existente
continuar con alta de paciente nuevo
cerrar el modal sin hacer nada
Si se cierra el modal:
no se crea paciente
no se crea encounter
no se modifica la visita
No existen flujos bloqueantes.
4. Datos incompletos del paciente
Durante el Encounter, si faltan datos no obligatorios:
se muestra un aviso suave e informativo
no bloquea
no obliga a completar
El aviso desaparece automáticamente cuando los datos se completan.
5. Guardado de datos del paciente
Los datos del paciente editados desde el Encounter:
se guardan automáticamente
sin botón “Guardar paciente”
sin confirmaciones intrusivas
El guardado es silencioso y no interrumpe la consulta.
6. Cierre del Encounter
6.1 Estado del Encounter
El Encounter tiene un único estado clínico principal:
Consulta realizada
No existe concepto de “encounter pendiente” por proposals.
6.2 Proposals y cierre
La existencia de proposals:
NO bloquea el cierre del encounter
NO implica venta
Las proposals pueden aceptarse o convertirse en venta:
en otro momento
incluso otro día
6.3 Acción de cierre
El cierre del encounter es manual mediante “Finalizar consulta”.
Al cerrar:
el encounter queda como “Consulta realizada”
el sistema redirige automáticamente a la Agenda.
7. Principios de diseño irrenunciables
❌ No flujos bloqueantes
❌ No decisiones forzadas
❌ No automatismos peligrosos (fusiones de pacientes)
✅ Simplicidad clínica
✅ Separación clara entre clínica y negocio
✅ ERP serio, pero humano
8. Estado del documento
Documento canónico
Fuente de verdad para frontend y backend
Cualquier desviación debe justificarse explícitamente