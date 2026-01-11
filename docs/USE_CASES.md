# USE CASES - Clinical & Scheduling

Casos de uso funcionales para el módulo clínico: gestión de pacientes, agenda, visitas (encounters), consentimientos, fotos clínicas y documentos adjuntos. Este documento define **qué** debe hacer el sistema, no **cómo** se implementa técnicamente.

## Actores y Roles

### Admin
- Acceso total a todos los módulos
- Gestión de usuarios y roles
- Configuración del sistema (app_settings, clinic_location)
- Operaciones de mantenimiento y diagnóstico

### Practitioner (Médico/Dermatólogo)
- Gestión completa de pacientes
- Creación y edición de encounters
- Subida y visualización de fotos clínicas
- Registro de consentimientos
- Acceso a timeline completo del paciente
- Finalización de encounters (firma digital en vNext)

### Reception (Recepción)
- Gestión de pacientes (crear, editar, buscar)
- Gestión de agenda (appointments)
- Confirmación/cancelación de citas
- Registro de consentimientos básicos
- **NO** puede ver fotos clínicas (solo verifica consents)
- **NO** puede editar encounters finalizados

### Marketing
- **NO** acceso a datos clínicos
- **SOLO** visualiza consents de marketing_photos y newsletter
- **NO** acceso a fotos clínicas
- (Casos de uso en documento separado para website/social)

### Accounting
- **NO** acceso a datos clínicos
- (Casos de uso en documento separado para commerce)

---

## PAC: Gestión de Pacientes

### PAC-01 Crear paciente
- **Actor principal:** Reception, Practitioner
- **Actores secundarios:** Admin
- **Precondiciones:** Usuario autenticado con rol adecuado
- **Disparador:** Nuevo paciente llega al consultorio

**Flujo principal:**
1. Usuario selecciona "Nuevo paciente"
2. Usuario ingresa datos obligatorios: first_name, last_name
3. Usuario ingresa datos opcionales: birth_date, sex, email, phone, address (address_line1, city, postal_code, country_code)
4. Usuario selecciona preferred_language (ru|fr|en|uk|hy|es)
5. Usuario selecciona preferred_contact_method (phone_call|sms|whatsapp|email)
6. Usuario ingresa preferred_contact_time si aplica
7. Usuario selecciona referral_source (instagram|google_maps|friend|doctor|walk_in|website|other)
8. Usuario ingresa referral_details si aplica
9. Usuario marca contact_opt_out si el paciente no quiere recibir comunicaciones
10. Sistema normaliza full_name_normalized (lowercase, sin acentos)
11. Sistema valida phone_e164 si se ingresó teléfono
12. Sistema asigna identity_confidence = 'low' por defecto
13. Sistema asigna row_version = 1
14. Sistema registra created_by_user_id
15. Sistema guarda Patient

**Flujos alternativos / errores:**
- Si email ya existe: advertir posible duplicado pero permitir continuar
- Si phone_e164 ya existe: advertir posible duplicado pero permitir continuar
- Si datos obligatorios faltantes: mostrar error de validación

**Datos creados/actualizados:**
- **Patient:** id, first_name, last_name, full_name_normalized, birth_date, sex, email, phone, phone_e164, address_line1, city, postal_code, country_code, preferred_language, preferred_contact_method, preferred_contact_time, contact_opt_out, identity_confidence='low', referral_source_id, referral_details, row_version=1, created_by_user_id, created_at, updated_at

**Reglas de negocio:**
- phone_e164 debe validarse en formato E.164 (+[country][number])
- full_name_normalized se usa para búsquedas case-insensitive
- identity_confidence empieza en 'low', puede elevarse a 'medium'/'high' con verificación posterior
- country_code permite segmentación por país

**Auditoría/seguridad:**
- created_by_user_id registra quién creó el paciente
- created_at registra cuándo se creó
- Todos los accesos a Patient se auditan en audit_log (vNext)

**Criterios de aceptación:**
```gherkin
Given usuario con rol reception o practitioner
When crea paciente con first_name="Juan" y last_name="Pérez"
Then Patient se guarda con full_name_normalized="juan perez"
And identity_confidence="low"
And row_version=1
And created_by_user_id=usuario actual
```

---

### PAC-02 Buscar paciente
- **Actor principal:** Reception, Practitioner
- **Actores secundarios:** Admin
- **Precondiciones:** Usuario autenticado
- **Disparador:** Usuario necesita encontrar un paciente existente

**Flujo principal:**
1. Usuario accede a búsqueda de pacientes
2. Usuario ingresa criterio de búsqueda: nombre completo, email, teléfono, o país
3. Sistema busca en índices: (last_name, first_name), email, phone_e164, country_code, full_name_normalized
4. Sistema filtra is_deleted=false por defecto
5. Sistema ordena por relevancia o fecha de creación
6. Sistema muestra resultados con: nombre completo, edad (calculada de birth_date), email, phone, última visita
7. Usuario selecciona paciente de la lista

**Flujos alternativos / errores:**
- Si búsqueda vacía: mostrar todos los pacientes activos (paginado)
- Si no hay resultados: ofrecer crear nuevo paciente
- Si paciente is_merged=true: mostrar enlace a merged_into_patient

**Datos creados/actualizados:**
- Ninguno (solo lectura)

**Reglas de negocio:**
- Búsqueda es case-insensitive usando full_name_normalized
- phone_e164 permite búsqueda exacta sin importar formato local
- Pacientes soft-deleted (is_deleted=true) NO aparecen por defecto
- Pacientes merged (is_merged=true) muestran redirección al paciente principal

**Auditoría/seguridad:**
- Búsquedas de pacientes se auditan (quién buscó qué) para HIPAA/GDPR
- Reception puede buscar todos los pacientes
- Marketing NO puede buscar pacientes

**Criterios de aceptación:**
```gherkin
Given existen Patient con last_name="Pérez" y last_name="Perez"
When usuario busca "perez"
Then ambos pacientes aparecen en resultados
And pacientes con is_deleted=true NO aparecen
And pacientes con is_merged=true muestran redirect
```

---

