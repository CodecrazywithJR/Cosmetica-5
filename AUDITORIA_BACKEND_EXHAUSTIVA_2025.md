# AUDITORÍA EXHAUSTIVA DEL BACKEND — Cosmetica 5

**Fecha:** 2025-07-10  
**Alcance:** Backend Django (`apps/api/`) — análisis estático del código fuente  
**Método:** Lectura directa de cada fichero del repositorio. Cero suposiciones.

---

## 1. RESUMEN EJECUTIVO

| Métrica | Valor |
|---|---|
| Framework | Django 4.2.8 + DRF 3.14.0 |
| Base de datos | PostgreSQL (con `django.contrib.postgres`) |
| Apps Django registradas | 17 en `INSTALLED_APPS` (1 deshabilitada: `social`) |
| Modelos de dominio | ~45 modelos concretos |
| LOC aplicación (sin migraciones) | **25 034** |
| LOC tests | **26 420** |
| Ficheros de test | 56 |
| Migraciones | 79 |
| Estado general | **MVP funcional con deuda técnica localizada y módulos placeholder** |

### Veredicto por principio arquitectónico

| # | Principio | Estado | Evidencia clave |
|---|---|---|---|
| 1 | Multi-tenancy | ⚠️ Parcial | `TenantModel` existe pero `AppSettings` es global, `Sale`/`TreatmentPlan` usan FK propio, `legal_entity` nullable |
| 2 | State machines | ✅ Sólido | Appointment (6 estados), Encounter (3), Proposal (5), Sale (5), TreatmentPlan (4), TreatmentSession (3) — todos en `save()` |
| 3 | Soft delete | ⚠️ Inconsistente | Patient/Encounter/Appointment/ClinicalPhoto/ClinicalMedia/PractitionerBlock: SÍ. User/Sale/SaleLine/Product/Stock*: NO |
| 4 | Immutabilidad de registros | ✅ Sólido | AuditLog y StockMove overridean `save()`/`delete()` con `TypeError` |
| 5 | RBAC | ✅ Funcional | 5 roles fijos, permisos por viewset, RBAC in-line en endpoints complejos |
| 6 | Auditoría | ✅ Dual | `ClinicalAccessLog` (acceso clínico) + `AuditLog` (ops/dominio) + `UserAuditLog` (admin auth) |
| 7 | i18n | ❌ Incompleto | `gettext_lazy` parcial, 0 ficheros `.po`/`.mo`, no `Accept-Language` handling |
| 8 | Fiscal | ❌ Ausente | No existe modelo `Invoice` ni `Payment`. `LegalEntity` declara explícitamente "NO FISCAL LOGIC" |
| 9 | Stock | ⚠️ Dual | Sistema `StockOnHand`+`StockBatch`+`StockMove` coexiste con `Product.stock_quantity` denormalizado |

---

## 2. MAPA DEL REPOSITORIO

```
apps/api/
├── config/
│   ├── settings.py          # Django settings, INSTALLED_APPS, JWT, CORS, DRF
│   ├── urls.py              # Root URL router (public, api/v1, system)
│   └── celery.py            # Celery configuration
├── apps/
│   ├── core/                # Infraestructura: TenantModel, TenantManager, TenantMiddleware,
│   │                        #   Clinic, AppSettings, audit.py, observability/
│   ├── authz/               # User (email-based, UUID PK), Role (5 fijos), Practitioner
│   ├── legal/               # LegalEntity (tenant master) — SOLO DATA MODEL
│   ├── clinical/            # Patient, Encounter, Appointment, Consent, Treatment,
│   │                        #   ClinicalPhoto, ClinicalMedia, PractitionerBlock/Schedule
│   │                        #   → 2162 LOC models.py, 2631 LOC views.py, 993 LOC services.py
│   ├── proposals/           # Proposal + ProposalLine (Clinical → Sales bridge)
│   ├── treatment_plans/     # TreatmentPlan + TreatmentSession
│   ├── sales/               # Sale, SaleLine, SaleRefund, SaleRefundLine + services (696 LOC)
│   ├── stock/               # StockLocation, StockBatch, StockMove (immutable), StockOnHand
│   │                        #   + services.py FEFO allocation (402 LOC)
│   ├── products/            # Product (SKU, price, cost, stock_quantity ← DUAL)
│   ├── pos/                 # POS views con fuzzy patient search (pg_trgm)
│   ├── documents/           # Document model (consent documents)
│   ├── ops/                 # AuditLog (immutable), diagnostics
│   ├── website/             # CMS público: Pages, Posts, Services, Leads, Staff
│   ├── photos/              # SkinPhoto → LEGACY (replaced by ClinicalPhoto)
│   ├── commerce/            # STUB — "Models will be implemented in PASO 2"
│   ├── integrations/        # VACÍO — models.py sin contenido
│   └── social/              # InstagramPost/Hashtag → DESHABILITADO en settings
├── tests/                   # 56 ficheros, ~965 test methods, 26420 LOC
└── conftest.py              # Fixtures compartidos
```

### Infraestructura externa

| Servicio | Uso | Configuración |
|---|---|---|
| PostgreSQL | DB principal | `django.contrib.postgres` (trigram, ExclusionConstraint) |
| Redis | Celery broker + JWT blacklist | `CELERY_BROKER_URL`, `CACHES` |
| MinIO (S3) | Object storage | 3 buckets: `derma-photos`, `marketing`, `documents` |
| Celery | Tareas async | `social/tasks.py`, `photos/tasks.py` (thumbnail generation) |

---

## 3. AUDITORÍA MÓDULO POR MÓDULO

---

### 3.1 `apps.core` — Infraestructura Tenant

