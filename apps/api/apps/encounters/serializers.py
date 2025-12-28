"""
Encounter serializers - DEPRECATED

⚠️ THESE SERIALIZERS ARE DEPRECATED ⚠️

DO NOT USE. This file is kept only for reference.
Use apps.clinical.serializers for Encounter serialization.

- Use: EncounterListSerializer, EncounterDetailSerializer, EncounterWriteSerializer
- From: apps.clinical.serializers
- Endpoint: /api/v1/clinical/encounters/

This file will be removed in a future cleanup.
"""
# Deprecated - kept for reference only
# All functionality moved to apps.clinical.serializers
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
