# ENCOUNTER_UX_DECISIONS.md
Fecha: 2026-01-XX  
Estado: CANÓNICO (fuente de verdad UX)  
Ámbito: UX de **Encounters (Consultas médicas)** + **gestión de fotos y documentos clínicos** dentro del Encounter.  
Fuera de ámbito: Agenda/Calendly (ver PROJECT_DECISIONS.md §17) y consentimientos documentales del paciente (ver PATIENT_* docs).

---

## 0) Principios (lo que NO se negocia)

1) **Encounter = acto clínico**
- Todo lo clínico “de trabajo” ocurre en el Encounter: notas, fotos asociadas a esa consulta, documentos clínicos, propuestas.
- La ficha del paciente sirve para **ver histórico** y gestionar **administrativo/legal**, no para trabajar la consulta.

2) **Cero bloqueos clínicos por UX**
- No habrá campos obligatorios en el Encounter.
- La doctora puede **cerrar/finalizar cuando quiera**, aunque haya poca información escrita.

3) **No sensación de “a medias”**
- Evitar textos o estados tipo “pendiente”, “incompleto”, “en progreso” en UX.
- El Encounter es una consulta; puede estar en “borrador” mientras se escribe, pero la UX debe sentirse como consulta real, no tarea administrativa.

4) **UX limpia (no formulario clásico)**
- Se evita una pantalla tipo “formulario rígido” o “SAP”.
- Se evita también el “bloc de notas en blanco” sin estructura.
- Se adopta **estructura mínima elegante**: orden y claridad sin burocracia.

5) **i18n obligatorio**
- **No hay ni un solo texto hardcodeado**.
- Todo texto, placeholders, tooltips, labels, errores y toasts **siempre** por i18n en **6 idiomas** (en/es/fr/ru/uk/hy), como el resto del ERP.

---

## 1) Navegación y dónde vive el trabajo clínico

### 1.1 Entry points permitidos
- Desde **Agenda**: “Atender” crea/abre Encounter asociado a la visita.
- Desde **Paciente**: entrar al listado de encounters del paciente y abrir uno existente.

### 1.2 Regla de oro
- La doctora **trabaja** dentro del Encounter.
- La ficha del paciente **no** se convierte en “pantalla de trabajo clínico”.

---

## 2) Estructura visual del Encounter (pantalla)

### 2.1 Estilo general
- Pantalla con **estructura mínima**, limpia y elegante.
- No debe parecer un formulario clásico.
- No debe parecer un lienzo vacío sin guía.

### 2.2 Secciones mínimas (sin campos obligatorios)
La pantalla del Encounter se organiza en secciones (cards/blocks) como mínimo:

1) **Resumen / Cabecera**
- Identificación del paciente
- Fecha/hora de la consulta
- Estado del encounter (draft/finalized/cancelled)
- Acciones principales (ver 2.3)

2) **Notas clínicas**
- Campo(s) libres de texto (sin validaciones duras)
- Sin obligación de completar nada
- Suficiente estructura visual para que no parezca vacío

3) **Fotos clínicas (adjuntos visuales)**
- Sección dedicada, con UX de drag & drop (ver sección 3)

4) **Documentos clínicos del Encounter**
- Adjuntos no-foto relacionados con la consulta (informes, PDFs, etc.)
- Separados de los **consentimientos escaneados del paciente** (administrativo/legal).

5) **Proposals**
- Existe el concepto de “propuesta” (recomendaciones / tratamientos / posible venta).
- La existencia de proposals **no bloquea** ni condiciona el cierre clínico del encounter.

> Nota: Si el producto evoluciona, se podrán añadir secciones, pero la pantalla debe seguir siendo “mínima y limpia”.

### 2.3 Botón de Finalizar (y UX de cierre)
- No hay campos obligatorios.
- Finalizar debe ser posible en cualquier momento.
- La posición del botón se decide por UX (no dogmática), pero con este objetivo:
  - **que sea fácil de encontrar**
  - **que no genere cierres por accidente**

Decisión UX:
- El botón de finalizar **no debe invitar al error** (evitar “zarpazo” accidental).
- Si hay confirmación, debe ser **clara y breve**.

