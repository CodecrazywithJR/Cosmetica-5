# Patient Clinical Actions - Consent-Based Blocking

## Overview
Implemented consent-based blocking for clinical actions in the patient detail page ([apps/web/src/app/\[locale\]/patients/\[id\]/page.tsx](apps/web/src/app/[locale]/patients/[id]/page.tsx)). This ensures that encounters and other clinical actions cannot be initiated unless the patient has accepted both privacy policy and terms & conditions.

## Business Rule
- **Patients CAN exist without consents** (data entry allowed)
- **Patients CANNOT have encounters/clinical actions without consents** (clinical workflow blocked)

## Implementation Details

### 1. New Clinical Actions Section

Added a new section in the patient detail page with:
- **Section Header**: "Clinical Actions" (i18n: `patients.sections.clinicalActions`)
- **ConsentBadge**: Small size badge showing consent status
- **"New Encounter" Button**: Primary clinical action with consent-based blocking

### 2. Button Blocking Logic

#### Disabled State
Button is disabled when:
```typescript
!patient.privacy_policy_accepted || !patient.terms_accepted
```

#### Visual Indicators
- **Enabled** (both consents = true):
  - Green background (`bg-green-600`)
  - White text
  - Hover effect (`hover:bg-green-700`)
  - Normal cursor
  
- **Disabled** (missing consents):
  - Gray background (`bg-gray-300`)
  - Light gray text (`text-gray-500`)
  - Not-allowed cursor (`cursor-not-allowed`)
  - Reduced opacity (`opacity-50`)

### 3. Accessibility Features

#### Button Attributes
```tsx
<button
  disabled={!patient.privacy_policy_accepted || !patient.terms_accepted}
  title={
    !patient.privacy_policy_accepted || !patient.terms_accepted
      ? t('actions.consentsRequired')
      : ''
  }
  aria-disabled={!patient.privacy_policy_accepted || !patient.terms_accepted}
>
```

- **`disabled`**: Native HTML attribute (blocks clicks)
- **`title`**: Tooltip on hover with explanation
- **`aria-disabled`**: Screen reader support

### 4. Contextual Help

#### Warning Banner (Conditional)
Shows when consents are missing:
```tsx
{(!patient.privacy_policy_accepted || !patient.terms_accepted) && (
  <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
    <p className="text-sm text-yellow-800">
      ⚠️ {t('actions.consentsRequired')}
    </p>
  </div>
)}
```

**Styling**:
- Yellow background (`bg-yellow-50`)
- Yellow border (`border-yellow-200`)
- Warning icon (⚠️)
- Clear message explaining why action is blocked

### 5. ConsentBadge Integration

Reuses existing `ConsentBadge` component:
```tsx
<ConsentBadge
  privacyAccepted={patient.privacy_policy_accepted}
  termsAccepted={patient.terms_accepted}
  size="sm"
/>
```

**Visual Feedback**:
- **Green badge**: Both consents accepted → "Consents OK"
- **Yellow badge**: Missing consents → "Consents Missing"

## i18n Keys Added

### All 6 Locales (en, es, fr, ru, uk, hy)

#### `patients.sections.clinicalActions`
- **en**: "Clinical Actions"
- **es**: "Acciones Clínicas"
- **fr**: "Actions cliniques"
- **ru**: "Клинические действия"
- **uk**: "Клінічні дії"
- **hy**: "Բժշկական գործողություններ"

#### `patients.actions.newEncounter`
- **en**: "New Encounter"
- **es**: "Nueva Consulta"
- **fr**: "Nouvelle consultation"
- **ru**: "Новая консультация"
- **uk**: "Нова консультація"
- **hy**: "Նոր խորհրդակցություն"

#### `patients.actions.consentsRequired`
- **en**: "Patient must accept consents before starting encounters"
- **es**: "El paciente debe aceptar los consentimientos antes de iniciar consultas"
- **fr**: "Le patient doit accepter les consentements avant de commencer les consultations"
- **ru**: "Пациент должен принять согласия перед началом консультаций"
- **uk**: "Пацієнт повинен прийняти згоди перед початком консультацій"
- **hy**: "Հիվանդը պետք է ընդունի համաձայնությունները նախքան խորհրդակցություններ սկսելուց"

## User Experience Flow

### Scenario 1: Consents Missing
```
User opens patient detail page
  → Patient has privacy_policy_accepted = false OR terms_accepted = false
  → ConsentBadge shows "Consents Missing" (yellow)
  → "New Encounter" button is disabled (gray, opacity 50%)
  → Hover shows tooltip: "Patient must accept consents..."
  → Yellow warning banner visible below button
  → Click does nothing (button disabled)
```

