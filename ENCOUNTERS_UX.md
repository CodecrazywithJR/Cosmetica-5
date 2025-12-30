# INTERNACIONALIZACIÓN (i18n) DE ENCOUNTERS UX

## Idiomas soportados
- Español (es)
- Inglés (en)
- Francés (fr)
- Ruso (ru)
- Ucraniano (uk)
- Armenio (hy)

## Principios de traducción
- Todo texto visible debe pasar por i18n (títulos, labels, botones, mensajes, modales, tooltips)
- ❌ Prohibido hardcodear texto en cualquier idioma
- ❌ Prohibido concatenar strings manualmente
- Usar keys completas, nunca textos sueltos

## Microcopy clínica y traducciones
- Traducciones semánticas, no literales
- Tono profesional, clínico, neutral
- Evitar expresiones coloquiales o ambiguas
- Ejemplo:
  - ❌ “Algo salió mal”
  - ✅ “No se ha podido completar la acción”

## Longitud y layout
- Diseñar para textos largos (francés, ruso, armenio, ucraniano)
- Botones deben admitir crecimiento horizontal
- No truncar mensajes críticos
- Evitar layouts dependientes de longitud exacta

## Estados y errores (i18n)
- Todos los mensajes definidos en UX deben existir como keys i18n, por ejemplo:
  - encounters.empty.patient
  - encounters.empty.global
  - encounters.error.generic
  - encounters.error.forbidden
  - encounters.error.conflict
  - encounters.action.save
  - encounters.action.finalize
  - encounters.action.delete
- No definir textos sueltos sin key

## Confirmaciones y acciones
- Textos de confirmación completamente traducidos
- No depender del orden gramatical de un idioma concreto
- Evitar frases con variables mal colocadas
- Ejemplo correcto: “Esta consulta no podrá editarse una vez finalizada.”

## Idioma por defecto
- El idioma por defecto es el del usuario autenticado
- No depender del navegador
- No cambiar idioma dinámicamente sin acción explícita del usuario

## Prohibiciones absolutas
- ❌ No textos hardcodeados
- ❌ No concatenaciones
- ❌ No traducciones literales sin contexto clínico
- ❌ No layouts frágiles al idioma
- ❌ No decisiones implícitas del frontend

---
# UX CLÍNICA DE ENCOUNTERS — ESTADOS VACÍOS, ERRORES Y MICROCOPY (v1)

## 1. Estados vacíos (LISTA)
### 1.1 Paciente sin consultas
- Mensaje: “Este paciente aún no tiene consultas registradas.”
- Acción primaria: “Crear nueva consulta”
- No mostrar tablas vacías ni errores
### 1.2 Lista global sin resultados
- Mensaje: “No hay consultas que coincidan con los filtros seleccionados.”
- Acción secundaria: “Limpiar filtros”
- No ofrecer “crear consulta” desde lista global

## 2. Estados vacíos (DETALLE)
### 2.1 Consulta recién creada (draft vacío)
- Secciones clínicas vacías, editables
- No mostrar mensajes tipo “empieza a escribir”
- No forzar orden
- La ausencia de datos no es un error
### 2.2 Sin adjuntos
- Mensaje neutro: “No hay fotos clínicas adjuntas.” / “No hay documentos adjuntos.”
- CTA claro: “Añadir foto” / “Añadir documento”

## 3. Estados de error (NO técnicos)
### 3.1 Error de red / backend genérico (5xx, timeout, inesperado)
- Mensaje: “No se ha podido cargar la consulta.”
- Acción: “Reintentar”
- No mostrar códigos HTTP ni stack traces
### 3.2 Error de permisos (403)
- Mensaje: “No tienes permisos para acceder a esta consulta.”
- Acción: “Volver”
- No explicar roles ni mostrar “contacta con admin”
### 3.3 Concurrencia (409 row_version)
- Mensaje: “Esta consulta ha sido modificada desde otro dispositivo.”
- Explicación: “Para evitar sobrescribir cambios, necesitas recargar.”
- Acciones: “Recargar consulta” / “Cancelar”
- No merge automático ni ocultar el error

## 4. Estados de acción (feedback)
- Guardar: “Guardando…”, “Cambios guardados”
- Finalizar consulta:
  - Confirmación previa: “Una vez finalizada, la consulta no podrá editarse.”
  - Acciones: “Finalizar” / “Volver”
- Eliminar consulta:
  - Modal obligatorio
  - Mensaje: “Se eliminará esta consulta clínica.”
  - Botones: “Eliminar” / “Volver” (no usar “cancelar”)

## 5. Microcopy clínica (reglas)
- Lenguaje humano, frases cortas
- Nunca técnico, ambiguo ni infantil
- Ejemplos prohibidos: ❌ “Oops”, ❌ “Algo salió mal”, ❌ “Error inesperado”

