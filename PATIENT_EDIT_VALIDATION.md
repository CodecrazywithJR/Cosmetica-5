# Patient Edit Form - Client-Side Validation Implementation

## Overview
Client-side validation has been implemented for the patient edit form ([apps/web/src/app/\[locale\]/patients/\[id\]/edit/page.tsx](apps/web/src/app/[locale]/patients/[id]/edit/page.tsx)) without using external validation libraries (no zod, yup, or react-hook-form).

## Implementation Details

### 1. Validation State
Added four state variables to track validation:
- `fieldErrors: Record<string, string>` - Stores error messages per field
- `touched: Record<string, boolean>` - Tracks which fields user has interacted with
- `submitAttempted: boolean` - Tracks if user tried to submit (shows all errors)
- `validationBanner: boolean` - Controls display of form-level error banner

### 2. Validation Rules

#### A. Required Fields
- `first_name` (2-100 chars)
- `last_name` (2-100 chars)

#### B. Format Validations
- `email` - Valid email format (regex: `/^[^\s@]+@[^\s@]+\.[^\s@]+$/`)
- `phone` - Minimum 6 characters (if provided)
- `birth_date` - Cannot be in the future

#### C. Pair Validations
- **Document pair**: If `document_type` exists, `document_number` is required (and vice versa)
- **Emergency pair**: If `emergency_contact_name` exists, `emergency_contact_phone` is required (and vice versa)

#### D. Consent Warnings (Non-blocking)
- Warns when `privacy_policy_accepted` or `terms_accepted` is false
- Does NOT prevent form submission (business rule: patients can exist without consents)
- Yellow banner displays warning message

### 3. Validation Function
```typescript
const validate = (data: any): { 
  fieldErrors: Record<string, string>; 
  isValid: boolean 
} => {
  // Returns fieldErrors object and isValid boolean
  // Called on:
  // - Field blur
  // - Field change (if touched or submit attempted)
  // - Form submit
}
```

### 4. User Interaction Handlers

#### handleBlur
```typescript
const handleBlur = (field: string) => {
  setTouched(prev => ({ ...prev, [field]: true }));
  const validation = validate(formData);
  setFieldErrors(validation.fieldErrors);
};
```
- Marks field as touched
- Triggers validation
- Attached to all validated inputs via `onBlur` prop

#### handleInputChange (Enhanced)
```typescript
const handleInputChange = (field: string, value: any) => {
  setFormData(prev => ({ ...prev, [field]: value }));
  // Revalidate if field was touched or submit attempted
  if (touched[field] || submitAttempted) {
    setTimeout(() => {
      const validation = validate({ ...formData, [field]: value });
      setFieldErrors(validation.fieldErrors);
    }, 0);
  }
};
```
- Updates form data
- Re-validates if field is touched or submit was attempted

#### handleSubmit (Enhanced)
```typescript
const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  setSubmitAttempted(true);
  
  const validation = validate(formData);
  setFieldErrors(validation.fieldErrors);
  
  if (!validation.isValid) {
    setValidationBanner(true);
    // Focus first error field
    const firstErrorField = Object.keys(validation.fieldErrors)[0];
    if (firstErrorField) {
      document.querySelector(`[name="${firstErrorField}"]`)?.focus();
    }
    return; // Block submission
  }
  
  // Check consents for warning (non-blocking)
  if (!formData.privacy_policy_accepted || !formData.terms_accepted) {
    setValidationBanner(true);
  }
  
  // Proceed with API call...
};
```
- Validates before submitting
- Blocks submission if errors exist
- Focuses first error field
- Shows non-blocking consent warning

### 5. Form Input Updates
All validated inputs now include:
- `name` attribute for focus management
- `onBlur={() => handleBlur('field_name')}` handler
- Conditional border styling: `border-red-300` if error exists
- Error message display below input (shown only if `touched[field] || submitAttempted`)

Example:
```tsx
<input
  type="text"
  name="first_name"
  value={formData.first_name}
  onChange={(e) => handleInputChange('first_name', e.target.value)}
  onBlur={() => handleBlur('first_name')}
  className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
    (touched.first_name || submitAttempted) && fieldErrors.first_name 
      ? 'border-red-300' 
      : 'border-gray-300'
  }`}
  placeholder={t('fields.first_name.help')}
  required
