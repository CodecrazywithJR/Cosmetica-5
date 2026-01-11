"""
Social Media API URLs.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InstagramPostViewSet, InstagramHashtagViewSet

router = DefaultRouter()
router.register(r'posts', InstagramPostViewSet, basename='instagram-posts')
router.register(r'hashtags', InstagramHashtagViewSet, basename='instagram-hashtags')

urlpatterns = [
    path('', include(router.urls)),
]
