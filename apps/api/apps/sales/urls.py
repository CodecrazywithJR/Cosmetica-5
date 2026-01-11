"""Sales URLs."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import SaleViewSet, SaleLineViewSet

router = DefaultRouter()
router.register(r'sales', SaleViewSet, basename='sale')
router.register(r'lines', SaleLineViewSet, basename='sale-line')

urlpatterns = [
    path('', include(router.urls)),
]
