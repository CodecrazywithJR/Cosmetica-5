"""
Encounter serializers.
"""
from rest_framework import serializers

from apps.patients.serializers import PatientListSerializer
from apps.clinical.models import log_clinical_audit

from .models import Encounter


class EncounterSerializer(serializers.ModelSerializer):
    """
    Full encounter serializer.
    
    AUDIT: Logs create/update actions to ClinicalAuditLog.
    """
    patient_details = PatientListSerializer(source='patient', read_only=True)
    
    class Meta:
        model = Encounter
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        """Create encounter with audit logging."""
        instance = super().create(validated_data)
        
        # Log creation
        request = self.context.get('request')
        log_clinical_audit(
            actor=request.user if request else None,
            instance=instance,
            action='create',
            after=self._get_audit_snapshot(instance),
            patient=instance.patient,
            request=request
        )
        
        return instance
    
    def update(self, instance, validated_data):
        """Update encounter with audit logging."""
        # Capture before snapshot
        before_snapshot = self._get_audit_snapshot(instance)
        
        # Detect changed fields
        changed_fields = []
        for field, value in validated_data.items():
            if getattr(instance, field) != value:
                changed_fields.append(field)
        
        # Perform update
        instance = super().update(instance, validated_data)
        
        # Log update only if there are actual changes
        if changed_fields:
            request = self.context.get('request')
            log_clinical_audit(
                actor=request.user if request else None,
                instance=instance,
                action='update',
                before=before_snapshot,
                after=self._get_audit_snapshot(instance),
                changed_fields=changed_fields,
                patient=instance.patient,
                request=request
            )
        
        return instance
    
    def _get_audit_snapshot(self, instance):
        """
        Get snapshot of clinically relevant fields for audit.
        
        CRITICAL: Only includes essential fields for audit trail.
        Excludes internal_notes to minimize sensitive data exposure.
        """
        return {
            'type': instance.type,
            'status': instance.status,
            'occurred_at': instance.occurred_at.isoformat() if instance.occurred_at else None,
            'chief_complaint': instance.chief_complaint[:200] if instance.chief_complaint else None,
            'assessment': instance.assessment[:200] if instance.assessment else None,
            'plan': instance.plan[:200] if instance.plan else None,
            # internal_notes excluded - too sensitive for audit logs
        }


class EncounterListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for encounter lists."""
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    
    class Meta:
        model = Encounter
        fields = [
            'id',
            'patient',
            'patient_name',
            'encounter_type',
            'status',
            'scheduled_at',
            'chief_complaint',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'patient_name']