### PAC-03 Editar paciente
- **Actor principal:** Reception, Practitioner
- **Actores secundarios:** Admin
- **Precondiciones:** Paciente existe, no está soft-deleted
- **Disparador:** Usuario necesita actualizar información del paciente

**Flujo principal:**
1. Usuario abre perfil del paciente
2. Usuario modifica campos editables: nombre, contacto, dirección, preferencias
3. Sistema verifica row_version actual vs versión cargada (optimistic locking)
4. Sistema valida phone_e164 si cambió
5. Sistema actualiza full_name_normalized si cambió el nombre
6. Sistema incrementa row_version
7. Sistema actualiza updated_at
8. Sistema guarda cambios

**Flujos alternativos / errores:**
- Si row_version no coincide: error "Otro usuario editó este paciente, recargar datos"
- Si phone_e164 inválido: error de validación
- Si is_deleted=true: no permitir edición

**Datos creados/actualizados:**
- **Patient:** campos modificados, full_name_normalized (si cambió nombre), row_version (incrementado), updated_at

**Reglas de negocio:**
- Control de concurrencia mediante row_version
- No se puede editar paciente soft-deleted
- No se puede editar paciente merged (is_merged=true)
- Cambios de email/phone deben validarse

**Auditoría/seguridad:**
- Cambios se registran en audit_log con fields_changed
- updated_at registra última modificación
- Cambios críticos (email, phone) pueden requerir confirmación

**Criterios de aceptación:**
```gherkin
Given Patient con row_version=5
When usuario A carga datos y usuario B edita primero
And usuario A intenta guardar
Then sistema rechaza cambios con error de concurrencia
And row_version sigue en 6 (incrementado por usuario B)
```

---

### PAC-04 Fusionar pacientes (merge)
- **Actor principal:** Practitioner, Admin
- **Actores secundarios:** Ninguno
- **Precondiciones:** Dos pacientes existen, identificados como duplicados
- **Disparador:** Se detectan pacientes duplicados en el sistema

**Flujo principal:**
1. Usuario identifica paciente duplicado (Patient A) y paciente principal (Patient B)
2. Usuario selecciona "Fusionar pacientes"
3. Sistema muestra comparación lado a lado de ambos pacientes
4. Usuario confirma: Patient A se fusionará en Patient B
5. Usuario ingresa merge_reason (ej: "Registro duplicado por error de recepción")
6. Sistema actualiza Patient A:
   - is_merged = true
   - merged_into_patient_id = Patient B.id
   - merge_reason = texto ingresado
7. Sistema mantiene Patient A en base de datos (NO hard delete)
8. Sistema redirige todos los futuros accesos de Patient A a Patient B

**Flujos alternativos / errores:**
- Si Patient A tiene encounters/photos: advertir que se mantendrán vinculados a Patient A (no se migran automáticamente en v1)
- Si Patient B ya está merged: error "No se puede fusionar en un paciente que ya está fusionado"
- Si merge_reason vacío: requerir razón obligatoria

**Datos creados/actualizados:**
- **Patient A:** is_merged=true, merged_into_patient_id=Patient B.id, merge_reason, updated_at

**Reglas de negocio:**
- Merge es unidireccional (A → B)
- Patient A nunca se elimina (hard delete prohibido)
- Encounters/Photos/Consents de Patient A se mantienen vinculados a Patient A
- Búsquedas por Patient A deben redirigir a Patient B
- No se permite merge en cadena (A→B→C prohibido, solo A→B)

**Auditoría/seguridad:**
- Merge se audita con actor_user_id, timestamp, y merge_reason
- Solo Practitioner y Admin pueden hacer merge
- Reception NO puede hacer merge

**Criterios de aceptación:**
```gherkin
Given Patient A (duplicado) y Patient B (principal)
When practitioner fusiona A en B con merge_reason="Email duplicado"
Then Patient A.is_merged=true
And Patient A.merged_into_patient_id=Patient B.id
And búsquedas de Patient A redirigen a Patient B
And encounters de Patient A siguen vinculados a Patient A
```

---

### PAC-05 Gestionar tutor legal de menor
- **Actor principal:** Reception, Practitioner
- **Actores secundarios:** Admin
- **Precondiciones:** Patient existe y es menor de edad
- **Disparador:** Paciente menor necesita registro de tutor legal

**Flujo principal:**
1. Usuario abre perfil del paciente menor
2. Usuario selecciona "Agregar tutor legal"
3. Usuario ingresa full_name del tutor
4. Usuario ingresa relationship (madre|padre|tutor legal|otro)
5. Usuario ingresa phone, email opcionales
6. Usuario ingresa address del tutor si difiere del paciente
7. Sistema crea PatientGuardian vinculado a Patient
8. Sistema registra created_at

**Flujos alternativos / errores:**
- Si paciente es mayor de edad: advertir pero permitir (puede tener tutor por discapacidad)
- Si se intenta eliminar último tutor de un menor: advertir
- Editar tutor: modificar datos y actualizar updated_at

**Datos creados/actualizados:**
- **PatientGuardian:** id, patient_id, full_name, relationship, phone, email, address_line1, city, postal_code, country_code, created_at, updated_at

**Reglas de negocio:**
- Un paciente puede tener múltiples tutores (ej: ambos padres)
- Relationship es texto libre pero se sugieren valores comunes
- PatientGuardian se elimina si Patient se soft-delete (CASCADE)

**Auditoría/seguridad:**
- Datos de tutores son sensibles (GDPR/HIPAA)
- Solo personal autorizado puede ver/editar tutores
- Cambios en tutores se auditan

**Criterios de aceptación:**
```gherkin
Given Patient menor de 18 años
When usuario agrega tutor con full_name="María Pérez" y relationship="Madre"
Then PatientGuardian se crea vinculado a Patient
And patient.guardians contiene el nuevo tutor
```

---

## AGD: Gestión de Agenda

### AGD-01 Crear cita manual
- **Actor principal:** Reception
- **Actores secundarios:** Practitioner, Admin
- **Precondiciones:** Usuario autenticado
- **Disparador:** Paciente llama o llega para agendar cita

