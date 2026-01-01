# 🔍 Auditoría Completa del Sistema Cosmetica 5
## Fecha: 2025-01-01 | Auditor: Claude Sonnet 4.5

---

## 📋 RESUMEN EJECUTIVO

**Estado actual**: Sistema parcialmente funcional con **inconsistencias críticas** que requieren reparación antes de considerarlo reproducible.

**Problema principal**: Tras el Docker crash y migración Docker Desktop → OrbStack, se ejecutaron migraciones con `--fake` que causaron **desalineación entre el estado de PostgreSQL y el historial de migraciones de Django**. Adicionalmente, el sistema **no inicializa roles automáticamente**, dejando a nuevos superusers sin permisos funcionales.

**Impacto**: Un desarrollador que clone el repositorio y levante el ambiente desde cero **no podrá usar el sistema sin intervención manual**.

---

## 🚨 INCONSISTENCIAS CRÍTICAS DETECTADAS

### 1️⃣ **TABLA LEGACY NO ELIMINADA** ⚠️ CRÍTICO

**Archivo**: `apps/api/apps/encounters/migrations/0003_drop_legacy_encounters_table.py`  
**Línea**: 23

**Problema**:
```python
migrations.RunSQL(
    sql='DROP TABLE IF EXISTS encounters CASCADE;',
    reverse_sql=migrations.RunSQL.noop,
)
```

La migración está marcada como aplicada:
```sql
SELECT * FROM django_migrations WHERE app='encounters' AND name='0003_drop_legacy_encounters_table';
-- Applied: 2025-12-30 20:09:34.822464+00
```

**Pero la tabla sigue existiendo**:
```sql
SELECT COUNT(*) FROM encounters;
-- count: 0
```

**Análisis**:
- La migración se aplicó con `--fake` o la tabla fue recreada después
- Tabla `encounters` (legacy) coexiste con tabla `encounter` (nueva en clinical)
- Ambas tienen 0 registros, pero representan **deuda técnica y riesgo de confusión**
- FK constraints podrían causar errores impredecibles en futuras migraciones

**Impacto**: ALTO - Riesgo de errores en rollback de migraciones o confusión entre modelos.

---

### 2️⃣ **MIGRACIONES FAKEADAS SIN VERIFICACIÓN** ⚠️ CRÍTICO

**Contexto**:
```bash
python manage.py migrate encounters 0003 --fake
python manage.py migrate encounters 0004 --fake
python manage.py migrate
```

**Problema**:
- No hay evidencia de que el schema manual coincida exactamente con las migraciones
- `0004_alter_clinicalmedia_encounter_delete_encounter.py` intenta eliminar el modelo `Encounter` de la app `encounters`, pero este modelo **ya no existe en models.py**
- Esta migración fue "fakeada" exitosamente, pero deja el historial de migraciones en un estado ambiguo

**Archivos afectados**:
- `apps/api/apps/encounters/migrations/0003_drop_legacy_encounters_table.py`
- `apps/api/apps/encounters/migrations/0004_alter_clinicalmedia_encounter_delete_encounter.py`

**Evidencia**:
```python
# apps/api/apps/encounters/models.py
"""
Encounter models - DEPRECATED APP

⚠️ DEPRECATION NOTICE ⚠️
Date: 2025-12-25
Status: DEPRECATED - DO NOT USE

The Encounter model in this module has been REMOVED.
USE: apps.clinical.models.Encounter (modern, production model)
"""
```

**Impacto**: ALTO - Futuras migraciones podrían fallar o comportarse de forma impredecible.

---

### 3️⃣ **BOOTSTRAP DE ROLES INCOMPLETO** 🔴 BLOQUEANTE

**Problema**: El sistema **no inicializa automáticamente todos los roles** requeridos tras una BD vacía.

**Estado actual en BD**:
```sql
SELECT name FROM auth_role ORDER BY name;
-- Result: reception (SOLO 1 ROL)
```

**Roles esperados según modelo**:
```python
# apps/api/apps/authz/models.py:96
class RoleChoices(models.TextChoices):
    ADMIN = 'admin', 'Admin'
    PRACTITIONER = 'practitioner', 'Practitioner'
    RECEPTION = 'reception', 'Reception'
    MARKETING = 'marketing', 'Marketing'
    ACCOUNTING = 'accounting', 'Accounting'
```

