"""
Core API URLs - Authentication, Health Checks, Diagnostics.
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenVerifyView

from .auth_views import CookieTokenObtainView, CookieTokenRefreshView, LogoutView
from .views import HealthCheckView, DiagnosticsView, CurrentUserView

urlpatterns = [
    # Health check
    path('healthz', HealthCheckView.as_view(), name='health-check'),
    
    # System diagnostics (staff only)
    path('ops/diagnostics', DiagnosticsView.as_view(), name='diagnostics'),
    
    # JWT Authentication (cookie-based refresh)
    path('auth/token/', CookieTokenObtainView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('auth/logout/', LogoutView.as_view(), name='auth_logout'),
    
    # Current user profile (requires authentication)
    path('auth/me/', CurrentUserView.as_view(), name='current_user'),
]
