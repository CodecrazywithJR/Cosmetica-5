# i18n Manual Verification Checklist

## Prerequisites
1. Backend running at `http://localhost:8000`
2. Frontend dependencies installed: `npm install`
3. Frontend running: `npm run dev`

## Test Steps

### 1. Initial Load
- [ ] Open `http://localhost:3000`
- [ ] Should redirect to `/login` (if not logged in)
- [ ] Login page loads without errors
- [ ] Console has no i18n errors

### 2. Login and Initial Language
- [ ] Login with valid credentials
- [ ] Redirects to `/agenda`
- [ ] Sidebar shows "Cosmetica 5" header
- [ ] Navigation items visible:
  - [ ] "Расписание" (Agenda in Russian)
  - [ ] "Пациенты" (Patients in Russian)
  - [ ] "Предложения" (Proposals in Russian)
- [ ] Sidebar footer shows:
  - [ ] Language selector dropdown
  - [ ] "Выйти" (Logout button in Russian)

### 3. Language Switching
- [ ] Open language dropdown in sidebar footer
- [ ] Options visible:
  - [ ] Русский
  - [ ] Українська
  - [ ] Հայերեն
  - [ ] Français
  - [ ] Español
- [ ] Select "Українська"
- [ ] Navigation items change immediately:
  - [ ] "Розклад" (Agenda in Ukrainian)
  - [ ] "Пацієнти" (Patients in Ukrainian)
  - [ ] "Пропозиції" (Proposals in Ukrainian)
- [ ] Logout button changes to "Вийти"

### 4. Persistence
- [ ] Open browser DevTools → Application → Local Storage
- [ ] Verify `preferred_language` = `uk`
- [ ] Reload page (`Cmd/Ctrl + R`)
- [ ] Language remains Ukrainian after reload
- [ ] Navigation labels still in Ukrainian

### 5. Other Languages
- [ ] Switch to "Հայերեն" (Armenian)
  - [ ] Navigation: "Ժամանակացույց" (Agenda)
  - [ ] Logout: "Ելք"
- [ ] Switch to "Français" (French)
  - [ ] Navigation: "Agenda"
  - [ ] Logout: "Déconnexion"
- [ ] Switch to "Español" (Spanish)
  - [ ] Navigation: "Agenda"
  - [ ] Logout: "Cerrar sesión"

### 6. API Integration
- [ ] Open browser DevTools → Network tab
- [ ] Make any API request (e.g., load appointments)
- [ ] Click on request → Headers
- [ ] Verify `Accept-Language: uk` (or current language)
- [ ] Change language to French
- [ ] Make another API request
- [ ] Verify `Accept-Language: fr`

### 7. Reset Test
- [ ] Open DevTools → Application → Local Storage
- [ ] Delete `preferred_language` key
- [ ] Reload page
- [ ] Should default to Russian ("Расписание", "Выйти")

## Expected Behavior Summary

✅ **Working correctly if:**
- Language selector appears in sidebar footer
- Navigation labels change immediately when selecting new language
- localStorage saves `preferred_language`
- Page reload respects saved language
- All API requests include `Accept-Language` header
- Default language is Russian when no preference saved

❌ **Issues to check:**
- Console errors about i18n initialization
- Navigation labels don't change when switching language
- Page reloads reset language to default
- API requests missing `Accept-Language` header

## Troubleshooting

### Language not changing
1. Check console for errors
2. Verify `I18nextProvider` in `providers.tsx`
3. Ensure components use `const { t } = useTranslation()`

### Language resets on reload
1. Check localStorage has `preferred_language` key
2. Verify `i18n/index.ts` reads from localStorage
3. Check for browser privacy settings blocking localStorage

### Accept-Language not sent
1. Verify `api-client.ts` imports i18n
2. Check request interceptor includes header
3. Ensure i18n is initialized before API calls

## Notes

- **Scope**: Navigation, common UI elements, and Agenda module are fully translated
- **Not translated**: Clinical notes, patient names, practitioner names, user data
- **Fallback**: If translation missing, shows Russian text
- **Backend**: Should handle Accept-Language header (not required for MVP)

