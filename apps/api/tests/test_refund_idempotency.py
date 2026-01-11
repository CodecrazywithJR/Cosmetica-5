"""
Tests for SaleRefund idempotency at database level.

Business Rule: Idempotency is enforced via UniqueConstraint on (sale, idempotency_key).
SINGLE SOURCE OF TRUTH: idempotency_key field (metadata is legacy read-only).

- Same sale + same key → Returns existing refund (no duplicate)
- Same sale + different key → Creates new refund (if allowed by anti-over-refund rules)
- No key provided → Always creates new refund
- Legacy requests with metadata.idempotency_key → Migrated to field

Tests cover:
1. Creating refund with idempotency_key (field only, NO metadata)
2. Retrying same request (idempotent behavior)
3. Creating multiple refunds with different keys
4. Database constraint validation
5. Legacy compatibility (metadata.idempotency_key → field)
"""

import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.test import APIClient

from apps.sales.models import Sale, SaleLine, SaleRefund, SaleStatusChoices, SaleRefundStatusChoices
from apps.sales.services import refund_partial_for_sale
from apps.products.models import Product
from apps.authz.models import User


@pytest.mark.django_db
class TestSaleRefundIdempotencySingleSourceOfTruth:
    """Test idempotency with field as single source of truth (NO metadata duplication)."""
    
    @pytest.fixture
    def user(self):
        """Create test user."""
        return User.objects.create_user(
            username='test_user',
            email='test@example.com',
            password='testpass123'
        )
    
    @pytest.fixture
    def product(self):
        """Create test product."""
        return Product.objects.create(
            name='Test Product',
            sku='TEST-001',
            unit_price=Decimal('100.00'),
            is_service=False
        )
    
    @pytest.fixture
    def paid_sale(self, user, product):
        """Create a PAID sale with one line (5 units @ $100)."""
        sale = Sale.objects.create(
            patient=None,
            appointment=None,
            status=SaleStatusChoices.PAID,
            created_by=user
        )
        
        SaleLine.objects.create(
            sale=sale,
            product=product,
            product_name=product.name,
            quantity=5,
            unit_price=Decimal('100.00'),
            discount=Decimal('0.00'),
            line_total=Decimal('500.00')
        )
        
        return sale
    
    def test_create_refund_stores_key_in_field_only(self, paid_sale, user):
        """
        Test creating refund with idempotency_key.
        
        SINGLE SOURCE OF TRUTH:
        - idempotency_key stored in FIELD
        - metadata does NOT contain idempotency_key (no duplication)
        """
        sale_line = paid_sale.lines.first()
        
        refund = refund_partial_for_sale(
            sale=paid_sale,
            refund_payload={
                'reason': 'Customer returned 2 units',
                'idempotency_key': 'refund-key-123',
                'lines': [
                    {
                        'sale_line_id': str(sale_line.id),
                        'qty_refunded': 2,
                        'amount_refunded': Decimal('200.00')
                    }
                ]
            },
            created_by=user
        )
        
        # Assertions: FIELD only (no metadata)
        assert refund.idempotency_key == 'refund-key-123'
        assert 'idempotency_key' not in refund.metadata  # NO duplication
        assert refund.status == SaleRefundStatusChoices.COMPLETED
    
    def test_retry_with_same_key_returns_existing_refund(self, paid_sale, user):
        """
        Test idempotent behavior: same request twice.
        
        Expected:
        - First request creates refund
        - Second request returns SAME refund (no duplicate)
        """
        sale_line = paid_sale.lines.first()
        
        payload = {
            'reason': 'Idempotent test',
            'idempotency_key': 'retry-key-456',
            'lines': [
                {
                    'sale_line_id': str(sale_line.id),
                    'qty_refunded': 2,
                    'amount_refunded': Decimal('200.00')
                }
            ]
        }
        
        # First request
        refund1 = refund_partial_for_sale(sale=paid_sale, refund_payload=payload, created_by=user)
        
        # Second request (SAME key)
        refund2 = refund_partial_for_sale(sale=paid_sale, refund_payload=payload, created_by=user)
        
        # Assertions
        assert refund1.id == refund2.id  # SAME refund
        assert SaleRefund.objects.filter(sale=paid_sale).count() == 1
        assert refund1.idempotency_key == 'retry-key-456'
    
    def test_different_keys_create_separate_refunds(self, paid_sale, user):
        """
        Test multiple refunds with different keys.
        
        Expected:
        - Each unique key creates a new refund
        """
        sale_line = paid_sale.lines.first()
        
        # First refund
        refund1 = refund_partial_for_sale(
            sale=paid_sale,
            refund_payload={
                'idempotency_key': 'key-AAA',
                'lines': [{'sale_line_id': str(sale_line.id), 'qty_refunded': 1}]
            },
            created_by=user
        )
        
        # Second refund (different key)
        refund2 = refund_partial_for_sale(
            sale=paid_sale,
            refund_payload={
                'idempotency_key': 'key-BBB',
                'lines': [{'sale_line_id': str(sale_line.id), 'qty_refunded': 1}]
            },
            created_by=user
        )
        
        # Assertions
        assert refund1.id != refund2.id
        assert refund1.idempotency_key == 'key-AAA'
        assert refund2.idempotency_key == 'key-BBB'
        assert SaleRefund.objects.filter(sale=paid_sale).count() == 2
    
    def test_database_constraint_prevents_duplicates(self, paid_sale, user):
        """
        Test UniqueConstraint at DB level.
        
        Expected: IntegrityError when creating duplicate (sale, key)
        """
        # Create first refund
        SaleRefund.objects.create(
            sale=paid_sale,
            status=SaleRefundStatusChoices.DRAFT,
            created_by=user,
            idempotency_key='duplicate-key'
        )
        
        # Attempt duplicate
        with pytest.raises(IntegrityError) as exc_info:
            SaleRefund.objects.create(
                sale=paid_sale,
                status=SaleRefundStatusChoices.DRAFT,
                created_by=user,
                idempotency_key='duplicate-key'  # SAME key
            )
        
        assert 'uniq_sale_refund_idempotency_key' in str(exc_info.value)
    
    def test_null_key_allows_multiple_refunds(self, paid_sale, user):
        """
        Test NULL keys don't trigger constraint.
        
        Expected: Multiple refunds without key can coexist
        """
        sale_line = paid_sale.lines.first()
        
        # Two refunds without key
        refund1 = refund_partial_for_sale(
            sale=paid_sale,
            refund_payload={
                'lines': [{'sale_line_id': str(sale_line.id), 'qty_refunded': 1}]
            },
            created_by=user
        )
        
        refund2 = refund_partial_for_sale(
            sale=paid_sale,
            refund_payload={
                'lines': [{'sale_line_id': str(sale_line.id), 'qty_refunded': 1}]
            },
            created_by=user
        )
        
        # Assertions
        assert refund1.id != refund2.id
        assert refund1.idempotency_key is None
        assert refund2.idempotency_key is None
        assert SaleRefund.objects.filter(sale=paid_sale).count() == 2


