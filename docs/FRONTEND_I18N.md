# Frontend Internationalization (i18n)

## Overview

The Frontend MVP uses **i18next** and **react-i18next** for internationalization. This document describes the setup, conventions, and usage patterns.

## Supported Languages

| Code | Language | Native Name |
|------|----------|-------------|
| `ru` | Russian (default) | Русский |
| `uk` | Ukrainian | Українська |
| `hy` | Armenian | Հայերեն |
| `fr` | French | Français |
| `es` | Spanish | Español |

**Default language**: Russian (`ru`)

## Architecture

### File Structure

```
apps/web/src/
├── i18n/
│   ├── index.ts                    # i18n initialization and configuration
│   └── locales/
│       ├── ru/
│       │   ├── common.json         # Russian common translations
│       │   ├── agenda.json         # Russian agenda translations
│       │   └── pos.json            # Russian proposals/POS translations
│       ├── uk/
│       │   ├── common.json         # Ukrainian common translations
│       │   ├── agenda.json         # Ukrainian agenda translations
│       │   └── pos.json            # Ukrainian proposals/POS translations
│       ├── hy/
│       │   ├── common.json         # Armenian common translations
│       │   ├── agenda.json         # Armenian agenda translations
│       │   └── pos.json            # Armenian proposals/POS translations
│       ├── fr/
│       │   ├── common.json         # French common translations
│       │   ├── agenda.json         # French agenda translations
│       │   └── pos.json            # French proposals/POS translations
│       └── es/
│           ├── common.json         # Spanish common translations
│           ├── agenda.json         # Spanish agenda translations
│           └── pos.json            # Spanish proposals/POS translations
├── components/
│   └── language-switcher.tsx       # Language selector component
└── lib/
    ├── providers.tsx               # I18nextProvider wrapper
    └── api-client.ts               # Axios with Accept-Language header
```

### Initialization

i18n is initialized in `src/i18n/index.ts` with:
- Resource loading from JSON files
- Multiple namespaces: `common` (shared), `agenda` (appointments), `pos` (proposals/sales)
- Language persistence in `localStorage` (key: `preferred_language`)
- Fallback to Russian (`ru`) if no saved language or invalid value
- Client-side only (no SSR) to avoid hydration mismatches

## Namespaces

### `common` Namespace

Contains shared translations used across the entire application:
- `app.name` - Application name
- `nav.*` - Navigation labels
- `actions.*` - Generic action buttons
- `status.*` - Status messages
- `errors.*` - Generic error messages
- `language.*` - Language names

### `agenda` Namespace

Contains translations specific to the Appointments/Agenda module:
- `agenda.title` - Page title
- `agenda.filters.*` - Filter labels and options
- `agenda.appointment.status.*` - Appointment statuses
- `agenda.appointment.type.*` - Appointment types
- `agenda.table.*` - Table column headers
- `agenda.actions.*` - Action button labels
- `agenda.empty.*` - Empty state messages
- `agenda.summary.*` - Summary labels
- `agenda.errors.*` - Error messages

### `pos` Namespace

Contains translations specific to the Proposals/POS (Point of Sale) module:
- `pos.title` - Page title
- `pos.filters.*` - Filter labels and options
- `pos.proposal.status.*` - Proposal statuses (draft, converted, cancelled)
- `pos.sale.status.*` - Sale statuses (draft, paid, refunded)
- `pos.table.*` - Table column headers
- `pos.labels.*` - Economic labels (quantity, price, total, currency)
- `pos.actions.*` - Action button labels (createSale, cancel, viewSale)
- `pos.modals.*` - Modal titles, descriptions, form labels
- `pos.empty.*` - Empty state messages
- `pos.summary.*` - Summary labels
- `pos.errors.*` - Error messages

### `clinical` Namespace