---

## 8. Agenda Module Translation Verification

### Page Title
- [ ] Open Agenda page (`/agenda`)
- [ ] Verify title in Russian: "Расписание"
- [ ] Switch to Ukrainian → Title: "Розклад"
- [ ] Switch to Armenian → Title: "Օրագիր"
- [ ] Switch to French → Title: "Agenda"
- [ ] Switch to Spanish → Title: "Agenda"
- [ ] Title changes instantly without page reload

### Filters Section
- [ ] Date input visible with calendar picker
- [ ] Status dropdown shows "All Status" in current language:
  - **Russian**: "Все статусы"
  - **Ukrainian**: "Всі статуси"
  - **Armenian**: "Բոլոր կարգավիճակները"
  - **French**: "Tous les statuts"
  - **Spanish**: "Todos los estados"
- [ ] Open status dropdown → all options translated
- [ ] Change language → filter labels update immediately

### Table Headers
Switch between languages and verify column headers:
- [ ] **Time**: Время / Час / Ժամանակ / Heure / Hora
- [ ] **Patient**: Пациент / Пацієнт / Հիվանդ / Patient / Paciente
- [ ] **Practitioner**: Специалист / Спеціаліст / Մասնագետ / Praticien / Profesional
- [ ] **Type**: Тип / Тип / Տեսակ / Type / Tipo
- [ ] **Status**: Статус / Статус / Կարգավիճակ / Statut / Estado
- [ ] **Actions**: Действия / Дії / Գործողություններ / Actions / Acciones

### Appointment Status Badges
With visible appointments:
- [ ] Status badges show translated labels (NOT raw values like "scheduled")
- [ ] Test each status translation:
  - **scheduled**: Запланировано / Заплановано / Նախատեսված / Planifié / Programado
  - **confirmed**: Подтверждено / Підтверджено / Հաստատված / Confirmé / Confirmado
  - **checked_in**: Прибыл / Прибув / Ներկայացել է / Arrivé / Llegó
  - **completed**: Завершено / Завершено / Ավարտված / Terminé / Completado
  - **cancelled**: Отменено / Скасовано / Չեղարկված / Annulé / Cancelado
  - **no_show**: Не явился / Не з'явився / Չներկայացավ / Absent / No se presentó

### Appointment Types
- [ ] Appointment types show translated labels:
  - **medical_consult**: Мед. консультация / Мед. консультація / Բժշկական խորհրդատվություն / Consultation médicale / Consulta médica
  - **cosmetic_consult**: Косметол. консультация / Косметол. консультація / Կոսմետիկ խորհրդատվություն / Consultation cosmétique / Consulta cosmética
  - **follow_up**: Повторный приём / Повторний прийом / Հետագա այց / Suivi / Seguimiento
  - **aesthetic_procedure**: Эстетическая процедура / Естетична процедура / Գեղագիտական ​​ընթացակարգ / Procédure esthétique / Procedimiento estético

### Action Buttons
Test with different appointment statuses:

**Scheduled appointments**:
- [ ] "Confirm" button: Подтвердить / Підтвердити / Հաստատել / Confirmer / Confirmar
- [ ] "Cancel" button: Отменить / Скасувати / Չեղարկել / Annuler / Cancelar

**Confirmed appointments**:
- [ ] "Check In" button: Принять / Прийняти / Ընդունել / Enregistrer / Registrar
- [ ] "Cancel" button: Отменить / Скасувати / Չեղարկել / Annuler / Cancelar

**Checked-in appointments**:
- [ ] "Complete" button: Завершить / Завершити / Ավարտել / Terminer / Completar

### Empty State
- [ ] Select date with no appointments
- [ ] Message appears: "No appointments found for [date]"
- [ ] Message translated in all 5 languages
- [ ] Date formatted according to locale (e.g., "15 января 2024 г." in Russian)

### Summary Section
With appointments visible:
- [ ] Summary shows: "Total appointments: X"
- [ ] Label translated:
  - **Russian**: "Всего записей:"
  - **Ukrainian**: "Всього записів:"
  - **Armenian**: "Ընդհանուր հանդիպումներ:"
  - **French**: "Total rendez-vous:"
  - **Spanish**: "Total de citas:"
