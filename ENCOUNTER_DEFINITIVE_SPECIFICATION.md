# Encounter: Especificación Definitiva y Estrategia de Migración

**Fecha**: 2025-01-04  
**Status**: ✅ ANÁLISIS COMPLETO - LISTO PARA DECISIÓN  
**Objetivo**: Definir UNA versión definitiva y coherente de Encounter a nivel DB, backend y API

---

## 1. DIAGNÓSTICO: Estado Actual

### 1.1 Base de Datos (PostgreSQL)

**Tabla**: `encounter` en esquema `public`

```sql
-- ESTRUCTURA ACTUAL (Verificada con \d encounter)
CREATE TABLE encounter (
    id                     uuid PRIMARY KEY NOT NULL,
    type                   character varying(30) NOT NULL,
    status                 character varying(20) NOT NULL,
    occurred_at            timestamp with time zone NOT NULL,
    chief_complaint        text,
    assessment             text,
    plan                   text,
    internal_notes         text,
    signed_at              timestamp with time zone,
    row_version            integer NOT NULL,
    is_deleted             boolean NOT NULL,
    deleted_at             timestamp with time zone,
    created_at             timestamp with time zone NOT NULL,
    updated_at             timestamp with time zone NOT NULL,
    created_by_user_id     uuid,
    deleted_by_user_id     uuid,
    location_id            uuid,
    patient_id             uuid NOT NULL,
    practitioner_id        uuid,
    signed_by_user_id      uuid,
    photo_count_cached     integer NOT NULL,
    document_count_cached  integer NOT NULL,
    has_photos_cached      boolean NOT NULL,
    has_documents_cached   boolean NOT NULL,
    
    -- Foreign Keys
    FOREIGN KEY (created_by_user_id) REFERENCES auth_user(id),
    FOREIGN KEY (deleted_by_user_id) REFERENCES auth_user(id),
    FOREIGN KEY (location_id) REFERENCES clinic_location(id),
    FOREIGN KEY (patient_id) REFERENCES patient(id),
    FOREIGN KEY (practitioner_id) REFERENCES practitioner(id),
    FOREIGN KEY (signed_by_user_id) REFERENCES auth_user(id)
);

-- Indexes
CREATE INDEX encounter_patient_id_e5436902 ON encounter(patient_id);
CREATE INDEX encounter_practitioner_id_8db6d511 ON encounter(practitioner_id);
CREATE INDEX idx_encounter_deleted ON encounter(is_deleted);
CREATE INDEX idx_encounter_occurred_at ON encounter(occurred_at);
CREATE INDEX idx_encounter_patient ON encounter(patient_id);
CREATE INDEX idx_encounter_patient_timeline ON encounter(patient_id, created_at DESC);
CREATE INDEX idx_encounter_practitioner ON encounter(practitioner_id);
CREATE INDEX idx_encounter_status ON encounter(status);
```

**✅ VALIDADO**: El tipo de ID es **UUID**, NO bigint. No hay inconsistencia de tipo.

**Registros actuales**: `0 rows` (base vacía en DEV)

### 1.2 Backend (Django Model)

**Archivo**: `apps/api/apps/clinical/models.py`

```python
class Encounter(models.Model):
    """
    Clinical encounter (consultation, follow-up, procedure).
    Core clinical entity for patient visits.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE, related_name='encounters')
    practitioner = models.ForeignKey('authz.Practitioner', on_delete=models.SET_NULL, null=True, related_name='encounters')
    location = models.ForeignKey('core.ClinicLocation', on_delete=models.SET_NULL, null=True)
    
    # Core fields
    type = models.CharField(max_length=30, choices=EncounterTypeChoices.choices)
    status = models.CharField(max_length=20, choices=EncounterStatusChoices.choices)
    occurred_at = models.DateTimeField()
    
    # Clinical content
    chief_complaint = models.TextField(blank=True)
    assessment = models.TextField(blank=True)
    plan = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    
    # Signature
    signed_at = models.DateTimeField(null=True, blank=True)
    signed_by_user = models.ForeignKey('authz.User', on_delete=models.SET_NULL, null=True, related_name='signed_encounters')
    
    # Concurrency control
    row_version = models.IntegerField(default=0)
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by_user = models.ForeignKey('authz.User', on_delete=models.SET_NULL, null=True, related_name='deleted_encounters')
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by_user = models.ForeignKey('authz.User', on_delete=models.SET_NULL, null=True, related_name='created_encounters')
    
    # Cached counters (denormalized for performance)
    photo_count_cached = models.IntegerField(default=0)
    document_count_cached = models.IntegerField(default=0)
    has_photos_cached = models.BooleanField(default=False)
    has_documents_cached = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'encounter'
        indexes = [
            models.Index(fields=['patient'], name='idx_encounter_patient'),
            models.Index(fields=['practitioner'], name='idx_encounter_practitioner'),
            models.Index(fields=['status'], name='idx_encounter_status'),
            models.Index(fields=['occurred_at'], name='idx_encounter_occurred_at'),
            models.Index(fields=['is_deleted'], name='idx_encounter_deleted'),
            models.Index(fields=['patient', '-created_at'], name='idx_encounter_patient_timeline'),
        ]
```

