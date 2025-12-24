"""
Authz serializers for Practitioner.
"""
from rest_framework import serializers
from apps.authz.models import Practitioner, PractitionerRoleChoices


class PractitionerListSerializer(serializers.ModelSerializer):
    """
    Serializer for Practitioner list view.
    
    Used for:
    - Listing practitioners (GET /api/v1/practitioners/)
    - Reception/ClinicalOps viewing available practitioners
    """
    user_email = serializers.EmailField(source='user.email', read_only=True)
    role_type_display = serializers.CharField(source='get_role_type_display', read_only=True)
    
    class Meta:
        model = Practitioner
        fields = [
            'id',
            'user',
            'user_email',
            'display_name',
            'role_type',
            'role_type_display',
            'specialty',
            'is_active',
            'created_at',
        ]
        read_only_fields = fields


class PractitionerDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for Practitioner detail view.
    
    Used for:
    - Getting practitioner detail (GET /api/v1/practitioners/{id}/)
    """
    user_email = serializers.EmailField(source='user.email', read_only=True)
    role_type_display = serializers.CharField(source='get_role_type_display', read_only=True)
    
    class Meta:
        model = Practitioner
        fields = [
            'id',
            'user',
            'user_email',
            'display_name',
            'role_type',
            'role_type_display',
            'specialty',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class PractitionerWriteSerializer(serializers.ModelSerializer):
    """
    Serializer for Practitioner create/update (Admin only).
    
    Used for:
    - Creating practitioners (POST /api/v1/practitioners/)
    - Updating practitioners (PATCH /api/v1/practitioners/{id}/)
    """
    
    class Meta:
        model = Practitioner
        fields = [
            'id',
            'user',
            'display_name',
            'role_type',
            'specialty',
            'is_active',
        ]
        read_only_fields = ['id']
    
    def validate_user(self, value):
        """Validate user doesn't already have a practitioner record."""
        if self.instance is None:  # Creating new practitioner
            if hasattr(value, 'practitioner'):
                raise serializers.ValidationError(
                    f"User {value.email} already has a practitioner record"
                )
        return value
    
    def validate_role_type(self, value):
        """Validate role_type is a valid choice."""
        if value not in dict(PractitionerRoleChoices.choices):
            raise serializers.ValidationError(
                f"Invalid role_type. Must be one of: {', '.join(dict(PractitionerRoleChoices.choices).keys())}"
            )
        return value