- [ ] Number displayed correctly after label

### Date/Time Formatting
- [ ] Appointment times use 24-hour format (14:30, not 2:30 PM)
- [ ] Times formatted correctly for locale
- [ ] Date in filter formatted according to locale
- [ ] Date in empty state formatted according to locale

### Untranslated Content (By Design)
Verify these remain unchanged across all languages:
- [ ] Patient names (e.g., "John Doe") NOT translated
- [ ] Patient emails (e.g., "john@example.com") NOT translated
- [ ] Practitioner display names (e.g., "Dr. Smith") NOT translated

### Error Handling
To test error messages:
1. Stop backend server temporarily
2. Reload Agenda page
3. Verify error message:
   - [ ] "Error loading appointments:" translated in all languages
   - [ ] Error details appear after translated label

### Loading State
- [ ] While loading: "Loading appointments..." shown in current language
- [ ] Message translated:
  - **Russian**: "Загрузка записей..."
  - **Ukrainian**: "Завантаження записів..."
  - **Armenian**: "Բեռնում հանդիպումներ..."
  - **French**: "Chargement des rendez-vous..."
  - **Spanish**: "Cargando citas..."

### Language Switch Responsiveness
- [ ] Switch from Russian to Ukrainian while viewing Agenda
- [ ] All labels update instantly (title, headers, buttons, statuses)
- [ ] No page reload
- [ ] Appointment data remains visible (no refetch)
- [ ] Date/time formatting updates to new locale

### React Query Integration
- [ ] Load appointments → data displays correctly
- [ ] Change language → appointments stay visible (no refetch)
- [ ] Click "Confirm" on scheduled appointment → status updates
- [ ] Updated status badge shows new translated label
- [ ] Mutation success/error messages work (if any)

## Agenda Module Sign-off

✅ **Agenda module fully translated if:**
- Zero hardcoded strings in Agenda page
- All statuses and types show translated labels
- Date/time formatted according to locale
- Language switching updates all Agenda text instantly
- Patient/practitioner names NOT translated (as designed)
- All CRUD operations still work correctly

❌ **Issues to check:**
- Status badges show raw backend values (e.g., "scheduled" instead of "Запланировано")
- Appointment types not translated
- Date/time not respecting locale
- Action buttons still in English
- Language change requires page reload

**Tested by**: _________________  
**Date**: _________________  
**Agenda version**: _________________

---

## 9. Proposals/POS Module Translation Verification

### Page Title and Navigation
- [ ] Open Proposals page (`/proposals`)
- [ ] Verify title in Russian: "Предложения"
- [ ] Switch to Ukrainian → Title: "Пропозиції"
- [ ] Switch to Armenian → Title: "Առաջարկություններ"
- [ ] Switch to French → Title: "Propositions"
- [ ] Switch to Spanish → Title: "Propuestas"
- [ ] Title changes instantly without page reload

### Filters Section
- [ ] Status dropdown shows "All Status" in current language:
  - **Russian**: "Все статусы"
  - **Ukrainian**: "Всі статуси"
  - **Armenian**: "Բոլոր կարգավիճակները"
  - **French**: "Tous les statuts"
  - **Spanish**: "Todos los estados"
- [ ] Open status dropdown → all options translated
- [ ] Change language → filter labels update immediately

### Table Headers
Switch between languages and verify column headers:
- [ ] **Date**: Дата / Дата / Ամսաթիվ / Date / Fecha
- [ ] **Patient**: Пациент / Пацієнт / Հիվանդ / Patient / Paciente
- [ ] **Practitioner**: Специалист / Спеціаліст / Մասնագետ / Praticien / Profesional
- [ ] **Items**: Элементы / Елементи / Տարրեր / Articles / Artículos
- [ ] **Total**: Итого / Разом / Ընդամենը / Total / Total
- [ ] **Status**: Статус / Статус / Կարգավիճակ / Statut / Estado
- [ ] **Actions**: Действия / Дії / Գործողություններ / Actions / Acciones