Contains translations specific to the Encounter (Clinical) module:
- `clinical.encounter.title` - Page title ("Encounter Details")
- `clinical.encounter.status.*` - Encounter statuses (draft, finalized, cancelled)
- `clinical.encounter.type.*` - Encounter types (medical_consult, cosmetic_consult, follow_up, aesthetic_procedure)
- `clinical.sections.*` - Section headers (patientInfo, encounterInfo, treatments)
- `clinical.patientLabels.*` - Patient field labels (name, email, phone, dateOfBirth)
- `clinical.encounterLabels.*` - Encounter field labels (practitioner, type, date, status, chiefComplaint, assessment, plan)
- `clinical.treatmentLabels.*` - Treatment table headers (treatment, quantity, unitPrice, total, notes)
- `clinical.actions.*` - Action buttons (addTreatment, finalize, generateProposal, back, cancel, add, finalizing, generating, adding)
- `clinical.modals.*` - Modal content (addTreatmentTitle, treatmentIdLabel, quantityLabel, unitPriceLabel, notesLabel, finalizeTitle, finalizeWarning, finalizeDescription, finalizeIrreversible, confirmFinalize)
- `clinical.empty.*` - Empty state messages (noTreatments)
- `clinical.messages.*` - Success messages (proposalGenerated, mustAddTreatments)
- `clinical.errors.*` - Error messages (loadingFailed, notFound, addingTreatmentFailed, finalizingFailed, generatingProposalFailed)
- `clinical.loading.*` - Loading messages (encounter)

**Critical Clinical Pattern**: The "Finalize Encounter" action uses a proper modal (NOT browser `confirm()`) with explicit warnings about immutability. This ensures the warning is translatable and properly styled with visual emphasis on irreversibility.

## Usage Patterns

### Basic Translation

```tsx
import { useTranslation } from 'react-i18next';

function MyComponent() {
  const { t } = useTranslation();

  return (
    <div>
      <h1>{t('nav.agenda')}</h1>
      <button>{t('actions.save')}</button>
    </div>
  );
}
```

### Using Specific Namespaces

```tsx
import { useTranslation } from 'react-i18next';

function AgendaPage() {
  // Load specific namespace
  const { t } = useTranslation('agenda');

  return (
    <div>
      <h1>{t('title')}</h1> {/* Uses agenda.title */}
      <button>{t('actions.confirm')}</button> {/* Uses agenda.actions.confirm */}
    </div>
  );
}

// Or load multiple namespaces
function ComplexComponent() {
  const { t } = useTranslation(['agenda', 'common']);

  return (
    <div>
      <h1>{t('agenda:title')}</h1>
      <button>{t('common:actions.save')}</button>
    </div>
  );
}
```

### Translation Keys

All translation keys use **dot notation**:

```typescript
t('key')                    // Uses default namespace
t('namespace:key')          // Uses specific namespace
```

### With Parameters (Interpolation)

```tsx
t('welcome.message', { name: 'John' })
// Translation: "Welcome, {{name}}!"
// Result: "Welcome, John!"
```

### Pluralization

```tsx
t('items', { count: 1 })  // "1 item"
t('items', { count: 5 })  // "5 items"
```

Translation file:
```json
{
  "items_one": "{{count}} item",
  "items_other": "{{count}} items"
}
```

### Dynamic Translation Keys (Agenda Module)

For appointment statuses and types that come from the backend:

```tsx
import { useTranslation } from 'react-i18next';

function AppointmentCard({ appointment }) {
  const { t } = useTranslation('agenda');

  // Translate dynamic status
  const statusLabel = t(`appointment.status.${appointment.status}`);

  // Translate dynamic appointment type
  const typeLabel = t(`appointment.type.${appointment.appointment_type}`);

  return (
    <div>
      <span className={`badge badge-${appointment.status}`}>
        {statusLabel}
      </span>
      <p>{typeLabel}</p>
    </div>
  );
}
```

Supported appointment statuses:
- `scheduled` → "Запланировано" / "Заплановано" / "Նախատեսված" / "Planifié" / "Programado"
- `confirmed` → "Подтверждено" / "Підтверджено" / "Հաստատված" / "Confirmé" / "Confirmado"
- `checked_in` → "Прибыл" / "Прибув" / "Ներկայացել է" / "Arrivé" / "Llegó"
- `completed` → "Завершено" / "Завершено" / "Ավարտված" / "Terminé" / "Completado"
- `cancelled` → "Отменено" / "Скасовано" / "Չեղարկված" / "Annulé" / "Cancelado"
- `no_show` → "Не явился" / "Не з'явився" / "Չներկայացավ" / "Absent" / "No se presentó"

