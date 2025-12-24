# Frontend i18n Refactor - 3 Commits

> **Status**: ✅ COMPLETED  
> **Date**: 2025-12-24  
> **Objective**: Eliminate react-i18next legacy, consolidate routes under [locale]/, ensure next-intl is the single i18n system

---

## Summary

This refactor cleans up dual i18n systems (react-i18next + next-intl) and reorganizes all routes under the `[locale]/` structure for proper internationalization with Next.js 14 App Router.

**Key Changes**:
- ✅ Default locale: `en` (English)
- ✅ Removed all `react-i18next` imports and config
- ✅ All routes now under `src/app/[locale]/`
- ✅ Legacy routes redirect to `/en/...`
- ✅ Navigation uses locale-aware helper

---

## COMMIT 1: i18n System Cleanup

**Files Changed**:
```
apps/web/
  src/i18n/                           → MOVED TO: _legacy/i18n/
  _legacy/i18n/README.md              → CREATED (deprecation notice)
  src/lib/api-client.ts               → UPDATED (removed react-i18next)
  src/components/language-switcher.tsx → UPDATED (next-intl)
  src/components/layout/app-layout.tsx → UPDATED (next-intl)
docs/PROJECT_DECISIONS.md             → UPDATED (section 7.3)
```

**Changes**:
1. **Archived Legacy i18n**
   - Moved `src/i18n/` to `_legacy/i18n/`
   - Added README explaining deprecation
   - Preserved for reference during migration

2. **api-client.ts** (Axios instance)
   ```diff
   - import i18n from '@/i18n';
   - headers: { 'Accept-Language': i18n.language }
   + const locale = window.location.pathname.split('/')[1];
   + headers: { 'Accept-Language': locale || 'en' }
   ```

3. **language-switcher.tsx**
   ```diff
   - import { useTranslation } from 'react-i18next';
   - const { i18n } = useTranslation();
   + import { useLocale, useRouter } from 'next-intl';
   + const locale = useLocale();
   + const router = useRouter();
   ```

4. **app-layout.tsx**
   ```diff
   - import { useTranslation } from 'react-i18next';
   - const { t } = useTranslation('nav');
   + import { useTranslations } from 'next-intl';
   + const t = useTranslations('nav');
   ```

**Rationale**:
- react-i18next is client-only, incompatible with App Router SSR
- next-intl is designed for Next.js 14+ with full server component support
- Maintaining two i18n systems causes conflicts and duplicate bundles

---

## COMMIT 2: Route Reorganization

**Files Changed**:
```
apps/web/src/app/
  [locale]/
    page.tsx                        → UPDATED (next-intl)
    encounters/                     → MOVED FROM: app/encounters/
      [id]/page.tsx                 → UPDATED (next-intl)
    proposals/                      → MOVED FROM: app/proposals/
      page.tsx                      → UPDATED (next-intl)
    login/                          → ALREADY EXISTS (duplicate removed)
  agenda/                           → REMOVED (consolidated into [locale]/page.tsx)
  encounters/                       → REMOVED (moved under [locale]/)
  proposals/                        → REMOVED (moved under [locale]/)
docs/PROJECT_DECISIONS.md           → UPDATED (section 7.5)
```

**Changes**:
1. **Moved Routes**
   - `app/encounters/` → `app/[locale]/encounters/`
   - `app/proposals/` → `app/[locale]/proposals/`
   - Removed duplicate `app/login/` (kept `[locale]/login/`)

2. **Updated Pages to next-intl**
   ```typescript
   // Before (all pages)
   import { useTranslation } from 'react-i18next';
   const { t, i18n } = useTranslation(['namespace', 'common']);

   // After
   import { useTranslations } from 'next-intl';
   const t = useTranslations('namespace');
   const tCommon = useTranslations('common');
   ```

3. **Verified Structure**
   ```
   app/
     [locale]/
       page.tsx                  → /en, /ru, /fr (dashboard/agenda)
       encounters/[id]/page.tsx  → /en/encounters/123
       proposals/page.tsx        → /en/proposals
       login/page.tsx            → /en/login
     api/                        → (API routes, no locale)
   ```

**Rationale**:
- URL-based locale detection (`/en/encounters` vs `/ru/encounters`)
- Enables static generation per locale
- Shareable, SEO-friendly URLs
- Browser history preserves locale preference

---

## COMMIT 3: Redirects and Navigation

**Files Created**:
```
apps/web/src/
  app/
    agenda/page.tsx                 → CREATED (redirect to /en)
    encounters/[id]/page.tsx        → CREATED (redirect to /en/encounters/:id)
    proposals/page.tsx              → CREATED (redirect to /en/proposals)
  lib/routing.ts                    → CREATED (locale-aware route helper)
```

**Files Updated**:
```
apps/web/src/
  components/layout/app-layout.tsx  → UPDATED (uses routing helper)
docs/PROJECT_DECISIONS.md           → UPDATED (section 7.8)
```

**Changes**:
1. **Legacy Redirects**
   ```typescript
   // app/agenda/page.tsx
   export default function LegacyAgendaRedirect() {
     redirect('/en');
   }

   // app/encounters/[id]/page.tsx
   export default function LegacyEncounterRedirect({ params }) {
     redirect(`/en/encounters/${params.id}`);
   }

   // app/proposals/page.tsx
   export default function LegacyProposalsRedirect() {
     redirect('/en/proposals');
   }
   ```

