# Test User Update: yo@ejemplo.com - Post FASE 4.2

**Fecha**: 2025-12-25  
**Estado**: ✅ **COMPLETADO**

---

## Resumen

Actualización del usuario de prueba existente `yo@ejemplo.com` con nombres (first_name/last_name) y Practitioner vinculado con Calendly URL definitivo, alineando el usuario con el modelo de datos de FASE 4.2.

---

## Usuario Actualizado

**Email**: `yo@ejemplo.com` ✅ **NO cambiado**  
**Password**: `Libertad` ✅ **NO cambiado**  
**First Name**: `Ricardo` ⬆️ **ACTUALIZADO**  
**Last Name**: `P` ⬆️ **ACTUALIZADO**  
**Perfil**: Administrador (is_staff=True, is_superuser=True) ✅  
**Rol**: admin ✅  
**Estado**: Activo ✅

---

## Practitioner Asociado

**Display Name**: `Ricardo P`  
**Role Type**: physician  
**Calendly URL**: `https://calendly.com/app/scheduling/meeting_types/user/me` ⬆️ **ACTUALIZADO**  
**Estado**: Activo ✅

---

## Validación Realizada

### 1. Base de Datos
```python
from apps.authz.models import User

user = User.objects.get(email='yo@ejemplo.com')
print(f"Nombre: {user.first_name} {user.last_name}")  # Ricardo P
print(f"Calendly: {user.practitioner.calendly_url}")
# https://calendly.com/app/scheduling/meeting_types/user/me
```

**Resultado**:
```
✅ Usuario obtenido: yo@ejemplo.com
✅ Nombres actualizados: Ricardo P
✅ Rol admin ya existía
✅ Practitioner actualizado

=== RESULTADO FINAL ===
Email: yo@ejemplo.com
Nombre: Ricardo
Apellido: P
Admin: is_staff=True, is_superuser=True
Practitioner ID: 740a8cee-ca35-440c-ab9f-d9c22eb3cd51
Calendly URL: https://calendly.com/app/scheduling/meeting_types/user/me
```

### 2. API Endpoint

**Endpoint**: `GET /api/auth/me/`  
**Auth**: JWT Bearer Token (login con `yo@ejemplo.com` / `Libertad`)

**Respuesta**:
```json
{
  "id": "d06ae995-ff12-4205-800b-74d19f5123be",
  "email": "yo@ejemplo.com",
  "first_name": "Ricardo",
  "last_name": "P",
  "is_active": true,
  "roles": ["admin"],
  "practitioner_calendly_url": "https://calendly.com/app/scheduling/meeting_types/user/me"
}
```

✅ **Todos los campos verificados**

### 3. Frontend Schedule Page

**Flujo completo**:
1. Usuario navega a `/en/login`
2. Ingresa credenciales: `yo@ejemplo.com` / `Libertad`
3. Frontend hace POST `/api/auth/token/` → recibe JWT
4. Frontend hace GET `/api/auth/me/` → recibe perfil completo
5. Usuario navega a `/en/schedule`
6. `useCalendlyConfig()` extrae `practitioner_calendly_url` del perfil
7. `<CalendlyEmbed>` carga widget con URL del practitioner

**Resultado esperado**: Widget de Calendly visible con URL personalizada

---

## Comandos Ejecutados

### Actualización del Usuario
```python
# Script ejecutado en Django shell
from apps.authz.models import User, Practitioner, Role, UserRole

# 1. Obtener usuario existente
user = User.objects.get(email='yo@ejemplo.com')

# 2. Actualizar nombres
user.first_name = 'Ricardo'
user.last_name = 'P'
user.save()

# 3. Verificar permisos (ya estaban activos)
user.is_staff = True
user.is_superuser = True
user.save()

# 4. Asegurar rol admin
admin_role, _ = Role.objects.get_or_create(name='admin')
UserRole.objects.get_or_create(user=user, role=admin_role)

# 5. Crear/actualizar Practitioner
practitioner, created = Practitioner.objects.get_or_create(
    user=user,
    defaults={
        'display_name': 'Ricardo P',
        'role_type': 'physician',
        'calendly_url': 'https://calendly.com/app/scheduling/meeting_types/user/me',
        'is_active': True
    }
)

if not created:
    practitioner.calendly_url = 'https://calendly.com/app/scheduling/meeting_types/user/me'
    practitioner.display_name = 'Ricardo P'
    practitioner.save()
```

### Verificación
```bash
# Verificar usuario actualizado
docker compose exec -T api python manage.py shell < script_update.py

# Ver todos los tests FASE 4.2
docker compose exec api pytest tests/test_user_profile_api.py -v
# ✅ 9 passed in 1.97s
```

---

## Garantías

### ✅ NO Modificado
- Email: `yo@ejemplo.com`
- Password: `Libertad`
- User ID: `d06ae995-ff12-4205-800b-74d19f5123be`

### ✅ Sin Datos Duplicados
- NO se creó usuario nuevo
- NO se creó practitioner duplicado
- Se usó `get_or_create()` para seguridad

### ✅ Sin Cambios Colaterales
- Otros usuarios NO afectados
- Base de datos íntegra
- Tests pasando

---

## Testing End-to-End

### Prueba Manual

**Paso 1**: Login
```bash
curl -X POST http://localhost:8001/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email": "yo@ejemplo.com", "password": "Libertad"}'
```

**Respuesta esperada**:
```json
{
  "access": "<JWT_TOKEN>",
  "refresh": "<REFRESH_TOKEN>"
}
```

**Paso 2**: Obtener Perfil
```bash
curl http://localhost:8001/api/auth/me/ \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

**Respuesta esperada**:
```json
{
  "id": "d06ae995-ff12-4205-800b-74d19f5123be",
  "email": "yo@ejemplo.com",
  "first_name": "Ricardo",
  "last_name": "P",
  "is_active": true,
  "roles": ["admin"],
  "practitioner_calendly_url": "https://calendly.com/app/scheduling/meeting_types/user/me"
}
```

**Paso 3**: Frontend
1. Abrir http://localhost:3000/en/login
2. Login con `yo@ejemplo.com` / `Libertad`
3. Navegar a http://localhost:3000/en/schedule
4. **Verificar**: Widget de Calendly carga correctamente

---

## Archivos Relacionados

- **Documentación**: [docs/PROJECT_DECISIONS.md](../docs/PROJECT_DECISIONS.md#1223-test-user-update-post-fase-42-2025-12-25)
- **Tests**: [apps/api/tests/test_user_profile_api.py](../apps/api/tests/test_user_profile_api.py)
- **Frontend User Interface**: [apps/web/src/lib/auth-context.tsx](../apps/web/src/lib/auth-context.tsx)
- **Backend User Model**: [apps/api/apps/authz/models.py](../apps/api/apps/authz/models.py)

---

## Conclusión

✅ **Usuario de prueba `yo@ejemplo.com` actualizado exitosamente**

- Nombres añadidos: Ricardo P
- Practitioner vinculado con Calendly URL
- Permisos de admin verificados
- Sin cambios en email/password
- Sin datos duplicados
- Listo para testing end-to-end completo

**Next**: Usar este usuario para validar flujo completo FASE 4.0 + 4.2:
1. Login → JWT
2. Profile → Nombres + Calendly URL
3. Schedule page → Widget funcional

---

**Autor**: GitHub Copilot  
**Revisión**: 2025-12-25