Supported appointment types:
- `medical_consult` → "Мед. консультация" / "Мед. консультація" / "Բժշկական խորհրդատվություն" / "Consultation médicale" / "Consulta médica"
- `cosmetic_consult` → "Косметол. консультация" / "Косметол. консультація" / "Կոսմետիկ խորհրդատվություն" / "Consultation cosmétique" / "Consulta cosmética"
- `follow_up` → "Повторный приём" / "Повторний прийом" / "Հետագա այց" / "Suivi" / "Seguimiento"
- `aesthetic_procedure` → "Эстетическая процедура" / "Естетична процедура" / "Գեղագիտական ​​ընթացակարգ" / "Procédure esthétique" / "Procedimiento estético"

### Dynamic Translation Keys (Clinical/Encounter Module)

For encounter statuses and types that come from the backend:

```tsx
import { useTranslation } from 'react-i18next';

function EncounterCard({ encounter }) {
  const { t } = useTranslation('clinical');

  // Translate dynamic status with fallback
  const statusLabel = t(`encounter.status.${encounter.status}`, encounter.status);

  // Translate dynamic encounter type
  const typeKey = encounter.type.replace(/-/g, '_'); // Convert "medical-consult" → "medical_consult"
  const typeLabel = t(`encounter.type.${typeKey}`, encounter.type);

  return (
    <div>
      <span className={`badge badge-${encounter.status}`}>
        {statusLabel}
      </span>
      <p>{typeLabel}</p>
    </div>
  );
}
```

Supported encounter statuses:
- `draft` → "Черновик" / "Чернетка" / "Սևագիր" / "Brouillon" / "Borrador"
- `finalized` → "Завершено" / "Завершено" / "Ավարտված" / "Finalisé" / "Finalizado"
- `cancelled` → "Отменено" / "Скасовано" / "Չեղարկված" / "Annulé" / "Cancelado"

Supported encounter types:
- `medical_consult` → "Мед. консультация" / "Мед. консультація" / "Բժշկական խորհրդատվություն" / "Consultation médicale" / "Consulta médica"
- `cosmetic_consult` → "Косметол. консультация" / "Косметол. консультація" / "Կոսմետիկ խորհրդատվություն" / "Consultation cosmétique" / "Consulta cosmética"
- `follow_up` → "Повторный приём" / "Повторний прийом" / "Հետագա այց" / "Suivi" / "Seguimiento"
- `aesthetic_procedure` → "Эстетическая процедура" / "Естетична процедура" / "Գեղագիտական ​​ընթացակարգ" / "Procédure esthétique" / "Procedimiento estético"

**Critical Safety Pattern**: The "Finalize Encounter" action uses a proper modal with explicit warnings about immutability:

```tsx
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

function FinalizeEncounterButton({ onFinalize }) {
  const { t } = useTranslation('clinical');
  const [showModal, setShowModal] = useState(false);

  return (
    <>
      <button onClick={() => setShowModal(true)}>
        {t('actions.finalize')}
      </button>

      {showModal && (
        <div className="modal">
          <h2>{t('modals.finalizeTitle')}</h2>
          <p style={{ color: 'var(--warning)' }}>
            {t('modals.finalizeWarning')}
          </p>
          <p>{t('modals.finalizeDescription')}</p>
          <p style={{ color: 'var(--error)', fontWeight: 500 }}>
            {t('modals.finalizeIrreversible')}
          </p>
          <button onClick={() => setShowModal(false)}>
            {t('actions.cancel')}
          </button>
          <button onClick={onFinalize}>
            {t('modals.confirmFinalize')}
          </button>
        </div>
      )}
    </>
  );
}
```

**Why proper modal instead of browser `confirm()`:**
- Browser `confirm()` dialogs cannot be translated (always in browser language)
- Cannot apply visual styling (red text for warnings)
- Cannot show multi-line explanations of consequences
- Inconsistent with application design patterns
- Poor UX for critical clinical action with legal/regulatory implications

