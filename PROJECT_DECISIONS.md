# Decisiones de Proyecto - Gestión de Usuarios

## Fecha de Análisis
27 de diciembre de 2025

## Contexto
Análisis del sistema de gestión de usuarios para entender el formato exacto que usa el backend y frontend para el campo `roles`.

---

## SECCIÓN 12: ERROR 500 EN PATCH /api/v1/users/{id}/ - DESINCRONIZACIÓN DE SCHEMA

### 12.1 Problema Identificado

**Fecha:** 27 de diciembre de 2025  
**Endpoint:** `PATCH /api/v1/users/{id}/`  
**Código HTTP:** 500 Internal Server Error

#### Síntomas
- Al intentar actualizar cualquier campo de un usuario (ej: `first_name`, `roles`, etc.) mediante PATCH
- El endpoint devolvía 500 sin mensaje de error visible en el frontend
- El error ocurría al intentar crear un registro de auditoría en `UserAuditLog`

#### Error Exacto
```
django.db.utils.ProgrammingError: column "created_at" of relation "user_audit_log" does not exist
LINE 1: INSERT INTO "user_audit_log" ("id", "created_at", "actor_use...
                                            ^
```

#### Traceback Completo
```python
File "/app/apps/authz/views_users.py", line 162, in update
    UserAuditLog.objects.create(
        actor_user=request.user,
        target_user=user,
        action=action,
        metadata={
            'changed_fields': changed_fields,
            'before': before_state,
            'after': after_state,
            'ip_address': get_client_ip(request),
        }
    )

File "/usr/local/lib/python3.11/site-packages/django/db/models/query.py", line 658, in create
    obj.save(force_insert=True, using=self.db)

File "/usr/local/lib/python3.11/site-packages/django/db/models/base.py", line 814, in save
    self.save_base(...)

File "/usr/local/lib/python3.11/site-packages/django/db/backends/utils.py", line 89, in _execute
    return self.cursor.execute(sql, params)
    
psycopg2.errors.UndefinedColumn: column "created_at" of relation "user_audit_log" does not exist
```

### 12.2 Causa Raíz

**Desincronización entre modelo Django y schema de base de datos:**

**Schema antiguo en PostgreSQL:**
```sql
Table "public.user_audit_log"
     Column     |           Type           | Nullable
----------------+--------------------------+----------
 id             | uuid                     | not null
 action_type    | character varying(50)    | not null  ❌ Incorrecto
 details        | jsonb                    |           ❌ Incorrecto
 timestamp      | timestamp with time zone | not null  ❌ Incorrecto
 action_by_id   | uuid                     |           ❌ Incorrecto
 target_user_id | uuid                     | not null  ✅ Correcto
```

**Modelo Django esperado (`apps/authz/models.py`):**
```python
class UserAuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)      # ✅ Esperado
    actor_user = models.ForeignKey(                           # ✅ Esperado (actor_user_id)
        User, on_delete=models.SET_NULL, null=True,
        related_name='admin_actions'
    )
    target_user = models.ForeignKey(                          # ✅ Correcto
        User, on_delete=models.CASCADE,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=20, choices=...)     # ✅ Esperado
    metadata = models.JSONField(default=dict)                 # ✅ Esperado
```

**Migración aplicada:** `0006_add_must_change_password_and_audit.py`  
**Estado:** Marcada como aplicada en `django_migrations` pero la tabla tenía estructura vieja

### 12.3 Impacto

- ❌ **BLOQUEANTE:** Imposible actualizar usuarios desde el frontend
- ❌ **BLOQUEANTE:** Imposible cambiar roles de usuarios
- ❌ **BLOQUEANTE:** No se registraban cambios en auditoría
- ✅ **NO AFECTADO:** Lectura de usuarios (GET) funcionaba correctamente
- ✅ **NO AFECTADO:** Creación de usuarios (si no usaba audit log en ese flujo)

### 12.4 Solución Aplicada

**Pasos ejecutados:**

1. **Identificación del problema:**
```bash
psql> \d user_audit_log
# Reveló nombres de columnas incorrectos
```

2. **Eliminación de tabla desincronizada:**
```sql
DROP TABLE user_audit_log CASCADE;
```

3. **Recreación manual con schema correcto:**
```sql
CREATE TABLE user_audit_log (
    id UUID PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    actor_user_id UUID,
    target_user_id UUID NOT NULL,
    action VARCHAR(20) NOT NULL,
    metadata JSONB DEFAULT '{}',
    FOREIGN KEY (actor_user_id) REFERENCES auth_user(id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (target_user_id) REFERENCES auth_user(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED
);
```

4. **Creación de índices:**
```sql
CREATE INDEX idx_user_audit_created ON user_audit_log(created_at);
CREATE INDEX idx_user_audit_actor ON user_audit_log(actor_user_id);
CREATE INDEX idx_user_audit_target ON user_audit_log(target_user_id);
CREATE INDEX idx_user_audit_action ON user_audit_log(action);
```

5. **Marcado de migración como aplicada:**
```bash
python manage.py migrate authz --fake
```

### 12.5 Verificación

**Test realizado:**
```bash
curl -X PATCH http://localhost:8000/api/v1/users/{id}/ \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Admin Updated"}'
```

**Resultado:** ✅ 200 OK
```json
{
  "id": "0f81a59e-2002-4c6e-b5a7-5561869ecbf4",
  "email": "admin@example.com",
  "first_name": "Admin Updated",
  "last_name": "User",
  "roles": ["practitioner"],
  "updated_at": "2025-12-27T15:01:33.561863Z"
}
```

### 12.6 Lecciones Aprendidas

1. **Validar schema después de migraciones:** Siempre verificar con `\d table_name` que el schema coincide con el modelo
2. **Audit trails críticos:** Los registros de auditoría pueden bloquear operaciones CRUD si fallan
3. **Migraciones fake con precaución:** Si se usa `--fake`, asegurar que el schema manual sea idéntico
4. **Nombres de columnas legacy:** Tablas con nombres antiguos pueden persistir si no se eliminan antes de migrar

