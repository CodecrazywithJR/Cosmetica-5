"""
Clinical viewsets for Patient and PatientGuardian.
Based on API_CONTRACTS.md PAC section.
"""
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, PermissionDenied
from django.db.models import Q
from django.db import transaction, IntegrityError
from apps.clinical.models import (
    Patient,
    PatientGuardian,
    Encounter,
    Appointment,
    Consent,
    ClinicalPhoto,
)
from apps.clinical.serializers import (
    PatientListSerializer,
    PatientDetailSerializer,
    PatientGuardianSerializer,
    AppointmentListSerializer,
    AppointmentDetailSerializer,
    AppointmentWriteSerializer,
)
from apps.clinical.permissions import (
    PatientPermission,
    GuardianPermission,
    AppointmentPermission,
)


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
        is_admin = 'Admin' in user_roles
        
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
        if not (user_roles & {'Admin', 'Practitioner'}):
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
        is_admin = 'Admin' in user_roles
        
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
        if 'Admin' not in user_roles:
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
        
        # Validate required fields
        external_id = request.data.get('external_id')
        scheduled_start_raw = request.data.get('scheduled_start')
        scheduled_end_raw = request.data.get('scheduled_end')
        
        if not external_id:
            return Response(
                {'error': 'external_id es obligatorio'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not scheduled_start_raw or not scheduled_end_raw:
            return Response(
                {'error': 'scheduled_start y scheduled_end son obligatorios'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse and validate datetime fields
        try:
            # Parse datetimes (DRF already parses them, but we validate explicitly)
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
        
        # DEFENSIVE: Validate timezone-aware datetimes if USE_TZ=True
        if settings.USE_TZ:
            from django.utils.timezone import is_aware
            if not is_aware(scheduled_start) or not is_aware(scheduled_end):
                return Response(
                    {'error': 'scheduled_start y scheduled_end deben incluir timezone'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # DEFENSIVE: Validate scheduled_end > scheduled_start (prevent negative/zero duration)
        if scheduled_end <= scheduled_start:
            return Response(
                {'error': 'scheduled_end debe ser posterior a scheduled_start'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Extract patient data
        patient_email = request.data.get('patient_email')
        patient_phone = request.data.get('patient_phone')
        patient_first_name = request.data.get('patient_first_name', '')
        patient_last_name = request.data.get('patient_last_name', '')
        
        # CRITICAL: Wrap in atomic transaction to prevent race conditions on external_id
        # Without atomic + get_or_create pattern, concurrent requests with same external_id
        # could both pass the "if not appointment" check and cause IntegrityError on unique constraint.
        with transaction.atomic():
            # Find or create patient
            patient = None
            
            # DEFENSIVE: Patient lookup by email (priority) vs phone_e164 (fallback).
            # RISK: If email→Patient A and phone→Patient B, we use Patient A (email priority).
            # This could be ambiguous if Calendly data is inconsistent.
            # DECISION: Email priority is intentional behavior, deferred to product requirements.
            
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
                    created_by_user=request.user
                )
            
            # CRITICAL: Use get_or_create pattern to prevent race conditions on external_id.
            # DEFENSIVE: In extremely rare cases, concurrent requests may both try to create
            # the same external_id simultaneously. If get_or_create raises IntegrityError,
            # we retry with a simple get() to fetch the record created by the concurrent request.
            # This ensures guaranteed idempotency even under high concurrency.
            try:
                appointment, created = Appointment.objects.get_or_create(
                    external_id=external_id,
                    defaults={
                        'patient': patient,
                        'source': 'calendly',
                        'scheduled_start': scheduled_start,
                        'scheduled_end': scheduled_end,
                        'status': request.data.get('status', 'scheduled'),
                        'practitioner_id': request.data.get('practitioner_id'),
                        'location_id': request.data.get('location_id'),
                        'notes': request.data.get('notes'),
                    }
                )
            except IntegrityError:
                # DEFENSIVE: Race condition detected - another request created this external_id
                # between our check and create. Fetch the existing record and treat as update.
                appointment = Appointment.objects.get(external_id=external_id)
                created = False
            
            if not created:
                # Update existing appointment
                
                # DEFENSIVE: Allow patient change on update.
                # RISK: This can break clinical traceability if appointment is linked to an encounter
                # (appointment→encounter→patient mismatch). Changing patient may orphan clinical data.
                # DECISION: Intentional behavior for now, deferred to clinical/product requirements.
                appointment.patient = patient
                
                appointment.scheduled_start = scheduled_start
                appointment.scheduled_end = scheduled_end
                
                # Update optional fields if provided
                if 'practitioner_id' in request.data:
                    appointment.practitioner_id = request.data['practitioner_id']
                if 'location_id' in request.data:
                    appointment.location_id = request.data['location_id']
                if 'status' in request.data:
                    appointment.status = request.data['status']
                if 'notes' in request.data:
                    appointment.notes = request.data['notes']
                
                # DEFENSIVE: Updating appointment even if is_deleted=True.
                # RISK: This "resurrects" soft-deleted appointments without explicit undelete logic,
                # which may bypass audit trails or business rules around deletion.
                # DECISION: Intentional behavior for now (Calendly sync has priority over soft-delete),
                # deferred to product requirements on whether to block or log this scenario.
                
                appointment.save()
            
            serializer = AppointmentDetailSerializer(appointment)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
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
        allowed_roles = {'Admin', 'Practitioner', 'Reception'}
        
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