## 6. Decisiones explícitas y prohibiciones
- ❌ No mensajes técnicos
- ❌ No pantallas “en blanco”
- ❌ No acciones ocultas
- ❌ No crear consultas desde estados vacíos incorrectos
- ❌ No ruido visual

---
# UX CLÍNICA DE ENCOUNTERS — CREACIÓN DE CONSULTA (v1)

## 1. Dónde se puede crear una Consulta
- Solo desde la ficha del Paciente (flujo principal v1)
  - Botón claro: “Nueva consulta” (solo roles clínicos)
- Desde Agenda: solo placeholder visual, sin lógica funcional (no inventar comportamiento)
- No se puede crear desde lista global ni desde otros contextos.

## 2. Reglas de creación
- ❌ No se crea una consulta “vacía” ni al abrir pantalla
- ✅ Solo se crea al confirmar el formulario
- Motivo: la consulta representa una visita real, no una cita ni un borrador fantasma.

## 3. Flujo UX de creación (desde Paciente)
### Paso 1 — Acción explícita
- Doctora pulsa “Nueva consulta”
### Paso 2 — Formulario mínimo (modal o página ligera)
- Campos obligatorios (solo backend):
  - Tipo de consulta (`type`)
  - Fecha/hora real (`occurred_at`, default: ahora)
  - Doctora (`practitioner`, default: usuaria actual)
- No incluir más campos. No pedir motivo, evaluación, plan ni adjuntos.
### Paso 3 — Confirmación
- Acciones: “Crear consulta” / “Cancelar”
- Al confirmar:
  - Backend crea Encounter en draft
  - Navegar automáticamente a página de detalle de la consulta

## 4. Errores y cancelaciones
- Si se cancela: ❌ No se crea nada
- Si falla creación: mostrar error claro, permanecer en ficha de Paciente

## 5. Estado inicial del Encounter
- Siempre: estado draft, editable, sin adjuntos ni campos clínicos rellenados

## 6. Permisos
- Solo Admin / ClinicalOps / Practitioner pueden crear consultas
- Accounting / Reception / Marketing:
  - ❌ No ven el botón
  - ❌ No ven estados vacíos
  - ❌ No reciben errores de permiso (no existe para ellos)

## 7. Navegación post-creación
- Tras crear: ir siempre al detalle de la consulta
- Botón “Volver” respeta contexto: vuelve a ficha del Paciente

## 8. Decisiones explícitas y prohibiciones
- ❌ No crear consulta automáticamente
- ❌ No crear desde lista global
- ❌ No mezclar cita y consulta
- ❌ No inventar flujos desde Agenda
- ❌ No crear consultas sin confirmación

---
# UX CLÍNICA DE ENCOUNTERS — PÁGINA DE DETALLE (v1)

## 1. Tipo de vista
- El detalle de Encounter es una **página completa** (no modal, no drawer).
  - Motivo: complejidad clínica, adjuntos, edición prolongada, estados terminales.

## 2. Estructura general de la página
- Secciones claras, visibles y escaneables:
  1. **Header fijo (arriba):**
     - Paciente (nombre completo)
     - Fecha/hora de la consulta (`occurred_at`)
     - Tipo de consulta (label humano)
     - Estado actual (badge: draft / finalized / cancelled)
     - Acciones disponibles (según estado):
       - Guardar
       - Finalizar consulta
       - Eliminar consulta
       - Volver a la lista de consultas (contextual)

## 3. Secciones clínicas (EDITABLES)
- Usar exactamente los campos del backend:
  - Motivo de consulta (`chief_complaint`): textarea
  - Evaluación (`assessment`): textarea
  - Plan (`plan`): textarea
  - Notas internas (`internal_notes`): textarea, claramente marcado como no visible para paciente
- No inventar más campos. No dividir ni fusionar campos.

## 4. Adjuntos (CRÍTICO)
### 4.1 Fotos clínicas
- Sección “Fotos clínicas” diferenciando:
  - Before
  - After
  - Progress
  - Other
- Upload desde iPhone (HEIC soportado, conversión transparente)
- Vista en grid
- Click → abrir en navegador (presigned URL)
- Hard delete con confirmación

### 4.2 Documentos
- Sección “Documentos”
- Tipos permitidos: PDF, Word, Excel, TXT
- Upload simple
- Click → abrir en navegador
- Hard delete con confirmación

## 5. Estados del Encounter
### 5.1 Draft
- Editable
- Se puede guardar, finalizar, eliminar
### 5.2 Finalized
- ❌ No editable
- Campos en modo lectura
- Adjuntos visibles
- No se puede volver a draft
### 5.3 Cancelled
- ❌ No editable
- Estado terminal, claramente diferenciado

## 6. Concurrencia (row_version)
- Si backend responde 409:
  - Mostrar mensaje claro: “Esta consulta ha sido modificada desde otro dispositivo”
  - Ofrecer: recargar datos, cancelar edición