### Proposal Status Badges
With visible proposals:
- [ ] Status badges show translated labels (NOT raw values like "draft")
- [ ] Test each status translation:
  - **draft**: Черновик / Чернетка / Սևագիր / Brouillon / Borrador
  - **converted**: Преобразовано / Перетворено / Փոխարկված / Converti / Convertido
  - **cancelled**: Отменено / Скасовано / Չեղարկված / Annulé / Cancelado

### Items Count Display
- [ ] Proposals show item count as translated text:
  - **Russian**: "3 элемента" (singular/plural rules)
  - **Ukrainian**: "3 елементи"
  - **Armenian**: "3 տարրեր"
  - **French**: "3 articles"
  - **Spanish**: "3 artículos"

### Currency Formatting
With proposals displaying totals:
- [ ] Amounts formatted as currency with EUR symbol
- [ ] Format respects locale:
  - **Russian**: "1 234,56 €" (space separator, comma decimal)
  - **French**: "1 234,56 €"
  - **Spanish**: "1234,56 €" or "1.234,56 €" depending on locale
- [ ] Currency symbol position correct for locale
- [ ] Decimal and thousands separators correct

### Action Buttons
Test with different proposal statuses:

**Draft proposals**:
- [ ] "Create Sale" button: Создать продажу / Створити продаж / Ստեղծել վաճառք / Créer une vente / Crear venta
- [ ] "Cancel" button: Отменить / Скасувати / Չեղարկել / Annuler / Cancelar

**Converted proposals**:
- [ ] "View Sale" link: Просмотр продажи / Переглянути продаж / Դիտել վաճառքը / Voir la vente / Ver venta

### Convert to Sale Modal
- [ ] Click "Create Sale" on draft proposal
- [ ] Modal opens with translated content:
  - **Title**: "Convert Proposal to Sale" → translated in all 5 languages
  - **Description**: Warning text translated
  - **Form label**: "Legal Entity ID *" → translated
  - **Placeholder**: "Enter legal entity UUID" → translated
  - **Help text**: "This is the UUID..." → translated
  - **Cancel button**: Отменить / Скасувати / Չեղարկել / Annuler / Cancelar
  - **Confirm button**: Создать продажу / Створити продаж / Ստեղծել վաճառք / Créer une vente / Crear venta

### Convert to Sale - Loading State
- [ ] Click confirm button
- [ ] Button shows loading state:
  - **Russian**: "Преобразование..."
  - **Ukrainian**: "Перетворення..."
  - **Armenian**: "Փոխարկում..."
  - **French**: "Conversion..."
  - **Spanish**: "Convirtiendo..."

### Cancel Proposal Modal
- [ ] Click "Cancel" button on draft proposal
- [ ] Modal opens with translated content:
  - **Title**: "Cancel Proposal" → translated in all 5 languages
  - **Description**: Warning about irreversibility → translated
  - **Description color**: Red/error color (visual warning)
  - **Form label**: "Cancellation Reason *" → translated
  - **Placeholder**: "Explain why..." → translated
  - **Back button**: Назад / Назад / Հետ / Retour / Atrás
  - **Confirm button**: Отменить предложение / Скасувати пропозицію / Չեղարկել առաջարկությունը / Annuler la proposition / Cancelar propuesta

### Cancel Proposal - Loading State
- [ ] Click confirm button
- [ ] Button shows loading state:
  - **Russian**: "Отмена..."
  - **Ukrainian**: "Скасування..."
  - **Armenian**: "Չեղարկում..."
  - **French**: "Annulation..."
  - **Spanish**: "Cancelando..."

### Empty State
- [ ] Select filter with no results (e.g., "Cancelled" with no cancelled proposals)
- [ ] Message appears: "No proposals found"
- [ ] Message translated:
  - **Russian**: "Предложения не найдены"
  - **Ukrainian**: "Пропозиції не знайдені"
  - **Armenian**: "Առաջարկություններ չեն գտնվել"
  - **French**: "Aucune proposition trouvée"
  - **Spanish**: "No se encontraron propuestas"

