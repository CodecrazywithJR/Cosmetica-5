"""
URL configuration for EMR Dermatology project.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Public API (NO authentication required)
    path('public/', include('apps.website.urls')),
    
    # Private API (authentication required)
    path('api/', include('apps.core.urls')),  # Core API (healthz, auth)
    path('api/patients/', include('apps.patients.urls')),
    path('api/encounters/', include('apps.encounters.urls')),
    path('api/photos/', include('apps.photos.urls')),
    path('api/products/', include('apps.products.urls')),
    path('api/stock/', include('apps.stock.urls')),
    path('api/sales/', include('apps.sales.urls')),
    path('api/integrations/', include('apps.integrations.urls')),
    path('api/social/', include('apps.social.urls')),  # Social media
    
    # API Schema
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# Debug toolbar
if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