**✅ COHERENTE**: El modelo Django coincide EXACTAMENTE con la estructura de BD.

### 1.3 Migraciones

**Archivo inicial**: `apps/clinical/migrations/0001_initial.py`

```python
migrations.CreateModel(
    name='Encounter',
    fields=[
        ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
        # ... resto de campos con UUID desde el inicio
    ],
)
```

**✅ DESDE EL ORIGEN**: Encounter se creó con UUID PK desde la migración inicial (0001_initial).

**Migraciones relevantes**:
- `0001_initial.py`: Creación de Encounter con UUID PK
- `0006_encounter_idx_encounter_patient_timeline.py`: Índice compuesto patient+created_at
- `0101_encounter_attachment_counters.py`: Campos denormalizados de contadores

**Total de migraciones**: 17 archivos en `apps/clinical/migrations/`

### 1.4 Serializers (API Contract)

**Archivo**: `apps/api/apps/clinical/serializers.py`

#### EncounterListSerializer

```python
class EncounterListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for GET /api/v1/clinical/encounters/"""
    patient_name = serializers.SerializerMethodField()
    practitioner_name = serializers.SerializerMethodField()
    treatment_count = serializers.SerializerMethodField()
    attachments_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = Encounter
        fields = [
            'id',                    # UUID
            'patient',               # UUID FK
            'patient_name',          # str (computed)
            'practitioner',          # UUID FK
            'practitioner_name',     # str (computed)
            'type',                  # enum
            'status',                # enum
            'occurred_at',           # datetime
            'treatment_count',       # int (computed)
            'attachments_summary',   # dict (computed)
            'created_at',            # datetime
        ]
```

#### EncounterDetailSerializer

```python
class EncounterDetailSerializer(serializers.ModelSerializer):
    """Full serializer for GET /api/v1/clinical/encounters/{id}/"""
    patient = serializers.SerializerMethodField()  # Nested object
    practitioner = serializers.SerializerMethodField()  # Nested object
    encounter_treatments = EncounterTreatmentSerializer(many=True, read_only=True)
    photos = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()
    
    class Meta:
        fields = [
            'id',                    # UUID
            'patient',               # {id, first_name, last_name, email, phone}
            'practitioner',          # {id, display_name, specialty}
            'location',              # UUID FK
            'type',                  # enum
            'status',                # enum
            'occurred_at',           # datetime
            'chief_complaint',       # text
            'assessment',            # text
            'plan',                  # text
            'internal_notes',        # text (RBAC: ClinicalOps only)
            'encounter_treatments',  # Array of treatment objects
            'photos',                # Array with presigned URLs
            'documents',             # Array with presigned URLs
            'signed_at',             # datetime
            'signed_by_user',        # UUID FK
            'row_version',           # int (optimistic locking)
            'created_at',            # datetime
            'updated_at',            # datetime
        ]
```

#### EncounterWriteSerializer

```python
class EncounterWriteSerializer(serializers.ModelSerializer):
    """Write serializer for POST/PATCH /api/v1/clinical/encounters/"""
    encounter_treatments = EncounterTreatmentSerializer(many=True, required=False)
    
    class Meta:
        fields = [
            'id',                    # UUID (read-only on create)
            'patient',               # UUID FK (required)
            'practitioner',          # UUID FK
            'location',              # UUID FK
            'type',                  # enum
            'status',                # enum (transition validation)
            'occurred_at',           # datetime
            'chief_complaint',       # text
            'assessment',            # text
            'plan',                  # text
            'internal_notes',        # text
            'encounter_treatments',  # Nested array (create only)
            'row_version',           # int (required on update)
        ]
```

### 1.5 API Endpoints

**Archivo**: `apps/api/apps/clinical/urls.py`

```python
router.register(r'encounters', EncounterViewSet, basename='encounter')

# Additional nested routes
path('encounters/<uuid:encounter_id>/photos/', ClinicalPhotoViewSet, ...),
path('encounters/<uuid:encounter_id>/documents/', DocumentViewSet, ...),
```

**ViewSet**: `apps/clinical/views.py` → `EncounterViewSet`

**Endpoints activos**:
- `GET /api/v1/clinical/encounters/` → List (EncounterListSerializer)
- `GET /api/v1/clinical/encounters/{id}/` → Detail (EncounterDetailSerializer)
- `POST /api/v1/clinical/encounters/` → Create (EncounterWriteSerializer)
- `PATCH /api/v1/clinical/encounters/{id}/` → Update (EncounterWriteSerializer)
- `DELETE /api/v1/clinical/encounters/{id}/` → Soft delete
- `POST /api/v1/clinical/encounters/{id}/generate-proposal/` → Generate charge proposal