### Scenario 2: Consents Present
```
User opens patient detail page
  → Patient has privacy_policy_accepted = true AND terms_accepted = true
  → ConsentBadge shows "Consents OK" (green)
  → "New Encounter" button is enabled (green, full opacity)
  → Hover shows no tooltip (or different tooltip for enabled state)
  → No warning banner visible
  → Click triggers encounter creation (TODO: implement navigation)
```

### Scenario 3: User Edits Consents
```
User opens patient detail
  → Consents missing → button disabled
  → User clicks "Edit"
  → User accepts both consents
  → User clicks "Save"
  → Redirected back to detail page
  → ConsentBadge updates to green
  → "New Encounter" button becomes enabled
  → User can now initiate clinical workflows
```

## Visual Layout

```
┌─────────────────────────────────────────────────────────┐
│  Patient Detail                                         │
│  [Back to List] [Edit]                                  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Clinical Actions     [🟡 Consents Missing]             │
│                                     [+ New Encounter ⚠️] │ ← disabled
│                                                          │
│  ⚠️ Patient must accept consents before starting...     │ ← warning banner
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Basic Information                                      │
│  ...                                                    │
└─────────────────────────────────────────────────────────┘

[...]
```

## Technical Implementation

### Component Structure
```tsx
{/* Clinical Actions Card */}
<div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
  <div className="flex items-center justify-between">
    {/* Left: Title + Badge */}
    <div className="flex items-center gap-4">
      <h2>{t('sections.clinicalActions')}</h2>
      <ConsentBadge {...} size="sm" />
    </div>
    
    {/* Right: CTA Button */}
    <button
      disabled={!consentsOK}
      title={!consentsOK ? t('actions.consentsRequired') : ''}
      aria-disabled={!consentsOK}
      className={consentsOK ? 'enabled-styles' : 'disabled-styles'}
    >
      {t('actions.newEncounter')}
    </button>
  </div>
  
  {/* Conditional Warning */}
  {!consentsOK && (
    <div className="warning-banner">
      ⚠️ {t('actions.consentsRequired')}
    </div>
  )}
</div>
```

### Consent Check Logic
```typescript
const consentsOK = 
  patient.privacy_policy_accepted && 
  patient.terms_accepted;

// Button disabled state
disabled={!consentsOK}

// Button styling
className={consentsOK ? 'bg-green-600...' : 'bg-gray-300 opacity-50...'}

// Conditional warning
{!consentsOK && <WarningBanner />}
```

## Frontend-Only Implementation

**✅ NO Backend Changes**:
- No new endpoints created
- No API modifications
- Uses existing Patient data structure
- `privacy_policy_accepted` and `terms_accepted` already exist in backend

**✅ NO API Client Changes**:
- No modifications to `api-client.ts`
- No modifications to `patients.ts`
- Uses existing `fetchPatientById()` function

**✅ Reuses Existing Components**:
- `ConsentBadge` component (already implemented)
- `AppLayout` wrapper
- Existing i18n infrastructure (next-intl)

## Extensibility

This pattern can be applied to other clinical actions:

### Example: Add Treatment Button
```tsx
<button
  disabled={!patient.privacy_policy_accepted || !patient.terms_accepted}
  title={!patient.privacy_policy_accepted || !patient.terms_accepted 
    ? t('actions.consentsRequired') 
    : ''
  }
  aria-disabled={!patient.privacy_policy_accepted || !patient.terms_accepted}
  className={/* same disabled logic */}
>
  {t('actions.addTreatment')}
</button>
```

### Example: Book Appointment
```tsx
<button
  disabled={!patient.privacy_policy_accepted || !patient.terms_accepted}
  /* same pattern */
>
  {t('actions.bookAppointment')}
</button>
```

### Example: View Medical History
```tsx
<button
  disabled={!patient.privacy_policy_accepted || !patient.terms_accepted}
  /* same pattern */
>
  {t('actions.viewHistory')}
</button>
```

## Files Modified

### Frontend Component
- **[apps/web/src/app/\[locale\]/patients/\[id\]/page.tsx](apps/web/src/app/[locale]/patients/[id]/page.tsx)** (+67 lines)
  - Added "Clinical Actions" section
  - Added "New Encounter" button with consent-based blocking
  - Added ConsentBadge display (size="sm")
  - Added conditional warning banner
  - Integrated tooltip and aria-disabled for accessibility