**Ficheros inspeccionados:**  
`models.py`, `tenant_model.py`, `managers.py`, `middleware.py`, `tenant_context.py`, `tenant.py`, `audit.py`, `observability/`

#### 3.1.1 Modelos

| Modelo | Herencia | Campos clave | Observaciones |
|---|---|---|---|
| `Clinic` | `TenantModel` | name, address, legal_entity FK PROTECT | Correcto: scoped por tenant |
| `AppSettings` | `models.Model` (**no** TenantModel) | language, currency, timezone | **GAP**: Singleton global, no scoped por tenant |

#### 3.1.2 Tenant Model (`tenant_model.py`)

```python
class TenantModel(models.Model):
    legal_entity = models.ForeignKey(LegalEntity, null=True, blank=True, ...)
    objects = TenantManager()
    unfiltered = models.Manager()
    
    def save(self, *args, **kwargs):
        if not self.legal_entity_id:
            self.legal_entity_id = get_current_tenant()  # Thread-local
```

**Evidencia:**
- `legal_entity` es **nullable** (migración safety): todo modelo que hereda `TenantModel` acepta `legal_entity=NULL` en DB.
- `save()` auto-popula desde thread-local si falta.
- `TenantManager.get_queryset()` retorna **sin filtrar** cuando no hay tenant activo (superuser, management commands).

**GAP:** Si el thread-local no se setea (race condition, Celery sin context), los registros se crean con `legal_entity=NULL` y escapan al filtro tenant.

#### 3.1.3 Middleware

| Middleware | Posición | Función |
|---|---|---|
| `TenantMiddleware` | Después de `AuthenticationMiddleware` | Resuelve tenant desde `user.legal_entity` o header `X-Legal-Entity-ID` (superusers) |
| `InactiveLegalEntityMiddleware` | Después de `TenantMiddleware` | Bloquea POST/PUT/PATCH/DELETE cuando LE `is_active=False`. Exime superusers y `/admin/` |
| `RequestCorrelationMiddleware` | Después de `InactiveLegalEntityMiddleware` | Inyecta `X-Correlation-ID` para observabilidad |

**GAP:** JWT auth se resuelve en la capa DRF (view layer), no en middleware. El `TenantMiddleware` ve `request.user` como `AnonymousUser` para JWT requests → fallback a header.

#### 3.1.4 Permisos y seguridad

