"""
Public API views for Website CMS.

CRITICAL RULES:
- ALL endpoints under /public/ are READ-ONLY (except leads POST)
- NO authentication required
- NO clinical data exposure
- Rate limiting on leads endpoint: 10/hour + 2/min burst protection
"""
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from django.utils import timezone
import time

from apps.core.observability import metrics, get_sanitized_logger
from apps.core.observability.events import log_domain_event

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

logger = get_sanitized_logger(__name__)


class LeadHourlyThrottle(AnonRateThrottle):
    """
    Rate limit for lead submissions: 10 per hour per IP.
    
    Prevents spam while allowing legitimate contact form usage.
    """
    scope = 'lead_submissions'


class LeadBurstThrottle(AnonRateThrottle):
    """
    Burst protection for lead submissions: 2 per minute per IP.
    
    Prevents rapid-fire spam attacks.
    """
    scope = 'lead_burst'


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
@throttle_classes([LeadBurstThrottle, LeadHourlyThrottle])
def create_lead(request):
    """
    Public endpoint for contact form submissions.
    POST /public/leads
    
    Rate limited: 10 submissions/hour + 2/min burst protection per IP.
    
    Rate limited: 3 requests per hour per IP.
    """
    start_time = time.time()
    
    serializer = LeadCreateSerializer(data=request.data)
    if serializer.is_valid():
        lead = serializer.save()
        duration_ms = int((time.time() - start_time) * 1000)
        
        # SUCCESS: Emit metrics and events
        metrics.public_leads_requests_total.labels(result='accepted').inc()
        
        log_domain_event(
            event_name='public.lead.created',
            entity_type='Lead',
            entity_id=str(lead.id),
            result='success',
            source='contact_form',
            duration_ms=duration_ms
        )
        
        logger.info(
            'Public lead created',
            extra={
                'lead_id': str(lead.id),
                'source': 'contact_form',
                'duration_ms': duration_ms
                # NOTE: email/name/phone are PHI - NEVER logged
            }
        )
        
        return Response(
            {'message': 'Thank you for your message. We will contact you soon.'},
            status=status.HTTP_201_CREATED
        )
    
    # VALIDATION ERROR
    metrics.public_leads_requests_total.labels(result='rejected').inc()
    
    logger.warning(
        'Public lead rejected - validation error',
        extra={
            'errors': serializer.errors,
            'duration_ms': int((time.time() - start_time) * 1000)
        }
    )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
