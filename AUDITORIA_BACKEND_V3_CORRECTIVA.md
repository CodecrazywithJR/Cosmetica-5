# V3 Correctiva sobre V2

---

## 1. Secciones de V2 que se mantienen válidas

Las siguientes secciones de `AUDITORIA_BACKEND_EXHAUSTIVA_V2.md` se mantienen tal cual, sin necesidad de corrección:

- **§1 Resumen Ejecutivo** — contenido factual correcto
- **§2 Mapa del Repositorio** — estructura y conteos verificados
- **§3 Auditoría Módulo por Módulo (3.1 a 3.17)** — hallazgos, modelos, FKs, state machines, permisos, services
- **§6 Contradicciones Detectadas** — las 6 contradicciones están soportadas por evidencia real (ver Evidence Pack C más abajo)
- **§7 Riesgos Priorizados** — hallazgos y severidades correctos

---

## 2. Secciones corregidas / sustituidas

### 2.1 MATRIZ DE MADUREZ (sustituye §4 completa)

| Módulo | Modelado de datos | API | Reglas backend | Permisos/RBAC | Tests | Estado general | Comentario corto |
|--------|-------------------|-----|----------------|---------------|-------|----------------|------------------|
| core | Sólido | Sólido | Sólido | Sólido | No verificable | Sólido | Tenant infra, middleware, auth JWT completos |
| authz | Sólido | Sólido | Sólido | Sólido | No verificable | Sólido | User, Role, Practitioner, audit log, CheckConstraint |
| legal | Sólido | Sólido | Medio | Sólido | No verificable | Medio | LegalEntity completo; sin validación SIREN/SIRET |
| clinical | Sólido | Sólido | Sólido | Sólido | No verificable | Sólido | Módulo más maduro; state machines, merge, availability |
| proposals | Sólido | Sólido | Sólido | Sólido | No verificable | Medio | State machine + immutability; sin TenantModel directo |
| treatment_plans | Sólido | Medio | Sólido | Medio | No verificable | Medio | State machine ok; API read-only; patrón tenant mixto |
| sales | Sólido | Sólido | Sólido | Sólido | No verificable | Medio | Flujo completo; currency default 'USD' inconsistente |
| stock | Débil | Medio | Sólido | Medio | No verificable | Muy débil | NameError impide carga del módulo; servicios FEFO diseñados |
| products | Medio | Medio | Débil | Medio | No verificable | Débil | Serializer expone legal_entity; stock_quantity duplicado |
| documents | Sólido | Ausente | Ausente | Ausente | No verificable | Muy débil | Solo modelo, sin API/views/urls/permisos |
| photos | Sólido | Sólido | Medio | Sólido | No verificable | Medio | Legacy; duplicación con ClinicalPhoto/ClinicalMedia |
| pos | Ausente | Medio | Medio | Sólido | No verificable | Medio | Sin modelo propio; opera sobre Patient; phone +52 hardcoded |
| ops | Sólido | Ausente | Sólido | Ausente | No verificable | Débil | Modelo inmutable correcto; sin API ni TenantManager |
| website | Sólido | Sólido | Medio | Sólido | No verificable | Verde pero incompleto | Público; rate-limit en leads; sin tenant (intencionado) |
| social | Medio | Medio | Débil | Débil | No verificable | Muy débil | Deshabilitada; path traversal risk; sin RBAC real |
| commerce | Ausente | Ausente | Ausente | Ausente | Ausente | Ausente | Placeholder vacío — "PASO 2" |
| integrations | Ausente | Ausente | Ausente | Ausente | Ausente | Ausente | Placeholder vacío — sin funcionalidad |

**Nota sobre Tests:** Todos marcados "No verificable" porque `stock/models.py` L22-24 contiene un NameError que impide que Django cargue. Ver Evidence Pack C, comando §C.7.

---

### 2.2 MATRIZ DE GAPS (sustituye §5 completa)

