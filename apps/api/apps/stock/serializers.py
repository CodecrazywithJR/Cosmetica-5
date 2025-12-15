"""Stock serializers with batch and expiry validation."""
from rest_framework import serializers
from django.utils import timezone
from .models import (
    StockLocation,
    StockBatch,
    StockMove,
    StockOnHand,
    StockMoveTypeChoices,
)


class StockLocationSerializer(serializers.ModelSerializer):
    """Serializer for StockLocation."""
    
    class Meta:
        model = StockLocation
        fields = [
            'id', 'name', 'code', 'location_type', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_code(self, value):
        """Ensure code is unique."""
        instance = self.instance
        if instance:
            # Update: check uniqueness excluding self
            if StockLocation.objects.exclude(pk=instance.pk).filter(code=value).exists():
                raise serializers.ValidationError(
                    f'Location code "{value}" already exists'
                )
        else:
            # Create: check uniqueness
            if StockLocation.objects.filter(code=value).exists():
                raise serializers.ValidationError(
                    f'Location code "{value}" already exists'
                )
        return value


class StockBatchSerializer(serializers.ModelSerializer):
    """Serializer for StockBatch with expiry validation."""
    
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = StockBatch
        fields = [
            'id', 'product', 'product_sku', 'product_name',
            'batch_number', 'expiry_date', 'received_at', 'metadata',
            'is_expired', 'days_until_expiry',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_expired', 'days_until_expiry']
    
    def validate(self, attrs):
        """Validate batch business rules."""
        product = attrs.get('product')
        batch_number = attrs.get('batch_number')
        expiry_date = attrs.get('expiry_date')
        
        # Handle updates
        if self.instance:
            if not product:
                product = self.instance.product
            if not batch_number:
                batch_number = self.instance.batch_number
            if expiry_date is None:
                expiry_date = self.instance.expiry_date
        
        # INVARIANT: batch_number unique per product
        if product and batch_number:
            existing = StockBatch.objects.filter(
                product=product,
                batch_number=batch_number
            )
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise serializers.ValidationError({
                    'batch_number': f'Batch "{batch_number}" already exists for product {product.sku}'
                })
        
        # INVARIANT: expiry_date should not be in the past (warning, not error)
        if expiry_date and expiry_date < timezone.now().date():
            # Allow creating expired batches (for historical data)
            # but warn the user
            pass
        
        return attrs


class StockMoveSerializer(serializers.ModelSerializer):
    """Serializer for StockMove with business validation."""
    
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    location_code = serializers.CharField(source='location.code', read_only=True)
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)
    is_inbound = serializers.BooleanField(read_only=True)
    is_outbound = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = StockMove
        fields = [
            'id', 'product', 'product_sku', 'product_name',
            'location', 'location_code',
            'batch', 'batch_number',
            'move_type', 'quantity',
            'reference_type', 'reference_id', 'reason',
            'is_inbound', 'is_outbound',
            'created_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at', 'is_inbound', 'is_outbound']
    
    def validate(self, attrs):
        """Validate stock move business rules."""
        quantity = attrs.get('quantity')
        move_type = attrs.get('move_type')
        batch = attrs.get('batch')
        
        # Handle updates
        if self.instance:
            if quantity is None:
                quantity = self.instance.quantity
            if not move_type:
                move_type = self.instance.move_type
            if batch is None:
                batch = self.instance.batch
        
        # INVARIANT: quantity != 0
        if quantity == 0:
            raise serializers.ValidationError({
                'quantity': 'Quantity cannot be zero'
            })
        
        # INVARIANT: IN movements must have positive quantity
        in_types = [
            StockMoveTypeChoices.PURCHASE_IN,
            StockMoveTypeChoices.ADJUSTMENT_IN,
            StockMoveTypeChoices.TRANSFER_IN,
        ]
        if move_type in in_types and quantity < 0:
            raise serializers.ValidationError({
                'quantity': f'{move_type} must have positive quantity'
            })
        
        # INVARIANT: OUT movements must have negative quantity
        out_types = [
            StockMoveTypeChoices.SALE_OUT,
            StockMoveTypeChoices.ADJUSTMENT_OUT,
            StockMoveTypeChoices.WASTE_OUT,
            StockMoveTypeChoices.TRANSFER_OUT,
        ]
        if move_type in out_types and quantity > 0:
            raise serializers.ValidationError({
                'quantity': f'{move_type} must have negative quantity. Use negative values for OUT movements.'
            })
        
        # INVARIANT: Cannot consume from expired batch
        if batch and batch.is_expired and quantity < 0:
            raise serializers.ValidationError({
                'batch': f'Cannot consume from expired batch {batch.batch_number} (expired on {batch.expiry_date})'
            })
        
        # INVARIANT: Batch required for OUT movements (enforced at service level for FEFO)
        # For manual moves, we still require batch
        if move_type in out_types and not batch:
            raise serializers.ValidationError({
                'batch': 'Batch is required for OUT movements. Use FEFO service for automatic allocation.'
            })
        
        return attrs


class StockOnHandSerializer(serializers.ModelSerializer):
    """Serializer for StockOnHand (read-only)."""
    
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    location_code = serializers.CharField(source='location.code', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    batch_number = serializers.CharField(source='batch.batch_number', read_only=True)
    batch_expiry_date = serializers.DateField(source='batch.expiry_date', read_only=True)
    batch_is_expired = serializers.BooleanField(source='batch.is_expired', read_only=True)
    
    class Meta:
        model = StockOnHand
        fields = [
            'id', 'product', 'product_sku', 'product_name',
            'location', 'location_code', 'location_name',
            'batch', 'batch_number', 'batch_expiry_date', 'batch_is_expired',
            'quantity_on_hand',
            'updated_at'
        ]
        read_only_fields = fields  # All fields read-only


class StockOutFEFOSerializer(serializers.Serializer):
    """
    Serializer for creating stock OUT movements using FEFO allocation.
    
    Used by service endpoint to consume stock automatically.
    """
    product = serializers.PrimaryKeyRelatedField(
        queryset=__import__('apps.products.models', fromlist=['Product']).Product.objects.all()
    )
    location = serializers.PrimaryKeyRelatedField(
        queryset=StockLocation.objects.filter(is_active=True)
    )
    quantity = serializers.IntegerField(min_value=1)
    move_type = serializers.ChoiceField(
        choices=[
            StockMoveTypeChoices.SALE_OUT,
            StockMoveTypeChoices.WASTE_OUT,
            StockMoveTypeChoices.ADJUSTMENT_OUT,
            StockMoveTypeChoices.TRANSFER_OUT,
        ]
    )
    reason = serializers.CharField(required=False, allow_blank=True)
    reference_type = serializers.CharField(required=False, allow_blank=True)
    reference_id = serializers.CharField(required=False, allow_blank=True)
    allow_expired = serializers.BooleanField(default=False)
    
    def validate_quantity(self, value):
        """Quantity must be positive."""
        if value <= 0:
            raise serializers.ValidationError('Quantity must be positive')
        return value
