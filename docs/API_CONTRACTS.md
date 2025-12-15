# API Contracts

## Objetivo del Documento

Este documento define los contratos REST de la API backend para el sistema de gestión de clínica dermatológica/cosmética. Especifica endpoints, formatos de request/response JSON, códigos de error, permisos por rol y convenciones generales. Cubre únicamente los módulos **clinical** y **scheduling** (pacientes, citas, encounters, consentimientos, fotos clínicas, documentos). Los módulos de **commerce**, **website** y **social** quedan fuera del alcance de este documento.

Este documento sirve como contrato entre frontend y backend, y como especificación previa a la implementación en Django REST Framework.

---

## Principios Generales

### Base Path
Todos los endpoints están bajo el prefijo `/api/v1/`.

### Formato
- **Request**: `Content-Type: application/json` (salvo uploads multipart/form-data)
- **Response**: `Content-Type: application/json`
- **Encoding**: UTF-8
- **Timestamps**: ISO 8601 UTC (`2025-12-13T14:30:00Z`)

### Códigos de Estado HTTP
- `200 OK`: Operación exitosa (GET, PATCH, PUT)
- `201 Created`: Recurso creado (POST)
- `204 No Content`: Operación exitosa sin cuerpo (DELETE)
- `400 Bad Request`: Validación fallida, parámetros inválidos
- `401 Unauthorized`: Token JWT ausente o inválido
- `403 Forbidden`: Usuario autenticado pero sin permisos para la acción
- `404 Not Found`: Recurso no existe o está soft-deleted sin permisos para verlo
- `409 Conflict`: Conflicto de concurrencia (row_version no coincide) o merge inválido
- `500 Internal Server Error`: Error del servidor

### Formato de Errores
Todas las respuestas de error incluyen:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Descripción legible del error",
    "details": {
      "field_name": ["Error específico del campo"]
    }
  }
}
```

Códigos de error comunes:
- `VALIDATION_ERROR`: Datos inválidos (400)
- `AUTHENTICATION_FAILED`: Token inválido/expirado (401)
- `PERMISSION_DENIED`: Sin permisos (403)
- `NOT_FOUND`: Recurso no encontrado (404)
- `CONFLICT`: Concurrencia o merge inválido (409)
- `INTERNAL_ERROR`: Error del servidor (500)

### Paginación
Endpoints de listado soportan paginación basada en página:
```
GET /api/v1/patients/?page=2&page_size=20
```

Response:
```json
{
  "count": 150,
  "next": "http://api.example.com/api/v1/patients/?page=3&page_size=20",
  "previous": "http://api.example.com/api/v1/patients/?page=1&page_size=20",
  "results": [...]
}
```

Defaults:
- `page_size`: 20 (máximo 100)

### Filtros
Endpoints de listado soportan filtros vía query params:
- `?search=term`: Búsqueda full-text en campos relevantes
- `?is_deleted=true`: Incluir soft-deleted (solo Admin)
- `?created_at__gte=2025-01-01`: Filtros por fecha
- `?guardian_id={uuid}`: Filtros por relación (ej: pacientes de un guardian)

### Ordenamiento
Soportado vía `?ordering=field`:
```
GET /api/v1/patients/?ordering=-created_at
```
- Ascendente: `?ordering=last_name`
- Descendente: `?ordering=-created_at`

---

## Convenciones

### UUIDs
Todos los recursos usan UUIDs como primary key. Ejemplo:
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab"
}
```

### Soft Delete
Por defecto, todos los endpoints de listado/detalle **excluyen** recursos con `is_deleted=true`.

**Para usuarios con rol Admin:**
- Pueden incluir soft-deleted con `?include_deleted=true`
- Response incluye campos: `is_deleted`, `deleted_at`, `deleted_by_user_id`

**Para otros roles:**
- Solo ven recursos activos (`is_deleted=false`)
- Los recursos soft-deleted retornan `404 Not Found`

Ejemplo de recurso soft-deleted (solo visible para Admin con filtro):
```json
{
  "id": "...",
  "is_deleted": true,
  "deleted_at": "2025-11-20T10:15:00Z",
  "deleted_by_user_id": "..."
}
```

### Optimistic Locking (row_version)
Los modelos `Patient` y `Encounter` implementan control de concurrencia optimista.

**En GET (detalle):**
```json
{
  "id": "...",
  "row_version": 3,
  "first_name": "María"
}
```

**En PATCH (update):**
Request debe incluir `row_version` actual:
```json
{
  "row_version": 3,
  "first_name": "María Isabel"
}
```

**Conflicto de concurrencia:**
Si otro usuario modificó el recurso (row_version cambió), el servidor responde:
```http
HTTP/1.1 409 Conflict
Content-Type: application/json

{
  "error": {
    "code": "CONFLICT",
    "message": "El recurso fue modificado por otro usuario. Recarga los datos.",
    "details": {
      "current_row_version": 4,
      "provided_row_version": 3
    }
  }
}
```

Cliente debe:
1. Hacer GET para obtener versión actualizada
2. Reintegrar cambios del usuario
3. Reintentar PATCH con nuevo `row_version`

---

## Autenticación JWT

### POST /api/v1/auth/token/
Obtiene par de tokens (access + refresh) con credenciales.

**Request:**
```json
{
  "email": "doctor@clinica.com",
  "password": "SecurePass123!"
}
```

**Response (200 OK):**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "doctor@clinica.com",
    "first_name": "Juan",
    "last_name": "Pérez",
    "is_active": true
  }
}
```

**Errores:**
- `401 Unauthorized`: Credenciales inválidas
```json
{
  "error": {
    "code": "AUTHENTICATION_FAILED",
    "message": "Email o contraseña incorrectos"
  }
}
```

**Uso del access token:**
Incluir en header de todas las requests autenticadas:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Duración:**
- `access`: 1 hora
- `refresh`: 7 días

---

### POST /api/v1/auth/token/refresh/
Renueva access token usando refresh token.

**Request:**
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 OK):**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Errores:**
- `401 Unauthorized`: Refresh token inválido/expirado
```json
{
  "error": {
    "code": "AUTHENTICATION_FAILED",
    "message": "Refresh token inválido o expirado. Vuelva a iniciar sesión."
  }
}
```

---

## Matriz de Permisos por Rol

### Roles Definidos
Según `apps/authz/models.py`:
- **Admin**: Control total del sistema
- **Practitioner**: Médicos/dermatólogos que atienden pacientes
- **Reception**: Personal de recepción y agendamiento
- **Marketing**: Gestión de contenido, redes sociales (NO acceso a clinical)
- **Accounting**: Gestión financiera (facturación, pagos)

---

### Pacientes (Patient, PatientGuardian)

| Acción                     | Admin | Practitioner | Reception | Marketing | Accounting |
|----------------------------|-------|--------------|-----------|-----------|------------|
| Ver listado de pacientes   | ✅    | ✅           | ✅        | ❌        | ✅         |
| Ver detalle de paciente    | ✅    | ✅           | ✅        | ❌        | ✅         |
| Buscar pacientes           | ✅    | ✅           | ✅        | ❌        | ✅         |
| Crear paciente             | ✅    | ✅           | ✅        | ❌        | ❌         |
| Editar paciente            | ✅    | ✅           | ✅        | ❌        | ❌         |
| Soft-delete paciente       | ✅    | ❌           | ❌        | ❌        | ❌         |
| Ver pacientes eliminados   | ✅    | ❌           | ❌        | ❌        | ❌         |
| Merge pacientes duplicados | ✅    | ✅           | ❌        | ❌        | ❌         |
| Gestionar guardians        | ✅    | ✅           | ✅        | ❌        | ❌         |

**Notas:**
- Marketing **NO** tiene acceso a datos de pacientes (GDPR/HIPAA)
- Accounting puede **ver** pacientes para facturación, no modificar datos clínicos
- Solo Admin puede ver pacientes soft-deleted con `?include_deleted=true`

---

### Citas (Appointment)

| Acción                        | Admin | Practitioner | Reception | Marketing | Accounting |
|-------------------------------|-------|--------------|-----------|-----------|------------|
| Ver listado de citas          | ✅    | ✅           | ✅        | ❌        | ❌         |
| Ver detalle de cita           | ✅    | ✅           | ✅        | ❌        | ❌         |
| Crear cita manual             | ✅    | ✅           | ✅        | ❌        | ❌         |
| Editar cita                   | ✅    | ✅           | ✅        | ❌        | ❌         |
| Cancelar cita                 | ✅    | ✅           | ✅        | ❌        | ❌         |
| Sincronizar desde Calendly    | ✅    | ❌           | ✅        | ❌        | ❌         |
| Ver citas de todos practitioners | ✅ | ❌           | ✅        | ❌        | ❌         |

**Notas:**
- Practitioners solo ven **sus propias citas** (filtro implícito por `practitioner_id`)
- Reception y Admin ven citas de todos los practitioners
- Sincronización Calendly es tarea de Admin o Reception

---

### Encounters (Visitas Clínicas)

| Acción                      | Admin | Practitioner | Reception | Marketing | Accounting |
|-----------------------------|-------|--------------|-----------|-----------|------------|
| Ver listado de encounters   | ✅    | ✅           | ❌        | ❌        | ✅         |
| Ver detalle de encounter    | ✅    | ✅           | ❌        | ❌        | ✅         |
| Crear encounter (draft)     | ✅    | ✅           | ❌        | ❌        | ❌         |
| Editar encounter (draft)    | ✅    | ✅           | ❌        | ❌        | ❌         |
| Finalizar encounter         | ✅    | ✅           | ❌        | ❌        | ❌         |
| Ver timeline de paciente    | ✅    | ✅           | ❌        | ❌        | ❌         |
| Soft-delete encounter       | ✅    | ❌           | ❌        | ❌        | ❌         |

**Notas:**
- Reception **NO** puede ver ni crear encounters (datos clínicos sensibles)
- Accounting puede **ver** encounters para facturación (sin modificar)
- Solo Practitioner que creó el encounter puede editarlo (mientras `status=draft`)
- Admin puede editar/eliminar cualquier encounter

---

### Consentimientos (Consent)

| Acción                       | Admin | Practitioner | Reception | Marketing | Accounting |
|------------------------------|-------|--------------|-----------|-----------|------------|
| Ver consentimientos de paciente | ✅ | ✅           | ✅        | ❌        | ❌         |
| Otorgar consentimiento       | ✅    | ✅           | ✅        | ❌        | ❌         |
| Revocar consentimiento       | ✅    | ✅           | ✅        | ❌        | ❌         |
| Ver estado de consentimiento | ✅    | ✅           | ✅        | ❌        | ❌         |

**Notas:**
- Reception puede gestionar consents para proceso de admisión
- Marketing **NO** puede ver consents (datos sensibles)
- Consents son inmutables: revocar crea nuevo registro con `is_granted=false`

---

### Fotos Clínicas (ClinicalPhoto, EncounterPhoto)

| Acción                           | Admin | Practitioner | Reception | Marketing | Accounting |
|----------------------------------|-------|--------------|-----------|-----------|------------|
| Ver fotos clínicas de paciente   | ✅    | ✅           | ❌        | ❌        | ❌         |
| Subir foto clínica (standalone)  | ✅    | ✅           | ❌        | ❌        | ❌         |
| Adjuntar foto a encounter        | ✅    | ✅           | ❌        | ❌        | ❌         |
| Desadjuntar foto de encounter    | ✅    | ✅           | ❌        | ❌        | ❌         |
| Ver comparativa before/after     | ✅    | ✅           | ❌        | ❌        | ❌         |
| Soft-delete foto                 | ✅    | ❌           | ❌        | ❌        | ❌         |

**Notas:**
- Fotos clínicas **NUNCA** son accesibles por Marketing (almacenadas en bucket `clinical`)
- ClinicalPhoto es **inmutable** (solo soft-delete, nunca actualización)
- EncounterPhoto es tabla M:N con `relation_type` (before/during/after)

---

### Documentos (Document, EncounterDocument)

| Acción                            | Admin | Practitioner | Reception | Marketing | Accounting |
|-----------------------------------|-------|--------------|-----------|-----------|------------|
| Ver documentos de paciente        | ✅    | ✅           | ✅        | ❌        | ✅         |
| Subir documento                   | ✅    | ✅           | ✅        | ❌        | ✅         |
| Adjuntar documento a encounter    | ✅    | ✅           | ❌        | ❌        | ❌         |
| Descargar documento               | ✅    | ✅           | ✅        | ❌        | ✅         |
| Soft-delete documento             | ✅    | ❌           | ❌        | ❌        | ❌         |

**Notas:**
- Documents incluyen: PDF lab results, consentimientos firmados, prescripciones
- Accounting puede subir facturas/recibos (`kind=invoice`)
- EncounterDocument tiene `kind` (lab_result, prescription, consent_form, invoice, other)

---

### Resumen de Restricciones por Rol

**Marketing:**
- **SIN ACCESO** a: pacientes, citas, encounters, fotos clínicas, documentos
- **CON ACCESO** a: módulos website y social (fuera del alcance de este documento)

**Reception:**
- **CON ACCESO** a: pacientes, guardians, citas, consentimientos, documentos (no clínicos)
- **SIN ACCESO** a: encounters, fotos clínicas, documentos adjuntos a encounters

**Accounting:**
- **SOLO LECTURA** en: pacientes, encounters (para facturación)
- **CON ACCESO** a: documentos tipo `invoice`
- **SIN ACCESO** a: citas, fotos clínicas, consentimientos

**Practitioner:**
- **ACCESO COMPLETO** a datos clínicos (pacientes, encounters, fotos, consentimientos)
- **FILTRO IMPLÍCITO**: Solo ve sus propias citas/encounters (salvo Admin)

**Admin:**
- **ACCESO TOTAL** a todos los recursos
- Único rol que puede soft-delete y ver recursos eliminados

---

## Patients & Guardians (PAC)

### POST /api/v1/patients/
Crea un nuevo paciente.

**Roles permitidos:** Admin, Practitioner, Reception

**Request:**
```json
{
  "first_name": "María",
  "last_name": "González",
  "date_of_birth": "1992-05-15",
  "gender": "female",
  "email": "maria.gonzalez@example.com",
  "phone": "5551234567",
  "country_code": "MX",
  "address_line1": "Calle Reforma 123",
  "address_line2": "Depto 4B",
  "city": "Ciudad de México",
  "state_province": "CDMX",
  "postal_code": "06600",
  "country": "México",
  "referral_source_id": "123e4567-e89b-12d3-a456-426614174000",
  "notes": "Paciente referida por campaña Facebook"
}
```

**Campos obligatorios:**
- `first_name`, `last_name`, `date_of_birth`, `gender`

**Campos opcionales:**
- `email`, `phone`, `country_code` (default: "MX")
- `address_line1`, `address_line2`, `city`, `state_province`, `postal_code`, `country`
- `referral_source_id` (FK a ReferralSource)
- `notes`

**Response (201 Created):**
```json
{
  "id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
  "first_name": "María",
  "last_name": "González",
  "date_of_birth": "1992-05-15",
  "gender": "female",
  "email": "maria.gonzalez@example.com",
  "phone": "5551234567",
  "country_code": "MX",
  "address_line1": "Calle Reforma 123",
  "address_line2": "Depto 4B",
  "city": "Ciudad de México",
  "state_province": "CDMX",
  "postal_code": "06600",
  "country": "México",
  "referral_source_id": "123e4567-e89b-12d3-a456-426614174000",
  "notes": "Paciente referida por campaña Facebook",
  "is_merged": false,
  "merged_into_patient_id": null,
  "merge_reason": null,
  "row_version": 1,
  "is_deleted": false,
  "created_at": "2025-12-13T14:30:00Z",
  "updated_at": "2025-12-13T14:30:00Z",
  "created_by_user_id": "abc12345-...",
  "updated_by_user_id": "abc12345-..."
}
```

**Errores:**
- `400 Bad Request`: Validación fallida (ej: email duplicado, fecha futura, gender inválido)
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Datos inválidos",
    "details": {
      "email": ["Ya existe un paciente con este email"],
      "date_of_birth": ["La fecha de nacimiento no puede ser futura"]
    }
  }
}
```
- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Marketing/Accounting intentan crear paciente

