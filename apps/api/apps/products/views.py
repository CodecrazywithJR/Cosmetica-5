"""Product views."""
from rest_framework import filters, viewsets
from .models import Product
from .serializers import ProductSerializer
from .permissions import ProductPermission
from apps.core.tenant import TenantQuerySetMixin


class ProductViewSet(TenantQuerySetMixin, viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [ProductPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'sku', 'category', 'brand']
    ordering_fields = ['name', 'price', 'stock_quantity']
    ordering = ['name']