**RBAC**: `EncounterPermission` (Admin, Practitioner, ClinicalOps)

### 1.6 Deprecated Encounter Module

**Archivo**: `apps/api/apps/encounters/models.py`

```python
"""
⚠️ ENCOUNTER REMOVED - USE apps.clinical.models.Encounter ⚠️

This module is DEPRECATED. All Encounter functionality has been
consolidated into the apps.clinical application.

MIGRATION PATH:
- Old: from apps.encounters.models import Encounter
- New: from apps.clinical.models import Encounter
"""
# Only ClinicalMedia remains here (will be moved later)
```

**Status**: Módulo marcado como DEPRECATED, contiene solo ClinicalMedia.

**Endpoint deprecated**: `/api/encounters/` retorna HTTP 410 Gone

### 1.7 Foreign Keys y Referencias

**Tablas que referencian a Encounter**:

```sql
appointment.encounter_id → encounter.id (UUID FK)
clinical_charge_proposal.encounter_id → encounter.id (UUID FK)
encounter_document.encounter_id → encounter.id (UUID FK)
encounter_photo.encounter_id → encounter.id (UUID FK)
encounter_treatment.encounter_id → encounter.id (UUID FK)
skin_photos.encounter_id → encounter.id (UUID FK, SET NULL)
```

**✅ TODOS UUID**: No hay inconsistencias de tipo en FKs.

---

## 2. CONCLUSIÓN DEL DIAGNÓSTICO

### ✅ NO HAY PROBLEMA DE TIPO

**HALLAZGO CRÍTICO**: La sospecha inicial de "bigint → UUID" es **FALSA**.

- ✅ Base de datos: `id uuid PRIMARY KEY`
- ✅ Django model: `id = models.UUIDField(primary_key=True)`
- ✅ Migraciones: UUID desde 0001_initial.py
- ✅ Serializers: UUID en todos los endpoints
- ✅ Foreign Keys: Todas las referencias son UUID → UUID

**NO SE REQUIERE MIGRACIÓN DE TIPO**.

### ⚠️ PROBLEMA REAL: Modelo Duplicado (Deprecated)

El verdadero problema es **arquitectónico**, no de tipo:

1. **Dos módulos Django**: `apps.encounters` (deprecated) y `apps.clinical` (activo)
2. **Dos URLs**: `/api/encounters/` (410 Gone) y `/api/v1/clinical/encounters/` (activo)
3. **Confusión en imports**: Código legacy puede importar desde módulo deprecated
4. **Documentación incompleta**: No hay limpieza formal del módulo `encounters`

---

## 3. PROPUESTA: Modelo Definitivo de Encounter

### 3.1 Especificación de Base de Datos

**Tabla definitiva**: `encounter` (sin cambios, ya es correcta)

```sql
CREATE TABLE encounter (
    -- Primary Key
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Relationships (all UUID FKs)
    patient_id             uuid NOT NULL REFERENCES patient(id) ON DELETE CASCADE,
    practitioner_id        uuid NULL REFERENCES practitioner(id) ON DELETE SET NULL,
    location_id            uuid NULL REFERENCES clinic_location(id) ON DELETE SET NULL,
    created_by_user_id     uuid NULL REFERENCES auth_user(id) ON DELETE SET NULL,
    deleted_by_user_id     uuid NULL REFERENCES auth_user(id) ON DELETE SET NULL,
    signed_by_user_id      uuid NULL REFERENCES auth_user(id) ON DELETE SET NULL,
    
    -- Core Business Fields
    type                   varchar(30) NOT NULL CHECK (type IN ('initial_consult', 'follow_up', 'procedure', 'emergency', 'other')),
    status                 varchar(20) NOT NULL CHECK (status IN ('draft', 'finalized', 'cancelled')),
    occurred_at            timestamptz NOT NULL,
    
    -- Clinical Content
    chief_complaint        text NULL,
    assessment             text NULL,
    plan                   text NULL,
    internal_notes         text NULL,  -- RBAC: ClinicalOps only
    
    -- Digital Signature
    signed_at              timestamptz NULL,
    
    -- Concurrency Control (Optimistic Locking)
    row_version            integer NOT NULL DEFAULT 0,
    
    -- Soft Delete Pattern
    is_deleted             boolean NOT NULL DEFAULT FALSE,
    deleted_at             timestamptz NULL,
    
    -- Audit Timestamps
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now(),
    
    -- Denormalized Counters (Performance Optimization)
    photo_count_cached     integer NOT NULL DEFAULT 0,
    document_count_cached  integer NOT NULL DEFAULT 0,
    has_photos_cached      boolean NOT NULL DEFAULT FALSE,
    has_documents_cached   boolean NOT NULL DEFAULT FALSE,
    
    -- Constraints
    CHECK (deleted_at IS NULL OR is_deleted = TRUE),
    CHECK (signed_at IS NULL OR signed_by_user_id IS NOT NULL)
);

-- Indexes (Performance-Critical)
CREATE INDEX idx_encounter_patient ON encounter(patient_id) WHERE is_deleted = FALSE;
CREATE INDEX idx_encounter_patient_timeline ON encounter(patient_id, created_at DESC) WHERE is_deleted = FALSE;
CREATE INDEX idx_encounter_practitioner ON encounter(practitioner_id) WHERE is_deleted = FALSE;
CREATE INDEX idx_encounter_status ON encounter(status) WHERE is_deleted = FALSE;
CREATE INDEX idx_encounter_occurred_at ON encounter(occurred_at DESC) WHERE is_deleted = FALSE;
CREATE INDEX idx_encounter_deleted ON encounter(is_deleted);  -- For admin queries
```

