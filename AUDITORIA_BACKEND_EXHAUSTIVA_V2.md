# AUDITORÍA EXHAUSTIVA DEL BACKEND — Cosmetica 5 — Evidence Pack V2

> **Fecha:** 2025-01-02  
> **Scope:** `/apps/api/` — Django 4.2.8 + DRF 3.14.0 + PostgreSQL  
> **Modo:** Solo diagnóstico — CERO cambios de código  
> **Total Python files:** 238 | **Total lines:** 58,955 | **Total migrations:** 79  
> **Total test files:** 57 | **Total apps:** 17 (15 activas + 2 deshabilitadas/vacías)

---

## 1. RESUMEN EJECUTIVO

El backend de Cosmetica 5 es un ERP clínico multi-tenant con 17 Django apps, arquitectura de aislamiento por Legal Entity, RBAC de 5 roles, y flujos de negocio complejos (citas → encuentros → propuestas → ventas → stock).

### Estado general

| Dimensión | Estado | Evidencia |
|-----------|--------|-----------|
| Multi-tenancy | ✅ Implementado | TenantModel + TenantManager + TenantMiddleware |
| RBAC | ✅ Implementado | 5 roles, permisos por ViewSet y acción |
| State machines | ✅ Implementado | Appointment (6 estados), Encounter (3), Proposal (5), Sale (5), TreatmentPlan (4), TreatmentSession (3) |
| Soft delete | ⚠️ Parcial | Patient, Encounter, Appointment, ClinicalPhoto, ClinicalMedia, PractitionerBlock, Document — pero NO en Proposal, Sale, TreatmentPlan, TreatmentSession |
| Audit trail | ✅ Doble capa | ops.AuditLog (append-only) + clinical.ClinicalAuditLog + clinical.ClinicalAccessLog |
| Test coverage | ⚠️ No verificable | 57 test files existen, pero tests **NO pueden ejecutarse** por bug bloqueante en stock/models.py |
| API schema | ✅ drf-spectacular | `/api/schema/`, Swagger UI, Redoc |
| Seguridad JWT | ✅ Implementado | Access 60min + Refresh 7d + rotación + blacklist |

### 🔴 HALLAZGOS BLOQUEANTES (P0)

1. **stock/models.py L22-24 — NameError impide arranque de Django**  
   ```python
   LABEL_CREATED_AT = LABEL_CREATED_AT  # NameError: name 'LABEL_CREATED_AT' is not defined
   LABEL_UPDATED_AT = LABEL_UPDATED_AT  # NameError
   FK_PRODUCT = FK_PRODUCT              # NameError
   ```
   **Impacto:** Toda la aplicación no arranca. Tests no ejecutables. Servidor no puede iniciar.

---

## 2. MAPA DEL REPOSITORIO

### Estructura de directorios

```
apps/api/
├── config/
│   ├── settings.py          (360 lines)
│   ├── urls.py              (65 lines)
│   ├── wsgi.py / asgi.py
│   └── celery.py
├── apps/
│   ├── core/                (tenant, middleware, auth, health, observability)
│   ├── authz/               (User, Role, Practitioner, permissions)
│   ├── legal/               (LegalEntity)
│   ├── clinical/            (Patient, Encounter, Appointment, Consent, Photo, Treatment...)
│   ├── proposals/           (Proposal, ProposalLine)
│   ├── treatment_plans/     (TreatmentPlan, TreatmentSession)
│   ├── sales/               (Sale, SaleLine, SaleRefund, SaleRefundLine)
│   ├── stock/               (StockLocation, StockBatch, StockMove, StockOnHand)
│   ├── products/            (Product) [legacy]
│   ├── documents/           (Document) [model-only, no API]
│   ├── photos/              (SkinPhoto) [legacy]
│   ├── pos/                 (Patient search/upsert for POS) [model-less]
│   ├── ops/                 (AuditLog) [admin-only, no API]
│   ├── website/             (Page, Post, Service, StaffMember, Lead, Settings, Asset) [público]
│   ├── social/              (InstagramPost, Hashtag) [DESHABILITADA]
│   ├── commerce/            (VACÍA — placeholder "PASO 2")
│   └── integrations/        (VACÍA — placeholder)
└── tests/                   (57 archivos)
```

### Archivos más grandes (top 10)

| Archivo | Líneas |
|---------|--------|
| clinical/views.py | 2,604 |
| clinical/models.py | 2,181 |
| clinical/serializers.py | 1,197 |
| clinical/services.py | 970 |
| clinical/views_public_booking.py | 734 |
| sales/models.py | 741 |
| sales/services.py | 696 |
| proposals/models.py | 503 |
| authz/serializers_users.py | 503 |
| stock/models.py | ~460 |

### Migraciones por app

| App | Migraciones | Última |
|-----|-------------|--------|
| clinical | 31 | 0116_prevent_practitioner_overbooking |
| authz | 10 | — |
| sales | 7 | — |
| proposals | 5 | 0005_add_tenant_isolation |
| treatment_plans | 5 | — |
| stock | 5 | — |
| photos | 4 | — |
| legal | 4 | — |
| core | 3 | — |
| products | 2 | — |
| documents | 2 | — |
| ops | 1 | — |

---

## 3. AUDITORÍA MÓDULO POR MÓDULO

---

### 3.1 CORE (`apps/core/`)

#### 3.1.1 Modelos

**Clinic** — `core/models.py`
- TenantModel: ✅ (hereda TenantModel base con `legal_entity` FK)
- Campos: `name`, `address`, `timezone`, `is_active`, `created_at`, `updated_at`
- FK: `legal_entity` → LegalEntity (PROTECT, null=True)
- Manager: TenantManager (auto-filtra por tenant)

**AppSettings** — `core/models.py`
- Singleton pattern (pk=1)
- Campos: `default_country` (FR), `default_currency` (EUR), `default_language` (fr)
- NO hereda TenantModel — es global

#### 3.1.2 Tenant Infrastructure

**TenantModel** — `core/tenant_model.py`
- Abstract base model
- `legal_entity` FK → LegalEntity (PROTECT, **null=True** para migraciones)
- `objects = TenantManager()` — auto-filtra por get_current_tenant()
- `unfiltered = models.Manager()` — escape hatch sin filtro
- `save()` auto-popula legal_entity desde thread-local si no está seteado

**TenantManager** — `core/managers.py`
- Extiende `models.Manager`
- `get_queryset()` filtra por `legal_entity=get_current_tenant()`
- Si `get_current_tenant()` retorna None → **retorna tabla completa** (⚠️ riesgo)

**TenantMiddleware** — `core/middleware.py` L135-216
- Resuelve tenant desde `request.user.legal_entity` para usuarios normales
- Header `X-Legal-Entity-ID` para superusers
- Paths exentos: `/admin/`, `/api/v1/system/`, `/api/v1/auth/`, `/health`
- Seteado en `request.tenant` + thread-local via `set_current_tenant()`

**InactiveLegalEntityMiddleware** — `core/middleware.py` L57-129
- Bloquea POST/PUT/PATCH/DELETE cuando `legal_entity.is_active == False`
- Exento: safe methods, unauthenticated, superusers, `/admin/`
- Retorna JSON 403

#### 3.1.3 Auth