| Requerimiento | Evidencia en código | Estado | Gap exacto |
|---|---|---|---|
| Multi-tenant real con LegalEntity | `legal/models.py:27` `class LegalEntity(models.Model)` + `core/tenant_model.py:35` `class TenantModel` con FK a LegalEntity + `core/managers.py` TenantManager auto-filtra | Implementado | TenantManager retorna tabla completa si `get_current_tenant()` es None (sin raise) |
| Clinic model | `core/models.py:59` `class Clinic(models.Model)` con FK a LegalEntity (PROTECT) + TenantManager | Implementado | Ninguno |
| Separación LegalEntity vs Clinic | LegalEntity en `legal/models.py:27`, Clinic en `core/models.py:59`, FK `legal_entity` en Clinic L80 (PROTECT) | Implementado | Ninguno |
| Roles oficiales | `authz/models.py:133-141` RoleChoices: admin, practitioner, reception, marketing, accounting | Implementado | Ninguno |
| Superuser bypass | `authz/permissions.py:25` `if request.user.is_superuser: return True` | Implementado | Ninguno |
| Patients por legal entity | `clinical/models.py:250` Patient hereda TenantModel → legal_entity FK + PatientManager filtra tenant+alive | Implementado | Ninguno |
| Appointments operativos reales | `clinical/models.py:906` Appointment con 6-status state machine (L1071-1075), attend workflow (`views.py:1182-1298`), start-treatment-session (`views.py:1300-1422`) | Implementado | Ninguno |
| Encounter con state machine | `clinical/models.py:806-830` `_validate_status_transition()`: draft→{finalized,cancelled}; finalized y cancelled son terminales | Implementado | Ninguno |
| Proposal desde encounter | `clinical/services.py:424` `generate_charge_proposal_from_encounter()` — requiere encounter FINALIZED, OneToOneField garantiza idempotencia | Implementado | Ninguno |
| Treatment plan desde aceptación de proposal | `proposals/models.py:321-341` `accept()` crea TreatmentPlan para líneas `full_package` dentro de `transaction.atomic` | Implementado | Solo para líneas tipo `full_package`; líneas `per_session` no generan plan |
| Separación clínico vs financiero | Encounter (clinical) → Proposal (proposals) → Sale (sales) — tres apps separadas; `services.py:424` exige encounter FINALIZED antes de generar propuesta; Sale se crea explícitamente desde Proposal.accept() | Implementado | Ninguno |
| Soft delete coherente | Patient L379, Encounter L726, Appointment L990, ClinicalPhoto L1389 usan `is_deleted: BooleanField`; ClinicalMedia L2033 usa `deleted_at: DateTimeField`; Document L68 usa `is_deleted: BooleanField` | Implementado pero inconsistente | ClinicalMedia usa patrón distinto (deleted_at nullable vs is_deleted bool). Proposal, Sale, TreatmentPlan, TreatmentSession, Treatment NO tienen soft delete |
| Audit logging clínico | `clinical/models.py:1505` ClinicalAuditLog + `clinical/audit_access_log.py:40` ClinicalAccessLog + `ops/models.py:61` AuditLog (append-only, immutable) + `authz/models.py:215` UserAuditLog | Implementado | ClinicalAuditLog no tiene FK a legal_entity → sin aislamiento directo por tenant |
| Terminal states inmutables | `proposals/models.py:220` bloquea save en TERMINAL_STATES; `sales/models.py:197` `is_terminal_status`; `treatment_plans/models.py:232` bloquea en TERMINAL_STATES; `treatment_session_models.py` bloquea save en terminal; `stock/models.py` StockMove bloquea update+delete | Implementado | Encounter no bloquea re-save explícitamente; solo valida transiciones de status en `_validate_status_transition` |
| Backend source of truth para estados | State machines en model.save() para Encounter, Appointment; métodos send()/accept()/cancel() para Proposal; activate()/cancel()/record_session_completed() para TreatmentPlan; transition_to() para Sale | Implementado | Ninguno |
| Multiidioma correctamente soportado en backend/API | `settings.py:136` USE_I18N=True; Patient.preferred_language (6 choices L287); website models con campo language; 6 LanguageChoices en clinical/models.py L33 | Parcialmente implementado | No existen archivos .po/.mo de traducción. USE_I18N=True pero sin catálogos de traducción reales. Solo i18n a nivel de choices de modelo, no de mensajes de API |
| Tests que cubren reglas críticas | 58 archivos en `apps/api/tests/` incluyendo: test_proposal_state_machine, test_treatment_session_api, test_clinical_sales_integration, test_layer3_a_sales_stock, test_layer3_b_refund_stock, test_tenant_mandatory, test_admin_bypass_protection | No verificable | NameError en `stock/models.py:22` impide que Django cargue → pytest no puede coleccionar ni ejecutar ningún test |

---

### 2.3 ORDEN DE SANEAMIENTO (sustituye §8 completa)

| Prioridad | Área | Motivo |
|-----------|------|--------|
| 1 | stock/models.py constants | NameError bloqueante impide arranque de toda la aplicación |
| 2 | products/serializers.py `fields='__all__'` | Expone legal_entity en API — leak de tenant |
| 3 | Management commands dev (create_admin_dev) | Password hardcoded en codebase de producción |
| 4 | Currency default inconsistente (Sale vs Proposal) | Inconsistencia financiera USD/EUR entre módulos enlazados |
| 5 | Ejecución completa del test suite | Tras fix #1, validar estado real de la cobertura |
| 6 | TenantManager fallback cuando tenant es None | Decidir política: raise error o queryset vacío, no tabla completa |
| 7 | Documentar decisiones de tenant para modelos sin TenantModel | Clarificar si PatientGuardian, PractitionerSchedule, ClinicalAuditLog son intencionalmente implícitos |
| 8 | Consolidación de modelos de fotos | Tres modelos (SkinPhoto, ClinicalPhoto, ClinicalMedia) para misma función |
| 9 | Consolidación de inventario | Product.stock_quantity vs StockOnHand.quantity_on_hand: dos fuentes de verdad |
| 10 | Split de clinical/views.py | 2,604 líneas en un solo archivo dificulta mantenimiento |

