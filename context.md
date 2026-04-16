# context.md — Estado del Proyecto Cosmetica 5 ERP

> **REGLA OBLIGATORIA**: Este archivo se revisa y actualiza en cada interacción.
> Cualquier cambio, bloqueo, error encontrado o lección aprendida debe reflejarse aquí.
> No se repiten errores. No se pierde contexto.

**Última actualización**: 2026-04-16

---

## 1. Datos del Proyecto

| Dato | Valor |
|------|-------|
| Nombre | Cosmetica 5 — ERP Clínica Estética |
| Workspace | `/Users/josericardoparlonsebastian/Desktop/Ideas/ERP_CLINICA_RESCATE/Cosmetica 5/` |
| Rama activa | `MEDICAL` (HEAD: `66b109f`) |
| Rama main | `2c64c23` (origin/main) |
| Python runtime | **3.9** (macOS system) |
| Django | 4.2.8 |
| DRF | 3.14.0 |
| PostgreSQL | 15 (Alpine, Docker) |
| Redis | 7 (Alpine, Docker) |
| MinIO | latest (S3-compatible) |
| Celery | 5.3.4 |
| Frontend ERP | Next.js 14 + React 18 + TypeScript + TailwindCSS (`apps/web/`) |
| Frontend Site | Next.js 14 + next-intl (`apps/site/`) |
| Venv | `.venv/bin/activate` |
| CI/CD | GitHub Actions (`security.yml`: pytest, bandit, pip-audit, semgrep, detect-secrets) |

---

## 2. Estado Actual del Sistema

### Backend (Django)

| Verificación | Estado | Comando | Resultado |
|-------------|--------|---------|-----------|
| Django system check | ✅ PASS | `python3 manage.py check` | `System check identified no issues (0 silenced).` |
| showmigrations | ⚠️ DB required | `python3 manage.py showmigrations --plan` | Falla por host `postgres` no resolvible (esperado sin Docker) |
| Test collection | ✅ PASS | `python3 -m pytest --co -q` | 57 archivos, 1057 tests, 0 errores |
| Test execution | ❓ No verificado | `python3 -m pytest` | Requiere PostgreSQL + Redis en Docker |
| SonarQube | ⚠️ 5 restantes | `null=True` en CharField de `clinical/models.py` | Requiere data migration NULL→'' |

### Git Working Tree

| Métrica | Valor |
|---------|-------|
| Archivos modificados | ~161 |
| Archivos nuevos (untracked) | ~90 |
| Total archivos dirty | ~251 |
| **Nota** | Working tree pesado — contiene cambios de múltiples sesiones sin commit |

---

## 3. Arquitectura de Apps (17 apps Django)

| App | Modelos | Estado | Función |
|-----|---------|--------|---------|
| `core` | 2 | ✅ Activa | AppSettings, Clinic, TenantModel/TenantManager, middleware, observability |
| `authz` | 5 | ✅ Activa | User (email-based), Role, UserRole, UserAuditLog, Practitioner |
| `clinical` | 20 | ✅ Activa | Pacientes, Encounters, Citas, Consentimientos, Fotos clínicas, Calendario |
| `legal` | 1 | ✅ Activa | LegalEntity (modelo tenant) — sin lógica fiscal (ADR-002) |
| `sales` | 4 | ✅ Activa | Sale, SaleLine, SaleRefund, SaleRefundLine — state machine |
| `stock` | 4 | ✅ Activa | StockLocation, StockBatch, StockMove, StockOnHand — FEFO |
| `products` | 1 | ✅ Activa | Product (catálogo SKU, precios) |
| `proposals` | 2 | ✅ Activa | Proposal, ProposalLine — state machine |
| `treatment_plans` | 2 | ✅ Activa | TreatmentPlan, TreatmentSession |
| `documents` | 1 | ✅ Activa | Document (PDF/attachments en MinIO) |
| `photos` | 1 | ⚠️ Legacy | SkinPhoto — almacenamiento legacy de fotos |
| `ops` | 1 | ✅ Activa | AuditLog — inmutable, append-only |
| `website` | 7 | ✅ Activa | CMS para site público |
| `pos` | 0 | ⚠️ Parcial | POS con búsqueda fuzzy — sin modelos propios |
| `commerce` | 0 | ❌ Vacía | Placeholder — "PASO 2" |
| `integrations` | 0 | ❌ Vacía | Placeholder — sin modelos |
| `social` | — | ❌ Deshabilitada | Comentada — AUTH_USER_MODEL issue |

