"""
TreatmentSession views — list, retrieve, partial_update (draft), complete, cancel.

Endpoints (registered via clinical/urls.py):
  GET    /api/v1/clinical/treatment-sessions/              list
  GET    /api/v1/clinical/treatment-sessions/{id}/          retrieve
  PATCH  /api/v1/clinical/treatment-sessions/{id}/          partial_update (draft only)
  POST   /api/v1/clinical/treatment-sessions/{id}/complete/ complete action
  POST   /api/v1/clinical/treatment-sessions/{id}/cancel/   cancel action

Query params:
  ?patient=<uuid>           filter by patient (via treatment_plan.patient)
  ?treatment_plan=<uuid>    filter by treatment plan

Permissions (IsClinicalStaff):
  Admin / Practitioner → 200
  Reception / Accounting / Marketing → 403
"""
import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.clinical.permissions import IsClinicalStaff
from apps.treatment_plans.models import TreatmentPlan
from apps.treatment_plans.treatment_session_models import (
    TreatmentSession,
    TreatmentSessionStatusChoices,
)
from apps.treatment_plans.treatment_session_serializers import (
    TreatmentSessionListSerializer,
    TreatmentSessionWriteSerializer,
)
from apps.core.audit import log_clinical_access
from apps.clinical.audit_access_log import ClinicalAccessAction
from apps.core.tenant import TenantQuerySetMixin
from apps.ops.services import log_event
from apps.ops.models import AuditEventType

logger = logging.getLogger(__name__)


class TreatmentSessionViewSet(
    TenantQuerySetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    TreatmentSession endpoints.

    * list / retrieve — read-only
    * partial_update  — PATCH notes/performed_at while draft
    * complete        — POST action: draft → completed
    * cancel          — POST action: draft → cancelled
    """

    permission_classes = [IsClinicalStaff]
    http_method_names = ['get', 'patch', 'post', 'head', 'options']

    def get_queryset(self):
        qs = TreatmentSession.objects.select_related(
            'treatment_plan',
            'treatment_plan__patient',
            'appointment',
            'practitioner',
        )
        # TenantManager (via TenantModel) already auto-filters by the active
        # thread-local tenant set in TenantQuerySetMixin.initial().
        # No manual legal_entity filter needed here.

        # ?patient=<uuid>
        patient_id = self.request.query_params.get('patient')
        if patient_id:
            qs = qs.filter(treatment_plan__patient_id=patient_id)

        # ?treatment_plan=<uuid>
        plan_id = self.request.query_params.get('treatment_plan')
        if plan_id:
            qs = qs.filter(treatment_plan_id=plan_id)

        return qs.order_by('-created_at')

    def get_serializer_class(self):
        if self.action in ('partial_update', 'update'):
            return TreatmentSessionWriteSerializer
        return TreatmentSessionListSerializer

    # ── PATCH — only in draft ──────────────────────────────────────────

    def update(self, request, *args, **kwargs):
        """PATCH /treatment-sessions/{id}/ — only allowed while draft."""
        kwargs['partial'] = True  # enforce partial
        instance = self.get_object()

        if instance.status != TreatmentSessionStatusChoices.DRAFT:
            return Response(
                {'error': f"Cannot modify session in '{instance.status}' state. Only DRAFT sessions are editable."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        log_clinical_access(
            request,
            action=ClinicalAccessAction.UPDATE_TREATMENT_SESSION,
            patient=instance.treatment_plan.patient,
            resource=instance,
        )

        return Response(
            TreatmentSessionListSerializer(instance).data,
            status=status.HTTP_200_OK,
        )

    # ── Complete action ────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        """
        POST /treatment-sessions/{id}/complete/

        Transition draft → completed.
        Auto-completes TreatmentPlan if all sessions done.
        All within transaction.atomic() + select_for_update().
        """
        try:
            with transaction.atomic():
                # Lock session row
                session = (
                    TreatmentSession.objects
                    .select_for_update()
                    .select_related('treatment_plan')
                    .get(pk=pk)
                )

                if session.status != TreatmentSessionStatusChoices.DRAFT:
                    return Response(
                        {'error': f"Cannot complete session in '{session.status}' state. Only DRAFT sessions can be completed."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Lock treatment plan row
                plan = (
                    TreatmentPlan.objects
                    .select_for_update()
                    .get(pk=session.treatment_plan_id)
                )

                from apps.treatment_plans.models import TreatmentPlanStatusChoices

                if plan.status != TreatmentPlanStatusChoices.ACTIVE:
                    return Response(
                        {'error': f"Cannot complete session: treatment plan is '{plan.status}', must be 'active'."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Count completed sessions (lock session rows to prevent race)
                completed_count = (
                    TreatmentSession.objects
                    .select_for_update()
                    .filter(
                        treatment_plan=plan,
                        status=TreatmentSessionStatusChoices.COMPLETED,
                    )
                    .count()
                )

                if completed_count >= plan.planned_sessions:
                    return Response(
                        {'error': 'Cannot complete session: all planned sessions already completed.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Complete the session via formal state machine
                session.complete()

                # Delegate plan accounting to formal state machine.
                # record_session_completed() increments completed_sessions
                # and auto-completes the plan when threshold is reached.
                plan.record_session_completed()

                # Re-fetch for serialization
                session.refresh_from_db()
                log_clinical_access(
                    request,
                    action=ClinicalAccessAction.COMPLETE_TREATMENT_SESSION,
                    patient=plan.patient,
                    resource=session,
                )
                log_event(
                    user=request.user,
                    legal_entity=session.legal_entity,
                    entity_type='TreatmentSession',
                    entity_id=session.pk,
                    event_type=AuditEventType.TREATMENT_SESSION_COMPLETED,
                    payload={
                        'treatment_plan_id': str(plan.id),
                        'completed_sessions': plan.completed_sessions,
                        'planned_sessions': plan.planned_sessions,
                    },
                )
                return Response(
                    TreatmentSessionListSerializer(session).data,
                    status=status.HTTP_200_OK,
                )

        except TreatmentSession.DoesNotExist:
            return Response(
                {'error': 'Treatment session not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoValidationError as e:
            return Response(
                {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # ── Cancel action ──────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """
        POST /treatment-sessions/{id}/cancel/

        Transition draft → cancelled.  Terminal.
        """
        try:
            with transaction.atomic():
                session = (
                    TreatmentSession.objects
                    .select_for_update()
                    .get(pk=pk)
                )

                if session.status != TreatmentSessionStatusChoices.DRAFT:
                    return Response(
                        {'error': f"Cannot cancel session in '{session.status}' state. Only DRAFT sessions can be cancelled."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                session.cancel()
                session.refresh_from_db()

                return Response(
                    TreatmentSessionListSerializer(session).data,
                    status=status.HTTP_200_OK,
                )

        except TreatmentSession.DoesNotExist:
            return Response(
                {'error': 'Treatment session not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except DjangoValidationError as e:
            return Response(
                {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