### i18n Files (6 locales)
- **apps/web/messages/en.json** (+3 keys: `sections.clinicalActions`, `actions.newEncounter`, `actions.consentsRequired`)
- **apps/web/messages/es.json** (+3 keys)
- **apps/web/messages/fr.json** (+3 keys)
- **apps/web/messages/ru.json** (+3 keys)
- **apps/web/messages/uk.json** (+3 keys)
- **apps/web/messages/hy.json** (+3 keys)

**Total**: 1 component + 6 i18n files = 7 files modified

## Acceptance Criteria ✅

- [x] With both consents accepted → CTA active (green button, clickable)
- [x] Missing consents → CTA blocked (gray button, disabled, cursor-not-allowed, opacity-50)
- [x] Tooltip visible on hover when disabled (title attribute with i18n message)
- [x] ConsentBadge visible near CTA (size="sm")
- [x] Warning banner appears when consents missing (yellow, non-intrusive)
- [x] Change locale → texts translated (all 6 locales supported)
- [x] TypeScript compiles without errors
- [x] Accessibility: `aria-disabled` attribute present
- [x] No hardcoded texts (all via i18n)
- [x] No backend modifications
- [x] No API client modifications
- [x] Reuses existing Patient data structure
- [x] Reuses existing ConsentBadge component

## Testing Checklist

### Visual Testing
- [ ] Button appears green when consents OK
- [ ] Button appears gray when consents missing
- [ ] ConsentBadge shows correct color (green/yellow)
- [ ] Warning banner appears only when consents missing
- [ ] Button opacity reduces when disabled

### Functional Testing
- [ ] Click on enabled button triggers action (TODO: add navigation)
- [ ] Click on disabled button does nothing
- [ ] Hover on disabled button shows tooltip
- [ ] Edit patient → accept consents → save → button becomes enabled

### i18n Testing
- [ ] English: "New Encounter" button text
- [ ] Spanish: "Nueva Consulta" button text
- [ ] French: "Nouvelle consultation" button text
- [ ] Russian: "Новая консультация" button text
- [ ] Ukrainian: "Нова консультація" button text
- [ ] Armenian: "Նոր խորհրդակցություն" button text

### Accessibility Testing
- [ ] Screen reader announces button state (disabled/enabled)
- [ ] Screen reader reads tooltip text when focused
- [ ] Keyboard navigation: Tab to button, Enter does nothing when disabled
- [ ] High contrast mode: Button still visually distinct

## Next Steps

1. **Implement encounter creation**:
   - Create `/encounters/new` page
   - Add patient_id as query param or route param
   - Pre-fill patient data in encounter form
   - Update button onClick to navigate instead of alert

2. **Add more clinical actions**:
   - "Add Treatment" button (same blocking logic)
   - "Book Appointment" button (same blocking logic)
   - "View Medical History" (may not need blocking, read-only)

3. **Backend validation** (defensive programming):
   - Even though frontend blocks, backend should also validate
   - POST /api/v1/encounters/ should check consents
   - Return 403 Forbidden if consents missing
   - Error message: "Patient must accept consents before creating encounter"

4. **Audit logging**:
   - Log when user tries to click disabled button (analytics)
   - Track consent acceptance before encounter creation (compliance)

## Related Documentation

- [PATIENT_EDIT_VALIDATION.md](PATIENT_EDIT_VALIDATION.md) - Client-side validation for patient edit form
- [PATIENT_EDIT_UNSAVED_CHANGES_PROTECTION.md](PATIENT_EDIT_UNSAVED_CHANGES_PROTECTION.md) - Unsaved changes protection
- [apps/web/src/components/patients/ConsentBadge.tsx](apps/web/src/components/patients/ConsentBadge.tsx) - Reusable consent status badge
- [apps/web/src/lib/api/patients.ts](apps/web/src/lib/api/patients.ts) - Patient API client

## Business Impact

### Compliance
- ✅ Enforces consent requirements at UI level
- ✅ Prevents accidental GDPR/HIPAA violations
- ✅ Clear visual indicators for missing consents
- ✅ Auditable (users cannot bypass disabled buttons)

### User Experience
- ✅ Proactive: Shows why action is blocked before user tries
- ✅ Educational: Warning banner explains business rule
- ✅ Recoverable: User can edit patient to accept consents
- ✅ Non-intrusive: Doesn't block viewing patient data

### Clinical Workflow
- ✅ Ensures clinical documentation has legal foundation
- ✅ Protects practitioners from incomplete consent scenarios
- ✅ Maintains data quality (no encounters without consents)
- ✅ Scalable: Pattern easily applied to other clinical actions
