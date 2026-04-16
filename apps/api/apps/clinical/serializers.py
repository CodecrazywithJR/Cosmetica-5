"""
Clinical serializers for Patient and PatientGuardian.
Based on API_CONTRACTS.md PAC section.
"""
from rest_framework import serializers
from django.core.exceptions import ValidationError
from django.db import transaction
from apps.clinical.models import (
    Patient,
    PatientGuardian,
    PatientInsurance,
    ReferralSource,
    Appointment,
    AppointmentStatusChoices,
    AppointmentType,
    Encounter,
    Treatment,
    EncounterTreatment,
    PractitionerBlock,
)
from apps.authz.models import Practitioner, RoleChoices
from apps.core.models import Clinic
from apps.treatment_plans.models import TreatmentPlan


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
    has_missing_legal_consents = serializers.SerializerMethodField()
    has_missing_consent_documents = serializers.SerializerMethodField()
    
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
            'has_missing_legal_consents',
            'has_missing_consent_documents',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_has_missing_legal_consents(self, obj):
        """Return precomputed annotation from queryset (no additional queries)"""
        return getattr(obj, 'has_missing_legal_consents', False)
    
    def get_has_missing_consent_documents(self, obj):
        """Return precomputed annotation from queryset (no additional queries)"""
        return getattr(obj, 'has_missing_consent_documents', False)


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
            'document_type',
            'document_number',
            'nationality',
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
            'blood_type',
            'allergies',
            'medical_history',
            'current_medications',
            'emergency_contact_name',
            'emergency_contact_phone',
            'privacy_policy_accepted',
            'privacy_policy_accepted_at',
            'terms_accepted',
            'terms_accepted_at',
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
        
        # Rule: document_type + document_number must be provided together
        doc_type = attrs.get('document_type', getattr(self.instance, 'document_type', None))
        doc_number = attrs.get('document_number', getattr(self.instance, 'document_number', None))
        if doc_type and not doc_number:
            raise serializers.ValidationError({
                'document_number': ['document_number es obligatorio cuando document_type está presente']
            })
        if doc_number and not doc_type:
            raise serializers.ValidationError({
                'document_type': ['document_type es obligatorio cuando document_number está presente']
            })

        # Rule: emergency_contact_name + emergency_contact_phone must be provided together
        ec_name = attrs.get('emergency_contact_name', getattr(self.instance, 'emergency_contact_name', None))
        ec_phone = attrs.get('emergency_contact_phone', getattr(self.instance, 'emergency_contact_phone', None))
        if ec_name and not ec_phone:
            raise serializers.ValidationError({
                'emergency_contact_phone': ['emergency_contact_phone es obligatorio cuando emergency_contact_name está presente']
            })
        if ec_phone and not ec_name:
            raise serializers.ValidationError({
                'emergency_contact_name': ['emergency_contact_name es obligatorio cuando emergency_contact_phone está presente']
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
        
        # Update all fields from validated_data
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
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
            if RoleChoices.RECEPTION in user_roles:
                # Remove clinical notes field
                representation.pop('notes', None)
        
        return representation


class AppointmentListSerializer(serializers.ModelSerializer):
    """Serializer for Appointment list view (lightweight)"""
    patient_name = serializers.SerializerMethodField()
    practitioner_name = serializers.SerializerMethodField()
    clinic_name = serializers.SerializerMethodField()
    appointment_type_name = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            'id',
            'patient_id',
            'patient_name',
            'practitioner_id',
            'practitioner_name',
            'clinic_id',
            'clinic_name',
            'appointment_type_id',
            'appointment_type_name',
            'source',
            'status',
            'scheduled_start',
            'scheduled_end',
            'duration_planned',
            'is_deleted',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_patient_name(self, obj):
        if obj.patient:
            return f"{obj.patient.first_name} {obj.patient.last_name}".strip()
        return None

    def get_practitioner_name(self, obj):
        if obj.practitioner:
            return obj.practitioner.display_name or str(obj.practitioner)
        return None

    def get_clinic_name(self, obj):
        if obj.clinic:
            return obj.clinic.name
        return None

    def get_appointment_type_name(self, obj):
        if obj.appointment_type:
            return obj.appointment_type.name
        return None


class AppointmentDetailSerializer(serializers.ModelSerializer):
    """Serializer for Appointment detail view (all fields, read-only)"""
    patient_name = serializers.SerializerMethodField()
    practitioner_name = serializers.SerializerMethodField()
    clinic_name = serializers.SerializerMethodField()
    appointment_type_name = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            'id',
            'patient_id',
            'patient_name',
            'practitioner_id',
            'practitioner_name',
            'clinic_id',
            'clinic_name',
            'appointment_type_id',
            'appointment_type_name',
            'encounter_id',
            'treatment_id',
            'treatment_plan_id',
            'source',
            'status',
            'scheduled_start',
            'scheduled_end',
            'duration_planned',
            'duration_real',
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
            'clinic_name',
            'appointment_type_name',
            'is_deleted',
            'deleted_at',
            'created_at',
            'updated_at',
        ]

    def get_patient_name(self, obj):
        if obj.patient:
            return f"{obj.patient.first_name} {obj.patient.last_name}".strip()
        return None

    def get_practitioner_name(self, obj):
        if obj.practitioner:
            return obj.practitioner.display_name or str(obj.practitioner)
        return None

    def get_clinic_name(self, obj):
        if obj.clinic:
            return obj.clinic.name
        return None

    def get_appointment_type_name(self, obj):
        if obj.appointment_type:
            return obj.appointment_type.name
        return None


class AppointmentWriteSerializer(serializers.ModelSerializer):
    """
    Serializer for Appointment create/update.

    Status changes must use the /transition/ endpoint.
    """
    patient_id = serializers.PrimaryKeyRelatedField(
        queryset=Patient.objects.all(), source='patient',
    )
    practitioner_id = serializers.PrimaryKeyRelatedField(
        queryset=Practitioner.objects.all(), source='practitioner',
    )
    clinic_id = serializers.PrimaryKeyRelatedField(
        queryset=Clinic.objects.all(), source='clinic',
        required=False, allow_null=True,
    )
    appointment_type_id = serializers.PrimaryKeyRelatedField(
        queryset=AppointmentType.objects.all(), source='appointment_type',
        required=False, allow_null=True,
    )
    encounter_id = serializers.PrimaryKeyRelatedField(
        queryset=Encounter.objects.all(), source='encounter',
        required=False, allow_null=True,
    )
    treatment_id = serializers.PrimaryKeyRelatedField(
        queryset=Treatment.objects.all(), source='treatment',
        required=False, allow_null=True,
    )
    treatment_plan_id = serializers.PrimaryKeyRelatedField(
        queryset=TreatmentPlan.objects.all(), source='treatment_plan',
        required=False, allow_null=True,
    )

    class Meta:
        model = Appointment
        fields = [
            'id',
            'patient_id',
            'practitioner_id',
            'clinic_id',
            'appointment_type_id',
            'encounter_id',
            'treatment_id',
            'treatment_plan_id',
            'source',
            'status',
            'scheduled_start',
            'scheduled_end',
            'duration_planned',
            'duration_real',
            'notes',
            'cancellation_reason',
            'no_show_reason',
        ]
        read_only_fields = ['id']

    def validate_patient_id(self, value):
        if not value:
            raise serializers.ValidationError(
                'La cita requiere un paciente asignado'
            )
        return value

    def validate_status(self, value):
        """Status can only be set on creation. Use /transition/ for updates."""
        if not self.instance:
            valid_statuses = [c[0] for c in AppointmentStatusChoices.choices]
            if value not in valid_statuses:
                raise serializers.ValidationError(
                    f"Valor inválido. Opciones: {', '.join(valid_statuses)}"
                )
            return value

        if self.instance and value != self.instance.status:
            raise serializers.ValidationError(
                'No se puede cambiar el estado directamente. '
                'Use el endpoint /appointments/{id}/transition/ para cambiar el estado.'
            )
        return value

    def validate(self, attrs):
        """Cross-field validation"""
        status_val = attrs.get('status', getattr(self.instance, 'status', None))
        cancellation_reason = attrs.get('cancellation_reason', getattr(self.instance, 'cancellation_reason', None))
        no_show_reason = attrs.get('no_show_reason', getattr(self.instance, 'no_show_reason', None))

        if status_val == AppointmentStatusChoices.CANCELLED and not cancellation_reason:
            raise serializers.ValidationError({
                'cancellation_reason': ['cancellation_reason es obligatorio si status=cancelled']
            })

        if status_val == AppointmentStatusChoices.NO_SHOW and not no_show_reason:
            raise serializers.ValidationError({
                'no_show_reason': ['no_show_reason es obligatorio si status=no_show']
            })

        # Lock checks on update
        if self.instance:
            user_roles = set(
                self.context['request'].user.user_roles.values_list('role__name', flat=True)
            )
            is_admin = RoleChoices.ADMIN in user_roles

            if self.instance.encounter_id and not is_admin:
                raise serializers.ValidationError({
                    'encounter_id': [
                        'No se puede editar una cita que ya está vinculada a un encuentro (solo Admin)'
                    ]
                })

            if self.instance.status == AppointmentStatusChoices.COMPLETED and not is_admin:
                raise serializers.ValidationError({
                    'status': [
                        'No se puede editar una cita con status=completed (solo Admin)'
                    ]
                })

        return attrs

    def validate_scheduled_start(self, value):
        if not value:
            raise serializers.ValidationError("scheduled_start es obligatorio")
        return value

    def validate_scheduled_end(self, value):
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
    - Attachments summary (photos + documents)
    """
    patient_name = serializers.SerializerMethodField()
    practitioner_name = serializers.SerializerMethodField()
    treatment_count = serializers.SerializerMethodField()
    attachments_summary = serializers.SerializerMethodField()
    
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
            'attachments_summary',
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
    
    def get_attachments_summary(self, obj):
        """Return attachments summary with counts."""
        # Count photos (through EncounterPhoto M2M)
        photo_count = obj.encounter_photos.filter(photo__is_deleted=False).count()
        
        # Count documents (through EncounterDocument M2M)
        document_count = obj.encounter_documents.filter(document__is_deleted=False).count()
        
        return {
            'has_photos': photo_count > 0,
            'has_documents': document_count > 0,
            'photo_count': photo_count,
            'document_count': document_count,
        }


class EncounterDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for Encounter detail view (GET /api/v1/encounters/{id}/).
    
    Includes:
    - All encounter fields
    - Nested treatments list
    - Patient details
    - Practitioner details
    - Photos array
    - Documents array
    """
    patient = serializers.SerializerMethodField()
    practitioner = serializers.SerializerMethodField()
    encounter_treatments = EncounterTreatmentSerializer(many=True, read_only=True)
    photos = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()
    
    class Meta:
        model = Encounter
        fields = [
            'id',
            'patient',
            'practitioner',
            'clinic',
            'type',
            'status',
            'occurred_at',
            'chief_complaint',
            'assessment',
            'plan',
            'internal_notes',
            'encounter_treatments',
            'photos',
            'documents',
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
    
    def get_photos(self, obj):
        """Return photos array with presigned URLs."""
        from apps.clinical.utils_storage import get_clinical_photo_url
        
        photos = []
        for encounter_photo in obj.encounter_photos.filter(photo__is_deleted=False).select_related('photo'):
            photo = encounter_photo.photo
            try:
                url = get_clinical_photo_url(photo)
            except Exception:
                url = None
            
            photos.append({
                'id': str(photo.id),
                'classification': photo.photo_kind,
                'created_at': photo.created_at.isoformat(),
                'url': url,
                'filename': photo.object_key.split('/')[-1] if photo.object_key else None,
                'mime_type': photo.content_type,
                'size_bytes': photo.size_bytes,
            })
        
        return photos
    
    def get_documents(self, obj):
        """Return documents array with presigned URLs."""
        from apps.clinical.utils_storage import get_document_url
        from apps.documents.models import Document
        
        documents = []
        for encounter_doc in obj.encounter_documents.filter(document__is_deleted=False).select_related('document'):
            doc = encounter_doc.document
            try:
                url = get_document_url(doc)
            except Exception:
                url = None
            
            documents.append({
                'id': str(doc.id),
                'created_at': doc.created_at.isoformat(),
                'url': url,
                'filename': doc.object_key.split('/')[-1] if doc.object_key else None,
                'mime_type': doc.content_type,
                'size_bytes': doc.size_bytes,
                'title': doc.title,
            })
        
        return documents


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
            'clinic',
            'type',
            'status',
            'occurred_at',
            'chief_complaint',
            'assessment',
            'plan',
            'internal_notes',
            'encounter_treatments',
            'row_version',
        ]
        read_only_fields = ['id']

    def validate(self, attrs):
        """Validate business rules, RBAC restrictions, and row_version concurrency."""
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

        # Require row_version on update
        if self.instance:
            if 'row_version' not in self.initial_data:
                raise serializers.ValidationError({
                    'row_version': ['Este campo es obligatorio para actualizar']
                })
            provided_version = self.initial_data.get('row_version')
            # Accept both int and str for row_version
            try:
                provided_version = int(provided_version)
            except Exception:
                raise serializers.ValidationError({
                    'row_version': ['Formato inválido para row_version']
                })
            if provided_version != self.instance.row_version:
                # Raise 409 Conflict by propagating exception up to view
                from rest_framework.exceptions import APIException
                class Conflict409(APIException):
                    status_code = 409
                    default_detail = 'Conflicto de versión: el registro fue modificado por otro usuario.'
                    default_code = 'conflict'
                raise Conflict409(
                    detail={
                        'row_version': [
                            f"El registro fue modificado por otro usuario. "
                            f"Versión actual: {self.instance.row_version}, "
                            f"versión proporcionada: {provided_version}"
                        ]
                    }
                )

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
        """Update encounter (treatments are updated separately, row_version incremented)."""
        # Remove treatments from validated_data (handle separately)
        validated_data.pop('encounter_treatments', None)

        # Remove row_version from validated_data (we'll increment it)
        validated_data.pop('row_version', None)

        # Update encounter fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Increment row_version
        instance.row_version += 1
        instance.save()

        return instance

# ============================================================================
# Calendar Event Serializers (Sprint 1)
# ============================================================================

class CalendarEventSerializer(serializers.Serializer):
    """
    Unified serializer for calendar events (appointments + blocks).
    
    Normalizes both Appointment and PractitionerBlock into a common format
    for the calendar feed endpoint.
    
    Used in: GET /api/v1/clinical/practitioners/{id}/calendar/
    """
    id = serializers.UUIDField(read_only=True)
    type = serializers.CharField(read_only=True)  # 'appointment' | 'block'
    title = serializers.CharField(read_only=True)
    start = serializers.DateTimeField(read_only=True)
    end = serializers.DateTimeField(read_only=True)
    practitioner_id = serializers.UUIDField(read_only=True)
    practitioner_name = serializers.CharField(read_only=True)
    
    # Appointment-specific fields (null for blocks)
    patient_id = serializers.UUIDField(read_only=True, allow_null=True)
    patient_name = serializers.CharField(read_only=True, allow_null=True)
    appointment_status = serializers.CharField(read_only=True, allow_null=True)
    appointment_source = serializers.CharField(read_only=True, allow_null=True)
    
    # Block-specific fields (null for appointments)
    block_kind = serializers.CharField(read_only=True, allow_null=True)
    
    # Common fields
    notes = serializers.CharField(read_only=True, allow_null=True)
    
    def to_representation(self, instance):
        """
        Convert Appointment or PractitionerBlock to unified calendar event format.
        """
        from apps.clinical.models import Appointment, PractitionerBlock
        
        if isinstance(instance, Appointment):
            # Appointment event
            practitioner_user = instance.practitioner.user if instance.practitioner else None
            patient_full_name = None
            if instance.patient:
                patient_full_name = f"{instance.patient.first_name} {instance.patient.last_name}".strip()
            
            return {
                'id': instance.id,
                'type': 'appointment',
                'title': patient_full_name or 'Appointment',
                'start': instance.scheduled_start,
                'end': instance.scheduled_end,
                'practitioner_id': instance.practitioner_id,
                'practitioner_name': practitioner_user.get_full_name() if practitioner_user else 'Unknown',
                'patient_id': instance.patient_id,
                'patient_name': patient_full_name,
                'appointment_status': instance.status,
                'appointment_source': instance.source,
                'block_kind': None,
                'notes': instance.notes,
            }
        
        elif isinstance(instance, PractitionerBlock):
            # Block event
            practitioner_user = instance.practitioner.user if instance.practitioner else None
            
            return {
                'id': instance.id,
                'type': 'block',
                'title': instance.title,
                'start': instance.start,
                'end': instance.end,
                'practitioner_id': instance.practitioner_id,
                'practitioner_name': practitioner_user.get_full_name() if practitioner_user else 'Unknown',
                'patient_id': None,
                'patient_name': None,
                'appointment_status': None,
                'appointment_source': None,
                'block_kind': instance.kind,
                'notes': instance.notes,
            }
        
        else:
            raise ValueError(f"Unsupported instance type: {type(instance)}")


# ============================================================================
# Patient Insurance
# ============================================================================

class PatientInsuranceSerializer(serializers.ModelSerializer):
    """
    Serializer for PatientInsurance with auto-close and overlap validation.

    On create:
    - If patient already has an active coverage, auto-close it
      (valid_to = new.valid_from - 1 day, is_active=False).
    - Validates no date overlap with existing records.
    """

    class Meta:
        model = PatientInsurance
        fields = [
            'id', 'patient', 'provider_name', 'member_number',
            'social_security_number', 'valid_from', 'valid_to',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    # ---- Cross-field validation ----

    def validate(self, attrs):
        valid_from = attrs.get('valid_from') or (self.instance and self.instance.valid_from)
        valid_to = attrs.get('valid_to', self.instance.valid_to if self.instance else None)

        if valid_to and valid_from and valid_to < valid_from:
            raise serializers.ValidationError(
                {'valid_to': 'valid_to cannot be before valid_from.'}
            )

        # Overlap check (R2)
        patient = attrs.get('patient') or (self.instance and self.instance.patient)
        if patient and valid_from:
            self._check_overlap(patient, valid_from, valid_to)

        return attrs

    def _check_overlap(self, patient, new_from, new_to):
        """
        Ensure no date overlap with existing records.

        On create: evaluate against ALL records **after** simulating auto-close
        of the currently-active one (its valid_to becomes new_from - 1 day).
        On update: exclude self.
        """
        from datetime import timedelta

        qs = PatientInsurance.objects.filter(patient=patient)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        for existing in qs:
            e_from = existing.valid_from

            # On create, simulate auto-close for the active record
            if not self.instance and existing.is_active:
                e_to = new_from - timedelta(days=1)
            else:
                e_to = existing.valid_to  # may be None (open-ended)

            # Two ranges overlap when: start1 <= end2 AND start2 <= end1
            # For open-ended (None) treat as +infinity
            end_check = e_to is None or new_from <= e_to
            start_check = new_to is None or e_from <= new_to

            if end_check and start_check:
                raise serializers.ValidationError(
                    {'valid_from': f'Date range overlaps with existing coverage {existing.id} ({e_from} — {e_to or "open"}).'}
                )

    # ---- Auto-close on create (R3) + temporal monotonicity ----

    def create(self, validated_data):
        from datetime import timedelta

        patient = validated_data['patient']
        new_from = validated_data['valid_from']

        with transaction.atomic():
            # R-temporal: new coverage must not go backwards in time
            latest = (
                PatientInsurance.objects
                .filter(patient=patient)
                .order_by('-valid_from')
                .first()
            )
            if latest and new_from < latest.valid_from:
                raise serializers.ValidationError(
                    {'valid_from': (
                        f'Cannot create coverage before the most recent one '
                        f'({latest.valid_from}). Chronological order is enforced.'
                    )}
                )

            # Close any currently-active coverage for this patient
            prev = PatientInsurance.objects.select_for_update().filter(
                patient=patient, is_active=True
            ).first()

            if prev:
                prev.valid_to = new_from - timedelta(days=1)
                prev.is_active = False
                prev.save(update_fields=['valid_to', 'is_active', 'updated_at'])

            return super().create(validated_data)

    # ---- Hardened update (R2 / PATCH) ----

    def update(self, instance, validated_data):
        # Block manual is_active changes — only auto-close controls this
        if 'is_active' in validated_data:
            raise serializers.ValidationError(
                {'is_active': 'Manual activation/deactivation is not allowed. '
                              'is_active is managed automatically on create.'}
            )

        # Block valid_from changes if this is not the most recent coverage
        if 'valid_from' in validated_data:
            newer = (
                PatientInsurance.objects
                .filter(patient=instance.patient, valid_from__gt=instance.valid_from)
                .exclude(pk=instance.pk)
                .exists()
            )
            if newer:
                raise serializers.ValidationError(
                    {'valid_from': 'Cannot change valid_from on a historical '
                                   'coverage. Only the most recent can be modified.'}
                )

        with transaction.atomic():
            return super().update(instance, validated_data)