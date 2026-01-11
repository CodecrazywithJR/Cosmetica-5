# Stock Module RBAC Permissions

## Overview

The stock module implements strict Role-Based Access Control (RBAC) to ensure only authorized personnel can access inventory management functionality. This document describes the permission model, protected endpoints, and setup procedures.

## Role Definitions

### Django Groups

Three Django groups control stock module access:

| Group | Description | Stock Access |
|-------|-------------|--------------|
| **Reception** | Front desk staff, patient intake | ❌ NO ACCESS |
| **ClinicalOps** | Clinical operations team | ✅ FULL ACCESS (read + write) |
| **Marketing** | Marketing and outreach staff | ❌ NO ACCESS |
| **Superuser** | System administrators | ✅ FULL ACCESS |

### Permission Matrix

| Role | List | Create | Read | Update | Delete | FEFO Consume | Reports |
|------|------|--------|------|--------|--------|--------------|---------|
| Reception | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Marketing | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| ClinicalOps | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Superuser | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

## Protected Endpoints

All stock endpoints require `IsClinicalOpsOrAdmin` permission:

### Stock Locations
- `GET /api/stock/locations/` - List all locations
- `POST /api/stock/locations/` - Create location
- `GET /api/stock/locations/{id}/` - Retrieve location
- `PUT/PATCH /api/stock/locations/{id}/` - Update location
- `DELETE /api/stock/locations/{id}/` - Delete location

### Stock Batches
- `GET /api/stock/batches/` - List all batches
- `POST /api/stock/batches/` - Create batch
- `GET /api/stock/batches/{id}/` - Retrieve batch
- `PUT/PATCH /api/stock/batches/{id}/` - Update batch
- `DELETE /api/stock/batches/{id}/` - Delete batch
- `GET /api/stock/batches/expiring-soon/` - Get expiring batches (custom action)
- `GET /api/stock/batches/expired/` - Get expired batches (custom action)

### Stock Moves
- `GET /api/stock/moves/` - List all moves
- `POST /api/stock/moves/` - Create move
- `GET /api/stock/moves/{id}/` - Retrieve move
- `PUT/PATCH /api/stock/moves/{id}/` - Update move (Note: moves are typically immutable)
- `DELETE /api/stock/moves/{id}/` - Delete move
- `POST /api/stock/moves/consume-fefo/` - FEFO consumption (custom action)

### Stock On-Hand (Read-Only)
- `GET /api/stock/on-hand/` - List current stock levels
- `GET /api/stock/on-hand/{id}/` - Retrieve specific on-hand record
- `GET /api/stock/on-hand/by-product/{product_id}/` - Stock summary by product (custom action)

## Implementation

### DRF Permission Class

The `IsClinicalOpsOrAdmin` permission class enforces access control:

```python
class IsClinicalOpsOrAdmin(permissions.BasePermission):
    """Allow access only to ClinicalOps group or superusers."""
    
    message = 'Access to stock module requires ClinicalOps role or admin privileges.'
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers have full access
        if request.user.is_superuser:
            return True
        
        # Check ClinicalOps group membership
        return request.user.groups.filter(name='ClinicalOps').exists()
```

### ViewSet Configuration

All stock ViewSets explicitly declare the permission:

```python
class StockLocationViewSet(viewsets.ModelViewSet):
    queryset = StockLocation.objects.all()
    serializer_class = StockLocationSerializer
    permission_classes = [IsClinicalOpsOrAdmin]  # Strict RBAC
```

### Custom Actions

Custom actions (e.g., `consume-fefo`, `expiring-soon`) inherit ViewSet permissions automatically:

```python
@action(detail=False, methods=['post'], url_path='consume-fefo')
def consume_fefo(self, request):
    # Permission check happens before this method is called
    # ClinicalOps or superuser only
    ...
```

## Setup

### 1. Create Django Groups

Run the management command to create groups idempotently:

```bash
python manage.py create_stock_groups
```

Output:
```
✓ Created group: Reception
✓ Created group: ClinicalOps
✓ Created group: Marketing

Summary: 3 created, 0 existing
```

If groups already exist:
```
→ Group already exists: Reception
→ Group already exists: ClinicalOps
→ Group already exists: Marketing

Summary: 0 created, 3 existing
```

### 2. Assign Users to Groups

#### Django Admin UI
1. Navigate to **Admin > Authentication and Authorization > Users**
2. Select user
3. Under **Groups**, add user to appropriate group(s)
4. Save

#### Django Shell
```python
from apps.authz.models import User
from django.contrib.auth.models import Group

# Get user
user = User.objects.get(email='clinician@clinic.com')

# Get ClinicalOps group
clinicalops = Group.objects.get(name='ClinicalOps')

# Add user to group
user.groups.add(clinicalops)

# Verify
print(user.groups.all())  # <QuerySet [<Group: ClinicalOps>]>
```

#### Programmatically (e.g., during user creation)
```python
user = User.objects.create_user(
    email='ops@clinic.com',
    password='secure_password'
)
clinicalops_group = Group.objects.get(name='ClinicalOps')
user.groups.add(clinicalops_group)
```

### 3. Verify Permissions

Use the test suite to verify RBAC:

```bash
# Run all stock permission tests
pytest apps/api/tests/test_stock_permissions.py -v

# Run specific role tests
pytest apps/api/tests/test_stock_permissions.py::TestReceptionStockPermissions -v
pytest apps/api/tests/test_stock_permissions.py::TestClinicalOpsStockPermissions -v
```

