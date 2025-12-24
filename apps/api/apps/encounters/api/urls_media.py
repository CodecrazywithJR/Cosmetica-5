"""
ClinicalMedia API URLs
"""
from django.urls import path
from apps.encounters.api.views_media import ClinicalMediaViewSet

# Media endpoints
urlpatterns = [
    # Upload media to encounter
    path(
        'encounters/<int:encounter_id>/media/',
        ClinicalMediaViewSet.as_view({
            'post': 'create',
            'get': 'list'
        }),
        name='encounter-media-list'
    ),
    
    # Delete and download media
    path(
        'media/<int:pk>/',
        ClinicalMediaViewSet.as_view({
            'delete': 'destroy'
        }),
        name='media-detail'
    ),
    path(
        'media/<int:pk>/download/',
        ClinicalMediaViewSet.as_view({
            'get': 'download'
        }),
        name='media-download'
    ),
]