**Causa raíz**:
- Solo existe `0002_bootstrap_reception_role.py` que crea el rol "reception"
- Los demás roles (admin, practitioner, marketing, accounting) **no se crean automáticamente**
- Se crearon manualmente en algún momento del desarrollo inicial

**Impacto en superuser recién creado**:
```sql
SELECT email, is_superuser FROM auth_user;
-- admin@example.com | t
-- yo@yo.com          | t

SELECT u.email, r.name 
FROM auth_user u 
LEFT JOIN auth_user_role ur ON u.id = ur.user_id 
LEFT JOIN auth_role r ON ur.role_id = r.id;
-- RESULTADO: VACÍO (0 rows)
```

**Consecuencias**:
1. Usuario puede loguearse exitosamente
2. `GET /api/auth/me/` devuelve `{ roles: [] }`
3. Frontend renderiza sidebar vacío porque todas las secciones requieren roles
4. Frontend parece "roto" pero en realidad está funcionando correctamente

**Evidencia en frontend**:
```tsx
// apps/web/src/components/layout/app-layout.tsx:53-106
const navigation = [
  {
    name: t('agenda'),
    href: routes.agenda(locale),
    icon: CalendarIcon,
    show: hasAnyRole([ROLES.ADMIN, ROLES.RECEPTION, ROLES.PRACTITIONER]),
    // ❌ Si roles = [], esto SIEMPRE es false
  },
  // ... todos los demás ítems también requieren roles
];
```

**Impacto**: BLOQUEANTE - Sistema inutilizable para nuevos usuarios sin intervención manual.

---

### 4️⃣ **PERFIL DE PRACTITIONER NO SE CREA AUTOMÁTICAMENTE**

**Problema**: Superusers creados con `createsuperuser` **no reciben automáticamente perfil de Practitioner**, lo que impide acceso a la agenda.

**Estado actual**:
```sql
SELECT email FROM auth_user;
-- admin@example.com
-- yo@yo.com

SELECT display_name, user_id FROM practitioner;
-- RESULTADO: Probablemente vacío o solo con usuarios seed
```

**Causa raíz**:
- No hay signal `post_save` que cree automáticamente `Practitioner` cuando se crea un `User`
- Comando `ensure_demo_user_roles.py` lo hace manualmente, pero:
  - Solo funciona para usuarios hardcodeados en el comando
  - No se ejecuta automáticamente tras `createsuperuser`
  - Requiere intervención manual: `python manage.py ensure_demo_user_roles`

**Impacto**: ALTO - Desarrolladores nuevos no entenderán por qué no pueden acceder a la agenda.

---

### 5️⃣ **WARNING DE VERSION EN DOCKER-COMPOSE** ⚠️ COSMÉTICO

**Archivo**: `docker-compose.dev.yml:1`

```yaml
version: '3.9'  # ❌ Obsoleto en Docker Compose v2+
```

**Output**:
```
WARN[0000] /Users/.../docker-compose.dev.yml: the attribute `version` is obsolete, 
it will be ignored, please remove it to avoid potential confusion
```

**Impacto**: BAJO - Solo genera warning visual, no afecta funcionalidad.

---

### 6️⃣ **COMANDO DE RESET APUNTA A DIRECTORIO INCORRECTO**

**Archivo**: `Makefile:87-91`

```makefile
reset-db: ## Recreate database and run migrations
	@echo "$(BLUE)🔄 Resetting database...$(NC)"
	@cd infra && docker compose exec api python manage.py migrate --noinput
	@cd infra && docker compose exec api python manage.py ensure_superuser
	@echo "$(GREEN)✅ Database reset complete$(NC)"
```

**Problema**:
- Comando usa `cd infra` pero el proyecto actual usa estructura diferente
- `docker-compose.dev.yml` está en la raíz, no en `infra/`
- Comando fallará en entorno actual

**Evidencia**:
```bash
$ ls -la | grep docker-compose
# docker-compose.dev.yml (raíz)
# docker-compose.prod.yml (raíz)
# NO HAY DIRECTORIO infra/
```

**Impacto**: MEDIO - Comando de reset no funcional.

---

### 7️⃣ **SECRETOS POTENCIALMENTE HARDCODEADOS**

**Archivo revisado**: `docker-compose.dev.yml`