**JWT** — `config/settings.py` L195-210
- Access: 60 minutos (configurable via env)
- Refresh: 7 días (configurable)
- Rotación de refresh tokens: ✅
- Blacklist post-rotación: ✅
- Algoritmo: HS256

**Cookie-based refresh** — `core/auth_views.py`
- LoginView: POST `/api/auth/login/` — retorna access en body, refresh en HttpOnly cookie
- RefreshView: POST `/api/auth/refresh/` — lee refresh de cookie, retorna nuevo access
- LogoutView: POST `/api/auth/logout/` — blacklistea refresh token + borra cookie

#### 3.1.4 Observability

- `RequestCorrelationMiddleware` — agrega `X-Correlation-ID` a cada request
- `SanitizedJSONFormatter` — formato JSON para logs
- `CorrelationFilter` — inyecta correlation_id en logs
- `HealthzView` / `ReadyzView` — endpoints de salud (`/healthz`, `/readyz`)
- `DiagnosticsView` — `/api/v1/system/diagnostics/` (superuser)

#### 3.1.5 Hallazgos Core

| ID | Severidad | Hallazgo | Ubicación |
|----|-----------|----------|-----------|
| C-1 | 🟡 MEDIA | TenantManager retorna toda la tabla si `get_current_tenant()` es None | core/managers.py |
| C-2 | 🟢 BAJA | TenantModel.legal_entity es `null=True` — requerido para migraciones pero permite registros sin tenant | core/tenant_model.py |
| C-3 | 🟢 BAJA | JWT signing key defaults to SECRET_KEY — preferible clave dedicada | config/settings.py L207 |

---

### 3.2 LEGAL (`apps/legal/`)

#### 3.2.1 Modelos

**LegalEntity** — `legal/models.py`
- NO hereda TenantModel — es la raíz del tenant tree
- 25+ campos: `name`, `trade_name`, `siren`, `siret`, `vat_number`, `address_*`, `is_active`, `contact_*`
- Campos fiscales franceses: SIREN (9 dígitos), SIRET (14 dígitos), VAT number
- `is_active` controla el "freeze" via InactiveLegalEntityMiddleware
- `created_at`, `updated_at` timestamps

#### 3.2.2 Views

**LegalEntityViewSet** — `legal/views.py`
- Ruta: `/api/v1/system/legal-entities/`
- Permiso: **IsAdmin** — solo admin y superusers
- ModelViewSet completo (CRUD)
- Filtro: `?is_active=true/false`

#### 3.2.3 Hallazgos Legal

| ID | Severidad | Hallazgo | Ubicación |
|----|-----------|----------|-----------|
| L-1 | 🟢 BAJA | Validación de formato SIREN/SIRET no implementada en modelo ni serializer — acepta cualquier string | legal/models.py |

---

### 3.3 AUTHZ (`apps/authz/`)

#### 3.3.1 Modelos

**User** — `authz/models.py`
- Custom model con email como USERNAME_FIELD
- `legal_entity` FK → LegalEntity (null=True para superusers)
- `CheckConstraint`: superuser OR legal_entity NOT NULL — todo user normal requiere tenant
- `is_active` para soft-delete (deactivation)
- Bypass en `save()` para partial updates (⚠️ ver hallazgo)

**Role / UserRole** — `authz/models.py`
- `RoleChoices`: admin, practitioner, reception, marketing, accounting
- `UserRole`: junction table con `unique_together(user, role)`

**Practitioner** — `authz/models.py`
- `OneToOneField` → User (CASCADE)
- Campos: `display_name`, `role_type` (practitioner/assistant/clinical_manager), `specialty`
- Relación 1:1 — cada practitioner tiene exactamente un User

**UserAuditLog** — `authz/models.py`
- Before/after JSON snapshots de operaciones sobre User
- Campos: `actor`, `target_user`, `action`, `details_before`, `details_after`, `ip_address`

#### 3.3.2 Permissions

**IsAdmin** — `authz/permissions.py`
- Verifica `user.is_superuser` OR tiene rol `admin`
- **Superuser bypass** — superusers pasan siempre

**PractitionerPermission** — `authz/permissions.py`
- Verifica que el usuario sea Practitioner

#### 3.3.3 Management Commands

**create_admin_dev** — `authz/management/commands/create_admin_dev.py`
- Crea admin con **credenciales hardcoded**: `yo@ejemplo.com` / `Libertad`
- ⚠️ Solo para desarrollo, pero existe en codebase de producción

**ensure_demo_user_roles** — `authz/management/commands/ensure_demo_user_roles.py`
- Asigna roles a `admin@example.com` y `ricardoparlon@gmail.com`
- ⚠️ Emails personales hardcoded

#### 3.3.4 Hallazgos Authz

| ID | Severidad | Hallazgo | Ubicación |
|----|-----------|----------|-----------|
| A-1 | 🔴 ALTA | Management command `create_admin_dev` con password hardcoded "Libertad" | authz/management/commands/create_admin_dev.py |
| A-2 | 🟡 MEDIA | `ensure_demo_user_roles` contiene email personal `ricardoparlon@gmail.com` | authz/management/commands/ensure_demo_user_roles.py |
| A-3 | 🟡 MEDIA | User.save() tiene bypass para partial updates que podría permitir guardar sin CheckConstraint | authz/models.py |
| A-4 | 🟢 BAJA | Protección de último admin implementada en serializer pero no en modelo | authz/serializers_users.py |

---

### 3.4 CLINICAL (`apps/clinical/`)

#### 3.4.1 Modelos (2,181 líneas — módulo más grande)

| Modelo | Líneas | TenantModel | Soft Delete | State Machine |
|--------|--------|-------------|-------------|---------------|
| ReferralSource | 168-195 | ✅ | ❌ | ❌ |
| Patient | 229-423 | ✅ | ✅ (is_deleted, deleted_at, deleted_by_user) | ❌ |
| PatientGuardian | 450-481 | ❌ (plain Model) | ❌ | ❌ |
| PatientInsurance | 486-532 | ❌ (plain Model) | ❌ | ❌ |
| PatientMergeLog | 535-643 | ❌ (plain Model) | ❌ | ❌ |
| Encounter | 670-823 | ✅ | ✅ | ✅ (draft→finalized/cancelled) |
| AppointmentType | 846-878 | ✅ | ❌ | ❌ |
| Appointment | 908-1126 | ✅ | ✅ | ✅ (6 estados, ver abajo) |
| Consent | 1185-1215 | ✅ | ❌ | ❌ |
| ClinicalPhoto | 1220-1348 | ✅ | ✅ | ❌ |
| EncounterPhoto | 1351-1382 | ❌ (junction) | ❌ | ❌ |
| EncounterDocument | 1385-1418 | ❌ (junction) | ❌ | ❌ |
| ClinicalAuditLog | 1421-1509 | ❌ (plain Model) | ❌ | ❌ |
| Treatment | 1620-1679 | ✅ | ❌ (is_active flag) | ❌ |
| EncounterTreatment | 1682-1759 | ❌ (junction) | ❌ | ❌ |
| ClinicalMedia | 1780-1926 | ✅ | ✅ (deleted_at nullable) | ❌ |
| PractitionerBlock | 1941-2012 | ✅ | ✅ | ❌ |
| PractitionerTreatment | 2025-2051 | ❌ (junction) | ❌ | ❌ |
| PractitionerSchedule | 2054-2103 | ❌ (plain Model) | ❌ | ❌ |