---

## 3) Fotos clínicas dentro del Encounter (decisiones cerradas)

### 3.1 Cómo se suben (UX)
- **Drag & Drop** como mecanismo principal.
- Se permite **selección múltiple** (arrastrar varias a la vez).
- Se evita el “explorador de Windows clásico” como experiencia principal.
- No mostrar panel permanente tipo “formulario”.
- La interfaz debe sentirse **fina/elegante**, no repetitiva ni “ruidosa”.

### 3.2 Qué fotos aparecen en un Encounter
- Un Encounter **solo muestra** fotos asociadas a ese Encounter.
- Las fotos “previas” pertenecen a consultas anteriores (otros encounters) y **no se mezclan automáticamente**.

Regla operativa:
- Si existen fotos clínicas “sueltas” (sin encounter asociado), el Encounter puede ofrecer una forma **limpia** de asociarlas:
  - “Fotos sin asociar” (solo las que tengan `encounter_id = null`) aparecen como candidatas.
  - La doctora decide qué fotos entran en esa consulta.

> Motivación: las fotos previas pueden corresponder a patologías diferentes y a consultas distintas.

### 3.3 Eliminación de fotos
- Eliminar debe requerir **confirmación** para evitar accidentes.
- Se prioriza evitar borrados involuntarios (decisión explícita).

### 3.4 Organización mínima para futuro (orden, estadísticas, ML)
La doctora es metódica y queremos que el Encounter no sea “un cajón”.
Por tanto:
- Debe existir una **estructura mínima** para ordenar el contenido (sin obligar).
- Esto ayudará en el futuro a:
  - búsquedas
  - reporting
  - estadísticas
  - machine learning

> Importante: esta estructura no puede convertir el Encounter en un formulario pesado.

### 3.5 Metadatos por foto (estado)
Decisión:
- Sería deseable que una foto pueda tener metadatos (comentario, fecha, etiqueta clínica).
- **Antes de diseñarlo definitivamente**, hay que verificar si el backend actual lo soporta (ClinicalPhoto/ClinicalMedia).
- Si el backend no lo soporta, se documenta como **fase 2**, sin bloquear el cierre UX actual.

---

## 4) Documentos del Encounter (no confundir con consentimientos escaneados)

### 4.1 Regla de separación
- **Consentimientos escaneados** (administrativos/legales) se gestionan en la **ficha del paciente**.
- **Documentos clínicos** de una consulta (informes, PDFs, etc.) se adjuntan al **Encounter**.

### 4.2 UX de documentos clínicos
- Adjuntar documentos en el Encounter debe ser simple y claro.
- Permitir ver/descargar/eliminar según permisos clínicos.
- No mezclar en la UI los “consent documents” del paciente con “encounter documents”.

---

## 5) Relación con la ficha del paciente (recordatorio canónico)

### 5.1 En ficha del paciente (administrativo/legal)
- Sí: gestionar consentimientos documentales (subir/ver/descargar/eliminar).
- No: trabajar clínica (notas, fotos “de consulta”).

### 5.2 En encounter (clínico)
- Sí: notas clínicas, fotos clínicas asociadas, documentos clínicos, proposals.
- No: consentimientos escaneados como “documentación del paciente”.

---

## 6) Requisitos de implementación (para Claude)

1) **i18n en 6 idiomas**: no hardcode.
2) UX **minimalista**: evitar pantallas de formulario clásico.
3) Drag & drop + multi-upload para fotos.
4) Confirmaciones para borrado (fotos y documentos).
5) No mezclar documentación administrativa del paciente con documentos clínicos del encounter.
6) No introducir bloqueos ni campos obligatorios.
7) Si faltan soportes de backend para metadatos por foto:
   - no inventar hacks en frontend
   - documentar gap y proponer evolución limpia del modelo.

---

## 7) Pendientes explícitos (no resueltos aún)
- Verificar modelo backend para metadatos por imagen (comentarios/etiquetas).
- Definir exactamente el set mínimo de metadatos (si procede) sin burocracia.
- Revisar el “timeline”/histórico de encounters del paciente para acceder a fotos previas de forma natural.

