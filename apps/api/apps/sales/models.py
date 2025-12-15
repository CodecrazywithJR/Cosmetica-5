"""Sales models - POS transactions (placeholder)."""
from django.db import models
from django.utils.translation import gettext_lazy as _


class Sale(models.Model):
    """Sale transaction - basic structure."""
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales',
        verbose_name=_('Patient')
    )
    total = models.DecimalField(_('Total'), max_digits=10, decimal_places=2, default=0)
    status = models.CharField(_('Status'), max_length=20, default='completed')
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    
    class Meta:
        db_table = 'sales'
        ordering = ['-created_at']
        verbose_name = _('Sale')
        verbose_name_plural = _('Sales')
    
    def __str__(self):
        return f"Sale #{self.id} - {self.total}"