**Patient** (L229-423) — 40+ campos:
- Nombre, demografía, contacto, dirección, preferencias, identidad, merge, marketing, médico, emergencia, consentimientos, concurrencia
- Custom managers: `PatientManager` (tenant+alive), `unfiltered`
- `row_version` para control de concurrencia optimista
- Constraints DB: no self-merge, merged requires target
- 8 índices

**Appointment State Machine** (L1019-1027):
```
scheduled → {confirmed, cancelled, no_show}
confirmed → {checked_in, cancelled, no_show}
checked_in → {completed}
Terminal: completed, cancelled, no_show
```

**Encounter State Machine** (L798-823):
```
draft → {finalized, cancelled}
Terminal: finalized, cancelled
```

**Overbooking Prevention**:
- Nivel aplicación: `_check_practitioner_overlap()` (L1111-1153)
- Nivel BD: ExclusionConstraint `prevent_practitioner_overbooking` via migración 0116

#### 3.4.2 Services (970 líneas)

**Patient Merge** — `services.py` L33-171:
- `merge_patients()` — atomic transaction + select_for_update()
- Guards: no self-merge, source not merged, target not merged, no cycles
- Reparents: appointments, encounters, clinical_photos, consents, guardians, audit_logs, sales

**Availability** — `services.py` L584-1113:
- `AvailabilityService.calculate_availability()` — multi-day slot generation
- Treatment-aware duration, practitioner capability check
- FEFO block overlap detection
- Slot alignment to boundaries

**Clinical→Sales** — `services.py` L403-577:
- `generate_charge_proposal_from_encounter()` — Encounter finalized → ClinicalChargeProposal
- `create_sale_from_proposal()` — Proposal → Sale (DRAFT)
- Idempotent: one proposal per encounter

#### 3.4.3 Views (2,604 líneas — archivo más grande)

| ViewSet | Líneas | Endpoints |
|---------|--------|-----------|
| PatientViewSet | 285-844 | CRUD + overview + merge |
| GuardianViewSet | 846-911 | Update + Delete |
| PatientInsuranceViewSet | 915-946 | CRUD con auto-close |
| AppointmentViewSet | 948-1468 | CRUD + transition + attend + start-treatment-session |
| TreatmentViewSet | 1470-1496 | CRUD (catálogo) |
| EncounterViewSet | 1498-1700 | CRUD + generate-proposal + add_treatment |
| ClinicalChargeProposalViewSet | 1702-1991 | List/Detail + send + accept + cancel + create-sale |
| ConsentViewSet | views_consents.py | CRUD + document attach/download/delete |
| DocumentViewSet | views_documents.py | CRUD + download |
| ClinicalPhotoViewSet | views_photos.py | CRUD + download |
| PractitionerCalendarView | 1993-2090 | GET calendar feed |
| PractitionerAvailabilityView | 2092-2190 | GET available slots |
| PractitionerBookingView | 2192-2608 | POST book appointment |

**Attend Workflow** (L1182-1298):
```
POST /appointments/{id}/attend/
→ Atomic: Crea Encounter (draft) + vincula a Appointment + marca completed
→ Idempotente: si ya tiene encounter, retorna existente
→ RBAC: Admin, Practitioner, Reception
```

**Start-Treatment-Session** (L1300-1422):
```
POST /appointments/{id}/start-treatment-session/
→ Crea TreatmentSession (draft) + marca appointment completed
→ Requiere: appointment.status=checked_in, plan.status=active
→ Guard: draft+completed sessions <= plan.planned_sessions
→ RBAC: Admin, Practitioner
```

#### 3.4.4 Public Booking API (views_public_booking.py — 734 líneas)

- `PublicAvailabilityView` — GET slots sin autenticación (token HMAC requerido)
- `PublicCreateBookingView` — POST crear cita desde web pública
- Seguridad: token firmado + anti-bot + throttle + PII masking
- Patient dedup: email > phone > crear nuevo (identity_confidence=low)

#### 3.4.5 Permissions (RBAC Matrix)

| Recurso | Admin | Practitioner | Reception | Accounting | Marketing |
|---------|-------|-------------|-----------|------------|-----------|
| Patient | CRUD+Delete | CRU | CRU | Read | ❌ |
| Guardian | CRUD | CRUD | CRUD | ❌ | ❌ |
| Appointment | CRUD+Delete | CRU | CRU | Read | ❌ |
| Encounter | CRUD | CRUD | ❌ | Read | ❌ |
| Consent | CRUD | CRUD | CRUD (admin) | ❌ | ❌ |
| Treatment | CRUD | CRUD | Read | ❌ | ❌ |

**Reception NO puede acceder a Encounters** — restricción clínica explícita.

#### 3.4.6 Hallazgos Clinical

| ID | Severidad | Hallazgo | Ubicación |
|----|-----------|----------|-----------|
| CL-1 | 🟡 MEDIA | PatientGuardian, PatientInsurance, PatientMergeLog NO heredan TenantModel — aislamiento solo vía FK a Patient (que sí es TenantModel) | clinical/models.py L450, L486, L535 |
| CL-2 | 🟡 MEDIA | PractitionerSchedule no hereda TenantModel — accesible cross-tenant si se consulta directamente | clinical/models.py L2054 |
| CL-3 | 🟡 MEDIA | ClinicalAuditLog no tiene aislamiento por tenant — contiene `patient` FK pero no `legal_entity` | clinical/models.py L1421 |
| CL-4 | 🟢 BAJA | Soft delete inconsistente: Patient/Encounter/Appointment/ClinicalPhoto usan `is_deleted` bool, ClinicalMedia usa `deleted_at` nullable | clinical/models.py |
| CL-5 | 🟢 BAJA | ClinicalPhoto y EncounterPhoto — ClinicalPhoto CASCADE on Patient delete, perderá fotos si se hace hard delete | clinical/models.py L1269 |
| CL-6 | 🟢 BAJA | views.py tiene 2,604 líneas — candidato a split en módulos | clinical/views.py |

---

### 3.5 PROPOSALS (`apps/proposals/`)

#### 3.5.1 Modelos

**Proposal** — `proposals/models.py` L63:
- ❌ **NO hereda TenantModel** — no tiene legal_entity directa
- FKs: encounter (OneToOne PROTECT), patient (PROTECT), practitioner (PROTECT), accepted_by (SET_NULL), converted_to_sale (SET_NULL), created_by (SET_NULL)
- State machine: DRAFT → SENT → ACCEPTED/CANCELLED/EXPIRED
- `TERMINAL_STATES = frozenset{ACCEPTED, CANCELLED, EXPIRED}`
- Financial: `total_amount` (Decimal), `currency` (EUR)
- Constraint: `total_amount >= 0`
- Immutability: save() bloquea ediciones en estados terminales

**Proposal.accept()** (L250-325):
- Atomic transaction
- SENT → ACCEPTED
- **Crea Sale + SaleLines + TreatmentPlans** en una sola transacción
- Side effects significativos

