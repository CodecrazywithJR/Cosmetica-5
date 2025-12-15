"""
Photo serializers.
"""
from rest_framework import serializers

from .models import SkinPhoto
from apps.clinical.models import log_clinical_audit


class SkinPhotoSerializer(serializers.ModelSerializer):
    """
    Full skin photo serializer.
    
    AUDIT: Logs create/update actions to ClinicalAuditLog.
    """
    
    class Meta:
        model = SkinPhoto
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'thumbnail', 'thumbnail_generated']
    
    def create(self, validated_data):
        """Create a new SkinPhoto and log the creation."""
        instance = super().create(validated_data)
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
        """Update a SkinPhoto and log changes if any."""
        before_snapshot = self._get_audit_snapshot(instance)
        
        # Detect which fields actually changed
        changed_fields = []
        for field, value in validated_data.items():
            if getattr(instance, field) != value:
                changed_fields.append(field)
        
        instance = super().update(instance, validated_data)
        
        # Only log if there were actual changes
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
        """Get snapshot of clinically relevant fields."""
        return {
            'body_part': instance.body_part,
            'tags': instance.tags,
            'taken_at': instance.taken_at.isoformat() if instance.taken_at else None,
            'notes': instance.notes,
            'image': instance.image.name if instance.image else None,
        }


class SkinPhotoListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for photo lists."""
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    
    class Meta:
        model = SkinPhoto
        fields = [
            'id',
            'patient',
            'patient_name',
            'encounter',
            'image',
            'thumbnail',
            'body_part',
            'tags',
            'taken_at',
            'thumbnail_generated',
        ]
        read_only_fields = ['id', 'patient_name', 'thumbnail', 'thumbnail_generated']