**Campos INMUTABLES** (requieren nueva migración para cambiar):
- `id` (UUID)
- `patient_id` (UUID FK, CASCADE)
- `created_at` (timestamptz)
- `created_by_user_id` (UUID FK)

### 3.2 Especificación de Django Model

**Ubicación definitiva**: `apps/api/apps/clinical/models.py`

```python
# apps/clinical/models.py

class EncounterTypeChoices(models.TextChoices):
    """Encounter types"""
    INITIAL_CONSULT = 'initial_consult', 'Initial Consultation'
    FOLLOW_UP = 'follow_up', 'Follow-up Visit'
    PROCEDURE = 'procedure', 'Procedure/Treatment'
    EMERGENCY = 'emergency', 'Emergency Visit'
    OTHER = 'other', 'Other'


class EncounterStatusChoices(models.TextChoices):
    """Encounter status lifecycle"""
    DRAFT = 'draft', 'Draft'
    FINALIZED = 'finalized', 'Finalized'
    CANCELLED = 'cancelled', 'Cancelled'


class Encounter(models.Model):
    """
    Clinical Encounter (patient visit).
    
    Business Rules:
    - Status transitions: draft → finalized|cancelled (terminal states)
    - Practitioner can be NULL (e.g., walk-in without assigned practitioner)
    - internal_notes requires ClinicalOps role (RBAC enforced in serializer)
    - Soft delete preserves audit trail
    - row_version for optimistic locking (concurrent updates)
    
    Related entities:
    - EncounterTreatment (M2M through table)
    - EncounterPhoto (M2M through table)
    - EncounterDocument (M2M through table)
    - ClinicalChargeProposal (1-to-many)
    - Appointment (1-to-1 optional)
    """
    
    # Primary Key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier (UUID v4)"
    )
    
    # Relationships
    patient = models.ForeignKey(
        'Patient',
        on_delete=models.CASCADE,
        related_name='encounters',
        help_text="Patient who attended this encounter"
    )
    practitioner = models.ForeignKey(
        'authz.Practitioner',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='encounters',
        help_text="Practitioner who conducted this encounter"
    )
    location = models.ForeignKey(
        'core.ClinicLocation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Physical location where encounter occurred"
    )
    
    # Core Business Fields
    type = models.CharField(
        max_length=30,
        choices=EncounterTypeChoices.choices,
        help_text="Type of clinical encounter"
    )
    status = models.CharField(
        max_length=20,
        choices=EncounterStatusChoices.choices,
        default=EncounterStatusChoices.DRAFT,
        help_text="Encounter status (draft → finalized|cancelled)"
    )
    occurred_at = models.DateTimeField(
        help_text="Date and time when encounter occurred (timezone-aware)"
    )
    
    # Clinical Content
    chief_complaint = models.TextField(
        blank=True,
        help_text="Patient's main complaint (SOAP: Subjective)"
    )
    assessment = models.TextField(
        blank=True,
        help_text="Clinical assessment and diagnosis (SOAP: Assessment)"
    )
    plan = models.TextField(
        blank=True,
        help_text="Treatment plan (SOAP: Plan)"
    )
    internal_notes = models.TextField(
        blank=True,
        help_text="Internal clinical notes (RBAC: ClinicalOps only)"
    )
    
    # Digital Signature
    signed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when encounter was digitally signed"
    )
    signed_by_user = models.ForeignKey(
        'authz.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='signed_encounters',
        help_text="User who signed this encounter"
    )
    
    # Concurrency Control
    row_version = models.IntegerField(
        default=0,
        help_text="Optimistic locking version (incremented on each update)"
    )
    
    # Soft Delete
    is_deleted = models.BooleanField(
        default=False,
        help_text="Soft delete flag"
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when encounter was soft-deleted"
    )
    deleted_by_user = models.ForeignKey(
        'authz.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deleted_encounters',
        help_text="User who soft-deleted this encounter"
    )
    
    # Audit Trail
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Creation timestamp (immutable)"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last update timestamp"
    )
    created_by_user = models.ForeignKey(
        'authz.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_encounters',
        help_text="User who created this encounter"
    )
    
    # Denormalized Counters (Performance)
    photo_count_cached = models.IntegerField(
        default=0,
        help_text="Cached count of photos (updated by signals)"
    )
    document_count_cached = models.IntegerField(
        default=0,
        help_text="Cached count of documents (updated by signals)"
    )
    has_photos_cached = models.BooleanField(
        default=False,
        help_text="Cached boolean: has at least one photo"
    )
    has_documents_cached = models.BooleanField(
        default=False,
        help_text="Cached boolean: has at least one document"
    )
    
    class Meta:
        db_table = 'encounter'
        verbose_name = 'Encounter'
        verbose_name_plural = 'Encounters'
        ordering = ['-occurred_at', '-created_at']
        indexes = [
            models.Index(fields=['patient'], name='idx_encounter_patient'),
            models.Index(fields=['practitioner'], name='idx_encounter_practitioner'),
            models.Index(fields=['status'], name='idx_encounter_status'),
            models.Index(fields=['occurred_at'], name='idx_encounter_occurred_at'),
            models.Index(fields=['is_deleted'], name='idx_encounter_deleted'),
            models.Index(fields=['patient', '-created_at'], name='idx_encounter_patient_timeline'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(deleted_at__isnull=True) | models.Q(is_deleted=True),
                name='encounter_deleted_at_requires_is_deleted'
            ),
            models.CheckConstraint(
                check=models.Q(signed_at__isnull=True) | models.Q(signed_by_user__isnull=False),
                name='encounter_signed_at_requires_signed_by'
            ),
        ]
    
    def __str__(self):
        return f"Encounter {self.id} - {self.patient} - {self.occurred_at.date()}"
    
    def transition_status(self, new_status, user=None):
        """
        Transition encounter to new status with validation.
        
        Allowed transitions:
        - draft → finalized
        - draft → cancelled
        - finalized → (none, terminal state)
        - cancelled → (none, terminal state)
        
        Raises:
            ValidationError: If transition is invalid
        """
        ALLOWED_TRANSITIONS = {
            EncounterStatusChoices.DRAFT: [
                EncounterStatusChoices.FINALIZED,
                EncounterStatusChoices.CANCELLED
            ],
            EncounterStatusChoices.FINALIZED: [],  # Terminal
            EncounterStatusChoices.CANCELLED: [],  # Terminal
        }
        
        if new_status not in ALLOWED_TRANSITIONS.get(self.status, []):
            raise ValidationError(
                f"Invalid status transition: {self.status} → {new_status}"
            )
        
        self.status = new_status
        self.row_version += 1
        
        if new_status == EncounterStatusChoices.FINALIZED and user:
            from django.utils import timezone
            self.signed_at = timezone.now()
            self.signed_by_user = user
```

