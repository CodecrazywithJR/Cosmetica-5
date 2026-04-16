"""
Public Booking API — Serializers

Dedicated serializers for the public booking endpoints.
These intentionally DO NOT reuse internal admin serializers
to avoid leaking internal-only fields.
"""
from django.conf import settings
from rest_framework import serializers


class PublicAvailabilityQuerySerializer(serializers.Serializer):
    """Validate query params for GET /public/booking/availability/."""

    clinic_id = serializers.UUIDField()
    treatment_id = serializers.UUIDField()
    date_from = serializers.DateField(input_formats=['%Y-%m-%d'])
    date_to = serializers.DateField(input_formats=['%Y-%m-%d'])
    practitioner_id = serializers.UUIDField(required=False)

    def validate(self, data):
        if data['date_from'] > data['date_to']:
            raise serializers.ValidationError(
                {'date_to': 'date_to must be on or after date_from.'}
            )
        # Limit range to prevent enumeration abuse
        delta = (data['date_to'] - data['date_from']).days
        max_days = getattr(settings, 'PUBLIC_BOOKING_MAX_DATE_RANGE_DAYS', 7)
        if delta > max_days:
            raise serializers.ValidationError(
                {'date_to': f'Date range must not exceed {max_days} days.'}
            )
        return data


class PublicAvailabilitySlotSerializer(serializers.Serializer):
    """Output serializer for a single availability slot."""

    start_datetime = serializers.DateTimeField()
    end_datetime = serializers.DateTimeField()
    practitioner_id = serializers.UUIDField()
    practitioner_display_name = serializers.CharField()
    clinic_id = serializers.UUIDField()
    treatment_id = serializers.UUIDField()


class PublicPatientPayloadSerializer(serializers.Serializer):
    """Patient data within a public booking request."""

    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    birth_date = serializers.DateField(required=False, input_formats=['%Y-%m-%d'])


class PublicCreateBookingSerializer(serializers.Serializer):
    """Validate POST body for /public/booking/create/."""

    clinic_id = serializers.UUIDField()
    treatment_id = serializers.UUIDField()
    start_datetime = serializers.DateTimeField()
    end_datetime = serializers.DateTimeField()
    practitioner_id = serializers.UUIDField(required=False)
    patient = PublicPatientPayloadSerializer()
    notes = serializers.CharField(required=False, allow_blank=True, max_length=1000)

    def validate(self, data):
        if data['end_datetime'] <= data['start_datetime']:
            raise serializers.ValidationError(
                {'end_datetime': 'end_datetime must be after start_datetime.'}
            )
        return data


class PublicBookingResultSerializer(serializers.Serializer):
    """Output serializer for a successful booking."""

    appointment_id = serializers.UUIDField()
    patient_id = serializers.UUIDField()
    practitioner_id = serializers.UUIDField()
    clinic_id = serializers.UUIDField()
    status = serializers.CharField()
    start_datetime = serializers.DateTimeField()
    end_datetime = serializers.DateTimeField()
