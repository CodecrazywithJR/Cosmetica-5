"""
Consent serializers for patient consent management.
"""
from rest_framework import serializers
from apps.clinical.models import Consent, ConsentTypeChoices, ConsentStatusChoices


class ConsentListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing patient consents.
    
    Includes:
    - Basic consent info (type, status, dates)
    - Document attachment info (if exists)
    """
    has_document = serializers.SerializerMethodField()
    document_id = serializers.SerializerMethodField()
    document_filename = serializers.SerializerMethodField()
    
    class Meta:
        model = Consent
        fields = [
            'id',
            'consent_type',
            'status',
            'granted_at',
            'revoked_at',
            'has_document',
            'document_id',
            'document_filename',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_has_document(self, obj):
        """Check if consent has document attached."""
        return obj.document is not None and not obj.document.is_deleted
    
    def get_document_id(self, obj):
        """Get document ID if exists."""
        if obj.document and not obj.document.is_deleted:
            return str(obj.document.id)
        return None
    
    def get_document_filename(self, obj):
        """Get document filename if exists."""
        if obj.document and not obj.document.is_deleted:
            # Extract filename from object_key
            return obj.document.object_key.split('/')[-1] if obj.document.object_key else None
        return None


class ConsentDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for consent detail/create/update.
    
    Used for:
    - GET /patients/{id}/consents/{consent_id}/
    - POST /patients/{id}/consents/
    - PATCH /consents/{consent_id}/
    """
    has_document = serializers.SerializerMethodField()
    document_id = serializers.SerializerMethodField()
    document_filename = serializers.SerializerMethodField()
    document_size_bytes = serializers.SerializerMethodField()
    document_content_type = serializers.SerializerMethodField()
    
    class Meta:
        model = Consent
        fields = [
            'id',
            'patient',
            'consent_type',
            'status',
            'granted_at',
            'revoked_at',
            'has_document',
            'document_id',
            'document_filename',
            'document_size_bytes',
            'document_content_type',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'patient', 'created_at', 'updated_at', 'document']
    
    def get_has_document(self, obj):
        """Check if consent has document attached."""
        return obj.document is not None and not obj.document.is_deleted
    
    def get_document_id(self, obj):
        """Get document ID if exists."""
        if obj.document and not obj.document.is_deleted:
            return str(obj.document.id)
        return None
    
    def get_document_filename(self, obj):
        """Get document filename if exists."""
        if obj.document and not obj.document.is_deleted:
            return obj.document.object_key.split('/')[-1] if obj.document.object_key else None
        return None
    
    def get_document_size_bytes(self, obj):
        """Get document size if exists."""
        if obj.document and not obj.document.is_deleted:
            return obj.document.size_bytes
        return None
    
    def get_document_content_type(self, obj):
        """Get document content type if exists."""
        if obj.document and not obj.document.is_deleted:
            return obj.document.content_type
        return None
    
    def validate_consent_type(self, value):
        """Validate consent_type is valid choice."""
        if value not in dict(ConsentTypeChoices.choices):
            raise serializers.ValidationError(f"Invalid consent_type. Must be one of: {', '.join(dict(ConsentTypeChoices.choices).keys())}")
        return value
    
    def validate_status(self, value):
        """Validate status is valid choice."""
        if value not in dict(ConsentStatusChoices.choices):
            raise serializers.ValidationError(f"Invalid status. Must be one of: {', '.join(dict(ConsentStatusChoices.choices).keys())}")
        return value
    
    def validate(self, data):
        """
        Cross-field validation.
        
        BUSINESS RULE: If status is 'revoked', revoked_at must be set.
        If status is 'granted', revoked_at must be None.
        """
        status = data.get('status', getattr(self.instance, 'status', None))
        revoked_at = data.get('revoked_at', getattr(self.instance, 'revoked_at', None))
        
        if status == ConsentStatusChoices.REVOKED and not revoked_at:
            raise serializers.ValidationError({
                'revoked_at': 'revoked_at is required when status is revoked.'
            })
        
        if status == ConsentStatusChoices.GRANTED and revoked_at:
            raise serializers.ValidationError({
                'revoked_at': 'revoked_at must be null when status is granted.'
            })
        
        return data


class ConsentUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for PATCH /consents/{consent_id}/.
    
    BUSINESS RULE: Only status, granted_at, and revoked_at can be updated.
    Documents are managed via separate endpoints.
    """
    class Meta:
        model = Consent
        fields = [
            'status',
            'granted_at',
            'revoked_at',
        ]
    
    def validate_status(self, value):
        """Validate status is valid choice."""
        if value not in dict(ConsentStatusChoices.choices):
            raise serializers.ValidationError(f"Invalid status. Must be one of: {', '.join(dict(ConsentStatusChoices.choices).keys())}")
        return value
    
    def validate(self, data):
        """
        Cross-field validation.
        
        BUSINESS RULE: If status is 'revoked', revoked_at must be set.
        If status is 'granted', revoked_at must be None.
        """
        status = data.get('status', self.instance.status)
        revoked_at = data.get('revoked_at', self.instance.revoked_at)
        
        if status == ConsentStatusChoices.REVOKED and not revoked_at:
            raise serializers.ValidationError({
                'revoked_at': 'revoked_at is required when status is revoked.'
            })
        
        if status == ConsentStatusChoices.GRANTED and revoked_at:
            raise serializers.ValidationError({
                'revoked_at': 'revoked_at must be null when status is granted.'
            })
        
        return data