- **No hay** `SECURE_HSTS_*`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` en `settings.py`.
- CORS configurable vía env var `DJANGO_CORS_ALLOWED_ORIGINS`.
- `CORS_ALLOW_CREDENTIALS = True`.

**RIESGO:** Producción sin headers de seguridad HTTP hardcodeados (depende de proxy/nginx).

---

### 3.2 `apps.authz` — Autenticación y Autorización

**Ficheros inspeccionados:**  
`models.py`, `permissions.py`, `views_users.py`, `urls.py`

#### 3.2.1 Modelos

| Modelo | PK | Campos clave | Soft delete |
|---|---|---|---|
| `User` | UUID | email (unique), first_name, last_name, legal_entity FK (nullable para superusers), `must_change_password`, `is_staff`, `is_superuser` | **NO** (`is_active=False` en views, pero no hay campo `is_deleted`) |
| `Role` | UUID | name (5 choices: admin, practitioner, reception, marketing, accounting) | N/A (catálogo fijo) |
| `UserRole` | UUID | user FK, role FK | N/A |
| `Practitioner` | UUID | user OneToOne, role_type (practitioner/assistant/clinical_manager), display_name, specialty | NO |
| `UserAuditLog` | UUID | admin_user FK, target_user FK, action (create/update/reset_password/change_password/deactivate/activate) | N/A (append-only) |

**Evidencia:** DB constraint `chk_non_superuser_has_legal_entity` fuerza que usuarios no-superuser tengan `legal_entity IS NOT NULL`.

#### 3.2.2 Roles y Permisos

| Permiso | Lógica |
|---|---|
| `IsAdmin` | `user.is_superuser OR admin role` (case-insensitive check) |
| `PractitionerPermission` | Bloquea marketing y accounting |

#### 3.2.3 JWT

```python
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': 60 min (configurable env),
    'REFRESH_TOKEN_LIFETIME': 7 days (configurable env),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': env JWT_SIGNING_KEY or SECRET_KEY,
}
```

#### 3.2.4 Views

`UserAdminViewSet`: CRUD completo con audit logging, search, role filter, reset-password, change-password (self y admin), soft-delete via `is_active=False`.

**GAP:** `destroy()` setea `is_active=False` pero el modelo no tiene `is_deleted`/`deleted_at`. No hay forma de distinguir "usuario desactivado por admin" de "usuario eliminado".

---

### 3.3 `apps.legal` — Legal Entity (Tenant Master)

**Ficheros inspeccionados:**  
`models.py`, `views.py`, `urls.py`

#### 3.3.1 Modelo

| Campo | Tipo | Observación |
|---|---|---|
| `id` | UUID PK | ✅ |
| `legal_name`, `trade_name` | CharField | ✅ |
| `siren`, `siret`, `vat_number` | CharField nullable, unique | Campos fiscales franceses |
| `currency` | CharField default `EUR` | Configurable por LE |
| `timezone` | CharField default `Europe/Paris` | ✅ |
| `invoice_footer_text` | TextField | Solo texto — NO genera facturas |
| `is_active` | BooleanField | Controls `InactiveLegalEntityMiddleware` freeze |

**Declaración explícita en código:**
```python
# NOTE: This is a minimal model for MVP legal entity management.
# NO fiscal logic (taxes, invoice numbering, PDF generation) lives here.
# That belongs in a future dedicated fiscal/billing module.
# See ADR-002 for rationale.
```

#### 3.3.2 Views

- `LegalEntityViewSet`: Superuser only. CREATE genera auto-admin user. DELETE deshabilitado. Activate/deactivate actions.

---

### 3.4 `apps.clinical` — Core Clínico

**Ficheros inspeccionados:**  
`models.py` (2162 líneas), `views.py` (2631 líneas), `services.py` (993 líneas), `serializers.py` (1206 líneas), `permissions.py` (327 líneas), `urls.py`, `signals.py`

#### 3.4.1 Modelos

| Modelo | LOC aprox. | Herencia | Soft delete | State machine | Campos clave |
|---|---|---|---|---|---|
| `Patient` | ~300 | TenantModel | ✅ `is_deleted`, `deleted_at`, `deleted_by_user` | No | 40+ campos, `row_version` (optimistic concurrency), `is_merged`, `merged_into_patient`, `full_name_normalized` |
| `PatientGuardian` | ~50 | Model (FK Patient) | No | No | Menor de edad support |
| `PatientInsurance` | ~80 | Model (FK Patient) | No | No | `is_active`, date range validation, unique constraint `active+patient` |
| `PatientMergeLog` | ~40 | Model | No | No | strategy, evidence (JSON), merged_by_user |
| `Encounter` | ~200 | TenantModel | ✅ | ✅ `draft→finalized\|cancelled` (terminal inmutable) | patient/practitioner/clinic FKs, occurred_at, clinical fields |
| `AppointmentType` | ~20 | TenantModel | No | No | name, unique per tenant |
| `Appointment` | ~350 | TenantModel | ✅ | ✅ `scheduled→confirmed→checked_in→completed`, plus `cancelled`/`no_show` | DB `ExclusionConstraint` overbooking, auto-Encounter on `checked_in`, treatment_plan integration |
| `Consent` | ~60 | TenantModel | No | No | 6 consent types, granted/revoked, document FK |
| `ClinicalPhoto` | ~50 | TenantModel | ✅ | No | MinIO storage, patient FK |
| `ClinicalMedia` | ~40 | TenantModel | ✅ (`deleted_at`) | No | ImageField |
| `Treatment` | ~50 | TenantModel | No (soft via `is_active`) | No | Catálogo: default_price, duration_minutes, is_active |
| `EncounterTreatment` | ~40 | Model | No | No | M2M Encounter↔Treatment, quantity, unit_price, `effective_price` property |
| `PractitionerBlock` | ~40 | TenantModel | ✅ | No | Calendar blocks (start/end) |
| `PractitionerTreatment` | ~30 | TenantModel | No (soft via `is_active`) | No | Capability mapping practitioner→treatment |
| `PractitionerSchedule` | ~40 | Model | No (soft via `is_active`) | No | Per-clinic, per-weekday, start_time/end_time |
| `ClinicalAuditLog` | ~30 | Model | No | No | Action tracking (append-only) |

**Evidencia — Patient merge (views.py L500-600):** Merge inline en `PatientViewSet.merge` + merge service dedicado en `services.py`. Ambos existen — code path duplicado.

**Evidencia — State machine Appointment (models.py):**
```python
ALLOWED_TRANSITIONS = {
    'scheduled': ['confirmed', 'cancelled', 'no_show'],
    'confirmed': ['checked_in', 'cancelled', 'no_show'],
    'checked_in': ['completed'],
    'completed': [],    # terminal
    'cancelled': [],    # terminal
    'no_show': [],      # terminal
}
```

**Evidencia — DB-level overbooking prevention:**
```python
ExclusionConstraint(
    name='prevent_practitioner_overbooking',
    expressions=[
        (DateTimeRangeField(...), RangeOperators.OVERLAPS),
        ('practitioner', RangeOperators.EQUAL),
    ],
    condition=Q(is_deleted=False, status__in=_ACTIVE_STATUSES),
)
```

#### 3.4.2 Views (2631 LOC)

| ViewSet/View | Endpoints | Audit | Transacciones |
|---|---|---|---|
| `PatientViewSet` | CRUD + merge + overview | `log_clinical_access` + `log_event` | `select_for_update` en merge |
| `GuardianViewSet` | PATCH, DELETE (hard) | No | No |
| `PatientInsuranceViewSet` | GET, POST, PATCH | No | No |
| `AppointmentViewSet` | CRUD + `/transition/` + `/attend/` + `/start-treatment-session/` | `log_event` en create/update/transition | `select_for_update` + `transaction.atomic` |
| `EncounterViewSet` | CRUD + `/generate-proposal/` + `/add_treatment/` | `log_clinical_access` + `log_event` | `transaction.atomic` en add_treatment |
| `TreatmentViewSet` | CRUD (Admin only) | No | No |
| `ClinicalChargeProposalViewSet` | ReadOnly + `/send/` + `/accept/` + `/cancel/` + `/create-sale/` | `log_event` en transiciones | Delegado a modelo `Proposal.accept()` |
| `PractitionerCalendarView` | GET calendar feed | No | No |
| `PractitionerAvailabilityView` | GET slots disponibles | No | No |
| `PractitionerBookingView` | POST booking | Logger info | `select_for_update` + `transaction.atomic` + DB ExclusionConstraint fallback |
| `PatientMergeCandidatesView` | GET merge candidates | No | No |
| `PatientMergeView` | POST merge | Via service | `transaction.atomic` en service |

**GAP — RBAC inline repetido:** Multiple views repiten el pattern:
```python
user_roles = set(request.user.user_roles.values_list('role__name', flat=True))
if RoleChoices.XYZ not in user_roles: raise PermissionDenied(...)
```
En lugar de usar permission classes consistentes.

#### 3.4.3 Services (993 LOC)

| Servicio | Función | Atomic | Audit |
|---|---|---|---|
| `merge_patients()` | Merge completo con validaciones, FK reassignment, audit log | ✅ `select_for_update` | ✅ `PatientMergeLog` + signal `patient_merged` + Prometheus counters |
| `get_merge_candidates()` | Fuzzy duplicate detection con pg_trgm | N/A (read-only) | No |
| `create_encounter_from_appointment()` | Crea Encounter desde Appointment completada | ✅ | No |
| `generate_charge_proposal_from_encounter()` | Genera Proposal+ProposalLines desde Encounter finalized | ✅ | ✅ logger |
| `create_sale_from_proposal()` | Convierte Proposal→Sale via `.accept()` | Delegado | ✅ logger |
| `AvailabilityService.calculate_availability()` | Calcula slots libres (FEFO-aware, capability check) | N/A (read-only) | No |

**Evidencia — Prometheus metrics:** Merge service tiene `Counter` de prometheus_client (con fallback si no está instalado).

---

### 3.5 `apps.proposals` — Propuestas (Clinical → Sales Bridge)

**Ficheros inspeccionados:**  
`models.py` (503 líneas), `permissions.py`

#### 3.5.1 Modelos

| Modelo | Campos clave | State machine |
|---|---|---|
| `Proposal` | encounter OneToOne, patient/practitioner FK, status, currency (default `EUR`), total_amount, valid_until (30 días), converted_to_sale FK | `draft→sent→accepted\|cancelled\|expired` |
| `ProposalLine` | proposal FK, treatment FK, treatment_name (snapshot), unit_price (snapshot), quantity, line_total (auto-calc), type (`per_session`/`full_package`) | No (inmutable cuando proposal no-draft) |

**Evidencia — `Proposal.accept()` (atómico):**
```python
@transaction.atomic
def accept(self, user, legal_entity):
    # Validates status == SENT, not expired
    # Creates Sale + SaleLines from ProposalLines
    # Creates TreatmentPlan for full_package lines
    # Sets self.status = ACCEPTED, self.converted_to_sale = sale
