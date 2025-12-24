# UX Patterns - Cosmetica 5 ERP

> **Purpose**: Standard UX patterns and guidelines for building consistent modules across the ERP.  
> **Reference Module**: Agenda (apps/web/src/app/[locale]/page.tsx)  
> **Last Updated**: 2025-12-24  
> **Status**: FASE 2 Complete - Production Ready

---

## Table of Contents

1. [Standard Page Structure](#standard-page-structure)
2. [Data State Management](#data-state-management)
3. [Component Reusability](#component-reusability)
4. [CSS Classes Reference](#css-classes-reference)
5. [Real Example: Agenda Module](#real-example-agenda-module)
6. [What NOT to Do](#what-not-to-do)

---

## 1. Standard Page Structure

Every ERP module page should follow this structure:

```tsx
'use client';

import AppLayout from '@/components/layout/app-layout';
import { DataState } from '@/components/data-state';
import { useTranslations, useLocale } from 'next-intl';
// Import your hooks and types

export default function ModulePage() {
  const t = useTranslations('yourModule');
  const tCommon = useTranslations('common');
  const locale = useLocale();

  // State management
  const [filters, setFilters] = useState({});
  
  // Data fetching
  const { data, isLoading, error } = useYourDataHook(filters);

  return (
    <AppLayout>
      <div>
        {/* 1. PAGE HEADER */}
        <div className="page-header">
          <h1>{t('title')}</h1>
          <div className="flex gap-2">
            {/* Filters or action buttons */}
          </div>
        </div>

        {/* 2. DATA STATE MANAGEMENT */}
        <DataState
          isLoading={isLoading}
          error={error}
          isEmpty={data?.results.length === 0}
          emptyMessage={t('emptyState.message')}
          emptyAction={{
            label: t('emptyState.action'),
            onClick: handleCreate, // or undefined if not implemented
          }}
          loadingMessage={tCommon('loading')}
          errorMessage={t('errors.loadingFailed')}
        >
          {/* 3. SUCCESS STATE - YOUR CONTENT */}
          <div className="card">
            {/* Table, list, or custom layout */}
          </div>

          {/* 4. OPTIONAL FOOTER */}
          {data && data.results.length > 0 && (
            <div style={{ marginTop: '16px', fontSize: '14px', color: 'var(--gray-600)' }}>
              {t('summary.totalItems')}: {data.count}
            </div>
          )}
        </DataState>
      </div>
    </AppLayout>
  );
}
```

### Key Elements:

1. **AppLayout**: Wrapper that provides sidebar and main content area
2. **Page Header**: Title + filters/actions (uses `.page-header` class)
3. **DataState**: Handles loading/error/empty/success states automatically
4. **Card**: Content container (uses `.card` class)
5. **Footer**: Optional summary or pagination info

---

## 2. Data State Management

### Using the DataState Component

The `<DataState>` component unifies how we handle different data states:

**Props:**
```typescript
interface DataStateProps {
  isLoading: boolean;          // From React Query
  error?: Error | null;         // From React Query
  isEmpty?: boolean;            // Your condition: data?.results.length === 0
  emptyMessage?: string;        // User-friendly message
  emptyDescription?: string;    // Optional context
  emptyAction?: {               // Optional CTA button
    label: string;
    onClick?: () => void;
  };
  loadingMessage?: string;      // Default: "Loading..."
  errorMessage?: string;        // Custom error message
  children: ReactNode;          // Your success content
}
```

**States Handled:**

1. **Loading State**
   - Shows centered card with loading message
   - Uses `tCommon('loading')` for i18n

2. **Error State**
   - Shows red alert with error message
   - Uses `.alert-error` CSS class
   - Automatically includes error.message

3. **Empty State**
   - Shows centered card with:
     - Icon (📋 emoji)
     - Message (from i18n)
     - Optional description
     - CTA button (can be disabled with `onClick: undefined`)

4. **Success State**
   - Renders children (your content)
   - Data is guaranteed to exist and not be empty

### Example Usage:

```tsx
<DataState
  isLoading={isLoading}
  error={error}
  isEmpty={data?.results.length === 0}
  emptyMessage={t('emptyState.message')}
  emptyAction={{
    label: t('emptyState.action'),
    onClick: undefined, // No functionality yet
  }}
  loadingMessage={tCommon('loading')}
  errorMessage={t('errors.loadingFailed')}
>
  <YourContent data={data} />
</DataState>
```

---

## 3. Component Reusability

### Available Components:

1. **AppLayout** (`@/components/layout/app-layout`)
   - Provides sidebar + main content area
   - Automatically handles user authentication
   - Required wrapper for all ERP pages

2. **DataState** (`@/components/data-state`)
   - Handles loading/error/empty/success states
   - See section 2 for details

3. **RBACGuard** (`@/components/rbac-guard`)
   - Role-based access control
   - Usage: `<RBACGuard requiredRoles={['Admin', 'ClinicalOps']}>`

4. **LanguageSwitcher** (`@/components/language-switcher`)
   - Already integrated in AppLayout sidebar
   - Don't use directly in pages

### Hooks:

All data hooks follow the same pattern from React Query:

```tsx
const { data, isLoading, error, refetch } = useYourDataHook(params);
const mutation = useYourMutationHook();

// Usage
mutation.mutate({ id, ...data }, {
  onSuccess: () => refetch(),
  onError: (err) => console.error(err),
});
```

---

## 4. CSS Classes Reference

### Layout Classes:

- `.app-layout` - Grid layout (sidebar + main)
- `.page-header` - Page title + actions container
- `.card` - White container with border
- `.card-header` - Card header with bottom border
- `.card-body` - Card content padding

### Button Classes:

- `.btn-primary` - Blue primary button
- `.btn-secondary` - White bordered button
- `.btn-destructive` - Red button
- `.btn-sm` - Small button variant

### Table Classes:

- `.table` - Full-width table with borders
- `.table thead` - Gray header background
- `.table th` - Header cell styling
- `.table td` - Data cell styling
- `.table tbody tr:hover` - Row hover effect

### Status Badges:

- `.badge` - Base badge class
- `.badge-scheduled` - Blue badge
- `.badge-confirmed` - Green badge
- `.badge-completed` - Gray badge
- `.badge-cancelled` - Red badge
- `.badge-no_show` - Orange badge

### Alert Classes:

- `.alert-error` - Red error alert
- `.alert-success` - Green success alert
- `.alert-info` - Blue info alert

### Form Classes:

- `.form-group` - Input/select wrapper
- `.form-label` - Label styling
- `.form-error` - Error message styling

### Utility Classes:

- `.flex` - Display flex
- `.gap-2` - Gap 8px
- `.items-center` - Align items center
- `.justify-between` - Space between
- `.w-full` - Width 100%
- `.text-center` - Text align center
- `.mt-4` / `.mb-4` - Margin top/bottom 16px

**DO NOT create new global CSS classes. Use existing ones.**

---

## 5. Real Example: Agenda Module

**File**: `apps/web/src/app/[locale]/page.tsx`

This is the reference implementation. Key patterns:

### Structure:
```tsx
export default function AgendaPage() {
  // 1. Translations
  const t = useTranslations('agenda');
  const tCommon = useTranslations('common');
  const locale = useLocale();

  // 2. State (filters)
  const [selectedDate, setSelectedDate] = useState(
    new Date().toISOString().split('T')[0]
  );
  const [statusFilter, setStatusFilter] = useState<string>('');

  // 3. Data fetching
  const { data, isLoading, error } = useAppointments({
    date: selectedDate,
    status: statusFilter || undefined,
  });

  // 4. Mutations
  const updateStatus = useUpdateAppointmentStatus();

  // 5. Formatters (locale-aware)
  const dateFormatter = useMemo(
    () => new Intl.DateTimeFormat(locale, { ... }),
    [locale]
  );

  // 6. Render with DataState
  return (
    <AppLayout>
      <div className="page-header">...</div>
      <DataState ...>
        <div className="card">
          <table className="table">...</table>
        </div>
      </DataState>
    </AppLayout>
  );
}
```

### Why Agenda is the Pattern:

1. ✅ Uses DataState for all states
2. ✅ Clear page structure
3. ✅ Locale-aware formatters
4. ✅ Filters in header
5. ✅ Clean i18n usage
6. ✅ No hardcoded endpoints (uses API_ROUTES)
7. ✅ Professional empty state
8. ✅ Uses existing CSS classes only

---

## 6. What NOT to Do

### ❌ DON'T:

1. **Create new global CSS classes**
   - Use existing classes from globals.css
   - If needed, use inline styles sparingly

2. **Handle states manually**
   ```tsx
   // ❌ BAD
   {isLoading ? <div>Loading...</div> : 
    error ? <div>Error</div> : 
    data?.length === 0 ? <div>Empty</div> : 
    <YourContent />}
   
   // ✅ GOOD
   <DataState isLoading={isLoading} error={error} isEmpty={...}>
     <YourContent />
   </DataState>
   ```

3. **Hardcode endpoint strings**
   ```tsx
   // ❌ BAD
   const response = await apiClient.get('/clinical/appointments/');
   
   // ✅ GOOD
   import { API_ROUTES } from '@/lib/api-config';
   const response = await apiClient.get(API_ROUTES.CLINICAL.APPOINTMENTS);
   ```

4. **Use i18n.language directly**
   ```tsx
   // ❌ BAD
   new Intl.DateTimeFormat(i18n.language, { ... });
   
   // ✅ GOOD
   const locale = useLocale();
   new Intl.DateTimeFormat(locale, { ... });
   ```

5. **Create duplicate empty state logic**
   - Always use DataState component

6. **Ignore translations**
   ```tsx
   // ❌ BAD
   <h1>Agenda</h1>
   
   // ✅ GOOD
   <h1>{t('title')}</h1>
   ```

7. **Break the page structure**
   - Always wrap with AppLayout
   - Always use page-header → DataState → content pattern

8. **Invent new button styles**
   - Use btn-primary, btn-secondary, btn-destructive
   - Use btn-sm for smaller variants

### ✅ DO:

1. **Follow the Agenda pattern exactly**
2. **Reuse DataState for all modules**
3. **Use existing CSS classes**
4. **Keep translations organized by module**
5. **Use locale-aware formatters**
6. **Use API_ROUTES constants**
7. **Document deviations from pattern**

---

## Summary

**Pattern Checklist for New Modules:**

- [ ] Wrap with `<AppLayout>`
- [ ] Use `<DataState>` for state management
- [ ] Page header with `.page-header`
- [ ] Use existing CSS classes only
- [ ] Implement i18n with `useTranslations('module')`
- [ ] Use `useLocale()` for formatters
- [ ] Use API_ROUTES for endpoints
- [ ] Follow Agenda structure
- [ ] No hardcoded strings
- [ ] Professional empty state with CTA

**When in doubt, copy from Agenda.**