### 3.3 Especificación de API Contract

**Base URL**: `/api/v1/clinical/encounters/`

#### GET /api/v1/clinical/encounters/

**Response** (200 OK):

```json
[
  {
    "id": "uuid",
    "patient": "uuid",
    "patient_name": "string",
    "practitioner": "uuid | null",
    "practitioner_name": "string | null",
    "type": "initial_consult | follow_up | procedure | emergency | other",
    "status": "draft | finalized | cancelled",
    "occurred_at": "ISO 8601 datetime",
    "treatment_count": "integer",
    "attachments_summary": {
      "has_photos": "boolean",
      "has_documents": "boolean",
      "photo_count": "integer",
      "document_count": "integer"
    },
    "created_at": "ISO 8601 datetime"
  }
]
```

**Query Parameters**:
- `?patient_id=<uuid>`: Filter by patient
- `?practitioner_id=<uuid>`: Filter by practitioner
- `?status=draft|finalized|cancelled`: Filter by status
- `?date_from=YYYY-MM-DD`: Filter occurred_at >= date_from
- `?date_to=YYYY-MM-DD`: Filter occurred_at <= date_to

#### GET /api/v1/clinical/encounters/{id}/

**Response** (200 OK):

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
  "type": "enum",
  "status": "enum",
  "occurred_at": "ISO 8601 datetime",
  "chief_complaint": "string | null",
  "assessment": "string | null",
  "plan": "string | null",
  "internal_notes": "string | null",  // RBAC: ClinicalOps only
  "encounter_treatments": [
    {
      "treatment_id": "uuid",
      "treatment_name": "string",
      "treatment_sku": "string | null",
      "quantity": "integer",
      "unit_price": "decimal",
      "notes": "string | null"
    }
  ],
  "photos": [
    {
      "id": "uuid",
      "classification": "before | after | during | other",
      "created_at": "ISO 8601 datetime",
      "url": "string (presigned URL)",
      "filename": "string",
      "mime_type": "string",
      "size_bytes": "integer"
    }
  ],
  "documents": [
    {
      "id": "uuid",
      "title": "string | null",
      "created_at": "ISO 8601 datetime",
      "url": "string (presigned URL)",
      "filename": "string",
      "mime_type": "string",
      "size_bytes": "integer"
    }
  ],
  "signed_at": "ISO 8601 datetime | null",
  "signed_by_user": "uuid | null",
  "row_version": "integer",
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime"
}
```

#### POST /api/v1/clinical/encounters/

**Request Body**:

```json
{
  "patient": "uuid",  // REQUIRED
  "practitioner": "uuid | null",
  "location": "uuid | null",
  "type": "enum",  // REQUIRED
  "status": "draft | finalized | cancelled",  // Default: draft
  "occurred_at": "ISO 8601 datetime",  // REQUIRED
  "chief_complaint": "string | null",
  "assessment": "string | null",
  "plan": "string | null",
  "internal_notes": "string | null",  // RBAC: ClinicalOps only
  "encounter_treatments": [  // Optional nested creation
    {
      "treatment_id": "uuid",
      "quantity": "integer",
      "unit_price": "decimal",
      "notes": "string | null"
    }
  ]
}
```

**Response** (201 Created): Same as GET detail

#### PATCH /api/v1/clinical/encounters/{id}/

**Request Body**:

```json
{
  "row_version": "integer",  // REQUIRED (optimistic locking)
  "status": "enum",  // Validated transition
  "occurred_at": "ISO 8601 datetime",
  "chief_complaint": "string",
  "assessment": "string",
  "plan": "string",
  "internal_notes": "string"  // RBAC check
  // Note: encounter_treatments updated separately via dedicated endpoint
}
```

**Response** (200 OK): Full encounter detail

**Error** (409 Conflict):

```json
{
  "row_version": [
    "El registro fue modificado por otro usuario. Versión actual: 3, versión proporcionada: 2"
  ]
}
```

#### DELETE /api/v1/clinical/encounters/{id}/

**Behavior**: Soft delete (sets `is_deleted=true`, `deleted_at=now()`)

**Response** (204 No Content)

---

## 4. ESTRATEGIA: NO SE REQUIERE MIGRACIÓN DE DATOS

### 4.1 Decisión

**NO ejecutar migración de datos** porque:

1. ✅ El esquema actual es **correcto y coherente**
2. ✅ No hay inconsistencia de tipos (UUID en todos los niveles)
3. ✅ Base de datos vacía en DEV (`0 rows`)
4. ✅ Las migraciones existentes son válidas

### 4.2 Acciones de Limpieza (Arquitectura)

#### Acción 1: Eliminar módulo `apps.encounters` (DEPRECATED)

**Archivos a eliminar**:

```
apps/api/apps/encounters/
├── __init__.py
├── admin.py
├── apps.py
├── models.py          # DEPRECATED - solo contiene ClinicalMedia
├── serializers.py     # DEPRECATED
├── urls.py            # 410 Gone endpoint
├── views.py           # 410 Gone endpoint
├── permissions.py
└── migrations/
    └── ...