**What NOT to Translate in Clinical Module:**
- Clinical notes written by practitioners (`chief_complaint`, `assessment`, `plan`)
- Patient names (`patient.full_name`)
- Practitioner names (`practitioner.display_name`)
- Treatment names from backend catalog (`treatment.name`)
- Notes about specific treatments (`encounter_treatments[].notes`)

These are user-generated or backend-sourced content, not UI labels.

### Date and Number Formatting

Use the browser's `Intl` API for locale-aware formatting:

```tsx
import { useTranslation } from 'react-i18next';

function DateTimeExample() {
  const { i18n } = useTranslation();
  const date = new Date('2024-01-15T14:30:00');

  // Format time
  const timeFormatter = new Intl.DateTimeFormat(i18n.language, {
    hour: '2-digit',
    minute: '2-digit',
  });
  const timeString = timeFormatter.format(date); // "14:30"

  // Format date
  const dateFormatter = new Intl.DateTimeFormat(i18n.language, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
  const dateString = dateFormatter.format(date); // "15 января 2024 г." (ru)

  return (
    <div>
      <p>Date: {dateString}</p>
      <p>Time: {timeString}</p>
    </div>
  );
}
```

### Currency Formatting

**IMPORTANT**: Currency is a **business constant (EUR)**, NOT derived from language.

The system operates with a single currency: **EUR**. User language preference affects **formatting only**, never the currency itself.

```tsx
import { useTranslation } from 'react-i18next';
import { useMemo } from 'react';

function PriceDisplay({ amount }: { amount: number }) {
  const { i18n } = useTranslation();

  // Currency formatter - note the fixed 'EUR' currency
  const currencyFormatter = useMemo(
    () => new Intl.NumberFormat(i18n.language, {
      style: 'currency',
      currency: 'EUR',  // ⚠️ ALWAYS EUR - business constant
    }),
    [i18n.language]
  );

  return <span>{currencyFormatter.format(amount)}</span>;
}
```

**Examples of localized EUR formatting**:
- Russian (`ru`): `1 234,56 €`
- Ukrainian (`uk`): `1 234,56 €`
- Armenian (`hy`): `1234,56 €`
- French (`fr`): `1 234,56 €`
- Spanish (`es`): `1.234,56 €`

**Key Points**:
- ✅ Currency symbol position changes with locale
- ✅ Decimal separator changes with locale (`,` vs `.`)
- ✅ Thousands separator changes with locale
- ❌ Currency code does NOT change (always EUR)
- ❌ Language ≠ Currency (Russian users in France still use EUR)

### Language vs. Currency: Critical Distinction

**Language** and **Currency** are independent concerns:

| Aspect | Language | Currency |
|--------|----------|----------|
| **Nature** | User preference | Business data |
| **Source** | User selection (5 choices) | Legal entity configuration (EUR) |
| **Changes** | Frequently (user switches) | Never (system constant) |
| **Affects** | UI labels, date format, number format | Financial calculations, invoices |
| **Storage** | `localStorage` (frontend) | Database (backend) |

**Example Scenario**:
```
User Profile:
- Language: Russian (ru)
- Location: France
- Legal Entity: French clinic

Result:
- UI displays in Russian: "Продажа", "Итого"
- Numbers formatted with Russian locale: "1 234,56 €"
- Currency is EUR (not RUB) because business operates in France
```

**Anti-Patterns to Avoid**:
- ❌ Deriving currency from language (`ru` → RUB) - INCORRECT
- ❌ Allowing users to select currency - NOT SUPPORTED
- ❌ Mixing currencies in calculations - IMPOSSIBLE (single-currency system)

**Why This Matters**:
1. **Legal Compliance**: French invoices must be in EUR
2. **Accounting**: Financial reports must be in legal entity's currency
3. **UX Clarity**: Users expect business currency, not their native currency
4. **Data Integrity**: Single-currency prevents conversion errors

**See**: `docs/PROJECT_DECISIONS.md` - Currency Strategy for architectural rationale