---

### GET /api/v1/patients/
Lista pacientes con búsqueda y filtros.

**Roles permitidos:** Admin, Practitioner, Reception, Accounting

**Query Parameters:**
- `q` (string): Búsqueda full-text en `first_name`, `last_name`, `email`, `phone`
- `email` (string): Filtro exacto por email
- `phone` (string): Filtro exacto por teléfono
- `country_code` (string): Filtro por país (ej: "MX", "US")
- `include_deleted` (boolean): Incluir soft-deleted (solo Admin, default: false)
- `page` (int): Número de página (default: 1)
- `page_size` (int): Resultados por página (default: 20, max: 100)
- `ordering` (string): Campo de ordenamiento (ej: `last_name`, `-created_at`)

**Ejemplos:**
```
GET /api/v1/patients/?q=maría
GET /api/v1/patients/?email=maria@example.com
GET /api/v1/patients/?country_code=MX&ordering=last_name
GET /api/v1/patients/?include_deleted=true  (solo Admin)
```

**Response (200 OK):**
```json
{
  "count": 150,
  "next": "http://api.example.com/api/v1/patients/?page=2",
  "previous": null,
  "results": [
    {
      "id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
      "first_name": "María",
      "last_name": "González",
      "date_of_birth": "1992-05-15",
      "gender": "female",
      "email": "maria.gonzalez@example.com",
      "phone": "5551234567",
      "country_code": "MX",
      "is_merged": false,
      "row_version": 3,
      "is_deleted": false,
      "created_at": "2025-12-13T14:30:00Z",
      "updated_at": "2025-12-13T16:45:00Z"
    },
    {
      "id": "abc12345-...",
      "first_name": "Juan",
      "last_name": "Martínez",
      "date_of_birth": "1985-08-22",
      "gender": "male",
      "email": "juan.martinez@example.com",
      "phone": "5559876543",
      "country_code": "MX",
      "is_merged": false,
      "row_version": 1,
      "is_deleted": false,
      "created_at": "2025-12-10T10:20:00Z",
      "updated_at": "2025-12-10T10:20:00Z"
    }
  ]
}
```

**Notas:**
- Por defecto, **excluye** pacientes con `is_deleted=true`
- Solo Admin puede usar `?include_deleted=true` para ver pacientes eliminados
- Búsqueda `?q=` es case-insensitive y busca en múltiples campos
- Pacientes con `is_merged=true` aparecen en resultados (hasta que sean soft-deleted)

**Errores:**
- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Marketing intenta acceder

---

### GET /api/v1/patients/{id}/
Obtiene detalle de un paciente por UUID.

**Roles permitidos:** Admin, Practitioner, Reception, Accounting

**Response (200 OK):**
```json
{
  "id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
  "first_name": "María",
  "last_name": "González",
  "date_of_birth": "1992-05-15",
  "gender": "female",
  "email": "maria.gonzalez@example.com",
  "phone": "5551234567",
  "country_code": "MX",
  "address_line1": "Calle Reforma 123",
  "address_line2": "Depto 4B",
  "city": "Ciudad de México",
  "state_province": "CDMX",
  "postal_code": "06600",
  "country": "México",
  "referral_source_id": "123e4567-e89b-12d3-a456-426614174000",
  "referral_source": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "Facebook Ads - Promoción Botox",
    "source_type": "paid_ad"
  },
  "notes": "Paciente referida por campaña Facebook",
  "is_merged": false,
  "merged_into_patient_id": null,
  "merge_reason": null,
  "row_version": 3,
  "is_deleted": false,
  "deleted_at": null,
  "deleted_by_user_id": null,
  "created_at": "2025-12-13T14:30:00Z",
  "updated_at": "2025-12-13T16:45:00Z",
  "created_by_user_id": "abc12345-...",
  "updated_by_user_id": "def67890-..."
}
```

**Errores:**
- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Marketing intenta acceder
- `404 Not Found`: Paciente no existe o está soft-deleted (para no-Admin)

**Notas:**
- Incluye objeto anidado `referral_source` si existe
- Admin puede ver pacientes soft-deleted (incluye `deleted_at`, `deleted_by_user_id`)
- Otros roles reciben `404` si paciente tiene `is_deleted=true`

---

### PATCH /api/v1/patients/{id}/
Actualiza un paciente existente. **Requiere row_version** para control de concurrencia.

**Roles permitidos:** Admin, Practitioner, Reception

**Request:**
```json
{
  "row_version": 3,
  "phone": "5559998877",
  "address_line1": "Av. Insurgentes 456",
  "city": "Ciudad de México",
  "notes": "Paciente cambió de domicilio. Teléfono actualizado."
}
```

**Campos actualizables:**
- Datos personales: `first_name`, `last_name`, `date_of_birth`, `gender`
- Contacto: `email`, `phone`, `country_code`
- Dirección: `address_line1`, `address_line2`, `city`, `state_province`, `postal_code`, `country`
- Otros: `referral_source_id`, `notes`

**Campos NO actualizables:**
- `id`, `is_merged`, `merged_into_patient_id`, `merge_reason` (solo via merge endpoint)
- `is_deleted`, `deleted_at`, `deleted_by_user_id` (solo via soft-delete)
- `row_version` (incrementado automáticamente por el servidor)
- `created_at`, `created_by_user_id`

**Response (200 OK):**
```json
{
  "id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
  "first_name": "María",
  "last_name": "González",
  "phone": "5559998877",
  "address_line1": "Av. Insurgentes 456",
  "city": "Ciudad de México",
  "row_version": 4,
  "updated_at": "2025-12-13T17:00:00Z",
  "updated_by_user_id": "def67890-..."
}
```

**Errores:**
- `400 Bad Request`: Validación fallida
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Datos inválidos",
    "details": {
      "row_version": ["Este campo es obligatorio para actualizar"],
      "email": ["Ya existe otro paciente con este email"]
    }
  }
}
```

- `409 Conflict`: row_version no coincide (otro usuario modificó el paciente)
```json
{
  "error": {
    "code": "CONFLICT",
    "message": "El paciente fue modificado por otro usuario. Recarga los datos.",
    "details": {
      "current_row_version": 5,
      "provided_row_version": 3
    }
  }
}
```

- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Accounting/Marketing intentan editar
- `404 Not Found`: Paciente no existe o está soft-deleted

**Notas:**
- Cliente debe incluir `row_version` obtenido del último GET
- Si hay conflicto (409), cliente debe:
  1. Hacer GET para obtener versión actualizada
  2. Mostrar al usuario los cambios conflictivos
  3. Reintentar PATCH con nuevo `row_version`

---

### POST /api/v1/patients/{id}/merge/
Fusiona un paciente duplicado con otro (PAC-04). El paciente origen (`{id}`) queda marcado como `is_merged=true` y apunta al paciente destino.

**Roles permitidos:** Admin, Practitioner

**Request:**
```json
{
  "target_patient_id": "abc12345-def6-7890-abcd-1234567890ab",
  "merge_reason": "Duplicado: mismo email y teléfono. Registro más antiguo tiene historial completo."
}
```

**Campos obligatorios:**
- `target_patient_id` (UUID): Paciente destino (el que se conserva)
- `merge_reason` (string, max 500 chars): Justificación del merge

**Validaciones:**
- Paciente origen (`{id}`) y destino (`target_patient_id`) deben existir y no estar eliminados
- Paciente origen no puede estar ya merged (`is_merged=false`)
- Paciente destino no puede estar merged
- No se puede mergear un paciente consigo mismo

**Response (200 OK):**
```json
{
  "id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
  "first_name": "María",
  "last_name": "González",
  "is_merged": true,
  "merged_into_patient_id": "abc12345-def6-7890-abcd-1234567890ab",
  "merge_reason": "Duplicado: mismo email y teléfono. Registro más antiguo tiene historial completo.",
  "row_version": 4,
  "updated_at": "2025-12-13T17:30:00Z",
  "updated_by_user_id": "admin-uuid-..."
}
```

**Efectos del merge:**
- Paciente origen: `is_merged=true`, `merged_into_patient_id` apunta al destino
- **Todas las relaciones del paciente origen se reasignan al destino:**
  - `PatientGuardian`: `patient_id` actualizado
  - `Appointment`: `patient_id` actualizado
  - `Encounter`: `patient_id` actualizado
  - `Consent`: `patient_id` actualizado
  - `ClinicalPhoto`: `patient_id` actualizado
- Paciente origen **NO** se soft-delete automáticamente (queda visible como merged)
- Admin puede soft-delete manualmente después del merge si es necesario

**Errores:**
- `400 Bad Request`: Validación fallida
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Merge inválido",
    "details": {
      "target_patient_id": ["El paciente destino no existe"],
      "merge_reason": ["Este campo es obligatorio"]
    }
  }
}
```

- `409 Conflict`: Reglas de negocio violadas
```json
{
  "error": {
    "code": "CONFLICT",
    "message": "No se puede realizar el merge",
    "details": {
      "reason": "El paciente origen ya está merged con otro paciente"
    }
  }
}
```

Otros casos de 409:
- Paciente destino está merged
- Paciente origen o destino están soft-deleted
- Intentar mergear un paciente consigo mismo

- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Reception/Accounting/Marketing intentan merge
- `404 Not Found`: Paciente origen no existe

**Notas:**
- Operación **irreversible** (solo Admin puede soft-delete después)
- Frontend debe mostrar confirmación clara antes de ejecutar
- Merge es **explícito** (no automático por coincidencia de campos)

---

### POST /api/v1/patients/{id}/guardians/
Crea un guardian (tutor legal) para un paciente menor o dependiente.

**Roles permitidos:** Admin, Practitioner, Reception

**Request:**
```json
{
  "first_name": "Roberto",
  "last_name": "González",
  "relationship": "parent",
  "phone": "5551112233",
  "email": "roberto.gonzalez@example.com",
  "notes": "Padre de la paciente. Contacto principal."
}
```

**Campos obligatorios:**
- `first_name`, `last_name`, `relationship`

**Valores de relationship (enum):**
- `parent` (padre/madre)
- `legal_guardian` (tutor legal)
- `other` (otro)

**Campos opcionales:**
- `phone`, `email`, `notes`

**Response (201 Created):**
```json
{
  "id": "guardian-uuid-...",
  "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
  "first_name": "Roberto",
  "last_name": "González",
  "relationship": "parent",
  "phone": "5551112233",
  "email": "roberto.gonzalez@example.com",
  "notes": "Padre de la paciente. Contacto principal.",
  "created_at": "2025-12-13T14:35:00Z",
  "updated_at": "2025-12-13T14:35:00Z",
  "created_by_user_id": "user-uuid-...",
  "updated_by_user_id": "user-uuid-..."
}
```

