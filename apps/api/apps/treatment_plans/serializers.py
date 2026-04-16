"""
TreatmentPlan serializers — read-only list + detail.
"""
from rest_framework import serializers

from apps.treatment_plans.models import TreatmentPlan


class TreatmentPlanListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for the list endpoint.

    Exposes stored fields plus two computed helpers:
      - remaining_sessions  (planned − completed, clamped to 0)
      - progress_percent    (completed / planned × 100, 0 when planned == 0)
    """

    remaining_sessions = serializers.SerializerMethodField()
    progress_percent = serializers.SerializerMethodField()
    practitioner_name = serializers.SerializerMethodField()

    class Meta:
        model = TreatmentPlan
        fields = [
            'id',
            'patient',
            'practitioner',
            'practitioner_name',
            'proposal',
            'sale',
            'package_name',
            'status',
            'planned_sessions',
            'completed_sessions',
            'remaining_sessions',
            'progress_percent',
            'total_price_snapshot',
            'currency',
            'activated_at',
            'completed_at',
            'cancelled_at',
            'created_at',
        ]
        read_only_fields = fields

    # -- computed -----------------------------------------------------------

    def get_remaining_sessions(self, obj: TreatmentPlan) -> int:
        return max(obj.planned_sessions - obj.completed_sessions, 0)

    def get_progress_percent(self, obj: TreatmentPlan) -> float:
        if obj.planned_sessions == 0:
            return 0.0
        return round(obj.completed_sessions / obj.planned_sessions * 100, 1)

    def get_practitioner_name(self, obj: TreatmentPlan) -> 'str | None':
        if obj.practitioner:
            return obj.practitioner.display_name
        return None
