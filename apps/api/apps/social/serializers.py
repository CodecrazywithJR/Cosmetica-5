"""
Social Media serializers.
"""
from rest_framework import serializers
from .models import InstagramPost, InstagramHashtag


class InstagramPostSerializer(serializers.ModelSerializer):
    """Instagram post serializer."""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    media_count = serializers.SerializerMethodField()
    can_generate_pack = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = InstagramPost
        fields = [
            'id',
            'caption',
            'language',
            'hashtags',
            'media_keys',
            'status',
            'scheduled_at',
            'published_at',
            'instagram_url',
            'pack_generated_at',
            'pack_file_path',
            'created_at',
            'updated_at',
            'created_by_username',
            'media_count',
            'can_generate_pack',
            'likes_count',
            'comments_count',
        ]
        read_only_fields = [
            'pack_generated_at',
            'pack_file_path',
            'created_at',
            'updated_at',
        ]
    
    def get_media_count(self, obj):
        return len(obj.media_keys) if obj.media_keys else 0


class InstagramHashtagSerializer(serializers.ModelSerializer):
    """Hashtag serializer."""
    
    class Meta:
        model = InstagramHashtag
        fields = ['id', 'tag', 'category', 'usage_count']
