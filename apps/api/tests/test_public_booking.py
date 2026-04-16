"""
Tests for Public Booking API.

Endpoints:
  GET  /public/booking/availability/
  POST /public/booking/create/

Coverage:
  1. availability with practitioner provided
  2. availability without practitioner (all eligible)
  3. create booking with practitioner provided
  4. create booking with auto-assignment
  5. patient auto-creation
  6. appointment status = scheduled
  7. appointment source = public_api
  8. booking rejects unavailable slots
  9. booking rejects practitioner/treatment mismatch
 10. booking respects overbooking protections
 11. concurrent booking: one succeeds, one fails
 12. audit log event written
"""
import threading
import pytest
from datetime import datetime, date, time, timedelta

import pytz
from django.utils import timezone
from rest_framework.test import APIClient

from apps.authz.models import Practitioner, User
from apps.clinical.models import (
    Appointment,
    Patient,
    PractitionerSchedule,
    PractitionerTreatment,
    Treatment,
)
from apps.core.models import Clinic
from apps.ops.models import AuditLog, AuditEventType
from tests.conftest import TEST_PASSWORD


def _make_token(clinic_id, **kwargs):
    """Generate a valid signed booking token for tests."""
    from apps.clinical.services_public_booking import PublicBookingTokenService
    return PublicBookingTokenService.generate(clinic_id=clinic_id, **kwargs)


@pytest.fixture(autouse=True)
def _disable_throttling(settings):
    """Set very high throttle rates to effectively disable throttling in tests."""
    from django.core.cache import cache
    cache.clear()
    settings.REST_FRAMEWORK = {
        **settings.REST_FRAMEWORK,
        'DEFAULT_THROTTLE_RATES': {
            'anon': '9999/min',
            'user': '9999/min',
            'lead_submissions': '9999/min',
            'lead_burst': '9999/min',
            'public_avail': '9999/min',
            'public_avail_burst': '9999/min',
            'public_create': '9999/min',
            'public_create_burst': '9999/min',
        },
    }


# ── Helpers ─────────────────────────────────────────────────────────

def _future_date(days=2):
    """Return a date safely in the future."""
    return (timezone.now() + timedelta(days=days)).date()


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def clinic(db, legal_entity):
    return Clinic.objects.create(
        name='Public Test Clinic',
        address_line1='1 Main St',
        city='Paris',
        timezone='UTC',
        is_active=True,
        legal_entity=legal_entity,
    )


@pytest.fixture
def treatment(db, legal_entity):
    return Treatment.objects.create(
        name='Botox Public',
        duration_minutes=30,
        is_active=True,
        legal_entity=legal_entity,
    )


@pytest.fixture
def practitioner_a(db):
    user = User.objects.create_user(
        email='pub_pract_a@test.com', password=TEST_PASSWORD, is_active=True,
    )
    return Practitioner.objects.create(
        user=user, display_name='Dr. Alpha', is_active=True,
    )


@pytest.fixture
def practitioner_b(db):
    user = User.objects.create_user(
        email='pub_pract_b@test.com', password=TEST_PASSWORD, is_active=True,
    )
    return Practitioner.objects.create(
        user=user, display_name='Dr. Beta', is_active=True,
    )


@pytest.fixture
def capability_a(db, practitioner_a, treatment):
    return PractitionerTreatment.objects.create(
        practitioner=practitioner_a, treatment=treatment, is_active=True,
    )


@pytest.fixture
def capability_b(db, practitioner_b, treatment):
    return PractitionerTreatment.objects.create(
        practitioner=practitioner_b, treatment=treatment, is_active=True,
    )


@pytest.fixture
def schedule_a(db, practitioner_a, clinic):
    """Create 7-day schedule for practitioner A at clinic."""
    objs = []
    for wd in range(7):
        objs.append(PractitionerSchedule(
            practitioner=practitioner_a, clinic=clinic,
            weekday=wd, start_time=time(8, 0), end_time=time(18, 0),
            is_active=True,
        ))
    return PractitionerSchedule.objects.bulk_create(objs)


@pytest.fixture
def schedule_b(db, practitioner_b, clinic):
    """Create 7-day schedule for practitioner B at clinic."""
    objs = []
    for wd in range(7):
        objs.append(PractitionerSchedule(
            practitioner=practitioner_b, clinic=clinic,
            weekday=wd, start_time=time(8, 0), end_time=time(18, 0),
            is_active=True,
        ))
    return PractitionerSchedule.objects.bulk_create(objs)


