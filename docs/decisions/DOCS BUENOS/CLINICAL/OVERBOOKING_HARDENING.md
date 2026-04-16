Evidence Pack: Overbooking Protection Hardening
Date: 2026-03-16
Scope: Database-level overbooking protection + transactional booking safety

1. Exact List of Files Touched
#	File	Change
1	settings.py	Added django.contrib.postgres to INSTALLED_APPS
2	models.py	Added constraint documentation in Appointment.Meta, updated _check_practitioner_overlap() docstring to explain dual-layer protection
3	views.py	Wrapped booking stages 4-6 in transaction.atomic() + select_for_update(), added OperationalError import, improved IntegrityError/deadlock handler → HTTP 409
4	0116_prevent_practitioner_overbooking.py	NEW — CREATE EXTENSION btree_gist + exclusion constraint prevent_practitioner_overbooking
5	test_booking.py	NEW TestConcurrentBooking class: test_concurrent_booking_one_wins (threading), test_db_constraint_blocks_raw_overlap (ORM)
Total: 5 files (4 modified + 1 new migration)

2. Unified Diffs
2.1 settings.py — django.contrib.postgres

 INSTALLED_APPS = [     'django.contrib.staticfiles',+    'django.contrib.postgres',          # Third-party apps
2.2 models.py — Appointment.Meta constraint documentation

         indexes = [             models.Index(fields=['patient'], name='idx_appointment_patient'),             ...             models.Index(fields=['is_deleted'], name='idx_appointment_deleted'),         ]+        # Database-level overbooking protection (GiST exclusion constraint).+        # Managed via RunSQL in migration 0116 because it uses tstzrange()+        # on plain DateTimeField columns (not Django RangeField).+        # Constraint name: prevent_practitioner_overbooking+        # Condition: same practitioner + overlapping time range ++        #            status IN (scheduled, confirmed, checked_in) + is_deleted=false
2.3 models.py — _check_practitioner_overlap() docstring

     def _check_practitioner_overlap(self):-        """-        Check for overlapping appointments with same practitioner.+        """+        Application-level overlap check (early validation layer).++        This runs BEFORE save() to provide user-friendly error messages.+        The database ExclusionConstraint 'prevent_practitioner_overbooking'+        is the final safety net against race conditions.
2.4 views.py — Transactional booking

-        # ========================-        # 4. VALIDATE SLOT IS AVAILABLE (using AvailabilityService)-        # ========================-        try:-            availability_data = AvailabilityService.calculate_availability(...)-            ...-            appointment = Appointment.objects.create(**create_kwargs)-            ...-        except IntegrityError as e:-            ...+        # ================================================================+        # TRANSACTIONAL BOOKING (Steps 4-6)+        #+        # Wrapped in transaction.atomic() to prevent race conditions.+        # The availability check + appointment creation happen atomically.+        # The DB ExclusionConstraint 'prevent_practitioner_overbooking'+        # is the final safety net: if two concurrent requests pass the+        # application-level check, the constraint will reject the second+        # INSERT, raising IntegrityError → HTTP 409.+        # ================================================================+        try:+            with transaction.atomic():+                # Lock the practitioner's active appointments to serialize+                # concurrent booking attempts for the same practitioner.+                Appointment.unfiltered.select_for_update().filter(+                    practitioner_id=practitioner_id,+                    status__in=Appointment._ACTIVE_STATUSES,+                    is_deleted=False,+                ).exists()++                # 4. VALIDATE SLOT IS AVAILABLE+                availability_data = AvailabilityService.calculate_availability(...)+                ...+                # 6. CREATE APPOINTMENT+                appointment = Appointment.objects.create(**create_kwargs)++            # Outside transaction — log + respond+            return Response({...}, status=status.HTTP_201_CREATED)++        except (IntegrityError, OperationalError) as e:+            # IntegrityError: exclusion constraint violation (overlap detected).+            # OperationalError: deadlock from concurrent constraint checks.+            logger.warning(f"Overbooking prevented by DB constraint: {e}")+            return Response({+                'error': 'The selected time slot is no longer available.',+                'details': 'Another appointment was booked for this practitioner at the same time.'+            }, status=status.HTTP_409_CONFLICT)
2.5 Migration 0116

operations = [    # Step 1: Enable btree_gist extension    migrations.RunSQL(        sql="CREATE EXTENSION IF NOT EXISTS btree_gist;",        reverse_sql="DROP EXTENSION IF EXISTS btree_gist;",    ),    # Step 2: Exclusion constraint with CASE to handle skip_validation rows    migrations.RunSQL(        sql="""            ALTER TABLE appointment            ADD CONSTRAINT prevent_practitioner_overbooking            EXCLUDE USING gist (                practitioner_id WITH =,                (CASE WHEN scheduled_start < scheduled_end                      THEN tstzrange(scheduled_start, scheduled_end)                      ELSE 'empty'::tstzrange                 END) WITH &&            )            WHERE (                status IN ('scheduled', 'confirmed', 'checked_in')                AND is_deleted = false            );        """,        reverse_sql="ALTER TABLE appointment DROP CONSTRAINT IF EXISTS prevent_practitioner_overbooking;",    ),]
2.6 New Tests — TestConcurrentBooking

@pytest.mark.django_db(transaction=True)class TestConcurrentBooking:    def test_concurrent_booking_one_wins(self, ...):        """Two threads book the same slot — exactly one gets 201, the other 409."""        # Uses threading to simulate concurrent requests        # Asserts exactly one 201 and one 409        # Verifies exactly 1 appointment exists    def test_db_constraint_blocks_raw_overlap(self, ...):        """Direct ORM: two overlapping appointments → IntegrityError."""        # Creates appointment via save(skip_validation=True)        # Second overlapping save raises django.db.IntegrityError
3. Verification Commands — Real Terminal Output
3.1 makemigrations --check

$ docker exec emr-api-dev python manage.py makemigrations --check --dry-runNo changes detected
Result: PASS — No pending migrations.

3.2 migrate

$ docker exec emr-api-dev python manage.py migrate clinical 0116Running migrations:  No migrations to apply.
Result: PASS — Migration 0116 already applied.

3.3 pytest (Full Suite)

$ docker exec emr-api-dev python -m pytest tests/ --tb=no844 passed, 182 skipped, 9 warnings in 164.15s (0:02:44)
Result: PASS — 844 passed (842 baseline + 2 new), 0 failed.

3.4 Appointment-Specific Tests

$ docker exec emr-api-dev python -m pytest tests/test_booking.py tests/test_business_rules.py \  tests/test_appointments_api.py tests/test_appointments_attend.py \  tests/test_appointments_link_encounter.py tests/test_appointments_practitioners.py \  tests/test_admin_bypass_protection.py --tb=no --create-db140 passed, 1 skipped, 4 warnings in 45.09s
Result: PASS — All 140 appointment tests pass (including 2 new concurrency tests).

4. Database Verification
4.1 Extensions

  extname   | extversion------------+------------ btree_gist | 1.7 pg_trgm    | 1.6 plpgsql    | 1.0
btree_gist 1.7 installed.

4.2 Exclusion Constraint

             conname              | contype |  definition----------------------------------+---------+----------------------------------------------------- prevent_practitioner_overbooking | x       | EXCLUDE USING gist (practitioner_id WITH =, (                                  |         | CASE                                  |         |     WHEN scheduled_start < scheduled_end                                  |         |         THEN tstzrange(scheduled_start, scheduled_end)                                  |         |     ELSE 'empty'::tstzrange                                  |         | END) WITH &&)                                  |         | WHERE ((status::text = ANY (ARRAY['scheduled',                                  |         |   'confirmed', 'checked_in']::text[]))                                  |         |   AND is_deleted = false)
Exclusion constraint (contype = x) exists with correct definition.

4.3 GiST Index (created automatically by exclusion constraint)

            indexname             |  indexdef----------------------------------+----------------------------------------------------- prevent_practitioner_overbooking | CREATE INDEX prevent_practitioner_overbooking                                  | ON public.appointment USING gist (practitioner_id, (...))                                  | WHERE (((status)::text = ANY (...)) AND (is_deleted = false))
GiST index confirmed.

4.4 All Appointment Indexes Preserved

 appointment_pkey idx_appointment_patient idx_appointment_practitioner idx_appointment_start idx_appointment_status idx_appointment_clinic idx_appointment_deleted idx_appointment_legal_entity prevent_practitioner_overbooking    ← NEW (GiST)
18 total indexes including the new GiST exclusion index.

5. Manual Verification Checklist
5.1 Database-Level Protection
 btree_gist extension enabled (v1.7)
 prevent_practitioner_overbooking exclusion constraint created
 Constraint uses GiST index
 Constraint condition: status IN ('scheduled','confirmed','checked_in') AND is_deleted = false
 CASE expression prevents DataError for rows with scheduled_end < scheduled_start (skip_validation edge case)
 Cancelled/no_show/completed appointments do NOT block slots
 Soft-deleted appointments do NOT block slots
5.2 Transactional Booking
 transaction.atomic() wraps availability check + appointment creation
 select_for_update() locks practitioner's active appointments during booking
 Availability check happens INSIDE the transaction (after lock)
 No TOCTOU race condition between availability check and INSERT
5.3 Error Handling
 IntegrityError caught → HTTP 409 Conflict
 OperationalError (deadlock) caught → HTTP 409 Conflict
 Error message: "The selected time slot is no longer available."
 Detailed message: "Another appointment was booked for this practitioner at the same time."
5.4 Application-Level Overlap (Preserved)
 _check_practitioner_overlap() method unchanged (still runs in clean())
 Provides user-friendly error messages before hitting DB constraint
 Docstring documents dual-layer protection strategy
5.5 Test Coverage
 test_concurrent_booking_one_wins: threading test — one 201, one 409
 test_db_constraint_blocks_raw_overlap: ORM-level IntegrityError test
 Existing test_double_booking_same_slot: sequential overlap test (still passes)
 test_save_with_skip_validation_bypasses_validation: CASE handler prevents DataError
5.6 Performance
 Exclusion constraint creates a partial GiST index (only active, non-deleted rows)
 Existing B-tree indexes on practitioner_id, scheduled_start, status preserved
 select_for_update() scoped to practitioner's active appointments only (minimal lock scope)
6. Architecture — Dual-Layer Protection

                   ┌─────────────────────────┐  Request ──────▶  │ PractitionerBookingView  │                   │                          │                   │  transaction.atomic() {  │                   │    select_for_update()   │  ← Serializes concurrent requests                   │    availability_check()  │  ← Reads under lock                   │    Appointment.create()  │  ← INSERT protected by constraint                   │  }                       │                   └──────────┬───────────────┘                              │              ┌───────────────┼───────────────┐              │               │               │    Layer 1: Model      Layer 2: Lock    Layer 3: DB    _check_overlap()    select_for_update   ExclusionConstraint    (clean/save)        (serialization)     (final safety net)              │               │               │    User-friendly      Prevents TOCTOU    Prevents INSERT    error messages     race condition     of overlapping rows
Why both layers?

Layer 1 (application): Provides user-friendly Spanish error messages before save. Catches errors early with field-level detail.
Layer 2 (lock): Serializes concurrent booking requests through select_for_update(). Prevents the TOCTOU race between availability check and INSERT.
Layer 3 (DB constraint): Final safety net. Even if layers 1-2 fail (e.g., direct SQL, Celery task, future code path), the database ABSOLUTELY prevents overlapping active appointments for the same practitioner.
Claude Opus 4.6 