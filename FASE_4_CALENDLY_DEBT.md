## 12.17. CalendlyEmbed Component - FASE 4.0 (2025-12-25)

**Context**: Componente reutilizable para renderizar el widget de Calendly usando react-calendly.

### 🎯 1. PROPÓSITO

Wrapper simple de `react-calendly` InlineWidget que:
- Recibe URL por props (NO hardcoded)
- NO contiene lógica de validación de configuración
- NO maneja estado "no configurado"
- Fail-safe: retorna `null` si URL es vacía

### 📝 2. INTERFACE

**Ubicación**: `apps/web/src/components/calendly-embed.tsx`

```typescript
interface CalendlyEmbedProps {
  url: string;              // Calendly URL (required)
  prefill?: {               // Optional pre-fill data
    name?: string;
    email?: string;
    customAnswers?: Record<string, string>;
  };
}
```

### 🔧 3. USO CORRECTO

**Pattern**:
```tsx
import { useCalendlyConfig } from '@/lib/hooks/use-calendly-config';
import { CalendlyEmbed } from '@/components/calendly-embed';
import { CalendlyNotConfigured } from '@/components/calendly-not-configured';

function SchedulePage() {
  const { calendlyUrl, isConfigured } = useCalendlyConfig();
  
  // 1. Check configuration first
  if (!isConfigured) {
    return <CalendlyNotConfigured />;
  }
  
  // 2. Render widget with configured URL
  return <CalendlyEmbed url={calendlyUrl!} />;
}
```

**Anti-pattern**:
```tsx
// ❌ WRONG: Component checks configuration
function CalendlyEmbed({ url }) {
  if (!url) return <CalendlyNotConfigured />; // NO - use hook
}

// ❌ WRONG: Hardcoded URL
<CalendlyEmbed url="https://calendly.com/..." />

// ❌ WRONG: Fallback to env var
<CalendlyEmbed url={url || process.env.NEXT_PUBLIC_CALENDLY_DEFAULT_URL} />
```

### 🚫 4. RESPONSABILIDADES

**CalendlyEmbed SOLO**:
- ✅ Renderizar InlineWidget con URL proporcionada
- ✅ Fail-safe si URL vacía (return null)
- ✅ Estilos consistentes (card + min-height)

**CalendlyEmbed NO**:
- ❌ Validar si URL está configurada (usa `useCalendlyConfig`)
- ❌ Mostrar estado "no configurado" (usa `<CalendlyNotConfigured>`)
- ❌ Usar fallback a env var
- ❌ Contener lógica de negocio

### ✅ 5. DECISIÓN REGISTRADA

**Date**: 2025-12-25  
**Phase**: 4.0 - CalendlyEmbed Component  
**Status**: ✅ **IMPLEMENTED**  

**Applies to**: Todas las páginas que necesiten widget de Calendly  
**Pattern**: Separación de responsabilidades (hook → validación, component → render)  
**Dependencies**: react-calendly package (ya instalado)  

---

## 12.18. FASE 4.2 Debt - Pantalla de Configuración (2025-12-25)

**Context**: Documentación de funcionalidad pendiente para configuración de Calendly URL por usuario.

### 🚧 DEUDA TÉCNICA EXPLÍCITA

**Funcionalidad NO implementada en FASE 4.0 ni 4.1**:
- Pantalla de perfil/configuración de usuario
- Formulario para editar `practitioner.calendly_url`
- Ruta `/[locale]/settings` o `/[locale]/profile`
- Botón "Ir a configuración" funcional en `<CalendlyNotConfigured>`

### 📋 ESTADO ACTUAL (FASE 4.0/4.1)

**Cuando practitioner_calendly_url NO configurado**:
- ✅ Se muestra `<CalendlyNotConfigured>` con mensaje informativo
- ✅ Texto i18n: "Añade tu URL de Calendly en tu perfil..."
- ❌ NO hay link a pantalla de settings (no existe)
- ❌ NO hay botón "Ir a configuración" (disabled o no renderizado)
- ⚠️ Mensaje alternativo: "Contact administrator to configure Calendly URL"

**Configuración actual**:
- Única vía: Django Admin → Authz → Practitioners → Edit → calendly_url
- Usuario final: NO puede configurar por sí mismo

### 🎯 PLANIFICACIÓN FASE 4.2

**Objetivo**: Permitir que practitioner configure su Calendly URL desde frontend.

**Tareas**:
1. **Crear página `/[locale]/settings`**:
   - Sección "Perfil"
   - Sección "Calendly Integration"
   - Formulario para editar `calendly_url`
   
2. **Backend endpoint**:
   - `PATCH /api/v1/practitioners/{id}/` (ya existe)
   - Validación: solo practitioner puede editar su propio perfil
   - Validación: URL debe ser válida (https://calendly.com/...)

3. **Frontend form**:
   ```tsx
   <input 
     type="url" 
     value={calendlyUrl} 
     placeholder="https://calendly.com/your-username/event"
   />
   <button>Guardar</button>
   ```

4. **Actualizar `<CalendlyNotConfigured>`**:
   ```tsx
   <CalendlyNotConfigured 
     onGoToSettings={() => router.push('/settings')}
   />
   ```

5. **I18N**:
   - Añadir keys `settings.*` en 6 idiomas
   - Traducciones para form labels, validación, success/error

6. **Testing**:
   - E2E: Configurar URL → Guardar → Ver widget en Schedule
   - Validación: URL inválida → Error message
   - Permissions: Solo owner puede editar su URL

### 🚨 IMPORTANTE

**NO implementar en FASE 4.0/4.1**:
- ❌ NO crear rutas falsas (`/settings` inexistente)
- ❌ NO añadir botones que lleven a páginas no implementadas
- ❌ NO prometer funcionalidad que no existe

**Mensaje UX actual** (honesto):
- "Contact administrator to configure Calendly URL"
- O simplemente NO renderizar botón "Ir a configuración"

### ✅ DECISIÓN REGISTRADA

**Date**: 2025-12-25  
**Phase**: 4.2 - Settings Page (PLANNED)  
**Status**: 🟡 **DEBT** - Not implemented yet  

**Rationale**: 
- FASE 4.0: Backend configuration ready
- FASE 4.1: Frontend rendering ready
- FASE 4.2: User self-service configuration

**Workaround actual**: Django Admin para configuración  
**Target date**: FASE 4.2 (después de Schedule page MVP)  
**Blocking**: NO - Admin can configure via Django Admin  
**Priority**: P2 (Nice to have, not critical for MVP)  

---