**Flujo principal:**
1. Usuario selecciona "Nueva cita manual"
2. Usuario busca y selecciona patient_id (puede ser null si paciente nuevo aún no registrado)
3. Usuario selecciona practitioner_id
4. Usuario selecciona location_id (clinic_location)
5. Usuario ingresa scheduled_start (fecha y hora inicio)
6. Usuario ingresa scheduled_end (fecha y hora fin)
7. Usuario ingresa notes opcionales
8. Sistema asigna source='manual'
9. Sistema asigna status='scheduled'
10. Sistema asigna external_id=null
11. Sistema guarda Appointment
12. Sistema registra created_at

**Flujos alternativos / errores:**
- Si scheduled_start >= scheduled_end: error de validación
- Si practitioner no disponible (conflicto de horario): advertir pero permitir
- Si patient_id es null: permitir (cita sin paciente asignado aún)

**Datos creados/actualizados:**
- **Appointment:** id, patient_id (nullable), practitioner_id (nullable), location_id (nullable), encounter_id=null, source='manual', external_id=null, status='scheduled', scheduled_start, scheduled_end, notes, created_at, updated_at

**Reglas de negocio:**
- source='manual' indica creación manual (no Calendly)
- external_id=null para citas manuales
- patient_id puede ser null inicialmente y asignarse después
- Citas manuales pueden editarse libremente

**Auditoría/seguridad:**
- created_at registra cuándo se creó la cita
- Cambios de status se auditan

**Criterios de aceptación:**
```gherkin
Given usuario reception
When crea cita manual para practitioner X el 2025-12-15 10:00-11:00
Then Appointment se guarda con source='manual'
And status='scheduled'
And external_id=null
```

---

### AGD-02 Importar/sincronizar cita desde Calendly
- **Actor principal:** Sistema (webhook/sincronización automática)
- **Actores secundarios:** Admin (configuración)
- **Precondiciones:** Integración Calendly configurada
- **Disparador:** Evento webhook de Calendly (created, rescheduled, canceled)

**Flujo principal:**
1. Sistema recibe webhook de Calendly con event_type y event_uri
2. Sistema extrae external_id del evento (Calendly event ID)
3. Sistema busca Appointment con external_id=Calendly event ID
4. **Si NO existe:** Sistema crea nuevo Appointment
   - source='calendly'
   - external_id=Calendly event ID
   - scheduled_start/end desde Calendly
   - status='scheduled'
   - patient_id=null inicialmente (vincular después)
5. **Si existe:** Sistema actualiza Appointment existente
   - scheduled_start/end si cambiaron (reschedule)
   - status='cancelled' si evento cancelado en Calendly
   - cancellation_reason="Cancelado en Calendly"
6. Sistema registra updated_at

**Flujos alternativos / errores:**
- Si webhook signature inválido: rechazar (seguridad)
- Si external_id duplicado: error crítico (no debería pasar)
- Si Calendly envía evento desconocido: log y skip

**Datos creados/actualizados:**
- **Appointment:** id, source='calendly', external_id, status, scheduled_start, scheduled_end, cancellation_reason (si aplica), created_at, updated_at

**Reglas de negocio:**
- external_id debe ser UNIQUE (garantiza no duplicados)
- source='calendly' NO permite edición manual de horarios (solo en Calendly)
- Cancelaciones en Calendly marcan status='cancelled' automáticamente
- patient_id se asigna manualmente después de identificar al paciente

**Auditoría/seguridad:**
- Webhooks Calendly se validan con signature
- Cambios desde Calendly se auditan con metadata_json

**Criterios de aceptación:**
```gherkin
Given webhook Calendly con event_type="created" y external_id="CAL123"
When sistema procesa webhook
Then Appointment se crea con source='calendly'
And external_id='CAL123'
And status='scheduled'

Given Appointment existente con external_id='CAL123'
When webhook Calendly con event_type="canceled"
Then Appointment.status='cancelled'
And cancellation_reason="Cancelado en Calendly"
```

---

### AGD-03 Confirmar cita
- **Actor principal:** Reception
- **Actores secundarios:** Practitioner
- **Precondiciones:** Appointment existe con status='scheduled'
- **Disparador:** Paciente confirma asistencia (por teléfono, SMS, etc.)

**Flujo principal:**
1. Usuario abre appointment
2. Usuario selecciona "Confirmar cita"
3. Sistema cambia status='scheduled' → 'confirmed'
4. Sistema actualiza updated_at
5. Sistema guarda cambios

**Flujos alternativos / errores:**
- Si status ya es 'confirmed': no hacer nada
- Si status es 'cancelled' o 'no_show': error "No se puede confirmar cita cancelada/no show"

**Datos creados/actualizados:**
- **Appointment:** status='confirmed', updated_at

**Reglas de negocio:**
- Solo citas 'scheduled' pueden pasar a 'confirmed'
- Confirmación no es obligatoria (cita puede pasar de 'scheduled' a 'attended' directamente)

**Auditoría/seguridad:**
- Cambio de status se audita con usuario y timestamp

**Criterios de aceptación:**
```gherkin
Given Appointment con status='scheduled'
When reception confirma cita
Then status='confirmed'
And updated_at se actualiza
```

---

### AGD-04 Marcar No Show / Cancelar con razón
- **Actor principal:** Reception, Practitioner
- **Actores secundarios:** Admin
- **Precondiciones:** Appointment existe
- **Disparador:** Paciente no asiste o cancela cita

**Flujo principal (No Show):**
1. Usuario abre appointment después de hora agendada
2. Usuario selecciona "Marcar como No Show"
3. Usuario ingresa no_show_reason (ej: "No contestó llamada de confirmación")
4. Sistema cambia status='no_show'
5. Sistema guarda no_show_reason
6. Sistema actualiza updated_at

**Flujo principal (Cancelar):**
1. Usuario abre appointment
2. Usuario selecciona "Cancelar cita"
3. Usuario ingresa cancellation_reason (ej: "Paciente enfermo, reprogramar")
4. Sistema cambia status='cancelled'
5. Sistema guarda cancellation_reason
6. Sistema actualiza updated_at

