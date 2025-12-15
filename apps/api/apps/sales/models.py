"""Sales models - POS transactions."""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from decimal import Decimal
import uuid


class SaleStatusChoices(models.TextChoices):
    """
    Sale status choices with state machine.
    
    Transitions:
    - draft -> pending, cancelled
    - pending -> paid, cancelled
    - paid -> refunded (terminal)
    - cancelled -> (terminal)
    - refunded -> (terminal)
    """
    DRAFT = 'draft', _('Draft')
    PENDING = 'pending', _('Pending')
    PAID = 'paid', _('Paid')
    CANCELLED = 'cancelled', _('Cancelled')
    REFUNDED = 'refunded', _('Refunded')


class Sale(models.Model):
    """
    Sale transaction.
    
    Business Rules:
    - total must equal sum of line totals
    - once paid/cancelled/refunded, lines cannot be modified
    - if appointment exists and patient exists, they must match
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales',
        verbose_name=_('Patient')
    )
    appointment = models.ForeignKey(
        'clinical.Appointment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales',
        verbose_name=_('Appointment'),
        help_text=_('Optional appointment this sale is associated with')
    )
    
    # Sale details
    sale_number = models.CharField(
        _('Sale Number'),
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        help_text=_('Human-readable sale number (e.g., INV-2025-001)')
    )
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=SaleStatusChoices.choices,
        default=SaleStatusChoices.DRAFT
    )
    
    # Financial fields
    subtotal = models.DecimalField(
        _('Subtotal'),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_('Sum of line totals before tax and discounts')
    )
    tax = models.DecimalField(
        _('Tax'),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    discount = models.DecimalField(
        _('Discount'),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total = models.DecimalField(
        _('Total'),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_('Final total (subtotal + tax - discount)')
    )
    currency = models.CharField(
        _('Currency'),
        max_length=3,
        default='USD',
        help_text=_('ISO 4217 currency code')
    )
    
    # Notes
    notes = models.TextField(_('Notes'), blank=True, null=True)
    cancellation_reason = models.TextField(_('Cancellation Reason'), blank=True, null=True)
    refund_reason = models.TextField(_('Refund Reason'), blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    paid_at = models.DateTimeField(_('Paid At'), blank=True, null=True)
    
    class Meta:
        db_table = 'sales'
        ordering = ['-created_at']
        verbose_name = _('Sale')
        verbose_name_plural = _('Sales')
        indexes = [
            models.Index(fields=['-created_at'], name='idx_sale_created'),
            models.Index(fields=['status', '-created_at'], name='idx_sale_status_created'),
            models.Index(fields=['patient', '-created_at'], name='idx_sale_patient_created'),
            models.Index(fields=['sale_number'], name='idx_sale_number'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(total__gte=0),
                name='sale_total_non_negative'
            ),
            models.CheckConstraint(
                check=models.Q(subtotal__gte=0),
                name='sale_subtotal_non_negative'
            ),
            models.CheckConstraint(
                check=models.Q(tax__gte=0),
                name='sale_tax_non_negative'
            ),
            models.CheckConstraint(
                check=models.Q(discount__gte=0),
                name='sale_discount_non_negative'
            ),
        ]
    
    def __str__(self):
        number = self.sale_number or f"#{self.id}"
        return f"Sale {number} - {self.get_status_display()} - {self.currency} {self.total}"
    
    def clean(self):
        """
        Validate sale business rules.
        
        1. If appointment and patient both exist, they must match
        2. Total must be consistent with calculated total
        """
        super().clean()
        
        # INVARIANT: Appointment-Patient coherence
        if self.appointment_id and self.patient_id:
            # Load appointment if not already loaded
            if not hasattr(self, '_appointment_cache') and self.appointment:
                self._appointment_cache = self.appointment
            
            appointment = self._appointment_cache if hasattr(self, '_appointment_cache') else self.appointment
            
            if appointment and appointment.patient_id != self.patient_id:
                raise ValidationError({
                    'appointment': (
                        f'Appointment patient mismatch: '
                        f'sale.patient={self.patient_id} but '
                        f'appointment.patient={appointment.patient_id}. '
                        f'Both must reference the same patient.'
                    )
                })
        
        # INVARIANT: Total consistency
        expected_total = self.subtotal + self.tax - self.discount
        if abs(self.total - expected_total) > Decimal('0.01'):  # Allow 1 cent rounding
            raise ValidationError({
                'total': (
                    f'Total mismatch: expected {expected_total} '
                    f'(subtotal {self.subtotal} + tax {self.tax} - discount {self.discount}), '
                    f'but got {self.total}'
                )
            })
    
    def recalculate_totals(self):
        """
        Recalculate subtotal and total from lines.
        
        This should be called whenever lines are added/updated/deleted.
        """
        from django.db.models import Sum, F
        
        # Calculate subtotal from lines
        lines_total = self.lines.aggregate(
            total=Sum(F('quantity') * F('unit_price') - F('discount'))
        )['total'] or Decimal('0.00')
        
        self.subtotal = lines_total
        self.total = self.subtotal + self.tax - self.discount
        
        return self
    
    def is_modifiable(self):
        """Check if sale can be modified (lines, prices, etc.)."""
        return self.status in [SaleStatusChoices.DRAFT, SaleStatusChoices.PENDING]
    
    def is_closed(self):
        """Check if sale is in a terminal/closed state."""
        return self.status in [SaleStatusChoices.PAID, SaleStatusChoices.CANCELLED, SaleStatusChoices.REFUNDED]
    
    @classmethod
    def get_valid_transitions(cls):
        """
        Get valid status transitions.
        
        Returns dict: {current_status: [allowed_next_statuses]}
        """
        return {
            SaleStatusChoices.DRAFT: [SaleStatusChoices.PENDING, SaleStatusChoices.CANCELLED],
            SaleStatusChoices.PENDING: [SaleStatusChoices.PAID, SaleStatusChoices.CANCELLED],
            SaleStatusChoices.PAID: [SaleStatusChoices.REFUNDED],
            SaleStatusChoices.CANCELLED: [],  # Terminal
            SaleStatusChoices.REFUNDED: [],   # Terminal
        }
    
    def can_transition_to(self, new_status):
        """Check if transition to new_status is valid."""
        valid_transitions = self.get_valid_transitions()
        return new_status in valid_transitions.get(self.status, [])
    
    def transition_to(self, new_status, reason=None, user=None):
        """
        Transition sale to new status with validation.
        
        Raises ValidationError if transition is invalid.
        """
        if not self.can_transition_to(new_status):
            valid = self.get_valid_transitions().get(self.status, [])
            raise ValidationError(
                f'Invalid transition from {self.status} to {new_status}. '
                f'Valid transitions: {", ".join(valid) if valid else "none (terminal state)"}'
            )
        
        old_status = self.status
        self.status = new_status
        
        # Set reason fields
        if new_status == SaleStatusChoices.CANCELLED and reason:
            self.cancellation_reason = reason
        elif new_status == SaleStatusChoices.REFUNDED and reason:
            self.refund_reason = reason
        elif new_status == SaleStatusChoices.PAID:
            from django.utils import timezone
            self.paid_at = timezone.now()
        
        self.save()
        
        return self


class SaleLine(models.Model):
    """
    Line item in a sale.
    
    Business Rules:
    - quantity must be > 0
    - unit_price must be >= 0
    - discount must be >= 0
    - line_total = quantity * unit_price - discount
    - cannot modify if sale is closed
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name=_('Sale')
    )
    
    # Product reference (flexible: could be FK to Product or just description)
    product_name = models.CharField(_('Product/Service'), max_length=255)
    product_code = models.CharField(_('Product Code'), max_length=100, blank=True, null=True)
    description = models.TextField(_('Description'), blank=True, null=True)
    
    # Pricing
    quantity = models.DecimalField(
        _('Quantity'),
        max_digits=10,
        decimal_places=2,
        help_text=_('Must be greater than 0')
    )
    unit_price = models.DecimalField(
        _('Unit Price'),
        max_digits=10,
        decimal_places=2,
        help_text=_('Price per unit (must be >= 0)')
    )
    discount = models.DecimalField(
        _('Discount'),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_('Line-level discount (must be >= 0)')
    )
    line_total = models.DecimalField(
        _('Line Total'),
        max_digits=10,
        decimal_places=2,
        help_text=_('Calculated as quantity * unit_price - discount')
    )
    
    # Timestamps
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        db_table = 'sale_lines'
        ordering = ['created_at']
        verbose_name = _('Sale Line')
        verbose_name_plural = _('Sale Lines')
        indexes = [
            models.Index(fields=['sale'], name='idx_sale_line_sale'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gt=0),
                name='sale_line_quantity_positive'
            ),
            models.CheckConstraint(
                check=models.Q(unit_price__gte=0),
                name='sale_line_unit_price_non_negative'
            ),
            models.CheckConstraint(
                check=models.Q(discount__gte=0),
                name='sale_line_discount_non_negative'
            ),
            models.CheckConstraint(
                check=models.Q(line_total__gte=0),
                name='sale_line_total_non_negative'
            ),
        ]
    
    def __str__(self):
        return f"{self.product_name} x {self.quantity} = {self.line_total}"
    
    def clean(self):
        """Validate line business rules."""
        super().clean()
        
        # INVARIANT: quantity > 0
        if self.quantity is not None and self.quantity <= 0:
            raise ValidationError({
                'quantity': 'Quantity must be greater than 0'
            })
        
        # INVARIANT: unit_price >= 0
        if self.unit_price is not None and self.unit_price < 0:
            raise ValidationError({
                'unit_price': 'Unit price cannot be negative'
            })
        
        # INVARIANT: discount >= 0
        if self.discount is not None and self.discount < 0:
            raise ValidationError({
                'discount': 'Discount cannot be negative'
            })
        
        # INVARIANT: discount cannot exceed line subtotal
        if self.quantity and self.unit_price and self.discount:
            line_subtotal = self.quantity * self.unit_price
            if self.discount > line_subtotal:
                raise ValidationError({
                    'discount': f'Discount ({self.discount}) cannot exceed line subtotal ({line_subtotal})'
                })
        
        # INVARIANT: line_total must match calculation
        if self.quantity and self.unit_price and self.line_total is not None:
            expected_total = self.quantity * self.unit_price - (self.discount or Decimal('0.00'))
            if abs(self.line_total - expected_total) > Decimal('0.01'):
                raise ValidationError({
                    'line_total': (
                        f'Line total mismatch: expected {expected_total} '
                        f'(quantity {self.quantity} * unit_price {self.unit_price} - discount {self.discount}), '
                        f'but got {self.line_total}'
                    )
                })
        
        # INVARIANT: Cannot modify line if sale is closed
        if self.sale_id and self.sale and not self.sale.is_modifiable():
            raise ValidationError(
                f'Cannot modify line: sale is in {self.sale.get_status_display()} status. '
                f'Only draft and pending sales can be modified.'
            )
    
    def calculate_line_total(self):
        """Calculate and set line_total from quantity, unit_price, and discount."""
        self.line_total = self.quantity * self.unit_price - (self.discount or Decimal('0.00'))
        return self.line_total
    
    def save(self, *args, **kwargs):
        """Override save to auto-calculate line_total."""
        # Auto-calculate line_total if not set or needs recalculation
        if self.quantity and self.unit_price:
            self.calculate_line_total()
        
        super().save(*args, **kwargs)
        
        # Trigger sale totals recalculation
        if self.sale_id:
            self.sale.recalculate_totals()
            self.sale.save(update_fields=['subtotal', 'total', 'updated_at'])
