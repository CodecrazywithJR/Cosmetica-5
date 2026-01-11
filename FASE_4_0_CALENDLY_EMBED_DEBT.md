
## 12.17. CalendlyEmbed Component - FASE 4.0 (2025-12-25)

**Context**: Componente reutilizable para embeber Calendly InlineWidget.

### 📦 Componente CalendlyEmbed

**Ubicación**: `apps/web/src/components/calendly-embed.tsx`

**Propósito**: Wrapper minimalista de react-calendly InlineWidget.

**Props**:
```typescript
interface CalendlyEmbedProps {
  url: string;                    // REQUIRED: Calendly URL
  prefill?: {                     // OPTIONAL: Pre-fill data
    name?: string;
    email?: string;
    customAnswers?: Record<string, string>;
  };
}
```

**Responsabilidades**:
- ✅ Renderizar InlineWidget de react-calendly
- ✅ Aplicar estilos consistentes (card + min-height)
- ✅ Fail-safe: Retornar null si URL vacía (no romper app)

**NO responsable de**:
- ❌ Validar si URL está configurada (usa useCalendlyConfig)
- ❌ Mostrar estado "no configurado" (usa CalendlyNotConfigured)
- ❌ Fallback a env var (Opción 2 siempre)

**Uso**:
```typescript
const { calendlyUrl, isConfigured } = useCalendlyConfig();

if (!isConfigured) {
  return <CalendlyNotConfigured />;
}

return <CalendlyEmbed url={calendlyUrl!} />;
```

**Styling**:
- Contenedor: `card` + `card-body` (consistente con DataState)
- Altura mínima: 700px (evita layout shift)
- Ancho: 100% (responsive)

---

## 12.18. DEUDA FASE 4.2 - Pantalla de Configuración de Perfil (2025-12-25)

### ⚠️ FUNCIONALIDAD NO IMPLEMENTADA

**Pantalla de configuración de perfil**: Editar `practitioner.calendly_url`

**Estado actual (FASE 4.0 / 4.1)**:
- ✅ Backend: Campo `calendly_url` existe en Practitioner model
- ✅ Backend: API expone `practitioner_calendly_url` en `/api/auth/me/`
- ✅ Frontend: Hook `useCalendlyConfig()` lee el campo
- ✅ Frontend: Componente `<CalendlyNotConfigured>` muestra mensaje
- ❌ **Frontend: NO hay página de configuración para editar el campo**

**Limitación**:
- Usuario practitioner **NO puede editar** su Calendly URL desde la app
- Configuración solo posible via **Django Admin** (solo para admins)

**UX actual**:
```
Usuario sin calendly_url configurado
         │
         ▼
<CalendlyNotConfigured />
  Título: "Calendly no está configurado"
  Descripción: "Añade tu URL de Calendly en tu perfil..."
  Botón: [Deshabilitado] "Ir a configuración" ← NO HAY RUTA
         │
         ▼
  Mensaje alternativo: "Contact administrator to configure Calendly URL"
```

### 📋 PLANIFICACIÓN FASE 4.2

**Alcance**: Implementar pantalla de configuración de perfil.

**Requisitos**:
1. Crear página `/[locale]/settings` o `/[locale]/profile`
2. Formulario con campo "Calendly URL" (URLField)
3. Validación frontend: formato URL válido
4. Validación backend: Ya existe en PractitionerWriteSerializer
5. Endpoint: `PATCH /api/v1/practitioners/{id}/` (ya existe)
6. Permisos: Solo practitioner puede editar su propio perfil

**Componentes a crear**:
- `apps/web/src/app/[locale]/settings/page.tsx`
- `apps/web/src/components/settings-form.tsx`
- I18N keys: `settings.calendlyUrl.label`, `settings.calendlyUrl.placeholder`, etc.

**Componentes a actualizar**:
- `<CalendlyNotConfigured>`: Habilitar prop `onGoToSettings` con navegación a `/settings`
- Navigation menu: Añadir link "Configuración" (solo para practitioners)

**Criterios de aceptación**:
- [ ] Practitioner puede ver su Calendly URL actual en `/settings`
- [ ] Practitioner puede editar y guardar nueva URL
- [ ] Validación de formato URL (frontend + backend)
- [ ] Mensaje de éxito al guardar
- [ ] `<CalendlyNotConfigured>` muestra botón habilitado "Ir a configuración"
- [ ] Solo practitioners ven link "Configuración" en menu

### 🚫 DECISIÓN: NO IMPLEMENTAR EN FASE 4.0 / 4.1

**Razón**:
- FASE 4.0: Preparación backend + frontend (hook, componentes UX)
- FASE 4.1: Página de scheduling + navegación (usa configuración existente)
- FASE 4.2: Pantalla de configuración (permite editar por usuario)

**Workaround actual**:
- Admin configura `calendly_url` via Django Admin
- Usuario ve URL configurada automáticamente en scheduling

**Por qué NO implementar ahora**:
1. **Separación de concerns**: Scheduling (4.1) vs Settings (4.2)
2. **MVP**: Configuración admin es suficiente para primeros usuarios
3. **Prioridad**: Funcionalidad de agendar > auto-configuración
4. **Testing**: Mejor probar scheduling primero, luego añadir self-service

### ✅ DECISIÓN REGISTRADA

**Date**: 2025-12-25  
**Phase**: 4.2 - Planned (NOT implemented)  
**Status**: 📋 **BACKLOG** - Settings page planned for FASE 4.2  

**Debt**:
- Frontend settings page NOT implemented
- `<CalendlyNotConfigured>` button disabled (no route)
- Practitioner cannot self-configure Calendly URL

**Workaround**:
- Admin configures via Django Admin (`/admin/authz/practitioner/`)
- Field: "Calendly url"

**Next Steps** (FASE 4.2):
1. Design settings page layout
2. Create form with validation
3. Wire up to existing backend endpoint
4. Update `<CalendlyNotConfigured>` to enable button
5. Add navigation menu item

**Blockers**: None (backend ready, just need frontend implementation)

---
