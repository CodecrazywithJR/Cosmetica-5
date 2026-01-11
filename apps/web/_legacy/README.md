# Legacy i18n Configuration

## ⚠️ OBSOLETO - NO USAR

Este directorio contiene la configuración **legacy** de i18n basada en `react-i18next`.

**Fecha de deprecación**: 2025-12-24  
**Razón**: Migración a `next-intl` para compatibilidad con Next.js App Router

## ¿Por qué se eliminó?

El proyecto usa **Next.js App Router** con **next-intl**, que es el estándar recomendado.  
`react-i18next` es incompatible con Server Components y causaba conflictos.

## Sistema actual (next-intl)

- **Config**: `/apps/web/i18n.ts` (raíz)
- **Middleware**: `/apps/web/src/middleware.ts`
- **Messages**: `/apps/web/messages/*.json`
- **Uso**: `import { useTranslations } from 'next-intl'`

## No eliminar todavía

Este código se mantiene temporalmente por si se necesita referencia para:
- Migrar traducciones faltantes
- Verificar namespaces y keys
- Auditoría de qué se perdió en la migración

**Eliminar después de**: Validar que todas las traducciones fueron migradas.

---

**Commit**: COMMIT 1 - i18n cleanup (react-i18next removal)