**ProposalLine** — `proposals/models.py` L354:
- ❌ NO tiene legal_entity
- FKs: proposal (CASCADE), encounter_treatment (PROTECT), treatment (PROTECT)
- Pricing snapshot: treatment_name, quantity, unit_price, line_total
- save()/delete() bloqueados en estados terminales del Proposal padre

#### 3.5.2 Permissions

**ProposalPermission** — `proposals/permissions.py` L16:
- Marketing → NO ACCESS
- SAFE: Admin, Practitioner, Reception, Accounting → Read
- Transitions (send/accept/cancel): Admin, Reception, Practitioner
- Practitioner solo ve sus propios proposals (has_object_permission)

#### 3.5.3 Hallazgos Proposals

| ID | Severidad | Hallazgo | Ubicación |
|----|-----------|----------|-----------|
| P-1 | 🟡 MEDIA | Proposal NO hereda TenantModel ni tiene legal_entity — aislamiento depende de FK a Patient/Encounter que sí son tenant-scoped | proposals/models.py L63 |
| P-2 | 🟡 MEDIA | Proposal.accept() NO es idempotente — si falla a mitad, puede dejar datos inconsistentes aunque es atomic | proposals/models.py L250 |
| P-3 | 🟢 BAJA | ProposalLine no tiene soft delete — eliminación es permanente | proposals/models.py L354 |

---

### 3.6 TREATMENT PLANS (`apps/treatment_plans/`)

#### 3.6.1 Modelos

**TreatmentPlan** — `treatment_plans/models.py` L51:
- ❌ NO hereda TenantModel — usa TenantManager() directamente
- `legal_entity` FK explícita (null=True, PROTECT) + `objects = TenantManager()`
- FKs: patient (PROTECT), practitioner (SET_NULL), proposal (PROTECT), proposal_line (OneToOne PROTECT), sale (SET_NULL)
- State machine: DRAFT → ACTIVE → COMPLETED/CANCELLED
- Campos snapshot: package_name, planned_sessions, completed_sessions, total_price_snapshot
- Methods: activate(), record_session_completed(), cancel()
- `record_session_completed()` auto-transiciona a COMPLETED si completed >= planned

**TreatmentSession** — `treatment_plans/treatment_session_models.py` L44:
- ✅ Hereda TenantModel
- FKs: treatment_plan (PROTECT), appointment (OneToOne PROTECT), practitioner (PROTECT)
- State machine: DRAFT → COMPLETED/CANCELLED
- Constraint: performed_at required si status=completed
- save() bloquea updates en estados terminales

#### 3.6.2 Views

**TreatmentPlanViewSet** — ReadOnly (list/detail)
- Permiso: IsClinicalStaff
- Filtros: ?patient, ?status

**TreatmentSessionViewSet** — List/Retrieve/Update + complete/cancel actions
- Permiso: IsClinicalStaff
- `complete()`: atomic + select_for_update + actualiza plan.completed_sessions
- `cancel()`: solo en status=draft

#### 3.6.3 Hallazgos Treatment Plans

| ID | Severidad | Hallazgo | Ubicación |
|----|-----------|----------|-----------|
| TP-1 | 🟡 MEDIA | TreatmentPlan NO hereda TenantModel pero tiene legal_entity FK + TenantManager — patrón inconsistente con el resto del proyecto | treatment_plans/models.py L51 |
| TP-2 | 🟢 BAJA | TreatmentPlan no tiene soft delete | treatment_plans/models.py |

---

### 3.7 SALES (`apps/sales/`)

#### 3.7.1 Modelos

**Sale** — `sales/models.py` L22:
- ❌ NO hereda TenantModel — usa TenantManager() directamente
- `legal_entity` FK explícita (PROTECT) + `objects = TenantManager()`
- FKs: patient (SET_NULL), appointment (SET_NULL)
- State machine: DRAFT → PENDING → PAID → REFUNDED | CANCELLED
- Financial: subtotal, tax, discount, total (Decimal), currency (default 'USD' — ⚠️ inconsistente con EUR en Proposals)
- Constraints: total/subtotal/tax/discount >= 0
- Immutability: save() bloquea en estados terminales
- `transition_to()`: ejecuta side effects de stock (consume/refund)
- `recalculate_totals()`: recalcula desde SaleLines

**SaleLine** — `sales/models.py` L268:
- FKs: sale (CASCADE), product (SET_NULL)
- Pricing: quantity, unit_price, discount, line_total
- save() auto-calcula line_total y trigger recalculate en parent Sale
- clean() valida reglas de negocio complejas

**SaleRefund** — `sales/models.py` L415:
- FKs: sale (CASCADE), created_by (SET_NULL)
- Estados: DRAFT, COMPLETED, FAILED
- `idempotency_key`: UniqueConstraint (sale, idempotency_key) WHERE NOT NULL
- Immutable audit trail

**SaleRefundLine** — `sales/models.py` L498:
- FKs: refund (CASCADE), sale_line (CASCADE)
- Validación: qty_refunded <= disponible, no over-refunding

#### 3.7.2 Services (696 líneas)

- `consume_stock_for_sale()` — FEFO stock consumption, idempotente, atómico
- `check_stock_availability_for_sale()` — check sin side effects
- `refund_stock_for_sale()` — 100% refund, restaura stock a batch/location exactos
- `refund_partial_for_sale()` — partial refund, proporcional, múltiples refunds por venta

#### 3.7.3 Permissions

**SalePermission**:
- SAFE: Admin, Reception, Accounting → Read
- Write: Admin, Reception only
- Practitioner, Marketing → NO ACCESS

#### 3.7.4 Hallazgos Sales

| ID | Severidad | Hallazgo | Ubicación |
|----|-----------|----------|-----------|
| S-1 | 🟡 MEDIA | Sale.currency default='USD' pero Proposal.currency default='EUR' — inconsistencia de moneda | sales/models.py L88 vs proposals/models.py L144 |
| S-2 | 🟡 MEDIA | Sale NO hereda TenantModel pero tiene legal_entity FK + TenantManager — misma inconsistencia que TreatmentPlan | sales/models.py L22 |
| S-3 | 🟢 BAJA | Sale no tiene soft delete | sales/models.py |

---

### 3.8 STOCK (`apps/stock/`)

#### 3.8.1 Modelos

**🔴 BLOQUEANTE: stock/models.py NO PUEDE CARGARSE**

```python
# stock/models.py L22-24
LABEL_CREATED_AT = LABEL_CREATED_AT  # NameError
LABEL_UPDATED_AT = LABEL_UPDATED_AT  # NameError
FK_PRODUCT = FK_PRODUCT              # NameError
```

Estas constantes se auto-referencian en lugar de definir valores reales. Esto impide que Django cargue el módulo y por tanto **toda la aplicación no arranca**.

**Modelos (según lectura estática del código):**

| Modelo | TenantModel | Campos clave |
|--------|-------------|-------------- |
| StockLocation | ✅ | name, code (unique), location_type, is_active |
| StockBatch | ✅ | product FK, batch_number, expiry_date |
| StockMove | ✅ | product FK, location FK, batch FK, move_type, quantity. **Inmutable**: no UPDATE, no DELETE |
| StockOnHand | ✅ | product FK, location FK, batch FK, quantity_on_hand. Unique (product, location, batch) |

