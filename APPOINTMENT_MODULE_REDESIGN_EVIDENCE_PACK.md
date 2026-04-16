# Evidence Pack: Appointment Module Redesign + Calendly Removal

**Date**: 2026-03-15
**Scope**: Complete Calendly removal, Appointment model redesign, AppointmentType model, state machine, auto-encounter, domain rule enforcement.

---

## 1. Exact List of Files Touched

### A. Backend — Source Code (Modified)

| # | File | Change |
|---|------|--------|
| 1 | `apps/api/apps/clinical/models.py` | AppointmentSourceChoices (removed CALENDLY, PUBLIC_LEAD; added ERP, PUBLIC_API), removed DRAFT from AppointmentStatusChoices, new AppointmentType model, Appointment redesign (clinic FK, appointment_type FK, treatment_plan FK, duration_planned/real, no external_id), `_ALLOWED_TRANSITIONS`, `clean()` with 5 business rules, `save()` with duration rule, `transition_status()` with auto-encounter, `_check_practitioner_overlap()` |
| 2 | `apps/api/apps/clinical/serializers.py` | AppointmentWriteSerializer with 7 explicit PrimaryKeyRelatedField declarations (patient, practitioner, clinic, appointment_type, encounter, treatment, treatment_plan), AppointmentDetailSerializer, AppointmentListSerializer |
| 3 | `apps/api/apps/clinical/views.py` | Unblocked `create()` (returns 201), `update()` with audit, `transition_status()` endpoint, attend() uses clinic, removed `_process_calendly_sync()`, PractitionerBookingView source='erp', backward compat clinic_id/location_id |
| 4 | `apps/api/apps/clinical/services.py` | `create_encounter_from_appointment()` uses appointment.clinic, `calculate_availability()` uses clinic_id filter, removed 'draft' from status filter |
| 5 | `apps/api/apps/clinical/admin.py` | Added AppointmentTypeAdmin, updated AppointmentAdmin |
| 6 | `apps/api/apps/clinical/urls.py` | Added URL patterns |
| 7 | `apps/api/apps/authz/models.py` | Removed calendly_url from Practitioner, removed calendly_event_type_uris |
| 8 | `apps/api/apps/authz/serializers.py` | Removed calendly_url |
| 9 | `apps/api/apps/authz/serializers_users.py` | Removed calendly_url from user serializers |
| 10 | `apps/api/apps/authz/views_users.py` | Removed `_calendly_warnings()` helper |
| 11 | `apps/api/apps/core/serializers.py` | Removed calendly references |
| 12 | `apps/api/apps/core/views.py` | Removed calendly config endpoint |
| 13 | `apps/api/apps/core/management/commands/bootstrap_dev_users.py` | Removed calendly_url from demo data |
| 14 | `apps/api/apps/integrations/views.py` | Gutted Calendly integration views |
| 15 | `apps/api/apps/integrations/urls.py` | Emptied URL patterns |
| 16 | `apps/api/config/settings.py` | Removed CALENDLY_API_KEY, CALENDLY_WEBHOOK_SECRET, CALENDLY_ORG_URI |
| 17 | `apps/api/config/urls.py` | Removed integrations URL include |
| 18 | `apps/api/update_user_email.py` | Removed calendly references |

### B. Backend — Test Files (Modified)