- No hacer merge automático. No ocultar el error.

## 7. Guardado y feedback
- Guardado explícito (no autosave silencioso)
- Feedback visual claro: guardando, guardado correcto, error

## 8. Reglas de navegación
- Botón “Volver a la lista de consultas” siempre visible
- Respeta el contexto de origen (Paciente o Lista global)

## 9. Prohibiciones absolutas
- ❌ No inventar campos
- ❌ No autosave implícito
- ❌ No permitir edición en finalized/cancelled
- ❌ No esconder errores de concurrencia
- ❌ No diseñar para roles no clínicos

---
# UX CLÍNICA DE ENCOUNTERS — LISTA, NAVEGACIÓN Y ESTADOS (v1)

## 1. Ubicación de las listas de Encounters

- Se implementan dos vistas de lista:
  1. **Lista de Encounters dentro de la ficha del Paciente**
     - Contexto: “Estoy viendo a este paciente”
     - Uso principal diario
  2. **Lista Global de Encounters**
     - Accesible desde menú principal
     - Contexto: “Qué he hecho / qué está pasando hoy”
  - Ambas usan el mismo componente base, con distinto contexto.

## 2. Estructura y columnas de la lista

- **Columnas visibles (en este orden):**
  - Fecha / Hora (`occurred_at`, formato clínico legible)
  - Tipo (`type`, label humano)
  - Estado (`status`, badge visual: draft / finalized / cancelled)
  - Doctora (`practitioner_name`, “—” si null)
  - Tratamientos (`treatment_count`)
  - Adjuntos (indicador visual usando `attachments_summary`)
    - Distingue: tiene fotos, tiene documentos
  - (Opcional) Fecha de creación (`created_at`, solo para auditoría)
- **No añadir otras columnas.**
- **No inventar campos.**

## 3. Filtros y rango de fechas

- Filtros permitidos (solo los soportados por backend):
  - Paciente (cuando aplique)
  - Doctora
  - Estado
  - Rango de fechas (`date_from` / `date_to`)
- **Default obligatorio:** últimos 7 días (no “este mes”, no “sin filtro”)
- No hay búsqueda por texto libre.

## 4. Navegación y acceso a detalle

- Al hacer click en una fila: navegar a página de detalle (no modal, no drawer)
- Siempre debe haber botón claro de “Volver a la lista de consultas”
  - Si venía desde Paciente → vuelve al Paciente
  - Si venía desde Lista Global → vuelve a Lista Global
- Nunca depender del botón “atrás” del navegador.

## 5. Estados de carga y error

- LIST:
  - Skeleton/loading state claro
  - Si falla DETAIL, la lista NO debe romperse
- DETAIL:
  - Cargar datos clínicos + adjuntos
  - Manejar: loading, error, conflicto de concurrencia (409)

## 6. Principio técnico UX

- LIST ≠ DETAIL
  - La lista renderiza con datos de LIST endpoint
  - El detalle se pide bajo demanda (por ID)
  - Cache por ID
  - Invalidar cache cuando: se guarda, se elimina, se recarga lista

## 7. Decisiones explícitas y prohibiciones

- ❌ No inventar campos, estados ni flujos no soportados
- ❌ No inventar permisos ni roles
- ❌ No añadir acciones no soportadas por backend
- ❌ No diseñar para Accounting, Reception, Marketing
- ❌ No asumir comportamiento “intuitivo” fuera de lo documentado

---
# MIGRATION CHAIN INCIDENT (2025-12-29)

**Problema:**
Al ejecutar tests o migraciones en una base limpia, Django reportaba:
`Migration clinical.0101_encounter_attachment_counters dependencies reference nonexistent parent node ('clinical', '0100_auto_last')`

**Causa:**
La migración `0100_auto_last.py` no existía en el repositorio. Probablemente fue generada localmente y no versionada, o renombrada/borrada accidentalmente tras cambios recientes.

**Solución:**
- Se creó una migración "stub" vacía `0100_auto_last.py` que depende de la última migración real (`0014_add_patient_identity_emergency_legal_fields`).
- Esto repara la cadena y permite aplicar correctamente `0101_encounter_attachment_counters.py` y posteriores.
- No se pierde ningún dato ni se altera el schema en producción.

**Instrucciones para entornos nuevos o CI:**
```bash
python manage.py migrate clinical
python manage.py test tests/test_encounters_api.py
```
Esto inicializa la base y ejecuta los tests de concurrencia obligatorios.

**Notas:**
- No borres ni modifiques migraciones existentes sin revisar dependencias.
- Si vuelves a ver errores de cadena, revisa dependencias y crea stubs si es seguro hacerlo.

---
# ENCOUNTERS UX — Backend v1 Implementation