**Flujos alternativos / errores:**
- Si status ya es 'attended': advertir "Cita ya fue atendida, ¿seguro cancelar?"
- Si cancellation_reason o no_show_reason vacío: requerir razón

**Datos creados/actualizados:**
- **Appointment:** status='no_show' o 'cancelled', no_show_reason o cancellation_reason, updated_at

**Reglas de negocio:**
- No show y cancelación son estados finales (no se puede reactivar)
- Razón es obligatoria para auditoría
- Citas Calendly canceladas en Calendly ya tienen cancellation_reason="Cancelado en Calendly"

**Auditoría/seguridad:**
- Cambios de status se auditan
- Razones se almacenan para análisis de no-shows

**Criterios de aceptación:**
```gherkin
Given Appointment con status='confirmed' y scheduled_start pasado
When reception marca No Show con no_show_reason="No asistió"
Then status='no_show'
And no_show_reason guardado
And updated_at actualizado

Given Appointment con status='scheduled'
When reception cancela con cancellation_reason="Paciente enfermo"
Then status='cancelled'
And cancellation_reason guardado
```

---

### AGD-05 Vincular cita a encounter
- **Actor principal:** Practitioner, Reception
- **Actores secundarios:** Admin
- **Precondiciones:** Appointment existe, Encounter existe o se va a crear
- **Disparador:** Paciente asiste a cita y se crea encounter

**Flujo principal:**
1. Usuario marca Appointment como status='attended'
2. Usuario selecciona "Crear encounter desde cita"
3. Sistema crea Encounter con:
   - patient_id desde Appointment.patient_id
   - practitioner_id desde Appointment.practitioner_id
   - location_id desde Appointment.location_id
   - occurred_at = Appointment.scheduled_start
   - type y status según tipo de visita
4. Sistema asigna Appointment.encounter_id = nuevo Encounter.id
5. Sistema guarda ambos registros

**Flujos alternativos / errores:**
- Si Appointment.patient_id es null: error "Asignar paciente antes de crear encounter"
- Si encounter_id ya asignado: mostrar encounter existente (no crear duplicado)
- Si usuario prefiere: puede vincular a encounter existente en lugar de crear nuevo

**Datos creados/actualizados:**
- **Appointment:** status='attended', encounter_id (FK), updated_at
- **Encounter:** (nuevo registro completo)

**Reglas de negocio:**
- Vinculación es opcional (puede haber Appointment sin encounter_id)
- Un Appointment puede tener máximo 1 Encounter
- Un Encounter puede tener múltiples Appointments (ej: cita inicial + seguimientos)

**Auditoría/seguridad:**
- Vinculación se audita
- Encounter hereda practitioner y location de Appointment si no se especifica

**Criterios de aceptación:**
```gherkin
Given Appointment con patient_id=X, practitioner_id=Y, status='confirmed'
When usuario marca 'attended' y crea encounter
Then Appointment.status='attended'
And Appointment.encounter_id apunta a nuevo Encounter
And Encounter.patient_id=X
And Encounter.practitioner_id=Y
```

---

## ENC: Gestión de Encounters (Visitas)

### ENC-01 Crear encounter (draft)
- **Actor principal:** Practitioner
- **Actores secundarios:** Reception (solo crear, no editar contenido clínico)
- **Precondiciones:** Patient existe
- **Disparador:** Paciente tiene consulta/procedimiento

**Flujo principal:**
1. Usuario abre perfil del paciente
2. Usuario selecciona "Nueva visita"
3. Usuario selecciona type (medical_consult|cosmetic_consult|aesthetic_procedure|follow_up|sale_only)
4. Usuario selecciona practitioner_id (puede ser el mismo usuario si es practitioner)
5. Usuario selecciona location_id
6. Usuario ingresa occurred_at (fecha y hora de la visita, default=ahora)
7. Usuario ingresa chief_complaint (motivo de consulta)
8. Usuario ingresa assessment (evaluación) opcional en draft
9. Usuario ingresa plan (plan de tratamiento) opcional en draft
10. Usuario ingresa internal_notes opcional
11. Sistema asigna status='draft'
12. Sistema asigna row_version=1
13. Sistema registra created_by_user_id
14. Sistema guarda Encounter

**Flujos alternativos / errores:**
- Si occurred_at es futuro: advertir pero permitir (cita agendada pre-documentada)
- Si patient_id inválido: error de validación

**Datos creados/actualizados:**
- **Encounter:** id, patient_id, practitioner_id, location_id, type, status='draft', occurred_at, chief_complaint, assessment, plan, internal_notes, row_version=1, created_by_user_id, created_at, updated_at

**Reglas de negocio:**
- Encounter en 'draft' puede editarse libremente
- chief_complaint es obligatorio
- assessment y plan son opcionales en draft, obligatorios para finalizar
- row_version permite control de concurrencia

**Auditoría/seguridad:**
- created_by_user_id registra quién creó el encounter
- Encounters son datos clínicos sensibles (HIPAA/GDPR)
- Solo Practitioner puede editar contenido clínico

**Criterios de aceptación:**
```gherkin
Given practitioner autenticado
When crea encounter para Patient X con type='medical_consult'
Then Encounter se guarda con status='draft'
And row_version=1
And created_by_user_id=practitioner actual
```

---

### ENC-02 Finalizar encounter
- **Actor principal:** Practitioner
- **Actores secundarios:** Ninguno
- **Precondiciones:** Encounter existe con status='draft'
- **Disparador:** Practitioner termina documentación de visita

**Flujo principal:**
1. Usuario abre Encounter en 'draft'
2. Usuario completa assessment (obligatorio)
3. Usuario completa plan (obligatorio)
4. Usuario adjunta fotos clínicas si aplica (ver PHO-02)
5. Usuario adjunta documentos si aplica (ver DOC-02)
6. Usuario selecciona "Finalizar encounter"
7. Sistema valida que assessment y plan no estén vacíos
8. Sistema cambia status='draft' → 'finalized'
9. Sistema incrementa row_version
10. Sistema actualiza updated_at
11. Sistema guarda cambios

