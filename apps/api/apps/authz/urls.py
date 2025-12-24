"""
Authz URLs - Practitioners
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import PractitionerViewSet

router = DefaultRouter()
router.register(r'practitioners', PractitionerViewSet, basename='practitioner')

urlpatterns = [
    path('', include(router.urls)),
]