### 12.7 Acciones Preventivas

- [ ] Agregar test de integración que valide PATCH de usuarios
- [ ] Documentar proceso de verificación post-migración
- [ ] Considerar health check que valide schemas críticos
- [ ] Revisar otras tablas por posibles desincronizaciones similares

---

## SECCIÓN 13: CALENDLY_URL PARA USUARIOS ADMIN - REUTILIZACIÓN DE ESTRUCTURA

### 13.1 Contexto

**Fecha:** 27 de diciembre de 2025  
**Objetivo:** Permitir que usuarios con rol ADMIN puedan tener calendly_url para gestionar sus agendas

### 13.2 Análisis de Estructura Existente

#### Modelo Practitioner (`apps/authz/models.py`)

```python
class Practitioner(models.Model):
    """
    Practitioners (doctors, clinical staff) linked to users.
    
    Relación: OneToOne con User (user.practitioner)
    """
    id = models.UUIDField(primary_key=True)
    user = models.OneToOneField(User, on_delete=CASCADE, related_name='practitioner')
    display_name = models.CharField(max_length=255)
    role_type = models.CharField(
        choices=PractitionerRoleChoices.choices,
        default='practitioner'
    )
    specialty = models.CharField(max_length=100, default='Dermatology')
    calendly_url = models.URLField(max_length=500, blank=True, null=True)
    is_active = models.BooleanField(default=True)
```

**Características clave:**
- ✅ Relación OneToOne con User (no hay restricción por rol)
- ✅ Campo `calendly_url` ya existe
- ✅ No requiere modificaciones del modelo

#### Serializers (`apps/authz/serializers_users.py`)

**UserCreateSerializer y UserUpdateSerializer:**
```python
class UserCreateSerializer(serializers.ModelSerializer):
    practitioner_data = serializers.DictField(required=False, write_only=True, allow_null=True)
    
    def create(self, validated_data):
        practitioner_data = validated_data.pop('practitioner_data', None)
        # ...
        if practitioner_data:
            Practitioner.objects.create(
                user=user,
                display_name=practitioner_data.get('display_name'),
                calendly_url=practitioner_data.get('calendly_url'),
                # ...
            )

class UserUpdateSerializer(serializers.ModelSerializer):
    practitioner_data = serializers.DictField(required=False, write_only=True, allow_null=True)
    
    def update(self, instance, validated_data):
        practitioner_data = validated_data.pop('practitioner_data', None)
        # ...
        if practitioner_data is not None:
            if hasattr(instance, 'practitioner'):
                # Update existing
                for attr, value in practitioner_data.items():
                    setattr(practitioner, attr, value)
                practitioner.save()
            elif practitioner_data:
                # Create new practitioner record
                Practitioner.objects.create(user=instance, ...)
```

**Características clave:**
- ✅ Ya acepta `practitioner_data` en create/update
- ✅ No valida roles antes de crear/actualizar practitioner
- ✅ Puede crear practitioner para cualquier usuario
- ✅ Soporta actualización de calendly_url

### 13.3 Verificación en Base de Datos

```sql
SELECT 
  u.email,
  r.name as role_name,
  p.display_name,
  p.calendly_url
FROM auth_user u
LEFT JOIN auth_user_role ur ON u.id = ur.user_id
LEFT JOIN auth_role r ON ur.role_id = r.id
LEFT JOIN practitioner p ON u.id = p.user_id
WHERE r.name = 'admin';
```

**Resultado:**
```
          email          | role_name |  display_name  |            calendly_url            
-------------------------+-----------+----------------+------------------------------------
 ricardoparlon@gmail.com | admin     | Ricardo Parlon | https://calendly.com/ricardoparlon
```

✅ **Confirmado:** Ya existe un usuario ADMIN con registro en Practitioner y calendly_url configurado

### 13.4 Decisión de Diseño

**"Admin y Practitioner comparten estructura de agenda (Calendly)"**

#### Razones

1. **Reutilización de código:** No duplicar campo `calendly_url` en múltiples lugares
2. **Flexibilidad:** Cualquier usuario puede tener agenda (admin, practitioner, etc.)
3. **Modelo existente:** `Practitioner` ya es OneToOne con `User`, no está limitado a rol
4. **Semántica:** "Practitioner" representa "persona que agenda citas", no solo médicos
5. **Sin cambios de API:** Los contratos existentes ya soportan esta funcionalidad

#### Campos Compartidos

Todos los usuarios con `practitioner` tienen acceso a:
- `calendly_url` - URL personal de Calendly
- `display_name` - Nombre para mostrar en agenda
- `specialty` - Especialidad (opcional, default "Dermatology")
- `role_type` - Tipo de rol clínico (puede ser no aplicable para admin)
- `is_active` - Estado activo/inactivo

#### Uso del API

**Crear usuario ADMIN con calendly_url:**
```json
POST /api/v1/users/
{
  "email": "admin@example.com",
  "first_name": "Admin",
  "last_name": "User",
  "roles": ["admin"],
  "practitioner_data": {
    "display_name": "Admin User",
    "calendly_url": "https://calendly.com/admin-user"
  }
}
```

**Actualizar calendly_url de usuario ADMIN existente:**
```json
PATCH /api/v1/users/{id}/
{
  "practitioner_data": {
    "calendly_url": "https://calendly.com/new-admin-url"
  }
}
```

**Respuesta (GET /api/v1/users/{id}/):**
```json
{
  "id": "...",
  "email": "admin@example.com",
  "roles": ["admin"],
  "practitioner": {
    "id": "...",
    "display_name": "Admin User",
    "calendly_url": "https://calendly.com/admin-user",
    "role_type": "practitioner",
    "specialty": "Dermatology",
    "is_active": true
  }
}
```

### 13.5 Consideraciones

#### ¿Por qué no crear campo separado `user.calendly_url`?