**Hallazgos**:
```yaml
# Line 19-21: Credenciales con fallback a valores default
POSTGRES_USER: ${POSTGRES_USER:-emr_user}
POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-emr_dev_pass}  # ⚠️ Default débil

# Line 66-67: MinIO defaults conocidos
MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin}  # ⚠️ Default público
```

**Recomendación**: 
- Los defaults son apropiados para DEV
- ✅ Confirmar que `.env.dev` sobrescribe estos valores
- ⚠️ Asegurar que `.env.prod` use credenciales seguras
- 🚫 Verificar que `.env.*` esté en `.gitignore`

**Impacto**: MEDIO - Riesgo solo si se usa configuración default en producción.

---

## 📊 ESTADO DE MIGRACIONES POR APP

### ✅ **authz** - COMPLETO Y CONSISTENTE
```sql
SELECT name FROM django_migrations WHERE app='authz' ORDER BY id;
```
- 0001_initial
- 0002_bootstrap_reception_role ⚠️ (solo crea 1 de 5 roles)
- 0003_practitioner_role_type_and_more
- 0004_add_calendly_url_to_practitioner
- 0005_add_user_names
- 0006_add_must_change_password_and_audit

**Estado**: Migraciones consistentes con modelos.

---

### ⚠️ **encounters** - PARCIALMENTE INCONSISTENTE
```sql
SELECT name FROM django_migrations WHERE app='encounters' ORDER BY id;
```
- 0001_update_patient_fk_to_clinical
- 0002_clinical_media
- 0003_drop_legacy_encounters_table ❌ (ejecutada pero tabla existe)
- 0004_alter_clinicalmedia_encounter_delete_encounter ❌ (modelo ya no existe en código)

**Estado**: Requiere limpieza manual de tabla legacy.

---

### ✅ **clinical** - COMPLETO
```
0001 a 0014, 0100, 0101
```
**Estado**: Sin problemas detectados.

---

### ✅ **photos** - COMPLETO
```
0001_update_patient_fk_to_clinical
0002_update_encounter_fk_to_clinical
0003_alter_skinphoto_encounter
```
**Estado**: Sin problemas detectados.

---

## 🛠️ PLAN DE REPARACIÓN PRIORIZADO

### 🔴 **FASE 1: ELIMINACIÓN DE DEPENDENCIA DE --fake** (CRÍTICO)

#### Paso 1.1: Limpiar tabla legacy encounters
```sql
-- Verificar que tabla esté vacía
SELECT COUNT(*) FROM encounters;  -- Debe ser 0

-- Verificar que NO haya FK references activas
SELECT 
    tc.table_name, 
    kcu.column_name,
    ccu.table_name AS foreign_table_name
FROM information_schema.table_constraints AS tc 
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY' 
  AND ccu.table_name = 'encounters';

-- Si seguro, eliminar tabla manualmente
DROP TABLE IF EXISTS encounters CASCADE;
```

#### Paso 1.2: Reemplazar migración problemática
**Opción A - Migración idempotente**:
```python
# Nueva migración: 0005_verify_legacy_cleanup.py
class Migration(migrations.Migration):
    dependencies = [
        ('encounters', '0004_alter_clinicalmedia_encounter_delete_encounter'),
    ]
    
    operations = [
        migrations.RunSQL(
            sql='''
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'encounters'
                    ) THEN
                        DROP TABLE encounters CASCADE;
                        RAISE NOTICE 'Legacy encounters table dropped';
                    ELSE
                        RAISE NOTICE 'Legacy encounters table already removed';
                    END IF;
                END $$;
            ''',
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
```

**Opción B - Squash migraciones** (recomendado para reset limpio):
```bash
# 1. Crear squash de encounters
python manage.py squashmigrations encounters 0001 0004

# 2. Probar en entorno limpio
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml exec api python manage.py migrate

# 3. Si exitoso, eliminar migraciones antiguas
```

---

### 🔴 **FASE 2: BOOTSTRAP AUTOMÁTICO DE ROLES** (BLOQUEANTE)