2. **Routing Helper** (`lib/routing.ts`)
   ```typescript
   export const routes = {
     dashboard: (locale) => `/${locale}`,
     encounters: {
       list: (locale) => `/${locale}/encounters`,
       detail: (locale, id) => `/${locale}/encounters/${id}`,
     },
     proposals: {
       list: (locale) => `/${locale}/proposals`,
     },
     login: (locale) => `/${locale}/login`,
   };
   ```

3. **Updated Navigation** (app-layout.tsx)
   ```typescript
   import { routes, type Locale } from '@/lib/routing';
   import { useLocale } from 'next-intl';

   const locale = useLocale() as Locale;

   const navigation = [
     { name: t('agenda'), href: routes.dashboard(locale) },
     { name: t('encounters'), href: routes.encounters.list(locale) },
     { name: t('proposals'), href: routes.proposals.list(locale) },
   ];
   ```

**Rationale**:
- Backward compatibility with old bookmarks
- Smooth migration without breaking existing links
- Centralized route management prevents hardcoded paths
- Type-safe routing with TypeScript

---

## Verification Steps

1. **No react-i18next Imports**
   ```bash
   grep -r "from 'react-i18next'" apps/web/src/
   # Should return: No matches (except _legacy/)
   ```

2. **All Routes Under [locale]/**
   ```bash
   ls apps/web/src/app/[locale]/
   # Should show: page.tsx, encounters/, proposals/, login/
   ```

3. **Redirects Work**
   ```bash
   # Visit http://localhost:3000/agenda
   # Should redirect to: http://localhost:3000/en
   ```

4. **Navigation Links Include Locale**
   ```typescript
   // All sidebar links should be:
   /en/encounters
   /en/proposals
   /ru/encounters  (when switching to Russian)
   ```

---

## Configuration Files

**apps/web/i18n.ts** (Root config)
```typescript
import { getRequestConfig } from 'next-intl/server';

export default getRequestConfig(async ({ locale }) => ({
  messages: (await import(`../messages/${locale}.json`)).default,
}));
```

**apps/web/src/middleware.ts**
```typescript
import createMiddleware from 'next-intl/middleware';

export default createMiddleware({
  locales: ['en', 'ru', 'fr', 'uk', 'hy', 'es'],
  defaultLocale: 'en',
  localePrefix: 'always'
});

export const config = {
  matcher: ['/((?!api|_next|_vercel|.*\\..*).*)']
};
```

---

## Migration Guide for New Pages

When creating new pages:

1. **Place under [locale]/ directory**
   ```
   ✅ CORRECT: apps/web/src/app/[locale]/patients/page.tsx
   ❌ WRONG:   apps/web/src/app/patients/page.tsx
   ```

2. **Use next-intl hooks**
   ```typescript
   import { useTranslations, useLocale } from 'next-intl';

   const t = useTranslations('namespace');
   const locale = useLocale();
   ```

3. **Use routing helper for navigation**
   ```typescript
   import { routes } from '@/lib/routing';

   // Instead of: router.push('/encounters/123')
   router.push(routes.encounters.detail(locale, '123'));
   ```

4. **Add to routing helper if needed**
   ```typescript
   // lib/routing.ts
   export const routes = {
     // ...existing routes
     patients: {
       list: (locale) => `/${locale}/patients`,
       detail: (locale, id) => `/${locale}/patients/${id}`,
     },
   };
   ```

---

## Breaking Changes

**None for end users** - all legacy routes redirect automatically.

**For developers**:
- ❌ **Cannot import** from `@/i18n` (moved to `_legacy/`)
- ❌ **Cannot use** `useTranslation` from `react-i18next`
- ✅ **Must use** `useTranslations` from `next-intl`
- ✅ **Must place** new pages under `[locale]/`

---

## Documentation Updates

- **PROJECT_DECISIONS.md**: Updated sections 7.1-7.8 with:
  - English as default locale (changed from Russian)
  - next-intl as sole i18n system
  - URL-based routing with [locale]/ structure
  - Legacy redirect strategy
  - Routing helper pattern

---

## Benefits Achieved

1. ✅ **Single i18n System**: No more conflicts between react-i18next and next-intl
2. ✅ **Type Safety**: Full TypeScript support for translations
3. ✅ **SSR Compatible**: Server components can use translations
4. ✅ **SEO Friendly**: Each locale has distinct URLs
5. ✅ **Maintainable**: Centralized routing with type-safe helper
6. ✅ **Backward Compatible**: Legacy routes redirect seamlessly

---

## Next Steps (Future Work)

- [ ] Add translation files for all locales in `messages/` directory
- [ ] Implement locale detection from user preferences
- [ ] Add locale switcher to persist choice in cookies
- [ ] Create missing pages (patients, sales, admin) under [locale]/
- [ ] Add E2E tests for locale switching and redirects

---

## References

- [next-intl Documentation](https://next-intl-docs.vercel.app/)
- [Next.js i18n Routing](https://nextjs.org/docs/app/building-your-application/routing/internationalization)
- [PROJECT_DECISIONS.md Section 7](../docs/PROJECT_DECISIONS.md#7-internationalization-i18n)
- [FRONTEND_I18N.md](../docs/FRONTEND_I18N.md)
