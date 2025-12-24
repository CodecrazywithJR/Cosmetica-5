# Frontend MVP - Cosmetica 5

**Sistema de gestión clínico y de ventas** (ERP/EMR) con enfoque Agenda-first.

## Principios de Diseño

1. **Valor real desde la primera pantalla** - NO landing pages con videos
2. **Transición rápida a la interfaz real** - Login → Agenda inmediatamente
3. **UI clara y densa** - Muchos registros visibles, tablas compactas
4. **Confirmaciones explícitas** - Para acciones críticas (delete, finalize, refund)
5. **RBAC estricto** - Permisos del backend respetados en frontend

## Stack Tecnológico

- **Framework**: Next.js 14 (App Router)
- **UI**: React 18 + TypeScript
- **Data Fetching**: TanStack Query (React Query) v5
- **HTTP Client**: Axios
- **Styling**: Tailwind CSS + Custom CSS (system fonts)
- **Date Handling**: date-fns
- **Internationalization**: i18next + react-i18next (5 languages: ru, uk, hy, fr, es)

## Estructura del Proyecto

```
apps/web/src/
├── app/
│   └── [locale]/
│       ├── layout.tsx           # Root layout with providers
│       ├── page.tsx             # Redirects to /agenda or /login
│       ├── login/
│       │   └── page.tsx         # Login page (NO videos, minimal)
│       ├── agenda/
│       │   └── page.tsx         # Agenda (FIRST SCREEN)
│       ├── proposals/
│       │   └── page.tsx         # Proposals list (Reception workflow)
│       ├── encounters/
│       │   └── [id]/
│       │       └── page.tsx     # Encounter detail (Practitioner workflow)
│       └── globals.css          # Global styles (FRONTEND_STYLE_GUIDE_V0)
├── components/
│   ├── layout/
│   │   └── app-layout.tsx       # Main layout with sidebar + i18n
│   ├── language-switcher.tsx   # Language selector (ru/uk/hy/fr/es)
│   └── rbac-guard.tsx           # Component-level permission guard
├── i18n/
│   ├── index.ts                 # i18n configuration
│   └── locales/
│       ├── ru/common.json       # Russian translations (default)
│       ├── uk/common.json       # Ukrainian translations
│       ├── hy/common.json       # Armenian translations
│       ├── fr/common.json       # French translations
│       └── es/common.json       # Spanish translations
└── lib/
    ├── api-client.ts            # Axios with Accept-Language header
    ├── types.ts                 # TypeScript types for all entities
    ├── auth-context.tsx         # Auth context with RBAC helpers
    ├── providers.tsx            # React Query + Auth + i18n providers
    └── hooks/
        ├── use-appointments.ts  # Appointment CRUD hooks
        ├── use-proposals.ts     # Proposal management hooks
        └── use-encounters.ts    # Encounter management hooks
```

## Configuración Inicial

### 1. Instalar Dependencias

```bash
cd apps/web
npm install
```

### 2. Variables de Entorno

Crea un archivo `apps/web/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### 3. Iniciar el Backend

```bash
# Desde la raíz del proyecto
docker-compose up
```

### 4. Iniciar el Frontend

```bash
cd apps/web
npm run dev
```

La aplicación estará disponible en **http://localhost:3000**

## Flujos de Trabajo

### 1. Reception (Recepción)

**Permisos**: `Reception`, `Admin`

**Flujo**:
1. **Agenda** → Ver citas del día
2. **Confirm Appointment** → Cambiar estado a "confirmed"
3. **Check In** → Cuando el paciente llega
4. **Proposals** → Ver propuestas generadas por practitioners
5. **Create Sale** → Convertir propuesta a venta (draft)
6. **Mark as Paid** → Completar la venta (en módulo Sales)

### 2. Practitioner (Profesional Médico)

**Permisos**: `Practitioner`, `ClinicalOps`, `Admin`

**Flujo**:
1. **Agenda** → Ver citas asignadas
2. **Open Encounter** → Crear encounter (draft)
3. **Add Treatments** → Agregar tratamientos al encounter
4. **Finalize Encounter** → Cerrar el encounter (no se puede editar después)
5. **Generate Proposal** → Crear propuesta para Reception

### 3. POS (Punto de Venta)

**Permisos**: `Reception`, `Accounting`, `Admin`

**Flujo**:
1. **Proposals** → Ver propuestas finalizadas
2. **Create Sale** → Convertir a venta (draft)
3. **Edit Sale** → Ajustar items, descuentos, impuestos (en módulo Sales)
4. **Mark as Paid** → Completar la venta

## Sistema de Permisos (RBAC)

### Roles Disponibles

- **Admin**: Acceso completo a todos los módulos
- **Practitioner**: Agenda + Encounters (lectura/escritura)
- **Reception**: Agenda + Proposals + Sales (lectura/escritura)
- **ClinicalOps**: Todos los módulos clínicos (sin ventas)
- **Accounting**: Proposals + Sales + Reportes financieros
- **Marketing**: Reportes de pacientes y campañas

### Implementación en Componentes

#### Page-Level Guard

```tsx
import { RBACGuard } from '@/components/rbac-guard';
import { ROLES } from '@/lib/auth-context';

