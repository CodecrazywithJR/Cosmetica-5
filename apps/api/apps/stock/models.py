"""Stock movement models."""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings


class StockMove(models.Model):
    """Stock movement - IN/OUT transactions."""
    MOVE_TYPE_CHOICES = [
        ('in', _('Stock In')),
        ('out', _('Stock Out')),
        ('adjustment', _('Adjustment')),
    ]
    
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='stock_moves',
        verbose_name=_('Product')
    )
    move_type = models.CharField(_('Type'), max_length=20, choices=MOVE_TYPE_CHOICES)
    quantity = models.IntegerField(_('Quantity'))
    reason = models.TextField(_('Reason'), blank=True)
    reference = models.CharField(_('Reference'), max_length=255, blank=True)
    
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
    
    def __str__(self):
        return f"{self.get_move_type_display()} - {self.product} ({self.quantity})"