## Principios UX y alcance del Encounter (canónico)
Principios UX y alcance del Encounter (canónico)
Separación estricta de responsabilidades (paciente vs consulta)
El sistema distingue de forma estricta entre documentación del paciente y contenido clínico de una consulta (Encounter):
Paciente:
Documentación administrativa y legal (consentimientos escaneados, PDFs, imágenes firmadas).
Estos documentos no pertenecen a una consulta concreta y tienen valor histórico y legal.
Encounter (consulta médica):
Contenido estrictamente clínico asociado a un acto médico concreto:
notas clínicas, observaciones y fotos clínicas.
No existe solapamiento entre ambos ámbitos.
Gestión de fotos clínicas
Las fotos clínicas solo se pueden subir desde un Encounter.
La ficha del paciente NO permite subir fotos clínicas.
Una foto clínica pertenece siempre a un único Encounter.
Las fotos clínicas no se heredan automáticamente entre consultas.
Las fotos de consultas anteriores se consultan navegando por el historial de encounters del paciente.
Esto evita mezclar imágenes de distintas patologías, tratamientos o momentos clínicos.
Flujo de subida de fotos en Encounter
Las fotos se adjuntan manualmente por la doctora durante la consulta.
El mecanismo principal es drag & drop múltiple directamente sobre el Encounter.
No se usan modales de sistema (explorador de archivos) como flujo principal.
El sistema permite subir varias imágenes de forma simultánea.
Antes de confirmar, el sistema permite eliminar imágenes seleccionadas para evitar subidas accidentales.
Metadatos de imágenes clínicas (v1)
En la versión actual del sistema:
Las imágenes clínicas NO tienen comentarios, etiquetas ni metadatos clínicos manuales.
No se añaden fechas personalizadas ni descripciones por imagen.
Los únicos metadatos almacenados son:
fecha de subida
usuario que sube la imagen
relación con el Encounter
datos técnicos del archivo (tamaño, tipo, hash)
Cualquier enriquecimiento semántico (comentarios, anotaciones, IA, estadísticas) queda explícitamente fuera de alcance de esta fase.
Filosofía UX del Encounter
El Encounter no es un formulario.
No existen campos obligatorios.
El botón de “Finalizar consulta” está siempre disponible.
La estructura visual es mínima y no intrusiva.
El sistema no bloquea el cierre por falta de datos, imágenes o documentos.
El objetivo es reflejar el trabajo real de la doctora, no imponer un flujo administrativo artificial.
2️⃣ TABLA DE COHERENCIA (PARA DEJARLO BLINDADO)
👉 Puedes pegar esta tabla justo después, como sección
## Coherencia documental (fuente de verdad)
Coherencia documental (fuente de verdad)
Tema	Decisión canónica	Documento que manda	Notas
Entidad clínica principal	Encounter	ENCOUNTERS_BUENO.md	No existe entidad “Clinical” separada
Fotos clínicas	Solo en Encounter	ENCOUNTERS_BUENO.md	Nunca en ficha de paciente
Documentos escaneados (PDF/JPG)	Solo en Paciente	PATIENT_* + PROJECT_DECISIONS.md	Consentimientos y legales
Herencia de fotos entre consultas	❌ No	ENCOUNTERS_BUENO.md	Historial vía lista de encounters
Subida de fotos	Manual, drag & drop múltiple	ENCOUNTERS_BUENO.md	Sin modales intrusivos
Metadatos de imágenes	Mínimos (v1)	ENCOUNTERS_BUENO.md	Sin comentarios ni tags
Campos obligatorios en Encounter	❌ Ninguno	ENCOUNTERS_BUENO.md	Cierre siempre posible
Bloqueos clínicos	❌ No existen	PROJECT_DECISIONS.md	Solo avisos informativos
Proposals / ventas	Separadas del cierre clínico	PROJECT_DECISIONS.md	No bloquean Encounter
Agenda	Calendly es fuente de verdad	PROJECT_DECISIONS.md §17	ERP nunca inventa citas
Subida de documentos clínicos	❌ No	ENCOUNTERS_BUENO.md	Solo fotos clínicas
Nota final de gobierno del sistema
ENCOUNTERS_BUENO.md es el documento canónico para cualquier decisión presente o futura relacionada con:
UX de consultas
Fotos clínicas
Flujo de trabajo médico
Cierre de consulta
Si otro documento entra en conflicto con este, prevalece este documento.
---

