"""
Encounter serializers.
"""
from rest_framework import serializers

from apps.patients.serializers import PatientListSerializer

from .models import Encounter


class EncounterSerializer(serializers.ModelSerializer):
    """Full encounter serializer."""
    patient_details = PatientListSerializer(source='patient', read_only=True)
    
    class Meta:
        model = Encounter
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


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