**Date**: 29 diciembre 2025  
**Status**: ✅ COMPLETE  
**Scope**: Soporte mínimo imprescindible para UX clínica de Encounters

---

## 1. RESUMEN FUNCIONAL

Backend v1 habilita en UX:
- ✅ Lista de Encounters (dentro de paciente y lista global para roles clínicos)
- ✅ Página de detalle editable de Encounter
- ✅ Adjuntos completos (fotos clínicas + documentos)
- ✅ Estados clínicos existentes (draft, finalized, cancelled)
- ✅ Soft delete de Encounter
- ✅ Hard delete de adjuntos (fotos y documentos)

---

## 2. CONTRATOS API

### Base URL
```
/api/v1/clinical/encounters/
```

### 2.1 LIST Endpoint

**Request:**
```http
GET /api/v1/clinical/encounters/
```

**Query Parameters:**
- `patient_id` (uuid): Filtrar por paciente
- `practitioner_id` (uuid): Filtrar por practicante
- `status` (string): draft | finalized | cancelled
- `date_from` (date): YYYY-MM-DD
- `date_to` (date): YYYY-MM-DD
- `limit` (int): Paginación (default 20)
- `offset` (int): Paginación (default 0)

**Response Fields:**
```json
{
  "results": [
    {
      "id": "uuid",
      "patient": "uuid",
      "patient_name": "string (computed)",
      "practitioner": "uuid | null",
      "practitioner_name": "string | null (computed)",
      "type": "string (enum)",
      "status": "draft | finalized | cancelled",
      "occurred_at": "datetime ISO 8601",
      "treatment_count": "integer (computed)",
      "attachments_summary": {
        "has_photos": "boolean",
        "has_documents": "boolean",
        "photo_count": "integer",
        "document_count": "integer"
      },
      "created_at": "datetime ISO 8601"
    }
  ],
  "count": "integer (total)"
}
```

**Orden fijo:** `occurred_at DESC` (consultas más recientes primero)

---

### 2.2 DETAIL Endpoint

**Request:**
```http
GET /api/v1/clinical/encounters/{id}/
```

**Response Fields:**
```json
{
  "id": "uuid",
  "patient": {
    "id": "uuid",
    "first_name": "string",
    "last_name": "string",
    "email": "string | null",
    "phone": "string | null"
  },
  "practitioner": {
    "id": "uuid",
    "display_name": "string",
    "specialty": "string | null"
  } | null,
  "location": "uuid | null",
  "type": "string (enum)",
  "status": "draft | finalized | cancelled",
  "occurred_at": "datetime ISO 8601",
  "chief_complaint": "string | null",
  "assessment": "string | null",
  "plan": "string | null",
  "internal_notes": "string | null",
  "encounter_treatments": [
    {
      "id": "uuid",
      "treatment": {
        "id": "uuid",
        "name": "string"
      },
      "quantity": "integer",
      "unit_price": "decimal",
      "notes": "string | null"
    }
  ],
  "photos": [
    {
      "id": "uuid",
      "classification": "before | after | clinical | progress | other",
      "created_at": "datetime ISO 8601",
      "url": "string (presigned URL, 1 hora de validez)",
      "filename": "string | null",
      "mime_type": "string",
      "size_bytes": "integer"
    }
  ],
  "documents": [
    {
      "id": "uuid",
      "created_at": "datetime ISO 8601",
      "url": "string (presigned URL, 1 hora de validez)",
      "filename": "string | null",
      "mime_type": "string",
      "size_bytes": "integer",
      "title": "string | null"
    }
  ],
  "signed_at": "datetime ISO 8601 | null",
  "signed_by_user": "uuid | null",
  "row_version": "integer",
  "created_at": "datetime ISO 8601",
  "updated_at": "datetime ISO 8601"
}
```

---

### 2.3 CREATE Endpoint

**Request:**
```http
POST /api/v1/clinical/encounters/
Content-Type: application/json

{
  "patient": "uuid (required)",
  "practitioner": "uuid | null",
  "location": "uuid | null",
  "type": "string (required)",
  "status": "draft (default) | finalized | cancelled",
  "occurred_at": "datetime ISO 8601 (required)",
  "chief_complaint": "string | null",
  "assessment": "string | null",
  "plan": "string | null",
  "internal_notes": "string | null",
  "encounter_treatments": [
    {
      "treatment_id": "uuid",
      "quantity": "integer",
      "unit_price": "decimal",
      "notes": "string | null"
    }
  ]
}
```

**Response:** Same as DETAIL

---


### 2.4 UPDATE Endpoint (PATCH /encounters/{id}/)

**Request:**
```http
PATCH /api/v1/clinical/encounters/{id}/
Content-Type: application/json

{
  "status": "finalized",
  "assessment": "Updated assessment text",
  "row_version": 3
}
```

