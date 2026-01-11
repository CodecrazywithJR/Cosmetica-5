# Agenda API Fetch Fix - Quick Reference

**Status**: ✅ Fixed  
**Date**: 2025-12-26  
**Phase**: FASE 4.4

## 🐛 Problema

**Síntoma**: "Unable to load agenda" en la pantalla Agenda (/)

**Detalles**:
- Backend healthy (✅ /api/healthz working)
- Auth working (✅ /api/auth/me/ working)
- Appointments endpoint exists (✅ curl returns 401 - auth required)
- Frontend no cargaba appointments

## 🔍 Diagnóstico

### Causa Raíz: Environment Variable Mismatch

**Lo que el código esperaba**:
```typescript
// apps/web/src/lib/api-client.ts línea 18
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
```

**Lo que había en .env.local**:
```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1  # ❌ Nombre incorrecto
```

**Problemas**:
1. **Nombre diferente**: `NEXT_PUBLIC_API_URL` vs `NEXT_PUBLIC_API_BASE_URL`
2. **Path incluido**: `/api/v1` en base URL (debería estar solo en API_ROUTES)

**Resultado**:
- Variable undefined → fallback a `'http://localhost:8000'` funcionaba
- Pero configuración inconsistente
- Si env var se leía correctamente → URL duplicada: `/api/v1/api/v1/...` (404)

## ✅ Solución

### 1. Corregir .env.local

**Antes**:
```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

**Después**:
```dotenv
# API Base URL (without /api/v1 prefix - that's added in API_ROUTES)
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

**Cambios**:
- ✅ Renombrar variable a `NEXT_PUBLIC_API_BASE_URL`
- ✅ Remover `/api/v1` (solo base URL, paths en API_ROUTES)
- ✅ Añadir comentario explicativo

### 2. Añadir Logs DEV

**Archivo**: `apps/web/src/lib/hooks/use-appointments.ts`

Añadido logging solo en desarrollo:
- Log antes de fetch (URL, params)
- Log después de éxito (count, total)
- Log detallado en error (status, data, message)

**Solo activo cuando**: `NODE_ENV === 'development'`

## 📋 Validación

### Pasos para Verificar

1. **Reiniciar servidor Next.js** (para cargar nueva variable):
```bash
# Detener servidor actual (Ctrl+C)
cd apps/web
npm run dev
```

2. **Abrir navegador con DevTools**:
- URL: http://localhost:3000/
- Console tab abierto

3. **Verificar logs en consola**:
```
[DEV] Fetching appointments: {
  url: '/api/v1/clinical/appointments/',
  params: { date: '2025-12-26' },
  fullUrl: '/api/v1/clinical/appointments/?date=2025-12-26'
}
[DEV] Appointments fetched successfully: {
  count: 5,
  total: 5
}
```

4. **Verificar Network tab**:
- Request: `GET http://localhost:8000/api/v1/clinical/appointments/?date=2025-12-26`
- Status: `200 OK`
- Response: JSON con appointments array

5. **Probar filtros**:
- Cambiar fecha → log muestra nueva URL
- Cambiar status → log muestra nuevo parámetro

## 📚 Convención Establecida

### Environment Variables

| Variable | Propósito | Ejemplo |
|----------|-----------|---------|
| `NEXT_PUBLIC_API_BASE_URL` | Base URL del backend (sin paths) | `http://localhost:8000` |
| `NEXT_PUBLIC_API_URL` | ❌ DEPRECATED | No usar |

### Arquitectura de URLs

```
Base URL (env):         http://localhost:8000
Route (API_ROUTES):     /api/v1/clinical/appointments/
───────────────────────────────────────────────────────
Final URL (axios):      http://localhost:8000/api/v1/clinical/appointments/
```

**Regla**:
> **"API_BASE_URL = protocol + host + port ONLY"**
> 
> No incluir paths. Los paths se definen en `API_ROUTES.ts`.

## 📁 Archivos Modificados

1. **apps/web/.env.local**
   - Renombrar variable
   - Remover `/api/v1` suffix
   - Añadir comentario

2. **apps/web/src/lib/hooks/use-appointments.ts**
   - Añadir console.log en DEV before fetch
   - Añadir console.log en DEV on success
   - Añadir console.error en DEV on error

## 🎯 Resultado

✅ **Agenda carga appointments correctamente**
- Request: `GET /api/v1/clinical/appointments/` → 200 OK
- Filtros de fecha funcionan
- Filtros de status funcionan
- Logs DEV ayudan a debugging futuro

## 🚨 Nota Importante

**Después de cambiar .env.local, DEBES reiniciar el servidor Next.js:**

```bash
# Detener servidor (Ctrl+C en terminal donde corre)
# Iniciar nuevamente
npm run dev
```

Las variables de entorno se cargan solo al inicio. Cambios en `.env*` requieren restart.

## 📚 Documentación

**Detallada**: [docs/PROJECT_DECISIONS.md §12.32](docs/PROJECT_DECISIONS.md)

**Relacionado**:
- §12.30: Agenda Date Filter (feature original)
- §12.31: i18n Regression Fix (feature anterior)
- API_ROUTES.ts: Definición de endpoints

---

**Implementado por**: Technical Team  
**Tiempo**: ~30min  
**Riesgo**: 🟢 BAJO (solo config)  
**Impacto**: 🟢 POSITIVO (Agenda ahora funciona)