Expected results:
- **Reception**: All tests should verify 403 Forbidden
- **Marketing**: All tests should verify 403 Forbidden
- **ClinicalOps**: All tests should verify 200 OK / 201 Created
- **Superuser**: All tests should verify 200 OK / 201 Created

## Security Considerations

### Why Strict RBAC?

1. **Inventory Integrity**: Only trained clinical operations staff should manage stock
2. **Regulatory Compliance**: Audit trails require role segregation
3. **Financial Controls**: Stock movements have direct financial implications
4. **Data Privacy**: Stock records may contain sensitive batch/supplier information

### Defense in Depth

The permission system uses multiple layers:

1. **Authentication**: User must be logged in (`IsAuthenticated` implied by `IsClinicalOpsOrAdmin`)
2. **Group Membership**: User must be in `ClinicalOps` group OR be superuser
3. **ViewSet-Level**: `permission_classes = [IsClinicalOpsOrAdmin]` on ALL stock ViewSets
4. **Action-Level**: Custom actions inherit ViewSet permissions

### No Bypass Routes

- ❌ **DEFAULT_PERMISSION_CLASSES** is NOT relied upon
- ✅ Every ViewSet explicitly declares `permission_classes`
- ✅ Custom actions inherit ViewSet permissions automatically
- ✅ No stock endpoint is accessible without proper permissions

## Testing

### Test Coverage

The test suite (`test_stock_permissions.py`) covers:

1. **Reception User (9 tests)**: Verify 403 on all endpoints
2. **Marketing User (6 tests)**: Verify 403 on all endpoints
3. **ClinicalOps User (11 tests)**: Verify 200/201 on all operations
4. **Superuser (10 tests)**: Verify 200/201 on all operations
5. **Unauthenticated (2 tests)**: Verify 401/403 on endpoints

### Test Fixtures

```python
@pytest.fixture
def clinicalops_user(db):
    """Create user in ClinicalOps group."""
    user = User.objects.create_user(email='ops@test.com', password='test')
    group, _ = Group.objects.get_or_create(name='ClinicalOps')
    user.groups.add(group)
    return user
```

### Example Test

```python
def test_reception_cannot_access_stock_endpoints(reception_user):
    """Reception user gets 403 when listing stock locations."""
    client = APIClient()
    client.force_authenticate(user=reception_user)
    
    response = client.get('/api/stock/locations/')
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert 'ClinicalOps' in response.data.get('detail', '')
```

## Troubleshooting

### User Cannot Access Stock Endpoints

**Symptom**: 403 Forbidden even though user should have access

**Checklist**:
1. ✅ User is authenticated
2. ✅ User is in `ClinicalOps` group: `user.groups.filter(name='ClinicalOps').exists()`
3. ✅ OR user is superuser: `user.is_superuser == True`
4. ✅ Groups exist: `Group.objects.filter(name='ClinicalOps').exists()`
5. ✅ ViewSet has `permission_classes = [IsClinicalOpsOrAdmin]`

**Diagnostic**:
```python
from apps.authz.models import User
user = User.objects.get(email='user@test.com')

print("Authenticated:", user.is_authenticated)
print("Superuser:", user.is_superuser)
print("Groups:", list(user.groups.values_list('name', flat=True)))
print("Has ClinicalOps:", user.groups.filter(name='ClinicalOps').exists())
```

### Permissions Not Working After Group Assignment

**Solution**: Django caches user permissions. Force refresh:

```python
user.refresh_from_db()
# Or in tests:
user = User.objects.get(pk=user.pk)
```

### Custom Action Returns 403

**Cause**: Custom actions inherit ViewSet `permission_classes`

**Solution**: Ensure ViewSet (not action) has correct permission:

```python
# ✅ CORRECT
class StockMoveViewSet(viewsets.ModelViewSet):
    permission_classes = [IsClinicalOpsOrAdmin]
    
    @action(...)
    def consume_fefo(self, request):
        # Inherits IsClinicalOpsOrAdmin
        ...

# ❌ WRONG - action-level permissions don't override ViewSet level
class StockMoveViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]  # Too permissive!
    
    @action(permission_classes=[IsClinicalOpsOrAdmin], ...)
    def consume_fefo(self, request):
        # Only this action is protected, rest of ViewSet is not!
        ...
```

## Migration Notes

### From IsAuthenticated to IsClinicalOpsOrAdmin

If migrating from generic `IsAuthenticated` permissions:

1. **Before Migration**: All authenticated users could access stock
2. **After Migration**: Only ClinicalOps and superusers can access
3. **Impact**: Existing non-ClinicalOps users will get 403

**Migration Checklist**:
1. ✅ Run `create_stock_groups` command
2. ✅ Assign all clinical staff to `ClinicalOps` group
3. ✅ Test with sample users from each group
4. ✅ Run full test suite: `pytest apps/api/tests/test_stock_permissions.py`
5. ✅ Verify in staging environment before production

## References

- **Permission Class**: `apps/stock/permissions.py`
- **ViewSets**: `apps/stock/views.py`
- **Tests**: `apps/api/tests/test_stock_permissions.py`
- **Management Command**: `apps/stock/management/commands/create_stock_groups.py`
- **Django Groups**: https://docs.djangoproject.com/en/4.2/topics/auth/default/#groups
- **DRF Permissions**: https://www.django-rest-framework.org/api-guide/permissions/
