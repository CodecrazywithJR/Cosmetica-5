"""
Public API views for Website CMS.

CRITICAL RULES:
- ALL endpoints under /public/ are READ-ONLY (except leads POST)
- NO authentication required
- NO clinical data exposure
- Rate limiting on leads endpoint
"""
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from django.utils import timezone
from .models import (
    WebsiteSettings,
    Page,
    Post,
    Service,
    StaffMember,
    Lead,
)
from .serializers import (
    WebsiteSettingsSerializer,
    PageSerializer,
    PostListSerializer,
    PostDetailSerializer,
    ServiceSerializer,
    StaffMemberSerializer,
    LeadCreateSerializer,
)


class LeadThrottle(AnonRateThrottle):
    """Rate limit for lead submissions: 3 per hour."""
    rate = '3/hour'


class PublicWebsiteSettingsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public endpoint for website settings.
    GET /public/content/settings
    """
    queryset = WebsiteSettings.objects.all()
    serializer_class = WebsiteSettingsSerializer
    permission_classes = []  # No auth required
    authentication_classes = []  # No auth required
    
    def list(self, request, *args, **kwargs):
        """Return singleton settings."""
        settings = WebsiteSettings.get_settings()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)


class PublicPageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public endpoint for pages.
    GET /public/content/pages
    GET /public/content/pages/{slug}?language=en
    """
    serializer_class = PageSerializer
    permission_classes = []
    authentication_classes = []
    lookup_field = 'slug'
    
    def get_queryset(self):
        """Filter by status=published and optional language."""
        queryset = Page.objects.filter(status='published')
        language = self.request.query_params.get('language')
        if language:
            queryset = queryset.filter(language=language)
        return queryset


class PublicPostViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public endpoint for blog posts.
    GET /public/content/posts - list
    GET /public/content/posts/{slug}?language=en - detail
    """
    permission_classes = []
    authentication_classes = []
    lookup_field = 'slug'
    
    def get_queryset(self):
        """Filter by status=published and optional language."""
        queryset = Post.objects.filter(
            status='published',
            published_at__lte=timezone.now()
        )
        language = self.request.query_params.get('language')
        if language:
            queryset = queryset.filter(language=language)
        
        # Filter by tag
        tag = self.request.query_params.get('tag')
        if tag:
            queryset = queryset.filter(tags__contains=[tag])
        
        return queryset
    
    def get_serializer_class(self):
        """Use different serializer for list vs detail."""
        if self.action == 'list':
            return PostListSerializer
        return PostDetailSerializer


class PublicServiceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public endpoint for services.
    GET /public/content/services?language=en
    """
    serializer_class = ServiceSerializer
    permission_classes = []
    authentication_classes = []
    
    def get_queryset(self):
        """Filter by status=published and optional language."""
        queryset = Service.objects.filter(status='published')
        language = self.request.query_params.get('language')
        if language:
            queryset = queryset.filter(language=language)
        return queryset


class PublicStaffViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public endpoint for staff/team members.
    GET /public/content/staff?language=en
    """
    serializer_class = StaffMemberSerializer
    permission_classes = []
    authentication_classes = []
    
    def get_queryset(self):
        """Filter by status=published and optional language."""
        queryset = StaffMember.objects.filter(status='published')
        language = self.request.query_params.get('language')
        if language:
            queryset = queryset.filter(language=language)
        return queryset


@api_view(['POST'])
@throttle_classes([LeadThrottle])
def create_lead(request):
    """
    Public endpoint for contact form submissions.
    POST /public/leads
    
    Rate limited: 3 requests per hour per IP.
    """
    serializer = LeadCreateSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(
            {'message': 'Thank you for your message. We will contact you soon.'},
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
