"""
Serializers for Clinical Charge Proposals (Fase 3: Clinical → Sales Integration).
"""
from rest_framework import serializers
from apps.clinical.models import (
    ClinicalChargeProposal,
    ClinicalChargeProposalLine,
    ProposalStatusChoices
)


class ClinicalChargeProposalLineSerializer(serializers.ModelSerializer):
    """
    Serializer for ClinicalChargeProposalLine.
    
    Read-only (lines are auto-generated from encounter treatments).
    """
    treatment_id = serializers.UUIDField(source='treatment.id', read_only=True)
    encounter_treatment_id = serializers.UUIDField(source='encounter_treatment.id', read_only=True)
    
    class Meta:
        model = ClinicalChargeProposalLine
        fields = [
            'id',
            'treatment_id',
            'encounter_treatment_id',
            'treatment_name',
            'description',
            'quantity',
            'unit_price',
            'line_total',
            'created_at'
        ]
        read_only_fields = fields


class ClinicalChargeProposalListSerializer(serializers.ModelSerializer):
    """
    List serializer for ClinicalChargeProposal (lightweight).
    """
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    practitioner_name = serializers.CharField(source='practitioner.display_name', read_only=True)
    encounter_id = serializers.UUIDField(source='encounter.id', read_only=True)
    line_count = serializers.IntegerField(source='lines.count', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = ClinicalChargeProposal
        fields = [
            'id',
            'encounter_id',
            'patient_name',
            'practitioner_name',
            'status',
            'status_display',
            'total_amount',
            'currency',
            'line_count',
            'converted_to_sale',
            'converted_at',
            'created_at',
            'created_by'
        ]
        read_only_fields = fields


class ClinicalChargeProposalDetailSerializer(serializers.ModelSerializer):
    """
    Detail serializer for ClinicalChargeProposal (with nested lines).
    """
    patient = serializers.SerializerMethodField()
    practitioner = serializers.SerializerMethodField()
    encounter = serializers.SerializerMethodField()
    lines = ClinicalChargeProposalLineSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    converted_to_sale_id = serializers.UUIDField(source='converted_to_sale.id', read_only=True, allow_null=True)
    
    class Meta:
        model = ClinicalChargeProposal
        fields = [
            'id',
            'encounter',
            'patient',
            'practitioner',
            'status',
            'status_display',
            'total_amount',
            'currency',
            'notes',
            'cancellation_reason',
            'converted_to_sale_id',
            'converted_at',
            'lines',
            'created_at',
            'created_by',
            'updated_at'
        ]
        read_only_fields = fields
    
    def get_patient(self, obj):
        """Patient summary."""
        return {
            'id': str(obj.patient.id),
            'full_name': obj.patient.full_name,
            'email': obj.patient.email
        }
    
    def get_practitioner(self, obj):
        """Practitioner summary."""
        if not obj.practitioner:
            return None
        return {
            'id': str(obj.practitioner.id),
            'display_name': obj.practitioner.display_name,
            'specialty': obj.practitioner.specialty
        }
    
    def get_encounter(self, obj):
        """Encounter summary."""
        return {
            'id': str(obj.encounter.id),
            'type': obj.encounter.type,
            'occurred_at': obj.encounter.occurred_at,
            'status': obj.encounter.status
        }


class CreateSaleFromProposalSerializer(serializers.Serializer):
    """
    Serializer for create_sale action.
    
    Input: legal_entity_id, optional notes
    Output: Sale ID + success message
    """
    legal_entity_id = serializers.UUIDField(
        required=True,
        help_text='Legal entity for the sale (required)'
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Optional notes for the sale'
    )
    
    def validate_legal_entity_id(self, value):
        """Validate legal entity exists and is active."""
        from apps.legal.models import LegalEntity
        
        try:
            legal_entity = LegalEntity.objects.get(id=value)
        except LegalEntity.DoesNotExist:
            raise serializers.ValidationError(
                f"Legal entity {value} does not exist"
            )
        
        if not legal_entity.is_active:
            raise serializers.ValidationError(
                f"Legal entity {value} is not active"
            )
        
        return value