**Errores:**
- `400 Bad Request`: Validación fallida
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Datos inválidos",
    "details": {
      "relationship": ["Valor inválido. Opciones: parent, legal_guardian, other"]
    }
  }
}
```
- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Marketing/Accounting intentan crear
- `404 Not Found`: Paciente no existe

---

### GET /api/v1/patients/{id}/guardians/
Lista guardians de un paciente.

**Roles permitidos:** Admin, Practitioner, Reception

**Response (200 OK):**
```json
[
  {
    "id": "guardian-uuid-1",
    "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
    "first_name": "Roberto",
    "last_name": "González",
    "relationship": "parent",
    "phone": "5551112233",
    "email": "roberto.gonzalez@example.com",
    "notes": "Padre de la paciente. Contacto principal.",
    "created_at": "2025-12-13T14:35:00Z",
    "updated_at": "2025-12-13T14:35:00Z"
  },
  {
    "id": "guardian-uuid-2",
    "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
    "first_name": "Ana",
    "last_name": "López",
    "relationship": "parent",
    "phone": "5554445566",
    "email": "ana.lopez@example.com",
    "notes": "Madre de la paciente.",
    "created_at": "2025-12-13T14:36:00Z",
    "updated_at": "2025-12-13T14:36:00Z"
  }
]
```

**Notas:**
- Retorna array vacío `[]` si paciente no tiene guardians
- No soporta paginación (típicamente pocos guardians por paciente)

**Errores:**
- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Marketing/Accounting intentan acceder
- `404 Not Found`: Paciente no existe

---

### PATCH /api/v1/guardians/{guardian_id}/
Actualiza un guardian existente.

**Roles permitidos:** Admin, Practitioner, Reception

**Request:**
```json
{
  "phone": "5559998888",
  "email": "roberto.gonzalez.nuevo@example.com",
  "notes": "Teléfono actualizado."
}
```

**Campos actualizables:**
- `first_name`, `last_name`, `relationship`, `phone`, `email`, `notes`

**Campos NO actualizables:**
- `id`, `patient_id` (para cambiar paciente, crear nuevo guardian)

**Response (200 OK):**
```json
{
  "id": "guardian-uuid-...",
  "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
  "first_name": "Roberto",
  "last_name": "González",
  "relationship": "parent",
  "phone": "5559998888",
  "email": "roberto.gonzalez.nuevo@example.com",
  "notes": "Teléfono actualizado.",
  "updated_at": "2025-12-13T18:00:00Z",
  "updated_by_user_id": "user-uuid-..."
}
```

**Errores:**
- `400 Bad Request`: Validación fallida
- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Marketing/Accounting intentan editar
- `404 Not Found`: Guardian no existe

---

### DELETE /api/v1/guardians/{guardian_id}/
Elimina un guardian (hard delete, no soft delete).

**Roles permitidos:** Admin, Practitioner, Reception

**Response (204 No Content):**
```
(sin cuerpo de respuesta)
```

**Errores:**
- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Marketing/Accounting intentan eliminar
- `404 Not Found`: Guardian no existe

**Notas:**
- Es **hard delete** (eliminación permanente)
- Modelo `PatientGuardian` **NO** tiene soft delete (según DOMAIN_MODEL.md)
- Usar con precaución: no se puede deshacer

---

## Appointments (AGD)

### POST /api/v1/appointments/
Crea una cita manual en la agenda.

**Roles permitidos:** Admin, Practitioner, Reception

**Request:**
```json
{
  "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
  "practitioner_id": "practitioner-uuid-...",
  "location_id": "location-uuid-...",
  "scheduled_start": "2025-12-20T10:00:00Z",
  "scheduled_end": "2025-12-20T11:00:00Z",
  "appointment_type": "consultation",
  "status": "scheduled",
  "notes": "Primera consulta - evaluación de tratamiento botox"
}
```

**Campos obligatorios:**
- `patient_id` (UUID): Paciente asociado
- `practitioner_id` (UUID): Practitioner que atenderá
- `location_id` (UUID): Ubicación de la clínica
- `scheduled_start` (datetime ISO 8601): Inicio de la cita
- `scheduled_end` (datetime ISO 8601): Fin de la cita
- `appointment_type` (enum): Tipo de cita
- `status` (enum): Estado inicial (típicamente "scheduled")

**Valores de appointment_type (enum):**
- `consultation` (consulta)
- `follow_up` (seguimiento)
- `procedure` (procedimiento)
- `other` (otro)

**Valores de status (enum):**
- `scheduled` (agendada)
- `confirmed` (confirmada)
- `cancelled` (cancelada)
- `completed` (completada)
- `no_show` (no asistió)

**Campos opcionales:**
- `notes` (string): Notas sobre la cita
- `cancellation_reason` (string): Solo si status=cancelled
- `no_show_reason` (string): Solo si status=no_show

**Campos automáticos:**
- `source`: Siempre `"manual"` para este endpoint
- `external_id`: Siempre `null` (solo para Calendly)

**Response (201 Created):**
```json
{
  "id": "appointment-uuid-...",
  "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
  "patient": {
    "id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
    "first_name": "María",
    "last_name": "González"
  },
  "practitioner_id": "practitioner-uuid-...",
  "practitioner": {
    "id": "practitioner-uuid-...",
    "user": {
      "first_name": "Dr. Juan",
      "last_name": "Pérez"
    }
  },
  "location_id": "location-uuid-...",
  "location": {
    "id": "location-uuid-...",
    "name": "Clínica Centro"
  },
  "scheduled_start": "2025-12-20T10:00:00Z",
  "scheduled_end": "2025-12-20T11:00:00Z",
  "appointment_type": "consultation",
  "status": "scheduled",
  "source": "manual",
  "external_id": null,
  "encounter_id": null,
  "notes": "Primera consulta - evaluación de tratamiento botox",
  "cancellation_reason": null,
  "no_show_reason": null,
  "is_deleted": false,
  "created_at": "2025-12-13T15:00:00Z",
  "updated_at": "2025-12-13T15:00:00Z",
  "created_by_user_id": "user-uuid-...",
  "updated_by_user_id": "user-uuid-..."
}
```

**Errores:**
- `400 Bad Request`: Validación fallida
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Datos inválidos",
    "details": {
      "scheduled_start": ["La fecha de inicio debe ser futura"],
      "scheduled_end": ["La fecha de fin debe ser posterior a la fecha de inicio"],
      "patient_id": ["El paciente no existe"]
    }
  }
}
```

- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Marketing/Accounting intentan crear cita
- `404 Not Found`: Patient, Practitioner o Location no existen

**Notas:**
- `scheduled_end` debe ser posterior a `scheduled_start`
- No hay validación automática de conflictos de horario (business logic futura)
- Status inicial recomendado: `scheduled` (puede ser `confirmed` si paciente ya confirmó)

---

### GET /api/v1/appointments/
Lista citas con filtros.

**Roles permitidos:**
- **Admin, Reception**: Ven todas las citas
- **Practitioner**: Solo ve sus propias citas (filtro implícito por `practitioner_id`)

**Query Parameters:**
- `status` (string): Filtrar por estado (scheduled, confirmed, cancelled, completed, no_show)
- `date_from` (date ISO): Citas desde esta fecha (ej: `2025-12-01`)
- `date_to` (date ISO): Citas hasta esta fecha (ej: `2025-12-31`)
- `patient_id` (UUID): Filtrar por paciente
- `practitioner_id` (UUID): Filtrar por practitioner (Admin/Reception pueden especificar cualquiera)
- `location_id` (UUID): Filtrar por ubicación
- `include_deleted` (boolean): Incluir soft-deleted (solo Admin, default: false)
- `page` (int): Número de página (default: 1)
- `page_size` (int): Resultados por página (default: 20, max: 100)
- `ordering` (string): Campo de ordenamiento (default: `scheduled_start`)

**Ejemplos:**
```
GET /api/v1/appointments/?status=scheduled&date_from=2025-12-20
GET /api/v1/appointments/?patient_id=987fcdeb-...&ordering=-scheduled_start
GET /api/v1/appointments/?practitioner_id=prac-uuid...&status=completed
GET /api/v1/appointments/?location_id=loc-uuid...&date_from=2025-12-01&date_to=2025-12-31
```

**Response (200 OK):**
```json
{
  "count": 45,
  "next": "http://api.example.com/api/v1/appointments/?page=2",
  "previous": null,
  "results": [
    {
      "id": "appointment-uuid-1",
      "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
      "patient": {
        "id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
        "first_name": "María",
        "last_name": "González"
      },
      "practitioner_id": "practitioner-uuid-...",
      "practitioner": {
        "id": "practitioner-uuid-...",
        "user": {
          "first_name": "Dr. Juan",
          "last_name": "Pérez"
        }
      },
      "location_id": "location-uuid-...",
      "location": {
        "id": "location-uuid-...",
        "name": "Clínica Centro"
      },
      "scheduled_start": "2025-12-20T10:00:00Z",
      "scheduled_end": "2025-12-20T11:00:00Z",
      "appointment_type": "consultation",
      "status": "scheduled",
      "source": "manual",
      "external_id": null,
      "encounter_id": null,
      "created_at": "2025-12-13T15:00:00Z",
      "updated_at": "2025-12-13T15:00:00Z"
    },
    {
      "id": "appointment-uuid-2",
      "patient_id": "abc12345-...",
      "patient": {
        "id": "abc12345-...",
        "first_name": "Juan",
        "last_name": "Martínez"
      },
      "practitioner_id": "practitioner-uuid-...",
      "practitioner": {
        "id": "practitioner-uuid-...",
        "user": {
          "first_name": "Dr. Juan",
          "last_name": "Pérez"
        }
      },
      "location_id": "location-uuid-...",
      "location": {
        "id": "location-uuid-...",
        "name": "Clínica Norte"
      },
      "scheduled_start": "2025-12-21T14:00:00Z",
      "scheduled_end": "2025-12-21T15:00:00Z",
      "appointment_type": "follow_up",
      "status": "confirmed",
      "source": "calendly",
      "external_id": "calendly_evt_abc123",
      "encounter_id": null,
      "created_at": "2025-12-10T12:00:00Z",
      "updated_at": "2025-12-12T09:30:00Z"
    }
  ]
}
```

**Notas:**
- Por defecto, **excluye** citas con `is_deleted=true`
- Solo Admin puede usar `?include_deleted=true`
- **Filtro implícito para Practitioners**: Solo ven citas donde `practitioner_id = user.practitioner.id`
- Incluye objetos anidados: `patient`, `practitioner`, `location` (solo campos básicos)
- Ordenamiento default: `scheduled_start` (ascendente, próximas primero)

**Errores:**
- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Marketing/Accounting intentan acceder

---

### PATCH /api/v1/appointments/{id}/
Actualiza una cita existente. Permite cambios de estado y edición de datos.

**Roles permitidos:** Admin, Practitioner (solo sus citas), Reception

**Request (cambio de estado a cancelled):**
```json
{
  "status": "cancelled",
  "cancellation_reason": "Paciente solicitó reprogramar por motivos personales"
}
```

**Request (cambio de estado a no_show):**
```json
{
  "status": "no_show",
  "no_show_reason": "No asistió y no avisó"
}
```

**Request (cambio de estado a completed):**
```json
{
  "status": "completed"
}
```

**Request (edición de horario y tipo):**
```json
{
  "scheduled_start": "2025-12-20T11:00:00Z",
  "scheduled_end": "2025-12-20T12:00:00Z",
  "appointment_type": "procedure",
  "notes": "Cita reprogramada. Cambiado a procedimiento."
}
```

**Campos actualizables:**
- `scheduled_start`, `scheduled_end`: Fechas de la cita
- `appointment_type`: Tipo de cita
- `status`: Estado (con transiciones válidas)
- `location_id`: Cambio de ubicación
- `notes`: Notas adicionales
- `cancellation_reason`: Requerido si `status=cancelled`
- `no_show_reason`: Requerido si `status=no_show`

**Campos NO actualizables:**
- `patient_id`, `practitioner_id` (para cambiar, crear nueva cita)
- `source`, `external_id` (solo para Calendly sync)
- `encounter_id` (usar endpoint `/link-encounter`)

**Transiciones de estado válidas:**
```
scheduled -> confirmed
scheduled -> cancelled
scheduled -> no_show
confirmed -> completed
confirmed -> cancelled
confirmed -> no_show
cancelled -> scheduled (reprogramar)
```

**Response (200 OK):**
```json
{
  "id": "appointment-uuid-...",
  "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
  "practitioner_id": "practitioner-uuid-...",
  "location_id": "location-uuid-...",
  "scheduled_start": "2025-12-20T10:00:00Z",
  "scheduled_end": "2025-12-20T11:00:00Z",
  "appointment_type": "consultation",
  "status": "cancelled",
  "source": "manual",
  "external_id": null,
  "encounter_id": null,
  "notes": "Primera consulta - evaluación de tratamiento botox",
  "cancellation_reason": "Paciente solicitó reprogramar por motivos personales",
  "no_show_reason": null,
  "updated_at": "2025-12-13T16:00:00Z",
  "updated_by_user_id": "user-uuid-..."
}
```