export default function ProposalsPage() {
  return (
    <RBACGuard roles={[ROLES.ADMIN, ROLES.RECEPTION]}>
      {/* Contenido de la página */}
    </RBACGuard>
  );
}
```

#### Component-Level Guard

```tsx
import { useHasAnyRole } from '@/lib/auth-context';
import { ROLES } from '@/lib/auth-context';

function MyComponent() {
  const canViewFinancials = useHasAnyRole([ROLES.ADMIN, ROLES.ACCOUNTING]);

  return (
    <div>
      {canViewFinancials && <FinancialSummary />}
    </div>
  );
}
```

## API Client

### Configuración Automática

El cliente API (`lib/api-client.ts`) incluye:

- **Base URL**: `NEXT_PUBLIC_API_URL` (env variable)
- **Request Interceptor**: Inyecta `Authorization: Bearer {token}` desde localStorage
- **Response Interceptor**: Maneja 401 (token expirado) → redirige a `/login`
- **Timeout**: 30 segundos

### Uso en Hooks

```tsx
import apiClient from '@/lib/api-client';

// GET request
const response = await apiClient.get<Appointment>('/clinical/appointments/123/');

// POST request
const response = await apiClient.post<Appointment>('/clinical/appointments/', data);

// PATCH request
const response = await apiClient.patch<Appointment>('/clinical/appointments/123/', { status: 'confirmed' });
```

## React Query Hooks

### Appointments

```tsx
import { useAppointments, useUpdateAppointmentStatus } from '@/lib/hooks/use-appointments';

function AgendaPage() {
  const { data, isLoading } = useAppointments({ date: '2025-12-22', status: 'scheduled' });
  const updateStatus = useUpdateAppointmentStatus();

  const handleConfirm = (id: string) => {
    updateStatus.mutate({ id, status: 'confirmed' });
  };
}
```

### Proposals

```tsx
import { useProposals, useConvertProposalToSale } from '@/lib/hooks/use-proposals';

function ProposalsPage() {
  const { data } = useProposals({ status: 'draft' });
  const convertToSale = useConvertProposalToSale();

  const handleCreateSale = (proposalId: string, legalEntityId: string) => {
    convertToSale.mutate({ proposalId, legalEntityId });
  };
}
```

### Encounters

```tsx
import { useEncounter, useAddTreatment, useFinalizeEncounter } from '@/lib/hooks/use-encounters';

