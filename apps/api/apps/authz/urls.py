"""
Authz URLs - Practitioners and User Administration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import PractitionerViewSet
from .views_users import UserAdminViewSet

router = DefaultRouter()
router.register(r'practitioners', PractitionerViewSet, basename='practitioner')
router.register(r'users', UserAdminViewSet, basename='user-admin')

urlpatterns = [
    path('', include(router.urls)),
]