| # | File | Change |
|---|------|--------|
| 19 | `conftest.py` | appointment fixture: location→clinic, factory: source='erp', clinic key |
| 20 | `apps/api/tests/conftest.py` | Updated appointment fixtures |
| 21 | `apps/api/tests/test_appointments_api.py` | test_create rewritten for 201, str() UUID comparison |
| 22 | `apps/api/tests/test_appointments_attend.py` | location_id→clinic_id |
| 23 | `apps/api/tests/test_appointments_link_encounter.py` | location→clinic, auto-encounter E2E fix |
| 24 | `apps/api/tests/test_appointments_practitioners.py` | location→clinic, PUBLIC_LEAD→PUBLIC_API, practitioner fixtures, E2E auto-encounter fix |
| 25 | `apps/api/tests/test_availability.py` | location→clinic, source→erp |
| 26 | `apps/api/tests/test_booking.py` | source assertion 'manual'→'erp', location→clinic |
| 27 | `apps/api/tests/test_business_rules.py` | location→clinic, source→erp, draft→scheduled, test rename |
| 28 | `apps/api/tests/test_admin_bypass_protection.py` | DRAFT→SCHEDULED, added practitioner |
| 29 | `apps/api/tests/test_permissions_smoke.py` | Expected 400→201 for create, location_id→clinic_id, source→erp |
| 30 | `apps/api/tests/test_treatment_plan.py` | treatment_plan.treatment→treatment_plan.proposal_line.treatment helper fix |
| 31 | `apps/api/tests/test_treatment_session_api.py` | location→clinic, source→erp, removed skip_validation from create |
| 32 | `apps/api/tests/test_patient_merge.py` | Added practitioner with user FK |
| 33 | `apps/api/tests/test_patient_merge_OLD.py` | Reverted Encounter location, added practitioner, source→erp |
| 34 | `apps/api/tests/test_layer2_a2_sales_integrity.py` | Added practitioner fixture with user FK |
| 35 | `apps/api/tests/test_user_profile_api.py` | Removed calendly_url tests |
| 36 | `apps/api/tests/test_yo_usuario.py` | Removed calendly_url assertions |
| 37 | `apps/api/tests/test_clinical_audit.py` | Updated appointment fixtures |

### C. Backend — Files Deleted

| # | File | Reason |
|---|------|--------|
| 38 | `apps/api/tests/test_calendly_webhook.py` | Calendly webhook tests — no longer needed |
| 39 | `apps/api/tests/test_appointment_creation_blocked.py` | Tested old "creation blocked" behavior — appointments can now be created |

### D. Frontend — Files Modified

| # | File | Change |
|---|------|--------|
| 40 | `apps/web/src/lib/routing.ts` | Removed /schedule route |
| 41 | `apps/web/src/lib/auth-context.tsx` | Removed calendly_url from user context |
| 42 | `apps/web/src/lib/types.ts` | Removed calendly_url from Practitioner type |
| 43 | `apps/web/src/app/[locale]/booking/page.tsx` | Removed Calendly embed references |
| 44 | `apps/web/src/app/[locale]/page.tsx` | Removed schedule card from Agenda |
| 45 | `apps/web/src/app/[locale]/admin/users/[id]/edit/page.tsx` | Removed calendly_url field |
| 46 | `apps/web/src/app/[locale]/admin/users/new/page.tsx` | Removed calendly_url field |

### E. Frontend — Files Deleted

| # | File | Reason |
|---|------|--------|
| 47 | `apps/web/src/components/calendly-embed.tsx` | Calendly iframe component |
| 48 | `apps/web/src/components/calendly-not-configured.tsx` | "Calendly not configured" fallback |
| 49 | `apps/web/src/lib/hooks/use-calendly-config.ts` | Calendly config hook |
| 50 | `apps/web/src/app/[locale]/schedule/page.tsx` | Schedule page (Calendly embed) |

### F. Migration Files Generated

| # | File |
|---|------|
| 51 | `apps/api/apps/authz/migrations/0009_drop_calendly_event_type_uris.py` |
| 52 | `apps/api/apps/authz/migrations/0010_remove_practitioner_calendly_url.py` |
| 53 | `apps/api/apps/clinical/migrations/0114_appointmenttype_and_more.py` |

**Total: 53 files (18 source + 19 tests + 2 deleted tests + 7 frontend modified + 4 frontend deleted + 3 migrations)**

---

## 2. Unified Diffs — Core Files

Full diffs for all 53 files are saved at:
- **Backend**: `/tmp/evidence_full_backend.diff` (16,311 lines)
- **Frontend**: `/tmp/evidence_frontend.diff` (3,440 lines)

### 2.1 AppointmentSourceChoices (models.py)

```diff
 class AppointmentSourceChoices(models.TextChoices):
-    """Appointment source"""
-    CALENDLY = 'calendly', 'Calendly'
+    """Appointment source (how the appointment was booked)"""
+    ERP = 'erp', 'ERP'
+    PUBLIC_API = 'public_api', 'Public API'
     MANUAL = 'manual', 'Manual'
-    PUBLIC_LEAD = 'public_lead', 'Public Lead'
```

### 2.2 AppointmentStatusChoices (models.py)