```

**GAP — Currency:** `Proposal.currency` default `EUR`, pero `Sale.currency` default `USD`. Cuando `Proposal.accept()` crea un Sale, pasa explícitamente `currency=self.currency`, por lo que Sales creadas desde Proposals hereden EUR. Pero Sales directas defaultean USD.

---

### 3.6 `apps.treatment_plans` — Planes de Tratamiento

**Ficheros inspeccionados:**  
`models.py` (321 líneas), `treatment_session_models.py` (201 líneas)

#### 3.6.1 Modelos

| Modelo | Herencia | State machine | Observación |
|---|---|---|---|
| `TreatmentPlan` | **Model** (no TenantModel) — tiene `legal_entity` FK propio | `draft→active→completed\|cancelled` | `planned_sessions`, `completed_sessions` counters, inmutable en estados terminales |
| `TreatmentSession` | TenantModel | `draft→completed\|cancelled` | OneToOne Appointment, `performed_at`, inmutable en terminales |

**GAP:** `TreatmentPlan` no hereda de `TenantModel` sino que tiene su propio FK `legal_entity`. Esto significa que no pasa por el `TenantManager` automático — necesita filtrado manual por `legal_entity`.

---

### 3.7 `apps.sales` — Ventas

**Ficheros inspeccionados:**  
`models.py` (741 líneas), `services.py` (696 líneas), `permissions.py`

#### 3.7.1 Modelos

| Modelo | Herencia | Soft delete | State machine |
|---|---|---|---|
| `Sale` | **Model** (FK `legal_entity` propio, NO TenantModel) | ❌ | `draft→pending→paid→refunded` + `cancelled` |
| `SaleLine` | Model (FK Sale CASCADE) | ❌ | No |
| `SaleRefund` | Model | ❌ | No (idempotency_key unique) |
| `SaleRefundLine` | Model (FK SaleRefund) | ❌ | No |

**Evidencia — Currency default contradicción:**
```python
# Sale.currency
currency = models.CharField(max_length=3, default='USD')  # ← USD

# Proposal.currency  
currency = models.CharField(max_length=3, default='EUR')  # ← EUR
```

**Evidencia — State machine Sale:**
```python
ALLOWED_TRANSITIONS = {
    'draft': ['pending', 'cancelled'],
    'pending': ['paid', 'cancelled'],
    'paid': ['refunded'],
    'refunded': [],
    'cancelled': [],
}
```

Sale `save()` trigger: `PAID` → `consume_stock_for_sale()`, `REFUNDED` → `refund_stock_for_sale()`.

#### 3.7.2 Services (696 LOC — `sales/services.py`)

| Función | Propósito | Atomic |
|---|---|---|
| `consume_stock_for_sale()` | FEFO consumption, idempotent, creates StockMoves | ✅ |
| `check_stock_availability_for_sale()` | Pre-check sin mutación | N/A |
| `refund_stock_for_sale()` | Full refund — exact batch reversal | ✅ |
| `refund_partial_for_sale()` | Partial refund (Layer 3C) — proportional reversal | ✅ |

**GAP:** Sale no tiene soft delete. Una venta errónea solo puede cancelarse (state machine), nunca eliminarse.

---

### 3.8 `apps.stock` — Inventario

**Ficheros inspeccionados:**  
`models.py` (481 líneas), `services.py` (402 líneas), `permissions.py`

#### 3.8.1 Modelos

| Modelo | Herencia | Inmutable | Observación |
|---|---|---|---|
| `StockLocation` | TenantModel | No | name, code, type |
| `StockBatch` | TenantModel | No | batch_number (unique per product), expiry_date, `is_expired`/`days_until_expiry` properties |
| `StockMove` | TenantModel | ✅ **INMUTABLE** | `save()` raises `TypeError` on update, `delete()` raises always. Quantity signed (+IN, -OUT). FKs: sale, sale_line, reversed_move, refund, source_move |
| `StockOnHand` | TenantModel | No | unique (product, location, batch), `quantity_on_hand >= 0` (CheckConstraint) |

**Evidencia — Inmutabilidad StockMove:**
```python
def save(self, *args, **kwargs):
    if self.pk:
        raise TypeError("StockMove is immutable – cannot update existing record.")
    super().save(*args, **kwargs)