**Business Rules:**
- Status transitions validadas:
  - `draft → finalized`
  - `draft → cancelled`
  - `finalized` es estado terminal (no cambios)
  - `cancelled` es estado terminal (no cambios)
- `encounter_treatments` no se actualizan aquí (endpoint separado futuro)
- **Control de concurrencia obligatorio:**
  - El campo `row_version` es **obligatorio** en cada PATCH.
  - Si el valor enviado no coincide con el valor actual en base de datos, la API responde:
    - **409 Conflict**
    - Body:
      ```json
      {
        "row_version": [
          "El registro fue modificado por otro usuario. Versión actual: 4, versión proporcionada: 3"
        ]
      }
      ```
  - El backend incrementa `row_version` automáticamente en cada actualización exitosa.
  - El cliente debe refrescar el DETAIL y reintentar si recibe 409.

**Response:** Same as DETAIL

---

### 2.5 DELETE Endpoint (Soft Delete)

**Request:**
```http
DELETE /api/v1/clinical/encounters/{id}/
```

**Response:** `204 No Content`

**Business Rule:** Soft delete (marca `is_deleted=True`, no elimina registro)

---

## 3. ADJUNTOS — FOTOS CLÍNICAS

### Sistema Utilizado
✅ **ClinicalPhoto** (Sistema B) con MinIO storage

### 3.1 Upload Photo

**Request:**
```http
POST /api/v1/clinical/encounters/{encounter_id}/photos/
Content-Type: multipart/form-data

file: <binary>
classification: "before" | "after" | "clinical" | "progress" | "other" (required)
```

**Validaciones:**
- ✅ Tipos permitidos: JPG, JPEG, PNG, WebP
- ✅ Límite: 10 MB
- ✅ Classification obligatoria
- ✅ MIME types: `image/jpeg`, `image/png`, `image/webp`

**Response:**
```json
{
  "id": "uuid",
  "upload_url": "string (presigned PUT URL, 15 min validity)",
  "object_key": "string (MinIO path)",
  "classification": "string"
}
```

**Upload Flow:**
1. Frontend POST con metadata → Backend crea registro y genera presigned URL
2. Frontend PUT directo a MinIO usando `upload_url`
3. Frontend refresca Encounter DETAIL para ver foto

---

### 3.2 List Photos

**Request:**
```http
GET /api/v1/clinical/encounters/{encounter_id}/photos/
```

**Response:**
```json
[
  {
    "id": "uuid",
    "classification": "before | after | clinical | progress | other",
    "created_at": "datetime ISO 8601",
    "url": "string (presigned GET URL, 1 hora)",
    "filename": "string | null",
    "mime_type": "string",
    "size_bytes": "integer"
  }
]
```

---

### 3.3 Delete Photo (Hard Delete)

**Request:**
```http
DELETE /api/v1/clinical/photos/{photo_id}/
```

**Response:** `204 No Content`

**Business Rule:**
- ✅ Hard delete (elimina registro de DB)
- ✅ Elimina archivo físico de MinIO
- ✅ Elimina relación con Encounter
- ❌ NO hay restauración

---

### 3.4 Download Photo

**Request:**
```http
GET /api/v1/clinical/photos/{photo_id}/download/
```

**Response:**
```json
{
  "url": "string (presigned GET URL, 1 hora)"
}
```

Frontend abre URL en nueva pestaña/ventana del navegador.

---

## 4. ADJUNTOS — DOCUMENTOS

### Sistema Utilizado
✅ **Document** (Sistema B) con MinIO storage

### 4.1 Upload Document

**Request:**
```http
POST /api/v1/clinical/encounters/{encounter_id}/documents/
Content-Type: multipart/form-data

file: <binary>
title: "string (optional, defaults to filename)"
```

**Validaciones:**
- ✅ Tipos permitidos: PDF, DOC, DOCX, XLS, XLSX, TXT
- ✅ Límite: 10 MB
- ✅ MIME types: 
  - `application/pdf`
  - `application/msword`
  - `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
  - `application/vnd.ms-excel`
  - `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
  - `text/plain`

**Response:**
```json
{
  "id": "uuid",
  "upload_url": "string (presigned PUT URL, 15 min validity)",
  "object_key": "string (MinIO path)",
  "title": "string"
}
```

**Upload Flow:** Same as photos

---

### 4.2 List Documents

**Request:**
```http
GET /api/v1/clinical/encounters/{encounter_id}/documents/
```

**Response:**
```json
[
  {
    "id": "uuid",
    "created_at": "datetime ISO 8601",
    "url": "string (presigned GET URL, 1 hora)",
    "filename": "string | null",
    "mime_type": "string",
    "size_bytes": "integer",
    "title": "string | null"
  }
]
```

---

### 4.3 Delete Document (Hard Delete)

**Request:**
```http
DELETE /api/v1/clinical/documents/{document_id}/
```

**Response:** `204 No Content`