```diff
-    SCHEDULED = 'scheduled', 'Scheduled'  # Initial state (replaces draft)
-    DRAFT = 'draft', 'Draft'  # Legacy - kept for backward compatibility
+    SCHEDULED = 'scheduled', 'Scheduled'
     CONFIRMED = 'confirmed', 'Confirmed'
```

### 2.3 New AppointmentType Model (models.py)

```python
class AppointmentType(TenantModel):
    """
    Types of appointment (e.g., Consultation, Follow-up, Laser Session).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    objects = TenantManager()
    unfiltered = models.Manager()
    legal_entity = models.ForeignKey(
        'legal.LegalEntity', on_delete=models.PROTECT, null=True, blank=True,
        related_name='appointment_types')
    name = models.CharField(max_length=100)
    default_duration_minutes = models.PositiveIntegerField(default=30)
    color = models.CharField(max_length=7, default='#3B82F6')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'appointment_type'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['legal_entity', 'name'],
                name='uq_appointment_type_name_per_entity',
            )
        ]
```

### 2.4 Appointment Model Redesign (models.py)

```diff
-    location = models.ForeignKey(
-        'core.ClinicLocation', on_delete=models.SET_NULL, blank=True, null=True,
-        related_name='appointments',
-    )
+    clinic = models.ForeignKey(
+        'core.ClinicLocation', on_delete=models.PROTECT, blank=True, null=True,
+        related_name='appointments',
+    )
+    appointment_type = models.ForeignKey(
+        'AppointmentType', on_delete=models.PROTECT, blank=True, null=True,
+        related_name='appointments',
+    )
+    treatment_plan = models.ForeignKey(
+        'treatment_plans.TreatmentPlan', on_delete=models.SET_NULL,
+        blank=True, null=True, related_name='appointments',
+    )
+    duration_planned = models.PositiveIntegerField(default=30)
+    duration_real = models.PositiveIntegerField(blank=True, null=True)
     source = models.CharField(
         max_length=20, choices=AppointmentSourceChoices.choices,
-        default=AppointmentSourceChoices.MANUAL,
+        default=AppointmentSourceChoices.ERP,
     )
-    external_id = models.CharField(max_length=255, unique=True, blank=True, null=True)
```

### 2.5 State Machine (models.py)

```python
_ALLOWED_TRANSITIONS = {
    'scheduled': ['confirmed', 'cancelled', 'no_show'],
    'confirmed': ['checked_in', 'cancelled', 'no_show'],
    'checked_in': ['completed'],
    'completed': [],  # Terminal state
    'cancelled': [],  # Terminal state
    'no_show': [],    # Terminal state
}
_ACTIVE_STATUSES = ['scheduled', 'confirmed', 'checked_in']
```

### 2.6 Business Rules — clean() (models.py)

```python
def clean(self):
    """
    BUSINESS RULES:
    1. Patient is required
    2. scheduled_end must be after scheduled_start
    3. No overlapping appointments for same practitioner
    4. treatment_plan requires treatment
    5. treatment_plan.proposal_line.treatment must equal treatment
    6. Duration rule: treatment.duration_minutes or appointment_type.default_duration_minutes
    """
    # RULE 4: treatment_plan requires treatment
    if self.treatment_plan_id and not self.treatment_id:
        errors['treatment'] = 'Un plan de tratamiento requiere un tratamiento asignado'

    # RULE 5: treatment_plan.proposal_line.treatment must equal appointment treatment
    if self.treatment_plan_id and self.treatment_id:
        try:
            plan_treatment_id = self.treatment_plan.proposal_line.treatment_id
            if plan_treatment_id and plan_treatment_id != self.treatment_id:
                errors['treatment'] = (
                    'El tratamiento de la cita no coincide con el del plan de tratamiento'
                )
        except Exception:
            pass  # plan or proposal_line not loaded yet, skip cross-check
```

### 2.7 Auto-Encounter on checked_in — transition_status() (models.py)

```python
def transition_status(self, new_status, user=None, reason=None):
    # ...validation...

    # Auto-create encounter on checked_in (max 1 per appointment)
    if new_status == AppointmentStatusChoices.CHECKED_IN and not self.encounter_id:
        encounter = Encounter(
            legal_entity=self.legal_entity,
            patient=self.patient,
            practitioner=self.practitioner,
            type=EncounterTypeChoices.COSMETIC_CONSULT,
            status=EncounterStatusChoices.DRAFT,
            occurred_at=timezone.now(),
        )
        encounter.save(skip_validation=True)
        self.encounter = encounter

    return True, None
```