### API Surface

- **480 URL patterns** registrados
- Prefijos: `api/v1/` (privado), `public/` (CMS + booking), `admin/`, `api/schema/` (OpenAPI)
- Endpoints de salud: `/healthz/`, `/readyz/`

---

## 4. Multi-Tenancy

| Aspecto | Implementación |
|---------|---------------|
| Modelo tenant | `LegalEntity` (`apps.legal.models`) |
| FK en modelos | `legal_entity` FK en todo modelo tenant-scoped |
| Manager | `TenantManager` — filtra automáticamente por `legal_entity` |
| Middleware | `TenantMiddleware` (resuelve LE por request) + `InactiveLegalEntityMiddleware` |
| Superuser | Resuelve tenant vía header `X-Legal-Entity-ID` |
| Test fixtures | `conftest.py` auto-assign `legal_entity` a users y modelos vía monkeypatch |
| RLS DB-level | ❌ No implementado — aislamiento solo a nivel ORM |

---

## 5. Historial de Saneamientos Completados

### Saneamiento #1 — stock/models.py NameError ✅
- **Problema**: 3 constantes auto-referenciadas (`LABEL_CREATED_AT = LABEL_CREATED_AT`) causaban `NameError` al importar
- **Fix**: Asignar valores literales reales
- **Archivos**: `apps/api/apps/stock/models.py` L22-24
- **Evidence**: `SANEAMIENTO_1_EVIDENCE_PACK.md`

### Saneamiento #2 — Type hints + Test IndentationErrors ✅
- **FASE 1**: 3 archivos con `str | None` (Python 3.10+) incompatibles con runtime Python 3.9
  - `core/audit.py:25` → `Optional[str]` con `from typing import Optional`
  - `treatment_plans/serializers.py:56` → string literal `'str | None'`
  - `treatment_plans/treatment_session_serializers.py:46` → string literal `'str | None'`
- **FASE 2**: 24 test files con `from tests.conftest import TEST_PASSWORD` insertado a columna 0 dentro de funciones
  - Fix: reubicar como import top-level en cada archivo
  - 2 archivos adicionales tenían el import insertado dentro de multi-line imports (`from ... import (`)
- **Resultado**: `manage.py check` PASS, 57 archivos / 1057 tests / 0 errores colección

### SonarQube Fixes (sesión anterior) ✅
- **294 → 5 warnings** reducidas
- **5 restantes**: `null=True` en CharField de `clinical/models.py` — requiere data migration

---

## 6. Problemas Conocidos (No Resueltos)

### P1 — SonarQube: 5 CharFields con null=True
- **Archivos**: `apps/api/apps/clinical/models.py`
- **Campos**: Necesitan data migration NULL→'' antes de quitar `null=True`
- **Riesgo**: Bajo (funcional correcto, solo code smell)
- **Acción pendiente**: Crear data migration en 3 pasos (nullable→backfill→not-null)

### P2 — Apps vacías en INSTALLED_APPS
- `commerce` (0 modelos, placeholder)
- `integrations` (0 modelos, placeholder)
- `social` (deshabilitada, AUTH_USER_MODEL issue)
- **Riesgo**: Bajo (no bloquean, pero ensucian INSTALLED_APPS)

### P3 — Working tree con 251 archivos dirty
- Mezcla de cambios de múltiples sesiones sin commit
- **Riesgo**: Alto — dificulta aislar cambios, diffs contaminados
- **Acción recomendada**: Commit parcial o stash antes de nuevos cambios

### P4 — Dev tools en requirements.txt de producción
- `black`, `debug_toolbar` están en `requirements.txt` (deberían estar solo en `requirements-dev.txt`)
- **Riesgo**: Medio — footprint innecesario en imagen Docker prod

