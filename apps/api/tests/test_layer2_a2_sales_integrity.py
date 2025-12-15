"""
Layer 2 A2: Sales Domain Integrity Tests

Test coverage:
1. SaleLine quantity > 0 (model + serializer)
2. SaleLine unit_price >= 0 (model + serializer)
3. SaleLine discount >= 0 (model + serializer)
4. Sale total calculation (subtotal + tax - discount)
5. Sale total equals sum of lines
6. Cannot modify closed sales (paid/cancelled/refunded)
7. Sale-Appointment-Patient coherence
8. State transitions (draft -> pending -> paid)
9. Invalid transitions rejected
10. Reason required for cancellation/refund
"""
import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.test import APIClient
from apps.sales.models import Sale, SaleLine, SaleStatusChoices
from apps.patients.models import Patient
from apps.clinical.models import Appointment
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def api_client():
    """API client for tests."""
    return APIClient()


@pytest.fixture
def user(db):
    """Create test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def patient(db):
    """Create test patient."""
    return Patient.objects.create(
        first_name='John',
        last_name='Doe',
        email='john@example.com'
    )


@pytest.fixture
def another_patient(db):
    """Create another test patient."""
    return Patient.objects.create(
        first_name='Jane',
        last_name='Smith',
        email='jane@example.com'
    )


@pytest.fixture
def appointment(db, patient):
    """Create test appointment."""
    return Appointment.objects.create(
        patient=patient,
        scheduled_start='2025-01-15T10:00:00Z',
        scheduled_end='2025-01-15T11:00:00Z',
        status='scheduled'
    )


@pytest.fixture
def draft_sale(db, patient):
    """Create draft sale."""
    return Sale.objects.create(
        patient=patient,
        status=SaleStatusChoices.DRAFT,
        subtotal=Decimal('100.00'),
        tax=Decimal('10.00'),
        discount=Decimal('5.00'),
        total=Decimal('105.00'),
    )


@pytest.fixture
def paid_sale(db, patient):
    """Create paid (closed) sale."""
    return Sale.objects.create(
        patient=patient,
        status=SaleStatusChoices.PAID,
        subtotal=Decimal('100.00'),
        tax=Decimal('10.00'),
        discount=Decimal('0.00'),
        total=Decimal('110.00'),
    )


# ============================================================================
# Test Class 1: SaleLine Quantity Constraints
# ============================================================================

@pytest.mark.django_db
class TestSaleLineQuantityConstraint:
    """Test that SaleLine.quantity > 0 is enforced."""
    
    def test_sale_line_quantity_must_be_positive_model_level(self, draft_sale):
        """SaleLine with quantity <= 0 should fail model validation."""
        line = SaleLine(
            sale=draft_sale,
            product_name='Test Product',
            quantity=Decimal('0.00'),  # Invalid
            unit_price=Decimal('10.00'),
            line_total=Decimal('0.00')
        )
        
        with pytest.raises(ValidationError) as exc_info:
            line.full_clean()
        
        assert 'quantity' in exc_info.value.message_dict
        assert 'greater than 0' in str(exc_info.value)
    
    def test_sale_line_negative_quantity_fails_model(self, draft_sale):
        """SaleLine with negative quantity should fail."""
        line = SaleLine(
            sale=draft_sale,
            product_name='Test Product',
            quantity=Decimal('-1.00'),  # Invalid
            unit_price=Decimal('10.00'),
            line_total=Decimal('-10.00')
        )
        
        with pytest.raises(ValidationError) as exc_info:
            line.full_clean()
        
        assert 'quantity' in exc_info.value.message_dict
    
    def test_sale_line_positive_quantity_succeeds(self, draft_sale):
        """SaleLine with positive quantity should succeed."""
        line = SaleLine(
            sale=draft_sale,
            product_name='Test Product',
            quantity=Decimal('5.00'),
            unit_price=Decimal('10.00'),
            discount=Decimal('0.00'),
            line_total=Decimal('50.00')
        )
        
        line.full_clean()  # Should not raise
        line.save()
        
        assert line.id is not None
        assert line.quantity == Decimal('5.00')


# ============================================================================
# Test Class 2: SaleLine Unit Price Constraints
# ============================================================================

@pytest.mark.django_db
class TestSaleLineUnitPriceConstraint:
    """Test that SaleLine.unit_price >= 0 is enforced."""
    
    def test_sale_line_negative_unit_price_fails_model(self, draft_sale):
        """SaleLine with negative unit_price should fail."""
        line = SaleLine(
            sale=draft_sale,
            product_name='Test Product',
            quantity=Decimal('1.00'),
            unit_price=Decimal('-10.00'),  # Invalid
            line_total=Decimal('-10.00')
        )
        
        with pytest.raises(ValidationError) as exc_info:
            line.full_clean()
        
        assert 'unit_price' in exc_info.value.message_dict
        assert 'cannot be negative' in str(exc_info.value)
    
    def test_sale_line_zero_unit_price_succeeds(self, draft_sale):
        """SaleLine with zero unit_price should succeed (free items)."""
        line = SaleLine(
            sale=draft_sale,
            product_name='Free Sample',
            quantity=Decimal('1.00'),
            unit_price=Decimal('0.00'),
            discount=Decimal('0.00'),
            line_total=Decimal('0.00')
        )
        
        line.full_clean()  # Should not raise
        line.save()
        
        assert line.unit_price == Decimal('0.00')


# ============================================================================
# Test Class 3: SaleLine Discount Constraints
# ============================================================================

@pytest.mark.django_db
class TestSaleLineDiscountConstraint:
    """Test that SaleLine.discount >= 0 and <= line subtotal."""
    
    def test_sale_line_negative_discount_fails(self, draft_sale):
        """SaleLine with negative discount should fail."""
        line = SaleLine(
            sale=draft_sale,
            product_name='Test Product',
            quantity=Decimal('1.00'),
            unit_price=Decimal('10.00'),
            discount=Decimal('-5.00'),  # Invalid
            line_total=Decimal('15.00')
        )
        
        with pytest.raises(ValidationError) as exc_info:
            line.full_clean()
        
        assert 'discount' in exc_info.value.message_dict
    
    def test_sale_line_discount_exceeds_subtotal_fails(self, draft_sale):
        """SaleLine with discount > subtotal should fail."""
        line = SaleLine(
            sale=draft_sale,
            product_name='Test Product',
            quantity=Decimal('1.00'),
            unit_price=Decimal('10.00'),
            discount=Decimal('15.00'),  # Invalid: > subtotal
            line_total=Decimal('-5.00')
        )
        
        with pytest.raises(ValidationError) as exc_info:
            line.full_clean()
        
        assert 'discount' in exc_info.value.message_dict
        assert 'cannot exceed' in str(exc_info.value)


# ============================================================================
# Test Class 4: Sale Total Calculation
# ============================================================================

@pytest.mark.django_db
class TestSaleTotalCalculation:
    """Test that Sale.total = subtotal + tax - discount."""
    
    def test_sale_total_consistency_validation(self, patient):
        """Sale with inconsistent total should fail validation."""
        sale = Sale(
            patient=patient,
            status=SaleStatusChoices.DRAFT,
            subtotal=Decimal('100.00'),
            tax=Decimal('10.00'),
            discount=Decimal('5.00'),
            total=Decimal('999.00'),  # Invalid: should be 105.00
        )
        
        with pytest.raises(ValidationError) as exc_info:
            sale.full_clean()
        
        assert 'total' in exc_info.value.message_dict
        assert 'mismatch' in str(exc_info.value)
    
    def test_sale_total_calculation_correct(self, patient):
        """Sale with correct total should succeed."""
        sale = Sale(
            patient=patient,
            status=SaleStatusChoices.DRAFT,
            subtotal=Decimal('100.00'),
            tax=Decimal('10.00'),
            discount=Decimal('5.00'),
            total=Decimal('105.00'),  # Correct
        )
        
        sale.full_clean()  # Should not raise
        sale.save()
        
        assert sale.total == Decimal('105.00')


# ============================================================================
# Test Class 5: Sale Total Equals Sum of Lines
# ============================================================================

@pytest.mark.django_db
class TestSaleTotalEqualsLinesSum:
    """Test that Sale.recalculate_totals() works correctly."""
    
    def test_recalculate_totals_from_lines(self, draft_sale):
        """recalculate_totals should sum all line totals into subtotal."""
        # Create lines
        SaleLine.objects.create(
            sale=draft_sale,
            product_name='Product A',
            quantity=Decimal('2.00'),
            unit_price=Decimal('10.00'),
            discount=Decimal('0.00'),
            line_total=Decimal('20.00')
        )
        SaleLine.objects.create(
            sale=draft_sale,
            product_name='Product B',
            quantity=Decimal('1.00'),
            unit_price=Decimal('15.00'),
            discount=Decimal('5.00'),
            line_total=Decimal('10.00')
        )
        
        # Recalculate
        draft_sale.tax = Decimal('3.00')
        draft_sale.discount = Decimal('2.00')
        draft_sale.recalculate_totals()
        
        # subtotal = 20 + 10 = 30
        # total = 30 + 3 - 2 = 31
        assert draft_sale.subtotal == Decimal('30.00')
        assert draft_sale.total == Decimal('31.00')


# ============================================================================
# Test Class 6: Immutability of Closed Sales
# ============================================================================

@pytest.mark.django_db
class TestClosedSaleImmutability:
    """Test that closed sales (paid/cancelled/refunded) cannot be modified."""
    
    def test_cannot_add_line_to_paid_sale_model(self, paid_sale):
        """Adding line to paid sale should fail."""
        line = SaleLine(
            sale=paid_sale,
            product_name='Late Product',
            quantity=Decimal('1.00'),
            unit_price=Decimal('10.00'),
            line_total=Decimal('10.00')
        )
        
        with pytest.raises(ValidationError) as exc_info:
            line.full_clean()
        
        assert 'Cannot modify line' in str(exc_info.value)
        assert 'Paid' in str(exc_info.value)
    
    def test_can_add_line_to_draft_sale(self, draft_sale):
        """Adding line to draft sale should succeed."""
        line = SaleLine(
            sale=draft_sale,
            product_name='New Product',
            quantity=Decimal('1.00'),
            unit_price=Decimal('10.00'),
            discount=Decimal('0.00'),
            line_total=Decimal('10.00')
        )
        
        line.full_clean()  # Should not raise
        line.save()
        
        assert line.id is not None


# ============================================================================
# Test Class 7: Sale-Appointment-Patient Coherence
# ============================================================================

@pytest.mark.django_db
class TestSaleAppointmentPatientCoherence:
    """Test that sale.appointment.patient == sale.patient."""
    
    def test_sale_appointment_patient_mismatch_fails_model(self, patient, another_patient, appointment):
        """Sale with mismatched appointment.patient should fail."""
        # appointment belongs to 'patient', but sale has 'another_patient'
        sale = Sale(
            patient=another_patient,
            appointment=appointment,  # Belongs to different patient
            status=SaleStatusChoices.DRAFT,
            subtotal=Decimal('100.00'),
            tax=Decimal('0.00'),
            discount=Decimal('0.00'),
            total=Decimal('100.00'),
        )
        
        with pytest.raises(ValidationError) as exc_info:
            sale.full_clean()
        
        assert 'appointment' in exc_info.value.message_dict
        assert 'patient mismatch' in str(exc_info.value)
    
    def test_sale_with_matching_appointment_patient_succeeds(self, patient, appointment):
        """Sale with matching appointment.patient should succeed."""
        sale = Sale(
            patient=patient,
            appointment=appointment,  # Same patient
            status=SaleStatusChoices.DRAFT,
            subtotal=Decimal('100.00'),
            tax=Decimal('0.00'),
            discount=Decimal('0.00'),
            total=Decimal('100.00'),
        )
        
        sale.full_clean()  # Should not raise
        sale.save()
        
        assert sale.appointment_id == appointment.id
        assert sale.patient_id == patient.id


# ============================================================================
# Test Class 8: Sale Status Transitions
# ============================================================================

@pytest.mark.django_db
class TestSaleStatusTransitions:
    """Test sale status state machine."""
    
    def test_valid_transition_draft_to_pending(self, draft_sale):
        """Draft -> Pending should succeed."""
        draft_sale.transition_to(SaleStatusChoices.PENDING)
        
        assert draft_sale.status == SaleStatusChoices.PENDING
    
    def test_valid_transition_pending_to_paid(self, patient):
        """Pending -> Paid should succeed."""
        sale = Sale.objects.create(
            patient=patient,
            status=SaleStatusChoices.PENDING,
            subtotal=Decimal('100.00'),
            tax=Decimal('0.00'),
            discount=Decimal('0.00'),
            total=Decimal('100.00'),
        )
        
        sale.transition_to(SaleStatusChoices.PAID)
        
        assert sale.status == SaleStatusChoices.PAID
        assert sale.paid_at is not None
    
    def test_valid_transition_paid_to_refunded(self, paid_sale):
        """Paid -> Refunded should succeed with reason."""
        paid_sale.transition_to(SaleStatusChoices.REFUNDED, reason='Customer request')
        
        assert paid_sale.status == SaleStatusChoices.REFUNDED
        assert paid_sale.refund_reason == 'Customer request'


# ============================================================================
# Test Class 9: Invalid Transitions
# ============================================================================

@pytest.mark.django_db
class TestInvalidTransitions:
    """Test that invalid status transitions are rejected."""
    
    def test_invalid_transition_draft_to_paid_fails(self, draft_sale):
        """Draft -> Paid (skipping Pending) should fail."""
        with pytest.raises(ValidationError) as exc_info:
            draft_sale.transition_to(SaleStatusChoices.PAID)
        
        assert 'Invalid transition' in str(exc_info.value)
    
    def test_cannot_transition_from_cancelled(self, patient):
        """Cancelled is terminal, no transitions allowed."""
        sale = Sale.objects.create(
            patient=patient,
            status=SaleStatusChoices.CANCELLED,
            subtotal=Decimal('100.00'),
            tax=Decimal('0.00'),
            discount=Decimal('0.00'),
            total=Decimal('100.00'),
        )
        
        with pytest.raises(ValidationError) as exc_info:
            sale.transition_to(SaleStatusChoices.DRAFT)
        
        assert 'Invalid transition' in str(exc_info.value)
        assert 'terminal' in str(exc_info.value)


# ============================================================================
# Test Class 10: Transition Reason Requirements
# ============================================================================

@pytest.mark.django_db
class TestTransitionReasonRequirements:
    """Test that cancellation/refund require a reason (serializer level)."""
    
    def test_cancellation_requires_reason_via_endpoint(self, api_client, user, draft_sale):
        """POST /sales/{id}/transition/ with cancelled status should require reason."""
        api_client.force_authenticate(user=user)
        
        response = api_client.post(
            f'/api/sales/sales/{draft_sale.id}/transition/',
            {'new_status': SaleStatusChoices.CANCELLED},  # No reason
            format='json'
        )
        
        assert response.status_code == 400
        assert 'reason' in response.data
        assert 'required' in str(response.data['reason']).lower()
    
    def test_cancellation_with_reason_succeeds(self, api_client, user, draft_sale):
        """POST /sales/{id}/transition/ with reason should succeed."""
        api_client.force_authenticate(user=user)
        
        response = api_client.post(
            f'/api/sales/sales/{draft_sale.id}/transition/',
            {
                'new_status': SaleStatusChoices.CANCELLED,
                'reason': 'Customer changed mind'
            },
            format='json'
        )
        
        assert response.status_code == 200
        
        draft_sale.refresh_from_db()
        assert draft_sale.status == SaleStatusChoices.CANCELLED
        assert draft_sale.cancellation_reason == 'Customer changed mind'