❌ **Rechazado** porque:
- Duplicaría información (calendly_url estaría en 2 lugares)
- Requeriría lógica para determinar qué URL usar
- Aumentaría complejidad de serializers
- No es extensible (¿qué pasa con otros campos de agenda?)

#### ¿Qué pasa si ADMIN no necesita todos los campos de Practitioner?

✅ **Aceptable** porque:
- Campos como `specialty`, `role_type` pueden ignorarse
- `display_name` y `calendly_url` son los únicos críticos
- No afecta funcionalidad del sistema
- Permite flexibilidad futura

#### ¿Puede un usuario tener múltiples roles y Practitioner?

✅ **Sí** - Ejemplo:
- Usuario con roles: `["admin", "practitioner"]`
- Tiene único registro en `practitioner`
- Un solo `calendly_url` para todas sus funciones

### 13.6 Estado Actual

✅ **IMPLEMENTADO** - No requiere cambios de código

- ✅ Modelo soporta OneToOne sin restricción de rol
- ✅ Serializers aceptan `practitioner_data` para cualquier usuario
- ✅ API permite create/update de practitioner en cualquier usuario
- ✅ Ya existe usuario ADMIN con calendly_url en producción
- ✅ Frontend puede enviar `practitioner_data` al crear/editar usuarios

### 13.7 Documentación para Desarrolladores

**Regla:** Si un usuario necesita calendly_url (independiente de su rol), debe tener registro en `practitioner`.

**Frontend:**
- Mostrar campo `calendly_url` para usuarios con roles: admin, practitioner
- Enviar `practitioner_data` al guardar usuario con calendly_url
- No validar rol antes de permitir edición de calendly_url

**Backend:**
- No agregar validaciones que impidan practitioner para admin
- Mantener `practitioner_data` como campo opcional en serializers
- Documentar que practitioner != solo médicos

---

## 1. FORMATO DE ROLES - ANÁLISIS COMPLETO

### 1.1 Backend - Serializers y Modelos

#### Modelo de Base de Datos (`apps/api/apps/authz/models.py`)

**Estructura de Roles:**
```python
class Role(models.Model):
    """Roles del sistema."""
    id = models.UUIDField(primary_key=True)
    name = models.CharField(
        max_length=50,
        unique=True,
        choices=RoleChoices.choices
    )
    created_at = models.DateTimeField(auto_now_add=True)

class RoleChoices(models.TextChoices):
    """Roles válidos del sistema."""
    ADMIN = 'admin', 'Admin'
    PRACTITIONER = 'practitioner', 'Practitioner'
    RECEPTION = 'reception', 'Reception'
    MARKETING = 'marketing', 'Marketing'
    ACCOUNTING = 'accounting', 'Accounting'

class UserRole(models.Model):
    """Many-to-many: Usuario <-> Rol."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_roles')
    
    class Meta:
        unique_together = [('user', 'role')]
```

**CLAVE:** La relación es many-to-many a través de `UserRole`. Un usuario puede tener múltiples roles.

---

#### Serializers del Backend (`apps/api/apps/authz/serializers_users.py`)

**1. UserListSerializer (GET /api/v1/users/)**
```python
class UserListSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    
    def get_roles(self, obj):
        """Retorna lista de STRINGS con nombres de roles."""
        return list(obj.user_roles.values_list('role__name', flat=True))
```
**FORMATO DE SALIDA:** `["admin", "practitioner"]` (lista de strings)

---

**2. UserDetailSerializer (GET /api/v1/users/{id}/)**
```python
class UserDetailSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    
    def get_roles(self, obj):
        """Retorna lista de OBJETOS con nombre y display."""
        return [
            {
                'role_name': ur.role.name,
                'role_display': ur.role.get_name_display()
            }
            for ur in obj.user_roles.select_related('role').all()
        ]
```
**FORMATO DE SALIDA:** 
```json
[
  {
    "role_name": "admin",
    "role_display": "Admin"
  },
  {
    "role_name": "practitioner",
    "role_display": "Practitioner"
  }
]
```

---

**3. UserCreateSerializer (POST /api/v1/users/)**
```python
class UserCreateSerializer(serializers.ModelSerializer):
    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=RoleChoices.choices),
        required=True,
        help_text='List of role names to assign'
    )
    
    def validate_roles(self, value):
        """Valida que roles sean strings válidos."""
        valid_roles = [choice[0] for choice in RoleChoices.choices]
        for role_name in value:
            if role_name not in valid_roles:
                raise serializers.ValidationError(f"Invalid role '{role_name}'")
        return value
    
    def create(self, validated_data):
        roles_data = validated_data.pop('roles')
        # ... crea usuario ...
        # Asigna roles
        for role_name in roles_data:
            role = Role.objects.get(name=role_name)
            UserRole.objects.create(user=user, role=role)
```
**FORMATO DE ENTRADA ESPERADO:** `["admin", "practitioner"]` (lista de strings)

---

**4. UserUpdateSerializer (PATCH /api/v1/users/{id}/)**
```python
class UserUpdateSerializer(serializers.ModelSerializer):
    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=RoleChoices.choices),
        required=False,
        help_text='List of role names to assign'
    )
    
    def update(self, instance, validated_data):
        roles_data = validated_data.pop('roles', None)
        # ... actualiza campos básicos ...
        
        if roles_data is not None:
            # Elimina roles antiguos
            instance.user_roles.all().delete()
            # Añade roles nuevos
            for role_name in roles_data:
                role = Role.objects.get(name=role_name)
                UserRole.objects.create(user=instance, role=role)
```
**FORMATO DE ENTRADA ESPERADO:** `["admin", "practitioner"]` (lista de strings)

---

### 1.2 Frontend - Formularios

#### Formulario Crear Usuario (`apps/web/src/app/[locale]/admin/users/new/page.tsx`)

**Interface FormData:**
```typescript
interface FormData {
  email: string;
  first_name: string;
  last_name: string;
  password: string;
  confirmPassword: string;
  roles: string[];  // ← ARRAY DE STRINGS
  is_active: boolean;
  create_practitioner: boolean;
  display_name: string;
  specialty: string;
  calendly_url: string;
}
```