---

## 3. Evidence Pack Final

### A. Lista exacta de archivos inspeccionados

**config/**
- `config/settings.py`, `config/urls.py`, `config/wsgi.py`, `config/asgi.py`, `config/celery.py`

**core/**
- `core/models.py`, `core/tenant_model.py`, `core/tenant_context.py`, `core/managers.py`, `core/middleware.py`, `core/auth_views.py`, `core/views.py`, `core/urls.py`, `core/serializers.py`, `core/observability/correlation.py`, `core/observability/health.py`, `core/observability/logging.py`

**authz/**
- `authz/models.py`, `authz/permissions.py`, `authz/serializers.py`, `authz/serializers_users.py`, `authz/views.py`, `authz/views_users.py`, `authz/urls.py`, `authz/management/commands/create_admin_dev.py`, `authz/management/commands/ensure_demo_user_roles.py`

**legal/**
- `legal/models.py`, `legal/views.py`, `legal/serializers.py`, `legal/urls.py`

**clinical/**
- `clinical/models.py`, `clinical/services.py`, `clinical/views.py`, `clinical/serializers.py`, `clinical/permissions.py`, `clinical/signals.py`, `clinical/urls.py`, `clinical/views_consents.py`, `clinical/views_documents.py`, `clinical/views_photos.py`, `clinical/views_public_booking.py`, `clinical/urls_public_booking.py`, `clinical/serializers_consents.py`, `clinical/serializers_proposals.py`, `clinical/serializers_public_booking.py`, `clinical/services_public_booking.py`, `clinical/audit_access_log.py`, `clinical/attachment_counters.py`

**proposals/**
- `proposals/models.py`, `proposals/serializers.py`, `proposals/permissions.py`

**treatment_plans/**
- `treatment_plans/models.py`, `treatment_plans/treatment_session_models.py`, `treatment_plans/views.py`, `treatment_plans/serializers.py`, `treatment_plans/treatment_session_views.py`, `treatment_plans/treatment_session_serializers.py`

**sales/**
- `sales/models.py`, `sales/serializers.py`, `sales/services.py`, `sales/views.py`, `sales/permissions.py`, `sales/urls.py`

**stock/**
- `stock/models.py`, `stock/serializers.py`, `stock/services.py`, `stock/views.py`, `stock/permissions.py`, `stock/urls.py`

**products/**
- `products/models.py`, `products/views.py`, `products/serializers.py`, `products/permissions.py`, `products/urls.py`, `products/admin.py`

**documents/**
- `documents/models.py`, `documents/admin.py`, `documents/apps.py`

**photos/**
- `photos/models.py`, `photos/views.py`, `photos/serializers.py`, `photos/urls.py`, `photos/signals.py`, `photos/tasks.py`, `photos/admin.py`

**pos/**
- `pos/views.py`, `pos/serializers.py`, `pos/permissions.py`, `pos/utils.py`, `pos/urls.py`

**ops/**
- `ops/models.py`, `ops/services.py`, `ops/admin.py`

**website/**
- `website/models.py`, `website/views.py`, `website/serializers.py`, `website/urls.py`, `website/admin.py`

**social/**
- `social/models.py`, `social/views.py`, `social/serializers.py`, `social/urls.py`, `social/tasks.py`, `social/admin.py`

**commerce/**
- `commerce/models.py`, `commerce/admin.py`, `commerce/apps.py`

**integrations/**
- `integrations/models.py`, `integrations/views.py`, `integrations/urls.py`, `integrations/admin.py`, `integrations/apps.py`

---

### B. Comandos exactos usados

```
find apps/api/apps -maxdepth 1 -type d | sort
find apps/api -type f -name "*.py" | xargs wc -l | tail -5
find apps/api -type f -name "*.py" | xargs wc -l | sort -rn | head -30
find apps/api -path "*/migrations/0*.py" | wc -l
find apps/api -path "*/migrations/0*.py" | sed 's|/migrations/.*||' | sort | uniq -c | sort -rn
grep -rn 'class.*TenantModel' apps/api/apps/core/tenant_model.py
sed -n '35,75p' apps/api/apps/core/tenant_model.py
grep -rn 'class.*TenantModel' apps/api/apps/*/models.py
grep -rn 'TenantManager' apps/api/apps/*/models.py | grep 'objects'
grep -n 'class LegalEntity' apps/api/apps/legal/models.py
grep -n 'class Clinic' apps/api/apps/core/models.py
sed -n '59,100p' apps/api/apps/core/models.py
grep -rn 'is_deleted\|deleted_at\|soft.delete\|soft_delete' apps/api/apps/*/models.py
grep -n 'currency' apps/api/apps/sales/models.py
grep -n 'currency' apps/api/apps/proposals/models.py
sed -n '113,118p' apps/api/apps/sales/models.py
sed -n '158,163p' apps/api/apps/proposals/models.py
grep -n 'stock_quantity' apps/api/apps/products/models.py
grep -n 'quantity_on_hand' apps/api/apps/stock/models.py
python3 -m pytest --co -q (dentro de apps/api con venv activo)
sed -n '20,25p' apps/api/apps/stock/models.py
grep -rn 'RoleChoices' apps/api/apps/authz/models.py
sed -n '133,145p' apps/api/apps/authz/models.py
grep -rn 'is_superuser' apps/api/apps/authz/permissions.py
sed -n '10,30p' apps/api/apps/authz/permissions.py
grep -rn "fields.*=.*'__all__'" apps/api/apps/products/serializers.py
grep -rn "SkinPhoto\|ClinicalPhoto\|ClinicalMedia" apps/api/apps/*/models.py | grep 'class \|db_table'
grep -rn 'EncounterStatusChoices\|_validate_status_transition' apps/api/apps/clinical/models.py
sed -n '806,830p' apps/api/apps/clinical/models.py
grep -rn 'generate_charge_proposal_from_encounter' apps/api/apps/clinical/services.py
sed -n '424,445p' apps/api/apps/clinical/services.py
grep -rn 'TreatmentPlan' apps/api/apps/proposals/models.py
sed -n '315,345p' apps/api/apps/proposals/models.py
grep -rn 'ClinicalAuditLog\|ClinicalAccessLog\|AuditLog' apps/api/apps/*/models.py | grep 'class '
grep -rn 'TERMINAL_STATES\|is_terminal' apps/api/apps/*/models.py
grep -rn 'USE_I18N\|LANGUAGE_CODE' apps/api/config/settings.py
find apps/api -name "*.po" -o -name "*.mo" -o -name "locale" -type d
find apps/api/tests -type f -name "*.py" | sort
grep -rn 'emr_derma_db\|EMR Dermatology\|skin_photos' apps/api/config/settings.py apps/api/apps/photos/models.py
cat apps/api/config/urls.py
```

---

### C. Output real de comandos

#### §C.1 Estructura del repo

```bash
find apps/api/apps -maxdepth 1 -type d | sort
```
```
apps/api/apps
apps/api/apps/authz
apps/api/apps/clinical
apps/api/apps/commerce
apps/api/apps/core
apps/api/apps/documents
apps/api/apps/integrations
apps/api/apps/legal
apps/api/apps/ops
apps/api/apps/photos
apps/api/apps/pos
apps/api/apps/products
apps/api/apps/proposals
apps/api/apps/sales
apps/api/apps/social
apps/api/apps/stock
apps/api/apps/treatment_plans
apps/api/apps/website
```
**Qué demuestra:** 17 apps Django bajo `apps/api/apps/`.

---

#### §C.2 Endpoints / URLs

```bash
cat apps/api/config/urls.py
```
```python
urlpatterns = [
    path('healthz', HealthzView.as_view(), name='healthz'),
    path('readyz', ReadyzView.as_view(), name='readyz'),
    path('admin/', admin.site.urls),
    path('public/', include('apps.website.urls')),
    path('public/booking/', include('apps.clinical.urls_public_booking')),
    path('api/', include('apps.core.urls')),
    path('api/v1/', include('apps.authz.urls')),
    path('api/v1/clinical/', include('apps.clinical.urls')),
    path('api/photos/', include('apps.photos.urls')),
    path('api/products/', include('apps.products.urls')),
    path('api/stock/', include('apps.stock.urls')),
    path('api/sales/', include('apps.sales.urls')),
    path('api/v1/pos/', include('apps.pos.urls')),
    # path('api/social/', include('apps.social.urls')),  # DISABLED
    path('api/v1/system/', include('apps.legal.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', ...),
    path('api/schema/redoc/', ...),
]
```
**Qué demuestra:** Registro de rutas por app. `social` comentada. `commerce`, `integrations`, `documents`, `ops` no tienen URLs registradas.

---

#### §C.3 Tenancy / TenantModel / LegalEntity / Clinic

```bash
grep -rn 'class.*TenantModel' apps/api/apps/*/models.py
```
```
apps/api/apps/clinical/models.py:184:class ReferralSource(TenantModel):
apps/api/apps/clinical/models.py:250:class Patient(TenantModel):
apps/api/apps/clinical/models.py:658:class Encounter(TenantModel):
apps/api/apps/clinical/models.py:841:class AppointmentType(TenantModel):
apps/api/apps/clinical/models.py:906:class Appointment(TenantModel):
apps/api/apps/clinical/models.py:1270:class Consent(TenantModel):
apps/api/apps/clinical/models.py:1324:class ClinicalPhoto(TenantModel):
apps/api/apps/clinical/models.py:1686:class Treatment(TenantModel):
apps/api/apps/clinical/models.py:1836:class PractitionerBlock(TenantModel):
apps/api/apps/clinical/models.py:1957:class ClinicalMedia(TenantModel):
apps/api/apps/documents/models.py:12:class Document(TenantModel):
apps/api/apps/photos/models.py:18:class SkinPhoto(TenantModel):
apps/api/apps/products/models.py:10:class Product(TenantModel):
apps/api/apps/proposals/models.py:61:class Proposal(TenantModel):
apps/api/apps/stock/models.py:53:class StockLocation(TenantModel):
apps/api/apps/stock/models.py:88:class StockBatch(TenantModel):
apps/api/apps/stock/models.py:178:class StockMove(TenantModel):
apps/api/apps/stock/models.py:414:class StockOnHand(TenantModel):
```
**Qué demuestra:** 18 modelos heredan TenantModel directamente.

```bash
grep -rn 'TenantManager' apps/api/apps/*/models.py | grep 'objects'
```
```
apps/api/apps/core/models.py:94:    objects = TenantManager()
apps/api/apps/sales/models.py:41:    objects = TenantManager()
apps/api/apps/treatment_plans/models.py:74:    objects = TenantManager()
```
**Qué demuestra:** 3 modelos adicionales (Clinic, Sale, TreatmentPlan) usan TenantManager sin heredar TenantModel abstract — patrón mixto.

```bash
sed -n '35,75p' apps/api/apps/core/tenant_model.py
```
```python
class TenantModel(models.Model):
    legal_entity = models.ForeignKey(
        'legal.LegalEntity',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_index=True,
        related_name='%(app_label)s_%(class)s_set',
        help_text='Owning legal entity (tenant isolation).',
    )
    objects = TenantManager()
    unfiltered = models.Manager()
    def save(self, *args, **kwargs):
        if self.legal_entity_id is None:
            from apps.core.tenant_context import get_current_tenant
            tenant = get_current_tenant()
            if tenant is not None:
                self.legal_entity = tenant
        super().save(*args, **kwargs)
    class Meta:
        abstract = True
```
**Qué demuestra:** TenantModel es abstract con FK nullable a LegalEntity, auto-popula desde thread-local en save(), manager + escape hatch definidos.

```bash
sed -n '59,100p' apps/api/apps/core/models.py
```
```python
class Clinic(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey(
        'legal.LegalEntity',
        on_delete=models.PROTECT,
        related_name='clinics',
    )
    name = models.CharField(max_length=255)
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    country_code = models.CharField(max_length=2, blank=True, null=True)
    timezone = models.CharField(max_length=64, default='Europe/Paris')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = TenantManager()
    unfiltered = models.Manager()
```
**Qué demuestra:** Clinic modelo separado de LegalEntity, con FK PROTECT + TenantManager. Relación N Clinics → 1 LegalEntity.

---

#### §C.4 Soft delete

```bash
grep -rn 'is_deleted\|deleted_at' apps/api/apps/*/models.py | grep -v '__pycache__' | grep 'models\.\|BooleanField\|DateTimeField' | head -15
```
```
apps/api/apps/clinical/models.py:379:    is_deleted = models.BooleanField(default=False)
apps/api/apps/clinical/models.py:380:    deleted_at = models.DateTimeField(blank=True, null=True)
apps/api/apps/clinical/models.py:726:    is_deleted = models.BooleanField(default=False)
apps/api/apps/clinical/models.py:727:    deleted_at = models.DateTimeField(blank=True, null=True)
apps/api/apps/clinical/models.py:990:    is_deleted = models.BooleanField(default=False)
apps/api/apps/clinical/models.py:991:    deleted_at = models.DateTimeField(blank=True, null=True)
apps/api/apps/clinical/models.py:1389:    is_deleted = models.BooleanField(default=False)
apps/api/apps/clinical/models.py:1390:    deleted_at = models.DateTimeField(blank=True, null=True)
apps/api/apps/clinical/models.py:1873:    is_deleted = models.BooleanField(default=False)
apps/api/apps/clinical/models.py:1874:    deleted_at = models.DateTimeField(null=True, blank=True)
apps/api/apps/clinical/models.py:2033:    deleted_at = models.DateTimeField(
apps/api/apps/documents/models.py:68:    is_deleted = models.BooleanField(
apps/api/apps/documents/models.py:72:    deleted_at = models.DateTimeField(
```
**Qué demuestra:** Soft delete en Patient (L379), Encounter (L726), Appointment (L990), ClinicalPhoto (L1389), PractitionerBlock (L1873) usan `is_deleted: BooleanField`. ClinicalMedia (L2033) usa solo `deleted_at: DateTimeField` (patrón distinto). Document (L68) usa `is_deleted`. Proposal, Sale, TreatmentPlan, TreatmentSession NO tienen soft delete.

---

#### §C.5 Sales / billing / currency

```bash
sed -n '113,118p' apps/api/apps/sales/models.py
```
```python
    currency = models.CharField(
        _('Currency'),
        max_length=3,
        default='USD',
        help_text=_('ISO 4217 currency code')
    )
```

```bash
sed -n '158,163p' apps/api/apps/proposals/models.py
```
```python
    currency = models.CharField(
        max_length=3,
        default='EUR',
        help_text='Currency code (ISO 4217)'
    )
```
**Qué demuestra:** Sale default='USD' (sales/models.py:116), Proposal default='EUR' (proposals/models.py:160). Inconsistencia directa en flujo Proposal→Sale.

---

#### §C.6 Inventario duplicado

```bash
grep -n 'stock_quantity' apps/api/apps/products/models.py
```
```
26:    stock_quantity = models.IntegerField(_('Stock Quantity'), default=0)
53:        return self.stock_quantity <= self.low_stock_threshold
```

```bash
grep -n 'quantity_on_hand' apps/api/apps/stock/models.py
```
```
446:    quantity_on_hand = models.IntegerField(
465:                check=models.Q(quantity_on_hand__gte=0),
```
**Qué demuestra:** `Product.stock_quantity` (products/models.py:26) y `StockOnHand.quantity_on_hand` (stock/models.py:446) son dos fuentes de verdad para stock del mismo producto.

---

#### §C.7 Tests — imposibilidad real de ejecutarlos

```bash
cd apps/api && python3 -m pytest --co -q
```
```
prometheus_client not available, using no-op metrics
NameError: name 'LABEL_CREATED_AT' is not defined
```

```bash
sed -n '20,25p' apps/api/apps/stock/models.py
```
```python
# Reusable verbose_name / FK reference constants (avoid S1192)
LABEL_CREATED_AT = LABEL_CREATED_AT
LABEL_UPDATED_AT = LABEL_UPDATED_AT
FK_PRODUCT = FK_PRODUCT
```
**Qué demuestra:** Las constantes se auto-referencian (circular). Django no puede importar `stock.models` → falla `apps.populate(INSTALLED_APPS)` → pytest no puede coleccionar tests → **ningún test es ejecutable**.

---

#### §C.8 Migraciones

```bash
find apps/api -path "*/migrations/0*.py" | wc -l
```
```
79
```

```bash
find apps/api -path "*/migrations/0*.py" | sed 's|/migrations/.*||' | sort | uniq -c | sort -rn
```
```
 31 apps/api/apps/clinical
 10 apps/api/apps/authz
  7 apps/api/apps/sales
  5 apps/api/apps/treatment_plans
  5 apps/api/apps/stock
  5 apps/api/apps/proposals
  4 apps/api/apps/photos
  4 apps/api/apps/legal
  3 apps/api/apps/core
  2 apps/api/apps/products
  2 apps/api/apps/documents
  1 apps/api/apps/ops
```
**Qué demuestra:** 79 migraciones totales. clinical tiene 31 (módulo más evolucionado). commerce, integrations, website, social, pos no tienen migraciones propias.

---

#### §C.9 Legacy naming

```bash
grep -rn 'emr_derma_db\|EMR Dermatology\|skin_photos' apps/api/config/settings.py apps/api/apps/photos/models.py
```
```
apps/api/config/settings.py:2:Django settings for EMR Dermatology + POS Cosmetics project.
apps/api/config/settings.py:109:        'NAME': os.environ.get('DATABASE_NAME', 'emr_derma_db'),
apps/api/config/settings.py:224:    'TITLE': 'EMR Dermatology + POS Cosmetics API',
apps/api/apps/photos/models.py:67:        db_table = 'skin_photos'
```
**Qué demuestra:** Nombres legacy: BD `emr_derma_db`, título API `EMR Dermatology`, tabla `skin_photos`. El proyecto se llama "Cosmetica 5" pero el código conserva naming dermatológico.

---

#### §C.10 Roles y superuser bypass

```bash
sed -n '133,141p' apps/api/apps/authz/models.py
```
```python
class RoleChoices(models.TextChoices):
    """Fixed role names from DOMAIN_MODEL.md"""
    ADMIN = 'admin', 'Admin'
    PRACTITIONER = 'practitioner', 'Practitioner'
    RECEPTION = 'reception', 'Reception'
    MARKETING = 'marketing', 'Marketing'
    ACCOUNTING = 'accounting', 'Accounting'
```

```bash
sed -n '25,26p' apps/api/apps/authz/permissions.py
```
```python
        if request.user.is_superuser:
            return True
```
**Qué demuestra:** 5 roles fijos definidos en `authz/models.py:133-141`. Superuser bypass explícito en `authz/permissions.py:25`.

---

#### §C.11 Encounter state machine

```bash
sed -n '806,830p' apps/api/apps/clinical/models.py
```
```python
    def _validate_status_transition(self, update_fields):
        if update_fields is not None and 'status' not in update_fields:
            return
        _old = (
            Encounter.unfiltered
            .filter(pk=self.pk)
            .values('status')
            .first()
        )
        if not _old or _old['status'] == self.status:
            return
        _ALLOWED = {
            EncounterStatusChoices.DRAFT: {
                EncounterStatusChoices.FINALIZED,
                EncounterStatusChoices.CANCELLED,
            },
        }
        valid_next = _ALLOWED.get(_old['status'], set())
        if self.status not in valid_next:
            from django.core.exceptions import ValidationError as DjangoValidationError
            raise DjangoValidationError({
                'status': (
                    f"Invalid encounter status transition from "
                    f"'{_old['status']}' to '{self.status}'. "
```
**Qué demuestra:** State machine implementada en `_validate_status_transition()`. Solo `DRAFT` tiene transiciones permitidas (`→ FINALIZED, → CANCELLED`). `FINALIZED` y `CANCELLED` no están en `_ALLOWED` → son terminales (any transition raises ValidationError).

---

#### §C.12 Proposal desde encounter + TreatmentPlan desde aceptación

```bash
sed -n '424,437p' apps/api/apps/clinical/services.py
```
```python
def generate_charge_proposal_from_encounter(
    encounter,
    created_by: User,
    notes: Optional[str] = None
):
    """
    Generate a ClinicalChargeProposal from a finalized Encounter.
    ...
    Business Rules:
    - Encounter must be FINALIZED (not draft, not cancelled)
    - One proposal per encounter (idempotency via OneToOneField)
    - Proposal lines derived from EncounterTreatment
    - Pricing snapshot: Uses EncounterTreatment.effective_price
    - NO TAX calculation (deferred to future fiscal module)
```

```bash
sed -n '321,341p' apps/api/apps/proposals/models.py
```
```python
            # 3. Create TreatmentPlans for full_package lines
            from apps.treatment_plans.models import TreatmentPlan
            full_package_lines = self.lines.filter(
                type=ProposalLineTypeChoices.FULL_PACKAGE
            )
            for pkg_line in full_package_lines:
                TreatmentPlan.objects.create(
                    patient=self.patient,
                    practitioner=self.practitioner,
                    proposal=self,
                    proposal_line=pkg_line,
                    sale=sale,
                    package_name=pkg_line.treatment_name,
                    description_snapshot=pkg_line.description or '',
                    planned_sessions=pkg_line.quantity,
                    completed_sessions=0,
                    total_price_snapshot=pkg_line.line_total,
                    currency=self.currency,
                )
```
**Qué demuestra:** Flujo Encounter(finalized) → `generate_charge_proposal_from_encounter()` → Proposal → `accept()` → Sale + TreatmentPlan(s). TreatmentPlan se crea solo para líneas `full_package`.

---

#### §C.13 Tres modelos de fotos

```bash
grep -rn "SkinPhoto\|ClinicalPhoto\|ClinicalMedia" apps/api/apps/*/models.py | grep 'class \|db_table'
```
```
apps/api/apps/clinical/models.py:1324:class ClinicalPhoto(TenantModel):
apps/api/apps/clinical/models.py:1957:class ClinicalMedia(TenantModel):
apps/api/apps/clinical/models.py:2041:        db_table = 'clinical_media'
apps/api/apps/photos/models.py:18:class SkinPhoto(TenantModel):
apps/api/apps/photos/models.py:67:        db_table = 'skin_photos'
```
**Qué demuestra:** Tres modelos distintos para fotos/media: `SkinPhoto` (legacy, `photos/`), `ClinicalPhoto` (clinical), `ClinicalMedia` (clinical). Tablas diferentes: `skin_photos`, `clinical_photo` (default), `clinical_media`.

---

#### §C.14 ProductSerializer leak

```bash
grep -rn "fields.*=.*'__all__'" apps/api/apps/products/serializers.py
```
```
apps/api/apps/products/serializers.py:11:        fields = '__all__'
```
**Qué demuestra:** `ProductSerializer` usa `fields = '__all__'` → expone campo `legal_entity` heredado de TenantModel. Un usuario autenticado puede ver/intentar escribir el ID de otro tenant.

---

#### §C.15 Archivos de i18n

```bash
find apps/api -name "*.po" -o -name "*.mo" -o -name "locale" -type d
```
```
(sin output — 0 resultados)
```
**Qué demuestra:** `USE_I18N=True` en settings pero no existen archivos `.po`, `.mo` ni directorios `locale/`. El soporte multiidioma se limita a choices en modelos, no hay traducción real de mensajes de API.

---

#### §C.16 Test files existentes

```bash
find apps/api/tests -type f -name "*.py" | wc -l
```
```
58
```
**Qué demuestra:** 58 archivos de test existen (57 tests + 1 `__init__.py`). Incluyen: `test_tenant_mandatory`, `test_admin_bypass_protection`, `test_proposal_state_machine`, `test_clinical_sales_integration`, `test_layer3_a_sales_stock`, `test_layer3_b_refund_stock`, `test_layer3_c_partial_refund`, `test_treatment_session_api`, `test_public_booking`, entre otros. Ninguno ejecutable por el NameError en stock/models.py.

---

### D. Áreas no verificadas

| Qué no se pudo verificar | Por qué | Impacto |
|---|---|---|
| Resultado de ejecución del test suite (pass/fail/skip) | `stock/models.py:22` NameError impide que Django cargue → pytest no colecciona | No se puede confirmar cobertura real ni estado de reglas de negocio en runtime |
| Schema real de la BD (tablas, constraints, índices) | Requiere conexión a PostgreSQL con migraciones aplicadas | Las constraints DB (ExclusionConstraint, CheckConstraint) no se pueden verificar como aplicadas |
| Respuestas reales de la API | Servidor Django no puede arrancar por NameError | Formatos de respuesta, status codes, y behavior solo verificados por lectura de código |
| Servicios externos en runtime (MinIO, Redis, Celery) | No corriendo en entorno de auditoría | Storage de fotos/documentos, colas async, y thumbnails no verificables |
| Config de producción específica | Solo existe `config/settings.py` base (sin `settings_prod.py` separado); variables sensibles vienen de env vars | No se puede confirmar que SECRET_KEY, DB password, JWT key sean distintos en prod |

---

### E. Legacy / naming contradictorio

**Existe:** Sí.

**Dónde e impacto:**

| Instancia | Archivo:línea | Impacto |
|---|---|---|
| BD nombrada `emr_derma_db` | `config/settings.py:109` | Nombre dermatología-específico para proyecto "Cosmetica 5" |
| Título API `EMR Dermatology + POS Cosmetics` | `config/settings.py:224` | Confusión de identidad en schema OpenAPI |
| Tabla `skin_photos` | `photos/models.py:67` | Naming dermatológico legacy; coexiste con `clinical_photo` y `clinical_media` |
| App `photos` marcada "Legacy" | `config/settings.py:56` comentario | Duplica funcionalidad de `clinical.ClinicalPhoto` y `clinical.ClinicalMedia` |
| App `products` marcada "Legacy" | `config/settings.py:57` comentario | `Product.stock_quantity` duplica `StockOnHand.quantity_on_hand` |
| Docstring proyecto `EMR Dermatology` | `config/settings.py:2` | Identidad del proyecto contradice nombre de carpeta |
| Celery app name `emr_dermatology` | `config/celery.py` | Naming legacy en infraestructura async |

---

### F. Clasificación final del repo

El repositorio implementa aislamiento por `LegalEntity` como modelo raíz de tenant, con `TenantModel` abstract + `TenantManager` que auto-filtra por thread-local. Un despliegue soporta múltiples `LegalEntity` con datos aislados. Sin embargo, existen modelos globales intencionales (website, social) y módulos sin aislamiento de queries (ops.AuditLog).

Conclusión de tenancy del repositorio: MULTI-TENANT

---

### G. Confirmación de exhaustividad real

He auditado los 17 apps Django del directorio `apps/api/apps/`, la configuración global (`config/`), el directorio de tests (`apps/api/tests/`), middleware, managers, y servicios. La lectura de código cubre la totalidad de archivos `.py` de producción. No se pudo verificar el comportamiento runtime (tests, API responses, BD schema) por el NameError bloqueante en `stock/models.py:22-24`.

NO he podido auditar exhaustivamente todo el alcance solicitado. Las áreas no verificadas son:

- **Tests:** resultado de ejecución (pass/fail) — por NameError que impide carga de Django
- **Runtime behavior:** respuestas de API, estado real de BD — por imposibilidad de arrancar el servidor
- **Servicios externos:** MinIO, Redis/Celery — no disponibles en entorno de auditoría
- **Configuración de producción:** variables de entorno reales — solo visibles los defaults de desarrollo

---

## 4. Cierre obligatorio

Conclusión de tenancy del repositorio: MULTI-TENANT

NO he podido auditar exhaustivamente todo el alcance solicitado. Las áreas que quedaron fuera y sus causas están detalladas en la sección D del Evidence Pack Final. Todo el código fuente estático sí fue auditado exhaustivamente; lo que quedó fuera es exclusivamente la verificación en runtime, bloqueada por el NameError en `stock/models.py:22-24`.