```

**Pasos**:

1. Verificar que NO hay imports activos de `apps.encounters.models.Encounter`
2. Mover `ClinicalMedia` a `apps.clinical.models` (si aún no está)
3. Eliminar directorio `apps/api/apps/encounters/` completo
4. Eliminar registro de URL `/api/encounters/` de `apps/api/config/urls.py`
5. Ejecutar tests de regresión

#### Acción 2: Actualizar imports en todo el codebase

**Buscar y reemplazar**:

```python
# OLD (deprecated)
from apps.encounters.models import Encounter

# NEW (definitive)
from apps.clinical.models import Encounter
```

**Comando de verificación**:

```bash
grep -r "from apps.encounters" apps/api/
grep -r "apps.encounters.models" apps/api/
```

#### Acción 3: Documentar en PROJECT_DECISIONS.md

Agregar nueva sección **Section 16: Encounter as Single Source of Truth**

---

## 5. REGLAS DE CONTRATO (Inmutables)

### 5.1 Campos NUNCA modificables (requieren nueva migración)

```python
# IMMUTABLE FIELDS - Cambiar estos requiere migración con impacto crítico
- id: UUID (PK)
- patient_id: UUID (FK, CASCADE delete)
- created_at: timestamptz (audit)
- created_by_user_id: UUID (audit)
```

### 5.2 Enums ESTABLES (evitar agregar valores)

```python
# EncounterTypeChoices - STABLE
'initial_consult', 'follow_up', 'procedure', 'emergency', 'other'