**Flujos alternativos / errores:**
- Si assessment o plan vacíos: error "Completar evaluación y plan antes de finalizar"
- Si otro usuario editó (row_version cambió): error de concurrencia
- Si status ya es 'finalized': advertir "Encounter ya finalizado, crear corrección" (vNext)

**Datos creados/actualizados:**
- **Encounter:** status='finalized', row_version (incrementado), updated_at

**Reglas de negocio:**
- Encounter 'finalized' NO puede editarse (inmutable en v1)
- En vNext: firma digital con signed_at y signed_by_user_id
- Finalizar encounter es acción irreversible en v1

**Auditoría/seguridad:**
- Finalización se audita con usuario y timestamp
- Encounter finalizado es evidencia médico-legal
- Cambios post-finalización requieren encounter de corrección (vNext)

**Criterios de aceptación:**
```gherkin
Given Encounter con status='draft' y assessment/plan completos
When practitioner finaliza encounter
Then status='finalized'
And row_version incrementado
And encounter NO puede editarse
```

---

### ENC-03 Ver timeline del paciente
- **Actor principal:** Practitioner
- **Actores secundarios:** Admin, Reception (vista limitada)
- **Precondiciones:** Patient existe
- **Disparador:** Usuario necesita ver historial completo del paciente

**Flujo principal:**
1. Usuario abre perfil del paciente
2. Usuario selecciona "Timeline / Historial"
3. Sistema recupera y ordena cronológicamente (descendente):
   - Encounters (con type, occurred_at, practitioner, status)
   - ClinicalPhotos (con taken_at, photo_kind, clinical_context)
   - Appointments (con scheduled_start, status)
   - Consents (con granted_at, revoked_at, consent_type, status)
   - Documents adjuntos a encounters (con created_at, kind)
4. Sistema muestra timeline unificada con iconos por tipo
5. Usuario puede filtrar por tipo (solo encounters, solo fotos, etc.)
6. Usuario puede expandir cada item para ver detalles

**Flujos alternativos / errores:**
- Si patient is_deleted=true: mostrar timeline en modo read-only
- Si patient is_merged=true: redirigir a merged_into_patient timeline
- Reception NO ve contenido clínico de encounters (solo fechas y tipo)

**Datos creados/actualizados:**
- Ninguno (solo lectura)

**Reglas de negocio:**
- Timeline es cronológica inversa (más reciente primero)
- Encounters soft-deleted (is_deleted=true) NO aparecen
- ClinicalPhotos soft-deleted NO aparecen
- Timeline incluye eventos de todas las locations

**Auditoría/seguridad:**
- Acceso a timeline se audita (quién vio el historial de quién)
- Practitioner ve todo
- Reception NO ve assessment/plan de encounters
- Marketing NO tiene acceso

**Criterios de aceptación:**
```gherkin
Given Patient con 2 encounters, 3 fotos, 1 consent
When practitioner ve timeline
Then timeline muestra 6 eventos ordenados por fecha
And puede filtrar solo encounters
And puede expandir encounter para ver assessment/plan

Given mismo Patient
When reception ve timeline
Then NO ve assessment/plan de encounters
And solo ve fechas y tipo de visita
```

---

## CON: Gestión de Consentimientos

### CON-01 Registrar consentimiento (grant)
- **Actor principal:** Reception, Practitioner
- **Actores secundarios:** Admin
- **Precondiciones:** Patient existe
- **Disparador:** Paciente firma consentimiento físico o digital

**Flujo principal:**
1. Usuario abre perfil del paciente
2. Usuario selecciona "Nuevo consentimiento"
3. Usuario selecciona consent_type (clinical_photos|marketing_photos|newsletter|marketing_messages)
4. Usuario ingresa granted_at (fecha y hora de firma, default=ahora)
5. Usuario opcionalmente adjunta document_id (PDF escaneado del consentimiento firmado)
6. Sistema asigna status='granted'
7. Sistema asigna revoked_at=null
8. Sistema guarda Consent

**Flujos alternativos / errores:**
- Si ya existe Consent del mismo tipo con status='granted': advertir "Ya existe consentimiento activo, ¿revocar anterior?"
- Si document_id inválido: error de validación
- Si consent_type inválido: error de validación

**Datos creados/actualizados:**
- **Consent:** id, patient_id, consent_type, status='granted', granted_at, revoked_at=null, document_id (nullable), created_at, updated_at

**Reglas de negocio:**
- Un paciente puede tener múltiples Consents del mismo tipo (si revoca y vuelve a dar)
- Solo último Consent de cada tipo con status='granted' es válido
- document_id vincula a Document (PDF escaneado o generado)
- Consents son críticos para GDPR/HIPAA

**Auditoría/seguridad:**
- Consents se auditan estrictamente (quién registró, cuándo)
- Marketing solo puede ver consents de marketing_photos y newsletter
- Practitioner y Reception ven todos los consents

**Criterios de aceptación:**
```gherkin
Given Patient sin consents previos
When reception registra consent_type='clinical_photos'
Then Consent se guarda con status='granted'
And revoked_at=null
And granted_at=timestamp actual

Given Patient con Consent clinical_photos status='granted'
When se registra otro clinical_photos
Then sistema advierte duplicado
And permite continuar (revocar anterior automáticamente en vNext)
```

---

### CON-02 Revocar consentimiento
- **Actor principal:** Practitioner, Reception
- **Actores secundarios:** Admin
- **Precondiciones:** Consent existe con status='granted'
- **Disparador:** Paciente retira consentimiento

**Flujo principal:**
1. Usuario abre perfil del paciente
2. Usuario selecciona Consent activo
3. Usuario selecciona "Revocar consentimiento"
4. Usuario confirma acción (advertencia legal)
5. Sistema cambia status='granted' → 'revoked'
6. Sistema asigna revoked_at=timestamp actual
7. Sistema actualiza updated_at
8. Sistema guarda cambios