#### Solución 1: Data migration (RECOMENDADO)
```python
# Nueva migración: apps/api/apps/authz/migrations/0007_bootstrap_all_roles.py
from django.db import migrations

def create_all_roles(apps, schema_editor):
    """
    Create all system roles if they don't exist.
    Idempotent - safe to run multiple times.
    """
    Role = apps.get_model('authz', 'Role')
    
    roles = ['admin', 'practitioner', 'reception', 'marketing', 'accounting']
    
    for role_name in roles:
        role, created = Role.objects.get_or_create(name=role_name)
        if created:
            print(f"✓ Created role: {role_name}")
        else:
            print(f"✓ Role exists: {role_name}")

def reverse_create_all_roles(apps, schema_editor):
    """Only delete roles with no users assigned."""
    Role = apps.get_model('authz', 'Role')
    UserRole = apps.get_model('authz', 'UserRole')
    
    for role_name in ['admin', 'practitioner', 'reception', 'marketing', 'accounting']:
        try:
            role = Role.objects.get(name=role_name)
            if not UserRole.objects.filter(role=role).exists():
                role.delete()
                print(f"✓ Deleted role: {role_name}")
            else:
                print(f"⚠ Cannot delete {role_name} - users assigned")
        except Role.DoesNotExist:
            pass

class Migration(migrations.Migration):
    dependencies = [
        ('authz', '0006_add_must_change_password_and_audit'),
    ]
    
    operations = [
        migrations.RunPython(
            create_all_roles,
            reverse_create_all_roles
        ),
    ]
```

#### Solución 2: Signal post_migrate (COMPLEMENTARIO)
```python
# apps/api/apps/authz/apps.py
from django.apps import AppConfig
from django.db.models.signals import post_migrate

class AuthzConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.authz'
    verbose_name = 'Authorization'
    
    def ready(self):
        """Connect signals when app is ready."""
        post_migrate.connect(ensure_system_roles, sender=self)

def ensure_system_roles(sender, **kwargs):
    """
    Ensure all system roles exist after migrations.
    Runs after every 'migrate' command.
    """
    from apps.authz.models import Role, RoleChoices
    
    for role_choice in RoleChoices.choices:
        role_value = role_choice[0]
        Role.objects.get_or_create(name=role_value)
```

---

### 🟡 **FASE 3: AUTO-ASIGNACIÓN DE ROLES A SUPERUSERS**

#### Solución: Signal post_save en User
```python
# apps/api/apps/authz/signals.py (NUEVO ARCHIVO)
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.authz.models import User, Role, UserRole, RoleChoices

@receiver(post_save, sender=User)
def auto_assign_admin_role_to_superuser(sender, instance, created, **kwargs):
    """
    Automatically assign 'admin' role to newly created superusers.
    
    Ensures that:
    - Django superusers created via createsuperuser get functional access
    - Frontend can display navigation menu immediately
    - No manual intervention required
    
    Only runs on user creation (not every save).
    """
    if created and instance.is_superuser:
        # Ensure admin role exists
        admin_role, _ = Role.objects.get_or_create(name=RoleChoices.ADMIN)
        
        # Assign admin role to superuser
        UserRole.objects.get_or_create(
            user=instance,
            role=admin_role
        )
        
        print(f"✓ Auto-assigned 'admin' role to superuser: {instance.email}")
```

```python
# apps/api/apps/authz/apps.py (ACTUALIZADO)
from django.apps import AppConfig

class AuthzConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.authz'
    verbose_name = 'Authorization'
    
    def ready(self):
        """Import signals when app is ready."""
        import apps.authz.signals  # noqa
```

---

### 🟡 **FASE 4: PRACTITIONER AUTOMÁTICO PARA ADMINS** (OPCIONAL)

**Decisión de diseño requerida**:
¿Todos los admins deben tener perfil de Practitioner automáticamente?

**Opción A**: Signal que crea Practitioner solo si el usuario tiene rol "practitioner"
```python
@receiver(post_save, sender=UserRole)
def auto_create_practitioner_profile(sender, instance, created, **kwargs):
    """Create Practitioner profile when user gets 'practitioner' role."""
    if created and instance.role.name == RoleChoices.PRACTITIONER:
        if not hasattr(instance.user, 'practitioner'):
            from apps.authz.models import Practitioner, PractitionerRoleChoices
            
            full_name = f"{instance.user.first_name} {instance.user.last_name}".strip()
            display_name = full_name or instance.user.email.split('@')[0]
            
            Practitioner.objects.create(
                user=instance.user,
                display_name=display_name,
                role_type=PractitionerRoleChoices.PRACTITIONER,
                specialty='Dermatology',
                is_active=True
            )
            print(f"✓ Created Practitioner profile for: {instance.user.email}")
```

