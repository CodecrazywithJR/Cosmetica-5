"""
Patient serializers.
"""
from rest_framework import serializers

from .models import Patient


class PatientSerializer(serializers.ModelSerializer):
    """
    Patient serializer with all fields.
    """
    full_name = serializers.ReadOnlyField()
    age = serializers.ReadOnlyField()
    
    class Meta:
        model = Patient
        fields = [
            'id',
            'first_name',
            'last_name',
            'middle_name',
            'full_name',
            'date_of_birth',
            'age',
            'gender',
            'phone',
            'email',
            'address',
            'city',
            'postal_code',
            'country',
            'blood_type',
            'allergies',
            'medical_history',
            'current_medications',
            'notes',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'full_name', 'age']


class PatientListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for patient lists.
    """
    full_name = serializers.ReadOnlyField()
    age = serializers.ReadOnlyField()
    
    class Meta:
        model = Patient
        fields = [
            'id',
            'first_name',
            'last_name',
            'full_name',
            'age',
            'gender',
            'phone',
            'email',
            'is_active',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'full_name', 'age']
