"""
Clinical viewsets for Patient and PatientGuardian.
Based on API_CONTRACTS.md PAC section.
"""
import logging
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Exists, OuterRef
from django.db import transaction, IntegrityError, OperationalError
from apps.authz.models import RoleChoices
from apps.clinical.models import (
    Patient,
    PatientGuardian,
    PatientInsurance,
    Encounter,
    EncounterStatusChoices,
    Appointment,
    Consent,
    ClinicalPhoto,
    Treatment,
    EncounterTreatment,
    PractitionerBlock,
)
from apps.proposals.models import Proposal
from apps.clinical.serializers import (
    PatientListSerializer,
    PatientDetailSerializer,
    PatientGuardianSerializer,
    PatientInsuranceSerializer,
    AppointmentListSerializer,
    AppointmentDetailSerializer,
    AppointmentWriteSerializer,
    EncounterListSerializer,
    EncounterDetailSerializer,
    EncounterWriteSerializer,
    TreatmentSerializer,
    CalendarEventSerializer,
)
from apps.proposals.serializers import (
    ProposalListSerializer,
    ProposalDetailSerializer,
    CreateSaleFromProposalSerializer,
)
from apps.clinical.permissions import (
    PatientPermission,
    GuardianPermission,
    AppointmentPermission,
    TreatmentPermission,
    EncounterPermission,
)
from apps.proposals.permissions import ProposalPermission
from apps.core.audit import log_clinical_access
from apps.clinical.audit_access_log import ClinicalAccessAction
from apps.core.tenant import TenantQuerySetMixin
from apps.ops.services import log_event
from apps.ops.models import AuditEventType

logger = logging.getLogger(__name__)

ERROR_MERGE_FAILED = 'No se puede realizar el merge'
HINT_REQUIRED_UUID = 'Required (UUID)'