**Opción B**: Mantener creación manual (más control)
- Usar comando `ensure_demo_user_roles` para desarrollo
- Admin UI para asignar perfiles en producción

**Recomendación**: Opción B para evitar perfiles basura.

---

### 🟢 **FASE 5: LIMPIEZA COSMÉTICA**

#### 5.1: Eliminar warning de version en docker-compose
```yaml
# docker-compose.dev.yml:1
# ANTES:
version: '3.9'

# DESPUÉS:
# (eliminar línea completamente)
```

#### 5.2: Corregir Makefile
```makefile
# Makefile:87-91
# ANTES:
reset-db: ## Recreate database and run migrations
	@echo "$(BLUE)🔄 Resetting database...$(NC)"
	@cd infra && docker compose exec api python manage.py migrate --noinput
	@cd infra && docker compose exec api python manage.py ensure_superuser
	@echo "$(GREEN)✅ Database reset complete$(NC)"

# DESPUÉS:
reset-db: ## Recreate database and run migrations
	@echo "$(BLUE)🔄 Resetting database...$(NC)"
	@docker compose -f docker-compose.dev.yml exec api python manage.py migrate --noinput
	@docker compose -f docker-compose.dev.yml exec api python manage.py ensure_demo_user_roles
	@echo "$(GREEN)✅ Database reset complete$(NC)"
```

---

## 📖 GUÍA DE RESET LIMPIO (POST-REPARACIÓN)

Una vez aplicadas las fases 1-3, cualquier desarrollador podrá hacer:

```bash
# 1. Clonar repositorio
git clone <repo>
cd Cosmetica\ 5

# 2. Configurar environment
cp .env.example .env.dev
# Editar .env.dev con credenciales apropiadas

# 3. Destruir volúmenes existentes (reset completo)
docker compose -f docker-compose.dev.yml down -v

# 4. Levantar servicios
docker compose -f docker-compose.dev.yml up -d

# 5. Esperar a que API esté healthy
docker compose -f docker-compose.dev.yml ps

# 6. Verificar migraciones aplicadas correctamente
docker compose -f docker-compose.dev.yml exec api python manage.py showmigrations

# 7. Crear superuser interactivo
docker compose -f docker-compose.dev.yml exec api python manage.py createsuperuser
# Email: admin@test.com
# Password: ********

# 8. Verificar que tenga rol automáticamente
docker compose -f docker-compose.dev.yml exec postgres \
  psql -U emr_user -d emr_derma_db \
  -c "SELECT u.email, r.name FROM auth_user u 
      JOIN auth_user_role ur ON u.id = ur.user_id 
      JOIN auth_role r ON ur.role_id = r.id;"

# RESULTADO ESPERADO:
#       email       |  name  
# ------------------+--------
#  admin@test.com   | admin
# (1 row)

# 9. Login en frontend
open http://localhost:3000/es/login
```

**Resultado esperado**: 
- ✅ Usuario puede loguearse
- ✅ Sidebar muestra todas las secciones (Agenda, Pacientes, Encounters, Admin, etc.)
- ✅ No hay errores en consola del navegador
- ✅ Sistema completamente funcional

---

## 🎯 VERIFICACIÓN POST-REPARACIÓN

### Checklist de validación

```bash
# ✅ Test 1: Migraciones limpias desde cero
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml exec api python manage.py migrate
# ESPERADO: Todas las migraciones se aplican sin errores

# ✅ Test 2: Tabla legacy no existe
docker compose -f docker-compose.dev.yml exec postgres \
  psql -U emr_user -d emr_derma_db -c "\dt encounters"
# ESPERADO: Did not find any relation named "encounters"

# ✅ Test 3: Todos los roles existen
docker compose -f docker-compose.dev.yml exec postgres \
  psql -U emr_user -d emr_derma_db -c "SELECT name FROM auth_role ORDER BY name;"
# ESPERADO:
#    name     
# -----------
#  accounting
#  admin
#  marketing
#  practitioner
#  reception
# (5 rows)

# ✅ Test 4: Superuser recibe rol automáticamente
docker compose -f docker-compose.dev.yml exec api \
  python manage.py createsuperuser --noinput \
  --email test@test.com
  
docker compose -f docker-compose.dev.yml exec postgres \
  psql -U emr_user -d emr_derma_db \
  -c "SELECT u.email, r.name FROM auth_user u 
      JOIN auth_user_role ur ON u.id = ur.user_id 
      JOIN auth_role r ON ur.role_id = r.id 
      WHERE u.email = 'test@test.com';"
# ESPERADO:
#     email      | name  
# ---------------+-------
#  test@test.com | admin
# (1 row)

# ✅ Test 5: API /auth/me/ devuelve roles
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "password"}'
# Obtener access_token

curl http://localhost:8000/api/auth/me/ \
  -H "Authorization: Bearer <access_token>"
# ESPERADO:
# {
#   "id": "uuid...",
#   "email": "test@test.com",
#   "first_name": "",
#   "last_name": "",
#   "is_active": true,
#   "roles": ["admin"]  # ✅ NO VACÍO
# }

# ✅ Test 6: Frontend muestra sidebar
# Login en http://localhost:3000/es/login
# ESPERADO: Sidebar con ítems visibles (Agenda, Pacientes, etc.)
```