**StockMove Immutability** (L256-273):
- `save()`: TypeError si ya existe
- `delete()`: TypeError siempre

**FEFO Service** — `stock/services.py`:
- `allocate_batch_fefo()` — First Expired First Out
- `create_stock_move()` — atomic, crea move + actualiza StockOnHand
- `create_stock_out_fefo()` — OUT movements con FEFO
- Custom exceptions: `InsufficientStockError`, `ExpiredBatchError`

#### 3.8.2 Hallazgos Stock

| ID | Severidad | Hallazgo | Ubicación |
|----|-----------|----------|-----------|
| ST-1 | 🔴 BLOQUEANTE | Constants auto-referenciadas causan NameError — Django no puede arrancar | stock/models.py L22-24 |
| ST-2 | 🟢 BAJA | StockMove.quantity es IntegerField sin constraint > 0 en modelo (solo `!= 0`) | stock/models.py |

---

### 3.9 PRODUCTS (`apps/products/`) — Legacy

#### 3.9.1 Modelo

**Product** — `products/models.py` L10-53:
- ✅ Hereda TenantModel
- Campos: sku (unique), name, description, category, brand, price, cost, stock_quantity, low_stock_threshold, is_active
- `is_low_stock` property

#### 3.9.2 Hallazgos Products

| ID | Severidad | Hallazgo | Ubicación |
|----|-----------|----------|-----------|
| PR-1 | 🔴 ALTA | ProductSerializer usa `fields = '__all__'` — expone `legal_entity` en la API, permitiendo potencialmente leer/escribir tenant ajeno | products/serializers.py L11 |
| PR-2 | 🟡 MEDIA | Product tiene `stock_quantity` local — duplica funcionalidad de StockOnHand. Dos fuentes de verdad para inventario | products/models.py L26 |

---

### 3.10 DOCUMENTS (`apps/documents/`) — Model-only

#### 3.10.1 Modelo

**Document** — `documents/models.py` L12-107:
- ✅ Hereda TenantModel
- Campos storage: object_key, content_type, size_bytes, sha256
- Soft delete: is_deleted, deleted_at, deleted_by_user
- Bucket fijo: 'documents'

#### 3.10.2 Hallazgos Documents

| ID | Severidad | Hallazgo | Ubicación |
|----|-----------|----------|-----------|
| D-1 | 🟡 MEDIA | App sin views, serializers, urls, ni permissions — solo accesible vía Django Admin | documents/ |

---

### 3.11 PHOTOS (`apps/photos/`) — Legacy

#### 3.11.1 Modelo

**SkinPhoto** — `photos/models.py` L20-106:
- ✅ Hereda TenantModel
- FKs: patient (CASCADE), encounter (SET_NULL)
- Campos: image (ImageField), body_part, tags, thumbnail
- Validación clean(): coherencia encounter-patient
- Celery task: `generate_thumbnail` post-save

#### 3.11.2 Hallazgos Photos

| ID | Severidad | Hallazgo | Ubicación |
|----|-----------|----------|-----------|
| PH-1 | 🟡 MEDIA | `on_delete=CASCADE` en patient FK — hard delete de patient elimina todas sus fotos irreversiblemente | photos/models.py L38 |
| PH-2 | 🟢 BAJA | Duplicación: existe tanto SkinPhoto (legacy) como ClinicalPhoto + ClinicalMedia (clinical) — 3 modelos para fotos | photos/models.py vs clinical/models.py |

---

### 3.12 POS (`apps/pos/`) — Model-less

#### 3.12.1 Funcionalidad

- PatientSearchView: búsqueda por phone (exact) > email (exact) > nombre (trigram fuzzy)
- PatientUpsertView: dedup por phone > email > crear nuevo (identity_confidence=low)
- PII siempre maskeada en respuestas
- Permiso: IsPOSUser (Admin + Reception)

#### 3.12.2 Hallazgos POS

| ID | Severidad | Hallazgo | Ubicación |
|----|-----------|----------|-----------|
| POS-1 | 🟡 MEDIA | Phone normalization hardcodea default country +52 (México) — inconsistente con contexto francés del ERP | pos/utils.py L29 |
| POS-2 | 🟢 BAJA | No usa TenantQuerySetMixin — depende de TenantMiddleware + Patient.TenantManager | pos/views.py |

---

### 3.13 OPS (`apps/ops/`) — Admin-only

#### 3.13.1 Modelo

**AuditLog** — `ops/models.py` L65-146:
- ❌ NO hereda TenantModel — plain Model
- ✅ Tiene `legal_entity` FK explícita (PROTECT, **NOT NULL** — más estricto que TenantModel)
- Inmutable: save() bloquea UPDATE, delete() siempre TypeError
- `log_event()` service: fail-safe, nunca aborta request principal

#### 3.13.2 Hallazgos Ops

| ID | Severidad | Hallazgo | Ubicación |
|----|-----------|----------|-----------|
| OP-1 | 🟡 MEDIA | AuditLog no usa TenantManager — queries devuelven datos cross-tenant | ops/models.py |
| OP-2 | 🟢 BAJA | Sin views/API — solo accesible vía Django Admin | ops/ |

---

### 3.14 WEBSITE (`apps/website/`) — Público

#### 3.14.1 Modelos (7 — todos plain Model, sin tenant)

- WebsiteSettings (singleton pk=1), Page, Post, Service, StaffMember, MarketingMediaAsset, Lead

#### 3.14.2 Seguridad

- Todos los endpoints son **públicos** (no auth)
- Content: read-only (status=published filter)
- Lead creation: rate limited (2/min burst, 10/hour)
- PII de leads nunca en logs

#### 3.14.3 Hallazgos Website

| ID | Severidad | Hallazgo | Ubicación |
|----|-----------|----------|-----------|
| W-1 | 🟡 MEDIA | Lead model sin aislamiento por tenant — todos los leads van a un pool global | website/models.py L283 |

---

### 3.15 SOCIAL (`apps/social/`) — DESHABILITADA

- Comentada en INSTALLED_APPS (L52) y urls.py (L38)
- Razón: "AUTH_USER_MODEL issue"
- Modelos: InstagramPost, InstagramHashtag — sin tenant
- ZIP guardado en `/tmp/` — efímero

#### Hallazgos Social

| ID | Severidad | Hallazgo | Ubicación |
|----|-----------|----------|-----------|
| SO-1 | 🟡 MEDIA | Path traversal risk en download_pack: `open(post.pack_file_path, 'rb')` sin validación de path | social/views.py |
| SO-2 | 🟡 MEDIA | No tiene RBAC — cualquier usuario autenticado puede gestionar posts | social/views.py |

---

### 3.16 COMMERCE (`apps/commerce/`) — VACÍA

- Contenido: solo `# Models will be implemented in PASO 2`
- Sin modelos, views, URLs, nada

### 3.17 INTEGRATIONS (`apps/integrations/`) — VACÍA

- Placeholder completo — ni un model definido
- urlpatterns = []

---

## 4. MATRIZ DE MADUREZ

