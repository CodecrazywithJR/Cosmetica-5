"""Sales views."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError
from .models import Sale, SaleLine
from .serializers import SaleSerializer, SaleLineSerializer, SaleTransitionSerializer


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
        sale = self.get_object()
        
        # Validate transition request
        serializer = SaleTransitionSerializer(
            data=request.data,
            context={'sale': sale, 'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        new_status = serializer.validated_data['new_status']
        reason = serializer.validated_data.get('reason')
        
        # Perform transition
        try:
            sale.transition_to(new_status, reason=reason, user=request.user)
        except ValidationError as e:
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