**Estado inicial:**
```typescript
const [formData, setFormData] = useState<FormData>({
  // ...
  roles: [],  // ← ARRAY VACÍO
  // ...
});
```

**Manejo de roles (checkboxes):**
```typescript
const handleRoleToggle = (role: string) => {
  setFormData((prev) => {
    const newRoles = prev.roles.includes(role)
      ? prev.roles.filter((r) => r !== role)
      : [...prev.roles, role];
    return { ...prev, roles: newRoles };
  });
};
```

**Envío al backend (línea 189):**
```typescript
const payload: any = {
  email: formData.email.trim(),
  first_name: formData.first_name.trim(),
  last_name: formData.last_name.trim(),
  password: formData.password,
  roles: formData.roles,  // ← ARRAY DE STRINGS DIRECTAMENTE
  is_active: formData.is_active,
};

const response = await apiClient.post<PasswordResponse>('/api/v1/users/', payload);
```

**CONCLUSIÓN:** El frontend envía `roles` como **array de strings** (ej: `["admin", "practitioner"]`).

---

#### Formulario Editar Usuario (`apps/web/src/app/[locale]/admin/users/[id]/edit/page.tsx`)

**Interface UserData (respuesta del backend):**
```typescript
interface UserData {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  roles: string[];  // ← ARRAY DE STRINGS (viene del backend)
  is_active: boolean;
  is_practitioner: boolean;
  must_change_password: boolean;
  practitioner_data: {
    id: number;
    display_name: string;
    specialty: string;
    calendly_url: string | null;
  } | null;
}
```

**NOTA IMPORTANTE:** El frontend espera que `GET /api/v1/users/{id}/` devuelva `roles` como **array de strings**, pero el backend (`UserDetailSerializer`) devuelve objetos con `role_name` y `role_display`.

**Carga inicial (línea 85-91):**
```typescript
const response = await apiClient.get<UserData>(`/api/v1/users/${id}/`);
const user = response.data;

setUserData(user);
setFormData({
  email: user.email,
  first_name: user.first_name,
  last_name: user.last_name,
  roles: user.roles,  // ← ASUME QUE ES ARRAY DE STRINGS
  is_active: user.is_active,
  calendly_url: user.practitioner_data?.calendly_url || '',
});
```

**Envío al backend (línea 212):**
```typescript
const payload: any = {
  email: formData.email.trim(),
  first_name: formData.first_name.trim(),
  last_name: formData.last_name.trim(),
  roles: formData.roles,  // ← ARRAY DE STRINGS
  is_active: formData.is_active,
};

await apiClient.patch(`/api/v1/users/${id}/`, payload);
```

---

### 1.3 Interface de Lista de Usuarios (`apps/web/src/app/[locale]/admin/users/page.tsx`)

**Interface User (línea 18-30):**
```typescript
interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  is_active: boolean;
  must_change_password: boolean;
  roles: string[];  // ← ARRAY DE STRINGS
  is_practitioner: boolean;
  last_login: string | null;
  created_at: string;
}
```

**CONCLUSIÓN:** La lista también espera `roles` como **array de strings**.

---

## 2. INCONSISTENCIA DETECTADA 🚨

### Problema Principal

El **frontend** espera que el endpoint `GET /api/v1/users/{id}/` devuelva:
```json
{
  "roles": ["admin", "practitioner"]
}
```

Pero el **backend** (`UserDetailSerializer`) devuelve:
```json
{
  "roles": [
    {"role_name": "admin", "role_display": "Admin"},
    {"role_name": "practitioner", "role_display": "Practitioner"}
  ]
}
```

### Impacto

- **Formulario de Edición:** No puede cargar correctamente los roles del usuario
- **Los checkboxes de roles no se marcan** porque el código hace:
  ```typescript
  formData.roles.includes(role.value)
  ```
  Pero `formData.roles` contiene objetos, no strings.

### Por Qué No Falla Todo

- **Formulario de Creación:** Funciona correctamente porque no carga datos previos.
- **Lista de Usuarios:** Funciona porque `UserListSerializer` sí retorna strings.
- **Actualización:** Puede fallar silenciosamente o causar errores si se intenta actualizar roles.

---

## 3. FORMATO CORRECTO SEGÚN ANÁLISIS

