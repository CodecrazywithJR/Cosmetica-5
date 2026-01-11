# FASE 4.0 - Calendly Configuration per Practitioner

**Date**: 2025-12-25  
**Status**: ✅ COMPLETED (Backend ready, frontend pending)

## 📋 Cambios Realizados

### 1. Backend - Modelo Practitioner

**Archivo**: `apps/api/apps/authz/models.py:186`

```python
calendly_url = models.URLField(
    max_length=500,
    blank=True,
    null=True,
    help_text='Personal Calendly scheduling URL for this practitioner. If null, system uses CALENDLY_DEFAULT_URL from settings.'
)
```

**Migración**: `apps/api/apps/authz/migrations/0004_add_calendly_url_to_practitioner.py`

### 2. Backend - Settings

**Archivo**: `apps/api/config/settings.py:239`

```python
CALENDLY_DEFAULT_URL = os.environ.get(
    'CALENDLY_DEFAULT_URL',
    'https://calendly.com/app/scheduling/meeting_types/user/me?pane=event_type_editor&paneState=ZGVmYXVsdE9wZW5LZXk9YXZhaWxhYmlsaXR5JmlkPTE4OTg2OTAzMSZ0eXBlPVN0YW5kYXJkRXZlbnRUeXBlJm93bmVyVHlwZT1Vc2VyJm93bmVySWQ9NDU3MzYwNTUma2luZD1zb2xv'
)
```

### 3. Backend - API Endpoints

**Modificados**:
- `apps/api/apps/core/views.py:378` - CurrentUserView incluye practitioner_calendly_url
- `apps/api/apps/core/serializers.py:7` - UserProfileSerializer con nuevo campo
- `apps/api/apps/authz/serializers.py` - Todos los serializers de Practitioner incluyen calendly_url

**Endpoint principal**: `GET /api/auth/me/`

**Response**:
```json
{
  "id": "uuid",
  "email": "doctora@example.com",
  "is_active": true,
  "roles": ["admin", "practitioner"],
  "practitioner_calendly_url": "https://calendly.com/doctora/consulta" // null si no configurado
}
```

### 4. Frontend - Type Definition

**Archivo**: `apps/web/src/lib/auth-context.tsx:25`

```typescript
export interface User {
  id: string;
  email: string;
  is_active: boolean;
  roles: string[];
  practitioner_calendly_url?: string | null; // FASE 4.0
}
```

### 5. Documentación

**Archivo**: `docs/PROJECT_DECISIONS.md` - Sección §12.15

Documentación completa de:
- Decisiones arquitectónicas
- Razones de usar Practitioner model
- Contrato API
- Comportamiento fallback
- Testing manual

## 🔧 Uso

### Backend - Configurar URL en Django Admin

1. Login a Django Admin: http://localhost:8000/admin/
2. Ir a **Authz → Practitioners**
3. Editar practitioner
4. Rellenar campo **Calendly url**
5. Guardar

### Backend - Environment Variable (Testing)

```bash
# apps/api/.env
CALENDLY_DEFAULT_URL=https://calendly.com/doctora/consulta
```

### Frontend - Environment Variable (Futuro)

```bash
# apps/web/.env.local
NEXT_PUBLIC_CALENDLY_DEFAULT_URL=https://calendly.com/doctora/consulta
```

## 🧪 Testing

### 1. Aplicar migración

```bash
docker-compose exec api python manage.py migrate
```

### 2. Verificar endpoint sin configuración

```bash
curl -X GET http://localhost:8000/api/auth/me/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Expected**:
```json
{
  "practitioner_calendly_url": null
}
```

### 3. Configurar URL en Admin

Admin → Practitioners → Edit → Calendly url: `https://calendly.com/test`

### 4. Verificar endpoint con configuración

```bash
curl -X GET http://localhost:8000/api/auth/me/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Expected**:
```json
{
  "practitioner_calendly_url": "https://calendly.com/test"
}
```

## ✅ Criterios de Finalización

- [x] Campo creado en modelo Practitioner
- [x] Migración generada y limpia
- [x] Variable CALENDLY_DEFAULT_URL en settings
- [x] API expone practitioner_calendly_url en /api/auth/me/
- [x] Serializers actualizados (list, detail, write)
- [x] Type User actualizado en frontend
- [x] Decisión documentada en PROJECT_DECISIONS.md §12.15
- [x] 0 errores de compilación
- [x] Ningún código legacy duplicado

## 🚫 Anti-Patterns Evitados

### ❌ NO hardcodear URL en frontend

```tsx
// WRONG
<InlineWidget url="https://calendly.com/doctora" />

// CORRECT (futuro)
const calendlyUrl = useCalendlyUrl(); // resuelve user.calendly_url || env var
<InlineWidget url={calendlyUrl} />
```

### ❌ NO exponer settings.CALENDLY_DEFAULT_URL en API

Backend settings NO se envían al frontend. Frontend usa su propia env var `NEXT_PUBLIC_CALENDLY_DEFAULT_URL`.

### ❌ NO crear tabla global ClinicSettings

Practitioner.calendly_url es más flexible (multi-practitioner ready) y escalable.

## 📦 Archivos Modificados

```
apps/api/
  apps/authz/
    models.py                  (campo calendly_url añadido)
    serializers.py             (3 serializers actualizados)
    migrations/
      0004_add_calendly_url_to_practitioner.py  (NUEVA)
  apps/core/
    views.py                   (CurrentUserView modificado)
    serializers.py             (UserProfileSerializer modificado)
  config/
    settings.py                (CALENDLY_DEFAULT_URL añadido)

apps/web/
  src/lib/
    auth-context.tsx           (User interface actualizado)

docs/
  PROJECT_DECISIONS.md         (§12.15 añadido)

FASE_4_0_CALENDLY_CONFIG.md    (ESTE ARCHIVO)
```

## 🚀 Próximos Pasos (FASE 4.1 - Frontend)

1. Crear hook `useCalendlyUrl()` que resuelva user.calendly_url || env var
2. Crear componente `<CalendlyEmbed>` usando react-calendly
3. Crear página `/[locale]/schedule` con selector practitioner
4. Añadir navegación "Agendar Cita" en header menu
5. Testing E2E: agendar → webhook → ver en Agenda

**Documentación de referencia**: `docs/PROJECT_DECISIONS.md` §12.14 (Auditoría Encounter/Calendly)

---

**Implementado por**: GitHub Copilot  
**Aprobado por**: Product Owner  
**Review**: Pending  