def _parse_occurred_at(raw_value):
    """Parse occurred_at from request data. Returns (datetime, None) or (None, Response)."""
    from django.utils import timezone
    from django.utils.dateparse import parse_datetime
    if not raw_value:
        return timezone.now(), None
    if isinstance(raw_value, str):
        parsed = parse_datetime(raw_value)
        if not parsed:
            return None, Response(
                {'error': 'occurred_at debe tener formato ISO 8601 válido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return parsed, None
    return raw_value, None


def _validate_appointment_for_session(appointment):
    """Validate appointment state for starting a treatment session. Returns Response on error, None on success."""
    if appointment.is_deleted:
        return Response(
            {'error': 'Cannot start session on a deleted appointment.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if appointment.status != 'checked_in':
        return Response(
            {'error': f"Appointment status must be 'checked_in', got '{appointment.status}'."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not appointment.practitioner_id:
        return Response(
            {'error': 'Appointment must have a practitioner to start a treatment session.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return None


def _validate_plan_for_session(plan, appointment, user_le):
    """Validate treatment plan for starting a session. Returns Response on error, None on success."""
    from apps.treatment_plans.models import TreatmentPlanStatusChoices
    if plan.status != TreatmentPlanStatusChoices.ACTIVE:
        return Response(
            {'error': f"Treatment plan must be 'active', got '{plan.status}'."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if plan.patient_id != appointment.patient_id:
        return Response(
            {'error': 'Treatment plan does not belong to the same patient as the appointment.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if user_le and plan.legal_entity_id and plan.legal_entity_id != user_le:
        return Response(
            {'error': 'Cross-tenant access denied.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


def _check_calendar_rbac(request, practitioner_id):
    """Check calendar RBAC: Admin/Reception=any, Practitioner=own only, Marketing/Accounting=403."""
    from apps.authz.models import Practitioner
    user_roles = set(
        request.user.user_roles.values_list('role__name', flat=True)
    )
    if RoleChoices.MARKETING in user_roles or RoleChoices.ACCOUNTING in user_roles:
        raise PermissionDenied("You don't have permission to view calendars")
    is_admin = RoleChoices.ADMIN in user_roles
    is_reception = RoleChoices.RECEPTION in user_roles
    is_practitioner = RoleChoices.PRACTITIONER in user_roles
    if not (is_admin or is_reception or is_practitioner):
        raise PermissionDenied("You don't have permission to view calendars")
    if is_practitioner and not (is_admin or is_reception):
        try:
            user_practitioner = Practitioner.objects.get(user=request.user)
            if str(user_practitioner.id) != str(practitioner_id):
                raise PermissionDenied("You can only view your own calendar")
        except Practitioner.DoesNotExist:
            raise PermissionDenied("You are not registered as a practitioner")


def _parse_date_range(request):
    """Parse and validate date_from/date_to query params. Returns (date_from, date_to, None) or (None, None, Response)."""
    from datetime import datetime as _dt
    date_from_str = request.query_params.get('date_from')
    date_to_str = request.query_params.get('date_to')
    if not date_from_str or not date_to_str:
        return None, None, Response(
            {'error': 'date_from and date_to are required (format: YYYY-MM-DD)'},
            status=status.HTTP_400_BAD_REQUEST
        )
    try:
        date_from = _dt.strptime(date_from_str, '%Y-%m-%d').date()
        date_to = _dt.strptime(date_to_str, '%Y-%m-%d').date()
    except ValueError:
        return None, None, Response(
            {'error': 'Invalid date format. Use YYYY-MM-DD'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if date_from > date_to:
        return None, None, Response(
            {'error': 'date_from cannot be after date_to'},
            status=status.HTTP_400_BAD_REQUEST
        )
    return date_from, date_to, None


def _validate_availability_params(clinic_id_str, date_from_str, date_to_str):
    """Validate clinic existence and date format for availability endpoints. Returns Response on error, None on success."""
    from apps.core.models import Clinic
    from datetime import datetime as _dt
    try:
        Clinic.objects.get(id=clinic_id_str)
    except Clinic.DoesNotExist:
        return Response({
            'error': 'Clinic not found',
            'details': f'No clinic with ID {clinic_id_str}'
        }, status=status.HTTP_404_NOT_FOUND)
    try:
        _dt.strptime(date_from_str, "%Y-%m-%d")
        _dt.strptime(date_to_str, "%Y-%m-%d")
    except ValueError:
        return Response({
            'error': 'Invalid date format',
            'details': 'Use YYYY-MM-DD format'
        }, status=status.HTTP_400_BAD_REQUEST)
    return None


def _parse_booking_slot(date_str, start_str, end_str):
    """Parse booking slot date/times. Returns (slot_start_dt, slot_end_dt) or Response on error."""
    from datetime import datetime as _dt
    import pytz
    try:
        date_obj = _dt.strptime(date_str, "%Y-%m-%d").date()
        start_time = _dt.strptime(start_str, "%H:%M").time()
        end_time = _dt.strptime(end_str, "%H:%M").time()
    except ValueError:
        return Response({
            'error': 'Invalid date/time format',
            'details': 'Use YYYY-MM-DD for date, HH:MM for times'
        }, status=status.HTTP_400_BAD_REQUEST)
    if start_time >= end_time:
        return Response({
            'error': 'Invalid time range',
            'details': 'start must be before end'
        }, status=status.HTTP_400_BAD_REQUEST)
    tz = pytz.UTC
    return (
        tz.localize(_dt.combine(date_obj, start_time)),
        tz.localize(_dt.combine(date_obj, end_time)),
    )


def _check_slot_available(availability_service, practitioner_id, clinic_id,
                           date_str, start_str, end_str, treatment_id, slot_duration):
    """Check if a booking slot is available. Returns Response on error, None if available."""
    availability_data = availability_service.calculate_availability(
        practitioner_id=str(practitioner_id),
        clinic_id=str(clinic_id),
        date_from=date_str,
        date_to=date_str,
        treatment_id=treatment_id,
        slot_duration=int(slot_duration),
        timezone_str='UTC',
    )
    day_availability = next(
        (day for day in availability_data['availability'] if day['date'] == date_str),
        None
    )
    if not day_availability:
        return Response({
            'error': 'Date not available',
            'details': f'No availability for date {date_str}'
        }, status=status.HTTP_400_BAD_REQUEST)
    slot_found = any(
        slot['start'] == start_str and slot['end'] == end_str
        for slot in day_availability['slots']
    )
    if not slot_found:
        return Response({
            'error': 'Slot not available',
            'details': f'Slot {start_str}-{end_str} is not available. It may be occupied or outside working hours.',
            'available_slots': day_availability['slots'][:5]
        }, status=status.HTTP_409_CONFLICT)
    return None


class PatientViewSet(TenantQuerySetMixin, viewsets.ModelViewSet):
    """
    ViewSet for Patient endpoints.
    
    Endpoints:
    - POST /api/v1/patients/
    - GET /api/v1/patients/
    - GET /api/v1/patients/{id}/
    - PATCH /api/v1/patients/{id}/
    """
    permission_classes = [PatientPermission]
    
    def get_queryset(self):
        """
        Filter queryset based on user role and include_deleted parameter.
        
        - By default, exclude soft-deleted patients (is_deleted=False)
        - Admin can use ?include_deleted=true to see deleted patients
        """
        # Check if user is Admin
        user_roles = set(
            self.request.user.user_roles.values_list('role__name', flat=True)
        )
        is_admin = RoleChoices.ADMIN in user_roles
        
        # Handle include_deleted parameter
        include_deleted = self.request.query_params.get('include_deleted', 'false').lower() == 'true'
        
        if include_deleted and is_admin:
            # Admin can see deleted patients with ?include_deleted=true.
            # Must use unfiltered manager to bypass the PatientManager is_deleted=False default.
            # Tenant filter is ALWAYS applied — even for superusers.
            # A superuser without X-Legal-Entity-ID header receives a 403 here.
            from apps.core.tenant_context import get_current_tenant as _get_tenant
            from rest_framework.exceptions import PermissionDenied as _PermissionDenied
            _tenant = _get_tenant()
            if _tenant is None:
                raise _PermissionDenied(
                    "X-Legal-Entity-ID header is required when using include_deleted."
                )
            queryset = Patient.unfiltered.select_related('referral_source').filter(
                legal_entity=_tenant
            )
        else:
            # PatientManager already applies is_deleted=False; no extra filter needed.
            queryset = Patient.objects.select_related('referral_source')
        
        # Search filters
        q = self.request.query_params.get('q')
        if q:
            # Full-text search in first_name, last_name, email, phone
            queryset = queryset.filter(
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(email__icontains=q) |
                Q(phone__icontains=q) |
                Q(full_name_normalized__icontains=q.lower())
            )
        
        # Exact filters
        email = self.request.query_params.get('email')
        if email:
            queryset = queryset.filter(email=email)
        
        phone = self.request.query_params.get('phone')
        if phone:
            queryset = queryset.filter(phone=phone)
        
        country_code = self.request.query_params.get('country_code')
        if country_code:
            queryset = queryset.filter(country_code=country_code)
        
        # Ordering
        ordering = self.request.query_params.get('ordering', 'last_name')
        queryset = queryset.order_by(ordering)
        
        # Annotate with consent warnings (for list view only)
        # TWO separate flags:
        # 1) has_missing_legal_consents: TRUE if checkboxes not marked (BLOCKS encounters)
        # 2) has_missing_consent_documents: TRUE if documents not uploaded (INFORMATIVE only)
        if self.action == 'list':
            from apps.clinical.models import Consent, ConsentTypeChoices, ConsentStatusChoices
            from django.db.models import Count, Case, When, BooleanField
            
            queryset = queryset.annotate(
                # Count granted privacy_policy consents (not revoked)
                privacy_policy_count=Count(
                    'consents',
                    filter=Q(
                        consents__consent_type=ConsentTypeChoices.PRIVACY_POLICY,
                        consents__status=ConsentStatusChoices.GRANTED,
                        consents__revoked_at__isnull=True
                    )
                ),
                # Count granted terms_and_conditions consents (not revoked)
                terms_count=Count(
                    'consents',
                    filter=Q(
                        consents__consent_type=ConsentTypeChoices.TERMS_AND_CONDITIONS,
                        consents__status=ConsentStatusChoices.GRANTED,
                        consents__revoked_at__isnull=True
                    )
                ),
                # Count privacy_policy consents WITH document attached
                privacy_with_doc_count=Count(
                    'consents',
                    filter=Q(
                        consents__consent_type=ConsentTypeChoices.PRIVACY_POLICY,
                        consents__status=ConsentStatusChoices.GRANTED,
                        consents__revoked_at__isnull=True,
                        consents__document__isnull=False
                    )
                ),
                # Count terms_and_conditions consents WITH document attached
                terms_with_doc_count=Count(
                    'consents',
                    filter=Q(
                        consents__consent_type=ConsentTypeChoices.TERMS_AND_CONDITIONS,
                        consents__status=ConsentStatusChoices.GRANTED,
                        consents__revoked_at__isnull=True,
                        consents__document__isnull=False
                    )
                )
            ).annotate(
                # Flag 1: TRUE if either required LEGAL CONSENT is missing (BLOCKING)
                has_missing_legal_consents=Case(
                    When(Q(privacy_policy_count=0) | Q(terms_count=0), then=True),
                    default=False,
                    output_field=BooleanField()
                ),
                # Flag 2: TRUE if consents exist BUT documents are missing (INFORMATIVE)
                # Only relevant when has_missing_legal_consents=False
                has_missing_consent_documents=Case(
                    When(
                        Q(privacy_policy_count__gt=0) &
                        Q(terms_count__gt=0) &
                        (Q(privacy_with_doc_count=0) | Q(terms_with_doc_count=0)),
                        then=True
                    ),
                    default=False,
                    output_field=BooleanField()
                )
            )
        
        return queryset
    
    def get_serializer_class(self):
        """Use list serializer for list view, detail serializer otherwise"""
        if self.action == 'list':
            return PatientListSerializer
        return PatientDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        """GET /api/v1/patients/{id}/ — detail + audit log."""
        response = super().retrieve(request, *args, **kwargs)
        patient = self.get_object()
        log_clinical_access(
            request,
            action=ClinicalAccessAction.VIEW_PATIENT,
            patient=patient,
            resource=patient,
        )
        return response

    def create(self, request, *args, **kwargs):
        """Create patient (POST /api/v1/patients/)"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # Return full detail using DetailSerializer
        detail_serializer = PatientDetailSerializer(
            serializer.instance,
            context={'request': request}
        )
        headers = self.get_success_headers(detail_serializer.data)
        log_clinical_access(
            request,
            action=ClinicalAccessAction.CREATE_PATIENT,
            patient=serializer.instance,
            resource=serializer.instance,
        )
        return Response(
            detail_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )
    
    def perform_create(self, serializer):
        """Save with audit fields"""
        serializer.save()
        patient = serializer.instance
        log_event(
            user=self.request.user,
            legal_entity=patient.legal_entity,
            entity_type='Patient',
            entity_id=patient.pk,
            event_type=AuditEventType.PATIENT_CREATED,
            payload={'first_name': patient.first_name, 'last_name': patient.last_name},
        )
    
    def update(self, request, *args, **kwargs):
        """Update patient (PATCH /api/v1/patients/{id}/)"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            # Check if it's a row_version conflict
            if 'row_version' in str(e):
                return Response(
                    {
                        'error': {
                            'code': 'CONFLICT',
                            'message': 'El paciente fue modificado por otro usuario. Recarga los datos.',
                            'details': {
                                'current_row_version': instance.row_version,
                                'provided_row_version': request.data.get('row_version')
                            }
                        }
                    },
                    status=status.HTTP_409_CONFLICT
                )
            raise
        
        self.perform_update(serializer)
        
        # Refresh from DB to get updated row_version
        serializer.instance.refresh_from_db()
        log_clinical_access(
            request,
            action=ClinicalAccessAction.UPDATE_PATIENT,
            patient=serializer.instance,
            resource=serializer.instance,
        )
        return Response(serializer.data)
    
    def perform_update(self, serializer):
        """Save update"""
        serializer.save()
        patient = serializer.instance
        log_event(
            user=self.request.user,
            legal_entity=patient.legal_entity,
            entity_type='Patient',
            entity_id=patient.pk,
            event_type=AuditEventType.PATIENT_UPDATED,
            payload={'updated_fields': list(self.request.data.keys())},
        )

    def destroy(self, request, *args, **kwargs):
        """
        DELETE /api/v1/patients/{id}/
        Soft delete patient (Admin only — enforced by PatientPermission).
        """
        from django.utils import timezone
        instance = self.get_object()
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.deleted_by_user = request.user
        instance.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by_user', 'updated_at'])
        log_event(
            user=request.user,
            legal_entity=instance.legal_entity,
            entity_type='Patient',
            entity_id=instance.pk,
            event_type=AuditEventType.PATIENT_SOFT_DELETED,
            payload={'deleted_at': instance.deleted_at.isoformat()},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get', 'post'], url_path='guardians', permission_classes=[GuardianPermission])
    def guardians(self, request, pk=None):
        """
        GET /api/v1/patients/{id}/guardians/
        POST /api/v1/patients/{id}/guardians/
        """
        patient = self.get_object()
        
        if request.method == 'GET':
            # List guardians
            guardians_qs = patient.guardians.all().order_by('created_at')
            serializer = PatientGuardianSerializer(guardians_qs, many=True)
            return Response(serializer.data)
        
        elif request.method == 'POST':
            # Create guardian
            data = request.data.copy()
            data['patient_id'] = patient.id
            
            serializer = PatientGuardianSerializer(data=data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            serializer.save()
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'], url_path='merge')
    def merge(self, request, pk=None):
        """
        POST /api/v1/patients/{id}/merge/
        
        Merge source patient (pk) into target patient.
        Only Admin and Practitioner can execute.
        
        Request body:
        {
            "target_patient_id": "<uuid>",
            "merge_reason": "Duplicado: mismo email y teléfono"
        }
        
        Response (200 OK):
        {
            "source_patient_id": "...",
            "target_patient_id": "...",
            "merged": true,
            "reassigned": {
                "encounters": <int>,
                "appointments": <int>,
                "consents": <int>,
                "photos": <int>,
                "guardians": <int>
            }
        }
        """
        # Check permissions: Only Admin and Practitioner
        user_roles = set(
            request.user.user_roles.values_list('role__name', flat=True)
        )
        if not (user_roles & {RoleChoices.ADMIN, RoleChoices.PRACTITIONER}):
            raise PermissionDenied("Solo Admin y Practitioner pueden ejecutar merge de pacientes")
        
        # Validate request data
        target_patient_id = request.data.get('target_patient_id')
        merge_reason = request.data.get('merge_reason')
        
        if not target_patient_id:
            raise ValidationError({
                'target_patient_id': ['Este campo es obligatorio']
            })
        
        if not merge_reason:
            raise ValidationError({
                'merge_reason': ['Este campo es obligatorio']
            })
        
        source_patient_id = pk
        
        # Validate source != target
        if str(source_patient_id) == str(target_patient_id):
            return Response(
                {
                    'error': {
                        'code': 'VALIDATION_ERROR',
                        'message': 'No se puede mergear un paciente consigo mismo',
                        'details': {
                            'target_patient_id': ['El paciente destino no puede ser el mismo que el origen']
                        }
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Execute merge in atomic transaction
        try:
            with transaction.atomic():
                # Lock source and target patients to prevent race conditions
                try:
                    source_patient = Patient.objects.select_for_update().get(pk=source_patient_id)
                except Patient.DoesNotExist:
                    return Response(
                        {
                            'error': {
                                'code': 'NOT_FOUND',
                                'message': 'Paciente origen no encontrado'
                            }
                        },
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                try:
                    target_patient = Patient.objects.select_for_update().get(pk=target_patient_id)
                except Patient.DoesNotExist:
                    return Response(
                        {
                            'error': {
                                'code': 'VALIDATION_ERROR',
                                'message': 'Paciente destino no encontrado',
                                'details': {
                                    'target_patient_id': ['El paciente destino no existe']
                                }
                            }
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Validate source is not already merged
                if source_patient.is_merged:
                    return Response(
                        {
                            'error': {
                                'code': 'CONFLICT',
                                'message': ERROR_MERGE_FAILED,
                                'details': {
                                    'reason': 'El paciente origen ya está merged con otro paciente'
                                }
                            }
                        },
                        status=status.HTTP_409_CONFLICT
                    )
                
                # Validate target is not merged
                if target_patient.is_merged:
                    return Response(
                        {
                            'error': {
                                'code': 'CONFLICT',
                                'message': ERROR_MERGE_FAILED,
                                'details': {
                                    'reason': 'El paciente destino está merged. No se puede usar como destino.'
                                }
                            }
                        },
                        status=status.HTTP_409_CONFLICT
                    )
                
                # Validate source and target are not soft-deleted
                if source_patient.is_deleted:
                    return Response(
                        {
                            'error': {
                                'code': 'CONFLICT',
                                'message': ERROR_MERGE_FAILED,
                                'details': {
                                    'reason': 'El paciente origen está eliminado'
                                }
                            }
                        },
                        status=status.HTTP_409_CONFLICT
                    )
                
                if target_patient.is_deleted:
                    return Response(
                        {
                            'error': {
                                'code': 'CONFLICT',
                                'message': ERROR_MERGE_FAILED,
                                'details': {
                                    'reason': 'El paciente destino está eliminado'
                                }
                            }
                        },
                        status=status.HTTP_409_CONFLICT
                    )
                
                # Reassign all related records from source to target
                reassigned = {}
                
                # Encounters
                encounters_count = Encounter.objects.filter(patient=source_patient).update(
                    patient=target_patient
                )
                reassigned['encounters'] = encounters_count
                
                # Appointments
                appointments_count = Appointment.objects.filter(patient=source_patient).update(
                    patient=target_patient
                )
                reassigned['appointments'] = appointments_count
                
                # Consents
                consents_count = Consent.objects.filter(patient=source_patient).update(
                    patient=target_patient
                )
                reassigned['consents'] = consents_count
                
                # Clinical Photos
                photos_count = ClinicalPhoto.objects.filter(patient=source_patient).update(
                    patient=target_patient
                )
                reassigned['photos'] = photos_count
                
                # Guardians
                guardians_count = PatientGuardian.objects.filter(patient=source_patient).update(
                    patient=target_patient
                )
                reassigned['guardians'] = guardians_count
                
                # Mark source patient as merged
                source_patient.is_merged = True
                source_patient.merged_into_patient = target_patient
                source_patient.merge_reason = merge_reason
                source_patient.row_version += 1
                source_patient.save(update_fields=[
                    'is_merged',
                    'merged_into_patient',
                    'merge_reason',
                    'row_version',
                    'updated_at'
                ])
                
                # Audit the merge
                log_clinical_access(
                    request,
                    action=ClinicalAccessAction.MERGE_PATIENT,
                    patient=source_patient,
                    resource=target_patient,
                )

                # Return success response
                return Response(
                    {
                        'source_patient_id': str(source_patient.id),
                        'target_patient_id': str(target_patient.id),
                        'merged': True,
                        'reassigned': reassigned
                    },
                    status=status.HTTP_200_OK
                )
        
        except Exception as e:
            # Catch any unexpected errors
            return Response(
                {
                    'error': {
                        'code': 'INTERNAL_ERROR',
                        'message': f'Error durante el merge: {str(e)}'
                    }
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # ------------------------------------------------------------------
    # Patient 360 — Overview
    # ------------------------------------------------------------------

    @action(detail=True, methods=['get'], url_path='overview')
    def overview(self, request, pk=None):
        """
        GET /api/v1/clinical/patients/{id}/overview/

        Returns patient summary with RBAC-filtered blocks:
        - patient: detail fields (notes hidden for non-clinical roles)
        - insurance_active: current active coverage or null
        - kpis: counts filtered by role
        """
        patient = self.get_object()

        # ── Role resolution ────────────────────────────────────────────
        user_roles = set(
            request.user.user_roles.values_list('role__name', flat=True)
        )
        can_view_clinical = bool(
            user_roles & {RoleChoices.ADMIN, RoleChoices.PRACTITIONER}
        )

        # ── Patient block (reuse existing serializer with request context) ─
        patient_data = PatientDetailSerializer(
            patient, context={'request': request}
        ).data

        # Additional RBAC: hide notes for accounting too (serializer only
        # hides for Reception; we extend to all non-clinical roles).
        if not can_view_clinical:
            patient_data.pop('notes', None)

        # ── Insurance block ────────────────────────────────────────────
        active_insurance = PatientInsurance.objects.filter(
            patient=patient, is_active=True
        ).order_by('-valid_from').first()

        insurance_data = None
        if active_insurance:
            insurance_data = PatientInsuranceSerializer(active_insurance).data

        # ── KPIs block ─────────────────────────────────────────────────
        from apps.proposals.models import ProposalStatusChoices
        from apps.sales.models import Sale

        kpis = {}

        # Proposals — visible to all authorized roles
        kpis['proposals_draft_count'] = Proposal.objects.filter(
            patient=patient, status=ProposalStatusChoices.DRAFT
        ).count()
        kpis['proposals_sent_count'] = Proposal.objects.filter(
            patient=patient, status=ProposalStatusChoices.SENT
        ).count()

        # Last sale date — visible to all authorized roles
        last_sale = (
            Sale.objects.filter(patient=patient)
            .order_by('-created_at')
            .values_list('created_at', flat=True)
            .first()
        )
        kpis['last_sale_date'] = (
            last_sale.date().isoformat() if last_sale else None
        )

        # Clinical KPIs — only for admin/practitioner
        if can_view_clinical:
            from apps.treatment_plans.models import TreatmentPlanStatusChoices
            from apps.treatment_plans.models import TreatmentPlan

            kpis['total_encounters'] = Encounter.objects.filter(
                patient=patient
            ).count()
            kpis['active_treatment_plans_count'] = TreatmentPlan.objects.filter(
                patient=patient, status=TreatmentPlanStatusChoices.ACTIVE
            ).count()

        return Response({
            'patient': patient_data,
            'insurance_active': insurance_data,
            'kpis': kpis,
        })


class GuardianViewSet(TenantQuerySetMixin, viewsets.ModelViewSet):
    """
    ViewSet for PatientGuardian endpoints.
    
    Endpoints:
    - PATCH /api/v1/guardians/{id}/
    - DELETE /api/v1/guardians/{id}/
    """
    queryset = PatientGuardian.objects.select_related('patient').filter(patient__is_deleted=False)
    serializer_class = PatientGuardianSerializer
    permission_classes = [GuardianPermission]
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']
    
    def update(self, request, *args, **kwargs):
        """Update guardian (PATCH /api/v1/guardians/{id}/)"""
        partial = kwargs.pop('partial', True)  # Always partial for PATCH
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response(serializer.data)
    
    def destroy(self, request, *args, **kwargs):
        """
        DELETE /api/v1/guardians/{id}/
        Hard delete guardian (no soft delete).
        """
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================================
# Patient Insurance ViewSet
# ============================================================================

class PatientInsuranceViewSet(TenantQuerySetMixin, viewsets.ModelViewSet):
    """
    ViewSet for PatientInsurance endpoints.

    Endpoints:
    - GET  /api/v1/clinical/patient-insurances/?patient_id=UUID
    - POST /api/v1/clinical/patient-insurances/
    - PATCH /api/v1/clinical/patient-insurances/{id}/

    Permissions: reuses PatientPermission (same RBAC rules).
    Filterable by patient_id query param (required for list).
    """
    serializer_class = PatientInsuranceSerializer
    permission_classes = [PatientPermission]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        qs = PatientInsurance.objects.select_related('patient').filter(patient__is_deleted=False)
        patient_id = self.request.query_params.get('patient_id')
        if patient_id:
            qs = qs.filter(patient_id=patient_id)
        return qs


class AppointmentViewSet(TenantQuerySetMixin, viewsets.ModelViewSet):
    """
    ViewSet for Appointment endpoints.
    
    Endpoints:
    - POST /api/v1/appointments/
    - GET /api/v1/appointments/
    - GET /api/v1/appointments/{id}/
    - PATCH /api/v1/appointments/{id}/
    - DELETE /api/v1/appointments/{id}/ (Admin only, soft delete)
    """
    permission_classes = [AppointmentPermission]
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    
    def get_queryset(self):
        """
        Filter queryset based on user role and query parameters.
        
        Filters:
        - status: Filter by appointment status
        - date_from: Filter appointments scheduled_start >= date_from
        - date_to: Filter appointments scheduled_start <= date_to
        - patient_id: Filter by patient UUID
        - practitioner_id: Filter by practitioner UUID
        - clinic_id: Filter by clinic UUID
        - include_deleted: Show soft-deleted appointments (Admin only)
        """
        # Optimize with select_related
        _select = ('patient', 'practitioner', 'clinic', 'encounter', 'appointment_type')
        
        # Check if user is Admin
        user_roles = set(
            self.request.user.user_roles.values_list('role__name', flat=True)
        )
        is_admin = RoleChoices.ADMIN in user_roles
        
        # Handle include_deleted (Admin only)
        include_deleted = self.request.query_params.get('include_deleted', 'false').lower() == 'true'
        if include_deleted and is_admin:
            # Admin explicitly requested deleted records — bypass AppointmentManager
            # soft-delete filter by using the unfiltered manager with only tenant scoping.
            from apps.core.tenant_context import get_current_tenant
            tenant = get_current_tenant()
            queryset = Appointment.unfiltered.select_related(
                *_select,
            ).filter(legal_entity=tenant)
        else:
            # Exclude deleted appointments and exclude appointments for deleted patients.
            queryset = Appointment.objects.select_related(
                *_select,
            ).filter(is_deleted=False, patient__is_deleted=False)
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from', None)
        if date_from:
            queryset = queryset.filter(scheduled_start__gte=date_from)
        
        date_to = self.request.query_params.get('date_to', None)
        if date_to:
            queryset = queryset.filter(scheduled_start__lte=date_to)
        
        # Filter by patient_id
        patient_id = self.request.query_params.get('patient_id', None)
        if patient_id:
            queryset = queryset.filter(patient_id=patient_id)
        
        # Filter by practitioner_id
        practitioner_id = self.request.query_params.get('practitioner_id', None)
        if practitioner_id:
            queryset = queryset.filter(practitioner_id=practitioner_id)
        
        # Filter by clinic_id
        clinic_id = self.request.query_params.get('clinic_id', None)
        if clinic_id:
            queryset = queryset.filter(clinic_id=clinic_id)
        
        # Order by scheduled_start descending
        queryset = queryset.order_by('-scheduled_start')
        
        return queryset
    
    def get_serializer_class(self):
        """
        Return appropriate serializer based on action.
        
        - list: AppointmentListSerializer (lightweight)
        - retrieve: AppointmentDetailSerializer (full read-only)
        - create/update: AppointmentWriteSerializer (write)
        """
        if self.action == 'list':
            return AppointmentListSerializer
        elif self.action == 'retrieve':
            return AppointmentDetailSerializer
        else:
            return AppointmentWriteSerializer
    
    def create(self, request, *args, **kwargs):
        """
        POST /api/v1/appointments/

        ERP is the sole scheduling engine. Creates appointment with status=scheduled.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        appointment = serializer.save()

        # Audit event
        log_event(
            user=request.user,
            legal_entity=appointment.legal_entity,
            entity_type='Appointment',
            entity_id=appointment.pk,
            event_type=AuditEventType.APPOINTMENT_CREATED,
            payload={'source': appointment.source, 'status': appointment.status},
        )

        response_serializer = AppointmentDetailSerializer(appointment)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """
        PATCH /api/v1/appointments/{id}/
        Update appointment fields (NOT status — use /transition/).
        """
        partial = kwargs.pop('partial', True)
        instance = self.get_object()

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # Audit
        log_event(
            user=request.user,
            legal_entity=instance.legal_entity,
            entity_type='Appointment',
            entity_id=instance.pk,
            event_type=AuditEventType.APPOINTMENT_UPDATED,
            payload={'changed_fields': list(request.data.keys())},
        )

        response_serializer = AppointmentDetailSerializer(instance)
        return Response(response_serializer.data)
    
    def destroy(self, request, *args, **kwargs):
        """
        DELETE /api/v1/appointments/{id}/
        Soft delete appointment (Admin only).
        """
        # Check if user is Admin
        user_roles = set(
            request.user.user_roles.values_list('role__name', flat=True)
        )
        if RoleChoices.ADMIN not in user_roles:
            raise PermissionDenied(
                "Solo Admin puede eliminar citas"
            )
        
        instance = self.get_object()
        
        # Soft delete — update only the specific fields to avoid side effects
        from django.utils import timezone
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.deleted_by_user = request.user
        instance.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by_user', 'updated_at'])

        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['post'], url_path='transition')
    def transition_status(self, request, pk=None):
        """
        POST /api/v1/appointments/{id}/transition/
        
        Transition appointment to a new status with validation.
        
        Allowed transitions:
        - scheduled -> confirmed | cancelled | no_show
        - confirmed -> checked_in | cancelled | no_show
        - checked_in -> completed
        
        On checked_in: auto-creates Encounter (max 1).
        
        Request body:
        {
            "status": "confirmed",
            "reason": "Patient requested cancellation"  // Optional
        }
        
        Returns:
            200: Transition successful
            400: Invalid transition or validation error
        """
        from django.core.exceptions import ValidationError as DjangoValidationError
        
        appointment = self.get_object()
        new_status = request.data.get('status')
        reason = request.data.get('reason')
        
        if not new_status:
            return Response(
                {'error': 'El campo "status" es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate with transaction and row locking to prevent race conditions
        try:
            with transaction.atomic():
                # Lock the row for update
                appointment = Appointment.objects.select_for_update().get(pk=pk)
                
                # Attempt transition
                appointment.transition_status(new_status, user=request.user, reason=reason)
                
                # Save the appointment
                appointment.save()
                
                # Emit domain audit event for key transitions
                _APPOINTMENT_AUDIT_MAP = {
                    'cancelled': AuditEventType.APPOINTMENT_CANCELLED,
                    'no_show':   AuditEventType.APPOINTMENT_NO_SHOW,
                    'checked_in': AuditEventType.APPOINTMENT_CHECKED_IN,
                }
                if new_status in _APPOINTMENT_AUDIT_MAP:
                    log_event(
                        user=request.user,
                        legal_entity=appointment.legal_entity,
                        entity_type='Appointment',
                        entity_id=appointment.pk,
                        event_type=_APPOINTMENT_AUDIT_MAP[new_status],
                        payload={'new_status': new_status, 'reason': reason or ''},
                    )
                
                # Return updated appointment
                serializer = AppointmentDetailSerializer(appointment)
                return Response(serializer.data, status=status.HTTP_200_OK)
                
        except DjangoValidationError as e:
            return Response(
                {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], url_path='attend')
    def attend(self, request, pk=None):
        """
        POST /api/v1/appointments/{id}/attend/
        
        ATOMIC operation: Create Encounter + Link to Appointment + Mark as 'completed'.
        This is the CANONICAL endpoint for "Atender paciente" workflow per ENCOUNTER_WORKFLOW_DECISIONS.md.
        
        Business Rules:
        - Creates new Encounter with status='draft'
        - Links appointment.encounter = new_encounter
        - Marks appointment.status = 'completed'
        - ALL operations in single transaction.atomic() with select_for_update()
        - Idempotent: If encounter already linked, returns existing encounter (no duplicate creation)
        
        Permissions: Admin, Practitioner, Reception (403 for Accounting/Marketing)
        
        Validations:
        - appointment.status must NOT be 'cancelled' or 'no_show' (400)
        - appointment.patient must exist (enforced by FK)
        
        Request body (all fields optional for encounter creation):
        {
            "encounter_type": "medical_consult|followup|emergency|...",  // Optional, defaults to 'medical_consult'
            "chief_complaint": "Patient-reported reason for visit",
            "occurred_at": "2025-01-09T10:00:00Z"  // Optional, defaults to timezone.now()
        }
        
        Response 201 CREATED (new encounter):
        {
            "appointment_id": "uuid",
            "encounter_id": "uuid",
            "appointment_status": "completed",
            "encounter_status": "draft",
            "created": true
        }
        
        Response 200 OK (idempotent - encounter already exists):
        {
            "appointment_id": "uuid",
            "encounter_id": "uuid",
            "appointment_status": "completed",
            "encounter_status": "draft|finalized|cancelled",
            "created": false
        }
        
        Response 400 BAD_REQUEST:
        {
            "error": "Cannot attend appointment with status 'cancelled'"
        }
        """
        from apps.clinical.models import Encounter, EncounterTypeChoices, EncounterStatusChoices
        
        # Permission check: Admin, Practitioner, Reception
        user_roles = set(
            request.user.user_roles.values_list('role__name', flat=True)
        )
        allowed_roles = {RoleChoices.ADMIN, RoleChoices.PRACTITIONER, RoleChoices.RECEPTION}
        
        if not (user_roles & allowed_roles):
            raise PermissionDenied(
                "Solo Admin, Practitioner y Reception pueden atender pacientes"
            )
        
        with transaction.atomic():
            # CRITICAL: Lock appointment row to prevent race conditions
            try:
                appointment = Appointment.objects.select_for_update().get(pk=pk)
            except Appointment.DoesNotExist:
                return Response(
                    {'error': 'Cita no encontrada'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Validation: Cannot attend deleted appointment
            if appointment.is_deleted:
                return Response(
                    {'error': 'No se puede atender una cita eliminada'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validation: Block terminal statuses (cancelled, no_show)
            if appointment.status in ['cancelled', 'no_show']:
                return Response(
                    {'error': f"No se puede atender una cita con status='{appointment.status}'"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # IDEMPOTENCY: If encounter already linked, return existing encounter
            if appointment.encounter:
                # Ensure status is 'completed' (hardening)
                if appointment.status != 'completed':
                    appointment.status = 'completed'
                    appointment.save(update_fields=['status', 'updated_at'])
                
                return Response(
                    {
                        'appointment_id': str(appointment.id),
                        'encounter_id': str(appointment.encounter.id),
                        'appointment_status': appointment.status,
                        'encounter_status': appointment.encounter.status,
                        'created': False
                    },
                    status=status.HTTP_200_OK
                )
            
            # Extract optional encounter fields from request
            encounter_type = request.data.get('encounter_type', 'medical_consult')
            chief_complaint = request.data.get('chief_complaint', '')
            
            # Parse occurred_at if provided, otherwise use now()
            occurred_at, err = _parse_occurred_at(request.data.get('occurred_at'))
            if err:
                return err
            
            # Validate encounter_type
            if encounter_type not in dict(EncounterTypeChoices.choices):
                return Response(
                    {'error': f"encounter_type inválido: '{encounter_type}'"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # CREATE ENCOUNTER (status='draft' per business rules)
            encounter = Encounter.objects.create(
                patient=appointment.patient,
                practitioner=appointment.practitioner,
                clinic=appointment.clinic,
                type=encounter_type,
                status=EncounterStatusChoices.DRAFT,
                occurred_at=occurred_at,
                chief_complaint=chief_complaint,
                created_by_user=request.user
            )
            
            # LINK APPOINTMENT TO ENCOUNTER + MARK AS COMPLETED
            appointment.encounter = encounter
            appointment.status = 'completed'
            appointment.save(update_fields=['encounter', 'status', 'updated_at'])
            
            return Response(
                {
                    'appointment_id': str(appointment.id),
                    'encounter_id': str(encounter.id),
                    'appointment_status': appointment.status,
                    'encounter_status': encounter.status,
                    'created': True
                },
                status=status.HTTP_201_CREATED
            )
    
    @action(detail=True, methods=['post'], url_path='start-treatment-session')
    def start_treatment_session(self, request, pk=None):
        """
        POST /api/v1/clinical/appointments/{id}/start-treatment-session/

        Creates a TreatmentSession (status=draft) linked to this appointment
        and transitions the appointment to 'completed'.

        Request body:
        {
            "treatment_plan_id": "<uuid>"   // required
        }

        Validations:
        1) Appointment must exist and not be deleted.
        2) Appointment.status must be 'checked_in'.
        3) treatment_plan_id is required and must reference an ACTIVE plan
           belonging to the same patient and tenant.
        4) No existing TreatmentSession for this appointment (unique).
        5) Creates session with practitioner = appointment.practitioner.

        Returns 201 with session data on success.
        """
        from apps.treatment_plans.models import TreatmentPlan, TreatmentPlanStatusChoices
        from apps.treatment_plans.treatment_session_models import TreatmentSession
        from apps.treatment_plans.treatment_session_serializers import TreatmentSessionListSerializer
        from apps.treatment_plans.treatment_session_models import TreatmentSessionStatusChoices
        from django.core.exceptions import ValidationError as DjangoValidationError

        # RBAC: Admin + Practitioner only (IsClinicalStaff equivalent)
        user_roles = set(
            request.user.user_roles.values_list('role__name', flat=True)
        )
        allowed_roles = {RoleChoices.ADMIN, RoleChoices.PRACTITIONER}
        if not (user_roles & allowed_roles):
            raise PermissionDenied(
                "Only Admin and Practitioner can start treatment sessions."
            )

        # Resolve active legal entity for multi-tenant isolation
        user_le = getattr(request.user, 'legal_entity_id', None)

        treatment_plan_id = request.data.get('treatment_plan_id')
        if not treatment_plan_id:
            return Response(
                {'error': 'treatment_plan_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                # 1) Lock appointment row
                try:
                    appointment = (
                        Appointment.objects
                        .select_for_update()
                        .get(pk=pk)
                    )
                except Appointment.DoesNotExist:
                    return Response(
                        {'error': 'Appointment not found.'},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                err = _validate_appointment_for_session(appointment)
                if err:
                    return err

                # 4) Lock + validate treatment plan
                try:
                    plan = (
                        TreatmentPlan.objects
                        .select_for_update()
                        .get(pk=treatment_plan_id)
                    )
                except TreatmentPlan.DoesNotExist:
                    return Response(
                        {'error': 'Treatment plan not found.'},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                err = _validate_plan_for_session(plan, appointment, user_le)
                if err:
                    return err

                # 6) Uniqueness: no existing session for this appointment
                if TreatmentSession.objects.filter(appointment=appointment).exists():
                    return Response(
                        {'error': 'A treatment session already exists for this appointment.'},
                        status=status.HTTP_409_CONFLICT,
                    )

                # 7) Count guard: lock session rows + check slots
                draft_count = (
                    TreatmentSession.objects
                    .select_for_update()
                    .filter(
                        treatment_plan=plan,
                        status=TreatmentSessionStatusChoices.DRAFT,
                    )
                    .count()
                )
                completed_count = (
                    TreatmentSession.objects
                    .select_for_update()
                    .filter(
                        treatment_plan=plan,
                        status=TreatmentSessionStatusChoices.COMPLETED,
                    )
                    .count()
                )
                if draft_count + completed_count >= plan.planned_sessions:
                    return Response(
                        {'error': 'All planned sessions are already created or completed.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # 8) Create session
                session = TreatmentSession.objects.create(
                    treatment_plan=plan,
                    appointment=appointment,
                    practitioner=appointment.practitioner,
                    status=TreatmentSessionStatusChoices.DRAFT,
                )

                # 9) Transition appointment via formal state machine
                appointment.transition_status('completed')
                appointment.save(update_fields=['status', 'updated_at'])

                log_clinical_access(
                    request,
                    action=ClinicalAccessAction.CREATE_TREATMENT_SESSION,
                    patient=plan.patient,
                    resource=session,
                )

                return Response(
                    {
                        'session': TreatmentSessionListSerializer(session).data,
                        'appointment_id': str(appointment.id),
                        'appointment_status': appointment.status,
                    },
                    status=status.HTTP_201_CREATED,
                )

        except IntegrityError:
            return Response(
                {'error': 'A treatment session already exists for this appointment (constraint violation).'},
                status=status.HTTP_409_CONFLICT,
            )
        except DjangoValidationError as e:
            return Response(
                {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


# Patient Merge Views

from apps.clinical.permissions import IsClinicalOpsOrAdmin
from apps.clinical.services import merge_patients, get_merge_candidates, PatientMergeError
from apps.clinical.serializers import (
    MergeCandidateSerializer,
    PatientMergeRequestSerializer,
    PatientMergeResponseSerializer
)


class PatientMergeCandidatesView(APIView):
    """
    GET /api/v1/clinical/patients/{id}/merge-candidates
    
    Find potential duplicate patients for merging.
    """
    permission_classes = [IsClinicalOpsOrAdmin]
    
    def get(self, request, pk):
        try:
            patient = Patient.objects.get(id=pk, is_deleted=False)
        except Patient.DoesNotExist:
            return Response(
                {'error': 'Patient not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        limit = int(request.query_params.get('limit', 20))
        limit = min(max(limit, 1), 100)  # Clamp between 1-100
        
        candidates = get_merge_candidates(patient, limit=limit)
        serializer = MergeCandidateSerializer(candidates, many=True)
        
        return Response(serializer.data)


class PatientMergeView(APIView):
    """
    POST /api/v1/clinical/patients/merge
    
    Merge source patient into target patient.
    
    Body:
    {
        "source_patient_id": "...",
        "target_patient_id": "...",
        "strategy": "manual|phone_exact|email_exact|name_trgm",
        "notes": "optional",
        "evidence": {...}
    }
    """
    permission_classes = [IsClinicalOpsOrAdmin]
    
    def post(self, request):
        serializer = PatientMergeRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = serializer.validated_data
        
        try:
            target_patient = merge_patients(
                source_id=data['source_patient_id'],
                target_id=data['target_patient_id'],
                merged_by=request.user,
                strategy=data.get('strategy', 'manual'),
                notes=data.get('notes'),
                evidence=data.get('evidence')
            )
            
            # Get relations summary
            from apps.clinical.services import _count_patient_relations
            Patient.objects.get(id=data['source_patient_id'])
            moved_relations = _count_patient_relations(target_patient)
            
            # Get merge log
            merge_log = target_patient.merge_target_logs.latest('merged_at')
            
            response_data = {
                'target_patient_id': target_patient.id,
                'moved_relations_summary': moved_relations,
                'merge_log_id': merge_log.id
            }
            
            response_serializer = PatientMergeResponseSerializer(response_data)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
            
        except Patient.DoesNotExist:
            return Response(
                {'error': 'Source or target patient not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except PatientMergeError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(
                "Unexpected error during patient merge",
                exc_info=True,
                extra={'user_id': str(request.user.id) if request.user else None}
            )
            return Response(
                {'error': 'An unexpected error occurred during merge'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ============================================================================
# Clinical Core v1: Encounter and Treatment ViewSets
# ============================================================================

class TreatmentViewSet(TenantQuerySetMixin, viewsets.ModelViewSet):
    """
    ViewSet for Treatment catalog.
    
    Endpoints:
    - GET /api/v1/treatments/ - List all treatments (filtered by is_active)
    - GET /api/v1/treatments/{id}/ - Get treatment detail
    - POST /api/v1/treatments/ - Create treatment (Admin only)
    - PATCH /api/v1/treatments/{id}/ - Update treatment (Admin only)
    - DELETE /api/v1/treatments/{id}/ - Soft delete treatment (Admin only)
    
    Query parameters:
    - ?include_inactive=true - Include inactive treatments (default: false)
    - ?q=search_term - Search by name
    """
    queryset = Treatment.objects.all()
    serializer_class = TreatmentSerializer
    permission_classes = [TreatmentPermission]
    
    def get_queryset(self):
        """Filter by is_active and search."""
        queryset = Treatment.objects.all()
        
        # Filter by is_active (default: only active)
        include_inactive = self.request.query_params.get('include_inactive', 'false').lower() == 'true'
        if not include_inactive:
            queryset = queryset.filter(is_active=True)
        
        # Search by name
        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(name__icontains=q)
        
        return queryset.order_by('name')


class EncounterViewSet(TenantQuerySetMixin, viewsets.ModelViewSet):
    """
    ViewSet for Encounter (clinical visits).
    
    Endpoints:
    - GET /api/v1/encounters/ - List encounters
    - GET /api/v1/encounters/{id}/ - Get encounter detail
    - POST /api/v1/encounters/ - Create encounter
    - PATCH /api/v1/encounters/{id}/ - Update encounter
    - DELETE /api/v1/encounters/{id}/ - Soft delete encounter
    
    Query parameters:
    - ?patient_id=... - Filter by patient
    - ?practitioner_id=... - Filter by practitioner
    - ?status=draft|finalized|cancelled - Filter by status
    - ?date_from=YYYY-MM-DD - Filter by occurred_at >= date_from
    - ?date_to=YYYY-MM-DD - Filter by occurred_at <= date_to
    """
    permission_classes = [EncounterPermission]
    
    def get_queryset(self):
        """Filter by patient, practitioner, status, date range."""
        # EncounterManager already excludes is_deleted=True from the default queryset.
        # Also exclude encounters linked to soft-deleted patients.
        queryset = Encounter.objects.select_related('patient', 'practitioner', 'clinic')
        queryset = queryset.filter(patient__is_deleted=False)
        queryset = queryset.prefetch_related('encounter_treatments__treatment')
        
        # Filter by patient
        patient_id = self.request.query_params.get('patient_id')
        if patient_id:
            queryset = queryset.filter(patient_id=patient_id)
        
        # Filter by practitioner
        practitioner_id = self.request.query_params.get('practitioner_id')
        if practitioner_id:
            queryset = queryset.filter(practitioner_id=practitioner_id)
        
        # Filter by status
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(occurred_at__date__gte=date_from)
        
        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(occurred_at__date__lte=date_to)
        
        return queryset.order_by('-occurred_at')
    
    def get_serializer_class(self):
        """Use different serializers for list/detail/write."""
        if self.action == 'list':
            return EncounterListSerializer
        elif self.action == 'retrieve':
            return EncounterDetailSerializer
        else:  # create, update, partial_update
            return EncounterWriteSerializer

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        encounter = self.get_object()
        log_clinical_access(
            request,
            action=ClinicalAccessAction.VIEW_ENCOUNTER,
            patient=encounter.patient,
            resource=encounter,
        )
        return response

    def perform_create(self, serializer):
        serializer.save()
        encounter = serializer.instance
        log_clinical_access(
            self.request,
            action=ClinicalAccessAction.CREATE_ENCOUNTER,
            patient=encounter.patient,
            resource=encounter,
        )
        log_event(
            user=self.request.user,
            legal_entity=encounter.legal_entity,
            entity_type='Encounter',
            entity_id=encounter.pk,
            event_type=AuditEventType.ENCOUNTER_CREATED,
            payload={'patient_id': str(encounter.patient_id), 'status': encounter.status},
        )

    def perform_update(self, serializer):
        serializer.save()
        encounter = serializer.instance
        log_clinical_access(
            self.request,
            action=ClinicalAccessAction.UPDATE_ENCOUNTER,
            patient=encounter.patient,
            resource=encounter,
        )
        # Emit domain-level event when encounter reaches a terminal state
        if encounter.status == EncounterStatusChoices.FINALIZED:
            log_event(
                user=self.request.user,
                legal_entity=encounter.legal_entity,
                entity_type='Encounter',
                entity_id=encounter.pk,
                event_type=AuditEventType.ENCOUNTER_FINALIZED,
                payload={'patient_id': str(encounter.patient_id)},
            )

    def destroy(self, request, *args, **kwargs):
        """
        DELETE /api/v1/encounters/{id}/
        Soft delete encounter (Admin only — enforced by EncounterPermission).

        BUSINESS RULE: Only DRAFT encounters can be deleted.
        FINALIZED and CANCELLED encounters are immutable clinical records.
        """
        from django.utils import timezone
        instance = self.get_object()
        if instance.status != EncounterStatusChoices.DRAFT:
            raise ValidationError(
                "Only draft encounters can be deleted. "
                f"This encounter is '{instance.status}' and is an immutable clinical record."
            )
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.deleted_by_user = request.user
        instance.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by_user', 'updated_at'])
        log_event(
            user=request.user,
            legal_entity=instance.legal_entity,
            entity_type='Encounter',
            entity_id=instance.pk,
            event_type=AuditEventType.ENCOUNTER_CANCELLED,
            payload={'deleted_at': instance.deleted_at.isoformat()},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='generate-proposal')
    def generate_proposal(self, request, pk=None):
        """
        POST /api/v1/clinical/encounters/{id}/generate-proposal/
        
        Generate a ClinicalChargeProposal from a finalized encounter.
        
        This is the EXPLICIT step before creating a Sale.
        
        Body:
        {
            "notes": "optional internal notes"
        }
        
        Returns:
        {
            "proposal_id": "uuid",
            "message": "Success message",
            "total_amount": "Decimal",
            "line_count": int
        }
        
        Business Rules:
        - Encounter must be FINALIZED
        - One proposal per encounter (idempotency)
        - Requires at least one treatment in encounter
        """
        from apps.clinical.services import generate_charge_proposal_from_encounter
        from django.core.exceptions import ValidationError as DjangoValidationError
        
        encounter = self.get_object()
        notes = request.data.get('notes', '')
        
        # Generate proposal (validation happens in service)
        try:
            proposal = generate_charge_proposal_from_encounter(
                encounter=encounter,
                created_by=request.user,
                notes=notes
            )
            log_event(
                user=request.user,
                legal_entity=proposal.legal_entity,
                entity_type='Proposal',
                entity_id=proposal.pk,
                event_type=AuditEventType.PROPOSAL_CREATED,
                payload={'encounter_id': str(encounter.id), 'total_amount': str(proposal.total_amount)},
            )
            return Response({
                'proposal_id': str(proposal.id),
                'message': f"Charge proposal generated from encounter {encounter.id}",
                'total_amount': str(proposal.total_amount),
                'line_count': proposal.lines.count(),
                'status': proposal.status
            }, status=status.HTTP_201_CREATED)
            
        except (ValidationError, DjangoValidationError) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def add_treatment(self, request, pk=None):
        """
        POST /api/v1/encounters/{id}/add_treatment/
        
        Add a treatment to an existing encounter.
        
        Body:
        {
            "treatment_id": "...",
            "quantity": 1,
            "unit_price": 100.00,  # optional
            "notes": "..."         # optional
        }
        """
        encounter = self.get_object()
        
        # Validate encounter status
        if encounter.status != 'draft':
            return Response(
                {'error': 'Solo se pueden agregar tratamientos a encuentros en estado draft'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate request data
        treatment_id = request.data.get('treatment_id')
        quantity = request.data.get('quantity', 1)
        unit_price = request.data.get('unit_price')
        notes = request.data.get('notes', '')
        
        if not treatment_id:
            return Response(
                {'error': 'treatment_id es obligatorio'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            treatment = Treatment.objects.get(id=treatment_id)
            if not treatment.is_active:
                return Response(
                    {'error': f"El tratamiento '{treatment.name}' está inactivo"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Treatment.DoesNotExist:
            return Response(
                {'error': 'Tratamiento no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create EncounterTreatment
        try:
            with transaction.atomic():
                encounter_treatment = EncounterTreatment.objects.create(
                    encounter=encounter,
                    treatment=treatment,
                    quantity=quantity,
                    unit_price=unit_price,
                    notes=notes
                )
            
            from apps.clinical.serializers import EncounterTreatmentSerializer
            serializer = EncounterTreatmentSerializer(encounter_treatment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except IntegrityError:
            return Response(
                {'error': 'Este tratamiento ya existe en el encuentro'},
                status=status.HTTP_400_BAD_REQUEST
            )


# ============================================================================
# Clinical → Sales Integration ViewSet (Fase 3)
# ============================================================================

class ClinicalChargeProposalViewSet(TenantQuerySetMixin, viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Proposals (Clinical → Sales Integration).
    
    Endpoints:
    - GET /api/v1/clinical/proposals/             - List proposals (with filters)
    - GET /api/v1/clinical/proposals/{id}/        - Detail with nested lines
    - POST /api/v1/clinical/proposals/{id}/send/  - Transition: draft → sent
    - POST /api/v1/clinical/proposals/{id}/accept/ - Transition: sent → accepted (creates Sale + TreatmentPlans)
    - POST /api/v1/clinical/proposals/{id}/cancel/ - Transition: draft|sent → cancelled
    - POST /api/v1/clinical/proposals/{id}/create_sale/ - Convert proposal to sale (legacy)
    
    Permissions:
    - ClinicalOps/Practitioner: Generate proposals (via Encounter viewset)
    - Reception: View proposals + convert to sale
    - Admin: Full access
    - Accounting: Read-only
    - Marketing: No access
    
    Query params:
    - ?status=draft|sent|accepted|cancelled|expired - Filter by status
    - ?patient={patient_id} - Filter by patient
    - ?encounter={encounter_id} - Filter by encounter
    """
    permission_classes = [ProposalPermission]
    
    def get_queryset(self):
        """
        Return proposals with optional filters.
        
        Query params:
        - status: Filter by proposal status
        - patient: Filter by patient ID
        - encounter: Filter by encounter ID
        """
        queryset = Proposal.objects.select_related(
            'patient',
            'practitioner',
            'encounter',
            'converted_to_sale',
            'created_by'
        ).prefetch_related('lines')
        
        # Filter by status
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        
        # Filter by patient
        patient_id = self.request.query_params.get('patient')
        if patient_id:
            queryset = queryset.filter(patient_id=patient_id)
        
        # Filter by encounter
        encounter_id = self.request.query_params.get('encounter')
        if encounter_id:
            queryset = queryset.filter(encounter_id=encounter_id)
        
        return queryset.order_by('-created_at')
    
    def get_serializer_class(self):
        """Use different serializers for list vs detail."""
        if self.action == 'list':
            return ProposalListSerializer
        elif self.action == 'create_sale':
            return CreateSaleFromProposalSerializer
        # send_proposal, accept_proposal, cancel_proposal return detail
        return ProposalDetailSerializer
    
    @action(detail=True, methods=['post'], url_path='create-sale')
    def create_sale(self, request, pk=None):
        """
        Convert proposal to Sale (draft status).
        
        POST /api/v1/clinical/proposals/{id}/create-sale/
        
        Body:
        {
            "legal_entity_id": "uuid",
            "notes": "optional notes"
        }
        
        Returns:
        {
            "sale_id": "uuid",
            "message": "Success message"
        }
        """
        from apps.clinical.services import create_sale_from_proposal
        from apps.legal.models import LegalEntity
        from django.core.exceptions import ValidationError as DjangoValidationError
        
        proposal = self.get_object()
        
        # Validate input
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        legal_entity_id = serializer.validated_data['legal_entity_id']
        notes = serializer.validated_data.get('notes', '')
        
        # Get legal entity
        try:
            legal_entity = LegalEntity.objects.get(id=legal_entity_id)
        except LegalEntity.DoesNotExist:
            return Response(
                {'error': f"Legal entity {legal_entity_id} not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create sale from proposal
        try:
            sale = create_sale_from_proposal(
                proposal=proposal,
                created_by=request.user,
                legal_entity=legal_entity,
                notes=notes
            )
            
            return Response({
                'sale_id': str(sale.id),
                'message': f"Proposal {proposal.id} converted to sale {sale.id}",
                'sale_status': sale.status,
                'sale_total': str(sale.total)
            }, status=status.HTTP_201_CREATED)
            
        except (ValidationError, DjangoValidationError) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    # ------------------------------------------------------------------
    # State-machine transition actions (FASE 2B)
    # ------------------------------------------------------------------

    @action(detail=True, methods=['post'], url_path='send')
    def send_proposal(self, request, pk=None):
        """
        Transition proposal: draft → sent.

        POST /api/v1/clinical/proposals/{id}/send/
        """
        from django.core.exceptions import ValidationError as DjangoValidationError

        proposal = self.get_object()
        try:
            proposal.send(request.user)
            log_event(
                user=request.user,
                legal_entity=proposal.legal_entity,
                entity_type='Proposal',
                entity_id=proposal.pk,
                event_type=AuditEventType.PROPOSAL_SENT,
                payload={'patient_id': str(proposal.patient_id)},
            )
            return Response(
                ProposalDetailSerializer(proposal).data,
                status=status.HTTP_200_OK,
            )
        except (ValidationError, DjangoValidationError) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=['post'], url_path='accept')
    def accept_proposal(self, request, pk=None):
        """
        Transition proposal: sent → accepted.

        POST /api/v1/clinical/proposals/{id}/accept/
        Body: { "legal_entity_id": "<uuid>" }

        Creates Sale + SaleLines + TreatmentPlans atomically.
        """
        from apps.legal.models import LegalEntity
        from django.core.exceptions import ValidationError as DjangoValidationError

        proposal = self.get_object()

        legal_entity_id = request.data.get('legal_entity_id')
        if not legal_entity_id:
            return Response(
                {'error': 'legal_entity_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            legal_entity = LegalEntity.objects.get(id=legal_entity_id)
        except LegalEntity.DoesNotExist:
            return Response(
                {'error': f'Legal entity {legal_entity_id} not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            proposal.accept(request.user, legal_entity=legal_entity)
            log_event(
                user=request.user,
                legal_entity=proposal.legal_entity,
                entity_type='Proposal',
                entity_id=proposal.pk,
                event_type=AuditEventType.PROPOSAL_ACCEPTED,
                payload={'patient_id': str(proposal.patient_id), 'total_amount': str(proposal.total_amount)},
            )
            return Response(
                ProposalDetailSerializer(proposal).data,
                status=status.HTTP_200_OK,
            )
        except (ValidationError, DjangoValidationError) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel_proposal(self, request, pk=None):
        """
        Transition proposal: draft | sent → cancelled.

        POST /api/v1/clinical/proposals/{id}/cancel/
        Body: { "cancellation_reason": "optional reason" }
        """
        from django.core.exceptions import ValidationError as DjangoValidationError

        proposal = self.get_object()
        reason = request.data.get('cancellation_reason', '')

        try:
            proposal.cancel(request.user, reason=reason)
            log_event(
                user=request.user,
                legal_entity=proposal.legal_entity,
                entity_type='Proposal',
                entity_id=proposal.pk,
                event_type=AuditEventType.PROPOSAL_CANCELLED,
                payload={'reason': reason, 'patient_id': str(proposal.patient_id)},
            )
            return Response(
                ProposalDetailSerializer(proposal).data,
                status=status.HTTP_200_OK,
            )
        except (ValidationError, DjangoValidationError) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

# ============================================================================
# Calendar View (Sprint 1: Agenda Read-Only)
# ============================================================================

class PractitionerCalendarView(APIView):
    """
    Unified calendar feed for a practitioner.
    
    Returns appointments + blocks in a normalized JSON format for calendar display.
    
    Endpoint: GET /api/v1/clinical/practitioners/{practitioner_id}/calendar/
    
    Query params:
    - date_from: YYYY-MM-DD (required)
    - date_to: YYYY-MM-DD (required)
    
    Permissions:
    - Admin: Can view any practitioner
    - Practitioner: Can view only their own calendar
    - Reception: Can view any practitioner (read-only)
    - Accounting: Forbidden (403)
    - Marketing: Forbidden (403)
    
    Business rules:
    - Appointments with is_deleted=True are excluded
    - Blocks with is_deleted=True are excluded
    - Events are sorted by start time
    - Timezone: All datetimes are in UTC (frontend must localize)
    """
    
    def get(self, request, practitioner_id):
        """
        Get calendar events for a practitioner within a date range.
        """
        from datetime import datetime, time
        from django.utils import timezone
        from apps.authz.models import Practitioner
        
        # ========================
        # 1. PERMISSION CHECK
        # ========================
        _check_calendar_rbac(request, practitioner_id)
        
        # ========================
        # 2. VALIDATE PRACTITIONER
        # ========================
        try:
            practitioner = Practitioner.objects.get(id=practitioner_id)
        except Practitioner.DoesNotExist:
            return Response(
                {'error': f"Practitioner {practitioner_id} not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # ========================
        # 3. VALIDATE DATE PARAMS
        # ========================
        date_from, date_to, err = _parse_date_range(request)
        if err:
            return err
        
        # Convert to timezone-aware datetimes (start of day to end of day)
        datetime_from = timezone.make_aware(datetime.combine(date_from, time.min))
        datetime_to = timezone.make_aware(datetime.combine(date_to, time.max))
        
        # ========================
        # 4. FETCH APPOINTMENTS
        # ========================
        appointments = Appointment.objects.filter(
            practitioner=practitioner,
            is_deleted=False,
            patient__is_deleted=False,
            scheduled_start__gte=datetime_from,
            scheduled_start__lte=datetime_to,
        ).select_related('patient', 'practitioner', 'practitioner__user').order_by('scheduled_start')
        
        # ========================
        # 5. FETCH BLOCKS
        # ========================
        blocks = PractitionerBlock.objects.filter(
            practitioner=practitioner,
            is_deleted=False,
            start__gte=datetime_from,
            start__lte=datetime_to,
        ).select_related('practitioner', 'practitioner__user').order_by('start')
        
        # ========================
        # 6. MERGE & SERIALIZE
        # ========================
        # Combine appointments and blocks into a single list
        events = list(appointments) + list(blocks)
        
        # Sort by start time
        events.sort(key=lambda e: e.scheduled_start if isinstance(e, Appointment) else e.start)
        
        # Serialize
        serializer = CalendarEventSerializer(events, many=True)
        
        return Response({
            'practitioner_id': str(practitioner.id),
            'practitioner_name': f"{practitioner.user.first_name} {practitioner.user.last_name}",
            'date_from': str(date_from),
            'date_to': str(date_to),
            'events': serializer.data,
            'total_events': len(events),
        }, status=status.HTTP_200_OK)


class PractitionerAvailabilityView(APIView):
    """
    GET /api/v1/clinical/practitioners/{practitioner_id}/availability/
    
    Calculate available time slots for a practitioner at a specific clinic.
    
    Query params:
        - clinic_id (required): UUID of the clinic
        - date_from (required): YYYY-MM-DD
        - date_to (required): YYYY-MM-DD
        - treatment_id (optional): UUID — overrides slot_duration with Treatment.duration_minutes
        - slot_duration (optional): minutes, default 30 (ignored when treatment_id set)
        - timezone (optional): default UTC
    
    RBAC Rules:
        - Admin: Can view any practitioner
        - Reception: Can view any practitioner
        - Practitioner: Can only view own availability
        - Marketing/Accounting: 403 Forbidden
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, practitioner_id):
        from apps.authz.models import Practitioner
        from apps.clinical.services import AvailabilityService
        from apps.core.models import Clinic
        from django.core.exceptions import ValidationError
        import logging
        
        logger = logging.getLogger(__name__)
        
        # RBAC
        _check_calendar_rbac(request, practitioner_id)
        
        # Validate practitioner exists
        try:
            Practitioner.objects.get(id=practitioner_id)
        except Practitioner.DoesNotExist:
            return Response({
                'error': 'Practitioner not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get query params — clinic_id is now required
        clinic_id_str = request.query_params.get('clinic_id')
        date_from_str = request.query_params.get('date_from')
        date_to_str = request.query_params.get('date_to')
        treatment_id_str = request.query_params.get('treatment_id')  # optional
        slot_duration = request.query_params.get('slot_duration', 30)
        timezone_str = request.query_params.get('timezone', 'UTC')
        
        # Validate required params
        if not clinic_id_str or not date_from_str or not date_to_str:
            return Response({
                'error': 'clinic_id, date_from and date_to are required',
                'details': {
                    'clinic_id': HINT_REQUIRED_UUID,
                    'date_from': 'Required format: YYYY-MM-DD',
                    'date_to': 'Required format: YYYY-MM-DD'
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        
        err = _validate_availability_params(clinic_id_str, date_from_str, date_to_str)
        if err:
            return err
        
        # Validate slot_duration
        try:
            slot_duration = int(slot_duration)
            if slot_duration < 5 or slot_duration > 240:
                raise ValueError()
        except (ValueError, TypeError):
            return Response({
                'error': 'Invalid slot_duration',
                'details': 'Must be integer between 5 and 240 minutes'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Calculate availability using service
        try:
            availability_data = AvailabilityService.calculate_availability(
                practitioner_id=str(practitioner_id),
                clinic_id=clinic_id_str,
                date_from=date_from_str,
                date_to=date_to_str,
                treatment_id=treatment_id_str,
                slot_duration=slot_duration,
                timezone_str=timezone_str,
            )
            
            return Response(availability_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error calculating availability: {str(e)}", exc_info=True)
            return Response({
                'error': 'Error calculating availability',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PractitionerBookingView(APIView):
    """
    POST /api/v1/clinical/practitioners/{practitioner_id}/book/
    
    Create an appointment by booking an available slot.
    
    Sprint 3 Implementation:
    - Creates REAL appointments in DB
    - Validates slot is available using AvailabilityService
    - CRITICAL: Rejects slots that already started (slot_start <= now)
    - Prevents double booking
    - Prevents booking over PractitionerBlocks
    - RBAC enforced (same as availability)
    
    Request Body:
        {
            "date": "YYYY-MM-DD",
            "start": "HH:MM",
            "end": "HH:MM",
            "slot_duration": 30,
            "patient_id": "uuid",
            "clinic_id": "uuid",
            "notes": "string (optional)"
        }
    
    RBAC Rules:
        - Admin: Can book for any practitioner
        - Reception: Can book for any practitioner
        - Practitioner: Can only book for themselves
        - Marketing/Accounting: 403 Forbidden
    
    Validations:
        - slot_start > now (STRICT: no slots that already started)
        - start < end
        - No overlap with existing appointments
        - No overlap with PractitionerBlocks
        - Slot must appear in AvailabilityService calculation
    
    Returns:
        201 CREATED: Appointment created successfully
        400 BAD REQUEST: Invalid slot or slot already started
        403 FORBIDDEN: Permission denied
        409 CONFLICT: Slot already booked or blocked
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, practitioner_id):
        from apps.authz.models import Practitioner
        from apps.clinical.services import AvailabilityService
        from apps.core.models import Clinic
        from datetime import datetime, timedelta
        from django.utils import timezone as django_timezone
        import pytz
        import logging
        
        logger = logging.getLogger(__name__)
        user = request.user
        
        # ========================
        # 1. RBAC CHECK (same as availability)
        # ========================
        _check_calendar_rbac(request, practitioner_id)
        
        # Validate practitioner exists
        try:
            practitioner = Practitioner.objects.get(id=practitioner_id)
        except Practitioner.DoesNotExist:
            return Response({
                'error': 'Practitioner not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # ========================
        # 2. VALIDATE REQUEST DATA
        # ========================
        date_str = request.data.get('date')
        start_str = request.data.get('start')
        end_str = request.data.get('end')
        slot_duration = request.data.get('slot_duration', 30)
        patient_id = request.data.get('patient_id')
        clinic_id = request.data.get('clinic_id') or request.data.get('location_id')  # backward compat
        treatment_id = request.data.get('treatment_id')  # optional
        notes = request.data.get('notes', '')
        
        # Required fields
        if not all([date_str, start_str, end_str, patient_id, clinic_id]):
            return Response({
                'error': 'Missing required fields',
                'details': {
                    'date': 'Required (YYYY-MM-DD)',
                    'start': 'Required (HH:MM)',
                    'end': 'Required (HH:MM)',
                    'patient_id': HINT_REQUIRED_UUID,
                    'clinic_id': HINT_REQUIRED_UUID
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Parse and validate slot times
        result = _parse_booking_slot(date_str, start_str, end_str)
        if isinstance(result, Response):
            return result
        slot_start_dt, slot_end_dt = result
        
        # ========================
        # 3. CRITICAL VALIDATION: Reject slots that already started
        # ========================
        now = django_timezone.now()
        if slot_start_dt <= now:
            return Response({
                'error': 'Slot already started',
                'details': f'Cannot book slot starting at {start_str}. Current time is {now.strftime("%H:%M")} UTC. Slot must start in the future.',
                'slot_start': slot_start_dt.isoformat(),
                'current_time': now.isoformat()
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # ================================================================
        # TRANSACTIONAL BOOKING (Steps 4-6)
        #
        # Wrapped in transaction.atomic() to prevent race conditions.
        # The availability check + appointment creation happen atomically.
        # The DB ExclusionConstraint 'prevent_practitioner_overbooking'
        # is the final safety net: if two concurrent requests pass the
        # application-level check, the constraint will reject the second
        # INSERT, raising IntegrityError → HTTP 409.
        # ================================================================
        try:
            with transaction.atomic():
                # Lock the practitioner's active appointments to serialize
                # concurrent booking attempts for the same practitioner.
                Appointment.unfiltered.select_for_update().filter(
                    practitioner_id=practitioner_id,
                    status__in=Appointment._ACTIVE_STATUSES,
                    is_deleted=False,
                ).exists()

                # ========================
                # 4. VALIDATE SLOT IS AVAILABLE (using AvailabilityService)
                # ========================
                err = _check_slot_available(
                    AvailabilityService, practitioner_id, clinic_id,
                    date_str, start_str, end_str, treatment_id, slot_duration,
                )
                if err:
                    return err

                # ========================
                # 5. VALIDATE PATIENT AND CLINIC
                # ========================
                try:
                    patient = Patient.objects.get(id=patient_id)
                except Patient.DoesNotExist:
                    return Response({
                        'error': 'Patient not found',
                        'details': f'No patient with ID {patient_id}'
                    }, status=status.HTTP_404_NOT_FOUND)

                try:
                    clinic = Clinic.objects.get(id=clinic_id)
                except Clinic.DoesNotExist:
                    return Response({
                        'error': 'Clinic not found',
                        'details': f'No clinic with ID {clinic_id}'
                    }, status=status.HTTP_404_NOT_FOUND)

                # ========================
                # 6. CREATE APPOINTMENT
                # ========================
                create_kwargs = {
                    'practitioner': practitioner,
                    'patient': patient,
                    'clinic': clinic,
                    'scheduled_start': slot_start_dt,
                    'scheduled_end': slot_end_dt,
                    'status': 'scheduled',
                    'source': 'erp',
                    'notes': notes,
                }
                if treatment_id:
                    from apps.clinical.models import Treatment
                    try:
                        create_kwargs['treatment'] = Treatment.objects.get(
                            id=treatment_id, is_active=True,
                        )
                    except Treatment.DoesNotExist:
                        return Response({
                            'error': 'Treatment not found or inactive',
                            'details': f'No active treatment with ID {treatment_id}',
                        }, status=status.HTTP_404_NOT_FOUND)
                appointment = Appointment.objects.create(**create_kwargs)

            # Outside transaction — log + respond
            logger.info(
                f"Appointment booked: {appointment.id} by {user.email} "
                f"for practitioner {practitioner.display_name} "
                f"on {date_str} {start_str}-{end_str}"
            )

            return Response({
                'success': True,
                'appointment_id': str(appointment.id),
                'practitioner_id': str(practitioner.id),
                'practitioner_name': practitioner.display_name,
                'patient_id': str(patient.id),
                'patient_name': f"{patient.first_name} {patient.last_name}",
                'scheduled_start': appointment.scheduled_start.isoformat(),
                'scheduled_end': appointment.scheduled_end.isoformat(),
                'status': appointment.status,
                'created_at': appointment.created_at.isoformat()
            }, status=status.HTTP_201_CREATED)

        except (IntegrityError, OperationalError) as e:
            # IntegrityError: exclusion constraint violation (overlap detected).
            # OperationalError: deadlock from concurrent constraint checks —
            # semantically equivalent (two bookings raced, one must lose).
            logger.warning(f"Overbooking prevented by DB constraint: {e}")
            return Response({
                'error': 'The selected time slot is no longer available.',
                'details': 'Another appointment was booked for this practitioner at the same time.'
            }, status=status.HTTP_409_CONFLICT)
        except Exception as e:
            logger.error(f"Error creating appointment: {str(e)}", exc_info=True)
            return Response({
                'error': 'Error creating appointment',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)