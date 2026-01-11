"""
Product models - Cosmetic product catalog.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _


class Product(models.Model):
    """
    Product model - cosmetic products for POS.
    """
    # Basic info
    sku = models.CharField(_('SKU'), max_length=100, unique=True)
    name = models.CharField(_('Name'), max_length=255)
    description = models.TextField(_('Description'), blank=True)
    category = models.CharField(_('Category'), max_length=100, blank=True)
    brand = models.CharField(_('Brand'), max_length=100, blank=True)
    
    # Pricing
    price = models.DecimalField(_('Price'), max_digits=10, decimal_places=2)
    cost = models.DecimalField(_('Cost'), max_digits=10, decimal_places=2, default=0)
    
    # Inventory
    stock_quantity = models.IntegerField(_('Stock Quantity'), default=0)
    low_stock_threshold = models.IntegerField(_('Low Stock Threshold'), default=10)
    
    # Status
    is_active = models.BooleanField(_('Active'), default=True)
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'products'
        ordering = ['name']
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['name']),
            models.Index(fields=['category']),
        ]
        verbose_name = _('Product')
        verbose_name_plural = _('Products')
    
    def __str__(self):
        return f"{self.name} ({self.sku})"
    
    @property
    def is_low_stock(self):
        """Check if stock is below threshold."""
        return self.stock_quantity <= self.low_stock_threshold
