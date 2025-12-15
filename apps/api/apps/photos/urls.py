"""
Photo URLs.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SkinPhotoViewSet

router = DefaultRouter()
router.register(r'', SkinPhotoViewSet, basename='photo')

urlpatterns = [
    path('', include(router.urls)),
]