Aclaraciones Canónicas UX – Encounter Detail (v1)
La pantalla de detalle de Encounter representa una consulta médica real ya iniciada, no un contenedor genérico ni un formulario administrativo.
Se establecen las siguientes aclaraciones definitivas:
El Encounter se crea vacío pero consciente
Solo se crea mediante acción explícita (“Nueva consulta”).
El estado inicial es siempre draft.
No existen campos obligatorios a nivel UX (solo backend mínimos).
La estructura no debe parecer un formulario
No se usan layouts tipo “formulario largo”.
Las secciones aparecen como bloques clínicos progresivos.
El diseño prioriza escritura natural y revisión clínica, no validación.
El botón “Finalizar consulta”
Está siempre visible mientras el Encounter esté en draft.
Puede accionarse en cualquier momento.
No valida contenido clínico (no hay campos obligatorios).
Cambia el estado a finalized, que es terminal y de solo lectura.
Gestión de fotos e imágenes clínicas
Las imágenes solo se asocian a un Encounter (no al Paciente).
No existe subida de fotos desde la ficha del paciente.
Una imagen pertenece a una única consulta y responde a una patología concreta.
No se arrastran automáticamente imágenes previas a un nuevo Encounter.
Subida de imágenes (UX)
Se realiza mediante drag & drop múltiple.
El área de drop no es permanente:
Aparece al pasar el cursor o iniciar arrastre.
Evita sensación de formulario o “panel fijo”.
Se permite selección múltiple y subida en lote.
La acción de eliminar imágenes requiere confirmación explícita (evitar borrados accidentales).
Adjuntos previos (“antes”)
El histórico visual del paciente se consulta a través de la lista de Encounters.
Cada Encounter conserva su propio contexto clínico.
No se mezclan imágenes de distintas consultas.
Metadatos y comentarios de imágenes
En v1, las imágenes no tienen comentarios clínicos complejos.
El modelo actual soporta fecha, autor y relación con Encounter.
Anotaciones avanzadas quedan fuera de alcance v1 (posible v2).
Estas decisiones son definitivas para la UX v1 y prevalecen sobre interpretaciones implícitas en documentos anteriores.
📊 TABLA DE COHERENCIA (PARA INCLUIR EN ENCOUTERS_BUENO.md)
Tema	ENCOUNTERS_UX.md	ENCOUNTER_DETAIL_UX.md	Decisión Canónica
Creación de Encounter	✔️ Acción explícita	✔️ Implícito	✔️ Crear solo bajo confirmación
Estado inicial	✔️ Draft	✔️ Draft	✔️ Draft siempre
Campos obligatorios UX	✔️ No	✔️ No	✔️ Ninguno
Botón Finalizar	⚠️ Implícito	⚠️ Implícito	✔️ Siempre visible en draft
Estructura tipo formulario	❌ Prohibida	❌ Prohibida	✔️ Bloques clínicos
Subida de fotos	✔️ Adjuntos por Encounter	✔️ Attachments section	✔️ Drag & drop múltiple
Fotos en ficha paciente	❌ No	❌ No	✔️ Nunca
Reutilizar fotos previas	❌ No	❌ No	✔️ Histórico por Encounter
Eliminación de fotos	⚠️ No detallado	⚠️ No detallado	✔️ Confirmación explícita
Comentarios en imágenes	❌ v1	❌ v1	✔️ Fuera de alcance v1
Leyenda
✔️ coherente · ⚠️ implícito (aclarado ahora) · ❌ explícitamente prohibido
🧭 RECOMENDACIÓN FINAL
ENCOUTERS_BUENO.md queda como fuente única de verdad UX.
Los otros .md pueden mantenerse como:
histórico,
detalle técnico,
o apoyo para frontend/backend.
Claude debe alinearse solo con ENCOUTERS_BUENO.md.