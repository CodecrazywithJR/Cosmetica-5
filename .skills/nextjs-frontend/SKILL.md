---
name: nextjs-frontend
description: Use when building or maintaining Next.js 14 applications with App Router, React Server Components, TypeScript, TailwindCSS, React Query (TanStack), next-intl for i18n, and Zod for validation.
license: MIT
metadata:
  author: Cosmetica-5 Team
  version: "1.0.0"
  domain: frontend
  triggers: Next.js, React, TypeScript, TailwindCSS, React Query, next-intl, i18n, App Router, Server Components, Zod, frontend components, pages, layouts
  role: specialist
  scope: implementation
  output-format: code
  related-skills: api-designer, test-master
---

# Next.js Frontend

Next.js 14 specialist with App Router, TypeScript, TailwindCSS, and React Query.

## When to Use This Skill

- Building pages, layouts, or components in Next.js App Router
- Implementing data fetching with React Query (TanStack)
- Adding i18n translations with next-intl
- Form validation with Zod
- API integration with axios
- Responsive UI with TailwindCSS
- Client vs Server Component decisions

## Core Workflow

1. **Decide component type** — Server Component (default) vs Client Component (`'use client'`)
2. **Define the data contract** — TypeScript interfaces matching API response
3. **Implement data fetching** — React Query for client, `fetch()` for server
4. **Build UI** — TailwindCSS utilities, responsive design
5. **Add i18n** — `useTranslations()` hook, message keys
6. **Validate forms** — Zod schemas, controlled inputs
7. **Test** — Component tests, API mocking

## Constraints

### MUST DO
- Use TypeScript strict mode — no `any` types
- Default to Server Components — only use `'use client'` when needed (hooks, events)
- Use React Query for all client-side API calls (caching, loading states, refetching)
- Define Zod schemas for form validation matching backend serializers
- Use `next-intl` message keys — never hardcode user-facing text
- Use TailwindCSS — no inline styles, no CSS modules
- Handle loading, error, and empty states explicitly
- Use `Suspense` boundaries for async Server Components
- Keep components small — extract into reusable pieces
- Use `next/image` for all images (optimization)

### MUST NOT DO
- Use `useEffect` for data fetching — use React Query
- Hardcode API URLs — use environment variables (`NEXT_PUBLIC_API_URL`)
- Mix Server and Client logic in the same file without clear boundaries
- Use `window` or `document` in Server Components
- Skip loading/error states
- Use `dangerouslySetInnerHTML` without sanitization
- Import large libraries in Server Components
- Use `'use client'` on layout files unnecessarily

## Data Fetching Pattern

```typescript
// hooks/usePatients.ts
'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Patient, PatientCreate } from '@/types/patient';

export function usePatients(page: number = 1) {
  return useQuery({
    queryKey: ['patients', page],
    queryFn: () => api.get<PaginatedResponse<Patient>>(`/api/v1/clinical/patients/?page=${page}`),
  });
}

export function useCreatePatient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: PatientCreate) => api.post('/api/v1/clinical/patients/', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['patients'] }),
  });
}
```

## Component Pattern

```tsx
// components/PatientCard.tsx
import { useTranslations } from 'next-intl';
import type { Patient } from '@/types/patient';

interface PatientCardProps {
  patient: Patient;
  onSelect: (id: number) => void;
}

export function PatientCard({ patient, onSelect }: PatientCardProps) {
  const t = useTranslations('patients');

  return (
    <div
      className="rounded-lg border p-4 hover:shadow-md transition-shadow cursor-pointer"
      onClick={() => onSelect(patient.id)}
    >
      <h3 className="font-semibold text-gray-900">
        {patient.first_name} {patient.last_name}
      </h3>
      <p className="text-sm text-gray-500">{patient.email}</p>
      <span className="text-xs text-gray-400">
        {t('lastVisit')}: {patient.last_visit ?? t('never')}
      </span>
    </div>
  );
}
```

## Form Validation Pattern

```typescript
// schemas/patient.ts
import { z } from 'zod';

export const patientSchema = z.object({
  first_name: z.string().min(1, 'Required').max(100),
  last_name: z.string().min(1, 'Required').max(100),
  email: z.string().email('Invalid email'),
  phone: z.string().optional(),
  date_of_birth: z.string().refine((v) => !isNaN(Date.parse(v)), 'Invalid date'),
});

export type PatientFormData = z.infer<typeof patientSchema>;
```

## Project-Specific Notes (Cosmetica 5)

- **Two frontends**: `apps/web/` (ERP dashboard) and `apps/site/` (public website)
- **API base**: `NEXT_PUBLIC_API_URL` pointing to Django backend
- **Auth**: JWT stored in httpOnly cookies or localStorage
- **i18n**: `next-intl` with French/English/Spanish support
- **Calendly**: `react-calendly` integration for booking
- **State**: React Query for server state, no Redux/Zustand needed
- **Date handling**: `date-fns` (not moment.js)