**Business Rule:** Same as photos (hard delete)

---

### 4.4 Download Document

**Request:**
```http
GET /api/v1/clinical/documents/{document_id}/download/
```

**Response:**
```json
{
  "url": "string (presigned GET URL, 1 hora)"
}
```

---

## 5. PERMISOS POR ROL

| Rol | Encounters | Fotos | Documentos | Notas |
|-----|-----------|-------|------------|-------|
| **Admin** | Full CRUD | Full CRUD | Full CRUD | Acceso total |
| **ClinicalOps** | Full CRUD | Full CRUD | Full CRUD | Acceso a clinical_notes |
| **Practitioner** | Full CRUD | Full CRUD | Full CRUD | Acceso a clinical_notes |
| **Accounting** | ❌ NO ACCESS | ❌ NO ACCESS | ❌ NO ACCESS | Sin acceso clínico |
| **Reception** | ❌ NO ACCESS | ❌ NO ACCESS | ❌ NO ACCESS | Business rule: sin acceso clínico |
| **Marketing** | ❌ NO ACCESS | ❌ NO ACCESS | ❌ NO ACCESS | Sin acceso |

**CRITICAL:** Accounting fue cambiado de "Read Only" a "NO ACCESS" según decisión v1.

---

## 6. DIFERENCIAS LIST vs DETAIL

| Campo | LIST | DETAIL | Justificación |
|-------|------|--------|---------------|
| `patient` | UUID | Object | LIST: FK solo. DETAIL: Datos completos |
| `practitioner` | UUID | Object | LIST: FK solo. DETAIL: Datos completos |
| `patient_name` | ✅ Computed | ❌ N/A | LIST: Optimización (evita JOINs pesados) |
| `practitioner_name` | ✅ Computed | ❌ N/A | LIST: Optimización |
| `treatment_count` | ✅ Computed | ❌ N/A | LIST: Badge contador UX |
| `attachments_summary` | ✅ Computed | ❌ N/A | LIST: Indicadores visuales UX |
| `photos` | ❌ N/A | ✅ Array | DETAIL: URLs presigned requieren cómputo |
| `documents` | ❌ N/A | ✅ Array | DETAIL: URLs presigned requieren cómputo |
| `encounter_treatments` | ❌ N/A | ✅ Array | DETAIL: Nested data con prices |
| `assessment` | ❌ N/A | ✅ Full | DETAIL: Campos clínicos completos |
| `plan` | ❌ N/A | ✅ Full | DETAIL: Campos clínicos completos |
| `internal_notes` | ❌ N/A | ✅ Full | DETAIL: Campos clínicos completos |

**Principio de diseño:** LIST optimizado para performance, DETAIL optimizado para completitud.

---

## 7. DECISIONES ARQUITECTÓNICAS

### 7.1 Sistema de Adjuntos
✅ **FUSIÓN de Sistemas A y B:**
- Modelos: `ClinicalPhoto` + `Document` (Sistema B)
- Storage: MinIO (producción-ready, escalable)
- Clasificación: Before/After/Progress/Other (desde Sistema A)
- ❌ NO se usa `ClinicalMedia` (Sistema A descartado)

### 7.2 Presigned URLs
✅ **Implementación:**
- GET URLs: 1 hora de validez
- PUT URLs: 15 minutos de validez
- Ventajas: Sin proxy Django, mejor performance, seguridad temporal
- Archivo: [`apps/clinical/utils_storage.py`](apps/api/apps/clinical/utils_storage.py)

### 7.3 Hard Delete vs Soft Delete
- **Encounters:** Soft delete (reversible, auditoría)
- **Adjuntos (fotos/docs):** Hard delete (no restauración, libera storage)

---

## 8. GAPS Y LIMITACIONES v1

### Implementado en v1:
✅ LIST/DETAIL endpoints  
✅ Adjuntos completos (fotos + documentos)  
✅ Clasificación obligatoria de fotos  
✅ Hard delete de adjuntos  
✅ Permisos RBAC estrictos  
✅ Presigned URLs  

### NO implementado en v1 (futuro):
❌ **Endpoint crear Encounter desde Appointment:**  
  - Gap identificado: `POST /appointments/{id}/create-encounter/`
  - Workaround v1: Frontend llama `POST /encounters/` con `patient` del appointment
  
❌ **Thumbnail generation para fotos:**  
  - Gap: Solo URL completa disponible
  - Impact: UX load time en lista de fotos
  
❌ **Búsqueda fulltext en Encounters:**  
  - Gap: Solo filtros exactos disponibles
  - Workaround: Frontend implementa filtros básicos
  
❌ **Batch upload de adjuntos:**  
  - Gap: Upload one-by-one
  - Impact: UX lenta para múltiples fotos

❌ **OCR o metadata extraction de documentos:**  
  - Gap: Solo storage, sin procesamiento
  
