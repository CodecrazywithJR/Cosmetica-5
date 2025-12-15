"""Stock serializers."""
from rest_framework import serializers
from .models import StockMove


class StockMoveSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    class Meta:
        model = StockMove
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'created_by', 'product_name']
