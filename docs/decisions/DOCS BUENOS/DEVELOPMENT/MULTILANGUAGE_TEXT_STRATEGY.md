# MULTILANGUAGE_TEXT_STRATEGY

## Status
APPROVED DECISION

## Purpose
Define the official product and architectural strategy for multilingual text handling in Cosmetica 5.

This document separates:
- multilingual master texts
- multilingual free texts

The goal is to preserve:
- legal and clinical integrity
- SaaS scalability
- product flexibility
- clean domain modeling
- a realistic implementation path

This decision complements the existing project contract and i18n rules:
- UI is multilingual by design
- visible UI strings must use next-intl
- backend remains source of truth for domain states
- we avoid overcomplicating the data model with unnecessary multilingual persistence

---

# 1. Problem Statement

The system already supports multilingual UI through next-intl.

However, the application contains several different categories of text:

1. UI labels and interface strings
2. master business texts
3. free user-authored texts

These three categories must not be treated the same way.

If they are mixed:
- the model becomes inconsistent
- multilingual behavior becomes unclear
- clinical/legal integrity is weakened
- SaaS onboarding becomes heavier than necessary

This document defines the official separation.

---

# 2. Official Separation of Text Types

## 2.1 UI Text

Examples:
- buttons
- labels
- menus
- warnings
- badges
- status labels
- empty states

### Rule
UI text is always handled through `next-intl`.

### Mandatory rules
- no hardcoded visible strings in JSX
- all visible labels must use translation keys
- all new keys must be added following project rules
- domain statuses are translated from canonical backend states

### Notes
UI text is not business data and is not stored as multilingual content in business tables.

---

## 2.2 Master Texts

### Definition
Stable business-owned content that can exist in one or multiple languages.

### Examples
- Treatment name
- Treatment commercial description
- reusable document templates
- reusable proposal text blocks
- reusable instructions
- standardized service descriptions

### Rule
Master texts support structured translations by language.

### Important
It is not mandatory to fill all supported languages.

The SaaS product must allow:
- one-language setups
- two-language setups
- partial multilingual setups
- progressive completion over time

### Business principle
At least one base language must exist for each master record.

Additional translations are optional.

---

## 2.3 Free Texts

### Definition
Text entered manually by users during real operations.

### Examples
- clinical notes
- encounter observations
- internal comments
- patient free notes
- proposal comments written ad hoc
- operational annotations

### Rule
Free texts are not stored translated in the database.

### Official behavior
- store only the original text
- original text remains the single source of truth
- translation is available only on demand in the UX
- translated output is only a reading aid
- translated output is not part of the official medical/legal record

### Why
Because free text:
- is contextual
- may contain nuance
- may have legal/clinical implications
- should not create duplicated persisted content
- should not require synchronization between original and translated versions

---

# 3. Decision Summary

## 3.1 Master Texts
Approved behavior:
- structured multilingual storage
- one mandatory base language
- optional additional translations
- fallback resolution at read time

## 3.2 Free Texts
Approved behavior:
- original only in DB
- no persisted automatic translations
- translation only under explicit user action in UX

---

# 4. Master Text Modeling Strategy

## 4.1 Recommended Pattern

Use:
- a main business table
- a dedicated translation child table

### Example

