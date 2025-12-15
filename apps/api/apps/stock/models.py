"""
Stock movement models with batch and expiry support.

Layer 2 A3: Stock/Inventory Domain Integrity
- Batch tracking with expiry dates
- FEFO (First Expired, First Out) allocation
- Multi-location support
- Auditable stock movements
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
import uuid


class StockLocationTypeChoices(models.TextChoices):
    """Location type choices."""
    WAREHOUSE = 'warehouse', _('Warehouse')
    CABINET = 'cabinet', _('Cabinet')
    CLINIC_ROOM = 'clinic_room', _('Clinic Room')
    OTHER = 'other', _('Other')


class StockMoveTypeChoices(models.TextChoices):
    """
    Stock movement types with clear IN/OUT semantics.
    
    IN movements: quantity > 0
    OUT movements: quantity < 0 (or use absolute value + type)
    """
    PURCHASE_IN = 'purchase_in', _('Purchase In')
    ADJUSTMENT_IN = 'adjustment_in', _('Adjustment In')
    TRANSFER_IN = 'transfer_in', _('Transfer In')
    
    SALE_OUT = 'sale_out', _('Sale Out')
    ADJUSTMENT_OUT = 'adjustment_out', _('Adjustment Out')
    WASTE_OUT = 'waste_out', _('Waste Out')
    TRANSFER_OUT = 'transfer_out', _('Transfer Out')


class StockLocation(models.Model):
    """
    Physical location where stock is stored.
    
    Examples: Main Warehouse, Treatment Room 1, Reception Cabinet
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    name = models.CharField(_('Name'), max_length=255)
    code = models.CharField(_('Code'), max_length=50, unique=True)
    location_type = models.CharField(
        _('Location Type'),
        max_length=20,
        choices=StockLocationTypeChoices.choices,
        default=StockLocationTypeChoices.WAREHOUSE
    )
    is_active = models.BooleanField(_('Active'), default=True)
    
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'stock_locations'
        ordering = ['name']
        verbose_name = _('Stock Location')
        verbose_name_plural = _('Stock Locations')
        indexes = [
            models.Index(fields=['code'], name='idx_location_code'),
            models.Index(fields=['is_active'], name='idx_location_active'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class StockBatch(models.Model):
    """
    Batch/Lot tracking for products with expiry dates.
    
    Business Rules:
    - batch_number unique per product
    - expiry_date required for products with expiry
    - FEFO allocation uses expiry_date
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='batches',
        verbose_name=_('Product')
    )
    batch_number = models.CharField(
        _('Batch Number'),
        max_length=100,
        help_text=_('Unique batch/lot number per product')
    )
    expiry_date = models.DateField(
        _('Expiry Date'),
        null=True,
        blank=True,
        help_text=_('Date when batch expires. Required for expirable products.')
    )
    received_at = models.DateField(
        _('Received Date'),
        default=timezone.now,
        help_text=_('Date when batch was received')
    )
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional batch information (supplier, quality checks, etc.)')
    )
    
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'stock_batches'
        ordering = ['expiry_date', 'batch_number']
        verbose_name = _('Stock Batch')
        verbose_name_plural = _('Stock Batches')
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'batch_number'],
                name='unique_batch_per_product'
            ),
        ]
        indexes = [
            models.Index(fields=['product', 'expiry_date'], name='idx_batch_prod_expiry'),
            models.Index(fields=['expiry_date'], name='idx_batch_expiry'),
            models.Index(fields=['batch_number'], name='idx_batch_number'),
        ]
    
    def __str__(self):
        expiry_str = f" (exp: {self.expiry_date})" if self.expiry_date else ""
        return f"{self.product.sku} - {self.batch_number}{expiry_str}"
    
    def clean(self):
        """Validate batch rules."""
        super().clean()
        
        # INVARIANT: Cannot use expired batch (checked at allocation time, not creation)
        # This validation is informational only
        if self.expiry_date and self.expiry_date < timezone.now().date():
            # Warning: batch is already expired
            pass
    
    @property
    def is_expired(self):
        """Check if batch is expired."""
        if not self.expiry_date:
            return False
        return self.expiry_date < timezone.now().date()
    
    @property
    def days_until_expiry(self):
        """Calculate days until expiry."""
        if not self.expiry_date:
            return None
        delta = self.expiry_date - timezone.now().date()
        return delta.days


class StockMove(models.Model):
    """
    Stock movement - auditable transactions.
    
    Business Rules:
    - quantity cannot be 0
    - IN movements: quantity > 0
    - OUT movements: quantity < 0
    - batch required for batch-tracked products
    - cannot consume from expired batch
    - cannot consume more than available
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='stock_moves',
        verbose_name=_('Product')
    )
    location = models.ForeignKey(
        StockLocation,
        on_delete=models.CASCADE,
        related_name='stock_moves',
        verbose_name=_('Location')
    )
    batch = models.ForeignKey(
        StockBatch,
        on_delete=models.CASCADE,
        related_name='stock_moves',
        verbose_name=_('Batch'),
        null=True,
        blank=True,
        help_text=_('Required for batch-tracked products')
    )
    
    move_type = models.CharField(
        _('Move Type'),
        max_length=20,
        choices=StockMoveTypeChoices.choices
    )
    quantity = models.IntegerField(
        _('Quantity'),
        help_text=_('Positive for IN, negative for OUT')
    )
    
    # Reference to originating document (Sale, Adjustment, etc.)
    reference_type = models.CharField(
        _('Reference Type'),
        max_length=50,
        blank=True,
        help_text=_('Type of document: Sale, SaleLine, Adjustment, etc.')
    )
    reference_id = models.CharField(
        _('Reference ID'),
        max_length=255,
        blank=True,
        help_text=_('ID of the referenced document')
    )
    
    reason = models.TextField(_('Reason'), blank=True)
    
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Created By')
    )
    
    class Meta:
        db_table = 'stock_moves'
        ordering = ['-created_at']
        verbose_name = _('Stock Move')
        verbose_name_plural = _('Stock Moves')
        constraints = [
            models.CheckConstraint(
                check=~models.Q(quantity=0),
                name='stock_move_quantity_non_zero'
            ),
        ]
        indexes = [
            models.Index(fields=['product', '-created_at'], name='idx_move_product'),
            models.Index(fields=['location', '-created_at'], name='idx_move_location'),
            models.Index(fields=['batch', '-created_at'], name='idx_move_batch'),
            models.Index(fields=['move_type', '-created_at'], name='idx_move_type'),
            models.Index(fields=['reference_type', 'reference_id'], name='idx_move_reference'),
        ]
    
    def __str__(self):
        batch_str = f" [{self.batch.batch_number}]" if self.batch else ""
        return f"{self.get_move_type_display()} - {self.product}{batch_str} ({self.quantity})"
    
    def clean(self):
        """Validate stock move rules."""
        super().clean()
        
        # INVARIANT: quantity != 0
        if self.quantity == 0:
            raise ValidationError({'quantity': 'Quantity cannot be zero'})
        
        # INVARIANT: IN movements must have positive quantity
        in_types = [
            StockMoveTypeChoices.PURCHASE_IN,
            StockMoveTypeChoices.ADJUSTMENT_IN,
            StockMoveTypeChoices.TRANSFER_IN,
        ]
        if self.move_type in in_types and self.quantity < 0:
            raise ValidationError({
                'quantity': f'{self.get_move_type_display()} must have positive quantity'
            })
        
        # INVARIANT: OUT movements must have negative quantity
        out_types = [
            StockMoveTypeChoices.SALE_OUT,
            StockMoveTypeChoices.ADJUSTMENT_OUT,
            StockMoveTypeChoices.WASTE_OUT,
            StockMoveTypeChoices.TRANSFER_OUT,
        ]
        if self.move_type in out_types and self.quantity > 0:
            raise ValidationError({
                'quantity': f'{self.get_move_type_display()} must have negative quantity'
            })
        
        # INVARIANT: batch required if product uses batches (check at service level)
        # This is validated at the service layer
        
        # INVARIANT: Cannot consume from expired batch
        if self.batch and self.batch.is_expired and self.quantity < 0:
            raise ValidationError({
                'batch': f'Cannot consume from expired batch {self.batch.batch_number} '
                        f'(expired on {self.batch.expiry_date})'
            })
    
    @property
    def is_inbound(self):
        """Check if movement is inbound (IN)."""
        return self.quantity > 0
    
    @property
    def is_outbound(self):
        """Check if movement is outbound (OUT)."""
        return self.quantity < 0


