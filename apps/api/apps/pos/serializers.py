"""Serializers for POS patient operations."""
from rest_framework import serializers
from apps.clinical.models import Patient


class POSPatientSearchResultSerializer(serializers.Serializer):
    """
    Serializer for patient search results in POS.
    
    Returns only basic identifying information, NO medical fields.
    """
    id = serializers.UUIDField(read_only=True)
    full_name_normalized = serializers.CharField(read_only=True)
    identity_confidence = serializers.CharField(read_only=True)
    phone_masked = serializers.CharField(read_only=True)
    email_masked = serializers.CharField(read_only=True)
    match_reason = serializers.CharField(read_only=True)
    score = serializers.FloatField(read_only=True)


class POSPatientUpsertSerializer(serializers.Serializer):
    """
    Serializer for upserting patients in POS.
    
    Minimal required fields, no medical information.
    """
    first_name = serializers.CharField(max_length=100, required=True)
    last_name = serializers.CharField(max_length=100, required=True)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    birth_date = serializers.DateField(required=False, allow_null=True)
    sex = serializers.ChoiceField(
        choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other'), ('U', 'Unknown')],
        required=False,
        allow_null=True
    )
    
    def validate(self, data):
        """Ensure at least phone or email is provided."""
        phone = data.get('phone')
        email = data.get('email')
        
        if not phone and not email:
            raise serializers.ValidationError(
                "At least one of 'phone' or 'email' must be provided."
            )
        
        return data


class POSPatientUpsertResponseSerializer(serializers.Serializer):
    """Response serializer for upsert operation."""
    patient = POSPatientSearchResultSerializer()
    created = serializers.BooleanField()
    match_reason = serializers.CharField()
