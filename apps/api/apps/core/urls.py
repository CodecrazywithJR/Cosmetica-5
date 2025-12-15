"""
Core API URLs - Authentication, Health Checks, Diagnostics.
"""
from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from .views import HealthCheckView, DiagnosticsView

urlpatterns = [
    # Health check
    path('healthz', HealthCheckView.as_view(), name='health-check'),
    
    # System diagnostics (staff only)
    path('ops/diagnostics', DiagnosticsView.as_view(), name='diagnostics'),
    
    # JWT Authentication
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
]
