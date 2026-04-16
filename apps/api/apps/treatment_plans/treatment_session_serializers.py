"""
TreatmentSession serializers.

Serializers:
  - TreatmentSessionListSerializer   (list / retrieve — read-only)
  - TreatmentSessionWriteSerializer   (PATCH notes in draft)
"""
from rest_framework import serializers

from apps.treatment_plans.treatment_session_models import TreatmentSession


class TreatmentSessionListSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for list/retrieve endpoints.

    Includes computed ``practitioner_name`` and ``patient`` (resolved
    through the treatment_plan FK) so the frontend can display sessions
    without extra requests.
    """

    practitioner_name = serializers.SerializerMethodField()
    patient = serializers.SerializerMethodField()
    package_name = serializers.SerializerMethodField()

    class Meta:
        model = TreatmentSession
        fields = [
            'id',
            'treatment_plan',
            'appointment',
            'practitioner',
            'practitioner_name',
            'patient',
            'package_name',
            'status',
            'notes',
            'performed_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    # -- computed -----------------------------------------------------------

    def get_practitioner_name(self, obj: TreatmentSession) -> 'str | None':
        if obj.practitioner:
            return obj.practitioner.display_name
        return None

    def get_patient(self, obj: TreatmentSession) -> str:
        return str(obj.treatment_plan.patient_id)

    def get_package_name(self, obj: TreatmentSession) -> str:
        return obj.treatment_plan.package_name


class TreatmentSessionWriteSerializer(serializers.ModelSerializer):
    """
    Write serializer for PATCH (draft only).

    Only ``notes`` and ``performed_at`` are writable.
    """

    class Meta:
        model = TreatmentSession
        fields = ['notes', 'performed_at']