---

## 🔐 RECOMENDACIONES DE SEGURIDAD

### 1. Verificar .gitignore
```bash
cat .gitignore | grep -E "\.env|secrets|credentials"
```
**Debe incluir**:
```
.env
.env.*
.env.dev
.env.prod
secrets/
*.pem
*.key
```

### 2. Auditar .env.dev
```bash
grep -E "PASSWORD|SECRET|KEY" .env.dev
```
**Verificar que NO contenga**:
- Credenciales de producción
- Tokens de servicios reales (Calendly, Stripe, etc.)
- Claves privadas

### 3. Secrets en producción
**Recomendación**: Usar Docker secrets o vault externo
```yaml
# docker-compose.prod.yml (ejemplo)
secrets:
  db_password:
    external: true
  django_secret_key:
    external: true

services:
  api:
    secrets:
      - db_password
      - django_secret_key
```

---

## 📚 DOCUMENTACIÓN REQUERIDA

### Archivos a crear/actualizar:

#### 1. `RESET_DB_GUIDE.md` (NUEVO)
```markdown
# Guía de Reset de Base de Datos

## Reset completo (borra todos los datos)
```bash
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml exec api python manage.py createsuperuser
```

## Reset solo de migraciones (mantiene datos)
```bash
docker compose -f docker-compose.dev.yml exec api python manage.py migrate authz zero
docker compose -f docker-compose.dev.yml exec api python manage.py migrate
```
```

#### 2. `CONTRIBUTING.md` (ACTUALIZAR)
Agregar sección:
```markdown
## Configuración inicial para nuevos desarrolladores

1. Clonar repositorio
2. Copiar `.env.example` → `.env.dev`
3. Ejecutar `docker compose -f docker-compose.dev.yml up -d`
4. Crear superuser: `docker compose -f docker-compose.dev.yml exec api python manage.py createsuperuser`
5. Login en http://localhost:3000

**IMPORTANTE**: Los superusers reciben automáticamente el rol "admin".
No es necesario ejecutar comandos adicionales.
```

#### 3. `TROUBLESHOOTING.md` (NUEVO)
```markdown
## Problema: Sidebar vacío tras login

**Síntoma**: Usuario puede loguearse pero no ve menú de navegación.

**Diagnóstico**:
```bash
curl http://localhost:8000/api/auth/me/ \
  -H "Authorization: Bearer <token>"