### Date and Number Formatting

  // Format number
  const numberFormatter = new Intl.NumberFormat(i18n.language);
  const numberString = numberFormatter.format(1234567.89); // "1 234 567,89" (ru)

  return (
    <div>
      <p>{dateString} в {timeString}</p>
      <p>{numberString}</p>
    </div>
  );
}
```

**Why use Intl instead of date-fns?**
- Automatically respects user's locale setting
- No need for locale imports (smaller bundle)
- Built-in browser API (no dependencies)
- Consistent with i18n.language changes

### POS Module: Currency Formatting

For monetary values in the Proposals/POS module, always use currency formatting:

```tsx
import { useTranslation } from 'react-i18next';

function ProposalCard({ proposal }) {
  const { i18n } = useTranslation();

  // Format currency
  const currencyFormatter = new Intl.NumberFormat(i18n.language, {
    style: 'currency',
    currency: 'EUR', // Or use proposal.currency dynamically
  });

  const totalFormatted = currencyFormatter.format(Number(proposal.total_amount));
  // "1 234,56 €" (ru), "€1,234.56" (en), etc.

  return (
    <div>
      <p>{t('pos:labels.totalAmount')}: {totalFormatted}</p>
    </div>
  );
}
```

**Critical for POS:**
- Always format prices with `Intl.NumberFormat` + `currency` style
- Currency code comes from backend (`proposal.currency`)
- Formatting respects locale (decimal separator, grouping, symbol position)
- Use `Number()` to convert string decimals from backend

### POS Module: Status Translation with Fallback

Proposal and sale statuses must be translated with **fallback** to handle new backend values:

```tsx
import { useTranslation } from 'react-i18next';

function ProposalStatus({ status }) {
  const { t } = useTranslation('pos');

  // Use fallback (second parameter) to display raw status if translation missing
  const statusLabel = t(`proposal.status.${status}`, status);

  return <span className={`badge badge-${status}`}>{statusLabel}</span>;
}
```

**Supported proposal statuses:**
- `draft` → "Черновик" / "Чернетка" / "Սևագիր" / "Brouillon" / "Borrador"
- `converted` → "Преобразовано" / "Перетворено" / "Փոխարկված" / "Converti" / "Convertido"
- `cancelled` → "Отменено" / "Скасовано" / "Չեղարկված" / "Annulé" / "Cancelado"

**Supported sale statuses:**
- `draft` → "Черновик" / "Чернетка" / "Սևագիր" / "Brouillon" / "Borrador"
- `paid` → "Оплачено" / "Оплачено" / "Վճարված" / "Payé" / "Pagado"
- `refunded` → "Возвращено" / "Повернуто" / "Վերադարձված" / "Remboursé" / "Reembolsado"

**Why use fallback?**
- Backend may introduce new statuses (e.g., `pending_approval`)
- Fallback prevents UI breaking with "undefined" or blank labels
- Development continues without blocking frontend

### POS Module: Confirmation Modals

Critical actions (convert to sale, cancel proposal) require explicit confirmation:

```tsx
import { useTranslation } from 'react-i18next';

function ConvertModal({ onConfirm, onCancel }) {
  const { t } = useTranslation('pos');

  return (
    <div className="modal">
      <h2>{t('modals.convertTitle')}</h2>
      <p>{t('modals.convertDescription')}</p>
      
      <label>{t('modals.legalEntityLabel')}</label>
      <input placeholder={t('modals.legalEntityPlaceholder')} />
      <small>{t('modals.legalEntityHelp')}</small>

      <button onClick={onCancel}>{t('actions.cancel')}</button>
      <button onClick={onConfirm}>{t('actions.createSale')}</button>
    </div>
  );
}
```

**Translation keys for modals:**
- `pos:modals.convertTitle` - "Convert Proposal to Sale"
- `pos:modals.convertDescription` - Explains what will happen
- `pos:modals.cancelTitle` - "Cancel Proposal"
- `pos:modals.cancelDescription` - Warning about irreversibility
- `pos:modals.legalEntityLabel` - Form field label
- `pos:modals.cancellationReasonLabel` - Form field label

**Design principle:**
- Never skip confirmation for destructive/irreversible actions
- Always translate confirmation messages (user safety)
- Use clear, explicit language about consequences



```tsx
t('items.count', { count: 5 })
// Translation: "{{count}} items"
// Result: "5 items"
```

## Component Integration

### In Functional Components

```tsx
'use client';