```text
Treatment
- id
- legal_entity_id
- base_language
- name
- description
- ...domain fields
TreatmentTranslation
- id
- treatment_id
- language_code
- name
- description
- created_at
- updated_at
4.2 Why this pattern is recommended
Because it is:
scalable
explicit
reusable across modules
safe for SaaS
compatible with partial translation coverage
It avoids:
schema pollution
rigid six-language columns
overuse of JSON blobs for critical searchable content
4.3 Base Language Rule
Each master record must define:
base_language
base values in that language
This base version lives in the main table.
The base version does not need to be duplicated in the translation table.
4.4 Translation Table Rule
Each translation table must enforce conceptual uniqueness:
unique (parent_id, language_code)
Meaning:
one translation per language per record
no duplicates
no ambiguity during read resolution
5. Fallback Rules for Master Texts
When rendering a master text in the UX:
Priority
requested user language
record base language
Because base language is mandatory, this guarantees there is always a usable value.
Example
User language = fr
Treatment has:
base_language = es
French translation exists
Result:
show French
If French translation does not exist:
show Spanish base value
6. Free Text Translation Strategy
6.1 Storage Rule
For free texts:
store original only
Optional enhancement:
language detection metadata may be added later if needed
but translated content is not stored
6.2 UX Rule
Translation is triggered by explicit user action.
Example UX
original note visible
button: "Translate"
translated text displayed below
clear label: "Automatic translation"
original remains visible or easily accessible
6.3 Safety Principle
Translation must never replace the original record visually in a misleading way.
The user must understand:
which text is original
which text is machine-translated
7. What Must NOT Be Done
7.1 Do NOT persist automatic translations of free text
Not allowed:
note_es
note_fr
note_ru
translation JSON stored for user-authored operational notes
7.2 Do NOT force six-language completion
Not allowed:
requiring ES + EN + FR + RU + UK + HY for each master record
7.3 Do NOT mix UI i18n with business multilingual content
Not allowed:
treating treatment descriptions like UI keys
storing catalog content inside message JSON files
7.4 Do NOT use six fixed multilingual columns in domain tables
Bad pattern:
name_es, name_en, name_fr, etc.
7.5 Do NOT replace original free text with translated free text
The translated view is assistive only.
8. Scope of This Strategy
8.1 Included
This strategy applies to:
treatment catalog texts
future reusable business templates
free user-authored texts in patient / encounter / proposal contexts
8.2 Excluded
This strategy does not yet define:
exact translation provider
exact caching mechanism for on-demand translations
exact RBAC for who may request translation
legal wording governance for patient-facing official documents
document generation pipeline details
These must be analyzed separately.
9. Product Rationale
This strategy is chosen because it balances:
9.1 Clinical integrity
Original clinical text remains authoritative.
9.2 Legal clarity
Machine translation is never confused with the official source text.
9.3 SaaS flexibility
A customer can operate with:
one language only
a small subset of supported languages
gradual multilingual expansion
9.4 Data model cleanliness
Translations are only persisted where they belong.
9.5 Implementation realism
We do not create a giant multilingual persistence problem across the whole ERP.
10. Action Plan — Analysis of Current Multilingual State
This section defines the audit plan that must be executed before implementation.
10.1 Objective
Understand the real current state of multilingual support in code.
10.2 Audit Goals
The audit must identify:
current next-intl coverage
hardcoded visible strings still present in frontend
modules already aligned with project contract
modules not aligned
current handling of business texts that should become multilingual master texts
current free-text fields affected by translation-on-demand strategy
impact on backend, frontend, API contracts, and UX
10.3 Audit Areas
A. Frontend UI i18n audit
Review:
all visible strings in active pages/components
all current use of next-intl
missing translation keys
any legacy patterns
any hardcoded strings in JSX
any state labels derived incorrectly in frontend
B. Domain text audit
Review all business entities that contain text fields and classify each field as:
UI text
master text
free text
out of scope
C. Catalog audit
Review current Treatment / service catalog model and determine:
which fields are master texts
how they are currently stored
migration impact to translation child-table model
D. Free text audit
Review current free text fields in:
Patient
Encounter
Proposal-related entities
any other operational module
Determine:
which fields are user-authored
where translation-on-demand would matter in UX
whether original language metadata is already present or absent
E. UX audit
Review current pages and identify:
where translated assistive reading would be useful
where the original must always stay prominent
whether there are existing patterns that would conflict with this decision
F. Backend/API audit
Review:
serializers
model constraints
API response shape
whether multilingual master text support already exists anywhere
what would break if introduced
11. Expected Output of the Analysis Phase
The analysis must produce:
11.1 Field Classification Matrix
For each relevant field:
module
model
field
current behavior
classification: master / free / UI / ignore
proposed target behavior
migration required: yes/no
11.2 Frontend i18n Gap List
A concrete list of:
files with hardcoded strings
missing namespaces/keys
invalid status rendering patterns
legacy or inconsistent i18n behavior
11.3 Impact Report
A real impact report describing:
backend model changes needed
serializer changes needed
query changes needed
frontend component changes needed
migration risk
UX risk
rollout order
12. Action Plan — Implementation Strategy
Implementation must be incremental and safe.
Phase 1 — Audit and Classification
Goal:
classify all relevant text fields
identify gaps
avoid blind implementation
Deliverables:
classification matrix
i18n frontend audit
impact report
Phase 2 — Fix current UI i18n gaps
Goal:
make active frontend comply with existing project contract first
Tasks:
remove hardcoded visible strings
normalize next-intl usage
ensure domain status rendering follows canonical backend state labels
No domain model changes yet.
Phase 3 — Introduce multilingual master-text architecture
Goal:
implement translation child-table pattern in the first selected module
Recommended first module:
Treatment catalog
Tasks:
add base_language
create translation table
adapt serializers
adapt admin/API/frontend reads
implement fallback behavior
Phase 4 — Update catalog UX
Goal:
make master-text editing usable
Tasks:
allow creating/editing base language content
allow optional per-language translations
do not require all six languages
clearly show missing translations
show effective rendered value by fallback logic
Phase 5 — Implement translation-on-demand for free text
Goal:
support assistive translation in UX without altering persistence
Tasks:
identify first UX targets
add translate action in selected screens
show translated output clearly labeled
keep original visible
do not store translated free text in database
Recommended first UX targets:
Encounter notes
Patient notes
other clinically relevant free-text sections
Phase 6 — Expand reusable multilingual master-text pattern
Goal:
apply same pattern to other master-text entities when needed
Examples:
document templates
reusable proposal blocks
standardized instructions
Only after first implementation is proven stable.
13. Rollout Principles
13.1 No big bang rewrite
This must not be implemented as a system-wide rewrite.
13.2 Start where business value is highest
Recommended first target:
Treatment catalog
13.3 Free text translation must remain assistive
No silent persistence.
No replacement of authoritative record.
13.4 Do not overbuild
No generalized multilingual engine before proving the first use case.
14. Open Questions for Future Decision
These are intentionally left open for later decisions:
Should original-language metadata be stored for free text?
Which translation provider should be used for on-demand free-text translation?
Should translated free text be cached transiently outside domain tables?
Which roles are allowed to request translation?
Which patient-facing documents require human-authored official translations rather than machine translation?
Should multilingual support for master texts be per LegalEntity configuration?
These are not blocked by the present decision and can be handled in later steps.
15. Final Approved Rule Set
Official Rules
UI text uses next-intl.
Master texts use structured optional translations.
Master texts require a base language.
Filling all six languages is not mandatory.
Free texts store original only.
Free-text translation is on-demand in UX only.
Automatic translation is assistive, never authoritative.
Original free text remains the single source of truth.
Translation persistence for free text is forbidden unless a future explicit architectural decision changes this.
16. Recommended Next Step
Run a real code audit of:
current next-intl compliance
current text-field classification
current catalog model
current free-text fields
UX points where translation-on-demand adds value
This analysis must happen before implementation work begins.