### Summary Section
With proposals visible:
- [ ] Summary shows: "Total proposals: X"
- [ ] Label translated:
  - **Russian**: "Всего предложений:"
  - **Ukrainian**: "Всього пропозицій:"
  - **Armenian**: "Ընդամենը առաջարկություններ:"
  - **French**: "Total des propositions:"
  - **Spanish**: "Total de propuestas:"
- [ ] Number displayed correctly after label

### Date Formatting
- [ ] Proposal creation dates formatted according to locale
- [ ] Date format examples:
  - **Russian**: "янв. 15, 2024" (short month)
  - **French**: "15 janv. 2024"
  - **Spanish**: "15 ene 2024"
- [ ] Dates update when language changes

### Untranslated Content (By Design)
Verify these remain unchanged across all languages:
- [ ] Patient names (e.g., "John Doe") NOT translated
- [ ] Patient emails (e.g., "john@example.com") NOT translated
- [ ] Practitioner display names (e.g., "Dr. Smith") NOT translated
- [ ] Legal Entity UUID in modal (user input) NOT translated

### Error Handling
To test error messages:
1. Stop backend server temporarily
2. Reload Proposals page
3. Verify error message:
   - [ ] "Error loading proposals:" translated in all languages
   - [ ] Error details appear after translated label

### Loading State
- [ ] While loading: "Loading..." shown in current language
- [ ] Uses common namespace: `t('common:status.loading')`

### Language Switch Responsiveness
- [ ] Switch from Russian to Ukrainian while viewing Proposals
- [ ] All labels update instantly (title, headers, buttons, statuses, modals)
- [ ] No page reload
- [ ] Proposal data remains visible (no refetch)
- [ ] Currency formatting updates to new locale
- [ ] Date formatting updates to new locale

### React Query Integration
- [ ] Load proposals → data displays correctly
- [ ] Change language → proposals stay visible (no refetch)
- [ ] Convert proposal to sale → success (if legal entity valid)
- [ ] Cancel proposal → success with reason
- [ ] Mutation success messages work
- [ ] Status badges update with translated labels after mutations

### Critical Business Flows
Test that economic flows remain intact:

**Convert Proposal to Sale:**
1. [ ] Create draft proposal (via Encounter → Generate Proposal)
2. [ ] Open Proposals page
3. [ ] Click "Create Sale" on draft proposal
4. [ ] Modal appears with translated content
5. [ ] Enter valid legal entity UUID
6. [ ] Click "Create Sale" button
7. [ ] Proposal status changes to "Converted"
8. [ ] "View Sale" link appears (translated)
9. [ ] Click "View Sale" → redirects to sale detail (if implemented)

**Cancel Proposal:**
1. [ ] Find draft proposal
2. [ ] Click "Cancel" button
3. [ ] Modal appears with warning (translated, red text)
4. [ ] Enter cancellation reason
5. [ ] Click "Cancel Proposal" button
6. [ ] Proposal status changes to "Cancelled"
7. [ ] Action buttons disappear (cannot convert cancelled proposal)

### Confirmation Safety
- [ ] Convert modal requires legal entity ID (cannot submit empty)
- [ ] Cancel modal requires cancellation reason (cannot submit empty)
- [ ] Both modals have explicit confirmation buttons (not just "OK")
- [ ] Modal descriptions explain consequences clearly
- [ ] Cancel modal uses warning color (red) for irreversible action

### Status Fallback Test (Advanced)
If backend adds new status (e.g., `pending_review`):
1. [ ] Manually modify proposal status in database to new value
2. [ ] Reload Proposals page
3. [ ] Verify badge shows fallback:
   - Badge displays raw value: "pending_review"
   - UI does NOT break (no "undefined" or blank)
   - Badge still styled with CSS class
4. [ ] Add translation to pos.json files
5. [ ] Reload → badge now shows translated label

## Proposals/POS Module Sign-off

