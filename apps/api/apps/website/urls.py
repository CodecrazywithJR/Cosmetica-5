"""
URL routing for public website content API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PublicWebsiteSettingsViewSet,
    PublicPageViewSet,
    PublicPostViewSet,
    PublicServiceViewSet,
    PublicStaffViewSet,
    create_lead,
)

router = DefaultRouter()
router.register(r'settings', PublicWebsiteSettingsViewSet, basename='public-settings')
router.register(r'pages', PublicPageViewSet, basename='public-pages')
router.register(r'posts', PublicPostViewSet, basename='public-posts')
router.register(r'services', PublicServiceViewSet, basename='public-services')
router.register(r'staff', PublicStaffViewSet, basename='public-staff')

urlpatterns = [
    path('content/', include(router.urls)),
    path('leads/', create_lead, name='public-leads'),
]