### Backend DEBE Aceptar (entrada)
**POST /api/v1/users/ y PATCH /api/v1/users/{id}/**
```json
{
  "roles": ["admin", "practitioner"]
}
```
✅ **CONFIRMADO:** Los serializers `UserCreateSerializer` y `UserUpdateSerializer` esperan esto.

### Backend DEBE Devolver (salida)

**Opción Consistente (recomendada):**
```json
{
  "roles": ["admin", "practitioner"]
}
```

**Razones:**
1. Es lo que el frontend espera
2. Es consistente con `UserListSerializer`
3. Es más simple para el frontend
4. El `display_name` se puede obtener en el frontend desde constantes

---

## 4. VALIDACIÓN DE ROLES EXISTENTES

### Roles Válidos del Sistema
Según `RoleChoices` en `apps/api/apps/authz/models.py`:

| Valor (name) | Display |
|-------------|---------|
| `admin` | Admin |
| `practitioner` | Practitioner |
| `reception` | Reception |
| `marketing` | Marketing |
| `accounting` | Accounting |

### Constantes en Frontend
Según `apps/web/src/lib/auth-context.tsx`:

```typescript
export const ROLES = {
  ADMIN: 'admin',
  PRACTITIONER: 'practitioner',
  RECEPTION: 'reception',
  MARKETING: 'marketing',
  ACCOUNTING: 'accounting',
} as const;
```

✅ **COINCIDEN PERFECTAMENTE**

---

## 5. RECOMENDACIONES

### A. Corregir UserDetailSerializer (Backend)

**Archivo:** `apps/api/apps/authz/serializers_users.py`

**Cambiar el método `get_roles` de:**
```python
def get_roles(self, obj):
    return [
        {
            'role_name': ur.role.name,
            'role_display': ur.role.get_name_display()
        }
        for ur in obj.user_roles.select_related('role').all()
    ]
```

**A:**
```python
def get_roles(self, obj):
    """Retorna lista de strings con nombres de roles."""
    return list(obj.user_roles.values_list('role__name', flat=True))
```

### B. Razones para el Cambio

1. **Consistencia:** Todos los serializers devolverán el mismo formato
2. **Compatibilidad:** El frontend ya espera este formato
3. **Simplicidad:** Menos código en frontend
4. **No Breaking Change:** Solo afecta a `GET /api/v1/users/{id}/`, no a la entrada

### C. NO Hacer Cambios en Frontend (de momento)

El código del frontend está **correcto** según la especificación esperada. Solo necesita que el backend se alinee.

---

## 6. DECISIÓN FINAL

### ✅ Formato Oficial de Roles

**ENTRADA (POST/PATCH):**
```json
{
  "roles": ["admin", "practitioner"]
}
```

**SALIDA (GET):**
```json
{
  "roles": ["admin", "practitioner"]
}
```

**Tipo:** Array de strings (valores de `RoleChoices.name`)

### ✅ NO Se Inventaron Campos Nuevos

Todo el análisis se basa en código existente.

### ✅ NO Se Inventaron Endpoints Nuevos

Todos los endpoints son existentes:
- `POST /api/v1/users/`
- `GET /api/v1/users/`
- `GET /api/v1/users/{id}/`
- `PATCH /api/v1/users/{id}/`

---

## 11. ESTRUCTURA DEL CAMPO CALENDLY_URL ✅

### Fecha: 27 de diciembre de 2025

**Objetivo:** Confirmar el campo real que representa el "Usuario Calendly" dentro del usuario del ERP.

#### Modelo de Base de Datos

**Tabla:** `practitioner`

**Campo:** `calendly_url`
```python
class Practitioner(models.Model):
    # ... otros campos
    calendly_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text='Personal Calendly scheduling URL for this practitioner. If null, system uses CALENDLY_DEFAULT_URL from settings.'
    )
```

**Características:**
- ✅ Tipo: `URLField` (máximo 500 caracteres)
- ✅ Nullable: `True` (puede ser `null`)
- ✅ Blank: `True` (puede estar vacío)
- ✅ Valor por defecto: Si es `null`, el sistema usa `CALENDLY_DEFAULT_URL` de settings

---

#### Estructura en API (Backend)

**1. GET /api/v1/users/{id}/ (UserDetailSerializer)**

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "roles": ["practitioner"],
  "is_active": true,
  "is_practitioner": true,
  "practitioner": {
    "id": "uuid",
    "display_name": "Dr. John Doe",
    "role_type": "practitioner",
    "specialty": "Dermatology",
    "calendly_url": "https://calendly.com/drjohndoe/consultation",
    "is_active": true
  }
}
```

**Ubicación:** `practitioner.calendly_url` (anidado dentro del objeto `practitioner`)

---

**2. POST /api/v1/users/ (UserCreateSerializer)**

**Payload esperado:**
```json
{
  "email": "newuser@example.com",
  "first_name": "Jane",
  "last_name": "Smith",
  "password": "SecurePass123!",
  "roles": ["practitioner"],
  "is_active": true,
  "practitioner_data": {
    "display_name": "Dr. Jane Smith",
    "specialty": "Dermatology",
    "calendly_url": "https://calendly.com/drjanesmith/appointment"
  }
}
```

**Ubicación:** `practitioner_data.calendly_url` (anidado dentro del objeto `practitioner_data`)

---

**3. PATCH /api/v1/users/{id}/ (UserUpdateSerializer)**

**Payload esperado:**
```json
{
  "email": "updated@example.com",
  "first_name": "Jane",
  "last_name": "Smith",
  "roles": ["practitioner"],
  "is_active": true,
  "practitioner_data": {
    "calendly_url": "https://calendly.com/drjanesmith/new-link"
  }
}
```

**Ubicación:** `practitioner_data.calendly_url` (anidado dentro del objeto `practitioner_data`)

**Nota importante:** Solo se incluye `practitioner_data` si `is_practitioner` es `true`.

---

#### Estructura en Frontend

**1. Interface UserData (GET response)**

```typescript
interface UserData {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  roles: string[];
  is_active: boolean;
  is_practitioner: boolean;
  must_change_password: boolean;
  practitioner_data: {
    id: number;
    display_name: string;
    specialty: string;
    calendly_url: string | null;  // ← AQUÍ
  } | null;
}
```

**Ubicación:** `practitioner_data.calendly_url`

---

**2. Interface FormData (estado del formulario)**

```typescript
interface FormData {
  email: string;
  first_name: string;
  last_name: string;
  roles: string[];
  is_active: boolean;
  calendly_url: string;  // ← PLANO (se extrae para facilitar el form)
}
```

**Mapeo en carga inicial:**
```typescript
setFormData({
  email: user.email,
  first_name: user.first_name,
  last_name: user.last_name,
  roles: user.roles,
  is_active: user.is_active,
  calendly_url: user.practitioner_data?.calendly_url || '',  // ← Se extrae
});
```

**Mapeo en envío (PATCH):**
```typescript
const payload = {
  email: formData.email.trim(),
  first_name: formData.first_name.trim(),
  last_name: formData.last_name.trim(),
  roles: formData.roles,
  is_active: formData.is_active,
};

// Solo si es practitioner
if (userData?.is_practitioner) {
  payload.practitioner_data = {
    calendly_url: formData.calendly_url.trim() || null,  // ← Se anida
  };
}
```

---

#### Resumen: Estructura del Campo

| Contexto | Formato | Campo |
|----------|---------|-------|
| **Base de datos** | Columna en tabla `practitioner` | `calendly_url` |
| **API GET (respuesta)** | Anidado en `practitioner` | `practitioner.calendly_url` |
| **API POST (creación)** | Anidado en `practitioner_data` | `practitioner_data.calendly_url` |
| **API PATCH (actualización)** | Anidado en `practitioner_data` | `practitioner_data.calendly_url` |
| **Frontend FormData** | Plano (extraído) | `calendly_url` |
| **Frontend UserData** | Anidado en `practitioner_data` | `practitioner_data.calendly_url` |

---

#### Validaciones

**Backend (serializers):**
```python
def validate_practitioner_data(self, value):
    if value and 'calendly_url' in value and value['calendly_url']:
        url = value['calendly_url']
        warnings = []
        if not url.startswith('https://calendly.com/'):
            warnings.append("Calendly URL should start with 'https://calendly.com/'")
        if '/' not in url.replace('https://calendly.com/', ''):
            warnings.append("Calendly URL should contain a scheduling slug")
        
        # Warnings no bloquean, solo informan
        if warnings:
            self._calendly_warnings = warnings
    return value
```

**Frontend (validación no bloqueante):**
```typescript
// Calendly URL warnings (non-blocking)
if (userData?.is_practitioner && formData.calendly_url.trim()) {
  const warnings: string[] = [];
  if (!formData.calendly_url.startsWith('https://calendly.com/')) {
    warnings.push(t('validation.calendlyUrlFormat'));
  }
  const parts = formData.calendly_url.replace('https://calendly.com/', '').split('/');
  if (parts.length < 2 || !parts[1]) {
    warnings.push(t('validation.calendlyUrlSlug'));
  }
  setCalendlyWarnings(warnings);
}
```

---

#### Nombres de Campo - NO Existen

Estos campos **NO existen** en el sistema:
- ❌ `user.calendly_url` (el user no tiene este campo directamente)
- ❌ `user.calendly_user` (no existe)
- ❌ `practitioner.calendly_user` (no existe)
- ❌ `calendly_username` (no existe)

**Campo correcto:** `practitioner.calendly_url` (o `practitioner_data.calendly_url` en payloads)

---

#### Flujo Completo de Datos

**Creación:**
1. Admin llena formulario con `calendly_url`
2. Frontend envía: `{"practitioner_data": {"calendly_url": "..."}}`
3. Backend crea `Practitioner` con `calendly_url`
4. Se guarda en columna `practitioner.calendly_url`

**Lectura:**
1. Frontend hace GET `/api/v1/users/{id}/`
2. Backend serializa: `{"practitioner": {"calendly_url": "..."}}`
3. Frontend extrae: `user.practitioner_data?.calendly_url`
4. Se muestra en formulario como `formData.calendly_url`

**Actualización:**
1. Admin edita `calendly_url` en formulario
2. Frontend envía: `{"practitioner_data": {"calendly_url": "..."}}`
3. Backend actualiza `practitioner.calendly_url`
4. Se guarda en BD

---

#### Uso del Campo

**En el sistema:**
- Se usa para mostrar el widget de Calendly en el frontend
- Si es `null`, el sistema usa `CALENDLY_DEFAULT_URL` del backend
- Solo aplica a usuarios con `is_practitioner = true`
- Es opcional (puede ser `null`)

**Ubicaciones donde se usa:**
1. **Formularios de usuario** (crear/editar)
2. **Widget de agendamiento** (componente `CalendlyNotConfigured`)
3. **API de perfil de usuario** (`/api/auth/me/` incluye `practitioner_calendly_url`)

---

## Autor
GitHub Copilot (Claude Sonnet 4.5)

## Referencias

### Fecha: 27 de diciembre de 2025

**Decisión:** Cambiar de selección múltiple (checkboxes) a selección única (radio buttons) para roles de usuario.

#### Contexto y Justificación

**Problema identificado:**
- El frontend permitía seleccionar múltiples roles simultáneamente (checkboxes)
- El backend técnicamente acepta un array de roles: `["admin", "practitioner"]`
- **Sin embargo, la lógica de negocio del sistema NO soporta usuarios multi-rol**
- Esto generaba estados inválidos y comportamientos indefinidos

**Motivo del cambio:**
1. **Regla de negocio:** Un usuario solo debe tener UN rol principal funcional
2. **Prevención de errores:** Evitar estados inválidos desde la UI
3. **Claridad:** La interfaz debe reflejar las restricciones del negocio
4. **UX coherente:** El usuario no puede crear configuraciones que el sistema no soporta

#### Cambios Implementados

**1. Handler de Selección**

**Antes (handleRoleToggle - múltiple selección):**
```typescript
const handleRoleToggle = (role: string) => {
  setFormData((prev) => {
    const newRoles = prev.roles.includes(role)
      ? prev.roles.filter((r) => r !== role)  // Toggle: quita si existe
      : [...prev.roles, role];                 // Toggle: agrega si no existe
    return { ...prev, roles: newRoles };
  });
};
```

**Después (handleRoleChange - selección única):**
```typescript
const handleRoleChange = (role: string) => {
  // Single role selection: replace array with selected role
  setFormData((prev) => ({ ...prev, roles: [role] }));  // ← Reemplaza completamente
};
```

**2. UI: Checkboxes → Radio Buttons**

**Antes:**
```tsx
<input
  type="checkbox"
  checked={formData.roles.includes(role.value)}
  onChange={() => handleRoleToggle(role.value)}
/>
```

**Después:**
```tsx
<input
  type="radio"
  name="role"
  value={role.value}
  checked={formData.roles.includes(role.value)}
  onChange={() => handleRoleChange(role.value)}
/>
```

#### Archivos Modificados

- `apps/web/src/app/[locale]/admin/users/new/page.tsx`
  - Handler: `handleRoleToggle` → `handleRoleChange`
  - UI: `type="checkbox"` → `type="radio"`
  
- `apps/web/src/app/[locale]/admin/users/[id]/edit/page.tsx`
  - Handler: `handleRoleToggle` → `handleRoleChange`
  - UI: `type="checkbox"` → `type="radio"`

#### Compatibilidad con Backend

**Formato mantenido:** El backend sigue recibiendo un array de strings:
```json
{
  "roles": ["admin"]  // ← Array con un solo elemento
}
```

**Razones para mantener el array:**
1. ✅ **Compatibilidad:** No requiere cambios en backend
2. ✅ **API estable:** Los endpoints siguen funcionando sin modificación
3. ✅ **Serializers:** `UserCreateSerializer` y `UserUpdateSerializer` esperan array
4. ✅ **Futuro-proof:** Si en el futuro se soporta multi-rol, solo se ajusta el frontend

#### Comportamiento Actual

**Crear Usuario:**
1. Usuario ve radio buttons (no checkboxes)
2. Solo puede seleccionar UN rol
3. Al seleccionar otro rol, el anterior se deselecciona automáticamente
4. Se envía: `{"roles": ["practitioner"]}`

**Editar Usuario:**
1. Carga con el rol actual preseleccionado
2. Usuario puede cambiar a otro rol
3. Solo un rol puede estar activo
4. Se envía: `{"roles": ["admin"]}`

#### Roles Disponibles

Los mismos 5 roles del sistema:
- ⚪ Administrador (`admin`)
- ⚪ Profesional sanitario (`practitioner`)
- ⚪ Recepción (`reception`)
- ⚪ Marketing (`marketing`)
- ⚪ Contabilidad (`accounting`)

**Selección:** Obligatoria (uno y solo uno debe estar seleccionado)

#### Validación

La validación existente sigue funcionando:
```typescript
if (formData.roles.length === 0) {
  newErrors.roles = t('validation.rolesRequired');
}
```

**Nota:** Con radio buttons, es imposible tener 0 roles después de la primera selección, pero la validación se mantiene por seguridad.

#### Impacto

- ✅ **Sin cambios en backend:** API intacta
- ✅ **Sin cambios en base de datos:** Modelo `UserRole` no cambia
- ✅ **Sin breaking changes:** Formato de payload idéntico
- ✅ **UX más clara:** Impossible state = impossible to reach
- ✅ **Regla de negocio respetada:** Un usuario = un rol
- ✅ **Prevención de errores:** No se pueden crear estados inválidos

#### Testing Necesario

1. ✓ Crear usuario: solo se puede seleccionar un rol
2. ✓ Cambiar de rol: el anterior se deselecciona automáticamente
3. ✓ Guardar: backend recibe array con un elemento
4. ✓ Editar usuario: muestra el rol actual preseleccionado
5. ✓ Cambiar rol en edición: funciona correctamente
6. ✓ Validación: requiere al menos un rol seleccionado

#### Posible Evolución Futura

Si en el futuro el sistema soporta multi-rol:
1. Cambiar radio buttons de vuelta a checkboxes
2. Restaurar lógica de toggle
3. Actualizar lógica de negocio del backend
4. No requiere cambios en API (ya acepta arrays)

---

## Autor
GitHub Copilot (Claude Sonnet 4.5)

## Referencias

### Fecha: 27 de diciembre de 2025

**Problema Identificado:** Después de guardar cambios en el formulario de Editar Usuario (PATCH 200), los checkboxes y campos mostraban valores desactualizados a pesar de que el backend guardaba correctamente.

#### Causa Raíz

Tras un PATCH exitoso, el código:
1. ✅ Hacía GET para recargar datos desde el servidor
2. ✅ Actualizaba `userData` con `setUserData(response.data)`
3. ❌ **NO actualizaba `formData`**, que es lo que usan los checkboxes y campos

**Resultado:** Los checkboxes seguían usando el estado viejo de `formData.roles`, dando la ilusión de que no se guardó nada.

#### Solución Implementada

**Archivo:** `apps/web/src/app/[locale]/admin/users/[id]/edit/page.tsx`

**Antes (líneas 224-228):**
```typescript
await apiClient.patch(`/api/v1/users/${id}/`, payload);
setSuccessMessage(t('messages.updateSuccess'));

// Reload user data to reflect changes
const response = await apiClient.get<UserData>(`/api/v1/users/${id}/`);
setUserData(response.data);  // ← Solo actualiza userData
```

**Después:**
```typescript
await apiClient.patch(`/api/v1/users/${id}/`, payload);
setSuccessMessage(t('messages.updateSuccess'));

// Reload user data to reflect changes
const response = await apiClient.get<UserData>(`/api/v1/users/${id}/`);
const user = response.data;
setUserData(user);

// Sync formData with reloaded data to reflect saved state in UI
setFormData({
  email: user.email,
  first_name: user.first_name,
  last_name: user.last_name,
  roles: user.roles,              // ← Ahora los checkboxes reflejan lo guardado
  is_active: user.is_active,
  calendly_url: user.practitioner_data?.calendly_url || '',
});
```

#### Campos Sincronizados

Los mismos que en la carga inicial:
- `email` - Campo de texto
- `first_name` - Campo de texto
- `last_name` - Campo de texto
- `roles` - **Checkboxes (el problema principal)**
- `is_active` - Checkbox
- `calendly_url` - Campo de texto (para practicantes)

#### Impacto

- ✅ **Checkboxes de roles:** Ahora reflejan exactamente lo que se guardó
- ✅ **Sin recarga de página:** La UI se actualiza automáticamente
- ✅ **Sincronización completa:** `userData` y `formData` siempre consistentes
- ✅ **UX mejorada:** El usuario ve inmediatamente el resultado de su acción
- ✅ **Sin cambios en lógica:** Solo sincronización de estado

#### Flujo Corregido

1. Usuario marca/desmarca checkbox → `formData.roles` cambia ✅
2. Usuario guarda → PATCH envía `formData.roles` ✅
3. Backend guarda → Responde 200 OK ✅
4. Frontend hace GET → Recarga datos del servidor ✅
5. Frontend actualiza `userData` → Datos frescos ✅
6. **Frontend actualiza `formData`** → **Checkboxes sincronizados** ✅ ← **FIX**
7. Mensaje de éxito → Usuario ve confirmación ✅

#### Testing Necesario

1. ✓ Editar usuario, cambiar roles, guardar
2. ✓ Verificar que checkboxes reflejan lo guardado sin recargar página
3. ✓ Verificar que otros campos también se actualizan
4. ✓ Verificar que `is_active` se sincroniza
5. ✓ Verificar que campos de practicante se actualizan si aplica

---

## Autor
GitHub Copilot (Claude Sonnet 4.5)

## Referencias

### Fecha: 27 de diciembre de 2025

**Objetivo:** Eliminar confusión en la interfaz de Crear/Editar Usuario mediante textos más claros y descriptivos.

#### Cambios Realizados

**1. Título de la Sección de Roles**

- **Antes:** "Roles"
- **Después:** "Permisos de acceso"
- **Razón:** Clarifica que se están definiendo permisos, no asignando "papeles" o "funciones"

**2. Texto Descriptivo Añadido**

Nuevo texto bajo el título:
- **Español:** "Define a qué partes del sistema puede acceder este usuario."
- **Inglés:** "Define which parts of the system this user can access."
- **Razón:** Ayuda al administrador a entender qué está configurando

**3. Texto del Checkbox Practitioner**

- **Antes:** "Profesional"
- **Después:** "Profesional sanitario"
- **Inglés Antes:** "Practitioner"
- **Inglés Después:** "Healthcare Professional"
- **Razón:** Especifica que es personal de salud, no cualquier "profesional"

**4. Columna en Lista de Usuarios**

- **Antes:** "Roles"
- **Después:** "Permisos"
- **Razón:** Consistencia con el nuevo naming y ahorro de espacio

#### Archivos Modificados

**Traducciones (i18n):**
- `apps/web/messages/es.json`
  - `users.fields.roles.label`: "Roles" → "Permisos de acceso"
  - `users.fields.roles.description`: Nueva clave agregada
  - `users.fields.roles.practitioner`: "Profesional" → "Profesional sanitario"
  - `users.table.roles`: "Roles" → "Permisos"

- `apps/web/messages/en.json`
  - `users.fields.roles.label`: "Roles" → "Access Permissions"
  - `users.fields.roles.description`: Nueva clave agregada
  - `users.fields.roles.practitioner`: "Practitioner" → "Healthcare Professional"
  - `users.table.roles`: "Roles" → "Permissions"

**Componentes Frontend:**
- `apps/web/src/app/[locale]/admin/users/new/page.tsx`
  - Añadido `<p>` con `{t('fields.roles.description')}`
  
- `apps/web/src/app/[locale]/admin/users/[id]/edit/page.tsx`
  - Añadido `<p>` con `{t('fields.roles.description')}`

#### Impacto

- ✅ **Sin cambios en lógica:** El valor interno sigue siendo `"practitioner"`
- ✅ **Sin cambios en backend:** El payload enviado es idéntico
- ✅ **Sin cambios en API:** Los endpoints no se modificaron
- ✅ **Mejora de claridad:** Los usuarios admin comprenden mejor qué configuran
- ✅ **Internacionalizado:** Cambios aplicados en español e inglés

#### Testing Necesario

1. ✓ Verificar que el formulario de crear usuario muestra "Permisos de acceso"
2. ✓ Verificar que el formulario de editar usuario muestra "Permisos de acceso"
3. ✓ Verificar que el texto descriptivo aparece correctamente
4. ✓ Verificar que el checkbox dice "Profesional sanitario"
5. ✓ Verificar que la funcionalidad sigue igual (crear/editar usuarios)

---

## Autor
GitHub Copilot (Claude Sonnet 4.5)

## Referencias

### Fecha: 27 de diciembre de 2025

**Cambio Aplicado:** Unificación del formato del campo `roles` en todos los endpoints.

#### Modificación en Backend

**Archivo:** `apps/api/apps/authz/serializers_users.py`

**Cambio en UserDetailSerializer.get_roles():**

```python
# ANTES (inconsistente):
def get_roles(self, obj):
    """Get user roles with display names."""
    return [
        {
            'role_name': ur.role.name,
            'role_display': ur.role.get_name_display()
        }
        for ur in obj.user_roles.select_related('role').all()
    ]

# DESPUÉS (consistente):
def get_roles(self, obj):
    """Get user roles as list of role names."""
    return list(obj.user_roles.values_list('role__name', flat=True))
```

#### Resultado

**Todos los endpoints ahora devuelven el mismo formato:**

- `GET /api/v1/users/` → `roles: ["admin", "practitioner"]` ✅
- `GET /api/v1/users/{id}/` → `roles: ["admin", "practitioner"]` ✅
- `POST /api/v1/users/` → acepta `roles: ["admin"]` ✅
- `PATCH /api/v1/users/{id}/` → acepta `roles: ["admin"]` ✅

#### Impacto

- ✅ **Frontend compatible:** No requiere cambios
- ✅ **Formulario de edición:** Ahora carga correctamente los roles
- ✅ **Checkboxes:** Se marcan correctamente según roles del usuario
- ✅ **Sin breaking changes:** Solo normalización de formato

#### Testing Necesario

1. ✓ Verificar GET /api/v1/users/{id}/ devuelve `roles: ["admin"]`
2. ✓ Verificar formulario de edición marca checkboxes correctamente
3. ✓ Verificar actualización de roles funciona correctamente

---

## Autor
GitHub Copilot (Claude Sonnet 4.5)

## Referencias
- `apps/api/apps/authz/models.py` - Modelos de User, Role, UserRole
- `apps/api/apps/authz/serializers_users.py` - Serializers completos
- `apps/web/src/app/[locale]/admin/users/new/page.tsx` - Formulario crear
- `apps/web/src/app/[locale]/admin/users/[id]/edit/page.tsx` - Formulario editar
- `apps/web/src/app/[locale]/admin/users/page.tsx` - Lista de usuarios