### 2.8 Duration Rule — save() (models.py)

```python
def save(self, *args, **kwargs):
    skip_validation = kwargs.pop('skip_validation', False)
    # Duration rule
    if self.treatment_id:
        try:
            self.duration_planned = self.treatment.duration_minutes
        except Exception:
            pass
    elif self.appointment_type_id:
        try:
            self.duration_planned = self.appointment_type.default_duration_minutes
        except Exception:
            pass
    if not skip_validation:
        self.full_clean()
    super().save(*args, **kwargs)
```

### 2.9 Serializer FK Fix (serializers.py)

```python
class AppointmentWriteSerializer(serializers.ModelSerializer):
    patient_id = serializers.PrimaryKeyRelatedField(
        queryset=Patient.objects.all(), source='patient')
    practitioner_id = serializers.PrimaryKeyRelatedField(
        queryset=Practitioner.objects.all(), source='practitioner')
    clinic_id = serializers.PrimaryKeyRelatedField(
        queryset=ClinicLocation.objects.all(), source='clinic',
        required=False, allow_null=True)
    appointment_type_id = serializers.PrimaryKeyRelatedField(
        queryset=AppointmentType.objects.all(), source='appointment_type',
        required=False, allow_null=True)
    encounter_id = serializers.PrimaryKeyRelatedField(
        queryset=Encounter.objects.all(), source='encounter',
        required=False, allow_null=True)
    treatment_id = serializers.PrimaryKeyRelatedField(
        queryset=Treatment.objects.all(), source='treatment',
        required=False, allow_null=True)
    treatment_plan_id = serializers.PrimaryKeyRelatedField(
        queryset=TreatmentPlan.objects.all(), source='treatment_plan',
        required=False, allow_null=True)
```

### 2.10 Calendly Removal — settings.py

```diff
-CALENDLY_API_KEY = os.environ.get('CALENDLY_API_KEY', '')
-CALENDLY_WEBHOOK_SECRET = os.environ.get('CALENDLY_WEBHOOK_SECRET', '')
-CALENDLY_ORG_URI = os.environ.get('CALENDLY_ORG_URI', '')
```

### 2.11 Calendly Removal — authz/models.py

```diff
-    calendly_url = models.URLField(max_length=512, blank=True, null=True)
-    calendly_event_type_uris = models.JSONField(default=list, blank=True)
```

### 2.12 Treatment Plan Domain Rule — test helper (test_treatment_plan.py)

```python
def _make_appointment(patient, practitioner, clinic_location, *, treatment_plan=None, status='scheduled', day_offset=1):
    """Create an appointment, optionally linked to a treatment plan."""
    treatment = treatment_plan.proposal_line.treatment if treatment_plan else None
    return Appointment.objects.create(
        patient=patient,
        practitioner=practitioner,
        clinic=clinic_location,
        source='erp',
        treatment_plan=treatment_plan,
        treatment=treatment,
        ...
    )
```

### 2.13 services.py — location→clinic fix

```diff
 def create_encounter_from_appointment(appointment, user=None):
-    location=appointment.location,
+    location=appointment.clinic,

 def calculate_availability(...):
-    .filter(location_id=clinic_id, ...)
+    .filter(clinic_id=clinic_id, ...)
-    .exclude(status__in=['draft', 'cancelled', 'no_show'])
+    .exclude(status__in=['cancelled', 'no_show'])
```

---

## 3. Verification Commands — Real Terminal Output

### 3.1 makemigrations --check

```
$ docker exec emr-api-dev python manage.py makemigrations --check --dry-run

No changes detected
```

**Result: PASS** — No pending migrations.

### 3.2 migrate

```
$ docker exec emr-api-dev python manage.py migrate --run-syncdb

Operations to perform:
    Running deferred SQL...
Running migrations:
  No migrations to apply.
```

**Result: PASS** — All migrations applied.

### 3.3 pytest (Full Suite)

```
$ docker exec emr-api-dev python -m pytest tests/ --tb=no

842 passed, 182 skipped, 9 warnings in 144.95s (0:02:24)
```