**Errores:**
- `400 Bad Request`: Validación fallida
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Datos inválidos",
    "details": {
      "cancellation_reason": ["Este campo es requerido cuando status=cancelled"],
      "status": ["Transición inválida: no se puede cambiar de completed a scheduled"]
    }
  }
}
```

- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`:
  - Practitioner intenta editar cita de otro practitioner
  - Marketing/Accounting intentan editar
- `404 Not Found`: Cita no existe o está soft-deleted

**Notas:**
- `cancellation_reason` es **obligatorio** si `status=cancelled`
- `no_show_reason` es **obligatorio** si `status=no_show`
- Cambiar status a `completed` típicamente se hace cuando se vincula un encounter
- Practitioners solo pueden editar sus propias citas (Admin/Reception pueden editar cualquiera)

---

### POST /api/v1/appointments/calendly/sync/
Sincroniza citas desde Calendly. **Operación idempotente** basada en `external_id`.

**Roles permitidos:** Admin, Reception

**Request:**
```json
{
  "appointments": [
    {
      "external_id": "calendly_evt_abc123",
      "patient_email": "maria.gonzalez@example.com",
      "patient_phone": "5551234567",
      "patient_first_name": "María",
      "patient_last_name": "González",
      "practitioner_id": "practitioner-uuid-...",
      "location_id": "location-uuid-...",
      "scheduled_start": "2025-12-21T14:00:00Z",
      "scheduled_end": "2025-12-21T15:00:00Z",
      "appointment_type": "consultation",
      "status": "confirmed"
    },
    {
      "external_id": "calendly_evt_def456",
      "patient_email": "juan.martinez@example.com",
      "patient_phone": "5559876543",
      "patient_first_name": "Juan",
      "patient_last_name": "Martínez",
      "practitioner_id": "practitioner-uuid-...",
      "location_id": "location-uuid-...",
      "scheduled_start": "2025-12-22T10:00:00Z",
      "scheduled_end": "2025-12-22T11:00:00Z",
      "appointment_type": "follow_up",
      "status": "scheduled"
    }
  ]
}
```

**Campos obligatorios por cita:**
- `external_id` (string unique): ID de Calendly (ej: `calendly_evt_...`)
- `patient_email` (string): Email del paciente (para match)
- `practitioner_id` (UUID): Practitioner asignado
- `location_id` (UUID): Ubicación
- `scheduled_start`, `scheduled_end` (datetime ISO 8601)
- `appointment_type` (enum)
- `status` (enum)

**Campos opcionales:**
- `patient_phone`, `patient_first_name`, `patient_last_name`: Usados si no se encuentra paciente por email

**Lógica de sincronización:**
1. **Buscar paciente** por `patient_email`:
   - Si existe: usar ese `patient_id`
   - Si no existe: crear nuevo paciente con datos provistos (first_name, last_name, email, phone)

2. **Buscar cita** por `external_id`:
   - Si existe: **actualizar** campos (scheduled_start, scheduled_end, status, appointment_type)
   - Si no existe: **crear** nueva cita con `source=calendly`

3. **Idempotencia**: Ejecutar el mismo payload múltiples veces no crea duplicados (basado en `external_id` unique)

**Response (200 OK):**
```json
{
  "synced": 2,
  "created": 1,
  "updated": 1,
  "errors": [],
  "details": [
    {
      "external_id": "calendly_evt_abc123",
      "action": "updated",
      "appointment_id": "appointment-uuid-1",
      "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
      "patient_action": "matched"
    },
    {
      "external_id": "calendly_evt_def456",
      "action": "created",
      "appointment_id": "appointment-uuid-2",
      "patient_id": "abc12345-...",
      "patient_action": "created"
    }
  ]
}
```

**Campos de response:**
- `synced` (int): Total de citas procesadas exitosamente
- `created` (int): Citas nuevas creadas
- `updated` (int): Citas existentes actualizadas
- `errors` (array): Errores parciales (citas no sincronizadas)
- `details` (array): Detalle por cita procesada
  - `action`: `"created"` | `"updated"`
  - `patient_action`: `"matched"` | `"created"`

**Errores parciales:**
Si algunas citas fallan pero otras se procesan correctamente:
```json
{
  "synced": 1,
  "created": 1,
  "updated": 0,
  "errors": [
    {
      "external_id": "calendly_evt_xyz999",
      "error": "Practitioner no existe",
      "details": {
        "practitioner_id": "invalid-uuid"
      }
    }
  ],
  "details": [
    {
      "external_id": "calendly_evt_abc123",
      "action": "created",
      "appointment_id": "appointment-uuid-...",
      "patient_id": "987fcdeb-...",
      "patient_action": "matched"
    }
  ]
}
```

**Errores globales:**
- `400 Bad Request`: Payload inválido (formato JSON incorrecto)
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Formato de request inválido",
    "details": {
      "appointments": ["Este campo es requerido"]
    }
  }
}
```

- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Practitioner/Marketing/Accounting intentan sincronizar

**Notas:**
- Endpoint diseñado para **webhooks de Calendly** o sincronización batch
- **Idempotente**: ejecutar múltiples veces con mismos `external_id` no crea duplicados
- Si paciente no existe, se crea automáticamente con datos mínimos (first_name, last_name, email, phone)
- Citas sincronizadas tienen `source=calendly` y `external_id` poblado
- No se eliminan citas ausentes en el payload (solo create/update)

---

### POST /api/v1/appointments/{id}/link-encounter/
Vincula una cita con un encounter (visita clínica). **Opcional y reversible**.

**Roles permitidos:** Admin, Practitioner

**Request:**
```json
{
  "encounter_id": "encounter-uuid-..."
}
```

**Campos obligatorios:**
- `encounter_id` (UUID): ID del encounter a vincular

**Validaciones:**
- Cita y encounter deben existir y no estar soft-deleted
- Encounter debe pertenecer al mismo `patient_id` que la cita
- Un encounter puede estar vinculado a **una sola cita** (relación 1:1)
- Una cita puede estar vinculada a **un solo encounter**

**Response (200 OK):**
```json
{
  "id": "appointment-uuid-...",
  "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
  "practitioner_id": "practitioner-uuid-...",
  "location_id": "location-uuid-...",
  "scheduled_start": "2025-12-20T10:00:00Z",
  "scheduled_end": "2025-12-20T11:00:00Z",
  "appointment_type": "consultation",
  "status": "completed",
  "encounter_id": "encounter-uuid-...",
  "encounter": {
    "id": "encounter-uuid-...",
    "encounter_date": "2025-12-20T10:15:00Z",
    "status": "finalized"
  },
  "updated_at": "2025-12-20T11:30:00Z",
  "updated_by_user_id": "practitioner-user-uuid-..."
}
```

**Efectos del link:**
- `appointment.encounter_id` apunta al encounter
- Típicamente, `appointment.status` cambia a `completed` (no automático, usar PATCH si se desea)

**Desvincular (opcional):**
Enviar `encounter_id: null` para quitar el vínculo:
```json
{
  "encounter_id": null
}
```

Response:
```json
{
  "id": "appointment-uuid-...",
  "encounter_id": null,
  "updated_at": "2025-12-20T12:00:00Z"
}
```

**Errores:**
- `400 Bad Request`: Validación fallida
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "No se puede vincular encounter",
    "details": {
      "encounter_id": ["El encounter no pertenece al mismo paciente que la cita"]
    }
  }
}
```

- `409 Conflict`: Encounter ya vinculado a otra cita
```json
{
  "error": {
    "code": "CONFLICT",
    "message": "El encounter ya está vinculado a otra cita",
    "details": {
      "existing_appointment_id": "other-appointment-uuid-..."
    }
  }
}
```

- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Reception/Marketing/Accounting intentan vincular
- `404 Not Found`: Cita o encounter no existen

**Notas:**
- Vincular cita con encounter es **opcional** (no obligatorio para encounters)
- Útil para rastrear qué cita generó qué visita clínica
- Relación **reversible**: se puede desvincular enviando `encounter_id: null`
- Un encounter puede existir sin cita (walk-in patient)
- Recomendado cambiar `appointment.status` a `completed` después de vincular (usar PATCH)

---

## Encounters (ENC)

### POST /api/v1/encounters/
Crea un nuevo encounter (visita clínica) en estado **draft**.

**Roles permitidos:** Admin, Practitioner

**Request:**
```json
{
  "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
  "practitioner_id": "practitioner-uuid-...",
  "location_id": "location-uuid-...",
  "encounter_date": "2025-12-20T10:15:00Z",
  "encounter_type": "consultation",
  "chief_complaint": "Evaluación para tratamiento de arrugas faciales",
  "clinical_notes": "Paciente refiere líneas de expresión en frente y entrecejo. Sin antecedentes de botox.",
  "diagnosis": "",
  "treatment_plan": "",
  "status": "draft"
}
```

**Campos obligatorios:**
- `patient_id` (UUID): Paciente asociado
- `practitioner_id` (UUID): Practitioner que atendió
- `location_id` (UUID): Ubicación de la clínica
- `encounter_date` (datetime ISO 8601): Fecha/hora de la visita
- `encounter_type` (enum): Tipo de encounter
- `status` (enum): Estado inicial (típicamente "draft")

**Valores de encounter_type (enum):**
- `consultation` (consulta)
- `follow_up` (seguimiento)
- `procedure` (procedimiento)
- `emergency` (emergencia)

**Valores de status (enum):**
- `draft` (borrador, editable)
- `finalized` (finalizado, inmutable)
- `cancelled` (cancelado)

**Campos opcionales:**
- `chief_complaint` (string): Motivo de consulta
- `clinical_notes` (text): Notas clínicas detalladas
- `diagnosis` (text): Diagnóstico
- `treatment_plan` (text): Plan de tratamiento
- `follow_up_date` (date): Fecha sugerida para seguimiento

**Response (201 Created):**
```json
{
  "id": "encounter-uuid-...",
  "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
  "patient": {
    "id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
    "first_name": "María",
    "last_name": "González"
  },
  "practitioner_id": "practitioner-uuid-...",
  "practitioner": {
    "id": "practitioner-uuid-...",
    "user": {
      "first_name": "Dr. Juan",
      "last_name": "Pérez"
    }
  },
  "location_id": "location-uuid-...",
  "location": {
    "id": "location-uuid-...",
    "name": "Clínica Centro"
  },
  "encounter_date": "2025-12-20T10:15:00Z",
  "encounter_type": "consultation",
  "chief_complaint": "Evaluación para tratamiento de arrugas faciales",
  "clinical_notes": "Paciente refiere líneas de expresión en frente y entrecejo. Sin antecedentes de botox.",
  "diagnosis": "",
  "treatment_plan": "",
  "follow_up_date": null,
  "status": "draft",
  "row_version": 1,
  "is_deleted": false,
  "created_at": "2025-12-20T10:20:00Z",
  "updated_at": "2025-12-20T10:20:00Z",
  "created_by_user_id": "practitioner-user-uuid-...",
  "updated_by_user_id": "practitioner-user-uuid-..."
}
```

