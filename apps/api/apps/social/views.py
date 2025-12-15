"""
Social Media API views.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import FileResponse
from .models import InstagramPost, InstagramHashtag
from .serializers import InstagramPostSerializer, InstagramHashtagSerializer
from .tasks import generate_instagram_pack


class InstagramPostViewSet(viewsets.ModelViewSet):
    """
    Instagram posts management.
    
    Endpoints:
    - GET /api/social/posts/ - List posts
    - POST /api/social/posts/ - Create post
    - GET /api/social/posts/{id}/ - Get post detail
    - PUT/PATCH /api/social/posts/{id}/ - Update post
    - DELETE /api/social/posts/{id}/ - Delete post
    - POST /api/social/posts/{id}/generate-pack/ - Generate publish pack
    - GET /api/social/posts/{id}/download-pack/ - Download pack
    """
    queryset = InstagramPost.objects.all()
    serializer_class = InstagramPostSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        """Set created_by on creation."""
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def generate_pack(self, request, pk=None):
        """
        Generate Instagram publish pack (ZIP).
        
        Triggers Celery task to create ZIP with:
        - caption.txt
        - image files from marketing bucket
        - README.txt with instructions
        """
        post = self.get_object()
        
        if not post.can_generate_pack():
            return Response(
                {
                    'error': 'Cannot generate pack',
                    'details': {
                        'status': post.status,
                        'media_count': len(post.media_keys) if post.media_keys else 0,
                        'required': 'status must be draft/ready and media_count > 0'
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Trigger Celery task
        task = generate_instagram_pack.delay(post.id)
        
        return Response(
            {
                'message': 'Pack generation started',
                'task_id': task.id,
                'post_id': post.id
            },
            status=status.HTTP_202_ACCEPTED
        )
    
    @action(detail=True, methods=['get'])
    def download_pack(self, request, pk=None):
        """
        Download generated pack ZIP.
        """
        post = self.get_object()
        
        if not post.pack_file_path:
            return Response(
                {'error': 'Pack not generated yet. Use generate-pack endpoint first.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        import os
        if not os.path.exists(post.pack_file_path):
            return Response(
                {'error': 'Pack file not found on disk. May have been cleaned up.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Return file
        return FileResponse(
            open(post.pack_file_path, 'rb'),
            as_attachment=True,
            filename=os.path.basename(post.pack_file_path)
        )
    
    @action(detail=True, methods=['post'])
    def mark_published(self, request, pk=None):
        """
        Mark post as published.
        
        Body:
        {
            "instagram_url": "https://instagram.com/p/..."
        }
        """
        post = self.get_object()
        instagram_url = request.data.get('instagram_url')
        
        post.mark_as_published(instagram_url)
        
        return Response(
            {
                'message': 'Post marked as published',
                'published_at': post.published_at,
                'instagram_url': post.instagram_url
            },
            status=status.HTTP_200_OK
        )


class InstagramHashtagViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Hashtag library (read-only for suggestions).
    """
    queryset = InstagramHashtag.objects.all()
    serializer_class = InstagramHashtagSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter by category if provided."""
        queryset = super().get_queryset()
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        return queryset