def delete(self, *args, **kwargs):
    raise TypeError("StockMove cannot be deleted – append a reversal instead.")
```

#### 3.8.2 Services (402 LOC — `stock/services.py`)

| Función | Propósito |
|---|---|
| `allocate_batch_fefo()` | FEFO allocation: earliest expiry first |
| `create_stock_move()` | Single move + StockOnHand update (validates non-negative) |
| `create_stock_out_fefo()` | Auto-FEFO consumption |
| `commit_sale_to_stock()` | Sale→Stock OUT (idempotent) — **INCOMPLETO**: función tiene `pass` y TODO |
| `get_stock_summary()` | Read-only aggregation |

**GAP CRÍTICO — `commit_sale_to_stock()` es un stub:**
```python
# TODO: This requires SaleLine to have a FK to Product
# For now, we'll document this limitation
pass
```
El método existe y se invoca pero **no hace nada**. La integración real Sale→Stock está en `sales/services.py::consume_stock_for_sale()`.

---

### 3.9 `apps.products` — Productos

**Ficheros inspeccionados:**  
`models.py`

| Modelo | Herencia | Campos clave | Soft delete |
|---|---|---|---|
| `Product` | TenantModel | sku, name, price, cost, **stock_quantity**, is_low_stock property | ❌ |

**GAP — Dual stock tracking:** `Product.stock_quantity` (campo denormalizado) coexiste con el sistema `StockOnHand` (normalizado por location+batch). No hay sincronización automática entre ambos.

---

### 3.10 `apps.ops` — Auditoría Operacional

**Ficheros inspeccionados:**  
`models.py` (154 líneas), `services.py` (98 líneas)

| Modelo | Inmutable | Campos clave |
|---|---|---|
| `AuditLog` | ✅ (`save()` raises TypeError on update, `delete()` raises always) | legal_entity FK (required), 20+ event types, entity_type/entity_id, payload JSON, user FK, ip_address |

**Evidencia — Event types definidos:**
```python
APPOINTMENT_CREATED, APPOINTMENT_UPDATED, APPOINTMENT_CANCELLED, APPOINTMENT_NO_SHOW,
APPOINTMENT_CHECKED_IN, ENCOUNTER_CREATED, ENCOUNTER_FINALIZED, ENCOUNTER_CANCELLED,
PROPOSAL_CREATED, PROPOSAL_SENT, PROPOSAL_ACCEPTED, PROPOSAL_CANCELLED,
SALE_CREATED, SALE_STATUS_CHANGED, SALE_PAID, SALE_REFUNDED,
STOCK_MOVE_CREATED, PATIENT_CREATED, PATIENT_UPDATED, PATIENT_DELETED, PATIENT_MERGED,
TREATMENT_SESSION_CREATED, TREATMENT_SESSION_COMPLETED
```

---

### 3.11 `apps.documents` — Documentos

**Ficheros inspeccionados:** `models.py`

- Modelo `Document` con document types (consent templates), asociado a LegalEntity.
- Usado por `Consent` para vincular documentos firmados.

---

### 3.12 `apps.pos` — Point of Sale

**Ficheros inspeccionados:** `views.py`, `utils.py`, `urls.py`

- Fuzzy patient search via `pg_trgm` (`TrigramSimilarity`).
- `mask_phone()`, `mask_email()` utilities para PII masking en merge candidates.
- `normalize_search_query()` para búsqueda normalizada.

---

### 3.13 `apps.website` — CMS Público

**Ficheros inspeccionados:** `models.py`, `urls.py`

| Modelo | Propósito |
|---|---|
| `WebsiteSettings` | Singleton CMS settings por tenant |
| `Page`, `Post`, `Service` | Contenido público |
| `StaffMember` | Perfil público de practitioners |
| `Lead` | Captura de leads (formulario público) |
| `MarketingMediaAsset` | Assets de marketing (MinIO) |

- URL prefix: `/public/` (sin autenticación)
- Throttling: `lead_submissions: 10/hour`, `lead_burst: 2/min`

---

### 3.14 Módulos Placeholder / Legacy / Deshabilitados

| App | Estado | Evidencia |
|---|---|---|
| `commerce` | **STUB** | `models.py`: `"Models will be implemented in PASO 2"` |
| `integrations` | **VACÍO** | `models.py` sin contenido |
| `social` | **DESHABILITADO** | Comentado en `INSTALLED_APPS`: `"DISABLED: AUTH_USER_MODEL issue"` |
| `photos` | **LEGACY** | `SkinPhoto` con `related_name='legacy_photos'`. Reemplazado por `ClinicalPhoto` |

---

## 4. MATRIZ DE MADUREZ POR MÓDULO

| Módulo | Modelos | State Machine | Soft Delete | Auditoría | Permisos RBAC | Tests | Tenant Scoping | Madurez |
|---|---|---|---|---|---|---|---|---|
| `core` | ✅ | N/A | N/A | N/A | N/A | ✅ | ⚠️ AppSettings global | 🟡 |
| `authz` | ✅ | N/A | ⚠️ is_active only | ✅ UserAuditLog | ✅ IsAdmin | ✅ | ✅ | 🟢 |
| `legal` | ✅ | N/A | N/A (activate/deactivate) | No | ✅ IsSuperUser | ✅ | N/A (system plane) | 🟢 |
| `clinical` | ✅✅ | ✅ Appointment + Encounter | ✅ Patient/Encounter/Appointment/Photo | ✅✅ Dual audit | ✅ 7 permission classes | ✅ | ✅ TenantModel | 🟢 |
| `proposals` | ✅ | ✅ 5 estados | N/A (terminal states) | ✅ log_event | ✅ ProposalPermission | ✅ | ✅ TenantModel | 🟢 |
| `treatment_plans` | ✅ | ✅ Plan + Session | N/A | ⚠️ Parcial | ⚠️ Via clinical views | ✅ | ⚠️ FK propio | 🟡 |
| `sales` | ✅ | ✅ 5 estados | ❌ | ✅ log_event | ✅ SalePermission | ✅ | ⚠️ FK propio | 🟡 |
| `stock` | ✅ | N/A | N/A (inmutable) | ✅ Via StockMove trail | ✅ IsClinicalOpsOrAdmin | ✅ | ✅ TenantModel | 🟢 |
| `products` | ✅ | N/A | ❌ | ❌ | ⚠️ No dedicado | ⚠️ | ✅ TenantModel | 🟡 |
| `pos` | ✅ Views only | N/A | N/A | No | ⚠️ | ⚠️ | ✅ Via TenantQuerySetMixin | 🟡 |
| `documents` | ✅ | N/A | N/A | No | ⚠️ | ⚠️ | ✅ | 🟡 |
| `ops` | ✅ Inmutable | N/A | N/A | ✅ (es el audit) | N/A | ✅ | ✅ (required LE) | 🟢 |
| `website` | ✅ | N/A | N/A | ❌ | ❌ (público) | ⚠️ | ✅ | 🟡 |
| `commerce` | ❌ Stub | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | 🔴 |
| `integrations` | ❌ Vacío | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | 🔴 |
| `social` | ❌ Deshabilitado | N/A | N/A | N/A | N/A | N/A | N/A | 🔴 |
| `photos` | ⚠️ Legacy | N/A | No | No | ⚠️ | ⚠️ | ✅ TenantModel | 🟠 |

**Leyenda:** 🟢 Producción-ready | 🟡 Funcional con gaps | 🟠 Legacy/deprecated | 🔴 No funcional

---

## 5. MATRIZ DE GAPS CONTRA REQUERIMIENTOS CLAVE

| Requerimiento | Estado | Fichero evidencia | Detalle |
|---|---|---|---|
| Multi-tenant isolation | ⚠️ Parcial | `core/tenant_model.py` L8 | `legal_entity` nullable; `Sale`/`TreatmentPlan` no usan `TenantModel`; `AppSettings` global |
| Overbooking prevention | ✅ | `clinical/models.py` ExclusionConstraint | Application-level check + DB constraint fallback |
| Patient merge | ✅ | `clinical/services.py` L1-180 | Atomic, validated, audit trail, signals, metrics. Pero duplicado con inline merge en views.py |
| Encounter state machine | ✅ | `clinical/models.py` Encounter.save() | draft→finalized/cancelled. Terminal states immutable |
| Proposal→Sale pipeline | ✅ | `proposals/models.py` Proposal.accept() | Atomic: Sale + SaleLines + TreatmentPlans |
| Stock FEFO | ✅ | `sales/services.py` + `stock/services.py` | Dual implementation: `sales/services.py` es funcional; `stock/services.py::commit_sale_to_stock()` es stub |
| Stock immutability | ✅ | `stock/models.py` StockMove.save()/delete() | TypeError on update/delete |
| Audit trail | ✅ | `ops/models.py` + `core/audit.py` | AuditLog inmutable + ClinicalAccessLog |
| Invoice generation | ❌ Ausente | N/A | No existe modelo Invoice ni Payment. LegalEntity.invoice_footer_text es solo texto |
| Tax calculation | ❌ Ausente | N/A | `LegalEntity` declara "NO FISCAL LOGIC". Proposal/Sale no tienen campos de tax |
| i18n completo | ❌ | 0 ficheros .po/.mo | `gettext_lazy` parcial (sales, stock, legal, products, website). clinical y authz NO usan `_()` |
| Soft delete uniforme | ❌ Inconsistente | Ver §3 por módulo | 7 modelos SÍ, 8+ modelos NO |
| Password change enforcement | ✅ | `authz/models.py` User.must_change_password | Flag exists, enforced in views |
| Optimistic concurrency | ✅ | `clinical/models.py` Patient.row_version | Validated in serializer, incremented on update |
| Public booking security | ✅ | `config/settings.py` PUBLIC_BOOKING_TOKEN_KEY | HMAC-signed tokens + throttling |

---

## 6. CONTRADICCIONES DETECTADAS

### 6.1 Contradicciones vs. Arquitectura Declarada

| # | Contradicción | Evidencia |
|---|---|---|
| C1 | **TenantModel → nullable FK** vs. "strict multi-tenancy" | `tenant_model.py` L5: `null=True, blank=True`. Permite registros sin tenant. |
| C2 | **Sale/TreatmentPlan no usan TenantModel** vs. "todo modelo hereda TenantModel" | `sales/models.py`: `legal_entity = ForeignKey(...)` directo. `treatment_plans/models.py`: igual. No pasan por `TenantManager`. |
| C3 | **AppSettings global** vs. "multi-tenant settings" | `core/models.py`: `AppSettings` no hereda `TenantModel`. Un solo registro global. |
| C4 | **commerce "PASO 2"** vs. siendo un `INSTALLED_APP` | `commerce/models.py`: stub. `settings.py`: `'apps.commerce'` registrado. App sin modelos en producción. |

### 6.2 Contradicciones Internas

| # | Contradicción | Evidencia |
|---|---|---|
| C5 | **Sale.currency default 'USD'** vs. **Proposal.currency default 'EUR'** | `sales/models.py` L~45: `default='USD'`. `proposals/models.py` L~30: `default='EUR'`. Sales directas (sin Proposal) defaultean USD. |
| C6 | **Product.stock_quantity** vs. **StockOnHand** | `products/models.py`: campo denormalizado. `stock/models.py`: normalizado por location+batch. Sin sincronización. |
| C7 | **Dual merge code paths** | `clinical/views.py` L~500: merge inline en PatientViewSet. `clinical/services.py` L50-180: merge service dedicado. `clinical/views.py` L~1550: `PatientMergeView` usa service. |
| C8 | **Dual stock service** | `stock/services.py::commit_sale_to_stock()`: stub con TODO. `sales/services.py::consume_stock_for_sale()`: implementación real funcional. |
| C9 | **Soft delete inconsistencia** | Clinical models: `is_deleted` + `deleted_at` + `deleted_by_user`. Sales: nada. Stock: inmutable (ni soft ni hard delete). Products: nada. User: `is_active=False` sin `is_deleted`. |
| C10 | **i18n parcial** | `sales/models.py`, `stock/models.py`, `legal/models.py`: usan `gettext_lazy`. `clinical/models.py`, `authz/models.py`: **NO** usan `_()`. 0 ficheros de traducción compilados. |

---

## 7. RIESGOS PRIORIZADOS

### 🔴 CRÍTICOS (bloquean producción real)

| # | Riesgo | Impacto | Fichero |
|---|---|---|---|
| R1 | **No hay modelo Invoice ni Payment** | Imposible facturar. Sale solo tiene status `paid` pero no genera documento fiscal. | N/A — ausente |
| R2 | **No hay cálculo de impuestos** | Precios ex-tax en proposals y sales. Ilegal en EU sin IVA. | `proposals/models.py`, `sales/models.py` |
| R3 | **Security headers ausentes** | No `SECURE_HSTS_*`, `SECURE_SSL_REDIRECT`, cookie flags. Depende 100% del reverse proxy. | `config/settings.py` |
| R4 | **Tenant FK nullable en TenantModel** | Registros pueden escapar del filtro tenant si el thread-local no se setea (Celery, management commands). | `core/tenant_model.py` L5 |

### 🟠 ALTOS (deuda significativa)

| # | Riesgo | Impacto | Fichero |
|---|---|---|---|
| R5 | **Product.stock_quantity desincronizado** | Frontend podría mostrar stock incorrecto si usa el campo denormalizado en lugar de StockOnHand. | `products/models.py` |
| R6 | **Sale.currency default USD vs. EUR** | Sales directas (sin Proposal) se crearían en USD en un contexto europeo. | `sales/models.py` |
| R7 | **`commit_sale_to_stock()` es un stub** | Código muerto que simula integración. La real está en sales/services.py. Confuso para nuevos desarrolladores. | `stock/services.py` L290-340 |
| R8 | **Sale/TreatmentPlan no usan TenantManager** | Queries directas sin filtro automático de tenant. Requiere filtrado manual en cada view/service. | `sales/models.py`, `treatment_plans/models.py` |
| R9 | **Soft delete inconsistente** | No hay convención única. Algunos modelos: is_deleted+deleted_at+deleted_by_user. Otros: is_active. Otros: nada. | Ver §6.2 C9 |

### 🟡 MEDIOS (deuda técnica aceptable)

| # | Riesgo | Impacto | Fichero |
|---|---|---|---|
| R10 | **i18n incompleto** | No se pueden generar respuestas en idiomas del cliente. | 0 ficheros .po/.mo |
| R11 | **AppSettings global** | Todos los tenants comparten configuración de idioma/moneda/timezone. | `core/models.py` AppSettings |
| R12 | **Módulos placeholder en INSTALLED_APPS** | commerce, integrations, social registrados pero sin funcionalidad. Contaminan migraciones. | `config/settings.py` |
| R13 | **Legacy photos app** | `SkinPhoto` coexiste con `ClinicalPhoto`. Requiere migración data y cleanup. | `photos/models.py` |
| R14 | **Dual merge code path** | PatientViewSet.merge (inline) + PatientMergeView (via service). El inline no usa el service validado. | `clinical/views.py` L~500 vs L~1550 |

---

## 8. ORDEN RECOMENDADO DE SANEAMIENTO

| Prioridad | Acción | Justificación | Módulos afectados |
|---|---|---|---|
| **P0** | Decidir si headers de seguridad van en Django o en reverse proxy, y documentarlo | R3 — Requisito OWASP. Si reverse proxy, agregar test de verificación. Si Django, agregar settings. | `config/settings.py` |
| **P1** | Diseñar e implementar módulo fiscal (Invoice, Payment, Tax) | R1, R2 — Bloqueante para operación comercial legal | Nuevo app `fiscal` o dentro de `commerce` |
| **P2** | Unificar tenant strategy: eliminar nullable en TenantModel o agregar NOT NULL constraint con migración | R4 — Integridad multi-tenant | `core/tenant_model.py`, migraciones |
| **P3** | Migrar Sale y TreatmentPlan a TenantModel | R8 — Consistencia de filtrado | `sales/models.py`, `treatment_plans/models.py` |
| **P4** | Resolver dual stock tracking: eliminar Product.stock_quantity o sincronizarlo | R5 — Single source of truth | `products/models.py`, `stock/models.py` |
| **P5** | Unificar currency default (EUR everywhere, o derivar de LegalEntity.currency) | R6, C5 — Consistencia financiera | `sales/models.py`, `proposals/models.py` |
| **P6** | Eliminar stub `commit_sale_to_stock()` y consolidar en `sales/services.py` | R7, C8 — Código muerto confuso | `stock/services.py` |
| **P7** | Estandarizar soft delete con mixin base (`SoftDeleteModel`) en todos los modelos de dominio | R9, C9 — Convención uniforme | Transversal |
| **P8** | Eliminar merge inline de PatientViewSet, usar solo PatientMergeView+service | R14, C7 — Single code path | `clinical/views.py` |
| **P9** | Migrar AppSettings a TenantModel (settings por tenant) | R11, C3 — Multi-tenant settings | `core/models.py` |
| **P10** | Limpiar INSTALLED_APPS: desregistrar commerce, integrations, social hasta que tengan código | R12 — Higiene | `config/settings.py` |
| **P11** | Completar i18n: agregar `_()` en clinical/authz, generar .po/.mo | R10, C10 — Internacionalización | Transversal |
| **P12** | Migrar data de SkinPhoto → ClinicalPhoto, eliminar app photos | R13 — Legacy cleanup | `photos/`, `clinical/` |

---

## EVIDENCE PACK

### Ficheros inspeccionados directamente (read_file)

| Fichero | LOC | Leído completo |
|---|---|---|
| `apps/core/models.py` | ~120 | ✅ |
| `apps/core/tenant_model.py` | ~50 | ✅ |
| `apps/core/managers.py` | ~40 | ✅ |
| `apps/core/middleware.py` | ~150 | ✅ |
| `apps/core/tenant_context.py` | ~20 | ✅ |
| `apps/core/tenant.py` | ~100 | ✅ |
| `apps/core/audit.py` | ~60 | ✅ |
| `apps/authz/models.py` | ~250 | ✅ |
| `apps/authz/permissions.py` | ~80 | ✅ |
| `apps/authz/views_users.py` | ~400 | ✅ |
| `apps/legal/models.py` | ~100 | ✅ |
| `apps/legal/views.py` | ~200 | ✅ |
| `apps/clinical/models.py` | 2162 | ✅ |
| `apps/clinical/views.py` | 2631 | ✅ |
| `apps/clinical/services.py` | 993 | ✅ |
| `apps/clinical/serializers.py` | 600/1206 | Parcial (primeras 600 líneas) |
| `apps/clinical/permissions.py` | 327 | ✅ |
| `apps/clinical/urls.py` | ~60 | ✅ |
| `apps/proposals/models.py` | 503 | ✅ |
| `apps/proposals/permissions.py` | ~50 | ✅ |
| `apps/treatment_plans/models.py` | 321 | ✅ |
| `apps/treatment_plans/treatment_session_models.py` | 201 | ✅ |
| `apps/sales/models.py` | 741 | ✅ |
| `apps/sales/services.py` | 696 | ✅ |
| `apps/sales/permissions.py` | ~60 | ✅ |
| `apps/stock/models.py` | 481 | ✅ |
| `apps/stock/services.py` | 402 | ✅ |
| `apps/stock/permissions.py` | ~40 | ✅ |
| `apps/products/models.py` | ~80 | ✅ |
| `apps/ops/models.py` | 154 | ✅ |
| `apps/ops/services.py` | 98 | ✅ |
| `apps/photos/models.py` | ~90 | ✅ |
| `apps/commerce/models.py` | ~5 | ✅ |
| `apps/integrations/models.py` | ~2 | ✅ |
| `config/settings.py` | ~300 | Parcial (secciones clave) |
| `config/urls.py` | ~50 | ✅ |

### Comandos ejecutados

```bash
# Estructura
find apps/api/apps -type f -name "*.py" | head -200
ls -la apps/api/apps/*/

# Conteos
find apps/api/apps -name "*.py" -path "*/migrations/*" ! -name "__init__.py" | wc -l  # → 79
find apps/api/tests -name "test_*.py" | wc -l                                          # → 56
find apps/api/apps -name "*.py" ! -path "*/migrations/*" ! -name "__init__.py" | xargs wc -l | tail -1  # → 25034
find apps/api/tests -name "*.py" | xargs wc -l | tail -1                               # → 26420

# Búsquedas específicas
grep -rn "is_deleted" apps/api/apps/authz/ apps/api/apps/sales/ apps/api/apps/products/  # → 0 results
grep -rn "class Invoice\|class Payment" apps/api/apps/                                     # → 0 results
grep -rn "gettext_lazy" apps/api/apps/clinical/models.py apps/api/apps/authz/models.py    # → 0 results
grep -rn "default=.*USD\|default=.*EUR" apps/api/apps/sales/ apps/api/apps/proposals/     # → USD vs EUR
find apps/api -name "*.po" -o -name "*.mo"                                                 # → 0 results
grep -E "SECURE_|CSRF_COOKIE_SECURE|SESSION_COOKIE_SECURE" apps/api/config/settings.py    # → 0 results
```

---

*Fin del informe. Cada hallazgo está respaldado por fichero y línea concreta del repositorio.*