**Errores:**
- `400 Bad Request`: Validación fallida
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Datos inválidos",
    "details": {
      "patient_id": ["El paciente no existe"],
      "encounter_date": ["La fecha del encounter no puede ser futura"]
    }
  }
}
```

- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Reception/Marketing/Accounting intentan crear encounter
- `404 Not Found`: Patient, Practitioner o Location no existen

**Notas:**
- Encounters se crean en estado `draft` por defecto (editable)
- Solo Practitioners y Admin pueden crear encounters
- `encounter_date` típicamente es la fecha/hora actual o pasada (no futura)
- Encounter puede existir sin cita vinculada (walk-in patient)

---

### GET /api/v1/encounters/
Lista encounters con filtros.

**Roles permitidos:**
- **Admin**: Ve todos los encounters
- **Practitioner**: Solo ve encounters que creó (filtro implícito por `practitioner_id`)
- **Accounting**: Ve todos los encounters (solo lectura)

**Query Parameters:**
- `patient_id` (UUID): Filtrar por paciente
- `practitioner_id` (UUID): Filtrar por practitioner (Admin/Accounting pueden especificar cualquiera)
- `encounter_type` (string): Filtrar por tipo (consultation, follow_up, procedure, emergency)
- `status` (string): Filtrar por estado (draft, finalized, cancelled)
- `date_from` (date ISO): Encounters desde esta fecha (ej: `2025-12-01`)
- `date_to` (date ISO): Encounters hasta esta fecha (ej: `2025-12-31`)
- `include_deleted` (boolean): Incluir soft-deleted (solo Admin, default: false)
- `page` (int): Número de página (default: 1)
- `page_size` (int): Resultados por página (default: 20, max: 100)
- `ordering` (string): Campo de ordenamiento (default: `-encounter_date`)

**Ejemplos:**
```
GET /api/v1/encounters/?patient_id=987fcdeb-...
GET /api/v1/encounters/?status=draft&practitioner_id=prac-uuid...
GET /api/v1/encounters/?date_from=2025-12-01&date_to=2025-12-31&ordering=-encounter_date
GET /api/v1/encounters/?encounter_type=procedure&status=finalized
```

**Response (200 OK):**
```json
{
  "count": 32,
  "next": "http://api.example.com/api/v1/encounters/?page=2",
  "previous": null,
  "results": [
    {
      "id": "encounter-uuid-1",
      "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
      "patient": {
        "id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
        "first_name": "María",
        "last_name": "González"
      },
      "practitioner_id": "practitioner-uuid-...",
      "practitioner": {
        "id": "practitioner-uuid-...",
        "user": {
          "first_name": "Dr. Juan",
          "last_name": "Pérez"
        }
      },
      "location_id": "location-uuid-...",
      "encounter_date": "2025-12-20T10:15:00Z",
      "encounter_type": "consultation",
      "status": "finalized",
      "row_version": 3,
      "created_at": "2025-12-20T10:20:00Z",
      "updated_at": "2025-12-20T11:00:00Z"
    },
    {
      "id": "encounter-uuid-2",
      "patient_id": "abc12345-...",
      "patient": {
        "id": "abc12345-...",
        "first_name": "Juan",
        "last_name": "Martínez"
      },
      "practitioner_id": "practitioner-uuid-...",
      "practitioner": {
        "id": "practitioner-uuid-...",
        "user": {
          "first_name": "Dr. Juan",
          "last_name": "Pérez"
        }
      },
      "location_id": "location-uuid-...",
      "encounter_date": "2025-12-19T14:30:00Z",
      "encounter_type": "procedure",
      "status": "draft",
      "row_version": 1,
      "created_at": "2025-12-19T14:35:00Z",
      "updated_at": "2025-12-19T14:35:00Z"
    }
  ]
}
```

**Notas:**
- Por defecto, **excluye** encounters con `is_deleted=true`
- Solo Admin puede usar `?include_deleted=true`
- **Filtro implícito para Practitioners**: Solo ven encounters donde `practitioner_id = user.practitioner.id`
- Accounting puede ver todos los encounters (para facturación)
- Ordenamiento default: `-encounter_date` (más recientes primero)

**Errores:**
- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Reception/Marketing intentan acceder

---

### GET /api/v1/encounters/{id}/
Obtiene detalle completo de un encounter.

**Roles permitidos:** Admin, Practitioner (solo sus encounters), Accounting (lectura)

**Response (200 OK):**
```json
{
  "id": "encounter-uuid-...",
  "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
  "patient": {
    "id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
    "first_name": "María",
    "last_name": "González",
    "date_of_birth": "1992-05-15"
  },
  "practitioner_id": "practitioner-uuid-...",
  "practitioner": {
    "id": "practitioner-uuid-...",
    "user": {
      "id": "user-uuid-...",
      "first_name": "Dr. Juan",
      "last_name": "Pérez",
      "email": "dr.perez@clinica.com"
    },
    "license_number": "MED-12345"
  },
  "location_id": "location-uuid-...",
  "location": {
    "id": "location-uuid-...",
    "name": "Clínica Centro",
    "address": "Av. Reforma 123"
  },
  "encounter_date": "2025-12-20T10:15:00Z",
  "encounter_type": "consultation",
  "chief_complaint": "Evaluación para tratamiento de arrugas faciales",
  "clinical_notes": "Paciente refiere líneas de expresión en frente y entrecejo. Sin antecedentes de botox. Se explica procedimiento y riesgos.",
  "diagnosis": "Arrugas dinámicas frontales y glabelares. Grado II.",
  "treatment_plan": "Aplicación de toxina botulínica tipo A, 20 unidades zona frontal, 20 unidades entrecejo. Seguimiento en 2 semanas.",
  "follow_up_date": "2026-01-03",
  "status": "finalized",
  "row_version": 3,
  "is_deleted": false,
  "deleted_at": null,
  "deleted_by_user_id": null,
  "created_at": "2025-12-20T10:20:00Z",
  "updated_at": "2025-12-20T11:00:00Z",
  "created_by_user_id": "practitioner-user-uuid-...",
  "updated_by_user_id": "practitioner-user-uuid-..."
}
```

**Errores:**
- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`:
  - Practitioner intenta ver encounter de otro practitioner
  - Reception/Marketing intentan acceder
- `404 Not Found`: Encounter no existe o está soft-deleted (para no-Admin)

**Notas:**
- Incluye objetos anidados expandidos: `patient`, `practitioner`, `location`
- Admin puede ver encounters soft-deleted (incluye `deleted_at`, `deleted_by_user_id`)
- Practitioners solo ven sus propios encounters
- Accounting puede ver cualquier encounter (para facturación)

---

### PATCH /api/v1/encounters/{id}/
Actualiza un encounter existente. **Requiere row_version** para control de concurrencia.

**Roles permitidos:** Admin, Practitioner (solo encounters propios en estado `draft`)

**Request:**
```json
{
  "row_version": 1,
  "clinical_notes": "Paciente refiere líneas de expresión en frente y entrecejo. Sin antecedentes de botox. Se explica procedimiento y riesgos. Paciente firma consentimiento informado.",
  "diagnosis": "Arrugas dinámicas frontales y glabelares. Grado II.",
  "treatment_plan": "Aplicación de toxina botulínica tipo A, 20 unidades zona frontal, 20 unidades entrecejo. Seguimiento en 2 semanas.",
  "follow_up_date": "2026-01-03"
}
```

**Campos actualizables (solo si status=draft):**
- `encounter_date`
- `encounter_type`
- `chief_complaint`
- `clinical_notes`
- `diagnosis`
- `treatment_plan`
- `follow_up_date`
- `status` (solo transiciones válidas: draft -> cancelled)

**Campos NO actualizables:**
- `patient_id`, `practitioner_id`, `location_id` (fijos al crear)
- `row_version` (incrementado automáticamente por el servidor)
- `is_deleted`, `deleted_at`, `deleted_by_user_id` (solo via soft-delete)
- `created_at`, `created_by_user_id`

**Restricción crítica:**
Si `status=finalized`, **NO** se pueden editar campos clínicos:
- `chief_complaint`, `clinical_notes`, `diagnosis`, `treatment_plan`, `follow_up_date`
- Solo Admin puede editar encounter finalizado (casos excepcionales)

**Response (200 OK):**
```json
{
  "id": "encounter-uuid-...",
  "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
  "practitioner_id": "practitioner-uuid-...",
  "encounter_date": "2025-12-20T10:15:00Z",
  "encounter_type": "consultation",
  "clinical_notes": "Paciente refiere líneas de expresión en frente y entrecejo. Sin antecedentes de botox. Se explica procedimiento y riesgos. Paciente firma consentimiento informado.",
  "diagnosis": "Arrugas dinámicas frontales y glabelares. Grado II.",
  "treatment_plan": "Aplicación de toxina botulínica tipo A, 20 unidades zona frontal, 20 unidades entrecejo. Seguimiento en 2 semanas.",
  "follow_up_date": "2026-01-03",
  "status": "draft",
  "row_version": 2,
  "updated_at": "2025-12-20T10:45:00Z",
  "updated_by_user_id": "practitioner-user-uuid-..."
}
```

**Errores:**
- `400 Bad Request`: Validación fallida
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Datos inválidos",
    "details": {
      "row_version": ["Este campo es obligatorio para actualizar"]
    }
  }
}
```

- `403 Forbidden`: Intento de editar encounter finalizado (no-Admin)
```json
{
  "error": {
    "code": "PERMISSION_DENIED",
    "message": "No se puede editar un encounter finalizado",
    "details": {
      "status": "finalized",
      "reason": "Los encounters finalizados son inmutables. Contacte al administrador si necesita corregir datos."
    }
  }
}
```

- `409 Conflict`: row_version no coincide
```json
{
  "error": {
    "code": "CONFLICT",
    "message": "El encounter fue modificado por otro usuario. Recarga los datos.",
    "details": {
      "current_row_version": 3,
      "provided_row_version": 1
    }
  }
}
```

- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Practitioner intenta editar encounter de otro practitioner
- `404 Not Found`: Encounter no existe o está soft-deleted

**Notas:**
- Cliente debe incluir `row_version` del último GET
- Encounters en estado `finalized` son **inmutables** (excepto Admin en casos excepcionales)
- Para finalizar un encounter, usar endpoint `/finalize` (no PATCH status directamente)
- Practitioners solo pueden editar sus propios encounters en estado `draft`

---

### POST /api/v1/encounters/{id}/finalize/
Finaliza un encounter, cambiando su estado a `finalized` y bloqueando ediciones futuras.

**Roles permitidos:** Admin, Practitioner (solo encounters propios)

**Request:**
```json
{
  "row_version": 2
}
```

**Campos obligatorios:**
- `row_version` (int): Versión actual del encounter (control de concurrencia)

**Validaciones:**
- Encounter debe estar en estado `draft`
- Encounter debe tener campos clínicos completos (chief_complaint, clinical_notes, diagnosis, treatment_plan no vacíos)
- `row_version` debe coincidir con versión actual

**Response (200 OK):**
```json
{
  "id": "encounter-uuid-...",
  "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
  "practitioner_id": "practitioner-uuid-...",
  "encounter_date": "2025-12-20T10:15:00Z",
  "encounter_type": "consultation",
  "chief_complaint": "Evaluación para tratamiento de arrugas faciales",
  "clinical_notes": "Paciente refiere líneas de expresión en frente y entrecejo. Sin antecedentes de botox. Se explica procedimiento y riesgos. Paciente firma consentimiento informado.",
  "diagnosis": "Arrugas dinámicas frontales y glabelares. Grado II.",
  "treatment_plan": "Aplicación de toxina botulínica tipo A, 20 unidades zona frontal, 20 unidades entrecejo. Seguimiento en 2 semanas.",
  "follow_up_date": "2026-01-03",
  "status": "finalized",
  "row_version": 3,
  "updated_at": "2025-12-20T11:00:00Z",
  "updated_by_user_id": "practitioner-user-uuid-..."
}
```

**Efectos de finalize:**
- `status` cambia de `draft` a `finalized`
- `row_version` se incrementa
- Campos clínicos se vuelven **inmutables** (no editables, excepto Admin)
- Encounter queda listo para facturación y reportes

**Errores:**
- `400 Bad Request`: Validación fallida
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "No se puede finalizar el encounter",
    "details": {
      "diagnosis": ["Este campo es requerido para finalizar el encounter"],
      "treatment_plan": ["Este campo es requerido para finalizar el encounter"]
    }
  }
}
```

- `409 Conflict`: row_version no coincide
```json
{
  "error": {
    "code": "CONFLICT",
    "message": "El encounter fue modificado por otro usuario. Recarga los datos.",
    "details": {
      "current_row_version": 3,
      "provided_row_version": 2
    }
  }
}
```

- `409 Conflict`: Encounter no está en draft
```json
{
  "error": {
    "code": "CONFLICT",
    "message": "Solo se pueden finalizar encounters en estado draft",
    "details": {
      "current_status": "finalized"
    }
  }
}
```

- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Practitioner intenta finalizar encounter de otro practitioner
- `404 Not Found`: Encounter no existe

**Notas:**
- **Operación irreversible**: Una vez finalizado, el encounter no puede volver a `draft`
- Admin puede editar encounters finalizados (casos excepcionales de corrección)
- Recomendado validar campos obligatorios antes de finalizar desde el frontend
- Finalizar encounter es requisito para auditoría y facturación

---

## Consents (CON)

### POST /api/v1/patients/{id}/consents/grant/
Otorga un consentimiento (GDPR/HIPAA) para un paciente.

**Roles permitidos:** Admin, Practitioner, Reception

**Request:**
```json
{
  "consent_type": "clinical_photos",
  "document_id": "document-uuid-...",
  "notes": "Consentimiento firmado presencialmente. Paciente autoriza uso de fotos clínicas para historial médico."
}
```

**Campos obligatorios:**
- `consent_type` (enum): Tipo de consentimiento

**Valores de consent_type (enum):**
- `clinical_photos`: Uso de fotos clínicas (historial médico)
- `marketing_photos`: Uso de fotos para marketing (antes/después en redes sociales)
- `newsletter`: Suscripción a newsletter por email
- `marketing_messages`: Mensajes promocionales (SMS/WhatsApp)

**Campos opcionales:**
- `document_id` (UUID): Documento escaneado del consentimiento firmado (FK a `Document`)
- `notes` (string): Notas adicionales sobre el consentimiento

**Response (201 Created):**
```json
{
  "id": "consent-uuid-...",
  "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
  "consent_type": "clinical_photos",
  "is_granted": true,
  "granted_at": "2025-12-20T10:00:00Z",
  "granted_by_user_id": "reception-user-uuid-...",
  "revoked_at": null,
  "revoked_by_user_id": null,
  "document_id": "document-uuid-...",
  "document": {
    "id": "document-uuid-...",
    "file_name": "consentimiento_fotos_clinicas.pdf",
    "mime_type": "application/pdf"
  },
  "notes": "Consentimiento firmado presencialmente. Paciente autoriza uso de fotos clínicas para historial médico.",
  "created_at": "2025-12-20T10:00:00Z",
  "updated_at": "2025-12-20T10:00:00Z"
}
```