| Módulo | Modelos | API | Permisos | Tests | Tenant | Audit | State Machine | Score |
|--------|---------|-----|----------|-------|--------|-------|---------------|-------|
| core | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | N/A | 9/10 |
| authz | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | N/A | 8/10 |
| legal | ✅ | ✅ | ✅ | ⚠️ | ✅ (raíz) | N/A | N/A | 8/10 |
| clinical | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅✅ | ✅ | 9/10 |
| proposals | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ⚠️ | ✅ | 7/10 |
| treatment_plans | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ⚠️ | ✅ | 7/10 |
| sales | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ⚠️ | ✅ | 7/10 |
| stock | 🔴 | ✅ | ✅ | ❌ | ✅ | ✅ | N/A | 3/10 |
| products | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ❌ | N/A | 5/10 |
| documents | ✅ | ❌ | ❌ | ⚠️ | ✅ | ❌ | N/A | 3/10 |
| photos | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | N/A | 7/10 |
| pos | N/A | ✅ | ✅ | ⚠️ | ⚠️ | ❌ | N/A | 5/10 |
| ops | ✅ | ❌ | ❌ | ⚠️ | ⚠️ | ✅ (ES audit) | N/A | 5/10 |
| website | ✅ | ✅ | ✅ (public) | ⚠️ | ❌ (ok) | ❌ | N/A | 7/10 |
| social | ✅ | ✅ | ⚠️ | ❌ | ❌ (ok) | ❌ | ⚠️ | 3/10 |
| commerce | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | 0/10 |
| integrations | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | 0/10 |

⚠️ Todos los tests marcados como "⚠️" porque no se pueden verificar (app no arranca por bug stock/models.py).

---

## 5. MATRIZ DE GAPS

### Implementado vs No Implementado

| Feature | Estado | Evidencia |
|---------|--------|-----------|
| Multi-tenancy con TenantModel | ✅ Implementado | 11 modelos usan TenantModel |
| Multi-tenancy con TenantManager | ✅ Implementado | Todos los modelos con tenant usan TenantManager |
| Middleware de tenant | ✅ Implementado | TenantMiddleware + InactiveLegalEntityMiddleware |
| RBAC 5 roles | ✅ Implementado | 8+ permission classes |
| Soft delete | ⚠️ Parcial | Solo Patient, Encounter, Appointment, ClinicalPhoto, ClinicalMedia, PractitionerBlock, Document |
| State machines | ✅ Implementado | 6 modelos con state machines |
| Optimistic locking | ⚠️ Parcial | Solo Patient y Encounter tienen `row_version` |
| Audit trail | ✅ Doble capa | ops.AuditLog + clinical.ClinicalAuditLog + ClinicalAccessLog |
| FEFO stock | ✅ Implementado (bloqueado) | stock/services.py — pero app no carga |
| Idempotency | ⚠️ Parcial | Sale refunds sí, Proposal.accept() no |
| API pública con seguridad | ✅ Implementado | HMAC token + anti-bot + throttle |
| Patient merge | ✅ Implementado | Atomic, audited, with dedup matching |
| Overbooking prevention | ✅ Implementado | App-level + DB ExclusionConstraint |
| File storage (MinIO) | ✅ Implementado | 3 buckets: clinical, marketing, documents |
| Email integration | ✅ Configurado | Console backend en dev, Gmail SMTP en prod |
| Celery tasks | ✅ Implementado | Thumbnail generation, async tasks |
| OpenAPI schema | ✅ Implementado | drf-spectacular + Swagger UI + Redoc |
| i18n | ✅ Parcial | 6 idiomas en choices, Django i18n configurado |

### Features Faltantes

| Feature | Estado | Impacto |
|---------|--------|---------|
| Facturación/Invoice | ❌ No implementado | commerce app vacía |
| Payments processing | ❌ No implementado | Solo estado PAID en Sale, sin pasarela |
| Notificaciones (email/SMS) | ❌ No implementado | Solo email backend configurado |
| Reporting/Analytics | ❌ No implementado | Solo overview endpoint en Patient |
| Rate limiting en API privada | ❌ No implementado | Solo en endpoints públicos |
| Calendly integration | ❌ No implementado | integrations app vacía |
| Social media publishing | ⚠️ Deshabilitado | App existe pero está disabled |
| GDPR data export | ❌ No implementado | No hay endpoint de export |
| Backup/Restore | ❌ No implementado | Solo documentación |

---

## 6. CONTRADICCIONES DETECTADAS

| # | Contradicción | Ubicación |
|---|--------------|-----------|
| 1 | **Moneda default inconsistente:** Sale defaults to 'USD', Proposal defaults to 'EUR' | sales/models.py L88 vs proposals/models.py L144 |
| 2 | **Dos inventarios paralelos:** Product.stock_quantity (legacy) vs StockOnHand.quantity_on_hand (nuevo) | products/models.py L26 vs stock/models.py StockOnHand |
| 3 | **Tres modelos de fotos:** SkinPhoto (legacy photos/), ClinicalPhoto (clinical/), ClinicalMedia (clinical/) — tres vías para subir fotos | photos/models.py vs clinical/models.py L1220, L1780 |
| 4 | **Patrón TenantModel inconsistente:** Algunos modelos heredan TenantModel, otros (Sale, TreatmentPlan) usan TenantManager directamente con FK explícita | Múltiples archivos |
| 5 | **Phone country code inconsistente:** POS asume +52 (México), LegalEntity tiene campos franceses (SIREN/SIRET) | pos/utils.py L29 vs legal/models.py |
| 6 | **Soft delete inconsistente:** Algunos usan `is_deleted` bool, ClinicalMedia usa `deleted_at` nullable, muchos no tienen soft delete | Múltiples modelos |

---

## 7. RIESGOS PRIORIZADOS

### 🔴 P0 — Bloqueante (impide operación)

| # | Riesgo | Impacto | Ubicación |
|---|--------|---------|-----------|
| 1 | **NameError en stock/models.py** — constantes auto-referenciadas impiden arranque de Django | No arranca la app. Tests no ejecutables. Deploy imposible. | stock/models.py L22-24 |
| 2 | **ProductSerializer expone legal_entity** via `fields='__all__'` — leak de tenant ID | Información cross-tenant expuesta en API | products/serializers.py L11 |

### 🟡 P1 — Alto (riesgo de seguridad o integridad)

| # | Riesgo | Impacto | Ubicación |
|---|--------|---------|-----------|
| 3 | Management command con password hardcoded "Libertad" | Si se ejecuta en producción, cuenta admin predecible | authz/management/commands/create_admin_dev.py |
| 4 | TenantManager retorna tabla completa si tenant es None | Queries sin contexto de tenant ven todos los registros | core/managers.py |
| 5 | Modelos sin TenantModel (PatientGuardian, PractitionerSchedule, ClinicalAuditLog) podrían ser accesibles cross-tenant | Aislamiento incompleto si se consultan directamente | clinical/models.py |
| 6 | Moneda inconsistente USD/EUR entre Sale y Proposal | Precios incorrectos al convertir Proposal → Sale | sales/models.py L88 |
| 7 | ops.AuditLog sin TenantManager — queries admin ven cross-tenant | Logs de auditoría no filtrados por tenant | ops/models.py |

### 🟢 P2 — Medio (tech debt, mantenibilidad)