# EncounterStatusChoices - STABLE
'draft', 'finalized', 'cancelled'
```

**Regla**: Si necesitas un nuevo valor, evalúa si realmente necesitas un nuevo enum o si cabe en `other`.

### 5.3 Transiciones de Estado (Business Rules)

```
draft ──┬──> finalized (terminal)
        └──> cancelled (terminal)

finalized ──> (no transitions allowed)
cancelled ──> (no transitions allowed)
```

**Invariante**: Estados terminales NO pueden cambiar.

### 5.4 RBAC (Role-Based Access Control)

```python
# Field-level RBAC
internal_notes: Requires ClinicalOps role (enforced in serializer)

# Endpoint-level RBAC
POST /encounters/: Admin, Practitioner, ClinicalOps
PATCH /encounters/{id}/: Admin, Practitioner, ClinicalOps (+ ownership check)
DELETE /encounters/{id}/: Admin only
```

### 5.5 Concurrency Control (Optimistic Locking)

```
- All PATCH requests MUST include row_version
- Server increments row_version on every update
- Conflict detection: provided_version != current_version → 409 Conflict
```

### 5.6 Soft Delete (Audit Preservation)

```python
# Soft delete rules
is_deleted = True  # Flag for application-level filtering
deleted_at = timezone.now()  # Timestamp for audit
deleted_by_user_id = user.id  # Who deleted it