❌ **Versioning de Encounters:**  
  - Gap: `row_version` existe pero no hay historial de cambios

---

## 9. ARCHIVOS IMPLEMENTADOS

### Nuevos archivos:
1. **[`apps/clinical/utils_storage.py`](apps/api/apps/clinical/utils_storage.py)**  
   Utilities MinIO: presigned URLs, object keys, delete helpers
   
2. **[`apps/clinical/views_photos.py`](apps/api/apps/clinical/views_photos.py)**  
   ClinicalPhotoViewSet: upload, list, delete, download
   
3. **[`apps/clinical/views_documents.py`](apps/api/apps/clinical/views_documents.py)**  
   DocumentViewSet: upload, list, delete, download

### Archivos modificados:
1. **[`apps/clinical/serializers.py`](apps/api/apps/clinical/serializers.py)**  
   - EncounterListSerializer: +`attachments_summary`
   - EncounterDetailSerializer: +`photos`, +`documents`
   
2. **[`apps/clinical/urls.py`](apps/api/apps/clinical/urls.py)**  
   Rutas nuevas:
   - `/encounters/{id}/photos/`
   - `/encounters/{id}/documents/`
   - `/photos/{id}/`
   - `/photos/{id}/download/`
   - `/documents/{id}/`
   - `/documents/{id}/download/`

### Sin cambios:
- **[`apps/clinical/permissions.py`](apps/api/apps/clinical/permissions.py)**  
  `EncounterPermission` ya tiene lógica correcta (Accounting NO acceso)
  
- **[`apps/clinical/models.py`](apps/api/apps/clinical/models.py)**  
  Sin cambios (modelos existentes correctos)

---

## 10. TESTING RECOMENDADO

### Manual Testing:
```bash
# 1. List encounters con attachments_summary
curl -X GET "http://localhost:8000/api/v1/clinical/encounters/" \
  -H "Authorization: Bearer {token}"

# 2. Detail con photos[] y documents[]
curl -X GET "http://localhost:8000/api/v1/clinical/encounters/{id}/" \
  -H "Authorization: Bearer {token}"

# 3. Upload photo
curl -X POST "http://localhost:8000/api/v1/clinical/encounters/{id}/photos/" \
  -H "Authorization: Bearer {token}" \
  -F "file=@photo.jpg" \
  -F "classification=before"

# 4. Upload document
curl -X POST "http://localhost:8000/api/v1/clinical/encounters/{id}/documents/" \
  -H "Authorization: Bearer {token}" \
  -F "file=@consent.pdf" \
  -F "title=Consent Form"

# 5. Delete photo (hard)
curl -X DELETE "http://localhost:8000/api/v1/clinical/photos/{photo_id}/" \
  -H "Authorization: Bearer {token}"
```

### Automated Tests (Recomendado para CI/CD):
- Unit tests: Serializers (attachments_summary computation)
- Integration tests: ViewSets (upload flow, permissions)
- E2E tests: Full workflow (create encounter → upload → delete)

---

## 11. MIGRACIÓN Y DEPLOYMENT

### Database Migrations:
❌ **NO se requieren migrations** (modelos ya existen en DB)

### MinIO Buckets Required:
- `derma-photos` (fotos clínicas)
- `documents` (documentos)

Verificar con:
```bash
docker exec emr-api-dev python manage.py shell -c "
from django.conf import settings
print('Clinical bucket:', settings.MINIO_CLINICAL_BUCKET)
print('Documents bucket:', settings.MINIO_DOCUMENTS_BUCKET)
"
```

### Environment Variables:
```env
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_USE_SSL=False
MINIO_PUBLIC_URL=http://localhost:9000
MINIO_CLINICAL_BUCKET=derma-photos
MINIO_DOCUMENTS_BUCKET=documents
```

---

## 12. PREGUNTAS ABIERTAS (PARA v2)

### Técnicas:
1. ¿Implementar thumbnail generation automática?
2. ¿Añadir virus scanning a uploads?
3. ¿Implementar batch upload de adjuntos?
4. ¿Añadir búsqueda fulltext (Elasticsearch)?

### Producto:
1. ¿Permitir adjuntos sin clasificación (generic "attachments")?
2. ¿Permitir restauración de adjuntos eliminados (soft delete)?
3. ¿Implementar "Encounter templates" para tipos comunes?
4. ¿Permitir comentarios/anotaciones en fotos?

---

## 13. NOTAS DE IMPLEMENTACIÓN

### Performance Considerations:
- `attachments_summary` en LIST hace 2 queries adicionales (JOINs optimizados con `.filter()`)
- URLs presigned se generan on-demand (no caching, expiran en 1 hora)
- MinIO direct upload evita bottleneck en Django

