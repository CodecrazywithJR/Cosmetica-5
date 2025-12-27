# FASE 4.2: Admin-Driven User Profile Management

**Fecha**: 2025-12-25  
**Estado**: ✅ **COMPLETADO**

---

## Resumen Ejecutivo

Implementación completa de **Opción A** (admin-driven) para creación de usuarios con perfil completo: nombre, apellido, email, password y Calendly URL. Sin funcionalidad de autoservicio (self-service) en este MVP.

---

## Objetivos Cumplidos

1. ✅ **Modelo User extendido** con `first_name` y `last_name`
2. ✅ **Admin UI mejorada** para creación de usuarios con nombres
3. ✅ **API actualizada** (`/api/auth/me/`) expone nombres en perfil
4. ✅ **Frontend preparado** (User interface incluye first_name/last_name)
5. ✅ **Tests comprehensivos** (9 tests, 100% passing)
6. ✅ **Migration aplicada** sin problemas
7. ✅ **Documentación completa** (PROJECT_DECISIONS.md §12.22)

---

## Cambios Implementados

### Backend

**Modelo User** (`apps/authz/models.py`):
```python
class User(AbstractBaseUser, PermissionsMixin):
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    # ... existing fields
```

**Admin Interface** (`apps/authz/admin.py`):
- Personal Info fieldset con first_name/last_name
- search_fields incluye nombres
- list_display muestra nombres

**API Endpoint** (`/api/auth/me/`):
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "first_name": "Jane",
  "last_name": "Smith",
  "is_active": true,
  "roles": ["practitioner"],
  "practitioner_calendly_url": "https://calendly.com/drsmith"
}
```

### Frontend

**User Interface** (`apps/web/src/lib/auth-context.tsx`):
```typescript
export interface User {
  first_name?: string; // FASE 4.2
  last_name?: string;  // FASE 4.2
  // ... existing fields
}
```

### Database

**Migration**: `0005_add_user_names.py`
```sql
ALTER TABLE auth_user ADD COLUMN first_name VARCHAR(150);
ALTER TABLE auth_user ADD COLUMN last_name VARCHAR(150);
```

---

## Workflow de Admin

### Paso 1: Crear Usuario
1. Admin navega a `/admin/authz/user/add/`
2. Llena el formulario:
   - **Email**: maria.garcia@example.com (required)
   - **Password**: SecurePassword123! (required)
   - **First name**: Maria (opcional)
   - **Last name**: Garcia (opcional)
   - **Is staff**: ☑️ (para acceso admin)
3. Guarda usuario

### Paso 2: Crear Practitioner
1. Admin navega a `/admin/authz/practitioner/add/`
2. Llena el formulario:
   - **User**: maria.garcia@example.com (autocomplete)
   - **Display name**: Dr. Maria Garcia
   - **Role type**: physician
   - **Specialty**: Dermatology
   - **Calendly URL**: https://calendly.com/drmariagarcia
3. Guarda practitioner

### Resultado
✅ Usuario creado con nombres  
✅ Practitioner vinculado con Calendly URL  
✅ Frontend recibe perfil completo en `/api/auth/me/`

---

## Tests

**Archivo**: `apps/api/tests/test_user_profile_api.py`

**9 tests implementados**:
1. ✅ `test_profile_includes_first_name_and_last_name`
2. ✅ `test_practitioner_includes_calendly_url`
3. ✅ `test_regular_user_no_calendly_url`
4. ✅ `test_blank_names_returned_as_empty_strings`
5. ✅ `test_roles_included_in_response`
6. ✅ `test_unauthenticated_request_returns_401`
7. ✅ `test_practitioner_without_calendly_url`
8. ✅ `test_profile_response_structure`
9. ✅ `test_profile_response_structure_practitioner`

**Resultado**: 9 passed in 1.97s

---

## Validación

### Backend Tests
```bash
docker compose exec api pytest tests/test_user_profile_api.py -v
# ✅ 9 passed
```

### Migration Status
```bash
docker compose exec api python manage.py migrate authz
# ✅ Applying authz.0005_add_user_names... OK
```

### Demo Manual
```bash
docker compose exec -T api python manage.py shell < /tmp/demo_fase42.py
# ✅ User: Maria Garcia
# ✅ Calendly: https://calendly.com/drmariagarcia
```

---

## Arquitectura

### Decisión Técnica
**Añadir `first_name`/`last_name` al modelo User** (en lugar de usar solo `Practitioner.display_name`)

**Ventajas**:
- ✅ Patrón estándar de Django (familiar para admins)
- ✅ Nombres disponibles para TODOS los usuarios (no solo practitioners)
- ✅ Consistencia con AbstractUser de Django
- ✅ Simplifica API (estructura plana, no nested)

**Tradeoffs**:
- ⚠️ Redundancia con `Practitioner.display_name` (puede derivarse)
- ⚠️ Admin debe crear User y Practitioner por separado (2 pasos)

### Futuras Mejoras (DEBT)
- **PractitionerInline**: Crear practitioner inline al crear User (1 paso)
- **Auto display_name**: Derivar de `first_name + last_name`
- **Settings Page**: Self-service user profile editing (FASE 4.2 original goal, NO MVP)

---

## Archivos Modificados

### Backend
- ✅ `apps/api/apps/authz/models.py` - User model
- ✅ `apps/api/apps/authz/admin.py` - Admin interface
- ✅ `apps/api/apps/core/serializers.py` - UserProfileSerializer
- ✅ `apps/api/apps/core/views.py` - CurrentUserView
- ✅ `apps/api/apps/authz/migrations/0005_add_user_names.py` - Migration (NEW)

### Frontend
- ✅ `apps/web/src/lib/auth-context.tsx` - User interface

### Tests
- ✅ `apps/api/tests/test_user_profile_api.py` - 9 tests (NEW)

### Documentación
- ✅ `docs/PROJECT_DECISIONS.md` - §12.22 (NEW)
- ✅ `FASE_4_2_ADMIN_USER_PROFILE.md` - Este documento (NEW)

---

## Comandos Útiles

### Crear usuario manualmente (shell)
```bash
docker compose exec api python manage.py shell
```
```python
from apps.authz.models import User, Practitioner