### P5 — Dos configuraciones pytest posiblemente conflictivas
- Root `pytest.ini`: `testpaths=tests`
- `apps/api/pyproject.toml`: puede tener otra `testpaths`
- **Riesgo**: Bajo — funciona actualmente, pero puede confundir

### P6 — Single settings.py sin separación por entorno
- Sin `settings/base.py`, `settings/dev.py`, `settings/prod.py`
- Variables de entorno con `os.environ.get()` sin `django-environ`
- **Riesgo**: Medio — funcional pero frágil para scaling

---

## 7. Lecciones Aprendidas (No Repetir)

| # | Lección | Contexto |
|---|---------|----------|
| L1 | **Python 3.9** es el runtime real — no usar `str \| None`, usar `Optional[str]` o string literals | Saneamiento #2 FASE 1 |
| L2 | **Heredocs en zsh** se corrompen con strings complejas — escribir scripts a archivo y ejecutar | Saneamiento #2 FASE 2 |
| L3 | **Scripts de bulk-fix** deben manejar multi-line imports (`from x import (\n...`) — no insertar dentro de paréntesis | Saneamiento #2 FASE 2 — 2 archivos fallaron |
| L4 | **Evidence Pack** debe tener diff aislado del cambio actual — working tree sucio invalida diffs globales | RULE.md §10 |
| L5 | **No mezclar diagnóstico con implementación** — primero diagnosticar, luego pedir permiso para implementar | RULE.md §11 |
| L6 | **stock/models.py constantes** — SonarQube auto-fix puede generar asignaciones auto-referenciadas | Saneamiento #1 |
| L7 | **`manage.py showmigrations`** requiere DB activa — falla esperada sin Docker, no es blocker | Verificación recurrente |
| L8 | **Archivos untracked** (`??` en git status) no aparecen en `git diff` — para estos archivos, mostrar contenido completo en evidence pack | FASE 1 archivos nuevos |

---

## 8. Skills Disponibles

### Relevantes al proyecto (usar estas)
- `django-expert` — Django ORM, managers, middleware, migrations, admin
- `drf-specialist` — DRF ViewSets, serializers, permissions, OpenAPI
- `postgresql-pro` — PostgreSQL indexes, EXPLAIN, constraints, multi-tenant
- `nextjs-frontend` — Next.js 14, React Query, next-intl, Zod, TailwindCSS
- `migration-safety` — Zero-downtime migrations, data migrations, rollback
- `celery-worker` — Celery tasks, retries, periodic jobs, monitoring
- `test-master` — Pytest, fixtures, coverage, test plans
- `code-reviewer` — Code quality audits, PR reviews
- `secure-code-guardian` — OWASP, auth, encryption, validation
- `api-designer` — REST API design, OpenAPI
- `architecture-designer` — System design, ADRs, patterns
- `devops-engineer` — Docker, CI/CD, GitHub Actions
- `debugging-wizard` — Error diagnosis, stack traces

### No relevantes (ignorar)
- `fastapi-expert` — Proyecto usa Django, no FastAPI
- `mcp-builder`, `mcp-developer` — No aplica
- `swiftui-animator`, `playful-mobile-ui` — No aplica
- `pandas-pro` — Solo si hay reportes de datos

---

## 9. Reglas de Trabajo (Referencia rápida de RULE.md)

1. **No inventar, no suponer, no adornar**
2. **Orden**: Entender → Acotar → Inspeccionar → Ejecutar → Probar → Parar
3. **Alcance cerrado** por prompt — no abrir frentes laterales
4. **Evidence Pack obligatorio** para cada cambio
5. **Unified diff completo** — no resúmenes
6. **Mínima intervención** — si se arregla con 3 líneas, tocar 3 líneas
7. **Separar diagnóstico de implementación**
8. **Economía de tokens** — ir al grano

---

## 10. Auditoría Backend — Hallazgos Verificados (2026-04-16)

### CRITICAL — ✅ ALL RESOLVED (2025-04-16)

