"""
Test POS Happy Path: Sale with Patient (without appointment).

Verifies that sales can be created with a patient but no appointment,
as required for POS operations where walk-in purchases are allowed.
"""
import pytest
from decimal import Decimal
from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase
from apps.clinical.models import Patient
from apps.sales.models import Sale, SaleLine, SaleStatusChoices
from apps.products.models import Product

User = get_user_model()


@pytest.mark.django_db
class TestPOSHappyPathPatientNoAppointment(TestCase):
    """Test POS happy path: Sale → Patient created without appointment → OK"""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='reception@clinic.com',
            password='testpass123'
        )

        # Create a product for the sale
        self.product = Product.objects.create(
            sku='PROD-WALK-001',
            name='Facial Cream',
            price=Decimal('75.00')
        )

    def test_sale_with_patient_no_appointment_success(self):
        """
        Test that a sale can be created with a patient but no appointment.
        
        Business Rule: Sales without appointments are allowed (POS flow).
        """
        # GIVEN: A new walk-in patient (no appointment)
        patient = Patient.objects.create(
            first_name='María',
            last_name='González',
            birth_date=date(1992, 8, 10),
            sex='F',
            email='maria.gonzalez@example.com',
            phone='+521234567890',
            blood_type='A+',
            allergies='None known'
        )

        # WHEN: Creating a sale for this patient WITHOUT an appointment
        sale = Sale.objects.create(
            patient=patient,
            appointment=None,  # No appointment (POS walk-in)
            status=SaleStatusChoices.DRAFT,
            subtotal=Decimal('150.00'),
            tax=Decimal('0.00'),
            discount=Decimal('0.00'),
            total=Decimal('150.00')
        )

        sale_line = SaleLine.objects.create(
            sale=sale,
            product=self.product,
            product_name='Facial Cream',
            quantity=2,
            unit_price=Decimal('75.00'),
            discount=Decimal('0.00'),
            line_total=Decimal('150.00')
        )

        # THEN: Sale is created successfully
        self.assertIsNotNone(sale.id)
        self.assertEqual(sale.patient, patient)
        self.assertIsNone(sale.appointment)
        self.assertEqual(sale.status, SaleStatusChoices.DRAFT)
        self.assertEqual(sale.total, Decimal('150.00'))

        # AND: Sale line is associated correctly
        self.assertEqual(sale_line.sale, sale)
        self.assertEqual(sale_line.quantity, 2)

        # AND: Patient relationship works bidirectionally
        self.assertEqual(patient.sales.count(), 1)
        self.assertEqual(patient.sales.first(), sale)

    def test_patient_with_medical_fields_in_pos_sale(self):
        """
        Test that patient medical fields are persisted when creating POS sale.
        
        Validates Patient model unification includes medical data.
        """
        # GIVEN: A patient with medical information
        patient = Patient.objects.create(
            first_name='Carlos',
            last_name='Ramírez',
            birth_date=date(1985, 3, 22),
            sex='M',
            email='carlos.ramirez@example.com',
            phone='+529876543210',
            blood_type='O-',
            allergies='Latex, Penicillin',
            medical_history='Hypertension since 2018',
            current_medications='Losartan 50mg daily'
        )

        # WHEN: Creating a POS sale
        sale = Sale.objects.create(
            patient=patient,
            appointment=None,
            status=SaleStatusChoices.PAID,
            subtotal=Decimal('200.00'),
            total=Decimal('200.00')
        )

        # THEN: Patient medical fields are accessible via sale
        sale_patient = Sale.objects.select_related('patient').get(id=sale.id).patient
        self.assertEqual(sale_patient.blood_type, 'O-')
        self.assertEqual(sale_patient.allergies, 'Latex, Penicillin')
        self.assertIn('Hypertension', sale_patient.medical_history)
        self.assertIn('Losartan', sale_patient.current_medications)

    def test_multiple_sales_same_patient_no_appointments(self):
        """
        Test that a patient can have multiple sales without appointments.
        
        Common POS scenario: Repeat walk-in customer.
        """
        # GIVEN: A patient with no appointments
        patient = Patient.objects.create(
            first_name='Ana',
            last_name='Martínez',
            birth_date=date(1995, 11, 5),
            sex='F',
            email='ana.martinez@example.com',
            phone='+521122334455'
        )

        # WHEN: Creating multiple sales for the same patient
        sale1 = Sale.objects.create(
            patient=patient,
            appointment=None,
            status=SaleStatusChoices.PAID,
            subtotal=Decimal('100.00'),
            total=Decimal('100.00')
        )

        sale2 = Sale.objects.create(
            patient=patient,
            appointment=None,
            status=SaleStatusChoices.PAID,
            subtotal=Decimal('150.00'),
            total=Decimal('150.00')
        )

        sale3 = Sale.objects.create(
            patient=patient,
            appointment=None,
            status=SaleStatusChoices.DRAFT,
            subtotal=Decimal('200.00'),
            total=Decimal('200.00')
        )

        # THEN: All sales are associated with the patient
        self.assertEqual(patient.sales.count(), 3)

        # AND: Sales can be queried by status
        paid_sales = patient.sales.filter(status=SaleStatusChoices.PAID)
        self.assertEqual(paid_sales.count(), 2)

        # AND: Total sales amount can be calculated
        total_paid = sum(s.total for s in paid_sales)
        self.assertEqual(total_paid, Decimal('250.00'))