function EncounterDetailPage({ id }: { id: string }) {
  const { data: encounter } = useEncounter(id);
  const addTreatment = useAddTreatment();
  const finalize = useFinalizeEncounter();

  const handleAddTreatment = () => {
    addTreatment.mutate({
      encounterId: id,
      treatmentId: 'abc-123',
      quantity: 2,
    });
  };

  const handleFinalize = () => {
    finalize.mutate(id);
  };
}
```

## Guía de Estilos

Ver **docs/FRONTEND_STYLE_GUIDE_V0.md** para:

- **Paleta de colores** (Professional Blue primary, semantic status colors)
- **Tipografía** (system font stack, tamaños, pesos)
- **Componentes** (buttons, cards, tables, badges, forms, modals)
- **Layout** (grid 240px sidebar + 1fr content)
- **Accesibilidad** (WCAG AA, focus indicators, keyboard navigation)
- **Animaciones** (subtle, fast, purposeful only)

### Colores Principales

```css
--primary-500: #2196f3;  /* Professional Blue */
--success: #4caf50;       /* Green */
--warning: #ff9800;       /* Orange */
--error: #f44336;         /* Red */
```

### Badges de Estado

```tsx
<span className="badge badge-scheduled">scheduled</span>
<span className="badge badge-confirmed">confirmed</span>
<span className="badge badge-cancelled">cancelled</span>
```

## Testing

### Backend API (Manual)

1. Iniciar el backend: `docker-compose up`
2. Verificar health: `curl http://localhost:8000/health/`
3. Login: `POST http://localhost:8000/api/v1/auth/login/` con `{ email, password }`

### Frontend (Manual)

1. Abrir DevTools → Application → Local Storage
2. Verificar `auth_token` y `user` después de login
3. Probar flujos completos (Agenda → Proposals → Sales)

## Troubleshooting

### "Network Error" en todas las requests

- **Causa**: Backend no está corriendo o CORS no configurado
- **Solución**: `docker-compose up` y verificar CORS en `backend/settings.py`

### "401 Unauthorized" después de login

- **Causa**: Token no se está guardando en localStorage
- **Solución**: Verificar que `login()` en `auth-context.tsx` guarda `auth_token`

### Estilos no se aplican

- **Causa**: Tailwind CSS no compilando o globals.css no importado
- **Solución**: Verificar que `globals.css` está importado en `layout.tsx`

### React Query no refetching después de mutación

- **Causa**: Query keys no están invalidándose
- **Solución**: Verificar que `queryClient.invalidateQueries()` está en `onSuccess`

## Internationalization (i18n)

The app supports **5 languages**: Russian (ru, default), Ukrainian (uk), Armenian (hy), French (fr), and Spanish (es).

**Features:**
- Language selector in sidebar footer
- Translations persist in localStorage
- Accept-Language header sent to backend on all API requests
- Navigation and common UI elements translated

**Usage:**
```tsx
import { useTranslation } from 'react-i18next';

function MyComponent() {
  const { t } = useTranslation();
  return <h1>{t('nav.agenda')}</h1>;
}
```

**Documentation**: See `docs/FRONTEND_I18N.md` for complete guide.

**Manual Verification:**
1. Start app and login
2. Open sidebar footer
3. Select different language from dropdown
4. Verify navigation labels change
5. Reload page → language persists

## Próximos Pasos

### Corto Plazo

- [ ] Módulo de Patients (CRUD completo)
- [ ] Módulo de Sales (editar draft, mark as paid, refunds)
- [ ] Formularios de creación (appointments, encounters)
- [ ] Búsqueda y filtros avanzados
- [ ] Paginación en tablas

### Mediano Plazo

- [ ] Reportes (ventas, pacientes, tratamientos más vendidos)
- [ ] Notificaciones (toasts para success/error)
- [ ] Optimistic updates en todas las mutaciones
- [ ] Tests unitarios (Vitest + Testing Library)
- [ ] Tests E2E (Playwright)

### Largo Plazo

- [ ] Dashboard con métricas clave
- [ ] Calendario interactivo (drag & drop)
- [ ] Chat interno (practitioner ↔ reception)
- [ ] Historial clínico del paciente (encounters timeline)
- [ ] Exportación de reportes (PDF, Excel)

## Referencias

- **Backend API**: `http://localhost:8000/api/docs/` (Swagger UI)
- **Design System**: `docs/FRONTEND_STYLE_GUIDE_V0.md`
- **Internationalization**: `docs/FRONTEND_I18N.md`
- **Architecture**: `docs/ARCHITECTURE.md`
- **RBAC**: `docs/RBAC.md`

## Contacto

Para preguntas o issues, revisar la documentación completa en `docs/`.
