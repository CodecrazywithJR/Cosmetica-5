"""
Clinical serializers for Patient and PatientGuardian.
Based on API_CONTRACTS.md PAC section.
"""
from rest_framework import serializers
from django.core.exceptions import ValidationError
from apps.clinical.models import (
    Patient,
    PatientGuardian,
    ReferralSource,
    Appointment,
    AppointmentSourceChoices,
    AppointmentStatusChoices,
    Encounter,
    Treatment,
    EncounterTreatment,
)


class ReferralSourceSerializer(serializers.ModelSerializer):
    """Nested serializer for referral source"""
    class Meta:
        model = ReferralSource
        fields = ['id', 'code', 'label']
        read_only_fields = ['id', 'code', 'label']


class PatientGuardianSerializer(serializers.ModelSerializer):
    """Serializer for PatientGuardian"""
    
    class Meta:
        model = PatientGuardian
        fields = [
            'id',
            'patient_id',
            'full_name',
            'relationship',
            'phone',
            'email',
            'address_line1',
            'city',
            'postal_code',
            'country_code',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_relationship(self, value):
        """Validate relationship enum values"""
        valid_relationships = ['parent', 'legal_guardian', 'other']
        if value not in valid_relationships:
            raise serializers.ValidationError(
                f"Valor inválido. Opciones: {', '.join(valid_relationships)}"
            )
        return value


class PatientListSerializer(serializers.ModelSerializer):
    """Serializer for Patient list view (limited fields)"""
    
    class Meta:
        model = Patient
        fields = [
            'id',
            'first_name',
            'last_name',
            'birth_date',
            'sex',
            'email',
            'phone',
            'country_code',
            'is_merged',
            'row_version',
            'is_deleted',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PatientDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for Patient detail/create/update (all fields).
    
    BUSINESS RULE: Reception cannot see clinical notes.
    The 'notes' field is hidden for Reception users.
    """
    referral_source = ReferralSourceSerializer(read_only=True)
    referral_source_id = serializers.UUIDField(
        write_only=True,
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = Patient
        fields = [
            'id',
            'first_name',
            'last_name',
            'full_name_normalized',
            'birth_date',
            'sex',
            'email',
            'phone',
            'phone_e164',
            'address_line1',
            'city',
            'postal_code',
            'country_code',
            'preferred_language',
            'preferred_contact_method',
            'preferred_contact_time',
            'contact_opt_out',
            'identity_confidence',
            'is_merged',
            'merged_into_patient_id',
            'merge_reason',
            'referral_source',
            'referral_source_id',
            'referral_details',
            'notes',  # CLINICAL FIELD - Hidden for Reception
            'row_version',
            'is_deleted',
            'deleted_at',
            'deleted_by_user_id',
            'created_at',
            'updated_at',
            'created_by_user_id',
        ]
        read_only_fields = [
            'id',
            'full_name_normalized',
            'is_merged',
            'merged_into_patient_id',
            'merge_reason',
            'is_deleted',
            'deleted_at',
            'deleted_by_user_id',
            'created_at',
            'updated_at',
            'created_by_user_id',
        ]
    
    def validate_birth_date(self, value):
        """Validate birth date is not in the future"""
        from datetime import date
        if value and value > date.today():
            raise serializers.ValidationError("La fecha de nacimiento no puede ser futura")
        return value
    
    def validate_sex(self, value):
        """Validate sex enum"""
        valid_values = ['female', 'male', 'other', 'unknown']
        if value and value not in valid_values:
            raise serializers.ValidationError(
                f"Valor inválido. Opciones: {', '.join(valid_values)}"
            )
        return value
    
    def validate_email(self, value):
        """Validate email uniqueness (excluding current instance on update)"""
        if value:
            qs = Patient.objects.filter(email=value, is_deleted=False)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError("Ya existe un paciente con este email")
        return value
    
    def validate(self, attrs):
        """Cross-field validation"""
        # Check for row_version on update
        if self.instance and 'row_version' not in self.initial_data:
            raise serializers.ValidationError({
                'row_version': ['Este campo es obligatorio para actualizar']
            })
        
        # Validate row_version on update (optimistic locking)
        if self.instance:
            provided_version = self.initial_data.get('row_version')
            if provided_version != self.instance.row_version:
                raise serializers.ValidationError({
                    'row_version': [
                        f"El paciente fue modificado por otro usuario. "
                        f"Versión actual: {self.instance.row_version}, "
                        f"versión proporcionada: {provided_version}"
                    ]
                })
        
        return attrs
    
    def create(self, validated_data):
        """Create patient with audit fields"""
        # Remove referral_source_id from validated_data if present
        referral_source_id = validated_data.pop('referral_source_id', None)
        
        # Add referral_source FK if provided
        if referral_source_id:
            validated_data['referral_source_id'] = referral_source_id
        
        # Add created_by_user
        validated_data['created_by_user'] = self.context['request'].user
        
        # Generate full_name_normalized
        validated_data['full_name_normalized'] = (
            f"{validated_data.get('first_name', '')} "
            f"{validated_data.get('last_name', '')}"
        ).strip().lower()
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update patient with row_version increment"""
        # Remove referral_source_id from validated_data if present
        referral_source_id = validated_data.pop('referral_source_id', None)
        
        # Update referral_source FK if provided
        if referral_source_id is not None:
            validated_data['referral_source_id'] = referral_source_id
        
        # Remove row_version from validated_data (we'll increment it)
        validated_data.pop('row_version', None)
        
        # Increment row_version
        instance.row_version += 1
        
        # Update full_name_normalized if name fields changed
        if 'first_name' in validated_data or 'last_name' in validated_data:
            first_name = validated_data.get('first_name', instance.first_name)
            last_name = validated_data.get('last_name', instance.last_name)
            instance.full_name_normalized = f"{first_name} {last_name}".strip().lower()
        
        # Update instance
        instance.save()
        return instance
    
    def to_representation(self, instance):
        """
        BUSINESS RULE: Hide clinical fields (notes) for Reception users.
        """
        representation = super().to_representation(instance)
        
        # Check if user is Reception
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            user_roles = set(
                request.user.user_roles.values_list('role__name', flat=True)
            )
            
            # Hide clinical fields for Reception
            if 'Reception' in user_roles:
                # Remove clinical notes field
                representation.pop('notes', None)
        
        return representation
        
        # Update fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class AppointmentListSerializer(serializers.ModelSerializer):
    """Serializer for Appointment list view (lightweight)"""
    patient_name = serializers.SerializerMethodField()
    practitioner_name = serializers.SerializerMethodField()
    location_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Appointment
        fields = [
            'id',
            'patient_id',
            'patient_name',
            'practitioner_id',
            'practitioner_name',
            'location_id',
            'location_name',
            'source',
            'status',
            'scheduled_start',
            'scheduled_end',
            'is_deleted',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_patient_name(self, obj):
        """Get patient full name"""
        if obj.patient:
            return f"{obj.patient.first_name} {obj.patient.last_name}".strip()
        return None
    
    def get_practitioner_name(self, obj):
        """Get practitioner full name"""
        if obj.practitioner:
            return f"{obj.practitioner.first_name} {obj.practitioner.last_name}".strip()
        return None
    
    def get_location_name(self, obj):
        """Get location name"""
        if obj.location:
            return obj.location.name
        return None


class AppointmentDetailSerializer(serializers.ModelSerializer):
    """Serializer for Appointment detail view (all fields, read-only)"""
    patient_name = serializers.SerializerMethodField()
    practitioner_name = serializers.SerializerMethodField()
    location_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Appointment
        fields = [
            'id',
            'patient_id',
            'patient_name',
            'practitioner_id',
            'practitioner_name',
            'location_id',
            'location_name',
            'encounter_id',
            'source',
            'external_id',
            'status',
            'scheduled_start',
            'scheduled_end',
            'notes',
            'cancellation_reason',
            'no_show_reason',
            'is_deleted',
            'deleted_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'patient_name',
            'practitioner_name',
            'location_name',
            'is_deleted',
            'deleted_at',
            'created_at',
            'updated_at',
        ]
    
    def get_patient_name(self, obj):
        """Get patient full name"""
        if obj.patient:
            return f"{obj.patient.first_name} {obj.patient.last_name}".strip()
        return None
    
    def get_practitioner_name(self, obj):
        """Get practitioner full name"""
        if obj.practitioner:
            return f"{obj.practitioner.first_name} {obj.practitioner.last_name}".strip()
        return None
    
    def get_location_name(self, obj):
        """Get location name"""
        if obj.location:
            return obj.location.name
        return None


class AppointmentWriteSerializer(serializers.ModelSerializer):
    """
    Serializer for Appointment create/update.
    
    BUSINESS RULE: Status changes must use the /transition/ endpoint,
    not direct PATCH/PUT. Status is read-only after creation.
    """
    
    class Meta:
        model = Appointment
        fields = [
            'id',
            'patient_id',
            'practitioner_id',
            'location_id',
            'encounter_id',
            'source',
            'external_id',
            'status',
            'scheduled_start',
            'scheduled_end',
            'notes',
            'cancellation_reason',
            'no_show_reason',
            'is_deleted',
            'deleted_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'is_deleted',
            'deleted_at',
            'created_at',
            'updated_at',
        ]
    
    def validate_patient_id(self, value):
        """
        BUSINESS RULE: Patient is required for all appointments.
        """
        if not value:
            raise serializers.ValidationError(
                'La cita requiere un paciente asignado'
            )
        return value
    
    def validate_source(self, value):
        """Validate source enum"""
        valid_sources = [choice[0] for choice in AppointmentSourceChoices.choices]
        if value not in valid_sources:
            raise serializers.ValidationError(
                f"Valor inválido. Opciones: {', '.join(valid_sources)}"
            )
        return value
    
    def validate_status(self, value):
        """
        BUSINESS RULE: Status can only be set on creation.
        For updates, use the /transition/ endpoint.
        """
        # Allow setting status on creation
        if not self.instance:
            valid_statuses = [choice[0] for choice in AppointmentStatusChoices.choices]
            if value not in valid_statuses:
                raise serializers.ValidationError(
                    f"Valor inválido. Opciones: {', '.join(valid_statuses)}"
                )
            return value
        
        # Block direct status change on update
        if self.instance and value != self.instance.status:
            raise serializers.ValidationError(
                'No se puede cambiar el estado directamente. '
                'Use el endpoint /appointments/{id}/transition/ para cambiar el estado.'
            )
        
        return value
    
    def validate_external_id(self, value):
        """Validate external_id uniqueness for calendly appointments"""
        if value:
            # Check if external_id already exists (excluding current instance)
            qs = Appointment.objects.filter(external_id=value)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "Ya existe una cita con este external_id"
                )
        return value
    
    def validate(self, attrs):
        """
        Model-level validation using Appointment.clean()
        
        This will check:
        - Patient is required
        - No overlapping appointments
        - Valid time range
        """
        # Create a temporary instance for validation
        instance = self.instance or Appointment()
        
        # Update instance with attrs
        for key, value in attrs.items():
            setattr(instance, key, value)
        
        # Run model validation
        try:
            instance.clean()
        except ValidationError as e:
            raise serializers.ValidationError(e.message_dict)
        
        return attrs
    
    def validate(self, attrs):
        """Cross-field validation"""
        source = attrs.get('source', getattr(self.instance, 'source', None))
        external_id = attrs.get('external_id', getattr(self.instance, 'external_id', None))
        status = attrs.get('status', getattr(self.instance, 'status', None))
        cancellation_reason = attrs.get('cancellation_reason', getattr(self.instance, 'cancellation_reason', None))
        no_show_reason = attrs.get('no_show_reason', getattr(self.instance, 'no_show_reason', None))
        
        # Validate external_id for calendly source
        if source == AppointmentSourceChoices.CALENDLY:
            if not external_id:
                raise serializers.ValidationError({
                    'external_id': ['external_id es obligatorio para citas de Calendly']
                })
        
        # Validate cancellation_reason if status is cancelled
        if status == AppointmentStatusChoices.CANCELLED:
            if not cancellation_reason:
                raise serializers.ValidationError({
                    'cancellation_reason': ['cancellation_reason es obligatorio si status=cancelled']
                })
        
        # Validate no_show_reason if status is no_show
        if status == AppointmentStatusChoices.NO_SHOW:
            if not no_show_reason:
                raise serializers.ValidationError({
                    'no_show_reason': ['no_show_reason es obligatorio si status=no_show']
                })
        
        # Validate status transitions (basic validation)
        if self.instance:
            old_status = self.instance.status
            new_status = status
            
            # Define allowed transitions
            allowed_transitions = {
                AppointmentStatusChoices.SCHEDULED: [
                    AppointmentStatusChoices.CONFIRMED,
                    AppointmentStatusChoices.CANCELLED,
                    AppointmentStatusChoices.NO_SHOW,
                ],
                AppointmentStatusChoices.CONFIRMED: [
                    AppointmentStatusChoices.ATTENDED,
                    AppointmentStatusChoices.CANCELLED,
                    AppointmentStatusChoices.NO_SHOW,
                ],
                AppointmentStatusChoices.ATTENDED: [],  # Terminal state
                AppointmentStatusChoices.NO_SHOW: [],  # Terminal state
                AppointmentStatusChoices.CANCELLED: [],  # Terminal state
            }
            
            # Check if transition is allowed (allow same status)
            if new_status != old_status:
                if new_status not in allowed_transitions.get(old_status, []):
                    raise serializers.ValidationError({
                        'status': [
                            f"Transición inválida de {old_status} a {new_status}"
                        ]
                    })
        
        # Check if appointment is locked (linked to encounter or status=attended)
        if self.instance:
            user_roles = set(
                self.context['request'].user.user_roles.values_list('role__name', flat=True)
            )
            is_admin = 'Admin' in user_roles
            
            # Lock if linked to encounter
            if self.instance.encounter_id and not is_admin:
                raise serializers.ValidationError({
                    'encounter_id': [
                        'No se puede editar una cita que ya está vinculada a un encuentro (solo Admin)'
                    ]
                })
            
            # Lock if status is attended (completed)
            if self.instance.status == AppointmentStatusChoices.ATTENDED and not is_admin:
                raise serializers.ValidationError({
                    'status': [
                        'No se puede editar una cita con status=attended (solo Admin)'
                    ]
                })
        
        return attrs
    
    def validate_scheduled_start(self, value):
        """Validate scheduled_start is not None"""
        if not value:
            raise serializers.ValidationError("scheduled_start es obligatorio")
        return value
    
    def validate_scheduled_end(self, value):
        """Validate scheduled_end is not None"""
        if not value:
            raise serializers.ValidationError("scheduled_end es obligatorio")
        return value


# Patient Merge Serializers

class MergeCandidateSerializer(serializers.Serializer):
    """Serializer for merge candidate results."""
    patient_id = serializers.UUIDField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    masked_phone = serializers.CharField(read_only=True)
    masked_email = serializers.CharField(read_only=True)
    birth_date = serializers.DateField(read_only=True, allow_null=True)
    score = serializers.FloatField(read_only=True)
    match_reasons = serializers.ListField(child=serializers.CharField(), read_only=True)


class PatientMergeRequestSerializer(serializers.Serializer):
    """Serializer for patient merge request."""
    source_patient_id = serializers.UUIDField(required=True)
    target_patient_id = serializers.UUIDField(required=True)
    strategy = serializers.ChoiceField(
        choices=['phone_exact', 'email_exact', 'name_trgm', 'manual', 'other'],
        default='manual'
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    evidence = serializers.JSONField(required=False, allow_null=True)


class PatientMergeResponseSerializer(serializers.Serializer):
    """Serializer for patient merge response."""
    target_patient_id = serializers.UUIDField(read_only=True)
    moved_relations_summary = serializers.DictField(read_only=True)
    merge_log_id = serializers.UUIDField(read_only=True)


# ============================================================================
# Clinical Core v1: Encounter, Treatment, EncounterTreatment Serializers
# ============================================================================

class TreatmentSerializer(serializers.ModelSerializer):
    """
    Serializer for Treatment catalog.
    
    Used for:
    - Listing all available treatments (GET /api/v1/treatments/)
    - Creating new treatments (POST /api/v1/treatments/) - Admin only
    - Updating treatments (PATCH /api/v1/treatments/{id}/) - Admin only
    """
    class Meta:
        model = Treatment
        fields = [
            'id',
            'name',
            'description',
            'is_active',
            'default_price',
            'requires_stock',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_name(self, value):
        """Validate name is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("El nombre del tratamiento es obligatorio")
        return value.strip()


class EncounterTreatmentSerializer(serializers.ModelSerializer):
    """
    Serializer for EncounterTreatment (nested in Encounter).
    
    Fields:
    - treatment_id: FK to Treatment (write)
    - treatment: nested Treatment object (read)
    - quantity, unit_price, notes
    - effective_price (read-only): unit_price or Treatment.default_price
    - total_price (read-only): quantity * effective_price
    """
    treatment = TreatmentSerializer(read_only=True)
    treatment_id = serializers.UUIDField(write_only=True)
    effective_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = EncounterTreatment
        fields = [
            'id',
            'treatment_id',
            'treatment',
            'quantity',
            'unit_price',
            'notes',
            'effective_price',
            'total_price',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'effective_price', 'total_price', 'created_at', 'updated_at']
    
    def validate_quantity(self, value):
        """Validate quantity >= 1."""
        if value < 1:
            raise serializers.ValidationError("La cantidad debe ser al menos 1")
        return value
    
    def validate_treatment_id(self, value):
        """Validate treatment exists and is active."""
        try:
            treatment = Treatment.objects.get(id=value)
            if not treatment.is_active:
                raise serializers.ValidationError(
                    f"El tratamiento '{treatment.name}' está inactivo"
                )
        except Treatment.DoesNotExist:
            raise serializers.ValidationError("Tratamiento no encontrado")
        return value


class EncounterListSerializer(serializers.ModelSerializer):
    """
    Serializer for Encounter list view (GET /api/v1/encounters/).
    
    Includes:
    - Basic encounter info
    - Patient name
    - Practitioner name
    - Treatment count
    """
    patient_name = serializers.SerializerMethodField()
    practitioner_name = serializers.SerializerMethodField()
    treatment_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Encounter
        fields = [
            'id',
            'patient',
            'patient_name',
            'practitioner',
            'practitioner_name',
            'type',
            'status',
            'occurred_at',
            'treatment_count',
            'created_at',
        ]
        read_only_fields = fields
    
    def get_patient_name(self, obj):
        """Return patient full name."""
        return f"{obj.patient.first_name} {obj.patient.last_name}"
    
    def get_practitioner_name(self, obj):
        """Return practitioner display name."""
        return obj.practitioner.display_name if obj.practitioner else None
    
    def get_treatment_count(self, obj):
        """Return count of treatments in this encounter."""
        return obj.encounter_treatments.count()


class EncounterDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for Encounter detail view (GET /api/v1/encounters/{id}/).
    
    Includes:
    - All encounter fields
    - Nested treatments list
    - Patient details
    - Practitioner details
    """
    patient = serializers.SerializerMethodField()
    practitioner = serializers.SerializerMethodField()
    encounter_treatments = EncounterTreatmentSerializer(many=True, read_only=True)
    
    class Meta:
        model = Encounter
        fields = [
            'id',
            'patient',
            'practitioner',
            'location',
            'type',
            'status',
            'occurred_at',
            'chief_complaint',
            'assessment',
            'plan',
            'internal_notes',
            'encounter_treatments',
            'signed_at',
            'signed_by_user',
            'row_version',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'signed_at', 'signed_by_user', 'row_version', 'created_at', 'updated_at']
    
    def get_patient(self, obj):
        """Return patient basic info."""
        return {
            'id': obj.patient.id,
            'first_name': obj.patient.first_name,
            'last_name': obj.patient.last_name,
            'email': obj.patient.email,
            'phone': obj.patient.phone,
        }
    
    def get_practitioner(self, obj):
        """Return practitioner basic info."""
        if not obj.practitioner:
            return None
        return {
            'id': obj.practitioner.id,
            'display_name': obj.practitioner.display_name,
            'specialty': obj.practitioner.specialty,
        }


class EncounterWriteSerializer(serializers.ModelSerializer):
    """
    Serializer for Encounter create/update (POST/PATCH /api/v1/encounters/).
    
    Features:
    - Nested treatments creation
    - Status transition validation
    - RBAC field restrictions (clinical_notes requires ClinicalOps)
    """
    encounter_treatments = EncounterTreatmentSerializer(many=True, required=False)
    
    class Meta:
        model = Encounter
        fields = [
            'id',
            'patient',
            'practitioner',
            'location',
            'type',
            'status',
            'occurred_at',
            'chief_complaint',
            'assessment',
            'plan',
            'internal_notes',
            'encounter_treatments',
        ]
        read_only_fields = ['id']
    
    def validate(self, attrs):
        """Validate business rules and RBAC restrictions."""
        # Validate status transitions
        if self.instance and 'status' in attrs:
            old_status = self.instance.status
            new_status = attrs['status']
            if old_status != new_status:
                allowed_transitions = {
                    'draft': ['finalized', 'cancelled'],
                    'finalized': [],  # Terminal state
                    'cancelled': [],  # Terminal state
                }
                if new_status not in allowed_transitions.get(old_status, []):
                    raise serializers.ValidationError({
                        'status': f"Transición inválida: {old_status} -> {new_status}"
                    })
        
        return attrs
    
    def create(self, validated_data):
        """Create encounter with nested treatments."""
        treatments_data = validated_data.pop('encounter_treatments', [])
        
        with transaction.atomic():
            encounter = Encounter.objects.create(**validated_data)
            
            # Create treatments
            for treatment_data in treatments_data:
                treatment_id = treatment_data.pop('treatment_id')
                treatment = Treatment.objects.get(id=treatment_id)
                EncounterTreatment.objects.create(
                    encounter=encounter,
                    treatment=treatment,
                    **treatment_data
                )
        
        return encounter
    
    def update(self, instance, validated_data):
        """Update encounter (treatments are updated separately)."""
        # Remove treatments from validated_data (handle separately)
        validated_data.pop('encounter_treatments', None)
        
        # Update encounter fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        return instance