| # | Riesgo | Impacto | Ubicación |
|---|--------|---------|-----------|
| 8 | Tres modelos de fotos (SkinPhoto, ClinicalPhoto, ClinicalMedia) | Confusión, duplicación, inconsistencia | photos/ + clinical/ |
| 9 | Dos fuentes de verdad para stock (Product.stock_quantity vs StockOnHand) | Stock desincronizado | products/ + stock/ |
| 10 | clinical/views.py tiene 2,604 líneas | Dificultad de mantenimiento | clinical/views.py |
| 11 | Social app deshabilitada con riesgo de path traversal | Vulnerabilidad latente si se habilita | social/views.py |
| 12 | POS hardcodea +52 (México) como country code | Usuarios en Francia tendrán problemas | pos/utils.py |
| 13 | Commerce + Integrations son apps vacías | Modulos registrados pero inútiles | commerce/, integrations/ |

---

## 8. ORDEN DE REMEDIACIÓN SUGERIDO

| Prioridad | Acción | Esfuerzo | Impacto |
|-----------|--------|----------|---------|
| 1 | **Fix NameError en stock/models.py** — definir constantes reales: `LABEL_CREATED_AT = _('Created at')`, `LABEL_UPDATED_AT = _('Updated at')`, `FK_PRODUCT = 'products.Product'` | 5 min | Desbloquea toda la app |
| 2 | **Fix ProductSerializer** — cambiar `fields='__all__'` por lista explícita sin `legal_entity` | 5 min | Cierra leak de tenant |
| 3 | **Eliminar/proteger management commands** — mover a dev-only o borrar create_admin_dev | 10 min | Elimina riesgo de credenciales |
| 4 | **Unificar default currency** — cambiar Sale.currency default a 'EUR' | 5 min | Consistencia financiera |
| 5 | **Ejecutar test suite** — verificar cobertura y estado real tras fix #1 | 30 min | Base de confianza |
| 6 | **Auditar TenantManager fallback None** — decidir: raise error o retornar vacío | 1h | Hardening multi-tenant |
| 7 | **Documentar decisiones de tenant** para modelos sin TenantModel | 2h | Claridad arquitectónica |
| 8 | **Planificar consolidación de fotos** — elegir modelo canónico, migrar datos, deprecar legacy | 1-2 días | Reducir deuda técnica |
| 9 | **Consolidar inventario** — deprecar Product.stock_quantity, usar solo StockOnHand | 1 día | Single source of truth |
| 10 | **Splitear clinical/views.py** — extraer ViewSets a archivos separados | 2h | Mantenibilidad |

---

## EVIDENCE PACK

### A. Archivos Inspeccionados

**Total: 238 archivos Python en apps/api/**

Archivos leídos completa o parcialmente durante esta auditoría:

| Archivo | Líneas | Método |
|---------|--------|--------|
| config/settings.py | 360 | Lectura directa |
| config/urls.py | 65 | Lectura directa |
| core/models.py | — | Subagent deep inspection |
| core/tenant_model.py | — | Subagent deep inspection |
| core/tenant_context.py | — | Subagent deep inspection |
| core/managers.py | — | Subagent deep inspection |
| core/middleware.py | — | Subagent deep inspection |
| core/auth_views.py | — | Subagent deep inspection |
| core/views.py | — | Subagent deep inspection |
| core/urls.py | — | Subagent deep inspection |
| core/serializers.py | — | Subagent deep inspection |
| core/observability/*.py | — | Subagent deep inspection |
| authz/models.py | — | Subagent deep inspection |
| authz/permissions.py | — | Subagent deep inspection |
| authz/serializers.py | — | Subagent deep inspection |
| authz/serializers_users.py | — | Subagent deep inspection |
| authz/views.py | — | Subagent deep inspection |
| authz/views_users.py | — | Subagent deep inspection |
| authz/urls.py | — | Subagent deep inspection |
| authz/management/commands/*.py | — | Subagent deep inspection |
| legal/models.py | — | Subagent deep inspection |
| legal/views.py | — | Subagent deep inspection |
| legal/serializers.py | — | Subagent deep inspection |
| legal/urls.py | — | Subagent deep inspection |
| clinical/models.py | 2,181 | Subagent deep inspection |
| clinical/services.py | 970 | Subagent deep inspection |
| clinical/views.py | 2,604 | Subagent deep inspection |
| clinical/serializers.py | 1,197 | Subagent deep inspection |
| clinical/permissions.py | 231 | Subagent deep inspection |
| clinical/signals.py | 60 | Subagent deep inspection |
| clinical/urls.py | 50 | Subagent deep inspection |
| clinical/views_consents.py | 458 | Subagent deep inspection |
| clinical/views_documents.py | 249 | Subagent deep inspection |
| clinical/views_photos.py | 252 | Subagent deep inspection |
| clinical/views_public_booking.py | 734 | Subagent deep inspection |
| clinical/urls_public_booking.py | 16 | Subagent deep inspection |
| clinical/serializers_consents.py | 176 | Subagent deep inspection |
| clinical/serializers_public_booking.py | 79 | Subagent deep inspection |
| clinical/services_public_booking.py | 207 | Subagent deep inspection |
| clinical/audit_access_log.py | 105 | Subagent deep inspection |
| clinical/attachment_counters.py | 43 | Subagent deep inspection |
| proposals/models.py | 503 | Subagent deep inspection |
| proposals/serializers.py | 187 | Subagent deep inspection |
| proposals/permissions.py | 98 | Subagent deep inspection |
| treatment_plans/models.py | — | Subagent deep inspection |
| treatment_plans/treatment_session_models.py | — | Subagent deep inspection |
| treatment_plans/views.py | — | Subagent deep inspection |
| treatment_plans/serializers.py | — | Subagent deep inspection |
| treatment_plans/treatment_session_views.py | — | Subagent deep inspection |
| treatment_plans/treatment_session_serializers.py | — | Subagent deep inspection |
| sales/models.py | 741 | Subagent deep inspection |
| sales/serializers.py | — | Subagent deep inspection |
| sales/services.py | 696 | Subagent deep inspection |
| sales/views.py | — | Subagent deep inspection |
| sales/permissions.py | — | Subagent deep inspection |
| sales/urls.py | — | Subagent deep inspection |
| stock/models.py | ~460 | Lectura directa + subagent |
| stock/serializers.py | — | Subagent deep inspection |
| stock/services.py | — | Subagent deep inspection |
| stock/views.py | — | Subagent deep inspection |
| stock/permissions.py | — | Subagent deep inspection |
| stock/urls.py | — | Subagent deep inspection |
| products/models.py | 53 | Subagent deep inspection |
| products/views.py | 18 | Subagent deep inspection |
| products/serializers.py | 14 | Subagent deep inspection |
| products/permissions.py | 40 | Subagent deep inspection |
| products/urls.py | 11 | Subagent deep inspection |
| documents/models.py | 107 | Subagent deep inspection |
| photos/models.py | 106 | Subagent deep inspection |
| photos/views.py | 33 | Subagent deep inspection |
| photos/serializers.py | 122 | Subagent deep inspection |
| photos/urls.py | 14 | Subagent deep inspection |
| photos/signals.py | 16 | Subagent deep inspection |
| photos/tasks.py | 57 | Subagent deep inspection |
| pos/views.py | — | Subagent deep inspection |
| pos/serializers.py | 54 | Subagent deep inspection |
| pos/permissions.py | 18 | Subagent deep inspection |
| pos/utils.py | 105 | Subagent deep inspection |
| pos/urls.py | 10 | Subagent deep inspection |
| ops/models.py | 146 | Subagent deep inspection |
| ops/services.py | 93 | Subagent deep inspection |
| website/models.py | 322 | Subagent deep inspection |
| website/views.py | 189 | Subagent deep inspection |
| website/serializers.py | 146 | Subagent deep inspection |
| website/urls.py | 20 | Subagent deep inspection |
| social/models.py | 145 | Subagent deep inspection |
| social/views.py | 125 | Subagent deep inspection |
| social/tasks.py | 97 | Subagent deep inspection |
| commerce/models.py | 3 | Subagent deep inspection |
| integrations/models.py | 5 | Subagent deep inspection |

### B. Comandos Ejecutados

```bash
find apps/api -type f -name "*.py" | xargs wc -l                    # → 58,955 total
find apps/api -type f -name "*.py" | xargs wc -l | sort -rn | head -30  # → top 30 files
find apps/api -path "*/migrations/0*.py" | wc -l                    # → 79 migrations
find apps/api -path "*/migrations/0*.py" | sed ... | uniq -c        # → per-app count
python3 -m pytest --tb=no -q                                        # → NameError (stock/models.py)
```

### C. Output Real de Comandos

**pytest output:**
```
NameError: name 'LABEL_CREATED_AT' is not defined
File "apps/api/apps/stock/models.py", line 22, in <module>
    LABEL_CREATED_AT = LABEL_CREATED_AT