class StockOnHand(models.Model):
    """
    Current stock level per product/location/batch.
    
    This is a calculated/cached view for performance.
    Updated automatically by StockMove operations.
    
    Business Rules:
    - quantity_on_hand >= 0 (no negative stock)
    - unique per (product, location, batch)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='stock_on_hand',
        verbose_name=_('Product')
    )
    location = models.ForeignKey(
        StockLocation,
        on_delete=models.CASCADE,
        related_name='stock_on_hand',
        verbose_name=_('Location')
    )
    batch = models.ForeignKey(
        StockBatch,
        on_delete=models.CASCADE,
        related_name='stock_on_hand',
        verbose_name=_('Batch')
    )
    
    quantity_on_hand = models.IntegerField(
        _('Quantity On Hand'),
        default=0,
        help_text=_('Current available quantity')
    )
    
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'stock_on_hand'
        ordering = ['product', 'location', 'batch']
        verbose_name = _('Stock On Hand')
        verbose_name_plural = _('Stock On Hand')
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'location', 'batch'],
                name='unique_stock_on_hand'
            ),
            models.CheckConstraint(
                check=models.Q(quantity_on_hand__gte=0),
                name='stock_on_hand_non_negative'
            ),
        ]
        indexes = [
            models.Index(fields=['product', 'location'], name='idx_onhand_prod_loc'),
            models.Index(fields=['location', 'product'], name='idx_onhand_loc_prod'),
            models.Index(fields=['batch'], name='idx_onhand_batch'),
        ]
    
    def __str__(self):
        return f"{self.product.sku} @ {self.location.code} [{self.batch.batch_number}]: {self.quantity_on_hand}"
    
    def clean(self):
        """Validate stock on hand rules."""
        super().clean()
        
        # INVARIANT: quantity_on_hand >= 0
        if self.quantity_on_hand < 0:
            raise ValidationError({
                'quantity_on_hand': 'Stock quantity cannot be negative'
            })
