# ✅ Routing Stubs - Módulos Futuros

## 🎯 Problema Resuelto
**Error**: `TypeError: routes.sales.list is undefined`

**Causa**: El menú de navegación referenciaba rutas de módulos no implementados aún.

**Solución**: Creación de stubs mínimos para evitar crashes sin implementar funcionalidad.

---

## 🔧 Cambios Realizados

### Archivo Modificado: `apps/web/src/lib/routing.ts`

#### ✅ **Rutas Agregadas**

```typescript
// Users - nested structure (used by admin pages)
users: {
  list: (locale: Locale) => `/${locale}/admin/users`,
  create: (locale: Locale) => `/${locale}/admin/users/new`,
  edit: (locale: Locale, id: number) => `/${locale}/admin/users/${id}/edit`,
  detail: (locale: Locale, id: number) => `/${locale}/admin/users/${id}`,
},

// Sales - FUTURE MODULE (stub to prevent crashes)
// TODO: Implement sales module pages when ready
sales: {
  list: (locale: Locale) => `/${locale}`,  // Redirect to home for now
  detail: (locale: Locale, id: number) => `/${locale}`,
  create: (locale: Locale) => `/${locale}`,
},
```

---

## 📋 Rutas Implementadas vs Stubs

### ✅ **Rutas FUNCIONANDO** (Páginas Existen)
| Ruta | Función | Página Física | Estado |
|------|---------|---------------|--------|
| `routes.home` | `(locale) => /${locale}` | ✅ `/[locale]/page.tsx` | OK |
| `routes.login` | `(locale) => /${locale}/login` | ✅ `/[locale]/login/page.tsx` | OK |
| `routes.patients.list` | `(locale) => /${locale}/patients` | ✅ `/[locale]/patients/page.tsx` | OK |
| `routes.patients.detail` | `(locale, id) => /${locale}/patients/${id}` | ✅ `/[locale]/patients/[id]/page.tsx` | OK |
| `routes.patients.edit` | `(locale, id) => /${locale}/patients/${id}/edit` | ✅ `/[locale]/patients/[id]/edit/page.tsx` | OK |
| `routes.patients.create` | `(locale) => /${locale}/patients/new` | ✅ `/[locale]/patients/new/page.tsx` | OK |
| `routes.encounters.list` | `(locale) => /${locale}/encounters` | ✅ `/[locale]/encounters/page.tsx` | OK |
| `routes.encounters.detail` | `(locale, id) => /${locale}/encounters/${id}` | ✅ `/[locale]/encounters/[id]/page.tsx` | OK |
| `routes.proposals.list` | `(locale) => /${locale}/proposals` | ✅ `/[locale]/proposals/page.tsx` | OK |
| `routes.schedule` | `(locale) => /${locale}/schedule` | ✅ `/[locale]/schedule/page.tsx` | OK |
| `routes.booking` | `(locale) => /${locale}/booking` | ✅ `/[locale]/booking/page.tsx` | OK |
| `routes.admin` | `(locale) => /${locale}/admin/users` | ✅ `/[locale]/admin/users/page.tsx` | OK |
| `routes.users.list` | `(locale) => /${locale}/admin/users` | ✅ `/[locale]/admin/users/page.tsx` | OK |
| `routes.users.create` | `(locale) => /${locale}/admin/users/new` | ✅ `/[locale]/admin/users/new/page.tsx` | OK |
| `routes.users.edit` | `(locale, id) => /${locale}/admin/users/${id}/edit` | ✅ `/[locale]/admin/users/[id]/edit/page.tsx` | OK |

### 🔄 **Rutas STUB** (Módulos Futuros)
| Ruta | Función | Destino Temporal | Estado |
|------|---------|-----------------|--------|
| `routes.sales.list` | `(locale) => /${locale}` | Redirige a home | ⚠️ STUB |
| `routes.sales.detail` | `(locale, id) => /${locale}` | Redirige a home | ⚠️ STUB |
| `routes.sales.create` | `(locale) => /${locale}` | Redirige a home | ⚠️ STUB |

---

## 📍 Referencias en el Código

### 1️⃣ **routes.sales.list** - Menú de Navegación
**Archivo**: `apps/web/src/components/layout/app-layout.tsx`
**Línea**: 90

```tsx
{
  name: t('sales'),
  href: routes.sales.list(locale),
  icon: ShoppingCartIcon,
  show: hasAnyRole([ROLES.ADMIN, ROLES.RECEPTION, ROLES.ACCOUNTING]),
},
```

**Estado**: ✅ **Resuelto** - Click en "Ventas" lleva a home temporalmente

---

### 2️⃣ **routes.users.list** - Menú de Navegación
**Archivo**: `apps/web/src/components/layout/app-layout.tsx`
**Línea**: 102

```tsx
{
  name: tUsers('title'), // "User Management"
  href: routes.users.list(locale),
  icon: UsersShieldIcon,
  show: hasRole(ROLES.ADMIN),
},
```

**Estado**: ✅ **Resuelto** - Funciona correctamente (página existe)

---

### 3️⃣ **routes.users.create** - Admin Users
**Archivo**: `apps/web/src/app/[locale]/admin/users/page.tsx`
**Línea**: 123

```tsx
onClick={() => router.push(routes.users.create(locale))}
```

