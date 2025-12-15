"""
Encounter URLs.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import EncounterViewSet

router = DefaultRouter()
router.register(r'', EncounterViewSet, basename='encounter')

urlpatterns = [
    path('', include(router.urls)),
]