@pytest.mark.django_db
class TestLegacyMetadataCompatibility:
    """Test backward compatibility with legacy metadata.idempotency_key."""
    
    @pytest.fixture
    def user(self):
        """Create test user."""
        return User.objects.create_user(
            username='legacy_user',
            email='legacy@example.com',
            password='testpass123'
        )
    
    @pytest.fixture
    def paid_sale(self, user):
        """Create PAID sale."""
        sale = Sale.objects.create(
            patient=None,
            appointment=None,
            status=SaleStatusChoices.PAID,
            created_by=user
        )
        
        product = Product.objects.create(
            name='Legacy Product',
            sku='LEGACY-001',
            unit_price=Decimal('50.00')
        )
        
        SaleLine.objects.create(
            sale=sale,
            product=product,
            product_name=product.name,
            quantity=10,
            unit_price=Decimal('50.00'),
            discount=Decimal('0.00'),
            line_total=Decimal('500.00')
        )
        
        return sale
    
    def test_legacy_request_with_metadata_key_migrates_to_field(self, paid_sale, user):
        """
        Test legacy request format: metadata.idempotency_key.
        
        Expected:
        - Service resolves key from metadata (fallback)
        - Stores in field (NOT in metadata for new record)
        """
        sale_line = paid_sale.lines.first()
        
        # Legacy payload: key in metadata
        refund = refund_partial_for_sale(
            sale=paid_sale,
            refund_payload={
                'reason': 'Legacy format',
                'metadata': {'idempotency_key': 'legacy-key-999'},  # Old format
                'lines': [{'sale_line_id': str(sale_line.id), 'qty_refunded': 1}]
            },
            created_by=user
        )
        
        # Assertions: migrated to field
        assert refund.idempotency_key == 'legacy-key-999'  # Migrated
        assert 'idempotency_key' not in refund.metadata  # NOT duplicated
    
    def test_explicit_key_takes_priority_over_metadata(self, paid_sale, user):
        """
        Test priority: explicit idempotency_key > metadata.idempotency_key.
        
        Expected:
        - Explicit key is used
        - Metadata key is ignored
        """
        sale_line = paid_sale.lines.first()
        
        refund = refund_partial_for_sale(
            sale=paid_sale,
            refund_payload={
                'idempotency_key': 'explicit-key',  # Priority
                'metadata': {'idempotency_key': 'ignored-key'},
                'lines': [{'sale_line_id': str(sale_line.id), 'qty_refunded': 1}]
            },
            created_by=user
        )
        
        # Assertions
        assert refund.idempotency_key == 'explicit-key'  # Explicit wins
    
    def test_legacy_db_records_with_metadata_key_still_queryable(self, paid_sale, user):
        """
        Test existing DB records with key only in metadata.
        
        Scenario: Pre-migration refund (field=NULL, metadata has key).
        Expected: Record exists and is queryable.
        """
        # Simulate legacy record (before migration)
        legacy_refund = SaleRefund.objects.create(
            sale=paid_sale,
            status=SaleRefundStatusChoices.COMPLETED,
            created_by=user,
            idempotency_key=None,  # NULL (not migrated yet)
            metadata={'idempotency_key': 'pre-migration-key', 'other': 'data'}
        )
        
        # Verify legacy record exists
        assert SaleRefund.objects.filter(id=legacy_refund.id).exists()
        assert legacy_refund.idempotency_key is None
        assert legacy_refund.metadata['idempotency_key'] == 'pre-migration-key'
        
        # New refund with same key in FIELD should be allowed (different constraint)
        new_refund = SaleRefund.objects.create(
            sale=paid_sale,
            status=SaleRefundStatusChoices.DRAFT,
            created_by=user,
            idempotency_key='pre-migration-key',  # SAME key but in field
            metadata={}
        )
        
        # Both coexist (constraint only applies when field NOT NULL)
        assert SaleRefund.objects.filter(sale=paid_sale).count() == 2