```

**wc -l total:** `58,955 total`

**Migration count:** `79 total` across 12 apps

### D. Áreas No Verificadas

| Área | Razón |
|------|-------|
| Test pass/fail rates | App no arranca por NameError en stock/models.py |
| Runtime behavior | No se puede ejecutar servidor |
| Database schema real | Requiere DB connection + migraciones aplicadas |
| MinIO bucket existence | Requiere MinIO service running |
| Celery task execution | Requiere Redis + Celery worker |
| Real API response formats | Servidor no levanta |
| Production config | Solo settings.py base analizado; no hay settings_prod.py separado |

### E. Issues de Legacy / Naming

| Issue | Ubicación |
|-------|-----------|
| App `photos` marcada como "legacy" en settings.py | INSTALLED_APPS L56 |
| App `products` marcada como "legacy" en settings.py | INSTALLED_APPS L57 |
| Model `SkinPhoto` — nombre dermatología-específico para app genérica | photos/models.py |
| DB table `skin_photos` vs `clinical_photos` — naming inconsistente | photos/models.py vs clinical/models.py |
| `emr_derma_db` como nombre de BD — refleja origen dermatológico | config/settings.py L110 |
| Proyecto llamado "EMR Dermatology" pero es "Cosmetica 5" | config/settings.py L1 |
| `sale_number` unique sin generador automático implementado | sales/models.py L56 |

### F. Clasificación de Tenancy

| Modelo | Tenancy | Mecanismo |
|--------|---------|-----------|
| LegalEntity | ROOT (es el tenant) | N/A |
| Clinic | TENANT | TenantModel herencia |
| AppSettings | GLOBAL | Singleton pk=1 |
| User | TENANT (FK directa) | CheckConstraint user-required tenant |
| Role, UserRole | GLOBAL | Catálogo estático |
| Practitioner | TENANT via User | OneToOneField → User |
| Patient | TENANT | TenantModel herencia |
| PatientGuardian | IMPLICIT via Patient | FK → Patient (tenant-scoped) |
| PatientInsurance | IMPLICIT via Patient | FK → Patient (tenant-scoped) |
| PatientMergeLog | IMPLICIT via Patient | FK → Patient (tenant-scoped) |
| Encounter | TENANT | TenantModel herencia |
| Appointment | TENANT | TenantModel herencia |
| AppointmentType | TENANT | TenantModel herencia |
| Consent | TENANT | TenantModel herencia |
| ClinicalPhoto | TENANT | TenantModel herencia |
| ClinicalMedia | TENANT | TenantModel herencia |
| ClinicalAuditLog | NONE ⚠️ | Plain model, patient FK pero no legal_entity |
| ClinicalAccessLog | TENANT | legal_entity FK explícita |
| Treatment | TENANT | TenantModel herencia |
| EncounterTreatment | IMPLICIT via Encounter | FK → Encounter (tenant-scoped) |
| EncounterPhoto | IMPLICIT via Encounter | FK → Encounter (tenant-scoped) |
| EncounterDocument | IMPLICIT via Encounter | FK → Encounter (tenant-scoped) |
| PractitionerBlock | TENANT | TenantModel herencia |
| PractitionerTreatment | IMPLICIT via Practitioner | FK → Practitioner |
| PractitionerSchedule | IMPLICIT via Practitioner | FK → Practitioner |
| Proposal | IMPLICIT via Patient/Encounter | FKs a modelos tenant-scoped |
| ProposalLine | IMPLICIT via Proposal | FK → Proposal |
| TreatmentPlan | TENANT | TenantManager + legal_entity FK explícita |
| TreatmentSession | TENANT | TenantModel herencia |
| Sale | TENANT | TenantManager + legal_entity FK explícita |
| SaleLine | IMPLICIT via Sale | FK → Sale |
| SaleRefund | IMPLICIT via Sale | FK → Sale |
| SaleRefundLine | IMPLICIT via SaleRefund | FK → SaleRefund |
| Product | TENANT | TenantModel herencia |
| Document | TENANT | TenantModel herencia |
| SkinPhoto (legacy) | TENANT | TenantModel herencia |
| StockLocation | TENANT | TenantModel herencia |
| StockBatch | TENANT | TenantModel herencia |
| StockMove | TENANT | TenantModel herencia |
| StockOnHand | TENANT | TenantModel herencia |
| AuditLog (ops) | TENANT (FK) ⚠️ no filtered | legal_entity FK NOT NULL, pero sin TenantManager |
| WebsiteSettings | GLOBAL | Singleton |
| Page, Post, Service | GLOBAL | Public CMS content |
| StaffMember | GLOBAL | Public CMS content |
| MarketingMediaAsset | GLOBAL | Public assets |
| Lead | GLOBAL | Public form submissions |
| InstagramPost | GLOBAL | Marketing content |
| InstagramHashtag | GLOBAL | Hashtag catalog |

### G. Confirmación de Exhaustividad

| Criterio | Cumplido |
|----------|----------|
| Todas las 17 apps Django inspeccionadas | ✅ |
| Todos los modelos documentados con campos y FKs | ✅ |
| Todas las state machines mapeadas con transiciones | ✅ |
| Todos los ViewSets documentados con permisos | ✅ |
| Todas las URL patterns listadas | ✅ |
| Todos los services analizados | ✅ |
| Settings completo analizado | ✅ |
| Middleware chain documentada | ✅ |
| Management commands inspeccionados | ✅ |
| Test suite intentada ejecutar | ✅ (falló por bug) |
| Migraciones contadas | ✅ (79 total) |
| Archivos más grandes identificados | ✅ |
| Tenant classification completa | ✅ |
| CERO cambios de código realizados | ✅ |

---

> **FIN DE AUDITORÍA — Solo diagnóstico, cero cambios**
