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
from django.db.models import Q
from django.db import transaction, IntegrityError
from apps.authz.models import RoleChoices
from apps.clinical.models import (
    Patient,
    PatientGuardian,
    Encounter,
    Appointment,
    Consent,
    ClinicalPhoto,
    Treatment,
    EncounterTreatment,
    ClinicalChargeProposal,
)
from apps.clinical.serializers import (
    PatientListSerializer,
    PatientDetailSerializer,
    PatientGuardianSerializer,
    AppointmentListSerializer,
    AppointmentDetailSerializer,
    AppointmentWriteSerializer,
    EncounterListSerializer,
    EncounterDetailSerializer,
    EncounterWriteSerializer,
    TreatmentSerializer,
)
from apps.clinical.serializers_proposals import (
    ClinicalChargeProposalListSerializer,
    ClinicalChargeProposalDetailSerializer,
    CreateSaleFromProposalSerializer,
)
from apps.clinical.permissions import (
    PatientPermission,
    GuardianPermission,
    AppointmentPermission,
    TreatmentPermission,
    EncounterPermission,
    ClinicalChargeProposalPermission,
)

logger = logging.getLogger(__name__)
class PatientViewSet(viewsets.ModelViewSet):
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
        queryset = Patient.objects.select_related('referral_source')
        
        # Check if user is Admin
        user_roles = set(
            self.request.user.user_roles.values_list('role__name', flat=True)
        )
        is_admin = RoleChoices.ADMIN in user_roles
        
        # Handle include_deleted parameter
        include_deleted = self.request.query_params.get('include_deleted', 'false').lower() == 'true'
        
        if include_deleted and is_admin:
            # Admin can see deleted patients with ?include_deleted=true
            pass  # Return all patients
        else:
            # Default: exclude soft-deleted
            queryset = queryset.filter(is_deleted=False)
        
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
        
        return queryset
    
    def get_serializer_class(self):
        """Use list serializer for list view, detail serializer otherwise"""
        if self.action == 'list':
            return PatientListSerializer
        return PatientDetailSerializer
    
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
        return Response(
            detail_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )
    
    def perform_create(self, serializer):
        """Save with audit fields"""
        serializer.save()
    
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
        
        return Response(serializer.data)
    
    def perform_update(self, serializer):
        """Save update"""
        serializer.save()
    
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
                                'message': 'No se puede realizar el merge',
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
                                'message': 'No se puede realizar el merge',
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
                                'message': 'No se puede realizar el merge',
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
                                'message': 'No se puede realizar el merge',
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


class GuardianViewSet(viewsets.ModelViewSet):
    """
    ViewSet for PatientGuardian endpoints.
    
    Endpoints:
    - PATCH /api/v1/guardians/{id}/
    - DELETE /api/v1/guardians/{id}/
    """
    queryset = PatientGuardian.objects.select_related('patient').all()
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


