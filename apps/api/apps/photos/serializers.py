"""
Photo serializers.
"""
from rest_framework import serializers

from .models import SkinPhoto


class SkinPhotoSerializer(serializers.ModelSerializer):
    """Full skin photo serializer."""
    
    class Meta:
        model = SkinPhoto
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'thumbnail', 'thumbnail_generated']


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