**Flujos alternativos / errores:**
- Si status ya es 'revoked': error "Consentimiento ya revocado"
- Si consent_type='clinical_photos' y existen fotos: advertir "Fotos clínicas quedan bajo protección legal pero no para uso marketing"

**Datos creados/actualizados:**
- **Consent:** status='revoked', revoked_at, updated_at

**Reglas de negocio:**
- Revocación es irreversible (crear nuevo Consent si paciente vuelve a dar permiso)
- Si consent_type='marketing_photos': fotos clínicas NO pueden usarse en marketing
- Si consent_type='newsletter': paciente sale de lista de emails
- Revocación debe procesarse inmediatamente (GDPR compliance)

**Auditoría/seguridad:**
- Revocación se audita con usuario y timestamp
- Sistema debe respetar revocación en todas las integraciones (email, social media)

**Criterios de aceptación:**
```gherkin
Given Consent con consent_type='newsletter' y status='granted'
When practitioner revoca consentimiento
Then status='revoked'
And revoked_at=timestamp actual
And paciente sale de lista de newsletter
```

---

### CON-03 Ver estado de consentimientos por paciente
- **Actor principal:** Practitioner, Reception
- **Actores secundarios:** Marketing (solo consents de marketing)
- **Precondiciones:** Patient existe
- **Disparador:** Usuario necesita verificar permisos del paciente

**Flujo principal:**
1. Usuario abre perfil del paciente
2. Usuario selecciona "Consentimientos"
3. Sistema muestra tabla con todos los consent_types posibles
4. Sistema indica para cada tipo:
   - Status actual (granted|revoked|sin registro)
   - granted_at si status='granted'
   - revoked_at si status='revoked'
   - document_id si existe
5. Sistema resalta en verde consents granted, en rojo revoked, en gris sin registro

**Flujos alternativos / errores:**
- Si múltiples Consents del mismo tipo: mostrar solo el más reciente
- Si usuario es Marketing: solo mostrar marketing_photos y newsletter

**Datos creados/actualizados:**
- Ninguno (solo lectura)

**Reglas de negocio:**
- Vista muestra estado actual, no historial completo (historial en vNext)
- consents críticos para operaciones legales (marketing, fotos, emails)

**Auditoría/seguridad:**
- Consulta de consents se audita
- Marketing NO ve consents clínicos

**Criterios de aceptación:**
```gherkin
Given Patient con consent clinical_photos='granted' y newsletter='revoked'
When practitioner ve consentimientos
Then clinical_photos muestra verde con granted_at
And newsletter muestra rojo con revoked_at
And marketing_photos muestra gris (sin registro)

Given mismo Patient
When marketing ve consentimientos
Then NO ve clinical_photos
And solo ve newsletter y marketing_photos
```

---

## PHO: Gestión de Fotos Clínicas

### PHO-01 Subir foto clínica a paciente (sin encounter)
- **Actor principal:** Practitioner
- **Actores secundarios:** Admin
- **Precondiciones:** Patient existe, usuario puede acceder a bucket "clinical"
- **Disparador:** Practitioner toma foto clínica del paciente

**Flujo principal:**
1. Usuario abre perfil del paciente
2. Usuario selecciona "Subir foto clínica"
3. Usuario selecciona archivo de imagen desde dispositivo
4. Usuario ingresa metadata:
   - photo_kind (clinical|before|after)
   - clinical_context (baseline|follow_up|post_procedure|other) opcional
   - body_area opcional
   - notes opcional
   - taken_at (default=ahora)
   - source_device opcional
5. Sistema valida formato (JPEG, PNG, HEIC)
6. Sistema genera object_key único en bucket "clinical" (ej: "patient_UUID/YYYYMMDD_HHmmss_UUID.jpg")
7. Sistema sube archivo a MinIO bucket "clinical"
8. Sistema calcula sha256 hash del archivo
9. Sistema genera thumbnail_object_key async (vNext)
10. Sistema asigna storage_bucket='clinical' (fixed, not editable)
11. Sistema asigna visibility='clinical_only' (default)
12. Sistema registra created_by_user_id
13. Sistema guarda ClinicalPhoto

**Flujos alternativos / errores:**
- Si archivo > 50MB: error "Archivo muy grande"
- Si formato inválido: error "Solo JPEG, PNG, HEIC"
- Si upload a MinIO falla: error "Error de almacenamiento, reintentar"

**Datos creados/actualizados:**
- **ClinicalPhoto:** id, patient_id, taken_at, photo_kind, clinical_context, body_area, notes, source_device, storage_bucket='clinical', object_key, thumbnail_object_key (nullable), content_type, size_bytes, sha256, visibility='clinical_only', created_by_user_id, created_at, updated_at

**Reglas de negocio:**
- ClinicalPhoto es INMUTABLE (no se puede editar object_key ni archivo)
- storage_bucket SIEMPRE es "clinical" (separación estricta de buckets)
- sha256 permite verificación de integridad
- Foto puede existir sin estar vinculada a ningún Encounter
- visibility='clinical_only' en v1 (marketing visibility en vNext requiere consent)

**Auditoría/seguridad:**
- Subida se audita con created_by_user_id
- Bucket "clinical" es PRIVADO (no público)
- Solo Practitioner y Admin pueden subir fotos clínicas
- Reception NO puede subir fotos clínicas

**Criterios de aceptación:**
```gherkin
Given practitioner autenticado
When sube foto JPEG de 2MB para Patient X
Then ClinicalPhoto se crea con storage_bucket='clinical'
And object_key único en formato patient_UUID/timestamp_UUID.jpg
And sha256 calculado
And visibility='clinical_only'
And foto NO está vinculada a encounter (encounter_photos vacío)
```

---

### PHO-02 Adjuntar foto a encounter
- **Actor principal:** Practitioner
- **Actores secundarios:** Admin
- **Precondiciones:** ClinicalPhoto existe, Encounter existe
- **Disparador:** Practitioner documenta visita con fotos

