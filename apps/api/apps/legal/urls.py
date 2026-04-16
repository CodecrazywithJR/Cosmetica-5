"""
Legal Entity URL configuration — System Plane.

Mounted at: /api/v1/system/legal-entities/
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.legal.views import LegalEntityViewSet

router = DefaultRouter()
router.register(r'legal-entities', LegalEntityViewSet, basename='legal-entity')

urlpatterns = [
    path('', include(router.urls)),
]
