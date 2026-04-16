"""
TreatmentPlan views — read-only API.

Endpoints:
  GET /api/v1/clinical/treatment-plans/          list  (paginated, filterable)
  GET /api/v1/clinical/treatment-plans/{id}/      detail

Query params:
  ?patient={uuid}          filter by patient
  ?status=draft|active|completed|cancelled   filter by status

Permissions (IsClinicalStaff):
  Admin / Practitioner → 200
  Reception / Accounting / Marketing → 403
"""
from rest_framework import viewsets

from apps.clinical.permissions import IsClinicalStaff
from apps.treatment_plans.models import TreatmentPlan
from apps.treatment_plans.serializers import TreatmentPlanListSerializer
from apps.core.tenant import TenantQuerySetMixin


class TreatmentPlanViewSet(TenantQuerySetMixin, viewsets.ReadOnlyModelViewSet):
    """Read-only viewset for TreatmentPlan resources."""

    permission_classes = [IsClinicalStaff]
    serializer_class = TreatmentPlanListSerializer

    def get_queryset(self):
        qs = TreatmentPlan.objects.select_related(
            'patient',
            'practitioner',
            'proposal',
            'sale',
        )

        # ?patient=<uuid>
        patient_id = self.request.query_params.get('patient')
        if patient_id:
            qs = qs.filter(patient_id=patient_id)

        # ?status=<choice>
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)

        return qs.order_by('-created_at')