import { useTranslation } from 'react-i18next';

export default function MyPage() {
  const { t } = useTranslation();

  return (
    <div>
      <h1>{t('nav.proposals')}</h1>
      <button>{t('actions.create')}</button>
    </div>
  );
}
```

### In App Layout (Navigation)

See `src/components/layout/app-layout.tsx`:

```tsx
const navigation = [
  {
    name: t('nav.agenda'),
    href: '/agenda',
    icon: CalendarIcon,
  },
  {
    name: t('nav.proposals'),
    href: '/proposals',
    icon: FileTextIcon,
  },
  // ...
];
```

## Language Switching

### LanguageSwitcher Component

The `LanguageSwitcher` component is integrated in the sidebar footer (`app-layout.tsx`).

Features:
- Dropdown with all supported languages
- Displays language name in native script (e.g., "Русский", "Українська")
- Saves selection to `localStorage`
- Automatically updates all UI text on change

### Manual Language Change

```tsx
import { useTranslation } from 'react-i18next';

function MyComponent() {
  const { i18n } = useTranslation();

  const changeLanguage = (lang: string) => {
    i18n.changeLanguage(lang);
  };

  return (
    <button onClick={() => changeLanguage('fr')}>
      Switch to French
    </button>
  );
}
```

## Persistence

### localStorage

When the user selects a language:
1. i18n changes the active language
2. `languageChanged` event fires
3. Language code is saved to `localStorage.preferred_language`

On app initialization:
1. i18n reads `localStorage.preferred_language`
2. If valid language code → use it
3. If invalid or missing → fallback to `ru`

### Reset Language

```tsx
localStorage.removeItem('preferred_language');
window.location.reload(); // Will load default language (ru)
```

## Backend Integration

### Accept-Language Header

All API requests automatically include the `Accept-Language` header with the current UI language.

**Implementation** (`src/lib/api-client.ts`):

```typescript
apiClient.interceptors.request.use((config) => {
  // Add Accept-Language header from i18n
  const currentLanguage = i18n.language || 'ru';
  config.headers['Accept-Language'] = currentLanguage;

  return config;
});
```

**Example request**:
```http
GET /api/v1/clinical/appointments/
Authorization: Bearer eyJ0eXAiOiJKV1QiLC...
Accept-Language: ru
```

The backend can use this header to:
- Return error messages in the user's language
- Localize date/time formats
- Provide localized data (if applicable)

## Conventions

### DO ✅

- **Always use `t()` for UI text**
  ```tsx
  <button>{t('actions.save')}</button>
  ```

- **Use semantic key names**
  ```json
  "actions.save": "Сохранить",
  "nav.agenda": "Расписание"
  ```

- **Keep translations in sync**
  - All locale files should have the same keys
  - Missing translations will fallback to default language

- **Group by feature/context**
  ```json
  {
    "nav": { "agenda": "...", "proposals": "..." },
    "actions": { "save": "...", "cancel": "..." },
    "errors": { "generic": "...", "network": "..." }
  }
  ```

### DON'T ❌

- **No hardcoded strings in new UI**
  ```tsx
  // ❌ Bad
  <button>Save</button>

  // ✅ Good
  <button>{t('actions.save')}</button>
  ```

- **Don't translate clinical notes or user-generated content**
  - Patient names, complaints, assessments → NOT translated
  - Only UI labels and system messages

- **Don't use inline translations**
  ```tsx
  // ❌ Bad
  const label = i18n.language === 'ru' ? 'Сохранить' : 'Save';

  // ✅ Good
  const label = t('actions.save');
  ```

## Adding New Translations

### 1. Define Keys in Common Namespace

Edit all locale files (`ru`, `uk`, `hy`, `fr`, `es`):

```json
// src/i18n/locales/ru/common.json
{
  "myFeature": {
    "title": "Мой заголовок",
    "description": "Описание функции"
  }
}
```

### 2. Use in Components

```tsx
const { t } = useTranslation();

