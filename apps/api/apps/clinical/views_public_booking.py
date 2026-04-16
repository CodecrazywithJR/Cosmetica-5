"""
Public Booking API — Views (Hardened)

Two public endpoints:

1. GET  /public/booking/availability/  — available slots
2. POST /public/booking/create/        — create a booking

Security layers:
  • Signed token required (PublicBookingTokenService) — ensures requests
    originate from trusted channels (clinic embed, landing page).
  • Anti-bot verification (AntiBotService) — pluggable CAPTCHA on booking
    creation.  Defaults to noop; set PUBLIC_BOOKING_ANTIBOT_BACKEND='require'.
  • Per-endpoint throttle scopes — availability is moderate; creation is strict.
  • Hardened error responses — generic messages to avoid leaking internals.
  • Privacy-safe audit logging — no PII in payloads.
  • Availability slot cap — limits enumeration volume.

Booking modes (unchanged):
  Mode A — practitioner_id provided.
  Mode B — practitioner_id omitted → auto-assign.

Core appointment engine reuse (unchanged):
  • AvailabilityService for slot calculation
  • transaction.atomic() + select_for_update() for serialised booking
  • PostgreSQL ExclusionConstraint (prevent_practitioner_overbooking)

Data exposure (documented):
  • Availability response exposes: practitioner_id, practitioner_display_name,
    clinic_id, treatment_id, start/end datetimes.
  • practitioner_display_name is a public-facing doctor name, kept in both
    Mode A and Mode B as required by the current API contract.
"""
import logging
from datetime import datetime, timedelta

import pytz
from django.conf import settings as django_settings
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.db.utils import OperationalError
from django.utils import timezone as django_timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.clinical.models import (
    Appointment,
    AppointmentSourceChoices,
    Patient,
    PractitionerTreatment,
    Treatment,
)
from apps.clinical.services import AvailabilityService
from apps.clinical.serializers_public_booking import (
    PublicAvailabilityQuerySerializer,
    PublicAvailabilitySlotSerializer,
    PublicBookingResultSerializer,
    PublicCreateBookingSerializer,
)
from apps.clinical.services_public_booking import (
    AntiBotService,
    PublicBookingTokenService,
    normalize_email_for_dedup,
    normalize_phone_for_dedup,
)
from apps.core.models import Clinic
from apps.authz.models import Practitioner
from apps.ops.models import AuditEventType
from apps.ops.services import log_event

logger = logging.getLogger(__name__)
sec_log = logging.getLogger('apps.clinical.security')


# ── Helpers ─────────────────────────────────────────────────────────

