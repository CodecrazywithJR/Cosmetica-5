"""Sales serializers."""
from rest_framework import serializers
from decimal import Decimal
from .models import Sale, SaleLine, SaleStatusChoices


class SaleLineSerializer(serializers.ModelSerializer):
    """
    Serializer for SaleLine with business validations.
    """
    class Meta:
        model = SaleLine
        fields = [
            'id', 'sale', 'product_name', 'product_code', 'description',
            'quantity', 'unit_price', 'discount', 'line_total',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'line_total', 'created_at', 'updated_at']
    
    def validate(self, attrs):
        """
        Validate sale line business rules.
        
        1. quantity > 0
        2. unit_price >= 0
        3. discount >= 0
        4. discount <= quantity * unit_price
        5. sale must be modifiable (not closed)
        """
        quantity = attrs.get('quantity')
        unit_price = attrs.get('unit_price')
        discount = attrs.get('discount', Decimal('0.00'))
        sale = attrs.get('sale')
        
        # Handle updates: get existing values if not provided
        if self.instance:
            if quantity is None:
                quantity = self.instance.quantity
            if unit_price is None:
                unit_price = self.instance.unit_price
            if discount is None:
                discount = self.instance.discount or Decimal('0.00')
            if sale is None:
                sale = self.instance.sale
        
        # INVARIANT: quantity > 0
        if quantity is not None and quantity <= 0:
            raise serializers.ValidationError({
                'quantity': 'Quantity must be greater than 0'
            })
        
        # INVARIANT: unit_price >= 0
        if unit_price is not None and unit_price < 0:
            raise serializers.ValidationError({
                'unit_price': 'Unit price cannot be negative'
            })
        
        # INVARIANT: discount >= 0
        if discount is not None and discount < 0:
            raise serializers.ValidationError({
                'discount': 'Discount cannot be negative'
            })
        
        # INVARIANT: discount <= line subtotal
        if quantity and unit_price and discount:
            line_subtotal = quantity * unit_price
            if discount > line_subtotal:
                raise serializers.ValidationError({
                    'discount': f'Discount ({discount}) cannot exceed line subtotal ({line_subtotal})'
                })
        
        # INVARIANT: sale must be modifiable
        if sale and not sale.is_modifiable():
            raise serializers.ValidationError(
                f'Cannot modify line: sale is in {sale.get_status_display()} status. '
                f'Only draft and pending sales can be modified.'
            )
        
        return attrs


class SaleSerializer(serializers.ModelSerializer):
    """
    Serializer for Sale with business validations and nested lines.
    """
    lines = SaleLineSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_modifiable = serializers.BooleanField(read_only=True)
    is_closed = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Sale
        fields = [
            'id', 'patient', 'appointment', 'sale_number', 'status', 'status_display',
            'subtotal', 'tax', 'discount', 'total', 'currency',
            'notes', 'cancellation_reason', 'refund_reason',
            'created_at', 'updated_at', 'paid_at',
            'lines', 'is_modifiable', 'is_closed'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'paid_at',
            'subtotal', 'total',  # Calculated from lines
            'status_display', 'is_modifiable', 'is_closed'
        ]
    
    def validate(self, attrs):
        """
        Validate sale business rules.
        
        1. If appointment and patient both exist, they must match
        2. Total consistency (subtotal + tax - discount)
        3. Cannot modify closed sales
        4. Status transitions must be valid
        """
        patient = attrs.get('patient')
        appointment = attrs.get('appointment')
        status = attrs.get('status')
        subtotal = attrs.get('subtotal')
        tax = attrs.get('tax', Decimal('0.00'))
        discount = attrs.get('discount', Decimal('0.00'))
        total = attrs.get('total')
        
        # Handle updates: get existing values if not provided
        if self.instance:
            if patient is None:
                patient = self.instance.patient
            if appointment is None:
                appointment = self.instance.appointment
            if status is None:
                status = self.instance.status
            if subtotal is None:
                subtotal = self.instance.subtotal
            if tax is None:
                tax = self.instance.tax
            if discount is None:
                discount = self.instance.discount
            if total is None:
                total = self.instance.total
        
        # INVARIANT: Appointment-Patient coherence
        if appointment and patient:
            if appointment.patient_id != patient.id:
                raise serializers.ValidationError({
                    'appointment': (
                        f'Appointment patient mismatch: '
                        f'sale.patient={patient.id} but '
                        f'appointment.patient={appointment.patient_id}. '
                        f'Both must reference the same patient.'
                    )
                })
        
        # INVARIANT: Total consistency (if being set manually)
        if subtotal is not None and tax is not None and discount is not None and total is not None:
            expected_total = subtotal + tax - discount
            if abs(total - expected_total) > Decimal('0.01'):  # Allow 1 cent rounding
                raise serializers.ValidationError({
                    'total': (
                        f'Total mismatch: expected {expected_total} '
                        f'(subtotal {subtotal} + tax {tax} - discount {discount}), '
                        f'but got {total}'
                    )
                })
        
        # INVARIANT: Cannot modify closed sales (except for status transitions)
        if self.instance and not self.instance.is_modifiable():
            # Allow status transitions even when closed
            allowed_fields = {'status', 'cancellation_reason', 'refund_reason'}
            modified_fields = set(attrs.keys()) - allowed_fields
            
            if modified_fields:
                raise serializers.ValidationError(
                    f'Cannot modify {", ".join(modified_fields)}: '
                    f'sale is in {self.instance.get_status_display()} status. '
                    f'Only draft and pending sales can be modified.'
                )
        
        # INVARIANT: Status transitions must be valid
        if self.instance and status and status != self.instance.status:
            if not self.instance.can_transition_to(status):
                valid = Sale.get_valid_transitions().get(self.instance.status, [])
                raise serializers.ValidationError({
                    'status': (
                        f'Invalid transition from {self.instance.status} to {status}. '
                        f'Valid transitions: {", ".join(valid) if valid else "none (terminal state)"}. '
                        f'Use the transition endpoint instead.'
                    )
                })
        
        return attrs
    
    def validate_tax(self, value):
        """Tax must be non-negative."""
        if value < 0:
            raise serializers.ValidationError('Tax cannot be negative')
        return value
    
    def validate_discount(self, value):
        """Discount must be non-negative."""
        if value < 0:
            raise serializers.ValidationError('Discount cannot be negative')
        return value


class SaleTransitionSerializer(serializers.Serializer):
    """
    Serializer for sale status transitions.
    
    Used by POST /sales/{id}/transition/
    """
    new_status = serializers.ChoiceField(
        choices=SaleStatusChoices.choices,
        required=True,
        help_text='Target status to transition to'
    )
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text='Reason for transition (required for cancellation/refund)'
    )
    
    def validate(self, attrs):
        """Validate transition is allowed."""
        sale = self.context.get('sale')
        new_status = attrs.get('new_status')
        reason = attrs.get('reason', '')
        
        if not sale:
            raise serializers.ValidationError('Sale context required')
        
        # Check if transition is valid
        if not sale.can_transition_to(new_status):
            valid = Sale.get_valid_transitions().get(sale.status, [])
            raise serializers.ValidationError({
                'new_status': (
                    f'Invalid transition from {sale.status} to {new_status}. '
                    f'Valid transitions: {", ".join(valid) if valid else "none (terminal state)"}'
                )
            })
        
        # Require reason for cancellation/refund
        if new_status in [SaleStatusChoices.CANCELLED, SaleStatusChoices.REFUNDED]:
            if not reason or not reason.strip():
                raise serializers.ValidationError({
                    'reason': f'Reason is required when transitioning to {new_status}'
                })
        
        return attrs