@pytest.fixture
def full_setup_a(capability_a, schedule_a):
    """Ensure capability + schedule exist for practitioner A."""
    pass


@pytest.fixture
def full_setup_both(capability_a, capability_b, schedule_a, schedule_b):
    """Ensure capability + schedule for both practitioners."""
    pass


# ── AVAILABILITY TESTS ─────────────────────────────────────────────

@pytest.mark.django_db
class TestPublicAvailability:

    URL = '/public/booking/availability/'

    def test_availability_with_practitioner(
        self, api_client, clinic, treatment, practitioner_a, full_setup_a,
    ):
        """1. Availability with practitioner_id returns slots for that practitioner."""
        fd = _future_date()
        resp = api_client.get(self.URL, {
            'clinic_id': str(clinic.id),
            'treatment_id': str(treatment.id),
            'date_from': fd.isoformat(),
            'date_to': fd.isoformat(),
            'practitioner_id': str(practitioner_a.id),
            'token': _make_token(clinic.id),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data['slots']) > 0
        # All slots belong to practitioner A
        for slot in data['slots']:
            assert slot['practitioner_id'] == str(practitioner_a.id)
            assert slot['practitioner_display_name'] == 'Dr. Alpha'

    def test_availability_without_practitioner(
        self, api_client, clinic, treatment,
        practitioner_a, practitioner_b, full_setup_both,
    ):
        """2. Availability without practitioner returns slots for all eligible."""
        fd = _future_date()
        resp = api_client.get(self.URL, {
            'clinic_id': str(clinic.id),
            'treatment_id': str(treatment.id),
            'date_from': fd.isoformat(),
            'date_to': fd.isoformat(),
            'token': _make_token(clinic.id),
        })
        assert resp.status_code == 200
        data = resp.json()
        pract_ids = {s['practitioner_id'] for s in data['slots']}
        assert str(practitioner_a.id) in pract_ids
        assert str(practitioner_b.id) in pract_ids

    def test_availability_invalid_clinic(self, api_client, treatment):
        """Availability returns 404 for nonexistent clinic."""
        import uuid
        fake_cid = uuid.uuid4()
        resp = api_client.get(self.URL, {
            'clinic_id': str(fake_cid),
            'treatment_id': str(treatment.id),
            'date_from': _future_date().isoformat(),
            'date_to': _future_date().isoformat(),
            'token': _make_token(fake_cid),
        })
        assert resp.status_code == 404

    def test_availability_practitioner_treatment_mismatch(
        self, api_client, clinic, treatment, practitioner_a, schedule_a,
    ):
        """Availability returns 422 if practitioner can't do the treatment."""
        # capability_a NOT loaded — practitioner has no capability
        fd = _future_date()
        resp = api_client.get(self.URL, {
            'clinic_id': str(clinic.id),
            'treatment_id': str(treatment.id),
            'date_from': fd.isoformat(),
            'date_to': fd.isoformat(),
            'practitioner_id': str(practitioner_a.id),
            'token': _make_token(clinic.id),
        })
        assert resp.status_code == 422


# ── CREATE BOOKING TESTS ───────────────────────────────────────────

@pytest.mark.django_db
class TestPublicCreateBooking:

    URL = '/public/booking/create/'

    def _payload(self, clinic, treatment, practitioner=None, **overrides):
        fd = _future_date()
        tz = pytz.UTC
        start = tz.localize(datetime.combine(fd, time(9, 0)))
        end = tz.localize(datetime.combine(fd, time(9, 30)))
        body = {
            'clinic_id': str(clinic.id),
            'treatment_id': str(treatment.id),
            'start_datetime': start.isoformat(),
            'end_datetime': end.isoformat(),
            'patient': {
                'first_name': 'Public',
                'last_name': 'Visitor',
                'email': 'visitor@example.com',
                'phone': '+33612345678',
            },
            'notes': 'Booked via website',
            'token': _make_token(clinic.id),
        }
        if practitioner:
            body['practitioner_id'] = str(practitioner.id)
        body.update(overrides)
        return body

    def test_create_booking_with_practitioner(
        self, api_client, clinic, treatment, practitioner_a, full_setup_a,
        legal_entity,
    ):
        """3. Create booking with practitioner_id succeeds."""
        resp = api_client.post(
            self.URL,
            self._payload(clinic, treatment, practitioner_a),
            format='json',
        )
        assert resp.status_code == 201, resp.json()
        data = resp.json()
        assert data['practitioner_id'] == str(practitioner_a.id)
        assert data['status'] == 'scheduled'

    def test_create_booking_auto_assignment(
        self, api_client, clinic, treatment,
        practitioner_a, practitioner_b, full_setup_both,
        legal_entity,
    ):
        """4. Create booking without practitioner auto-assigns one."""
        resp = api_client.post(
            self.URL,
            self._payload(clinic, treatment),
            format='json',
        )
        assert resp.status_code == 201, resp.json()
        data = resp.json()
        assert data['practitioner_id'] in [
            str(practitioner_a.id), str(practitioner_b.id),
        ]

    def test_patient_auto_creation(
        self, api_client, clinic, treatment, practitioner_a, full_setup_a,
        legal_entity,
    ):
        """5. Patient is auto-created when not found."""
        before = Patient.unfiltered.count()
        resp = api_client.post(
            self.URL,
            self._payload(clinic, treatment, practitioner_a),
            format='json',
        )
        assert resp.status_code == 201
        assert Patient.unfiltered.count() == before + 1
        patient = Patient.unfiltered.get(id=resp.json()['patient_id'])
        assert patient.first_name == 'Public'
        assert patient.last_name == 'Visitor'
        assert patient.email == 'visitor@example.com'

    def test_patient_dedup_by_email(
        self, api_client, clinic, treatment, practitioner_a, full_setup_a,
        legal_entity,
    ):
        """Patient with same email is reused, not duplicated."""
        Patient.objects.create(
            first_name='Existing', last_name='Patient',
            email='visitor@example.com',
            legal_entity=legal_entity,
        )
        before = Patient.unfiltered.count()
        resp = api_client.post(
            self.URL,
            self._payload(clinic, treatment, practitioner_a),
            format='json',
        )
        assert resp.status_code == 201
        assert Patient.unfiltered.count() == before  # no new patient

    def test_status_is_scheduled(
        self, api_client, clinic, treatment, practitioner_a, full_setup_a,
        legal_entity,
    ):
        """6. Created appointment has status = scheduled."""
        resp = api_client.post(
            self.URL,
            self._payload(clinic, treatment, practitioner_a),
            format='json',
        )
        assert resp.status_code == 201
        appt = Appointment.unfiltered.get(id=resp.json()['appointment_id'])
        assert appt.status == 'scheduled'

    def test_source_is_public_api(
        self, api_client, clinic, treatment, practitioner_a, full_setup_a,
        legal_entity,
    ):
        """7. Created appointment has source = public_api."""
        resp = api_client.post(
            self.URL,
            self._payload(clinic, treatment, practitioner_a),
            format='json',
        )
        assert resp.status_code == 201
        appt = Appointment.unfiltered.get(id=resp.json()['appointment_id'])
        assert appt.source == 'public_api'

    def test_rejects_unavailable_slot(
        self, api_client, clinic, treatment, practitioner_a, full_setup_a,
        legal_entity,
    ):
        """8. Booking is rejected when slot is not available."""
        fd = _future_date()
        tz = pytz.UTC
        start = tz.localize(datetime.combine(fd, time(9, 0)))
        end = tz.localize(datetime.combine(fd, time(9, 30)))

        # Pre-book the slot
        Appointment.objects.create(
            practitioner=practitioner_a, patient=Patient.objects.create(
                first_name='X', last_name='Y', legal_entity=legal_entity,
            ),
            clinic=clinic,
            scheduled_start=start, scheduled_end=end,
            status='scheduled', source='erp',
            legal_entity=legal_entity,
        )

        resp = api_client.post(
            self.URL,
            self._payload(clinic, treatment, practitioner_a),
            format='json',
        )
        assert resp.status_code == 409

    def test_rejects_practitioner_treatment_mismatch(
        self, api_client, clinic, treatment, practitioner_a, schedule_a,
        legal_entity,
    ):
        """9. Booking rejected if practitioner lacks capability."""
        # NO capability_a → mismatch
        resp = api_client.post(
            self.URL,
            self._payload(clinic, treatment, practitioner_a),
            format='json',
        )
        assert resp.status_code == 422

    def test_overbooking_protection(
        self, api_client, clinic, treatment, practitioner_a, full_setup_a,
        legal_entity,
    ):
        """10. Second booking on the same slot is rejected."""
        payload = self._payload(clinic, treatment, practitioner_a)

        r1 = api_client.post(self.URL, payload, format='json')
        assert r1.status_code == 201

        # Change patient email to avoid dedup reusing same Patient
        payload['patient']['email'] = 'other@example.com'
        r2 = api_client.post(self.URL, payload, format='json')
        assert r2.status_code == 409

    def test_audit_log_written(
        self, api_client, clinic, treatment, practitioner_a, full_setup_a,
        legal_entity,
    ):
        """12. Audit log entry created on booking."""
        before = AuditLog.objects.filter(
            event_type=AuditEventType.APPOINTMENT_CREATED,
        ).count()

        resp = api_client.post(
            self.URL,
            self._payload(clinic, treatment, practitioner_a),
            format='json',
        )
        assert resp.status_code == 201

        after = AuditLog.objects.filter(
            event_type=AuditEventType.APPOINTMENT_CREATED,
        ).count()
        assert after == before + 1

        log = AuditLog.objects.filter(
            event_type=AuditEventType.APPOINTMENT_CREATED,
        ).order_by('-timestamp').first()
        assert log.payload_json['source'] == 'public_api'
        assert str(log.entity_id) == resp.json()['appointment_id']

    def test_patient_creation_audit_log(
        self, api_client, clinic, treatment, practitioner_a, full_setup_a,
        legal_entity,
    ):
        """Audit log for patient auto-creation."""
        before = AuditLog.objects.filter(
            event_type=AuditEventType.PATIENT_CREATED,
        ).count()

        resp = api_client.post(
            self.URL,
            self._payload(clinic, treatment, practitioner_a),
            format='json',
        )
        assert resp.status_code == 201

        after = AuditLog.objects.filter(
            event_type=AuditEventType.PATIENT_CREATED,
        ).count()
        assert after == before + 1


@pytest.mark.django_db(transaction=True)
class TestPublicBookingConcurrency:
    """11. Concurrent bookings: one succeeds, one fails via DB constraint."""

    URL = '/public/booking/create/'

    def test_concurrent_booking_one_wins(
        self, clinic, treatment, practitioner_a,
        capability_a, schedule_a, legal_entity,
    ):
        fd = _future_date()
        tz = pytz.UTC
        start = tz.localize(datetime.combine(fd, time(10, 0)))
        end = tz.localize(datetime.combine(fd, time(10, 30)))

        payload = {
            'clinic_id': str(clinic.id),
            'treatment_id': str(treatment.id),
            'start_datetime': start.isoformat(),
            'end_datetime': end.isoformat(),
            'patient': {
                'first_name': 'Concurrent',
                'last_name': 'User',
            },
            'token': _make_token(clinic.id),
        }

        results = []

        def _book(email_suffix):
            client = APIClient()
            body = {**payload, 'patient': {
                'first_name': 'Concurrent',
                'last_name': f'User{email_suffix}',
                'email': f'concurrent{email_suffix}@test.com',
            }}
            try:
                r = client.post(self.URL, body, format='json')
                results.append(r.status_code)
            except Exception:
                results.append(500)

        t1 = threading.Thread(target=_book, args=('A',))
        t2 = threading.Thread(target=_book, args=('B',))
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        assert sorted(results) == [201, 409], f'Expected [201, 409] got {sorted(results)}'


# ── HARDENING TESTS ─────────────────────────────────────────────────

@pytest.mark.django_db
class TestPublicBookingHardening:
    """Tests for the hardening pass: signed tokens, anti-bot, dedup, errors."""

    AVAIL_URL = '/public/booking/availability/'
    CREATE_URL = '/public/booking/create/'

    def _booking_payload(self, clinic, treatment, practitioner=None):
        fd = _future_date()
        tz = pytz.UTC
        start = tz.localize(datetime.combine(fd, time(9, 0)))
        end = tz.localize(datetime.combine(fd, time(9, 30)))
        body = {
            'clinic_id': str(clinic.id),
            'treatment_id': str(treatment.id),
            'start_datetime': start.isoformat(),
            'end_datetime': end.isoformat(),
            'patient': {
                'first_name': 'Test',
                'last_name': 'Hardening',
                'email': 'hardening@example.com',
            },
            'token': _make_token(clinic.id),
        }
        if practitioner:
            body['practitioner_id'] = str(practitioner.id)
        return body

    # ── Token tests ─────────────────────────────────────────

    def test_invalid_signature_rejected(self, api_client, clinic, treatment):
        """Invalid token signature → 403."""
        resp = api_client.get(self.AVAIL_URL, {
            'clinic_id': str(clinic.id),
            'treatment_id': str(treatment.id),
            'date_from': _future_date().isoformat(),
            'date_to': _future_date().isoformat(),
            'token': 'totally-invalid-token',
        })
        assert resp.status_code == 403
        assert resp.json()['error'] == 'Access denied.'

    def test_expired_signature_rejected(
        self, api_client, clinic, treatment, settings,
    ):
        """Expired token → 403."""
        token = _make_token(clinic.id)
        # Set max_age to 0 so any token is immediately expired
        settings.PUBLIC_BOOKING_TOKEN_MAX_AGE = 0
        resp = api_client.get(self.AVAIL_URL, {
            'clinic_id': str(clinic.id),
            'treatment_id': str(treatment.id),
            'date_from': _future_date().isoformat(),
            'date_to': _future_date().isoformat(),
            'token': token,
        })
        assert resp.status_code == 403

    def test_valid_signature_accepted(
        self, api_client, clinic, treatment, practitioner_a, full_setup_a,
    ):
        """Valid token → 200."""
        fd = _future_date()
        resp = api_client.get(self.AVAIL_URL, {
            'clinic_id': str(clinic.id),
            'treatment_id': str(treatment.id),
            'date_from': fd.isoformat(),
            'date_to': fd.isoformat(),
            'practitioner_id': str(practitioner_a.id),
            'token': _make_token(clinic.id),
        })
        assert resp.status_code == 200

    def test_no_token_rejected(self, api_client, clinic, treatment):
        """Missing token → 403."""
        resp = api_client.get(self.AVAIL_URL, {
            'clinic_id': str(clinic.id),
            'treatment_id': str(treatment.id),
            'date_from': _future_date().isoformat(),
            'date_to': _future_date().isoformat(),
        })
        assert resp.status_code == 403

    def test_token_clinic_mismatch(self, api_client, clinic, treatment):
        """Token for different clinic → 403."""
        import uuid
        wrong_token = _make_token(uuid.uuid4())
        resp = api_client.get(self.AVAIL_URL, {
            'clinic_id': str(clinic.id),
            'treatment_id': str(treatment.id),
            'date_from': _future_date().isoformat(),
            'date_to': _future_date().isoformat(),
            'token': wrong_token,
        })
        assert resp.status_code == 403

    # ── Anti-bot tests ──────────────────────────────────────

    def test_antibot_required_in_production(
        self, api_client, clinic, treatment, practitioner_a, full_setup_a,
        legal_entity, settings,
    ):
        """With backend='require' and no captcha_token → 403."""
        settings.PUBLIC_BOOKING_ANTIBOT_BACKEND = 'require'
        payload = self._booking_payload(clinic, treatment, practitioner_a)
        # No captcha_token
        resp = api_client.post(self.CREATE_URL, payload, format='json')
        assert resp.status_code == 403
        assert resp.json()['error'] == 'Verification required.'

    def test_antibot_bypass_in_noop_mode(
        self, api_client, clinic, treatment, practitioner_a, full_setup_a,
        legal_entity, settings,
    ):
        """With backend='noop' and no captcha_token → 201 (bypass)."""
        settings.PUBLIC_BOOKING_ANTIBOT_BACKEND = 'noop'
        payload = self._booking_payload(clinic, treatment, practitioner_a)
        resp = api_client.post(self.CREATE_URL, payload, format='json')
        assert resp.status_code == 201

    def test_antibot_passes_with_token(
        self, api_client, clinic, treatment, practitioner_a, full_setup_a,
        legal_entity, settings,
    ):
        """With backend='require' and valid captcha_token → 201."""
        settings.PUBLIC_BOOKING_ANTIBOT_BACKEND = 'require'
        payload = self._booking_payload(clinic, treatment, practitioner_a)
        payload['captcha_token'] = 'valid-captcha-response'
        resp = api_client.post(self.CREATE_URL, payload, format='json')
        assert resp.status_code == 201

    # ── Dedup normalization tests ───────────────────────────

    def test_dedup_email_normalization(
        self, api_client, clinic, treatment, practitioner_a, full_setup_a,
        legal_entity,
    ):
        """Email with uppercase/spaces is deduped against lowercase stored."""
        Patient.objects.create(
            first_name='Exists', last_name='Already',
            email='hardening@example.com',
            legal_entity=legal_entity,
        )
        before = Patient.unfiltered.count()
        payload = self._booking_payload(clinic, treatment, practitioner_a)
        payload['patient']['email'] = '  Hardening@Example.COM  '
        resp = api_client.post(self.CREATE_URL, payload, format='json')
        assert resp.status_code == 201
        assert Patient.unfiltered.count() == before  # no new patient

    def test_dedup_phone_normalization(
        self, api_client, clinic, treatment, practitioner_a, full_setup_a,
        legal_entity,
    ):
        """Phone with formatting is deduped against normalized stored."""
        Patient.objects.create(
            first_name='Phone', last_name='Match',
            phone='+33612345678',
            legal_entity=legal_entity,
        )
        before = Patient.unfiltered.count()
        payload = self._booking_payload(clinic, treatment, practitioner_a)
        payload['patient'].pop('email', None)
        payload['patient']['phone'] = '+33 6 12 34 56 78'
        resp = api_client.post(self.CREATE_URL, payload, format='json')
        assert resp.status_code == 201
        assert Patient.unfiltered.count() == before  # no new patient

    # ── Availability hardening tests ────────────────────────

    def test_availability_date_range_cap(self, api_client, clinic, treatment):
        """Date range > 7 days is rejected."""
        fd = _future_date()
        resp = api_client.get(self.AVAIL_URL, {
            'clinic_id': str(clinic.id),
            'treatment_id': str(treatment.id),
            'date_from': fd.isoformat(),
            'date_to': (fd + timedelta(days=8)).isoformat(),
            'token': _make_token(clinic.id),
        })
        assert resp.status_code == 400

    def test_availability_slot_cap(
        self, api_client, clinic, treatment, practitioner_a, full_setup_a,
    ):
        """Slot count is capped at PUBLIC_BOOKING_MAX_SLOTS."""
        fd = _future_date()
        resp = api_client.get(self.AVAIL_URL, {
            'clinic_id': str(clinic.id),
            'treatment_id': str(treatment.id),
            'date_from': fd.isoformat(),
            'date_to': (fd + timedelta(days=2)).isoformat(),
            'practitioner_id': str(practitioner_a.id),
            'token': _make_token(clinic.id),
        })
        assert resp.status_code == 200
        # 3 days × 20 slots (08:00-18:00, 30-min) = 60, cap at 50
        assert len(resp.json()['slots']) <= 50

    # ── Error response hardening tests ──────────────────────

    def test_error_no_internal_leak_clinic(self, api_client, treatment):
        """404 for nonexistent clinic doesn't leak 'Clinic' in error."""
        import uuid
        fake_cid = uuid.uuid4()
        resp = api_client.get(self.AVAIL_URL, {
            'clinic_id': str(fake_cid),
            'treatment_id': str(treatment.id),
            'date_from': _future_date().isoformat(),
            'date_to': _future_date().isoformat(),
            'token': _make_token(fake_cid),
        })
        assert resp.status_code == 404
        error_msg = resp.json()['error']
        assert 'Clinic' not in error_msg
        assert 'not found' not in error_msg.lower()
        assert error_msg == 'The requested resource is not available.'

    def test_error_no_internal_leak_422(
        self, api_client, clinic, treatment, practitioner_a, schedule_a,
        legal_entity,
    ):
        """422 for capability mismatch doesn't leak specifics."""
        payload = self._booking_payload(clinic, treatment, practitioner_a)
        resp = api_client.post(self.CREATE_URL, payload, format='json')
        assert resp.status_code == 422
        error_msg = resp.json()['error']
        assert 'Practitioner' not in error_msg
        assert 'treatment' not in error_msg.lower()
        assert error_msg == 'The requested configuration is not available.'

    def test_409_no_details_field(
        self, api_client, clinic, treatment, practitioner_a, full_setup_a,
        legal_entity,
    ):
        """409 conflict response has no 'details' key."""
        payload = self._booking_payload(clinic, treatment, practitioner_a)
        r1 = api_client.post(self.CREATE_URL, payload, format='json')
        assert r1.status_code == 201
        # Second booking same slot
        payload['patient']['email'] = 'other-hardening@example.com'
        payload['token'] = _make_token(clinic.id)
        r2 = api_client.post(self.CREATE_URL, payload, format='json')
        assert r2.status_code == 409
        assert 'details' not in r2.json()