/>
{(touched.first_name || submitAttempted) && fieldErrors.first_name && (
  <p className="mt-1 text-xs text-red-600">{fieldErrors.first_name}</p>
)}
```

### 6. Updated Fields
The following fields now have validation feedback:
- ✅ first_name
- ✅ last_name
- ✅ email
- ✅ phone
- ✅ birth_date
- ✅ document_type
- ✅ document_number
- ✅ emergency_contact_name
- ✅ emergency_contact_phone

### 7. Save Button State
The save button is now disabled when:
- Form has validation errors (`Object.keys(fieldErrors).length > 0`)
- Save operation is in progress (`saving === true`)

```tsx
<button
  type="submit"
  disabled={saving || Object.keys(fieldErrors).length > 0}
  className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
>
```

### 8. Error Banners

#### Validation Error Banner (Red)
Appears when user tries to submit with errors:
```tsx
{submitAttempted && Object.keys(fieldErrors).length > 0 && (
  <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-md mb-4">
    <p className="text-sm font-medium">{t('errors.formInvalid')}</p>
  </div>
)}
```

#### Consent Warning Banner (Yellow, Non-blocking)
Appears when consents are not accepted:
```tsx
{validationBanner && (!formData.privacy_policy_accepted || !formData.terms_accepted) && (
  <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded-md mb-4">
    <p className="text-sm font-medium">{t('warnings.consentsMissing')}</p>
  </div>
)}
```

## i18n Keys Added

### Error Messages
All 6 locales (en, es, fr, ru, uk, hy) have these keys under `patients.errors.*`:
- `formInvalid` - "Please fix the errors before saving"
- `required` - "This field is required"
- `minLength` - "Must be at least {min} characters"
- `maxLength` - "Must not exceed {max} characters"
- `invalidEmail` - "Invalid email format"
- `invalidDate` - "Invalid date"
- `futureDate` - "Date cannot be in the future"
- `pairRequired` - "Both fields in this pair are required"
- `documentPairRequired` - "Document type and number must be provided together"

### Warning Messages
Under `patients.warnings.*`:
- `consentsMissing` - "Warning: Consents are not accepted. Patient can be saved but cannot have encounters without accepting them."

## UX Behavior

### Initial Load
- No errors shown
- All fields pristine (untouched)
- Save button enabled

### Field Interaction
1. User types in field → no error shown
2. User leaves field (blur) → field marked as touched → validation runs → error shown if invalid
3. User fixes field → error disappears immediately

### Submit Attempt with Errors
1. User clicks "Save" with invalid data
2. `submitAttempted` set to true
3. All errors become visible (regardless of touched state)
4. Red banner appears with "Please fix the errors"
5. First error field receives focus
6. Save button disabled
7. API call blocked

### Submit with Missing Consents (Non-blocking)
1. User clicks "Save" with valid data but consents = false
2. Yellow warning banner appears
3. Form submits successfully to API
4. User redirected to detail page

## Technical Notes

- **No external libraries**: All validation logic is custom
- **Performance**: Validation function runs on every blur and on change (if touched)
- **Accessibility**: Focus management on validation failure
- **i18n**: All error messages support internationalization
- **Type safety**: TypeScript ensures field names match Patient interface

## Testing Checklist

- [ ] Required field validation (first_name, last_name)
- [ ] Email format validation
- [ ] Phone min length validation
- [ ] Birth date future check
- [ ] Document pair validation (type + number)
- [ ] Emergency pair validation (name + phone)
- [ ] Error visibility on blur
- [ ] Error visibility on submit attempt
- [ ] Save button disabled state
- [ ] First error field focus
- [ ] Consent warning (non-blocking)
- [ ] Successful save with missing consents
- [ ] i18n messages in all 6 locales

## Related Files

- **Form**: [apps/web/src/app/\[locale\]/patients/\[id\]/edit/page.tsx](apps/web/src/app/[locale]/patients/[id]/edit/page.tsx)
- **i18n**: apps/web/messages/{en,es,fr,ru,uk,hy}.json
- **Types**: [apps/web/src/lib/api/patients.ts](apps/web/src/lib/api/patients.ts)

## Business Rules Enforced

1. ✅ Basic identity required (first_name, last_name)
2. ✅ Email must be valid format (if provided)
3. ✅ Phone minimum length (if provided)
4. ✅ Birth date cannot be future
5. ✅ Document type and number must be paired
6. ✅ Emergency contact name and phone must be paired
7. ✅ **Consents are optional for patient creation** (business rule: "Patients can exist without consents but cannot have encounters without accepting them")

## Next Steps

1. Test validation in browser with real data
2. Verify i18n keys display correctly in all 6 locales
3. Test accessibility (keyboard navigation, screen readers)
4. Verify focus management on validation failure
5. Test consent warning (non-blocking) behavior
6. Integration test with backend (row_version + validation)