@pytest.mark.django_db
class TestAPIIdempotency:
    """Test idempotency via REST API."""
    
    @pytest.fixture
    def auth_client(self, user):
        """Create authenticated API client."""
        client = APIClient()
        client.force_authenticate(user=user)
        return client
    
    @pytest.fixture
    def user(self):
        """Create user with refund permissions."""
        user = User.objects.create_user(
            username='api_user',
            email='api@example.com',
            password='testpass123'
        )
        from apps.authz.models import Role
        reception_role = Role.objects.get(name='Reception')
        user.user_role.add(reception_role)
        return user
    
    @pytest.fixture
    def paid_sale(self, user):
        """Create PAID sale."""
        sale = Sale.objects.create(
            patient=None,
            appointment=None,
            status=SaleStatusChoices.PAID,
            created_by=user
        )
        
        product = Product.objects.create(
            name='API Product',
            sku='API-001',
            unit_price=Decimal('100.00')
        )
        
        SaleLine.objects.create(
            sale=sale,
            product=product,
            product_name=product.name,
            quantity=10,
            unit_price=Decimal('100.00'),
            discount=Decimal('0.00'),
            line_total=Decimal('1000.00')
        )
        
        return sale
    
    def test_api_retry_returns_same_refund(self, auth_client, paid_sale):
        """
        Test API idempotency: retry POST with same key.
        
        Expected:
        - First POST: 201 CREATED
        - Second POST: 201 CREATED (same refund ID)
        - Count remains 1
        """
        sale_line = paid_sale.lines.first()
        
        payload = {
            'idempotency_key': 'api-retry-001',
            'lines': [{'sale_line_id': str(sale_line.id), 'qty_refunded': 2}]
        }
        
        # First request
        resp1 = auth_client.post(f'/api/sales/{paid_sale.id}/refunds/', data=payload, format='json')
        
        # Second request (SAME key)
        resp2 = auth_client.post(f'/api/sales/{paid_sale.id}/refunds/', data=payload, format='json')
        
        # Assertions
        assert resp1.status_code == status.HTTP_201_CREATED
        assert resp2.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        assert resp1.data['id'] == resp2.data['id']  # SAME refund
        assert SaleRefund.objects.filter(sale=paid_sale).count() == 1