def _get_client_ip(request):
    """Extract client IP, respecting X-Forwarded-For."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def _extract_token(request):
    """Extract booking token from header, query param, or body."""
    return (
        request.META.get('HTTP_X_BOOKING_TOKEN')
        or request.query_params.get('token')
        or request.data.get('token')
        or ''
    )


def _verify_token_signature(request):
    """Verify token exists and has valid signature + expiry (no cross-check)."""
    client_ip = _get_client_ip(request)
    raw_token = _extract_token(request)
    if not raw_token:
        sec_log.warning('booking_no_token ip=%s', client_ip)
        return None, Response(
            {'error': 'Access denied.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    payload, error = PublicBookingTokenService.verify(raw_token)
    if error:
        sec_log.warning('booking_token_%s ip=%s', error, client_ip)
        return None, Response(
            {'error': 'Access denied.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    return payload, None


def _cross_check_token(request, token_payload, *, clinic_id,
                       practitioner_id=None, treatment_id=None):
    """Verify token payload matches request params. Returns Response on failure."""
    mismatch = PublicBookingTokenService.validate_request(
        token_payload, clinic_id=clinic_id,
        practitioner_id=practitioner_id, treatment_id=treatment_id,
    )
    if mismatch:
        sec_log.warning('booking_token_%s ip=%s', mismatch,
                        _get_client_ip(request))
        return Response(
            {'error': 'Access denied.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


# ── Throttle classes ────────────────────────────────────────────────

class AvailAnonThrottle(AnonRateThrottle):
    scope = 'public_avail'


class AvailBurstThrottle(AnonRateThrottle):
    scope = 'public_avail_burst'


class CreateAnonThrottle(AnonRateThrottle):
    scope = 'public_create'


class CreateBurstThrottle(AnonRateThrottle):
    scope = 'public_create_burst'


# ── Availability ────────────────────────────────────────────────────
class PublicAvailabilityView(APIView):
    """
    GET /public/booking/availability/

    Return available slots for a clinic + treatment + date range.
    Optionally filtered by practitioner_id (Mode A).
    """
    permission_classes = []
    authentication_classes = []
    throttle_classes = [AvailAnonThrottle, AvailBurstThrottle]

    def get(self, request):
        # ── Token signature verification (fast reject) ──────
        token_payload, token_err = _verify_token_signature(request)
        if token_err:
            return token_err

        serializer = PublicAvailabilityQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # ── Token cross-check ───────────────────────────────
        cross_err = _cross_check_token(
            request, token_payload,
            clinic_id=data['clinic_id'],
            practitioner_id=data.get('practitioner_id'),
            treatment_id=data['treatment_id'],
        )
        if cross_err:
            return cross_err

        clinic_id = str(data['clinic_id'])
        treatment_id = str(data['treatment_id'])
        date_from = data['date_from'].isoformat()
        date_to = data['date_to'].isoformat()
        practitioner_id = data.get('practitioner_id')

        # ── Validate clinic exists ──────────────────────────────
        try:
            clinic = Clinic.unfiltered.get(id=clinic_id, is_active=True)
        except Clinic.DoesNotExist:
            return Response(
                {'error': 'The requested resource is not available.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Validate treatment exists (scoped to same legal entity) ─
        try:
            treatment = Treatment.unfiltered.get(
                id=treatment_id,
                is_active=True,
                legal_entity=clinic.legal_entity,
            )
        except Treatment.DoesNotExist:
            return Response(
                {'error': 'The requested resource is not available.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Resolve practitioner list ───────────────────────────
        if practitioner_id:
            practitioners = self._resolve_single_practitioner(
                practitioner_id, clinic, treatment,
            )
            if isinstance(practitioners, Response):
                return practitioners  # error response
        else:
            practitioners = self._resolve_eligible_practitioners(
                clinic, treatment,
            )

        if not practitioners:
            return Response({
                'clinic_id': clinic_id,
                'treatment_id': treatment_id,
                'date_from': date_from,
                'date_to': date_to,
                'slots': [],
            })

        # ── Collect slots across practitioners ──────────────────
        all_slots = []
        slot_duration = treatment.duration_minutes

        for pract in practitioners:
            avail = AvailabilityService.calculate_availability(
                practitioner_id=str(pract.id),
                clinic_id=clinic_id,
                date_from=date_from,
                date_to=date_to,
                treatment_id=treatment_id,
                slot_duration=slot_duration,
                timezone_str=clinic.timezone or 'UTC',
            )
            tz = pytz.timezone(clinic.timezone or 'UTC')
            for day in avail.get('availability', []):
                date_str = day['date']
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                for slot in day.get('slots', []):
                    start_t = datetime.strptime(slot['start'], '%H:%M').time()
                    end_t = datetime.strptime(slot['end'], '%H:%M').time()
                    all_slots.append({
                        'start_datetime': tz.localize(
                            datetime.combine(date_obj, start_t)
                        ),
                        'end_datetime': tz.localize(
                            datetime.combine(date_obj, end_t)
                        ),
                        'practitioner_id': pract.id,
                        'practitioner_display_name': pract.display_name,
                        'clinic_id': clinic.id,
                        'treatment_id': treatment.id,
                    })

        # Sort by datetime, then practitioner
        all_slots.sort(key=lambda s: (s['start_datetime'], str(s['practitioner_id'])))

        # Cap slots to limit enumeration
        max_slots = getattr(django_settings, 'PUBLIC_BOOKING_MAX_SLOTS', 50)
        all_slots = all_slots[:max_slots]

        out = PublicAvailabilitySlotSerializer(all_slots, many=True)
        return Response({
            'clinic_id': clinic_id,
            'treatment_id': treatment_id,
            'date_from': date_from,
            'date_to': date_to,
            'slots': out.data,
        })

    # ── helpers ─────────────────────────────────────────────────
    @staticmethod
    def _resolve_single_practitioner(practitioner_id, clinic, treatment):
        """Mode A — validate the specified practitioner."""
        try:
            practitioner = Practitioner.objects.get(
                id=practitioner_id, is_active=True,
            )
        except Practitioner.DoesNotExist:
            return Response(
                {'error': 'The requested resource is not available.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Capability check
        if not PractitionerTreatment.objects.filter(
            practitioner=practitioner,
            treatment=treatment,
            is_active=True,
        ).exists():
            return Response(
                {'error': 'The requested configuration is not available.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # Schedule-at-clinic check
        from apps.clinical.models import PractitionerSchedule
        if not PractitionerSchedule.objects.filter(
            practitioner=practitioner,
            clinic=clinic,
            is_active=True,
        ).exists():
            return Response(
                {'error': 'The requested configuration is not available.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return [practitioner]

    @staticmethod
    def _resolve_eligible_practitioners(clinic, treatment):
        """Mode B — find all capable practitioners at the clinic."""
        from apps.clinical.models import PractitionerSchedule

        # Practitioners scheduled at this clinic
        scheduled_ids = (
            PractitionerSchedule.objects
            .filter(clinic=clinic, is_active=True)
            .values_list('practitioner_id', flat=True)
            .distinct()
        )

        # Intersect with capability
        capable_ids = (
            PractitionerTreatment.objects
            .filter(
                treatment=treatment,
                is_active=True,
                practitioner_id__in=scheduled_ids,
            )
            .values_list('practitioner_id', flat=True)
            .distinct()
        )

        return list(
            Practitioner.objects.filter(id__in=capable_ids, is_active=True)
            .order_by('display_name')
        )


# ── Create Booking ──────────────────────────────────────────────────
class PublicCreateBookingView(APIView):
    """
    POST /public/booking/create/

    Create a booking through the public API.
    Supports both practitioner-provided (Mode A) and
    auto-assignment (Mode B) flows.

    Appointments are created as:
        status  = scheduled
        source  = public_api
    """
    permission_classes = []
    authentication_classes = []
    throttle_classes = [CreateAnonThrottle, CreateBurstThrottle]

    def post(self, request):
        client_ip = _get_client_ip(request)

        # ── Token signature verification (fast reject) ──────
        token_payload, token_err = _verify_token_signature(request)
        if token_err:
            return token_err

        # ── Anti-bot verification ────────────────────────
        captcha_token = request.data.get('captcha_token', '')
        if not AntiBotService.verify(captcha_token, client_ip):
            sec_log.warning('booking_antibot_fail ip=%s', client_ip)
            return Response(
                {'error': 'Verification required.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = PublicCreateBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # ── Token cross-check ───────────────────────────────
        cross_err = _cross_check_token(
            request, token_payload,
            clinic_id=data['clinic_id'],
            practitioner_id=data.get('practitioner_id'),
            treatment_id=data['treatment_id'],
        )
        if cross_err:
            return cross_err

        clinic_id = str(data['clinic_id'])
        treatment_id = str(data['treatment_id'])
        start_dt = data['start_datetime']
        end_dt = data['end_datetime']
        practitioner_id = data.get('practitioner_id')
        patient_payload = data['patient']
        notes = data.get('notes', '')

        # ── 1. Validate clinic ──────────────────────────────────
        try:
            clinic = Clinic.unfiltered.get(id=clinic_id, is_active=True)
        except Clinic.DoesNotExist:
            return Response(
                {'error': 'The requested resource is not available.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        legal_entity = clinic.legal_entity

        # ── 2. Validate treatment ───────────────────────────────
        try:
            treatment = Treatment.unfiltered.get(
                id=treatment_id,
                is_active=True,
                legal_entity=legal_entity,
            )
        except Treatment.DoesNotExist:
            return Response(
                {'error': 'The requested resource is not available.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── 3. Reject slots in the past ─────────────────────────
        now = django_timezone.now()
        if start_dt <= now:
            return Response(
                {'error': 'Invalid request.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── 4. Resolve practitioner ─────────────────────────────
        if practitioner_id:
            practitioner = self._resolve_provided_practitioner(
                practitioner_id, clinic, treatment,
            )
            if isinstance(practitioner, Response):
                return practitioner
        else:
            practitioner = self._auto_assign_practitioner(
                clinic, treatment, start_dt, end_dt,
            )
            if isinstance(practitioner, Response):
                return practitioner

        # ── 5. Resolve / create patient ─────────────────────────
        patient, patient_created = self._resolve_or_create_patient(
            patient_payload, legal_entity,
        )

        # ── 6. Transactional booking ────────────────────────────
        slot_date = start_dt.strftime('%Y-%m-%d')
        slot_start_str = start_dt.strftime('%H:%M')
        slot_end_str = end_dt.strftime('%H:%M')

        try:
            with transaction.atomic():
                # Lock practitioner's active appointments
                Appointment.unfiltered.select_for_update().filter(
                    practitioner_id=practitioner.id,
                    status__in=Appointment._ACTIVE_STATUSES,
                    is_deleted=False,
                ).exists()

                # Availability recheck inside transaction
                avail = AvailabilityService.calculate_availability(
                    practitioner_id=str(practitioner.id),
                    clinic_id=clinic_id,
                    date_from=slot_date,
                    date_to=slot_date,
                    treatment_id=treatment_id,
                    slot_duration=treatment.duration_minutes,
                    timezone_str=clinic.timezone or 'UTC',
                )

                day = next(
                    (d for d in avail.get('availability', [])
                     if d['date'] == slot_date),
                    None,
                )
                if not day:
                    sec_log.info('booking_409 ip=%s', _get_client_ip(request))
                    return Response(
                        {'error': 'The requested slot is not available.'},
                        status=status.HTTP_409_CONFLICT,
                    )

                slot_found = any(
                    s['start'] == slot_start_str and s['end'] == slot_end_str
                    for s in day.get('slots', [])
                )
                if not slot_found:
                    sec_log.info('booking_409 ip=%s', _get_client_ip(request))
                    return Response(
                        {'error': 'The requested slot is not available.'},
                        status=status.HTTP_409_CONFLICT,
                    )

                # Create appointment
                appointment = Appointment(
                    practitioner=practitioner,
                    patient=patient,
                    clinic=clinic,
                    treatment=treatment,
                    scheduled_start=start_dt,
                    scheduled_end=end_dt,
                    status='scheduled',
                    source=AppointmentSourceChoices.PUBLIC_API,
                    notes=notes,
                    legal_entity=legal_entity,
                )
                appointment.save()

        except (IntegrityError, OperationalError) as exc:
            logger.warning('Overbooking prevented by DB constraint: %s', exc)
            sec_log.warning('booking_overbooking ip=%s', _get_client_ip(request))
            return Response(
                {'error': 'The requested slot is not available.'},
                status=status.HTTP_409_CONFLICT,
            )

        # ── 7. Audit log ────────────────────────────────────────
        log_event(
            user=None,
            legal_entity=legal_entity,
            entity_type='Appointment',
            entity_id=appointment.pk,
            event_type=AuditEventType.APPOINTMENT_CREATED,
            payload={
                'source': 'public_api',
                'practitioner_id': str(practitioner.id),
                'patient_id': str(patient.id),
                'clinic_id': clinic_id,
                'treatment_id': treatment_id,
                'patient_created': patient_created,
            },
        )

        if patient_created:
            log_event(
                user=None,
                legal_entity=legal_entity,
                entity_type='Patient',
                entity_id=patient.pk,
                event_type=AuditEventType.PATIENT_CREATED,
                payload={'source': 'public_api'},
            )

        logger.info(
            'Public booking created: appointment=%s', appointment.pk,
        )

        # ── 8. Response ─────────────────────────────────────────
        result = PublicBookingResultSerializer({
            'appointment_id': appointment.pk,
            'patient_id': patient.pk,
            'practitioner_id': practitioner.id,
            'clinic_id': clinic.id,
            'status': appointment.status,
            'start_datetime': appointment.scheduled_start,
            'end_datetime': appointment.scheduled_end,
        })
        return Response(result.data, status=status.HTTP_201_CREATED)

    # ── helpers ─────────────────────────────────────────────────
    @staticmethod
    def _resolve_provided_practitioner(practitioner_id, clinic, treatment):
        """Mode A — validate practitioner provided by caller."""
        try:
            practitioner = Practitioner.objects.get(
                id=practitioner_id, is_active=True,
            )
        except Practitioner.DoesNotExist:
            return Response(
                {'error': 'The requested resource is not available.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not PractitionerTreatment.objects.filter(
            practitioner=practitioner,
            treatment=treatment,
            is_active=True,
        ).exists():
            return Response(
                {'error': 'The requested configuration is not available.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        from apps.clinical.models import PractitionerSchedule
        if not PractitionerSchedule.objects.filter(
            practitioner=practitioner,
            clinic=clinic,
            is_active=True,
        ).exists():
            return Response(
                {'error': 'The requested configuration is not available.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return practitioner

    @staticmethod
    def _auto_assign_practitioner(clinic, treatment, start_dt, end_dt):
        """
        Mode B — auto-assign first available practitioner.

        Algorithm:
        1. Find practitioners capable of the treatment at the clinic.
        2. For each, check if the requested slot is available.
        3. Return the first match.
        """
        from apps.clinical.models import PractitionerSchedule

        scheduled_ids = (
            PractitionerSchedule.objects
            .filter(clinic=clinic, is_active=True)
            .values_list('practitioner_id', flat=True)
            .distinct()
        )
        capable_ids = (
            PractitionerTreatment.objects
            .filter(
                treatment=treatment,
                is_active=True,
                practitioner_id__in=scheduled_ids,
            )
            .values_list('practitioner_id', flat=True)
            .distinct()
        )
        practitioners = (
            Practitioner.objects
            .filter(id__in=capable_ids, is_active=True)
            .order_by('display_name')
        )

        slot_date = start_dt.strftime('%Y-%m-%d')
        slot_start_str = start_dt.strftime('%H:%M')
        slot_end_str = end_dt.strftime('%H:%M')

        for pract in practitioners:
            avail = AvailabilityService.calculate_availability(
                practitioner_id=str(pract.id),
                clinic_id=str(clinic.id),
                date_from=slot_date,
                date_to=slot_date,
                treatment_id=str(treatment.id),
                slot_duration=treatment.duration_minutes,
                timezone_str=clinic.timezone or 'UTC',
            )
            day = next(
                (d for d in avail.get('availability', [])
                 if d['date'] == slot_date),
                None,
            )
            if not day:
                continue

            slot_found = any(
                s['start'] == slot_start_str and s['end'] == slot_end_str
                for s in day.get('slots', [])
            )
            if slot_found:
                return pract

        return Response(
            {'error': 'The requested slot is not available.'},
            status=status.HTTP_409_CONFLICT,
        )

    @staticmethod
    def _resolve_or_create_patient(payload, legal_entity):
        """
        Lookup or create patient within the legal entity.

        Dedup rules (applied in order):
        1. email — case-insensitive, whitespace-stripped
        2. phone — normalized (digits + leading + only), checked against
           both Patient.phone and Patient.phone_e164
        3. No match → create new patient

        No fuzzy matching.  Trivial formatting differences are handled
        by normalization.  Unrelated patients are never merged.

        Returns (patient, created: bool).
        """
        first_name = payload['first_name'].strip()
        last_name = payload['last_name'].strip()
        email = normalize_email_for_dedup(payload.get('email'))
        phone = normalize_phone_for_dedup(payload.get('phone'))
        birth_date = payload.get('birth_date')

        # Dedup by email (case-insensitive)
        if email:
            existing = Patient.unfiltered.filter(
                legal_entity=legal_entity,
                is_deleted=False,
                email__iexact=email,
            ).first()
            if existing:
                return existing, False

        # Dedup by phone (normalized, checks both phone and phone_e164)
        if phone:
            existing = Patient.unfiltered.filter(
                legal_entity=legal_entity,
                is_deleted=False,
            ).filter(
                Q(phone=phone) | Q(phone_e164=phone)
            ).first()
            if existing:
                return existing, False

        # Create new patient with normalized contact info
        patient = Patient(
            first_name=first_name,
            last_name=last_name,
            full_name_normalized=f'{first_name} {last_name}'.lower(),
            email=email,
            phone=phone,
            phone_e164=phone,
            birth_date=birth_date,
            legal_entity=legal_entity,
        )
        patient.save()
        return patient, True