**Estado**: ✅ **Resuelto** - Funciona correctamente

---

### 4️⃣ **routes.users.edit** - Admin Users
**Archivo**: `apps/web/src/app/[locale]/admin/users/page.tsx`
**Línea**: 216

```tsx
onClick={() => router.push(routes.users.edit(locale, user.id))}
```

**Estado**: ✅ **Resuelto** - Funciona correctamente

---

## 🚨 Errores Eliminados

### ✅ Antes (CRASHEABA)
```bash
TypeError: routes.sales.list is undefined
  at app-layout.tsx:90
```

### ✅ Después (FUNCIONA)
```bash
✓ Ready in 719ms
GET /es 200 in 99ms
```

---

## 📊 Estado del Sistema

### ✅ **Funcionando Correctamente**
- Frontend compila sin errores
- Página principal carga (`http://localhost:3000/es`)
- Login funcional
- Menú de navegación no crashea
- Click en "Ventas" redirige a home (comportamiento temporal esperado)
- Click en "Administración" → "Gestión de Usuarios" funciona

### ⚠️ **Módulos Pendientes de Implementación**
1. **Sales (Ventas)**
   - Backend: ✅ Existe (`apps/api/apps/sales/`)
   - Frontend: ❌ No existe (`apps/web/src/app/[locale]/sales/` NO CREADO)
   - Stub: ✅ Redirige a home temporalmente
   - Próximo paso: Crear páginas cuando sea necesario

---

## 🎯 Restricciones Cumplidas

✅ **NO se implementó lógica de ventas**
- Solo se crearon stubs que redirigen a home
- No se crearon páginas nuevas
- No se tocó código de backend

✅ **NO se eliminaron enlaces del menú**
- "Ventas" sigue visible para ADMIN/RECEPTION/ACCOUNTING
- Click funciona (redirige a home)

✅ **NO se rompió i18n**
- 6 idiomas intactos (en, ru, fr, uk, hy, es)
- Traducciones sin cambios

✅ **NO se rediseñó navegación**
- Estructura del menú sin cambios
- Solo agregadas rutas mínimas necesarias

---

## 📝 Documentación de Stubs

### Convención para Módulos Futuros

Cuando un módulo **aparece en navegación** pero **no tiene implementación frontend**:

```typescript
// MODULE_NAME - FUTURE MODULE (stub to prevent crashes)
// TODO: Implement module_name pages when ready
module_name: {
  list: (locale: Locale) => `/${locale}`,  // Redirect to home for now
  detail: (locale: Locale, id: number) => `/${locale}`,
  create: (locale: Locale) => `/${locale}`,
},
```

**Características de un stub válido**:
1. ✅ Retorna ruta válida existente (`/${locale}` = home)
2. ✅ Comentario `FUTURE MODULE` para identificar
3. ✅ TODO con intención de implementación futura
4. ✅ Nunca retorna `undefined`
5. ✅ Firma de función coincide con uso en código

---

## 🛠️ Comandos de Verificación

```bash
# Frontend arrancando correctamente
docker logs emr-web-dev --tail 20
# Debe mostrar: "✓ Ready in XXXms"

# Página principal cargando
curl -s http://localhost:3000/es | grep -i "error\|ready" | head -5
# No debe mostrar errores

# Sin errores de TypeScript
# En VSCode: No underlines rojos en routing.ts
```

---

## 📌 Próximos Pasos (Cuando se implemente Sales)

### Paso 1: Crear estructura de páginas
```bash
mkdir -p apps/web/src/app/[locale]/sales
touch apps/web/src/app/[locale]/sales/page.tsx
touch apps/web/src/app/[locale]/sales/new/page.tsx
touch apps/web/src/app/[locale]/sales/[id]/page.tsx
```

### Paso 2: Actualizar routing.ts
```typescript
// Cambiar de:
sales: {
  list: (locale: Locale) => `/${locale}`,  // Redirect to home for now
  
// A:
sales: {
  list: (locale: Locale) => `/${locale}/sales`,  // Real page
```

### Paso 3: Agregar traducciones
```json
// apps/web/src/messages/es.json
{
  "sales": {
    "title": "Ventas",
    "list": {...},
    "create": {...}
  }
}
```

---

## 🎉 Resultado Final

### ✅ **ERROR ELIMINADO**
- `TypeError: routes.sales.list is undefined` → ✅ RESUELTO
- `TypeError: routes.users.list is undefined` → ✅ RESUELTO

### ✅ **APP FUNCIONAL**
- Frontend arranca sin errores
- Navegación no crashea
- Login y páginas principales accesibles

### ✅ **MANTENIBILIDAD**
- Stubs documentados con comentarios claros
- TODO explícito para futura implementación
- Convención establecida para nuevos módulos

---

## 📅 Fecha de Cambio
**6 de enero de 2026**

**Archivos Modificados**: 1
- ✅ `apps/web/src/lib/routing.ts`

**Rutas Agregadas**: 7
- ✅ `routes.users.*` (4 rutas: list, create, edit, detail)
- ⚠️ `routes.sales.*` (3 stubs: list, detail, create)

**Páginas Creadas**: 0 (solo stubs)

**Backend Modificado**: 0 (sin cambios)

**i18n Modificado**: 0 (sin cambios)
