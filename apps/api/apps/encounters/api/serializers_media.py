"""
ClinicalMedia API Serializers
"""
from rest_framework import serializers
from django.utils import timezone
from apps.encounters.models import ClinicalMedia, Encounter


class ClinicalMediaSerializer(serializers.ModelSerializer):
    """
    Serializer for ClinicalMedia upload and retrieval.
    """
    uploaded_by_name = serializers.CharField(
        source='uploaded_by.get_full_name',
        read_only=True
    )
    file_url = serializers.SerializerMethodField()
    file_size_mb = serializers.ReadOnlyField()
    
    class Meta:
        model = ClinicalMedia
        fields = [
            'id',
            'encounter',
            'media_type',
            'category',
            'file',
            'file_url',
            'file_size_mb',
            'notes',
            'uploaded_by',
            'uploaded_by_name',
            'created_at',
            'deleted_at',
        ]
        read_only_fields = ['id', 'uploaded_by', 'created_at', 'deleted_at']
    
    def get_file_url(self, obj):
        """
        Return authenticated URL (not direct file path).
        Frontend must use API endpoint with auth token.
        """
        request = self.context.get('request')
        if obj.file and request:
            # Return API endpoint, not direct media URL (security)
            return request.build_absolute_uri(
                f'/api/v1/clinical/media/{obj.id}/download/'
            )
        return None
    
    def validate_encounter(self, encounter):
        """
        Validate encounter is not cancelled.
        """
        if encounter.status == 'cancelled':
            raise serializers.ValidationError(
                "Cannot upload media to cancelled encounters."
            )
        return encounter
    
    def validate_file(self, file):
        """
        Validate file size (max 10MB).
        """
        max_size = 10 * 1024 * 1024  # 10MB
        if file.size > max_size:
            raise serializers.ValidationError(
                f"File size must be less than 10MB. Current size: {round(file.size / (1024*1024), 2)}MB"
            )
        return file
    
    def create(self, validated_data):
        """
        Create media and set uploaded_by from request user.
        """
        validated_data['uploaded_by'] = self.context['request'].user
        return super().create(validated_data)


class ClinicalMediaUploadSerializer(serializers.Serializer):
    """
    Specialized serializer for multipart/form-data upload.
    Used for POST /api/v1/clinical/encounters/{id}/media/
    """
    file = serializers.ImageField(required=True)
    category = serializers.ChoiceField(
        choices=ClinicalMedia.CATEGORY_CHOICES,
        default='other'
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_file(self, file):
        """Validate file size and type."""
        # Size check
        max_size = 10 * 1024 * 1024  # 10MB
        if file.size > max_size:
            raise serializers.ValidationError(
                f"File size must be less than 10MB. Current size: {round(file.size / (1024*1024), 2)}MB"
            )
        
        # Extension check
        allowed_extensions = ['jpg', 'jpeg', 'png', 'webp']
        ext = file.name.split('.')[-1].lower()
        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        return file
    
    def create(self, validated_data):
        """
        Create ClinicalMedia from upload.
        Encounter comes from view context.
        """
        encounter = self.context['encounter']
        user = self.context['request'].user
        
        # Validate encounter not cancelled
        if encounter.status == 'cancelled':
            raise serializers.ValidationError(
                "Cannot upload media to cancelled encounters."
            )
        
        media = ClinicalMedia.objects.create(
            encounter=encounter,
            uploaded_by=user,
            media_type='photo',  # Phase 1: photos only
            category=validated_data.get('category', 'other'),
            file=validated_data['file'],
            notes=validated_data.get('notes', '')
        )
        
        return media


class ClinicalMediaListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing media (no file URL generation).
    """
    uploaded_by_name = serializers.CharField(
        source='uploaded_by.get_full_name',
        read_only=True
    )
    
    class Meta:
        model = ClinicalMedia
        fields = [
            'id',
            'media_type',
            'category',
            'notes',
            'uploaded_by_name',
            'file_size_mb',
            'created_at',
        ]