<h1>{t('myFeature.title')}</h1>
<p>{t('myFeature.description')}</p>
```

### 3. Add to Other Languages

Ensure all languages have the same keys:

```json
// src/i18n/locales/fr/common.json
{
  "myFeature": {
    "title": "Mon titre",
    "description": "Description de la fonctionnalité"
  }
}
```

## Namespaces (Future)

Currently, all translations are in the `common` namespace. For larger apps, consider organizing by feature:

```
locales/
  ├── ru/
  │   ├── common.json      # Shared UI (nav, actions, errors)
  │   ├── agenda.json      # Agenda-specific translations
  │   ├── proposals.json   # Proposals-specific translations
  │   └── clinical.json    # Clinical-specific translations
```

Usage:
```tsx
const { t } = useTranslation(['agenda', 'common']);
t('agenda:appointment.create');  // From agenda namespace
t('common:actions.save');        // From common namespace
```

## Testing i18n

### Manual Verification

1. Start the app: `npm run dev`
2. Login and navigate to Agenda
3. Open sidebar footer
4. Change language using dropdown
5. Verify:
   - Navigation labels change (Agenda, Proposals, etc.)
   - Action buttons change (Logout)
   - App name changes in sidebar header
   - `localStorage.preferred_language` is set
6. Reload page → language persists

### Automated Testing (Future)

Example test with Vitest + Testing Library:

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import i18n from '@/i18n';
import AppLayout from '@/components/layout/app-layout';

test('changes language when selecting from dropdown', async () => {
  render(
    <I18nextProvider i18n={i18n}>
      <AppLayout>Content</AppLayout>
    </I18nextProvider>
  );

  // Initial language is Russian
  expect(screen.getByText('Расписание')).toBeInTheDocument();

  // Change to French
  const select = screen.getByLabelText(/Язык|Langue|Language/i);
  fireEvent.change(select, { target: { value: 'fr' } });

  // Verify text changed
  expect(await screen.findByText('Agenda')).toBeInTheDocument();
});
```

## Troubleshooting

### Translations not updating

**Cause**: i18n not initialized or component not re-rendering
**Solution**: 
- Ensure `I18nextProvider` wraps app in `providers.tsx`
- Use `const { t } = useTranslation()` (not `i18n.t()`)

### SSR hydration mismatch

**Cause**: Server renders with default language, client with saved language
**Solution**: 
- i18n is client-only (see `providers.tsx` with `i18nReady` state)
- All components using `t()` are `'use client'`

### Accept-Language not sent

**Cause**: i18n instance not imported in `api-client.ts`
**Solution**: 
- Verify `import i18n from '@/i18n'` at top of file
- Check `config.headers['Accept-Language'] = i18n.language`

### Missing translations

**Cause**: Key exists in one locale but not others
**Solution**:
- Add missing keys to all locale files
- i18next will fallback to default language (`ru`) for missing keys

## Best Practices

1. **Use translation keys consistently**
   - Prefix with context: `nav.`, `actions.`, `errors.`
   - Avoid deeply nested keys (max 2-3 levels)

2. **Keep translations short for UI elements**
   - Buttons: 1-2 words ("Save", "Cancel")
   - Nav labels: 1 word ("Agenda", "Patients")

3. **Provide context in key names**
   - `actions.save` (generic save)
   - `agenda.save` (save appointment in agenda context)

4. **Document complex translations**
   ```json
   {
     // {{count}} is replaced with actual number
     "items.count": "{{count}} items"
   }
   ```

5. **Don't translate technical terms**
   - API error codes → keep in English
   - Medical terminology → depends on context
   - Brand names → keep original

## References

- **i18next docs**: https://www.i18next.com/
- **react-i18next docs**: https://react.i18next.com/
- **Translation keys**: See `src/i18n/locales/*/common.json`
- **LanguageSwitcher**: `src/components/language-switcher.tsx`
- **API integration**: `src/lib/api-client.ts`

## Summary

- **5 languages**: ru (default), uk, hy, fr, es
- **Persistence**: localStorage (key: `preferred_language`)
- **Backend integration**: Accept-Language header on all API requests
- **Convention**: Use `t()` for all UI text, no hardcoded strings
- **Scope**: Navigation, actions, status messages (NOT clinical notes)