user = User.objects.create_user(
    email="test@example.com",
    password="testpass123",
    first_name="John",
    last_name="Doe"
)

practitioner = Practitioner.objects.create(
    user=user,
    display_name="Dr. John Doe",
    role_type="physician",
    calendly_url="https://calendly.com/drjohndoe"
)
```

### Verificar perfil API
```bash
curl http://localhost:8001/api/auth/me/ \
  -H "Authorization: Bearer <access_token>"
```

### Ejecutar tests
```bash
docker compose exec api pytest tests/test_user_profile_api.py -v
```

---

## Estado del Proyecto

**Integración FASE 4.0 + FASE 4.2**:
- ✅ Calendly URL por practitioner (backend + frontend)
- ✅ Schedule page (`/[locale]/schedule`)
- ✅ Webhook signature verification con tests
- ✅ Legacy Encounter deprecation
- ✅ User profile con nombres (NEW)
- ✅ Admin-driven user creation (NEW)

**PENDIENTE**:
- ⏳ Settings page para self-service (NO MVP, debt documentada)
- ⏳ PractitionerInline en UserAdmin (mejora UX admin)
- ⏳ Webhook event processing (handler vacío, TODO)

---

## Conclusión

✅ **FASE 4.2 COMPLETADA**

Admin puede crear usuarios con perfil completo (nombres + Calendly URL) en Django Admin. Frontend recibe y muestra datos correctamente. Sistema 100% funcional y testeado.

**Next Steps** (opcional, NO bloqueante):
- Settings page para edición self-service
- Inline Practitioner en User admin
- Auto-populate display_name

---

**Autor**: GitHub Copilot  
**Revisión**: 2025-12-25