**Flujo principal:**
1. Usuario abre Encounter en 'draft'
2. Usuario selecciona "Adjuntar fotos"
3. Sistema muestra fotos del paciente (patient_id coincide)
4. Usuario selecciona una o más ClinicalPhotos
5. Usuario selecciona relation_type para cada foto (attached|comparison)
6. Sistema crea EncounterPhoto para cada foto seleccionada
7. Sistema valida unique_together (encounter, photo) - no duplicados
8. Sistema guarda EncounterPhotos

**Flujos alternativos / errores:**
- Si foto ya adjunta al encounter: error "Foto ya adjunta, cambiar relation_type si es necesario"
- Si encounter status='finalized': error "No se pueden adjuntar fotos a encounter finalizado"
- Usuario puede subir nueva foto Y adjuntarla en un solo flujo

**Datos creados/actualizados:**
- **EncounterPhoto:** encounter_id, photo_id, relation_type

**Reglas de negocio:**
- Una ClinicalPhoto puede adjuntarse a múltiples Encounters (M:N)
- relation_type='attached': foto tomada en esta visita
- relation_type='comparison': foto de visita anterior usada para comparación
- No hay CASCADE delete: eliminar Encounter NO elimina fotos

**Auditoría/seguridad:**
- Vinculación se audita
- Solo Practitioner puede adjuntar fotos a encounters

**Criterios de aceptación:**
```gherkin
Given ClinicalPhoto A y Encounter E1
When practitioner adjunta foto A a E1 con relation_type='attached'
Then EncounterPhoto se crea vinculando A y E1
And unique_together garantiza no duplicados

Given ClinicalPhoto B ya adjunta a E1
When practitioner intenta adjuntar B a E1 nuevamente
Then sistema rechaza con error duplicado
```

---

### PHO-03 Asociar foto a múltiples encounters como comparación
- **Actor principal:** Practitioner
- **Actores secundarios:** Admin
- **Precondiciones:** ClinicalPhoto existe, múltiples Encounters del mismo Patient existen
- **Disparador:** Practitioner quiere comparar evolución del paciente

**Flujo principal:**
1. Usuario abre Encounter E2 (visita de seguimiento)
2. Usuario selecciona "Comparar con visitas anteriores"
3. Sistema muestra encounters previos del paciente
4. Usuario selecciona Encounter E1 (visita anterior)
5. Sistema muestra fotos de E1
6. Usuario selecciona ClinicalPhoto B de E1
7. Usuario selecciona "Usar como comparación en visita actual"
8. Sistema crea EncounterPhoto(encounter=E2, photo=B, relation_type='comparison')
9. Sistema guarda vinculación

**Flujos alternativos / errores:**
- Si foto B ya adjunta a E2: error duplicado
- Usuario puede adjuntar múltiples fotos de comparación

**Datos creados/actualizados:**
- **EncounterPhoto:** encounter_id=E2, photo_id=B, relation_type='comparison'

**Reglas de negocio:**
- Foto de Encounter E1 puede usarse como comparison en E2, E3, E4, etc.
- relation_type='comparison' indica foto NO tomada en esta visita
- Facilita before/after tracking

**Auditoría/seguridad:**
- Vinculación se audita
- Solo Practitioner puede crear comparaciones

**Criterios de aceptación:**
```gherkin
Given ClinicalPhoto B adjunta a Encounter E1 con relation_type='attached'
When practitioner crea Encounter E2 (seguimiento)
And adjunta foto B a E2 con relation_type='comparison'
Then foto B aparece en ambos encounters
And E1 muestra B como 'attached'
And E2 muestra B como 'comparison'
```

---

### PHO-04 Listar fotos del paciente con filtros
- **Actor principal:** Practitioner
- **Actores secundarios:** Admin
- **Precondiciones:** Patient existe
- **Disparador:** Usuario necesita ver fotos clínicas del paciente

**Flujo principal:**
1. Usuario abre perfil del paciente
2. Usuario selecciona "Fotos clínicas"
3. Sistema lista ClinicalPhotos del paciente ordenadas por taken_at desc
4. Sistema muestra thumbnails (thumbnail_object_key si existe)
5. Usuario puede filtrar por:
   - photo_kind (clinical|before|after)
   - clinical_context (baseline|follow_up|post_procedure|other)
   - Rango de fechas (taken_at)
   - body_area
6. Usuario puede ordenar por taken_at asc/desc
7. Usuario selecciona foto para ver full-size

**Flujos alternativos / errores:**
- Si no hay fotos: mostrar "Sin fotos clínicas"
- Si is_deleted=true: NO mostrar (soft delete)
- Usuario puede descargar foto original (object_key)

**Datos creados/actualizados:**
- Ninguno (solo lectura)

**Reglas de negocio:**
- Solo fotos con is_deleted=false aparecen
- Thumbnails cargan async para performance
- Full-size requiere presigned URL de MinIO (vNext)

**Auditoría/seguridad:**
- Acceso a fotos se audita
- Solo Practitioner y Admin ven fotos clínicas
- Reception NO ve fotos clínicas

**Criterios de aceptación:**
```gherkin
Given Patient con 5 fotos: 3 'before', 2 'after'
When practitioner filtra por photo_kind='before'
Then lista muestra solo 3 fotos
And ordenadas por taken_at descendente

Given mismo Patient
When reception intenta ver fotos clínicas
Then acceso denegado (permiso insuficiente)
```

---

## DOC: Gestión de Documentos

### DOC-01 Subir documento interno
- **Actor principal:** Practitioner, Reception
- **Actores secundarios:** Admin
- **Precondiciones:** Usuario autenticado, acceso a bucket "documents"
- **Disparador:** Usuario necesita guardar PDF/documento interno

**Flujo principal:**
1. Usuario selecciona "Subir documento"
2. Usuario selecciona archivo (PDF, DOCX, JPEG, PNG, etc.)
3. Usuario ingresa title opcional
4. Sistema valida formato y tamaño (max 100MB)
5. Sistema genera object_key único en bucket "documents" (ej: "documents/YYYY/MM/UUID.pdf")
6. Sistema sube archivo a MinIO bucket "documents"
7. Sistema calcula sha256 hash
8. Sistema asigna storage_bucket='documents' (fixed)
9. Sistema registra created_by_user_id
10. Sistema guarda Document

