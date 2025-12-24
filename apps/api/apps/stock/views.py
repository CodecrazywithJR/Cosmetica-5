"""Stock views with batch and FEFO support."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.core.exceptions import ValidationError

from .models import (
    StockLocation,
    StockBatch,
    StockMove,
    StockOnHand,
    StockMoveTypeChoices,
)
from .serializers import (
    StockLocationSerializer,
    StockBatchSerializer,
    StockMoveSerializer,
    StockOnHandSerializer,
    StockOutFEFOSerializer,
)
from .services import (
    create_stock_out_fefo,
    get_stock_summary,
    InsufficientStockError,
    ExpiredBatchError,
)
from .permissions import IsClinicalOpsOrAdmin


class StockLocationViewSet(viewsets.ModelViewSet):
    """ViewSet for StockLocation management."""
    
    queryset = StockLocation.objects.all()
    serializer_class = StockLocationSerializer
    permission_classes = [IsClinicalOpsOrAdmin]
    filterset_fields = ['is_active', 'location_type']
    search_fields = ['name', 'code']
    ordering = ['name']


class StockBatchViewSet(viewsets.ModelViewSet):
    """ViewSet for StockBatch management."""
    
    queryset = StockBatch.objects.select_related('product').all()
    serializer_class = StockBatchSerializer
    permission_classes = [IsClinicalOpsOrAdmin]
    filterset_fields = ['product']
    search_fields = ['batch_number', 'product__sku', 'product__name']
    ordering = ['expiry_date', 'batch_number']
    
    @action(detail=False, methods=['get'], url_path='expiring-soon')
    def expiring_soon(self, request):
        """
        Get batches expiring within specified days.
        
        Query params:
        - days: number of days (default 30)
        """
        from django.utils import timezone
        from datetime import timedelta
        
        days = int(request.query_params.get('days', 30))
        cutoff_date = timezone.now().date() + timedelta(days=days)
        
        batches = self.get_queryset().filter(
            expiry_date__lte=cutoff_date,
            expiry_date__gte=timezone.now().date()
        )
        
        serializer = self.get_serializer(batches, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='expired')
    def expired(self, request):
        """Get all expired batches with stock."""
        from django.utils import timezone
        
        # Get expired batches that still have stock
        batch_ids_with_stock = StockOnHand.objects.filter(
            quantity_on_hand__gt=0
        ).values_list('batch_id', flat=True)
        
        batches = self.get_queryset().filter(
            id__in=batch_ids_with_stock,
            expiry_date__lt=timezone.now().date()
        )
        
        serializer = self.get_serializer(batches, many=True)
        return Response(serializer.data)


class StockMoveViewSet(viewsets.ModelViewSet):
    """ViewSet for StockMove management."""
    
    queryset = StockMove.objects.select_related(
        'product', 'location', 'batch'
    ).all()
    serializer_class = StockMoveSerializer
    permission_classes = [IsClinicalOpsOrAdmin]
    filterset_fields = ['product', 'location', 'batch', 'move_type']
    search_fields = ['product__sku', 'product__name', 'reason']
    ordering = ['-created_at']
    
    def perform_create(self, serializer):
        """Auto-set created_by to current user."""
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['post'], url_path='consume-fefo')
    def consume_fefo(self, request):
        """
        Consume stock using FEFO allocation.
        
        POST /api/stock/moves/consume-fefo/
        {
            "product": "uuid-product-id",
            "location": "uuid-location-id",
            "quantity": 10,
            "move_type": "sale_out",
            "reason": "Sale #INV-2025-001",
            "reference_type": "Sale",
            "reference_id": "uuid-sale-id",
            "allow_expired": false
        }
        
        Returns list of created StockMove instances.
        """
        serializer = StockOutFEFOSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            moves = create_stock_out_fefo(
                product=serializer.validated_data['product'],
                location=serializer.validated_data['location'],
                quantity=serializer.validated_data['quantity'],
                move_type=serializer.validated_data['move_type'],
                reference_type=serializer.validated_data.get('reference_type', ''),
                reference_id=serializer.validated_data.get('reference_id', ''),
                reason=serializer.validated_data.get('reason', ''),
                created_by=request.user,
                allow_expired=serializer.validated_data.get('allow_expired', False)
            )
            
            output_serializer = StockMoveSerializer(moves, many=True)
            return Response(output_serializer.data, status=status.HTTP_201_CREATED)
            
        except InsufficientStockError as e:
            return Response(
                {'error': str(e), 'error_type': 'insufficient_stock'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except ExpiredBatchError as e:
            return Response(
                {'error': str(e), 'error_type': 'expired_batch'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class StockOnHandViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for StockOnHand (read-only).
    
    Stock levels are updated automatically by StockMove operations.
    """
    queryset = StockOnHand.objects.select_related(
        'product', 'location', 'batch'
    ).all()
    serializer_class = StockOnHandSerializer
    permission_classes = [IsClinicalOpsOrAdmin]
    filterset_fields = ['product', 'location', 'batch']
    search_fields = ['product__sku', 'product__name', 'batch__batch_number']
    ordering = ['product', 'location', 'batch']
    
    @action(detail=False, methods=['get'], url_path='by-product/(?P<product_id>[^/.]+)')
    def by_product(self, request, product_id=None):
        """
        Get stock summary for a specific product.
        
        GET /api/stock/on-hand/by-product/{product_id}/
        """
        from apps.products.models import Product
        
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        summary = get_stock_summary(product)
        
        # Also include detailed records
        records = self.get_queryset().filter(product=product, quantity_on_hand__gt=0)
        serializer = self.get_serializer(records, many=True)
        
        return Response({
            'summary': summary,
            'records': serializer.data
        })
