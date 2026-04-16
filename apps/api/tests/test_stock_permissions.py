"""
Tests for stock module RBAC permissions.

Tests verify that:
- Reception users CANNOT access any stock endpoints (403)
- Marketing users CANNOT access any stock endpoints (403)
- ClinicalOps users CAN access all stock endpoints (200/201)
- Superusers CAN access all stock endpoints (200/201)
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.authz.models import User, Role, UserRole, RoleChoices
from apps.products.models import Product
from tests.conftest import TEST_PASSWORD
from apps.stock.models import (
    StockLocation,
    StockBatch,
    StockMove,
    StockOnHand,
    StockMoveTypeChoices,
)


@pytest.fixture
def reception_user(db):
    """Create user with Reception role."""
    user = User.objects.create_user(
        email='reception@test.com',
        password=TEST_PASSWORD
    )
    reception_role, _ = Role.objects.get_or_create(name=RoleChoices.RECEPTION)
    UserRole.objects.create(user=user, role=reception_role)
    return user


@pytest.fixture
def marketing_user(db):
    """Create user with Marketing role."""
    user = User.objects.create_user(
        email='marketing@test.com',
        password=TEST_PASSWORD
    )
    marketing_role, _ = Role.objects.get_or_create(name=RoleChoices.MARKETING)
    UserRole.objects.create(user=user, role=marketing_role)
    return user


@pytest.fixture
def clinicalops_user(db):
    """Create user with Practitioner role (replaces ClinicalOps group)."""
    user = User.objects.create_user(
        email='clinicalops@test.com',
        password=TEST_PASSWORD
    )
    practitioner_role, _ = Role.objects.get_or_create(name=RoleChoices.PRACTITIONER)
    UserRole.objects.create(user=user, role=practitioner_role)
    return user


@pytest.fixture
def superuser(db):
    """Create superuser with Admin role."""
    user = User.objects.create_superuser(
        email='admin@test.com',
        password=TEST_PASSWORD
    )
    admin_role, _ = Role.objects.get_or_create(name=RoleChoices.ADMIN)
    UserRole.objects.create(user=user, role=admin_role)
    return user


@pytest.fixture
def superuser_client(superuser, legal_entity):
    """Superuser APIClient with mandatory X-Legal-Entity-ID header."""
    from rest_framework.test import APIClient
    c = APIClient()
    c.force_authenticate(user=superuser)
    c.credentials(HTTP_X_LEGAL_ENTITY_ID=str(legal_entity.id))
    return c


@pytest.fixture
def test_product(db):
    """Create test product for stock operations."""
    return Product.objects.create(
        sku='TEST-STOCK-001',
        name='Test Stock Product',
        price=Decimal('100.00')
    )


@pytest.fixture
def test_location(db):
    """Create test stock location."""
    return StockLocation.objects.create(
        code='TEST-LOC',
        name='Test Location',
        location_type='warehouse'
    )


@pytest.fixture
def test_batch(test_product):
    """Create test stock batch."""
    return StockBatch.objects.create(
        product=test_product,
        batch_number='BATCH-TEST-001',
        expiry_date=date.today() + timedelta(days=365),
        received_at=date.today()
    )


@pytest.fixture
def test_stock_move(test_product, test_location, test_batch, clinicalops_user):
    """Create test stock move (requires clinicalops user for creation)."""
    move = StockMove(
        product=test_product,
        location=test_location,
        batch=test_batch,
        move_type=StockMoveTypeChoices.PURCHASE_IN,
        quantity=Decimal('100.00'),
        reason='Test stock in',
        created_by=clinicalops_user
    )
    move.save(skip_validation=True)
    return move


# ============================================================================
# Reception User Tests (Should get 403 on ALL endpoints)
# ============================================================================

@pytest.mark.django_db
class TestReceptionStockPermissions:
    """Test that Reception users cannot access stock endpoints."""
    
    def test_reception_cannot_list_stock_locations(self, reception_user):
        """Reception user gets 403 when listing stock locations."""
        client = APIClient()
        client.force_authenticate(user=reception_user)
        
        response = client.get('/api/stock/locations/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'Practitioner' in response.data.get('detail', '')
    
    def test_reception_cannot_create_stock_location(self, reception_user):
        """Reception user gets 403 when creating stock location."""
        client = APIClient()
        client.force_authenticate(user=reception_user)
        
        data = {
            'code': 'REC-LOC',
            'name': 'Reception Location',
            'location_type': 'warehouse'
        }
        response = client.post('/api/stock/locations/', data)
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_reception_cannot_list_batches(self, reception_user):
        """Reception user gets 403 when listing batches."""
        client = APIClient()
        client.force_authenticate(user=reception_user)
        
        response = client.get('/api/stock/batches/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_reception_cannot_access_expiring_soon(self, reception_user):
        """Reception user gets 403 on expiring-soon endpoint."""
        client = APIClient()
        client.force_authenticate(user=reception_user)
        
        response = client.get('/api/stock/batches/expiring-soon/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_reception_cannot_access_expired_batches(self, reception_user):
        """Reception user gets 403 on expired endpoint."""
        client = APIClient()
        client.force_authenticate(user=reception_user)
        
        response = client.get('/api/stock/batches/expired/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_reception_cannot_list_stock_moves(self, reception_user):
        """Reception user gets 403 when listing stock moves."""
        client = APIClient()
        client.force_authenticate(user=reception_user)
        
        response = client.get('/api/stock/moves/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_reception_cannot_consume_fefo(self, reception_user, test_product, test_location):
        """Reception user gets 403 on consume-fefo endpoint."""
        client = APIClient()
        client.force_authenticate(user=reception_user)
        
        data = {
            'product': str(test_product.id),
            'location': str(test_location.id),
            'quantity': 10,
            'move_type': 'sale_out',
            'reason': 'Test consumption'
        }
        response = client.post('/api/stock/moves/consume-fefo/', data)
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_reception_cannot_list_on_hand(self, reception_user):
        """Reception user gets 403 when listing on-hand stock."""
        client = APIClient()
        client.force_authenticate(user=reception_user)
        
        response = client.get('/api/stock/on-hand/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_reception_cannot_access_by_product(self, reception_user, test_product):
        """Reception user gets 403 on by-product endpoint."""
        client = APIClient()
        client.force_authenticate(user=reception_user)
        
        response = client.get(f'/api/stock/on-hand/by-product/{test_product.id}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# Marketing User Tests (Should get 403 on ALL endpoints)
# ============================================================================

@pytest.mark.django_db
class TestMarketingStockPermissions:
    """Test that Marketing users cannot access stock endpoints."""
    
    def test_marketing_cannot_list_stock_locations(self, marketing_user):
        """Marketing user gets 403 when listing stock locations."""
        client = APIClient()
        client.force_authenticate(user=marketing_user)
        
        response = client.get('/api/stock/locations/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_marketing_cannot_list_batches(self, marketing_user):
        """Marketing user gets 403 when listing batches."""
        client = APIClient()
        client.force_authenticate(user=marketing_user)
        
        response = client.get('/api/stock/batches/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_marketing_cannot_access_expiring_soon(self, marketing_user):
        """Marketing user gets 403 on expiring-soon endpoint."""
        client = APIClient()
        client.force_authenticate(user=marketing_user)
        
        response = client.get('/api/stock/batches/expiring-soon/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_marketing_cannot_list_stock_moves(self, marketing_user):
        """Marketing user gets 403 when listing stock moves."""
        client = APIClient()
        client.force_authenticate(user=marketing_user)
        
        response = client.get('/api/stock/moves/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_marketing_cannot_consume_fefo(self, marketing_user, test_product, test_location):
        """Marketing user gets 403 on consume-fefo endpoint."""
        client = APIClient()
        client.force_authenticate(user=marketing_user)
        
        data = {
            'product': str(test_product.id),
            'location': str(test_location.id),
            'quantity': 10,
            'move_type': 'sale_out',
            'reason': 'Test consumption'
        }
        response = client.post('/api/stock/moves/consume-fefo/', data)
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_marketing_cannot_list_on_hand(self, marketing_user):
        """Marketing user gets 403 when listing on-hand stock."""
        client = APIClient()
        client.force_authenticate(user=marketing_user)
        
        response = client.get('/api/stock/on-hand/')
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# ClinicalOps User Tests (Should get 200/201 on ALL endpoints)
# ============================================================================

@pytest.mark.django_db
class TestClinicalOpsStockPermissions:
    """Test that ClinicalOps users CAN access all stock endpoints."""
    
    def test_clinicalops_can_list_stock_locations(self, clinicalops_user, test_location):
        """ClinicalOps user can list stock locations."""
        client = APIClient()
        client.force_authenticate(user=clinicalops_user)
        
        response = client.get('/api/stock/locations/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_clinicalops_can_create_stock_location(self, clinicalops_user):
        """ClinicalOps user can create stock location."""
        client = APIClient()
        client.force_authenticate(user=clinicalops_user)
        
        data = {
            'code': 'CLIN-LOC',
            'name': 'Clinical Location',
            'location_type': 'warehouse'
        }
        response = client.post('/api/stock/locations/', data)
        assert response.status_code == status.HTTP_201_CREATED
    
    def test_clinicalops_can_list_batches(self, clinicalops_user, test_batch):
        """ClinicalOps user can list batches."""
        client = APIClient()
        client.force_authenticate(user=clinicalops_user)
        
        response = client.get('/api/stock/batches/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_clinicalops_can_access_expiring_soon(self, clinicalops_user):
        """ClinicalOps user can access expiring-soon endpoint."""
        client = APIClient()
        client.force_authenticate(user=clinicalops_user)
        
        response = client.get('/api/stock/batches/expiring-soon/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_clinicalops_can_access_expired_batches(self, clinicalops_user):
        """ClinicalOps user can access expired endpoint."""
        client = APIClient()
        client.force_authenticate(user=clinicalops_user)
        
        response = client.get('/api/stock/batches/expired/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_clinicalops_can_list_stock_moves(self, clinicalops_user, test_stock_move):
        """ClinicalOps user can list stock moves."""
        client = APIClient()
        client.force_authenticate(user=clinicalops_user)
        
        response = client.get('/api/stock/moves/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_clinicalops_can_create_stock_move(self, clinicalops_user, test_product, test_location, test_batch):
        """ClinicalOps user can create stock move."""
        client = APIClient()
        client.force_authenticate(user=clinicalops_user)
        
        data = {
            'product': str(test_product.id),
            'location': str(test_location.id),
            'batch': str(test_batch.id),
            'move_type': 'purchase_in',
            'quantity': '50.00',
            'reason': 'Test purchase'
        }
        response = client.post('/api/stock/moves/', data)
        assert response.status_code == status.HTTP_201_CREATED
    
    def test_clinicalops_can_consume_fefo(self, clinicalops_user, test_product, test_location, test_batch, test_stock_move):
        """ClinicalOps user can consume stock via FEFO."""
        client = APIClient()
        client.force_authenticate(user=clinicalops_user)
        
        data = {
            'product': str(test_product.id),
            'location': str(test_location.id),
            'quantity': '10.00',
            'move_type': 'sale_out',
            'reason': 'Test FEFO consumption'
        }
        response = client.post('/api/stock/moves/consume-fefo/', data)
        # FEFO requires stock to exist - 400 is acceptable if insufficient stock
        # The key test is permissions (not 403)
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            # Verify it's a business logic error, not permission error
            assert 'error' in response.data or 'detail' not in response.data or 'ClinicalOps' not in str(response.data)
    
    def test_clinicalops_can_list_on_hand(self, clinicalops_user):
        """ClinicalOps user can list on-hand stock."""
        client = APIClient()
        client.force_authenticate(user=clinicalops_user)
        
        response = client.get('/api/stock/on-hand/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_clinicalops_can_access_by_product(self, clinicalops_user, test_product):
        """ClinicalOps user can access by-product endpoint."""
        client = APIClient()
        client.force_authenticate(user=clinicalops_user)
        
        response = client.get(f'/api/stock/on-hand/by-product/{test_product.id}/')
        assert response.status_code == status.HTTP_200_OK


# ============================================================================
# Superuser Tests (Should get 200/201 on ALL endpoints)
# ============================================================================

@pytest.mark.django_db
class TestSuperuserStockPermissions:
    """Test that superusers CAN access all stock endpoints."""
    
    def test_superuser_can_list_stock_locations(self, superuser_client, test_location):
        """Superuser can list stock locations."""
        response = superuser_client.get('/api/stock/locations/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_superuser_can_create_stock_location(self, superuser_client):
        """Superuser can create stock location."""
        data = {
            'code': 'ADMIN-LOC',
            'name': 'Admin Location',
            'location_type': 'warehouse'
        }
        response = superuser_client.post('/api/stock/locations/', data)
        assert response.status_code == status.HTTP_201_CREATED
    
    def test_superuser_can_list_batches(self, superuser_client, test_batch):
        """Superuser can list batches."""
        response = superuser_client.get('/api/stock/batches/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_superuser_can_access_expiring_soon(self, superuser_client):
        """Superuser can access expiring-soon endpoint."""
        response = superuser_client.get('/api/stock/batches/expiring-soon/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_superuser_can_list_stock_moves(self, superuser_client, test_stock_move):
        """Superuser can list stock moves."""
        response = superuser_client.get('/api/stock/moves/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_superuser_can_create_stock_move(self, superuser_client, test_product, test_location, test_batch):
        """Superuser can create stock move."""
        data = {
            'product': str(test_product.id),
            'location': str(test_location.id),
            'batch': str(test_batch.id),
            'move_type': 'purchase_in',
            'quantity': '75.00',
            'reason': 'Admin purchase'
        }
        response = superuser_client.post('/api/stock/moves/', data)
        assert response.status_code == status.HTTP_201_CREATED
    
    def test_superuser_can_consume_fefo(self, superuser_client, test_product, test_location, test_batch, test_stock_move):
        """Superuser can consume stock via FEFO."""
        data = {
            'product': str(test_product.id),
            'location': str(test_location.id),
            'quantity': '5.00',
            'move_type': 'sale_out',
            'reason': 'Admin FEFO consumption'
        }
        response = superuser_client.post('/api/stock/moves/consume-fefo/', data)
        # FEFO requires stock to exist - 400 is acceptable if insufficient stock
        # The key test is permissions (not 403)
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            # Verify it's a business logic error, not permission error
            assert 'error' in response.data or 'detail' not in response.data or 'ClinicalOps' not in str(response.data)
    
    def test_superuser_can_list_on_hand(self, superuser_client):
        """Superuser can list on-hand stock."""
        response = superuser_client.get('/api/stock/on-hand/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_superuser_can_access_by_product(self, superuser_client, test_product):
        """Superuser can access by-product endpoint."""
        response = superuser_client.get(f'/api/stock/on-hand/by-product/{test_product.id}/')
        assert response.status_code == status.HTTP_200_OK


# ============================================================================
# Unauthenticated User Tests
# ============================================================================

@pytest.mark.django_db
class TestUnauthenticatedStockAccess:
    """Test that unauthenticated users cannot access stock endpoints."""
    
    def test_unauthenticated_cannot_list_locations(self):
        """Unauthenticated user gets 401/403."""
        client = APIClient()
        
        response = client.get('/api/stock/locations/')
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
    
    def test_unauthenticated_cannot_list_moves(self):
        """Unauthenticated user gets 401/403."""
        client = APIClient()
        
        response = client.get('/api/stock/moves/')
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