class AppointmentViewSet(viewsets.ModelViewSet):
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
        - location_id: Filter by location UUID
        - include_deleted: Show soft-deleted appointments (Admin only)
        """
        # Optimize with select_related
        queryset = Appointment.objects.select_related(
            'patient',
            'practitioner',
            'location',
            'encounter'
        )
        
        # Check if user is Admin
        user_roles = set(
            self.request.user.user_roles.values_list('role__name', flat=True)
        )
        is_admin = RoleChoices.ADMIN in user_roles
        
        # Handle include_deleted (Admin only)
        include_deleted = self.request.query_params.get('include_deleted', 'false').lower() == 'true'
        if include_deleted and is_admin:
            # Include deleted appointments
            pass
        else:
            # Exclude deleted appointments
            queryset = queryset.filter(is_deleted=False)
        
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
        
        # Filter by location_id
        location_id = self.request.query_params.get('location_id', None)
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        
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
        Create manual appointment (source=manual, external_id=null).
        """
        # Set source to manual if not provided
        data = request.data.copy()
        if 'source' not in data:
            data['source'] = 'manual'
        
        # Ensure external_id is null for manual appointments
        if data.get('source') == 'manual':
            data['external_id'] = None
        
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # Return detail serializer for response
        instance = serializer.instance
        response_serializer = AppointmentDetailSerializer(instance)
        
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, *args, **kwargs):
        """
        PATCH /api/v1/appointments/{id}/
        Update appointment with status transition validation.
        """
        partial = kwargs.pop('partial', True)  # Always partial for PATCH
        instance = self.get_object()
        
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        # Return detail serializer for response
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
        
        # Soft delete
        from django.utils import timezone
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save()
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['post'], url_path='transition')
    def transition_status(self, request, pk=None):
        """
        POST /api/v1/appointments/{id}/transition/
        
        Transition appointment to a new status with validation.
        
        BUSINESS RULES:
        - Only allowed transitions are permitted (see model)
        - no_show can only be set after scheduled_start has passed
        - Terminal states (completed, cancelled, no_show) cannot be changed
        
        Request body:
        {
            "status": "confirmed",  # New status
            "reason": "Patient requested cancellation"  # Optional reason for cancel/no_show
        }
        
        Allowed transitions:
        - draft -> confirmed | cancelled
        - confirmed -> checked_in | cancelled | no_show
        - checked_in -> completed | cancelled
        
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
                
                # Return updated appointment
                serializer = AppointmentDetailSerializer(appointment)
                return Response(serializer.data, status=status.HTTP_200_OK)
                
        except DjangoValidationError as e:
            return Response(
                {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    

def _process_calendly_sync(sync_data, created_by_user=None):
    """
    Internal function: Process Calendly sync (shared by webhook and manual endpoint).
    
    This function contains the core logic for creating/updating appointments from Calendly.
    It's called by both:
    - AppointmentViewSet.calendly_sync() (manual endpoint)
    - calendly_webhook() (automatic webhook)
    
    Args:
        sync_data (dict): Appointment data with keys:
            - external_id (str, required): Calendly event ID
            - scheduled_start (datetime, required): Start time (timezone-aware)
            - scheduled_end (datetime, required): End time (timezone-aware)
            - patient_email (str, optional): Patient email for lookup
            - patient_phone (str, optional): Patient phone for lookup
            - patient_first_name (str, optional): Patient first name
            - patient_last_name (str, optional): Patient last name
            - practitioner_id (UUID, optional): Practitioner ID
            - location_id (UUID, optional): Location ID
            - status (str, optional): Appointment status (default: 'scheduled')
            - notes (str, optional): Appointment notes
        created_by_user (User, optional): User who triggered the sync (None for webhook)
    
    Returns:
        tuple: (appointment: Appointment, created: bool)
    
    Raises:
        ValueError: If validation fails
        IntegrityError: If database constraint fails (unlikely due to get_or_create)
    """
    from django.db import transaction
    from django.db import IntegrityError
    
    # Extract and validate required fields
    external_id = sync_data.get('external_id')
    scheduled_start = sync_data.get('scheduled_start')
    scheduled_end = sync_data.get('scheduled_end')
    
    if not external_id:
        raise ValueError('external_id es obligatorio')
    
    if not scheduled_start or not scheduled_end:
        raise ValueError('scheduled_start y scheduled_end son obligatorios')
    
    # Validate datetime types and timezone awareness
    from django.utils.timezone import is_aware
    from django.conf import settings
    
    if settings.USE_TZ:
        if not is_aware(scheduled_start) or not is_aware(scheduled_end):
            raise ValueError('scheduled_start y scheduled_end deben incluir timezone')
    
    if scheduled_end <= scheduled_start:
        raise ValueError('scheduled_end debe ser posterior a scheduled_start')
    
    # Extract patient data
    patient_email = sync_data.get('patient_email')
    patient_phone = sync_data.get('patient_phone')
    patient_first_name = sync_data.get('patient_first_name', '')
    patient_last_name = sync_data.get('patient_last_name', '')
    
    # CRITICAL: Wrap in atomic transaction to prevent race conditions
    with transaction.atomic():
        # Find or create patient
        patient = None
        
        # Try to find by email first (priority)
        if patient_email:
            patient = Patient.objects.filter(
                email=patient_email,
                is_deleted=False
            ).first()
        
        # If not found by email, try phone_e164
        if not patient and patient_phone:
            # Normalize phone to E.164 if needed (basic normalization)
            phone_e164 = patient_phone.strip()
            if not phone_e164.startswith('+'):
                phone_e164 = f'+{phone_e164}'
            
            patient = Patient.objects.filter(
                phone_e164=phone_e164,
                is_deleted=False
            ).first()
        
        # Create minimal patient if not found
        if not patient:
            full_name_normalized = f"{patient_first_name} {patient_last_name}".strip().lower()
            
            patient = Patient.objects.create(
                first_name=patient_first_name or 'Calendly',
                last_name=patient_last_name or 'Patient',
                full_name_normalized=full_name_normalized or 'calendly patient',
                email=patient_email or None,
                phone=patient_phone or None,
                phone_e164=phone_e164 if patient_phone else None,
                identity_confidence='low',
                created_by_user=created_by_user
            )
        
        # CRITICAL: Use get_or_create pattern to prevent race conditions on external_id
        try:
            appointment, created = Appointment.objects.get_or_create(
                external_id=external_id,
                defaults={
                    'patient': patient,
                    'source': 'calendly',
                    'scheduled_start': scheduled_start,
                    'scheduled_end': scheduled_end,
                    'status': sync_data.get('status', 'scheduled'),
                    'practitioner_id': sync_data.get('practitioner_id'),
                    'location_id': sync_data.get('location_id'),
                    'notes': sync_data.get('notes'),
                }
            )
        except IntegrityError:
            # DEFENSIVE: Race condition detected - fetch existing record
            appointment = Appointment.objects.get(external_id=external_id)
            created = False
        
        if not created:
            # Update existing appointment
            appointment.patient = patient
            appointment.scheduled_start = scheduled_start
            appointment.scheduled_end = scheduled_end
            
            # Update optional fields if provided
            if 'practitioner_id' in sync_data:
                appointment.practitioner_id = sync_data['practitioner_id']
            if 'location_id' in sync_data:
                appointment.location_id = sync_data['location_id']
            if 'status' in sync_data:
                appointment.status = sync_data['status']
            if 'notes' in sync_data:
                appointment.notes = sync_data['notes']
            
            appointment.save()
        
        return appointment, created


class AppointmentViewSet(viewsets.ModelViewSet):
    """Appointment API ViewSet."""
    
    # ... (resto del código del ViewSet)
    
    @action(detail=False, methods=['post'], url_path='calendly/sync')
    def calendly_sync(self, request):
        """
        POST /api/v1/appointments/calendly/sync/
        Sync appointment from Calendly (idempotent by external_id).
        
        Creates or updates appointment with source='calendly'.
        If patient doesn't exist, creates minimal patient record.
        If patient exists, finds by email or phone_e164 (email priority).
        
        Default status: 'scheduled'
        
        Request body:
        {
            "external_id": "calendly_event_id",
            "scheduled_start": "2025-12-15T10:00:00Z",
            "scheduled_end": "2025-12-15T11:00:00Z",
            "patient_email": "patient@example.com",
            "patient_phone": "+34600000000",
            "patient_first_name": "John",
            "patient_last_name": "Doe",
            "practitioner_id": "uuid",
            "location_id": "uuid",
            "status": "scheduled|confirmed"
        }
        """
        from django.conf import settings
        from django.utils.dateparse import parse_datetime
        
        # Parse and validate datetime fields
        scheduled_start_raw = request.data.get('scheduled_start')
        scheduled_end_raw = request.data.get('scheduled_end')
        
        # Parse datetimes if they are strings
        try:
            if isinstance(scheduled_start_raw, str):
                scheduled_start = parse_datetime(scheduled_start_raw)
                if not scheduled_start:
                    raise ValueError("Invalid scheduled_start format")
            else:
                scheduled_start = scheduled_start_raw
            
            if isinstance(scheduled_end_raw, str):
                scheduled_end = parse_datetime(scheduled_end_raw)
                if not scheduled_end:
                    raise ValueError("Invalid scheduled_end format")
            else:
                scheduled_end = scheduled_end_raw
        except (ValueError, TypeError) as e:
            return Response(
                {'error': f'Formato de fecha inválido: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Build sync_data dict
        sync_data = {
            'external_id': request.data.get('external_id'),
            'scheduled_start': scheduled_start,
            'scheduled_end': scheduled_end,
            'patient_email': request.data.get('patient_email'),
            'patient_phone': request.data.get('patient_phone'),
            'patient_first_name': request.data.get('patient_first_name', ''),
            'patient_last_name': request.data.get('patient_last_name', ''),
            'practitioner_id': request.data.get('practitioner_id'),
            'location_id': request.data.get('location_id'),
            'status': request.data.get('status', 'scheduled'),
            'notes': request.data.get('notes'),
        }
        
        # Call shared sync logic
        try:
            appointment, created = _process_calendly_sync(sync_data, created_by_user=request.user)
            serializer = AppointmentDetailSerializer(appointment)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], url_path='link-encounter')
    def link_encounter(self, request, pk=None):
        """
        POST /api/v1/appointments/{id}/link-encounter/
        Link or unlink appointment to/from encounter.
        
        Permissions: Admin, Practitioner, Reception (403 for Accounting/Marketing)
        
        Link (encounter_id = uuid):
        - appointment.status cannot be 'cancelled' or 'no_show' (409)
        - encounter must exist and not be deleted (404/409)
        - encounter.patient_id must match appointment.patient_id (409)
        - 1:1 relationship: appointment cannot have different encounter already (409)
        - ON LINK: appointment.status → 'attended' (idempotent si ya attended)
        
        Unlink (encounter_id = null):
        - appointment must have encounter (409)
        - Cannot unlink if status is terminal (cancelled/no_show) → 409
        - ON UNLINK: appointment.status → 'confirmed' (solo si no terminal)
        
        Request body:
        {
            "encounter_id": "uuid or null"
        }
        
        Response 200:
        {
            "appointment_id": "uuid",
            "encounter_id": "uuid or null",
            "linked": true or false,
            "status": "current appointment status"
        }
        """
        # Permission check: Admin, Practitioner, Reception
        user_roles = set(
            request.user.user_roles.values_list('role__name', flat=True)
        )
        allowed_roles = {RoleChoices.ADMIN, RoleChoices.PRACTITIONER, RoleChoices.RECEPTION}
        
        if not (user_roles & allowed_roles):
            raise PermissionDenied(
                "Solo Admin, Practitioner y Reception pueden vincular encuentros"
            )
        
        with transaction.atomic():
            # Select for update to prevent race conditions
            appointment = Appointment.objects.select_for_update().get(pk=pk)
            
            # Validation: Cannot operate on deleted appointment
            if appointment.is_deleted:
                return Response(
                    {'error': 'No se puede vincular una cita eliminada'},
                    status=status.HTTP_409_CONFLICT
                )
            
            encounter_id = request.data.get('encounter_id')
            
            if encounter_id:
                # LINK to encounter
                
                # NOTE: Normalize and validate UUID format to return 400 BAD_REQUEST early.
                # This prevents weird inputs (None via truthy check above, integers, malformed strings)
                # from reaching DB layer. Covered by: test_link_invalid_encounter_id_format,
                # test_link_uuid_validation_empty_string, test_link_uuid_validation_integer.
                try:
                    from uuid import UUID
                    encounter_uuid = UUID(str(encounter_id))
                except (ValueError, AttributeError, TypeError):
                    return Response(
                        {'error': 'encounter_id debe ser un UUID válido'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Rationale: Idempotent link to same encounter. If already linked, ensure status='attended'
                # (hardening) and return 200 without additional side-effects. Prevents unnecessary DB writes
                # and potential race conditions. Covered by: test_link_encounter_already_linked_to_same_is_idempotent,
                # test_link_idempotence_updates_status_when_needed, test_link_multiple_times_to_same_encounter.
                if appointment.encounter_id and str(appointment.encounter_id) == str(encounter_id):
                    # Already linked to this exact encounter - ensure status is 'attended'
                    if appointment.status != 'attended':
                        appointment.status = 'attended'
                        appointment.save()
                    
                    return Response(
                        {
                            'appointment_id': str(appointment.id),
                            'encounter_id': str(encounter_id),
                            'linked': True,
                            'status': appointment.status
                        },
                    status=status.HTTP_200_OK
                )
                
                # NOTE: Block link for terminal statuses (business rule). Once an appointment is
                # cancelled or no_show, it represents a finalized state that should not be modified
                # to avoid audit trail corruption. Covered by: test_link_encounter_cancelled_status_rejected,
                # test_link_encounter_no_show_status_rejected.
                if appointment.status in ['cancelled', 'no_show']:
                    return Response(
                        {
                            'error': f'No se puede vincular una cita con status={appointment.status}'
                        },
                    status=status.HTTP_409_CONFLICT
                )
                
                # Rationale: Enforce 1:1 relationship (appointment ↔ encounter) to maintain traceability.
                # Each appointment can only link to ONE encounter at a time. Attempting to link to a different
                # encounter without unlinking first = 409 CONFLICT. Prevents orphaned data and ensures
                # audit integrity. Covered by: test_link_encounter_already_linked_to_different.
                if appointment.encounter_id and str(appointment.encounter_id) != str(encounter_id):
                    return Response(
                        {
                            'error': 'La cita ya está vinculada a otro encuentro'
                        },
                        status=status.HTTP_409_CONFLICT
                    )
                
                # Verify encounter exists and is not deleted
                try:
                    encounter = Encounter.objects.select_for_update().get(
                        pk=encounter_id,
                        is_deleted=False
                    )
                except Encounter.DoesNotExist:
                    return Response(
                        {'error': 'Encounter no encontrado o está eliminado'},
                    status=status.HTTP_404_NOT_FOUND
                )
                
                # NOTE: Validate patient match. IMPORTANT: Both appointment.patient_id and encounter.patient_id
                # can be None (data integrity issue). In Python, None == None evaluates to True, which would
                # pass this check silently, potentially allowing corrupted data links. This edge case is covered
                # by data integrity tests: test_link_appointment_with_null_patient, test_link_encounter_with_null_patient,
                # test_link_both_null_patients. Consider adding explicit null checks if strict validation is required.
                if encounter.patient_id != appointment.patient_id:
                    return Response(
                        {
                            'error': 'El encounter no pertenece al mismo paciente que la cita'
                        },
                        status=status.HTTP_409_CONFLICT
                    )
                
                # Link AND change status to 'attended'
                appointment.encounter_id = encounter_id
                appointment.status = 'attended'
                appointment.save()
                
                return Response(
                    {
                        'appointment_id': str(appointment.id),
                        'encounter_id': str(encounter_id),
                        'linked': True,
                        'status': appointment.status
                    },
                    status=status.HTTP_200_OK
                )
            else:
                # UNLINK from encounter
                
                # Validation: Cannot unlink if no encounter
                if not appointment.encounter_id:
                    return Response(
                        {'error': 'La cita no está vinculada a ningún encuentro'},
                    status=status.HTTP_409_CONFLICT
                )
                
                # NOTE: Block unlink for terminal statuses (business rule). Cannot unlink from cancelled/no_show
                # appointments to preserve audit trail and prevent status rollback to 'confirmed' on finalized
                # appointments. Covered by: test_unlink_encounter_cancelled_status_rejected,
                # test_unlink_encounter_no_show_status_rejected, test_unlink_atomicity_terminal_status.
                if appointment.status in ['cancelled', 'no_show']:
                    return Response(
                        {
                            'error': f'No se puede desvincular una cita con status={appointment.status} (terminal)'
                        },
                        status=status.HTTP_409_CONFLICT
                    )
                
                # Unlink AND change status to 'confirmed'
                appointment.encounter_id = None
                appointment.status = 'confirmed'
                appointment.save()
                
                return Response(
                    {
                        'appointment_id': str(appointment.id),
                        'encounter_id': None,
                        'linked': False,
                        'status': appointment.status
                    },
                    status=status.HTTP_200_OK
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
            source_patient = Patient.objects.get(id=data['source_patient_id'])
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

class TreatmentViewSet(viewsets.ModelViewSet):
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


class EncounterViewSet(viewsets.ModelViewSet):
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
        queryset = Encounter.objects.select_related('patient', 'practitioner', 'location')
        queryset = queryset.prefetch_related('encounter_treatments__treatment')
        queryset = queryset.filter(is_deleted=False)
        
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
        
        encounter = self.get_object()
        notes = request.data.get('notes', '')
        
        # Generate proposal (validation happens in service)
        try:
            proposal = generate_charge_proposal_from_encounter(
                encounter=encounter,
                created_by=request.user,
                notes=notes
            )
            
            return Response({
                'proposal_id': str(proposal.id),
                'message': f"Charge proposal generated from encounter {encounter.id}",
                'total_amount': str(proposal.total_amount),
                'line_count': proposal.lines.count(),
                'status': proposal.status
            }, status=status.HTTP_201_CREATED)
            
        except ValidationError as e:
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

class ClinicalChargeProposalViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for ClinicalChargeProposal (Clinical → Sales Integration).
    
    Endpoints:
    - GET /api/v1/clinical/proposals/             - List proposals (with filters)
    - GET /api/v1/clinical/proposals/{id}/        - Detail with nested lines
    - POST /api/v1/clinical/proposals/{id}/create_sale/ - Convert proposal to sale
    
    Permissions:
    - ClinicalOps/Practitioner: Generate proposals (via Encounter viewset)
    - Reception: View proposals + convert to sale
    - Admin: Full access
    - Accounting: Read-only
    - Marketing: No access
    
    Query params:
    - ?status=draft|converted|cancelled - Filter by status
    - ?patient={patient_id} - Filter by patient
    - ?encounter={encounter_id} - Filter by encounter
    """
    permission_classes = [ClinicalChargeProposalPermission]
    
    def get_queryset(self):
        """
        Return proposals with optional filters.
        
        Query params:
        - status: Filter by proposal status
        - patient: Filter by patient ID
        - encounter: Filter by encounter ID
        """
        from apps.clinical.models import ClinicalChargeProposal
        
        queryset = ClinicalChargeProposal.objects.select_related(
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
        from apps.clinical.serializers_proposals import (
            ClinicalChargeProposalListSerializer,
            ClinicalChargeProposalDetailSerializer,
            CreateSaleFromProposalSerializer
        )
        
        if self.action == 'list':
            return ClinicalChargeProposalListSerializer
        elif self.action == 'create_sale':
            return CreateSaleFromProposalSerializer
        return ClinicalChargeProposalDetailSerializer
    
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
            
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