**Errores:**
- `400 Bad Request`: Validación fallida
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Datos inválidos",
    "details": {
      "consent_type": ["Valor inválido. Opciones: clinical_photos, marketing_photos, newsletter, marketing_messages"],
      "document_id": ["El documento no existe"]
    }
  }
}
```

- `409 Conflict`: Ya existe un consentimiento activo del mismo tipo
```json
{
  "error": {
    "code": "CONFLICT",
    "message": "Ya existe un consentimiento activo de este tipo",
    "details": {
      "existing_consent_id": "consent-uuid-...",
      "consent_type": "clinical_photos",
      "granted_at": "2025-11-15T14:00:00Z"
    }
  }
}
```

- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Marketing/Accounting intentan otorgar consent
- `404 Not Found`: Paciente no existe

**Notas:**
- Consent es **inmutable**: otorgar crea nuevo registro con `is_granted=true`
- Si ya existe consent activo del mismo tipo, retorna `409 Conflict`
- Para revocar, usar endpoint `/revoke` (crea nuevo registro con `is_granted=false`)
- `document_id` es opcional pero recomendado (respaldo legal del consentimiento firmado)

---

### POST /api/v1/patients/{id}/consents/revoke/
Revoca un consentimiento previamente otorgado.

**Roles permitidos:** Admin, Practitioner, Reception

**Request:**
```json
{
  "consent_type": "marketing_photos",
  "notes": "Paciente solicitó revocar autorización para uso de fotos en redes sociales."
}
```

**Campos obligatorios:**
- `consent_type` (enum): Tipo de consentimiento a revocar

**Campos opcionales:**
- `notes` (string): Razón de la revocación

**Response (201 Created):**
```json
{
  "id": "consent-uuid-new-...",
  "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
  "consent_type": "marketing_photos",
  "is_granted": false,
  "granted_at": null,
  "granted_by_user_id": null,
  "revoked_at": "2025-12-20T15:00:00Z",
  "revoked_by_user_id": "reception-user-uuid-...",
  "document_id": null,
  "notes": "Paciente solicitó revocar autorización para uso de fotos en redes sociales.",
  "created_at": "2025-12-20T15:00:00Z",
  "updated_at": "2025-12-20T15:00:00Z"
}
```

**Errores:**
- `400 Bad Request`: Validación fallida
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Datos inválidos",
    "details": {
      "consent_type": ["Este campo es obligatorio"]
    }
  }
}
```

- `409 Conflict`: No existe consentimiento activo para revocar
```json
{
  "error": {
    "code": "CONFLICT",
    "message": "No existe un consentimiento activo de este tipo para revocar",
    "details": {
      "consent_type": "marketing_photos"
    }
  }
}
```

- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Marketing/Accounting intentan revocar consent
- `404 Not Found`: Paciente no existe

**Notas:**
- Revocación es **inmutable**: crea nuevo registro con `is_granted=false`
- No elimina el registro de consentimiento anterior (historial completo)
- Después de revocar, ya no existe consent activo de ese tipo
- Paciente puede volver a otorgar el mismo consent posteriormente (nuevo registro)

---

### GET /api/v1/patients/{id}/consents/status/
Obtiene el estado actual de todos los consentimientos de un paciente.

**Roles permitidos:** Admin, Practitioner, Reception

**Response (200 OK):**
```json
{
  "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
  "consents": {
    "clinical_photos": {
      "status": "granted",
      "granted_at": "2025-12-20T10:00:00Z",
      "granted_by_user_id": "reception-user-uuid-...",
      "consent_id": "consent-uuid-...",
      "document_id": "document-uuid-...",
      "notes": "Consentimiento firmado presencialmente."
    },
    "marketing_photos": {
      "status": "revoked",
      "revoked_at": "2025-12-20T15:00:00Z",
      "revoked_by_user_id": "reception-user-uuid-...",
      "consent_id": "consent-uuid-revoked-...",
      "notes": "Paciente solicitó revocar autorización."
    },
    "newsletter": {
      "status": "not_granted"
    },
    "marketing_messages": {
      "status": "granted",
      "granted_at": "2025-11-10T12:00:00Z",
      "granted_by_user_id": "marketing-user-uuid-...",
      "consent_id": "consent-uuid-marketing-...",
      "notes": "Paciente aceptó recibir promociones por WhatsApp."
    }
  }
}
```

**Estructura de response:**
- `consents`: Objeto con 4 claves (una por `consent_type`)
- Cada tipo tiene `status`:
  - `"granted"`: Consentimiento activo (incluye `granted_at`, `granted_by_user_id`, `consent_id`, `document_id`, `notes`)
  - `"revoked"`: Consentimiento revocado (incluye `revoked_at`, `revoked_by_user_id`, `consent_id`, `notes`)
  - `"not_granted"`: Nunca otorgado (solo `status`)

**Errores:**
- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Marketing/Accounting intentan acceder
- `404 Not Found`: Paciente no existe

**Notas:**
- Retorna estado **actual** de los 4 tipos de consent (no historial completo)
- Para ver historial completo de consents (todos los registros), usar endpoint futuro `/consents/history`
- `status="not_granted"` significa que nunca se ha otorgado ese consent
- `status="revoked"` significa que se otorgó y luego se revocó
- Útil para validar permisos antes de tomar fotos clínicas o enviar marketing

---

## Photos (PHO)

### POST /api/v1/patients/{id}/photos/
Crea una foto clínica asociada a un paciente. La foto se almacena en bucket **clinical** (MinIO).

**Roles permitidos:** Admin, Practitioner

**Request:**
```json
{
  "object_key": "clinical/2025/12/20/987fcdeb-51a2-43f7-8d9e-1234567890ab/face_frontal_before.jpg",
  "original_filename": "face_frontal_before.jpg",
  "mime_type": "image/jpeg",
  "file_size_bytes": 2458624,
  "photo_kind": "before",
  "photo_context": "face_frontal",
  "taken_at": "2025-12-20T10:30:00Z",
  "notes": "Foto frontal antes de tratamiento botox"
}
```

**Campos obligatorios:**
- `object_key` (string): Clave del objeto en MinIO bucket `clinical` (obtenida de `/uploads/presign`)
- `original_filename` (string): Nombre original del archivo
- `mime_type` (string): Tipo MIME (ej: `image/jpeg`, `image/png`)
- `file_size_bytes` (int): Tamaño del archivo en bytes

**Valores de photo_kind (enum):**
- `before` (antes de tratamiento)
- `after` (después de tratamiento)
- `during` (durante procedimiento)
- `other` (otro)

**Valores de photo_context (enum):**
- `face_frontal` (rostro frontal)
- `face_left_profile` (perfil izquierdo)
- `face_right_profile` (perfil derecho)
- `body_frontal` (cuerpo frontal)
- `body_back` (cuerpo espalda)
- `detail` (detalle específico)
- `other` (otro)

**Campos opcionales:**
- `photo_kind` (enum): Clasificación temporal de la foto
- `photo_context` (enum): Área anatómica capturada
- `taken_at` (datetime ISO 8601): Fecha/hora en que se tomó la foto (default: now)
- `notes` (string): Notas sobre la foto

**Response (201 Created):**
```json
{
  "id": "photo-uuid-...",
  "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
  "patient": {
    "id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
    "first_name": "María",
    "last_name": "González"
  },
  "object_key": "clinical/2025/12/20/987fcdeb-51a2-43f7-8d9e-1234567890ab/face_frontal_before.jpg",
  "storage_bucket": "clinical",
  "original_filename": "face_frontal_before.jpg",
  "mime_type": "image/jpeg",
  "file_size_bytes": 2458624,
  "photo_kind": "before",
  "photo_context": "face_frontal",
  "taken_at": "2025-12-20T10:30:00Z",
  "notes": "Foto frontal antes de tratamiento botox",
  "is_deleted": false,
  "created_at": "2025-12-20T10:35:00Z",
  "updated_at": "2025-12-20T10:35:00Z",
  "created_by_user_id": "practitioner-user-uuid-...",
  "updated_by_user_id": "practitioner-user-uuid-..."
}
```

**Errores:**
- `400 Bad Request`: Validación fallida
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Datos inválidos",
    "details": {
      "object_key": ["El archivo no existe en el bucket clinical"],
      "mime_type": ["Tipo MIME no soportado. Solo image/jpeg, image/png"]
    }
  }
}
```

- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Reception/Marketing/Accounting intentan crear foto clínica
- `404 Not Found`: Paciente no existe

**Notas:**
- Foto se almacena en bucket **clinical** (privado, solo acceso autenticado)
- `ClinicalPhoto` es **inmutable**: no se puede editar `object_key`, `mime_type`, `file_size_bytes`
- Solo se pueden actualizar metadatos: `photo_kind`, `photo_context`, `notes` (endpoint PATCH futuro)
- Flujo típico: 1) Subir archivo con `/uploads/presign`, 2) Crear metadata con este endpoint
- Marketing **NO** tiene acceso a fotos clínicas (bucket separation)

---

### GET /api/v1/patients/{id}/photos/
Lista fotos clínicas de un paciente.

**Roles permitidos:** Admin, Practitioner

**Query Parameters:**
- `photo_kind` (string): Filtrar por tipo (before, after, during, other)
- `photo_context` (string): Filtrar por contexto anatómico (face_frontal, face_left_profile, etc.)
- `date_from` (date ISO): Fotos desde esta fecha (campo `taken_at`)
- `date_to` (date ISO): Fotos hasta esta fecha
- `include_deleted` (boolean): Incluir soft-deleted (solo Admin, default: false)
- `page` (int): Número de página (default: 1)
- `page_size` (int): Resultados por página (default: 20, max: 100)
- `ordering` (string): Campo de ordenamiento (default: `-taken_at`)

**Ejemplos:**
```
GET /api/v1/patients/987fcdeb-.../photos/?photo_kind=before
GET /api/v1/patients/987fcdeb-.../photos/?photo_context=face_frontal&ordering=-taken_at
GET /api/v1/patients/987fcdeb-.../photos/?date_from=2025-01-01&date_to=2025-12-31
```

**Response (200 OK):**
```json
{
  "count": 12,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "photo-uuid-1",
      "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
      "object_key": "clinical/2025/12/20/987fcdeb-.../face_frontal_before.jpg",
      "storage_bucket": "clinical",
      "original_filename": "face_frontal_before.jpg",
      "mime_type": "image/jpeg",
      "file_size_bytes": 2458624,
      "photo_kind": "before",
      "photo_context": "face_frontal",
      "taken_at": "2025-12-20T10:30:00Z",
      "notes": "Foto frontal antes de tratamiento botox",
      "created_at": "2025-12-20T10:35:00Z"
    },
    {
      "id": "photo-uuid-2",
      "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
      "object_key": "clinical/2025/12/20/987fcdeb-.../face_left_before.jpg",
      "storage_bucket": "clinical",
      "original_filename": "face_left_before.jpg",
      "mime_type": "image/jpeg",
      "file_size_bytes": 2301456,
      "photo_kind": "before",
      "photo_context": "face_left_profile",
      "taken_at": "2025-12-20T10:31:00Z",
      "notes": "Perfil izquierdo antes",
      "created_at": "2025-12-20T10:36:00Z"
    }
  ]
}
```

**Notas:**
- Solo Admin y Practitioners pueden ver fotos clínicas
- Por defecto, **excluye** fotos con `is_deleted=true`
- Response NO incluye URL de descarga (usar endpoint `/photos/{id}/download` futuro)
- Ordenamiento default: `-taken_at` (más recientes primero)

**Errores:**
- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Reception/Marketing/Accounting intentan acceder
- `404 Not Found`: Paciente no existe

---

### POST /api/v1/encounters/{id}/photos/attach/
Adjunta fotos clínicas existentes a un encounter. Crea relación M:N vía `EncounterPhoto`.

**Roles permitidos:** Admin, Practitioner (solo encounters propios)

**Request:**
```json
{
  "photo_ids": [
    "photo-uuid-1",
    "photo-uuid-2"
  ],
  "relation_type": "attached"
}
```

**Campos obligatorios:**
- `photo_ids` (array of UUIDs): IDs de las fotos clínicas a adjuntar
- `relation_type` (enum): Tipo de relación

**Valores de relation_type (enum):**
- `attached`: Foto adjunta al encounter (general)
- `comparison`: Foto usada en comparativa before/after (usar endpoint `/photos/compare`)

**Response (200 OK):**
```json
{
  "encounter_id": "encounter-uuid-...",
  "attached_photos": [
    {
      "photo_id": "photo-uuid-1",
      "relation_type": "attached",
      "created_at": "2025-12-20T11:00:00Z"
    },
    {
      "photo_id": "photo-uuid-2",
      "relation_type": "attached",
      "created_at": "2025-12-20T11:00:00Z"
    }
  ],
  "total_photos": 2
}
```

**Errores:**
- `400 Bad Request`: Validación fallida
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Datos inválidos",
    "details": {
      "photo_ids": ["Una o más fotos no existen o no pertenecen al mismo paciente del encounter"]
    }
  }
}
```

- `409 Conflict`: Foto ya adjunta al encounter
```json
{
  "error": {
    "code": "CONFLICT",
    "message": "Una o más fotos ya están adjuntas a este encounter",
    "details": {
      "duplicate_photo_ids": ["photo-uuid-1"]
    }
  }
}
```

- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Practitioner intenta adjuntar fotos a encounter de otro practitioner
- `404 Not Found`: Encounter no existe

**Notas:**
- Fotos y encounter deben pertenecer al **mismo paciente**
- Se pueden adjuntar múltiples fotos en una sola request
- Relación M:N permite que una foto esté adjunta a múltiples encounters
- `relation_type=attached` para fotos generales del encounter
- Para comparativas before/after, usar endpoint `/photos/compare`

---

