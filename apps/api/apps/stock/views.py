"""Stock views."""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import StockMove
from .serializers import StockMoveSerializer


class StockMoveViewSet(viewsets.ModelViewSet):
    queryset = StockMove.objects.select_related('product').all()
    serializer_class = StockMoveSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['-created_at']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