✅ **POS module fully translated if:**
- Zero hardcoded strings in Proposals page
- All proposal statuses show translated labels
- Currency formatted according to locale (EUR symbol, separators)
- Date formatted according to locale
- Both modals (convert, cancel) fully translated
- Confirmation messages explicit and translated
- Language switching updates all POS text instantly
- Patient/practitioner names NOT translated (as designed)
- All economic flows work correctly (convert, cancel)
- Status fallback prevents UI breaking with new backend statuses

❌ **Issues to check:**
- Status badges show raw backend values (e.g., "draft" instead of "Черновик")
- Currency shows raw numbers (e.g., "EUR 1234.56" instead of "1 234,56 €")
- Modal titles or descriptions still in English
- Date not respecting locale format
- Action buttons still in English
- Language change requires page reload
- Confirmation modals can be submitted empty

**Tested by**: _________________  
**Date**: _________________  
**POS version**: _________________


## 10. Encounter/Clinical Module Translation Verification

### Page Title and Status
- [ ] Open Encounter detail page (`/encounters/[id]`)
- [ ] Verify title in Russian: "Детали консультации"
- [ ] Switch to Ukrainian → Title: "Деталі консультації"
- [ ] Switch to Armenian → Title: "Խորհրդատվության մանրամասներ"
- [ ] Switch to French → Title: "Détails de la consultation"
- [ ] Switch to Spanish → Title: "Detalles de la consulta"
- [ ] Status badge shows translated value (not "draft")

### Encounter Status Badges
- [ ] Status badges show translated labels:
  - **draft**: Черновик / Чернетка / Սևագիր / Brouillon / Borrador
  - **finalized**: Завершено / Завершено / Ավարտված / Finalisé / Finalizado
  - **cancelled**: Отменено / Скасовано / Չեղարկված / Annulé / Cancelado

### Section Headers
- [ ] "Patient Information" translated in all 5 languages
- [ ] "Encounter Information" translated in all 5 languages
- [ ] "Treatments" translated in all 5 languages

### Patient Information Card
- [ ] All labels translated: Name, Email, Phone, Date of Birth
- [ ] Patient name NOT translated (displays actual name)
- [ ] Patient email NOT translated
- [ ] Patient phone NOT translated

### Encounter Information Card
- [ ] All labels translated: Practitioner, Type, Date, Status
- [ ] Practitioner name NOT translated (displays actual name)
- [ ] Date formatted according to locale (e.g., "янв. 15, 2024 14:30" for Russian)
- [ ] Encounter type translated dynamically
- [ ] Chief Complaint label translated, but content NOT translated
- [ ] Assessment label translated, but content NOT translated
- [ ] Plan label translated, but content NOT translated

### Treatments Section
- [ ] "Add Treatment" button translated
- [ ] Table headers translated: Treatment, Quantity, Unit Price, Total, Notes
- [ ] Treatment names NOT translated (from backend catalog)
- [ ] Treatment prices formatted as currency with locale (e.g., "$1,234.56" vs "1 234,56 $")
- [ ] Treatment notes NOT translated (clinical notes)
- [ ] Empty state: "No treatments added yet" translated

### Add Treatment Modal
- [ ] Click "Add Treatment" button
- [ ] Modal title: "Add Treatment" translated
- [ ] All form labels translated:
  - Treatment ID label and placeholder
  - Quantity label
  - Unit Price label and placeholder
  - Notes label and placeholder
- [ ] Cancel button translated
- [ ] Add button translated
- [ ] Loading state: "Adding..." translated

### Finalize Encounter Modal (CRITICAL)
- [ ] Uses proper modal (NOT browser confirm dialog)
- [ ] Modal title translated: "Finalize Encounter"
- [ ] Warning question translated (e.g., "Вы уверены, что хотите завершить эту консультацию?")
- [ ] Description about immutability translated
- [ ] Irreversibility warning shown in RED color
- [ ] Cancel button translated
- [ ] Confirm button translated
- [ ] All 4 warning elements visible and translated

### Finalize Flow Safety
- [ ] Cannot finalize without treatments (button disabled with tooltip)
- [ ] Modal explains consequences clearly
- [ ] Irreversibility warning visually distinct (red color)
- [ ] After finalize, encounter status changes to "Finalized"
- [ ] After finalize, "Add Treatment" button disappears
- [ ] After finalize, "Generate Proposal" button appears
- [ ] Button states translate correctly in all languages