**Flujos alternativos / errores:**
- Si archivo > 100MB: error "Archivo muy grande"
- Si upload falla: error "Error de almacenamiento, reintentar"
- Si content_type inválido: advertir pero permitir

**Datos creados/actualizados:**
- **Document:** id, storage_bucket='documents', object_key, content_type, size_bytes, sha256, title (nullable), created_by_user_id, created_at, updated_at

**Reglas de negocio:**
- storage_bucket SIEMPRE es "documents" (separación de clinical/marketing/documents)
- Document es genérico (consentimientos, resultados de laboratorio, instrucciones, etc.)
- sha256 permite verificación de integridad
- Documento puede existir sin vinculación a Encounter o Consent

**Auditoría/seguridad:**
- Subida se audita con created_by_user_id
- Bucket "documents" es PRIVADO
- Soft delete: is_deleted, deleted_at, deleted_by_user

**Criterios de aceptación:**
```gherkin
Given usuario practitioner
When sube PDF de 5MB con title="Consentimiento firmado"
Then Document se crea con storage_bucket='documents'
And object_key único
And sha256 calculado
And title="Consentimiento firmado"
```

---

### DOC-02 Adjuntar documento a encounter
- **Actor principal:** Practitioner
- **Actores secundarios:** Reception
- **Precondiciones:** Document existe, Encounter existe
- **Disparador:** Usuario vincula documento a visita

**Flujo principal:**
1. Usuario abre Encounter
2. Usuario selecciona "Adjuntar documento"
3. Sistema muestra documentos recientes o permite buscar/subir nuevo
4. Usuario selecciona Document
5. Usuario selecciona kind (consent_copy|lab_result|instruction|other)
6. Sistema crea EncounterDocument
7. Sistema valida unique_together (encounter, document)
8. Sistema guarda vinculación

**Flujos alternativos / errores:**
- Si documento ya adjunto: error "Documento ya adjunto"
- Si encounter status='finalized': permitir adjuntar (documentos pueden agregarse post-finalización)
- Usuario puede subir Y adjuntar en un solo flujo

**Datos creados/actualizados:**
- **EncounterDocument:** encounter_id, document_id, kind

**Reglas de negocio:**
- Un Document puede adjuntarse a múltiples Encounters (M:N)
- kind clasifica tipo de documento
- No hay CASCADE delete: eliminar Encounter NO elimina Document

**Auditoría/seguridad:**
- Vinculación se audita
- Solo Practitioner y Reception pueden adjuntar documentos

**Criterios de aceptación:**
```gherkin
Given Document D y Encounter E
When practitioner adjunta D a E con kind='lab_result'
Then EncounterDocument se crea vinculando D y E
And kind='lab_result'

Given Document D ya adjunto a E
When usuario intenta adjuntar D a E nuevamente
Then sistema rechaza con error duplicado
```

---

### DOC-03 Adjuntar documento a consentimiento
- **Actor principal:** Practitioner, Reception
- **Actores secundarios:** Admin
- **Precondiciones:** Document existe (PDF escaneado del consentimiento firmado), Consent existe
- **Disparador:** Usuario sube copia firmada de consentimiento

**Flujo principal:**
1. Usuario abre Consent (ver CON-01)
2. Usuario selecciona "Adjuntar PDF firmado"
3. Sistema permite subir nuevo Document o seleccionar existente
4. Usuario sube/selecciona Document (PDF del consentimiento)
5. Sistema asigna Consent.document_id = Document.id
6. Sistema actualiza Consent.updated_at
7. Sistema guarda cambios

**Flujos alternativos / errores:**
- Si document_id ya asignado: permitir reemplazar (actualizar FK)
- Si Document.content_type no es PDF: advertir pero permitir

**Datos creados/actualizados:**
- **Consent:** document_id (FK), updated_at
- **Document:** (ya existe o se crea)

**Reglas de negocio:**
- Consent.document_id es FK nullable (consentimiento puede ser solo registro sin PDF)
- Un Document puede ser referenciado por múltiples Consents (ej: PDF con múltiples firmas)
- document_id NO es obligatorio pero recomendado para evidencia legal

**Auditoría/seguridad:**
- Vinculación se audita
- PDF de consentimiento es evidencia legal crítica

**Criterios de aceptación:**
```gherkin
Given Consent C sin document_id
When usuario adjunta Document D (PDF firmado)
Then Consent.document_id = D.id
And updated_at se actualiza

Given Consent C con document_id=D1
When usuario reemplaza con D2
Then Consent.document_id = D2.id
And D1 queda disponible para otros usos
```

---

## Decisiones pendientes (vNext)

1. **Firma digital de Encounters:** Implementar signed_at y signed_by_user_id con certificado digital para validez médico-legal (en v1 solo finalized).

2. **Correcciones post-finalización:** Mecanismo para crear Encounter de corrección (addendum) cuando se necesita modificar encounter finalizado, sin editar el original inmutable.

3. **Historial de cambios en Patient:** Tracking completo de cambios en campos críticos (email, phone, address) con usuario y timestamp para auditoría GDPR.

4. **Generación automática de thumbnails:** Procesamiento async de ClinicalPhoto para crear thumbnail_object_key usando Celery task.

5. **Presigned URLs para fotos/documentos:** Generación de URLs temporales firmadas de MinIO para descargar archivos sin exponer credentials.

6. **Búsqueda avanzada de pacientes:** Fuzzy matching en nombres, búsqueda fonética, detección de duplicados automática con sugerencias de merge.

7. **Calendly bidireccional:** No solo importar eventos de Calendly sino también crear/cancelar citas en Calendly desde el ERP.

8. **Consents con versioning:** Historial completo de grants/revokes con timestamps, no solo último estado.

9. **Merge automático de Encounters/Photos:** Al fusionar Patient A en Patient B, migrar automáticamente encounters y fotos (en v1 se mantienen vinculados a Patient A).

10. **Visibility de fotos con consents:** Si Patient tiene consent marketing_photos='granted', permitir visibility='marketing' en ClinicalPhoto (en v1 solo clinical_only).
