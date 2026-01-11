"""
Serializers for Website CMS - PUBLIC endpoints only.

CRITICAL: These serializers expose PUBLIC data only.
NO clinical data (patients, encounters, clinical photos).
"""
from rest_framework import serializers
from .models import (
    WebsiteSettings,
    Page,
    Post,
    Service,
    StaffMember,
    Lead,
)


class WebsiteSettingsSerializer(serializers.ModelSerializer):
    """Public website settings."""
    
    class Meta:
        model = WebsiteSettings
        fields = [
            'clinic_name',
            'phone',
            'email',
            'address',
            'opening_hours',
            'instagram_url',
            'facebook_url',
            'youtube_url',
            'default_language',
            'enabled_languages',
        ]
        read_only_fields = fields


class PageSerializer(serializers.ModelSerializer):
    """Public pages (about, contact, etc.)."""
    
    class Meta:
        model = Page
        fields = [
            'id',
            'title',
            'slug',
            'language',
            'content_json',
            'content_markdown',
            'seo_title',
            'seo_description',
            'og_image_key',
            'updated_at',
        ]
        read_only_fields = fields


class PostListSerializer(serializers.ModelSerializer):
    """Blog posts list (summary)."""
    
    class Meta:
        model = Post
        fields = [
            'id',
            'title',
            'slug',
            'language',
            'excerpt',
            'cover_image_key',
            'tags',
            'published_at',
        ]
        read_only_fields = fields


class PostDetailSerializer(serializers.ModelSerializer):
    """Blog post detail."""
    
    class Meta:
        model = Post
        fields = [
            'id',
            'title',
            'slug',
            'language',
            'excerpt',
            'content_json',
            'content_markdown',
            'cover_image_key',
            'tags',
            'seo_title',
            'seo_description',
            'published_at',
            'updated_at',
        ]
        read_only_fields = fields


class ServiceSerializer(serializers.ModelSerializer):
    """Services offered."""
    
    class Meta:
        model = Service
        fields = [
            'id',
            'name',
            'slug',
            'language',
            'description',
            'price',
            'duration_minutes',
            'order_index',
        ]
        read_only_fields = fields


class StaffMemberSerializer(serializers.ModelSerializer):
    """Team members."""
    
    class Meta:
        model = StaffMember
        fields = [
            'id',
            'name',
            'role',
            'language',
            'bio',
            'photo_key',
            'order_index',
        ]
        read_only_fields = fields


class LeadCreateSerializer(serializers.ModelSerializer):
    """Create lead from contact form submission."""
    
    class Meta:
        model = Lead
        fields = [
            'name',
            'email',
            'phone',
            'message',
            'preferred_language',
            'source',
        ]
    
    def validate_email(self, value):
        """Basic email validation."""
        if not value or '@' not in value:
            raise serializers.ValidationError("Invalid email address")
        return value.lower()
    
    def validate_message(self, value):
        """Ensure message is not too short."""
        if len(value.strip()) < 10:
            raise serializers.ValidationError("Message too short (minimum 10 characters)")
        return value