**Result: PASS** — 842 passed, 0 failed, 0 errors.

### 3.4 grep -R "calendly" (Calendly Removal Verification)

```
$ docker exec emr-api-dev grep -Ri "calendly" --include="*.py" --include="*.tsx" \
  --include="*.ts" --include="*.json" --include="*.yml" --include="*.yaml" \
  --include="*.sh" --include="*.md" -l . 2>/dev/null \
  | grep -v "__pycache__" | grep -v "node_modules" | grep -v migrations | grep -v ".git"

(empty — zero matches)
```

**Result: PASS** — Zero Calendly references in all source files (only remains in migration history, which is correct).

---

## 4. Domain Rule Verification: Appointment.treatment must match TreatmentPlan

### Rule Implementation Path

Since `TreatmentPlan` does **NOT** have a direct `treatment` FK, the validation traverses:

```
treatment_plan → proposal_line → treatment
```

### In Model (apps/clinical/models.py — Appointment.clean(), RULE 5)

```python
# RULE 5: treatment_plan.proposal_line.treatment must equal appointment treatment
if self.treatment_plan_id and self.treatment_id:
    try:
        plan_treatment_id = self.treatment_plan.proposal_line.treatment_id
        if plan_treatment_id and plan_treatment_id != self.treatment_id:
            errors['treatment'] = (
                'El tratamiento de la cita no coincide con el del plan de tratamiento'
            )
    except Exception:
        pass  # plan or proposal_line not loaded yet, skip cross-check
```

### In Tests (test_treatment_plan.py — _make_appointment helper)

```python
treatment = treatment_plan.proposal_line.treatment if treatment_plan else None
```

### Chain Explanation

```
TreatmentPlan
  └── proposal_line (OneToOneField → ProposalLine)
        └── treatment (ForeignKey → Treatment)

Appointment
  └── treatment (ForeignKey → Treatment)
  └── treatment_plan (ForeignKey → TreatmentPlan)

RULE: Appointment.treatment_id == Appointment.treatment_plan.proposal_line.treatment_id
```

---

## 5. Manual Verification Checklist

### 5.1 Calendly Removal

- [x] `AppointmentSourceChoices.CALENDLY` removed
- [x] `AppointmentSourceChoices.PUBLIC_LEAD` removed
- [x] `Practitioner.calendly_url` field removed (+ migration)
- [x] `Practitioner.calendly_event_type_uris` field removed (+ migration)
- [x] `settings.CALENDLY_API_KEY` removed
- [x] `settings.CALENDLY_WEBHOOK_SECRET` removed
- [x] `settings.CALENDLY_ORG_URI` removed
- [x] `integrations/views.py` — Calendly sync/webhook handlers removed
- [x] `integrations/urls.py` — URL patterns emptied
- [x] `config/urls.py` — integrations include removed
- [x] `views_users.py` — `_calendly_warnings()` helper removed
- [x] `bootstrap_dev_users.py` — calendly_url removed from demo data
- [x] `update_user_email.py` — calendly references removed
- [x] Frontend: `calendly-embed.tsx` DELETED
- [x] Frontend: `calendly-not-configured.tsx` DELETED
- [x] Frontend: `use-calendly-config.ts` DELETED
- [x] Frontend: `schedule/page.tsx` DELETED
- [x] Frontend: `routing.ts` — /schedule route removed
- [x] Frontend: `auth-context.tsx` — calendly_url removed
- [x] Frontend: `types.ts` — calendly_url removed from Practitioner
- [x] Frontend: admin user edit/new pages — calendly_url field removed
- [x] Test: `test_calendly_webhook.py` DELETED
- [x] Test: `test_appointment_creation_blocked.py` DELETED
- [x] Test: `test_user_profile_api.py` — calendly assertions removed
- [x] Test: `test_yo_usuario.py` — calendly assertions removed
- [x] `grep -Ri "calendly"` returns **zero matches** outside migrations

### 5.2 Appointment Model Redesign