# Database-level constraint
CHECK (deleted_at IS NULL OR is_deleted = TRUE)
```

---

## 6. DECISIONES IRREVERSIBLES (Documentar en PROJECT_DECISIONS.md)

### Decisión 1: UUID como Primary Key

**Tipo**: `UUIDField` (UUID v4)

**Razones**:
- ✅ Globalmente único (distribuido, merges, imports)
- ✅ No expone volumen de datos (vs autoincrement)
- ✅ Compatible con APIs RESTful
- ❌ Mayor tamaño (16 bytes vs 4/8 bytes bigint)
- ❌ Performance de índices ligeramente inferior

**Irreversible**: Cambiar a bigint requiere migración de TODAS las FKs.

### Decisión 2: Soft Delete (vs Hard Delete)

**Patrón**: `is_deleted` + `deleted_at` + `deleted_by_user_id`

**Razones**:
- ✅ Preserva audit trail completo
- ✅ Permite recuperación de errores
- ✅ Cumple con regulaciones de salud (HIPAA, GDPR right to be forgotten with audit)
- ❌ Complejidad en queries (WHERE is_deleted = FALSE)
- ❌ Crecimiento de BD (records nunca eliminados)

**Irreversible**: Pasar a hard delete pierde historial de cambios.

### Decisión 3: Optimistic Locking (vs Pessimistic)

**Patrón**: `row_version` integer incremental

**Razones**:
- ✅ Mejor performance (no locks en DB)
- ✅ Escalabilidad horizontal
- ✅ UX: Usuario ve conflicto y decide qué hacer
- ❌ Requiere manejo de 409 Conflict en cliente

**Irreversible**: Cambiar a pessimistic locking (SELECT FOR UPDATE) requiere refactorización de transacciones.

### Decisión 4: Denormalized Counters

**Campos**: `photo_count_cached`, `document_count_cached`, `has_photos_cached`, `has_documents_cached`

**Razones**:
- ✅ Performance en list views (evita JOINs)
- ✅ Simple de mantener (signals o triggers)
- ❌ Riesgo de desincronización

**Mitigación**: Comando de management para recalcular counters.

**Irreversible**: Eliminar estos campos requiere modificar serializers y queries.

### Decisión 5: Single Source of Truth (apps.clinical)

**Decisión**: Encounter vive SOLO en `apps.clinical.models.Encounter`

**Razones**:
- ✅ Claridad: Un solo import path
- ✅ Mantenibilidad: Un solo lugar para modificar
- ✅ No duplicación de lógica

**Irreversible**: Una vez eliminado `apps.encounters`, no hay vuelta atrás sin restaurar de Git.

---

## 7. CHECKLIST DE IMPLEMENTACIÓN

### Fase 1: Validación (1 hora)

- [x] Verificar estructura de BD con `\d encounter`
- [x] Confirmar tipo UUID en id y FKs
- [x] Contar registros en encounter (0 rows en DEV)
- [x] Verificar serializers y views activos
- [x] Identificar módulo deprecated

### Fase 2: Limpieza del Módulo Deprecated (2 horas)

- [ ] Buscar imports de `apps.encounters.models` en codebase
- [ ] Reemplazar imports con `apps.clinical.models`
- [ ] Mover `ClinicalMedia` a `apps.clinical.models` (si aplica)
- [ ] Eliminar directorio `apps/api/apps/encounters/`
- [ ] Actualizar `INSTALLED_APPS` en settings.py
- [ ] Eliminar URL pattern `/api/encounters/` de `urls.py`
- [ ] Ejecutar tests: `python manage.py test apps.clinical`

### Fase 3: Documentación (1 hora)

- [ ] Agregar Section 16 a PROJECT_DECISIONS.md
- [ ] Crear este documento: ENCOUNTER_DEFINITIVE_SPECIFICATION.md
- [ ] Actualizar API_CONTRACTS.md con contract definitivo
- [ ] Actualizar README.md con import path correcto

### Fase 4: Verificación (30 min)

- [ ] Ejecutar `python manage.py check`
- [ ] Ejecutar `python manage.py makemigrations --dry-run` (debe estar vacío)
- [ ] Smoke test: Crear encounter via API
- [ ] Smoke test: Listar encounters via API
- [ ] Smoke test: Actualizar encounter con row_version

### Fase 5: Frontend (NO EN ESTE SPRINT)

- [ ] Actualizar TypeScript types para Encounter
- [ ] Implementar hooks: `useEncounters`, `useEncounterDetail`
- [ ] Componentes: EncounterList, EncounterDetail, EncounterForm
- [ ] Manejo de 409 Conflict (row_version mismatch)

---

## 8. RIESGOS Y MITIGACIONES

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Imports legacy de `apps.encounters` rompen tests | MEDIA | MEDIO | Búsqueda exhaustiva con grep, ejecución de test suite completa |
| Frontend usa endpoint deprecated `/api/encounters/` | BAJA | ALTO | Frontend ya usa `/api/v1/clinical/encounters/`, verificar con network inspector |
| Pérdida de ClinicalMedia al eliminar módulo | BAJA | CRÍTICO | Mover ClinicalMedia antes de eliminar, verificar con migration check |
| Desincronización de counters cached | BAJA | BAJO | Implementar comando `recalculate_encounter_counters` |

---

## 9. MÉTRICAS DE ÉXITO

✅ **Criterios de Aceptación**:

1. Módulo `apps.encounters` eliminado completamente de codebase
2. Todos los imports apuntan a `apps.clinical.models.Encounter`
3. Test suite pasa al 100% (`python manage.py test`)
4. API responde correctamente en todos los endpoints de Encounter
5. Documentación actualizada en PROJECT_DECISIONS.md
6. Zero warnings en `python manage.py check`
7. Zero pending migrations en `python manage.py showmigrations`

---

## 10. PRÓXIMOS PASOS

### Inmediato (HOY)

1. ✅ Obtener aprobación del usuario para esta estrategia
2. Ejecutar Fase 2: Limpieza del módulo deprecated
3. Ejecutar Fase 3: Documentación
4. Ejecutar Fase 4: Verificación

### Corto Plazo (Esta Semana)

1. Implementar comando de management: `recalculate_encounter_counters`
2. Agregar tests de integración para transiciones de estado
3. Documentar en API_CONTRACTS.md

### Mediano Plazo (Próximo Sprint)

1. Frontend: Implementar UI para Encounter
2. Frontend: Manejo de optimistic locking (409 Conflict)
3. Observability: Agregar métricas de Encounter en logging

---

## APÉNDICE A: Comandos Útiles

### Verificar estructura de tabla

```bash
docker exec -i emr-postgres-dev psql -U emr_user emr_derma_db -c "\d encounter"
```

### Buscar imports legacy

```bash
grep -rn "from apps.encounters" apps/api/
grep -rn "apps.encounters.models" apps/api/
```

### Verificar migraciones

```bash
docker compose -f docker-compose.dev.yml run --rm api python manage.py showmigrations clinical
```

### Test suite

```bash
docker compose -f docker-compose.dev.yml run --rm api python manage.py test apps.clinical.tests
```

### Crear encounter de prueba

```bash
# Ver create_encounter_example.py en raíz del proyecto
docker compose -f docker-compose.dev.yml run --rm api python create_encounter_example.py
```

---

## CONCLUSIÓN

**Encuentro NO tiene problema de tipo de dato**. El esquema actual con UUID es correcto, coherente y óptimo para este sistema.

**El verdadero problema es arquitectónico**: duplicación de módulos y falta de limpieza del código deprecated.

**Estrategia recomendada**: LIMPIEZA, NO MIGRACIÓN. Eliminar `apps.encounters`, documentar decisiones irreversibles, y establecer `apps.clinical.models.Encounter` como única fuente de verdad.

**Tiempo estimado de implementación**: 4 horas (sin contar frontend)

**Riesgo de implementación**: BAJO (base vacía, sin datos de producción)

---

**PRÓXIMA ACCIÓN**: Obtener aprobación del usuario y proceder con Fase 2 (Limpieza).