| # | Hallazgo | Fix aplicado | Estado |
|---|----------|-------------|--------|
| C1 | SECRET_KEY con fallback hardcoded | `RuntimeError` si `DJANGO_SECRET_KEY` ausente y `DEBUG=False`. Fallback solo en dev. | ✅ |
| C2 | JWT SIGNING_KEY cae a SECRET_KEY (compound C1) | `os.environ.get('JWT_SIGNING_KEY') or SECRET_KEY` — SECRET_KEY ahora es seguro en prod | ✅ |
| C3 | `derma-photos` bucket con anonymous download en PROD | `mc anonymous set none` para bucket clínico | ✅ |
| C4 | POS views sin filtrado de tenant | `TenantQuerySetMixin` + `_tenant_patients()` helper en ambas views; `legal_entity=tenant` en create | ✅ |

### HIGH — ✅ ALL RESOLVED (2025-04-16)

| # | Hallazgo | Fix aplicado | Estado |
|---|----------|-------------|--------|
| H1 | DEBUG defaults `True` | Default cambiado a `'False'` | ✅ |
| H2 | DATABASE_PASSWORD fallback hardcoded | Fallback `'emr_dev_pass'` solo si `DEBUG=True`, cadena vacía en prod | ✅ |
| H3 | MinIO credentials fallback | Fallback `'minioadmin'` solo si `DEBUG=True`, cadena vacía en prod | ✅ |
| H4 | Sin HTTPS/security headers | Bloque `if not DEBUG:` con SSL_REDIRECT, COOKIE_SECURE, HSTS 1yr+preload, NOSNIFF | ✅ |
| H5 | debug_toolbar activo en prod (compound H1) | Resuelto: DEBUG ahora defaults False → toolbar no se activa | ✅ |

### MEDIUM

| # | Hallazgo | Archivo | Línea(s) |
|---|----------|---------|----------|
| M1 | Dev tools (black, ruff, pytest, factory-boy, debug-toolbar) en `requirements.txt` — van a imagen prod Docker | `requirements.txt` | 31-41 |

### LOW

| # | Hallazgo | Archivo | Línea(s) |
|---|----------|---------|----------|
| L1 | `apps.commerce` en INSTALLED_APPS sin modelos (placeholder) | `config/settings.py` | 47 |
| L2 | `apps.integrations` en INSTALLED_APPS sin modelos (placeholder) | `config/settings.py` | 56 |
| L3 | `TreatmentViewSet.get_queryset()` sin `select_related` — N+1 potencial | `clinical/views.py` | 1634 |
| L4 | `ProductViewSet.get_queryset()` sin `select_related` — N+1 potencial | `products/views.py` | 10 |

---

## 11. Próximos Pasos Sugeridos (pendientes de autorización)

| Prioridad | Acción | Estado |
|-----------|--------|--------|
| ~~🔴 CRÍTICA~~ | ~~Fix C4: POS views — añadir filtrado por `legal_entity`~~ | ✅ Completado |
| ~~🔴 CRÍTICA~~ | ~~Fix C3: `docker-compose.prod.yml` — quitar `anonymous download` de `derma-photos`~~ | ✅ Completado |
| ~~🔴 CRÍTICA~~ | ~~Fix C1+C2: settings.py — forzar error si SECRET_KEY/JWT_SIGNING_KEY no están en env~~ | ✅ Completado |
| ~~🔴 Alta~~ | ~~Fix H1: DEBUG default `False` en vez de `True`~~ | ✅ Completado |
| ~~🔴 Alta~~ | ~~Fix H4: Añadir HTTPS/security headers condicionados a `not DEBUG`~~ | ✅ Completado |
| ~~🟡 Media~~ | ~~Fix H2+H3: DB/MinIO passwords sin fallback (forzar env vars)~~ | ✅ Completado |
| 🟡 Media | Fix M1+H5: Separar requirements.txt / requirements-dev.txt, Dockerfile multistage | ❌ Pendiente |
| 🟡 Media | Commit/stash del working tree (251 archivos dirty) | ❌ Pendiente |
| 🟡 Media | Data migration para 5 CharFields con `null=True` | ❌ Pendiente |
| 🟢 Baja | Eliminar apps vacías de INSTALLED_APPS | ❌ Pendiente |
| 🟢 Baja | Add `select_related` a TreatmentViewSet, ProductViewSet | ❌ Pendiente |
| 🟢 Baja | Resolver conflicto pytest.ini vs pyproject.toml | ❌ Pendiente |