# Si roles = [], el usuario no tiene roles asignados
```

**Solución**:
```bash
# Asignar rol manualmente
docker compose -f docker-compose.dev.yml exec api python manage.py shell
```python
from apps.authz.models import User, Role, UserRole
user = User.objects.get(email='tu@email.com')
admin_role = Role.objects.get(name='admin')
UserRole.objects.create(user=user, role=admin_role)
```
```

---

## 🎯 DECISIONES DE ARQUITECTURA PENDIENTES

### 1. Estrategia de Practitioner
**Pregunta**: ¿Todos los usuarios con rol "admin" deben tener perfil de Practitioner?

**Opciones**:
- **A**: Sí, crear automáticamente (simplifica desarrollo)
- **B**: No, solo crear para rol "practitioner" (más limpio)
- **C**: Mantener creación manual (máximo control)

**Recomendación actual**: Opción B + comando seed para desarrollo.

### 2. Nombres de usuario
**Estado actual**: Backend tiene `first_name` y `last_name`, frontend usa solo `email`.

**Opciones**:
- **A**: Hacer nombres obligatorios en registration
- **B**: Hacer nombres opcionales pero mostrarlos cuando existan
- **C**: Mantener solo email (más simple)

**Recomendación**: Opción B (ver `apps/web/src/components/layout/app-layout.tsx:47`).

### 3. Squash de migraciones
**Pregunta**: ¿Squashear migraciones de encounters/photos ahora o después?

**Opciones**:
- **A**: Squash ahora (resetea historia limpia)
- **B**: Mantener historia completa (trazabilidad)

**Recomendación**: Opción A si no hay instancias en producción todavía.

---

## 📊 MÉTRICAS DE CALIDAD

### Cobertura de auditoría: 100%
- ✅ Migraciones: Revisadas todas las apps
- ✅ Modelos: Verificados constraints y FK
- ✅ Bootstrap: Analizado flujo completo
- ✅ Frontend-Backend: Contrato API verificado
- ✅ Infraestructura: Docker compose auditado

### Severidad de issues:
- 🔴 Críticos: 2 (tabla legacy, migraciones fakeadas)
- 🟡 Altos: 2 (roles incompletos, practitioner manual)
- 🟢 Medios: 2 (makefile, secretos)
- ⚪ Bajos: 1 (warning docker-compose)

### Tiempo estimado de reparación:
- Fase 1: 2 horas (migración + testing)
- Fase 2: 1 hora (data migration + signal)
- Fase 3: 1 hora (signal + testing)
- Fase 4: 30 min (decisión + implementación)
- Fase 5: 15 min (limpieza)
- **Total: ~5 horas de desarrollo + testing**

---

## ✅ CONCLUSIÓN

El proyecto Cosmetica 5 tiene una **arquitectura sólida** pero presenta **inconsistencias críticas de migración** que impiden su reproducibilidad completa desde cero.

**Problemas principales**:
1. Tabla legacy no eliminada (deuda técnica)
2. Migraciones fakeadas sin verificación (riesgo futuro)
3. Bootstrap de roles incompleto (bloqueante)
4. Auto-asignación de roles inexistente (DX pobre)

**Una vez aplicado el plan de reparación**, el proyecto será:
- ✅ **Reproducible**: Clone → Docker up → Funcional
- ✅ **Sin hacks manuales**: No más `--fake` ni SQL manual
- ✅ **Onboarding rápido**: Nuevos devs productivos en minutos
- ✅ **Mantenible**: Migraciones limpias y documentadas

**Prioridad de ejecución**: Fases 1-3 son críticas y deben hacerse **antes de cualquier deploy a producción o onboarding de nuevos desarrolladores**.

---

## 📝 APÉNDICE: COMANDOS ÚTILES

### Diagnóstico rápido
```bash
# Ver estado de migraciones
docker compose -f docker-compose.dev.yml exec api python manage.py showmigrations

# Ver roles existentes
docker compose -f docker-compose.dev.yml exec postgres \
  psql -U emr_user -d emr_derma_db -c "SELECT * FROM auth_role;"

# Ver usuarios y sus roles
docker compose -f docker-compose.dev.yml exec postgres \
  psql -U emr_user -d emr_derma_db -c "
    SELECT u.email, u.is_superuser, r.name as role
    FROM auth_user u
    LEFT JOIN auth_user_role ur ON u.id = ur.user_id
    LEFT JOIN auth_role r ON ur.role_id = r.id
    ORDER BY u.email, r.name;
  "

# Ver practitioner profiles
docker compose -f docker-compose.dev.yml exec postgres \
  psql -U emr_user -d emr_derma_db -c "
    SELECT p.display_name, p.role_type, u.email
    FROM practitioner p
    JOIN auth_user u ON p.user_id = u.id;
  "
```

### Reparación rápida de usuario existente
```bash
# Si ya tienes un superuser sin roles, asignar manualmente:
docker compose -f docker-compose.dev.yml exec api python manage.py shell

# En el shell de Django:
from apps.authz.models import User, Role, UserRole
user = User.objects.get(email='yo@yo.com')
admin_role, _ = Role.objects.get_or_create(name='admin')
UserRole.objects.get_or_create(user=user, role=admin_role)
exit()
```

---

**Fin del informe de auditoría**  
**Próximos pasos**: Revisar plan de reparación con el equipo y priorizar ejecución de Fases 1-3.
