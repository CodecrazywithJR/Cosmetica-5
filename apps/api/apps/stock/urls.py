"""Stock URLs."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (
    StockLocationViewSet,
    StockBatchViewSet,
    StockMoveViewSet,
    StockOnHandViewSet,
)

router = DefaultRouter()
router.register(r'locations', StockLocationViewSet, basename='stock-location')
router.register(r'batches', StockBatchViewSet, basename='stock-batch')
router.register(r'moves', StockMoveViewSet, basename='stock-move')
router.register(r'on-hand', StockOnHandViewSet, basename='stock-onhand')

urlpatterns = [
    path('', include(router.urls)),
]