### Security Considerations:
- Presigned URLs no requieren auth adicional (ya son firmadas)
- RBAC verificado en cada endpoint (Admin/ClinicalOps/Practitioner only)
- Hard delete asegura eliminación física de datos sensibles

### UX Considerations:
- `attachments_summary` permite badges visuales sin cargar fotos completas
- Clasificación obligatoria fuerza workflow clínico correcto
- URLs válidas 1 hora evitan re-fetches innecesarios

---

## 14. RECÁLCULO DE CONTADORES CACHEADOS DE ADJUNTOS

### ¿Por qué es necesario?
Al añadir los campos cacheados `photo_count_cached`, `document_count_cached`, `has_photos_cached`, `has_documents_cached` al modelo Encounter, es obligatorio recalcular estos valores para todos los registros existentes, asegurando que la UX muestre siempre datos correctos y rápidos (sin queries adicionales en LIST).

### Comando de recálculo

**Archivo:** `apps/clinical/management/commands/recalc_encounter_attachment_counters.py`

**Uso:**
```bash
python manage.py recalc_encounter_attachment_counters
```

**Qué hace:**
- Itera por todos los Encounters no eliminados (`is_deleted=False`)
- Cuenta fotos reales asociadas (ClinicalPhoto no eliminadas)
- Cuenta documentos reales asociados (Document no eliminados)
- Actualiza los campos cacheados:
  - `photo_count_cached`
  - `document_count_cached`
  - `has_photos_cached` = `photo_count_cached > 0`
  - `has_documents_cached` = `document_count_cached > 0`
- Solo guarda si hay cambios (optimización)
- Ignora adjuntos eliminados (hard delete)
- Idempotente: puede ejecutarse múltiples veces sin efectos colaterales
- Optimizado: evita N+1 queries

**Cuándo ejecutarlo:**
- Tras aplicar la migración que añade los campos cacheados
- Tras importar datos históricos
- Siempre que se sospeche inconsistencia en los contadores

**Impacto en UX:**
- Garantiza que los badges y resúmenes de adjuntos en LIST sean correctos
- Evita mostrar contadores incorrectos tras migraciones o importaciones

**Ejemplo de ejecución:**
```bash
python manage.py recalc_encounter_attachment_counters
# Output esperado:
# Recalculando contadores de adjuntos en Encounter...
# Procesados: 1200, actualizados: 37
```

**Nota:**
- No usar data migrations automáticas para este recálculo
- No inicializar contadores a cero sin recalcular
- El comando es seguro y re-ejecutable

---

## 15. LÓGICA AUTOMÁTICA DE CONTADORES DE ADJUNTOS (FOTOS Y DOCUMENTOS)

### Garantía de consistencia
- Tras cada upload o hard delete de foto/documento, los campos cacheados del Encounter (`photo_count_cached`, `document_count_cached`, `has_photos_cached`, `has_documents_cached`) se recalculan y persisten automáticamente, siempre desde la base de datos.
- La lógica es **simétrica** para fotos y documentos: ambos flujos usan el mismo patrón y garantías.
- La operación es **transaccional**: si falla cualquier parte (creación, borrado, actualización de contadores), se hace rollback completo.
- No depende de comandos manuales, tareas batch ni cron jobs.
- LIST y DETAIL reflejan el estado correcto inmediatamente después de cada operación.

### Flujo de upload/delete

**Upload de foto/documento:**
1. Validar archivo y permisos.
2. Crear registro de foto/documento y relación con Encounter.
3. Recalcular y persistir contadores cacheados (`*_count_cached`, `has_*_cached`) usando COUNT real en BD.
4. Commit transaccional.

**Hard delete de foto/documento:**
1. Validar permisos.
2. Eliminar archivo físico de MinIO.
3. Eliminar registro de foto/documento y relación con Encounter.
4. Recalcular y persistir contadores cacheados (`*_count_cached`, `has_*_cached`) usando COUNT real en BD.
5. Commit transaccional.

### Casos borde cubiertos
- Subir primer adjunto → badge aparece en LIST inmediatamente.
- Eliminar último adjunto → badge desaparece.
- Encounter sin adjuntos → contadores coherentes (cero y false).
- Subidas concurrentes → contadores correctos (transacción + select_for_update).

### Relación con comando de recálculo
- El comando `recalc_encounter_attachment_counters` es solo para migraciones o importaciones masivas.
- En uso normal, los contadores siempre están correctos tras cada operación.
- Re-ejecutar el comando no produce cambios si la lógica automática está activa (idempotencia global).

### Prohibiciones
- ❌ No actualizar contadores solo en memoria.
- ❌ No depender del frontend para coherencia.
- ❌ No dejar TODOs ni lógica parcial.
- ❌ No asumir que siempre será +1 / -1: siempre se recalcula desde la BD.

---

**Documento generado:** 29 diciembre 2025  
**Versión:** v1.0  
**Siguiente revisión:** Post-testing UX