### Generate Proposal Flow
- [ ] "Generate Proposal" button translated
- [ ] Loading state: "Generating..." translated
- [ ] Success message translated: "Proposal generated successfully. ID: [id]"
- [ ] Redirects to /proposals after generation
- [ ] New proposal visible in proposals list

### Date/Time Formatting
- [ ] Encounter date formatted according to locale
- [ ] Format examples:
  - Russian: "янв. 15, 2024 14:30"
  - Ukrainian: "15 січ. 2024, 14:30"
  - Armenian: "15 հուն 2024 թ., 14:30"
  - French: "15 janv. 2024 14:30"
  - Spanish: "15 ene 2024 14:30"

### Currency Formatting
- [ ] Treatment prices formatted as USD currency
- [ ] Decimal separator respects locale
- [ ] Currency symbol position correct
- [ ] Total prices formatted correctly

### Untranslated Content Verification (By Design)
- [ ] Patient full name displays actual name (e.g., "John Doe")
- [ ] Practitioner display name shows actual name (e.g., "Dr. Smith")
- [ ] Chief complaint text NOT translated (user-entered)
- [ ] Assessment text NOT translated (user-entered)
- [ ] Plan text NOT translated (user-entered)
- [ ] Treatment catalog names NOT translated
- [ ] Treatment-specific notes NOT translated

### Language Switch Responsiveness
- [ ] Switch from Russian to Ukrainian while viewing encounter
- [ ] All UI labels update instantly (no page reload)
- [ ] Clinical notes remain unchanged (not translated)
- [ ] Patient/practitioner names remain unchanged
- [ ] Date/currency formatting updates
- [ ] Status badges update
- [ ] Modal content updates

### Critical Clinical Flows
**Draft to Finalized:**
1. [ ] Open draft encounter
2. [ ] Add at least one treatment
3. [ ] Click "Finalize Encounter" button
4. [ ] Modal appears with translated warnings
5. [ ] Confirm finalize
6. [ ] Status changes to "Finalized"
7. [ ] "Add Treatment" button disappears
8. [ ] "Generate Proposal" button appears

**Generate Proposal:**
1. [ ] From finalized encounter
2. [ ] Click "Generate Proposal"
3. [ ] Success message appears (translated)
4. [ ] Redirects to /proposals
5. [ ] New proposal visible in proposals list

### Multi-Language Finalize Modal Verification
- [ ] **Russian**: "Вы уверены, что хотите завершить эту консультацию?" + "Это действие необратимо."
- [ ] **Ukrainian**: "Ви впевнені, що хочете завершити цю консультацію?" + "Ця дія незворотна."
- [ ] **Armenian**: "Համոզվա՞ծ եք, որ ցանկանում եք ավարտել այս խորհրդատվությունը:" + "Այս գործողությունը անդառնալի է։"
- [ ] **French**: "Êtes-vous sûr de vouloir finaliser cette consultation ?" + "Cette action est irréversible."
- [ ] **Spanish**: "¿Está seguro de que desea finalizar esta consulta?" + "Esta acción es irreversible."

## Encounter/Clinical Module Sign-off

✅ **Clinical module fully translated if:**
- Zero hardcoded strings in Encounter page
- All statuses show translated labels
- Finalize uses proper modal (NOT browser confirm)
- Date/currency formatted according to locale
- Clinical notes NOT translated (as designed)
- Patient/practitioner names NOT translated (as designed)
- Language switching updates all UI text instantly
- All clinical flows work correctly
- Finalize confirmation explicit with visual warnings

❌ **Issues to check:**
- Status badges show raw values (e.g., "draft" instead of "Черновик")
- Browser `confirm()` used instead of modal
- Clinical notes accidentally translated
- Patient/practitioner names translated
- Finalize warning not clear or not translated
- Date/currency not respecting locale
- Modal not showing all 4 warning elements

**Tested by**: _________________  
**Date**: _________________  
**Clinical version**: _________________