### POST /api/v1/encounters/{id}/photos/compare/
Adjunta fotos para comparativa before/after. Crea relación M:N con `relation_type=comparison`.

**Roles permitidos:** Admin, Practitioner (solo encounters propios)

**Request:**
```json
{
  "before_photo_id": "photo-uuid-before",
  "after_photo_id": "photo-uuid-after",
  "notes": "Comparativa antes/después de tratamiento botox en zona frontal. Resultado visible a 2 semanas."
}
```

**Campos obligatorios:**
- `before_photo_id` (UUID): Foto "before"
- `after_photo_id` (UUID): Foto "after"

**Campos opcionales:**
- `notes` (string): Notas sobre la comparativa

**Response (200 OK):**
```json
{
  "encounter_id": "encounter-uuid-...",
  "comparison": {
    "before_photo_id": "photo-uuid-before",
    "before_photo": {
      "id": "photo-uuid-before",
      "object_key": "clinical/.../face_frontal_before.jpg",
      "photo_kind": "before",
      "taken_at": "2025-12-20T10:30:00Z"
    },
    "after_photo_id": "photo-uuid-after",
    "after_photo": {
      "id": "photo-uuid-after",
      "object_key": "clinical/.../face_frontal_after.jpg",
      "photo_kind": "after",
      "taken_at": "2026-01-03T14:00:00Z"
    },
    "notes": "Comparativa antes/después de tratamiento botox en zona frontal. Resultado visible a 2 semanas.",
    "created_at": "2026-01-03T14:30:00Z"
  }
}
```

**Errores:**
- `400 Bad Request`: Validación fallida
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Datos inválidos",
    "details": {
      "before_photo_id": ["La foto no pertenece al mismo paciente del encounter"],
      "after_photo_id": ["La foto no existe o está eliminada"]
    }
  }
}
```

- `409 Conflict`: Comparativa ya existe
```json
{
  "error": {
    "code": "CONFLICT",
    "message": "Ya existe una comparativa con estas fotos en este encounter"
  }
}
```

- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Practitioner intenta crear comparativa en encounter de otro practitioner
- `404 Not Found`: Encounter no existe

**Notas:**
- Crea **dos** registros en `EncounterPhoto`: uno para before, otro para after, ambos con `relation_type=comparison`
- Fotos deben pertenecer al **mismo paciente** del encounter
- No se valida que `before_photo.taken_at < after_photo.taken_at` (puede ser mismo día)
- Útil para documentar resultados de tratamientos estéticos

---

### DELETE /api/v1/photos/{photo_id}/
Elimina una foto clínica (soft delete).

**Roles permitidos:** Admin

**Response (204 No Content):**
```
(sin cuerpo de respuesta)
```

**Errores:**
- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Practitioner/Reception/Marketing/Accounting intentan eliminar
- `404 Not Found`: Foto no existe o ya está eliminada

**Notas:**
- Es **soft delete**: `is_deleted=true`, `deleted_at`, `deleted_by_user_id` se populan
- Solo **Admin** puede eliminar fotos clínicas
- Foto eliminada NO aparece en listados (salvo `?include_deleted=true` para Admin)
- Archivo en MinIO **NO** se elimina (solo metadata marcada como deleted)
- Relaciones `EncounterPhoto` se mantienen (no se eliminan automáticamente)

---

## Documents (DOC)

### POST /api/v1/documents/
Crea metadata de un documento (PDF, Word, etc.). Documento se almacena en bucket **documents** (MinIO).

**Roles permitidos:** Admin, Practitioner, Reception, Accounting

**Request:**
```json
{
  "object_key": "documents/2025/12/20/lab_result_987fcdeb.pdf",
  "original_filename": "resultado_laboratorio.pdf",
  "mime_type": "application/pdf",
  "file_size_bytes": 1245680,
  "content_type": "lab_result",
  "description": "Resultado de laboratorio pre-procedimiento",
  "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab"
}
```

**Campos obligatorios:**
- `object_key` (string): Clave del objeto en MinIO bucket `documents` (obtenida de `/uploads/presign`)
- `original_filename` (string): Nombre original del archivo
- `mime_type` (string): Tipo MIME (ej: `application/pdf`, `image/jpeg`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`)
- `file_size_bytes` (int): Tamaño del archivo en bytes

**Valores de content_type (enum):**
- `lab_result` (resultado de laboratorio)
- `prescription` (prescripción médica)
- `consent_form` (formulario de consentimiento firmado)
- `invoice` (factura)
- `receipt` (recibo de pago)
- `other` (otro)

**Campos opcionales:**
- `content_type` (enum): Tipo de contenido
- `description` (string): Descripción del documento
- `patient_id` (UUID): Paciente asociado (opcional, puede ser null para documentos generales)

**Response (201 Created):**
```json
{
  "id": "document-uuid-...",
  "object_key": "documents/2025/12/20/lab_result_987fcdeb.pdf",
  "storage_bucket": "documents",
  "original_filename": "resultado_laboratorio.pdf",
  "mime_type": "application/pdf",
  "file_size_bytes": 1245680,
  "content_type": "lab_result",
  "description": "Resultado de laboratorio pre-procedimiento",
  "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
  "patient": {
    "id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
    "first_name": "María",
    "last_name": "González"
  },
  "is_deleted": false,
  "created_at": "2025-12-20T09:00:00Z",
  "updated_at": "2025-12-20T09:00:00Z",
  "created_by_user_id": "reception-user-uuid-...",
  "updated_by_user_id": "reception-user-uuid-..."
}
```

**Errores:**
- `400 Bad Request`: Validación fallida
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Datos inválidos",
    "details": {
      "object_key": ["El archivo no existe en el bucket documents"],
      "patient_id": ["El paciente no existe"]
    }
  }
}
```

- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Marketing intenta crear documento

**Notas:**
- Documento se almacena en bucket **documents** (acceso controlado)
- `patient_id` es **opcional** (puede ser null para documentos no asociados a paciente)
- Accounting puede crear documentos tipo `invoice` o `receipt`
- Flujo típico: 1) Subir archivo con `/uploads/presign`, 2) Crear metadata con este endpoint

---

### GET /api/v1/documents/
Lista documentos con filtros.

**Roles permitidos:** Admin, Practitioner, Reception, Accounting

**Query Parameters:**
- `content_type` (string): Filtrar por tipo (lab_result, prescription, consent_form, invoice, receipt, other)
- `patient_id` (UUID): Filtrar por paciente
- `date_from` (date ISO): Documentos desde esta fecha (campo `created_at`)
- `date_to` (date ISO): Documentos hasta esta fecha
- `include_deleted` (boolean): Incluir soft-deleted (solo Admin, default: false)
- `page` (int): Número de página (default: 1)
- `page_size` (int): Resultados por página (default: 20, max: 100)
- `ordering` (string): Campo de ordenamiento (default: `-created_at`)

**Ejemplos:**
```
GET /api/v1/documents/?content_type=lab_result
GET /api/v1/documents/?patient_id=987fcdeb-...&ordering=-created_at
GET /api/v1/documents/?content_type=invoice&date_from=2025-12-01
```

**Response (200 OK):**
```json
{
  "count": 28,
  "next": "http://api.example.com/api/v1/documents/?page=2",
  "previous": null,
  "results": [
    {
      "id": "document-uuid-1",
      "object_key": "documents/2025/12/20/lab_result_987fcdeb.pdf",
      "storage_bucket": "documents",
      "original_filename": "resultado_laboratorio.pdf",
      "mime_type": "application/pdf",
      "file_size_bytes": 1245680,
      "content_type": "lab_result",
      "description": "Resultado de laboratorio pre-procedimiento",
      "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
      "patient": {
        "id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
        "first_name": "María",
        "last_name": "González"
      },
      "created_at": "2025-12-20T09:00:00Z"
    },
    {
      "id": "document-uuid-2",
      "object_key": "documents/2025/12/19/consent_abc12345.pdf",
      "storage_bucket": "documents",
      "original_filename": "consentimiento_botox.pdf",
      "mime_type": "application/pdf",
      "file_size_bytes": 856320,
      "content_type": "consent_form",
      "description": "Consentimiento informado tratamiento botox",
      "patient_id": "abc12345-...",
      "patient": {
        "id": "abc12345-...",
        "first_name": "Juan",
        "last_name": "Martínez"
      },
      "created_at": "2025-12-19T15:00:00Z"
    }
  ]
}
```

**Notas:**
- Por defecto, **excluye** documentos con `is_deleted=true`
- Marketing **NO** tiene acceso a documentos (contienen información sensible)
- Response NO incluye URL de descarga (usar endpoint `/documents/{id}/download` futuro)
- Accounting puede ver todos los documentos (típicamente filtra por `content_type=invoice|receipt`)

**Errores:**
- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Marketing intenta acceder

---

### POST /api/v1/encounters/{id}/documents/attach/
Adjunta documentos existentes a un encounter. Crea relación M:N vía `EncounterDocument`.

**Roles permitidos:** Admin, Practitioner (solo encounters propios)

**Request:**
```json
{
  "document_ids": [
    "document-uuid-1",
    "document-uuid-2"
  ],
  "kind": "lab_result"
}
```

**Campos obligatorios:**
- `document_ids` (array of UUIDs): IDs de los documentos a adjuntar
- `kind` (enum): Tipo de documento en contexto del encounter

**Valores de kind (enum):**
- `lab_result` (resultado de laboratorio)
- `prescription` (prescripción médica)
- `consent_form` (formulario de consentimiento)
- `invoice` (factura)
- `other` (otro)

**Response (200 OK):**
```json
{
  "encounter_id": "encounter-uuid-...",
  "attached_documents": [
    {
      "document_id": "document-uuid-1",
      "kind": "lab_result",
      "created_at": "2025-12-20T11:30:00Z"
    },
    {
      "document_id": "document-uuid-2",
      "kind": "lab_result",
      "created_at": "2025-12-20T11:30:00Z"
    }
  ],
  "total_documents": 2
}
```

**Errores:**
- `400 Bad Request`: Validación fallida
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Datos inválidos",
    "details": {
      "document_ids": ["Uno o más documentos no existen"]
    }
  }
}
```

- `409 Conflict`: Documento ya adjunto al encounter
```json
{
  "error": {
    "code": "CONFLICT",
    "message": "Uno o más documentos ya están adjuntos a este encounter",
    "details": {
      "duplicate_document_ids": ["document-uuid-1"]
    }
  }
}
```

- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Practitioner intenta adjuntar documentos a encounter de otro practitioner
- `404 Not Found`: Encounter no existe

**Notas:**
- Se pueden adjuntar múltiples documentos en una sola request
- Relación M:N permite que un documento esté adjunto a múltiples encounters
- `kind` ayuda a clasificar el documento en contexto del encounter (puede diferir de `Document.content_type`)
- Documentos y encounter **NO** necesitan pertenecer al mismo paciente (ej: documentos generales)

---

### POST /api/v1/consents/{id}/document/attach/
Adjunta un documento a un consent (formulario de consentimiento firmado).

**Roles permitidos:** Admin, Practitioner, Reception

**Request:**
```json
{
  "document_id": "document-uuid-..."
}
```

**Campos obligatorios:**
- `document_id` (UUID): ID del documento a adjuntar

**Response (200 OK):**
```json
{
  "consent_id": "consent-uuid-...",
  "consent_type": "clinical_photos",
  "document_id": "document-uuid-...",
  "document": {
    "id": "document-uuid-...",
    "original_filename": "consentimiento_fotos_clinicas.pdf",
    "mime_type": "application/pdf",
    "created_at": "2025-12-20T09:00:00Z"
  },
  "updated_at": "2025-12-20T10:00:00Z"
}
```

