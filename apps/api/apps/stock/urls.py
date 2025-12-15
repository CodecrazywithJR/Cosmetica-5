"""Stock URLs."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import StockMoveViewSet

router = DefaultRouter()
router.register(r'', StockMoveViewSet, basename='stock-move')

urlpatterns = [
    path('', include(router.urls)),
]
