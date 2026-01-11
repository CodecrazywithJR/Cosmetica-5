"""Sales views."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError
from apps.stock.services import InsufficientStockError, ExpiredBatchError
import time

from apps.core.observability import metrics, get_sanitized_logger
from apps.core.observability.events import log_domain_event
from apps.core.observability.tracing import trace_span

from .models import Sale, SaleLine, SaleRefund
from .serializers import (
    SaleSerializer, SaleLineSerializer, SaleTransitionSerializer,
    SaleRefundCreateSerializer, SaleRefundSerializer
)
from .permissions import IsReceptionOrClinicalOpsOrAdmin
from .services import refund_partial_for_sale

logger = get_sanitized_logger(__name__)


class SaleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Sale management with transition endpoint.
    
    Additional endpoints:
    - POST /sales/{id}/transition/ - Transition sale status
    """
    queryset = Sale.objects.all().prefetch_related('lines')
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['-created_at']
    filterset_fields = ['status', 'patient', 'appointment']
    search_fields = ['sale_number', 'notes']
    
    @action(detail=True, methods=['post'], url_path='transition')
    def transition(self, request, pk=None):
        """
        Transition sale to new status.
        
        POST /api/sales/{id}/transition/
        {
            "new_status": "paid",
            "reason": "Payment received via cash"  // optional, required for cancel/refund
        }
        
        Returns:
        - 200: Transition successful
        - 400: Invalid transition or validation error
        - 404: Sale not found
        """
        start_time = time.time()
        sale = self.get_object()
        old_status = sale.status
        
        # Validate transition request
        serializer = SaleTransitionSerializer(
            data=request.data,
            context={'sale': sale, 'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        new_status = serializer.validated_data['new_status']
        reason = serializer.validated_data.get('reason')
        
        with trace_span('sale_transition', attributes={
            'sale_id': str(sale.id),
            'from_status': old_status,
            'to_status': new_status
        }):
            # Perform transition
            try:
                sale.transition_to(new_status, reason=reason, user=request.user)
                
                # SUCCESS: Emit metrics and events
                duration_ms = int((time.time() - start_time) * 1000)
                
                metrics.sales_transition_total.labels(
                    from_status=old_status,
                    to_status=new_status,
                    result='success'
                ).inc()
                
                log_domain_event(
                    event_name='sale.transition',
                    entity_type='Sale',
                    entity_id=str(sale.id),
                    result='success',
                    from_status=old_status,
                    to_status=new_status,
                    duration_ms=duration_ms
                )
                
                logger.info(
                    f'Sale transitioned: {old_status} → {new_status}',
                    extra={
                        'sale_id': str(sale.id),
                        'from_status': old_status,
                        'to_status': new_status,
                        'duration_ms': duration_ms
                    }
                )
                
            except InsufficientStockError as e:
                metrics.sales_transition_total.labels(
                    from_status=old_status,
                    to_status=new_status,
                    result='insufficient_stock'
                ).inc()
                
                logger.warning(
                    'Sale transition failed - insufficient stock',
                    extra={
                        'sale_id': str(sale.id),
                        'from_status': old_status,
                        'to_status': new_status,
                        'error': str(e)
                    }
                )
                
                return Response(
                    {
                        'error': str(e),
                        'error_type': 'insufficient_stock',
                        'message': 'Cannot mark sale as paid: insufficient stock for one or more products'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            except ExpiredBatchError as e:
                metrics.sales_transition_total.labels(
                    from_status=old_status,
                    to_status=new_status,
                    result='expired_batch'
                ).inc()
                
                logger.warning(
                    'Sale transition failed - expired batches',
                    extra={
                        'sale_id': str(sale.id),
                        'from_status': old_status,
                        'to_status': new_status,
                        'error': str(e)
                    }
                )
                
                return Response(
                    {
                        'error': str(e),
                        'error_type': 'expired_batch',
                        'message': 'Cannot mark sale as paid: only expired stock available'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            except ValidationError as e:
                metrics.sales_transition_total.labels(
                    from_status=old_status,
                    to_status=new_status,
                    result='validation_error'
                ).inc()
                
                logger.warning(
                    'Sale transition failed - validation error',
                    extra={
                        'sale_id': str(sale.id),
                        'from_status': old_status,
                        'to_status': new_status,
                        'error': str(e)
                    }
                )
                
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Return updated sale
        output_serializer = SaleSerializer(sale, context={'request': request})
        return Response(output_serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='recalculate')
    def recalculate(self, request, pk=None):
        """
        Recalculate sale totals from lines.
        
        POST /api/sales/{id}/recalculate/
        
        Returns:
        - 200: Recalculation successful
        - 400: Sale is closed (cannot recalculate)
        - 404: Sale not found
        """
        sale = self.get_object()
        
        # Only allow recalculation for modifiable sales
        if not sale.is_modifiable():
            return Response(
                {'error': f'Cannot recalculate: sale is in {sale.get_status_display()} status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Recalculate
        sale.recalculate_totals()
        sale.save()
        
        # Return updated sale
        serializer = SaleSerializer(sale, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(
        detail=True,
        methods=['post', 'get'],
        url_path='refunds',
        permission_classes=[IsReceptionOrClinicalOpsOrAdmin]
    )
    def refunds(self, request, pk=None):
        """
        Partial refund endpoint for sales.
        
        GET /api/sales/{id}/refunds/
        - List all refunds for this sale
        - Returns: Array of SaleRefund objects
        
        POST /api/sales/{id}/refunds/
        - Create a partial (or full) refund for this sale
        - Payload: {
            "reason": "Customer returned 2 units",
            "idempotency_key": "refund-abc-123",  // optional
            "lines": [
                {"sale_line_id": "uuid", "qty_refunded": 2, "amount_refunded": 600.00},
                {"sale_line_id": "uuid", "qty_refunded": 1}
            ]
          }
        - Returns: SaleRefund object with lines and stock moves
        - Permissions: Reception, ClinicalOps, or Admin only (Marketing blocked)
        
        Business Rules:
        - Sale must be PAID
        - qty_refunded per line <= (original qty - already refunded)
        - Stock restored to exact batch/location (NO FEFO)
        - Idempotent via unique constraint
        - Transaction: all-or-nothing
        """
        sale = self.get_object()
        
        if request.method == 'GET':
            # List all refunds for this sale
            refunds = SaleRefund.objects.filter(sale=sale).order_by('-created_at')
            serializer = SaleRefundSerializer(refunds, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        elif request.method == 'POST':
            # Create partial refund
            serializer = SaleRefundCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            try:
                refund = refund_partial_for_sale(
                    sale=sale,
                    refund_payload=serializer.validated_data,
                    created_by=request.user
                )
            except ValidationError as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                return Response(
                    {
                        'error': 'Refund creation failed',
                        'detail': str(e)
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Return created refund
            output_serializer = SaleRefundSerializer(refund)
            return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class SaleLineViewSet(viewsets.ModelViewSet):
    """
    ViewSet for SaleLine management.
    
    Lines are nested under sales.
    """
    queryset = SaleLine.objects.all().select_related('sale')
    serializer_class = SaleLineSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['sale']
    
    def perform_create(self, serializer):
        """Auto-recalculate sale totals after creating line."""
        line = serializer.save()
        # Sale totals are auto-recalculated in SaleLine.save()
    
    def perform_update(self, serializer):
        """Auto-recalculate sale totals after updating line."""
        line = serializer.save()
        # Sale totals are auto-recalculated in SaleLine.save()
    
    def perform_destroy(self, instance):
        """Auto-recalculate sale totals after deleting line."""
        sale = instance.sale
        instance.delete()
        
        # Manually recalculate since line is already deleted
        if sale:
            sale.recalculate_totals()
            sale.save(update_fields=['subtotal', 'total', 'updated_at'])