**Errores:**
- `400 Bad Request`: Validación fallida
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Datos inválidos",
    "details": {
      "document_id": ["El documento no existe"]
    }
  }
}
```

- `409 Conflict`: Consent ya tiene documento adjunto
```json
{
  "error": {
    "code": "CONFLICT",
    "message": "El consentimiento ya tiene un documento adjunto",
    "details": {
      "existing_document_id": "document-uuid-old"
    }
  }
}
```

- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Marketing/Accounting intentan adjuntar documento
- `404 Not Found`: Consent no existe

**Notas:**
- Relación **1:1** (un consent tiene un solo documento adjunto)
- Si ya existe documento, retorna `409 Conflict` (primero eliminar el anterior o usar PATCH para reemplazar)
- Típicamente documento tipo `consent_form` (PDF firmado)
- Adjuntar documento es **opcional** (consent puede existir sin documento)

---

## Timeline

### GET /api/v1/patients/{id}/timeline/
Obtiene línea de tiempo del paciente: encounters, appointments, fotos, documentos ordenados cronológicamente.

**Roles permitidos:** Admin, Practitioner

**Query Parameters:**
- `date_from` (date ISO): Eventos desde esta fecha
- `date_to` (date ISO): Eventos hasta esta fecha
- `event_types` (string): Filtrar por tipo (comma-separated: `encounter,appointment,photo,document`)
- `page` (int): Número de página (default: 1)
- `page_size` (int): Eventos por página (default: 50, max: 200)

**Ejemplos:**
```
GET /api/v1/patients/987fcdeb-.../timeline/
GET /api/v1/patients/987fcdeb-.../timeline/?date_from=2025-01-01&date_to=2025-12-31
GET /api/v1/patients/987fcdeb-.../timeline/?event_types=encounter,photo
```

**Response (200 OK):**
```json
{
  "patient_id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
  "patient": {
    "id": "987fcdeb-51a2-43f7-8d9e-1234567890ab",
    "first_name": "María",
    "last_name": "González",
    "date_of_birth": "1992-05-15"
  },
  "count": 23,
  "next": null,
  "previous": null,
  "events": [
    {
      "event_type": "photo",
      "event_date": "2026-01-03T14:00:00Z",
      "id": "photo-uuid-after",
      "data": {
        "photo_kind": "after",
        "photo_context": "face_frontal",
        "original_filename": "face_frontal_after.jpg",
        "notes": "Foto después de 2 semanas de tratamiento botox"
      }
    },
    {
      "event_type": "encounter",
      "event_date": "2025-12-20T10:15:00Z",
      "id": "encounter-uuid-...",
      "data": {
        "encounter_type": "consultation",
        "status": "finalized",
        "chief_complaint": "Evaluación para tratamiento de arrugas faciales",
        "diagnosis": "Arrugas dinámicas frontales y glabelares. Grado II.",
        "practitioner": {
          "id": "practitioner-uuid-...",
          "user": {
            "first_name": "Dr. Juan",
            "last_name": "Pérez"
          }
        }
      }
    },
    {
      "event_type": "photo",
      "event_date": "2025-12-20T10:30:00Z",
      "id": "photo-uuid-before",
      "data": {
        "photo_kind": "before",
        "photo_context": "face_frontal",
        "original_filename": "face_frontal_before.jpg",
        "notes": "Foto frontal antes de tratamiento botox"
      }
    },
    {
      "event_type": "appointment",
      "event_date": "2025-12-20T10:00:00Z",
      "id": "appointment-uuid-...",
      "data": {
        "appointment_type": "consultation",
        "status": "completed",
        "source": "manual",
        "practitioner": {
          "id": "practitioner-uuid-...",
          "user": {
            "first_name": "Dr. Juan",
            "last_name": "Pérez"
          }
        }
      }
    },
    {
      "event_type": "document",
      "event_date": "2025-12-20T09:00:00Z",
      "id": "document-uuid-...",
      "data": {
        "content_type": "lab_result",
        "original_filename": "resultado_laboratorio.pdf",
        "description": "Resultado de laboratorio pre-procedimiento"
      }
    }
  ]
}
```

**Estructura de eventos:**
Cada evento tiene:
- `event_type` (string): Tipo de evento (`encounter`, `appointment`, `photo`, `document`)
- `event_date` (datetime ISO 8601): Fecha del evento (según tipo)
- `id` (UUID): ID del recurso
- `data` (object): Datos específicos del evento (campos relevantes del recurso)

**Mapeo de fechas:**
- `encounter`: `encounter_date`
- `appointment`: `scheduled_start`
- `photo`: `taken_at`
- `document`: `created_at`

**Ordenamiento:**
- Eventos ordenados por `event_date` **descendente** (más recientes primero)

**Errores:**
- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`: Reception/Marketing/Accounting intentan acceder
- `404 Not Found`: Paciente no existe

**Notas:**
- Timeline **unifica** múltiples recursos en una vista cronológica
- Solo incluye recursos **no eliminados** (soft-deleted excluidos)
- Útil para vista de historial del paciente en frontend
- `event_types` permite filtrar por tipo de evento específico
- Paginación default: 50 eventos por página (ajustable hasta 200)

---

## Upload Strategy v1

### POST /api/v1/uploads/presign/
Genera URL presignada para subir archivos a MinIO (S3-compatible). **Paso 1** del flujo de uploads.

**Roles permitidos:** Admin, Practitioner, Reception, Accounting

**Request:**
```json
{
  "bucket": "clinical",
  "content_type": "image/jpeg",
  "filename": "face_frontal_before.jpg"
}
```

**Campos obligatorios:**
- `bucket` (enum): Bucket destino (`"clinical"` o `"documents"`)
- `content_type` (string): Tipo MIME del archivo (ej: `image/jpeg`, `application/pdf`)
- `filename` (string): Nombre original del archivo (usado para generar `object_key`)

**Validaciones:**
- **Bucket `clinical`**: Solo Admin y Practitioner (fotos clínicas sensibles)
- **Bucket `documents`**: Admin, Practitioner, Reception, Accounting
- `content_type` debe ser válido según bucket:
  - `clinical`: `image/jpeg`, `image/png`
  - `documents`: `application/pdf`, `image/jpeg`, `image/png`, `application/vnd.*` (Office docs)

**Response (200 OK):**
```json
{
  "upload_url": "https://minio.clinica.com/clinical/2025/12/20/987fcdeb-51a2.../face_frontal_before.jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...",
  "object_key": "clinical/2025/12/20/987fcdeb-51a2-43f7-8d9e-1234567890ab/face_frontal_before.jpg",
  "bucket": "clinical",
  "expires_in": 3600,
  "method": "PUT"
}
```

**Campos de response:**
- `upload_url` (string): URL presignada para subir archivo (método PUT)
- `object_key` (string): Clave del objeto en MinIO (usar al crear `ClinicalPhoto` o `Document`)
- `bucket` (string): Bucket donde se subirá el archivo
- `expires_in` (int): Segundos hasta que expire la URL (default: 3600 = 1 hora)
- `method` (string): Método HTTP a usar (`PUT`)

**Flujo completo de upload:**

1. **Paso 1**: Cliente llama `POST /api/v1/uploads/presign/` → Obtiene `upload_url` y `object_key`

2. **Paso 2**: Cliente sube archivo directamente a MinIO usando `upload_url`:
   ```bash
   curl -X PUT "https://minio.clinica.com/clinical/...?X-Amz-..." \
     -H "Content-Type: image/jpeg" \
     --data-binary @face_frontal_before.jpg
   ```

3. **Paso 3**: Cliente crea metadata en API:
   - Si bucket `clinical`: `POST /api/v1/patients/{id}/photos/` con `object_key`
   - Si bucket `documents`: `POST /api/v1/documents/` con `object_key`

**Errores:**
- `400 Bad Request`: Validación fallida
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Datos inválidos",
    "details": {
      "bucket": ["Bucket inválido. Opciones: clinical, documents"],
      "content_type": ["Tipo MIME no soportado para bucket clinical"]
    }
  }
}
```

- `401 Unauthorized`: Sin token JWT
- `403 Forbidden`:
  - Reception/Accounting intentan subir a bucket `clinical`
  - Marketing intenta subir a cualquier bucket

**Notas:**
- URL presignada expira en **1 hora** (configurable)
- Cliente sube **directamente a MinIO** (no pasa por backend Django)
- Después de subir, cliente **debe** crear metadata (foto o documento) para que el archivo sea visible en la API
- Si upload a MinIO falla, archivo no queda "huérfano" (no existe metadata)
- Si metadata no se crea después de upload exitoso, archivo queda en MinIO sin registro (limpieza futura vNext)

**Seguridad:**
- URL presignada es **temporal** y **específica** para un archivo
- No se puede reutilizar URL para subir archivos diferentes
- Permisos de bucket se validan al generar URL presignada (según rol del usuario)

---

## Mapping 1:1 (Use Cases → Endpoints)

Esta sección mapea los **25 use cases** documentados en `USE_CASES.md` a los endpoints REST definidos en este documento.

### PAC - Patients (Pacientes)

| Use Case | Endpoint(s) | Método | Descripción |
|----------|------------|--------|-------------|
| **PAC-01** | `/api/v1/patients/` | POST | Crear nuevo paciente |
| **PAC-02** | `/api/v1/patients/` | GET | Buscar pacientes (query params: `q`, `email`, `phone`) |
| **PAC-03** | `/api/v1/patients/{id}/` | GET, PATCH | Ver/editar perfil de paciente (incluye `row_version`) |
| **PAC-04** | `/api/v1/patients/{id}/merge/` | POST | Mergear pacientes duplicados |
| **PAC-05** | `/api/v1/patients/{id}/guardians/`<br>`/api/v1/guardians/{id}/` | POST, GET, PATCH, DELETE | Gestionar guardians (crear, listar, editar, eliminar) |

---

### AGD - Appointments (Agenda)

| Use Case | Endpoint(s) | Método | Descripción |
|----------|------------|--------|-------------|
| **AGD-01** | `/api/v1/appointments/` | POST | Crear cita manual |
| **AGD-02** | `/api/v1/appointments/calendly/sync/` | POST | Sincronizar citas desde Calendly (idempotente por `external_id`) |
| **AGD-03** | `/api/v1/appointments/{id}/` | PATCH | Cambiar estado de cita (status transitions, cancellation_reason) |
| **AGD-04** | `/api/v1/appointments/` | GET | Ver agenda (filtros: `status`, `date_from`, `date_to`, `practitioner_id`) |
| **AGD-05** | `/api/v1/appointments/{id}/link-encounter/` | POST | Vincular cita con encounter (relación 1:1 opcional) |

---

### ENC - Encounters (Visitas Clínicas)

| Use Case | Endpoint(s) | Método | Descripción |
|----------|------------|--------|-------------|
| **ENC-01** | `/api/v1/encounters/` | POST | Crear encounter en estado `draft` |
| **ENC-02** | `/api/v1/encounters/{id}/` | PATCH | Editar encounter `draft` (requiere `row_version`) |
| **ENC-03** | `/api/v1/encounters/{id}/finalize/` | POST | Finalizar encounter (bloquea ediciones, status → `finalized`) |

---

### CON - Consents (Consentimientos)

| Use Case | Endpoint(s) | Método | Descripción |
|----------|------------|--------|-------------|
| **CON-01** | `/api/v1/patients/{id}/consents/grant/` | POST | Otorgar consentimiento (crea registro `is_granted=true`) |
| **CON-02** | `/api/v1/patients/{id}/consents/revoke/` | POST | Revocar consentimiento (crea registro `is_granted=false`) |
| **CON-03** | `/api/v1/patients/{id}/consents/status/` | GET | Consultar estado de consentimientos (4 tipos: clinical_photos, marketing_photos, newsletter, marketing_messages) |

---

### PHO - Photos (Fotos Clínicas)

| Use Case | Endpoint(s) | Método | Descripción |
|----------|------------|--------|-------------|
| **PHO-01** | `1. /api/v1/uploads/presign/`<br>`2. PUT {upload_url}`<br>`3. /api/v1/patients/{id}/photos/` | POST, PUT, POST | Subir foto clínica (3 pasos: presign, upload MinIO, crear metadata) |
| **PHO-02** | `/api/v1/encounters/{id}/photos/attach/` | POST | Adjuntar foto a encounter (`relation_type=attached`) |
| **PHO-03** | `/api/v1/encounters/{id}/photos/compare/` | POST | Crear comparativa before/after (`relation_type=comparison`) |
| **PHO-04** | `/api/v1/patients/{id}/photos/` | GET | Ver fotos de paciente (filtros: `photo_kind`, `photo_context`, `date_from`) |

---

### DOC - Documents (Documentos)

| Use Case | Endpoint(s) | Método | Descripción |
|----------|------------|--------|-------------|
| **DOC-01** | `1. /api/v1/uploads/presign/`<br>`2. PUT {upload_url}`<br>`3. /api/v1/documents/` | POST, PUT, POST | Subir documento (3 pasos: presign, upload MinIO, crear metadata) |
| **DOC-02** | `/api/v1/encounters/{id}/documents/attach/` | POST | Adjuntar documento a encounter (con `kind`) |
| **DOC-03** | `/api/v1/patients/{id}/timeline/` | GET | Ver timeline de paciente (encounters, appointments, photos, documents) |

---

### Endpoints Adicionales (No mapeados a use cases específicos)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/v1/auth/token/` | POST | Autenticación JWT (obtener access + refresh tokens) |
| `/api/v1/auth/token/refresh/` | POST | Renovar access token |
| `/api/v1/encounters/` | GET | Listar encounters con filtros (usado en múltiples flujos) |
| `/api/v1/encounters/{id}/` | GET | Ver detalle de encounter |
| `/api/v1/documents/` | GET | Listar documentos con filtros |
| `/api/v1/photos/{id}/` | DELETE | Soft-delete de foto clínica (solo Admin) |
| `/api/v1/consents/{id}/document/attach/` | POST | Adjuntar PDF firmado a consent |

---

### Resumen de Cobertura

- **Total de use cases**: 25 (PAC: 5, AGD: 5, ENC: 3, CON: 3, PHO: 4, DOC: 3, Timeline: 2)
- **Total de endpoints principales**: 32 (incluyendo auth, CRUD, y operaciones especiales)
- **Cobertura**: ✅ 100% (todos los use cases tienen endpoint(s) correspondiente(s))

---

### Notas Finales sobre el Mapping

- **Flujos multi-paso**: Upload de fotos/documentos requiere 3 pasos (presign → upload MinIO → crear metadata)
- **Operaciones especiales**: Merge, finalize, link-encounter, attach, compare son endpoints dedicados (no simples PATCH)
- **Idempotencia**: Calendly sync es idempotente por `external_id` (múltiples ejecuciones no crean duplicados)
- **Soft delete**: Pacientes, encounters, fotos, documentos usan soft delete (no hard delete, excepto guardians)
- **Concurrencia**: Pacientes y encounters usan `row_version` para optimistic locking (409 Conflict si no coincide)

---