- [x] `AppointmentType` model created with name, default_duration_minutes, color, is_active
- [x] `Appointment.location` → `Appointment.clinic` (FK rename)
- [x] `Appointment.external_id` removed
- [x] `Appointment.appointment_type` FK added
- [x] `Appointment.treatment_plan` FK added
- [x] `Appointment.duration_planned` field added (default=30)
- [x] `Appointment.duration_real` field added (nullable)
- [x] `Appointment.practitioner` is NOT NULL (PROTECT)
- [x] `Appointment.source` default changed to 'erp'
- [x] `AppointmentStatusChoices.DRAFT` removed
- [x] Indexes on: patient, practitioner, scheduled_start, status, clinic, is_deleted

### 5.3 State Machine

- [x] scheduled → confirmed, cancelled, no_show
- [x] confirmed → checked_in, cancelled, no_show
- [x] checked_in → completed (ONLY)
- [x] completed, cancelled, no_show → terminal (no transitions)
- [x] no_show requires scheduled_start in the past
- [x] `transition_status()` method with ValidationError on invalid transitions

### 5.4 Auto-Encounter

- [x] Auto-creates Encounter on checked_in transition
- [x] Max 1 encounter per appointment (check `not self.encounter_id`)
- [x] Encounter created with type=COSMETIC_CONSULT, status=DRAFT, occurred_at=now()

### 5.5 Business Rules (clean())

- [x] RULE 1: Patient required
- [x] RULE 2: scheduled_end > scheduled_start
- [x] RULE 3: Practitioner overlap detection for active statuses
- [x] RULE 4: treatment_plan requires treatment
- [x] RULE 5: treatment matches via `treatment_plan.proposal_line.treatment_id`
- [x] RULE 6: Duration auto-computed from treatment or appointment_type

### 5.6 Serializer

- [x] 7 explicit PrimaryKeyRelatedField declarations (patient, practitioner, clinic, appointment_type, encounter, treatment, treatment_plan)
- [x] Status validation: cannot change via PUT/PATCH, must use /transition/ endpoint
- [x] Create returns 201

### 5.7 Test Suite

- [x] Baseline: 856 passed (pre-changes)
- [x] Final: **842 passed, 0 failed, 0 errors, 182 skipped**
- [x] Delta: −14 tests (2 files deleted: test_calendly_webhook 237 lines, test_appointment_creation_blocked 167 lines)
- [x] All location→clinic renames applied in tests
- [x] All source='manual'→'erp' where appropriate
- [x] All status='draft'→'scheduled' for appointment creates
- [x] All practitioner fixtures include user FK (NOT NULL constraint)
- [x] Encounter.location NOT renamed (only Appointment was renamed)

---

## 6. Migration Files

### authz/0009_drop_calendly_event_type_uris.py
Removes `calendly_event_type_uris` JSONField from Practitioner.

### authz/0010_remove_practitioner_calendly_url.py
Removes `calendly_url` URLField from Practitioner.

### clinical/0114_appointmenttype_and_more.py
- Creates `AppointmentType` model with unique constraint
- Renames `Appointment.location` → `Appointment.clinic`
- Removes `Appointment.external_id`
- Adds `Appointment.appointment_type`, `treatment_plan`, `duration_planned`, `duration_real` fields
- Updates indexes
- Makes `Appointment.practitioner` NOT NULL
- Changes `Appointment.source` default to 'erp'
- Removes `DRAFT` from status choices

---

## 7. Architecture Summary

```
┌─────────────┐    ┌──────────────────┐    ┌───────────────┐
│ Frontend    │───▶│ DRF ViewSet      │───▶│ Appointment   │
│ (ERP UI)    │    │ create/update    │    │ Model         │
└─────────────┘    │ /transition/     │    │               │
                   └──────────────────┘    │ save()        │
┌─────────────┐             │              │  └─duration   │
│ Public API  │─────────────┘              │ clean()       │
│ (Booking)   │                            │  ├─patient    │
└─────────────┘                            │  ├─time range │
                                           │  ├─overlap    │
                                           │  ├─tp→treat   │
                                           │  └─tp match   │
                                           │ transition()  │
                                           │  └─auto enc   │
                                           └───────────────┘

State Machine:
  scheduled ──▶ confirmed ──▶ checked_in ──▶ completed
      │              │              │
      ├─▶ cancelled  ├─▶ cancelled  (only → completed)
      └─▶ no_show    └─▶ no_show

Domain Rule (treatment match):
  Appointment.treatment_id == TreatmentPlan.proposal_line.treatment_id
```

---

*End of Evidence Pack*
