# Admin Bypass Protection

## Overview

This document describes the multi-layer protection mechanisms implemented to prevent Django admin from bypassing business rules on critical models.

**Problem:** Django admin by default does NOT call `full_clean()` when saving objects, allowing invalid data to bypass model validation. Additionally, admin users could edit objects in terminal states (completed appointments, paid sales) or modify immutable audit trails (stock moves).

**Solution:** Multi-layer protection at both model and admin levels.

## Architecture

### Layer 1: Model-Level Validation (save() override)

All critical models override `save()` to enforce `full_clean()` validation:

```python
def save(self, *args, **kwargs):
    """Override save to enforce full_clean() validation."""
    if not kwargs.pop('skip_validation', False):
        self.full_clean()
    super().save(*args, **kwargs)
```

**Key Features:**
- Forces validation before every save
- Catches validation errors before database constraints
- `skip_validation` flag allows migrations/fixtures to bypass
- Applies to both admin and programmatic saves

### Layer 2: Admin-Level Protection

ModelAdmin classes implement multiple protection methods:

```python
class SomeModelAdmin(admin.ModelAdmin):
    
    def get_readonly_fields(self, request, obj=None):
        """Make fields readonly for terminal status objects."""
        if obj and obj.is_terminal_status:
            return [all_critical_fields]
        return readonly_fields
    
    def has_change_permission(self, request, obj=None):
        """Prevent editing immutable objects."""
        if obj and obj.is_immutable:
            return False
        return super().has_change_permission(request, obj)
    
    def has_delete_permission(self, request, obj=None):
        """Restrict deletion of terminal objects."""
        if obj and obj.is_terminal_status:
            return request.user.is_superuser
        return super().has_delete_permission(request, obj)
    
    def save_model(self, request, obj, form, change):
        """Enforce full_clean() validation explicitly."""
        obj.full_clean()
        super().save_model(request, obj, form, change)
```

## Protected Models

### 1. Appointment

**Terminal States:** `completed`, `cancelled`, `no_show`

**Protection Rules:**
- ✅ Can edit draft/scheduled appointments
- ❌ Cannot edit terminal status appointments (all fields readonly except notes)
- ❌ Regular admin cannot delete terminal appointments
- ✅ Superuser can delete (for data cleanup)

**Validation Enforced:**
- Patient required
- Scheduled end must be after start
- No overlapping appointments for same practitioner
- Status transitions follow business rules

**Code:**
```python
# Model
class Appointment(models.Model):
    def save(self, *args, **kwargs):
        if not kwargs.pop('skip_validation', False):
            self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def is_terminal_status(self):
        return self.status in ['completed', 'cancelled', 'no_show']

# Admin
class AppointmentAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_terminal_status:
            return [f.name for f in self.model._meta.fields if f.name != 'notes']
        return self.readonly_fields
```

### 2. Sale

**Terminal States:** `paid`, `cancelled`, `refunded`

**Protection Rules:**
- ✅ Can edit draft/pending sales
- ❌ Cannot edit terminal status sales (financial fields readonly)
- ❌ Cannot add/edit/delete lines when sale is terminal
- ❌ Regular admin cannot delete terminal sales
- ✅ Superuser can delete (for data cleanup)

**Validation Enforced:**
- Patient required
- Totals must be consistent (subtotal + tax = total)
- Currency must be valid
- Sale lines cannot have negative quantities/prices
- Sale lines auto-recalculate parent totals

**Code:**
```python
# Model
class Sale(models.Model):
    def save(self, *args, **kwargs):
        if not kwargs.pop('skip_validation', False):
            self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def is_terminal_status(self):
        return self.status in [SaleStatusChoices.PAID, SaleStatusChoices.CANCELLED, SaleStatusChoices.REFUNDED]

# Admin
class SaleAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj and obj.is_terminal_status:
            readonly.extend(['patient', 'appointment', 'status', 'currency', 'tax', 'discount', 'notes'])
        return readonly
```

### 3. SaleLine

**Protection Rules:**
- ✅ Can add/edit lines for draft/pending sales
- ❌ Cannot add lines to terminal sales (inline blocked)
- ❌ Cannot edit lines of terminal sales
- ❌ Cannot delete lines from terminal sales

**Validation Enforced:**
- Quantity must be positive
- Unit price must be positive
- Line total auto-calculated (quantity × unit_price)
- Parent sale totals auto-recalculated on line save

**Code:**
```python
# Model
class SaleLine(models.Model):
    def save(self, *args, **kwargs):
        if self.quantity and self.unit_price:
            self.calculate_line_total()
        
        if not kwargs.pop('skip_validation', False):
            self.full_clean()
        
        super().save(*args, **kwargs)
        
        # Trigger parent recalculation
        if self.sale_id:
            self.sale.recalculate_totals()
            self.sale.save(skip_validation=True, update_fields=['subtotal', 'total', 'updated_at'])

# Admin (Inline)
class SaleLineInline(admin.TabularInline):
    def has_add_permission(self, request, obj=None):
        if obj and obj.is_terminal_status:
            return False
        return super().has_add_permission(request, obj)
```

### 4. StockMove

**Terminal States:** ALWAYS IMMUTABLE (audit trail)

**Protection Rules:**
- ✅ Can create new stock moves
- ❌ Cannot edit ANY stock move (not even superuser)
- ❌ Cannot update existing stock moves (raises ValidationError)
- ❌ Regular admin cannot delete
- ✅ Superuser can delete (for data cleanup only)

**Validation Enforced:**
- Product, location, batch required
- Quantity must be positive (cannot be zero)
- Move type must be valid
- Immutability enforced at model level (no updates allowed)

**Code:**
```python
# Model
class StockMove(models.Model):
    def save(self, *args, **kwargs):
        if not kwargs.pop('skip_validation', False):
            # Enforce immutability: no updates allowed
            if self.pk is not None:
                raise ValidationError(
                    'StockMove is immutable. Cannot update existing stock moves. '
                    'Create a new adjustment move instead.'
                )
            self.full_clean()
        super().save(*args, **kwargs)

# Admin
class StockMoveAdmin(admin.ModelAdmin):
    def has_change_permission(self, request, obj=None):
        """StockMove is immutable - prevent all edits."""
        return False  # Nobody can edit, not even superuser
```

### 5. Encounter

**Protection Rules:**
- ✅ Can create/edit encounters
- ❌ Cannot save with mismatched patient/appointment

**Validation Enforced:**
- Patient required
- If appointment provided, encounter.patient must match appointment.patient
- Type and status must be valid choices
- Occurred_at required

**Code:**
```python
# Model
class Encounter(models.Model):
    def save(self, *args, **kwargs):
        if not kwargs.pop('skip_validation', False):
            self.full_clean()
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate patient-appointment coherence."""
        if self.appointment and self.patient != self.appointment.patient:
            raise ValidationError({
                'patient': 'Encounter patient must match appointment patient.'
            })

# Admin
class EncounterAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)
```

## Bypass Mechanism

### When to Bypass Validation

**Use `skip_validation=True` ONLY for:**
1. Data migrations (loading fixtures, backfilling data)
2. System-generated saves (audit logs, automatic status transitions)
3. Test fixtures (creating test data in known states)

**NEVER use `skip_validation=True` for:**
- User input (admin or API)
- Business logic operations
- Production code (except migrations)

### How to Bypass

```python
# In migrations
obj.save(skip_validation=True)

# In management commands
obj.save(skip_validation=True)

# In test fixtures
@pytest.fixture
def completed_appointment(patient):
    return Appointment.objects.create(
        patient=patient,
        status='completed',
        # ... other fields ...
        skip_validation=True  # Bypass validation for fixture
    )
```

### Migration Safety

All migrations continue to work because:
1. `skip_validation` flag bypasses `full_clean()` in model save
2. Migration operations use `skip_validation=True`
3. Database constraints still enforce data integrity

Example migration:
```python
from django.db import migrations

def forwards_func(apps, schema_editor):
    Sale = apps.get_model('sales', 'Sale')
    for sale in Sale.objects.filter(status='draft'):
        sale.status = 'pending'
        sale.save(skip_validation=True)  # Skip validation during migration

class Migration(migrations.Migration):
    operations = [
        migrations.RunPython(forwards_func),
    ]
```

## Permission Matrix

| Model | State | Admin Edit | Admin Delete | Superuser Edit | Superuser Delete |
|-------|-------|-----------|--------------|----------------|------------------|
| Appointment (draft) | Modifiable | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| Appointment (completed) | Terminal | ❌ No (readonly) | ❌ No | ❌ No (readonly) | ✅ Yes |
| Sale (draft) | Modifiable | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| Sale (paid) | Terminal | ❌ No (readonly) | ❌ No | ❌ No (readonly) | ✅ Yes |
| SaleLine (draft sale) | Modifiable | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| SaleLine (paid sale) | Terminal | ❌ No | ❌ No | ❌ No | ✅ Yes |
| StockMove | Always Immutable | ❌ No | ❌ No | ❌ No | ✅ Yes (cleanup only) |
| Encounter | Modifiable | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |

**Legend:**
- ✅ Yes: Full permission granted
- ❌ No: Permission denied
- ❌ No (readonly): Can view but all fields readonly

## Testing

### Running Tests

```bash
# Run all admin bypass protection tests
pytest apps/api/tests/test_admin_bypass_protection.py -v

# Run specific test class
pytest apps/api/tests/test_admin_bypass_protection.py::TestAppointmentAdminProtection -v

# Run specific test
pytest apps/api/tests/test_admin_bypass_protection.py::TestStockMoveAdminProtection::test_stock_move_cannot_be_updated -v
```

### Test Coverage

**Appointment Tests (6 tests):**
- ✅ Readonly fields for terminal status
- ✅ Editable fields for draft status
- ✅ Delete restriction for regular admin
- ✅ Delete permission for superuser
- ✅ Validation enforcement on save

**Sale Tests (4 tests):**
- ✅ Readonly fields for terminal status
- ✅ Editable fields for draft status
- ✅ Delete restriction for regular admin
- ✅ Validation enforcement on save

**SaleLine Tests (5 tests):**
- ✅ Cannot edit line of paid sale
- ✅ Cannot delete line of paid sale
- ✅ Can edit line of draft sale
- ✅ Cannot add line to paid sale (inline)
- ✅ Validation prevents negative quantity

**StockMove Tests (5 tests):**
- ✅ Cannot edit in admin
- ✅ Superuser cannot edit (immutable)
- ✅ Superuser can delete
- ✅ Cannot update at model level
- ✅ Validation prevents zero quantity

**Encounter Tests (2 tests):**
- ✅ Patient-appointment coherence validation
- ✅ Admin enforces validation

**Integration Tests (2 tests):**
- ✅ Appointment full lifecycle protection
- ✅ Sale and lines protection together

**Total: 24 test cases**

### Manual Testing

1. **Create terminal object:**
   ```bash
   # Django admin
   # Create appointment, set status to "completed"
   ```

2. **Try to edit:**
   ```bash
   # Click "Change" on completed appointment
   # Verify all fields except "notes" are readonly
   # Try to change status → should be readonly
   ```

3. **Try to delete as regular admin:**
   ```bash
   # Login as non-superuser admin
   # Try to delete completed appointment
   # Should see "Cannot delete" message
   ```

4. **Try to edit StockMove:**
   ```bash
   # Try to click "Change" on any StockMove
   # Should redirect or show message (no edit permission)
   ```

## Known Limitations

### 1. Readonly Fields Still Submitted

Django admin still submits readonly field values in the form, but they are ignored by the admin's save logic. The readonly display is UI-only protection.

**Mitigation:** Model-level `save()` validation catches any attempts to bypass readonly via form manipulation.

### 2. Superuser Can Force Delete

Superusers can delete terminal objects from admin. This is intentional for data cleanup, but should be audited.

**Mitigation:** 
- Use audit log to track superuser deletions
- Implement soft deletes for critical models (future enhancement)

### 3. Direct Database Access Bypasses All Protection

Admin protections don't apply to raw SQL or ORM `.update()` calls.

**Mitigation:**
- Use database CHECK constraints where possible
- Monitor database access logs
- Restrict direct database access to DBA role only

### 4. Inline Forms May Show Edit UI

Even with `has_change_permission=False`, Django may still render inline forms (grayed out). The save will fail, but UX is not ideal.

**Mitigation:** This is a Django admin limitation. Consider custom admin templates for better UX.

## Security Considerations

### Defense in Depth

The multi-layer approach ensures:
1. **Model Level:** Catches bypass via direct ORM calls or admin
2. **Admin Level:** Prevents UI access to edit forms
3. **Database Level:** CHECK constraints as final safety net
4. **Audit Level:** All admin saves logged in audit trail

### Attack Vectors Mitigated

| Attack | Protection |
|--------|-----------|
| Admin form manipulation | Model `save()` calls `full_clean()` |
| Direct ORM `.save()` call | Model `save()` calls `full_clean()` |
| ORM `.update()` bypass | Database CHECK constraints |
| Terminal object edit | Admin readonly fields + permission checks |
| Immutable object update | Model-level immutability check (StockMove) |
| Invalid data submission | `full_clean()` validation |

### Audit Trail

All admin saves trigger Django's built-in LogEntry creation. Monitor for:
- Superuser deletions of terminal objects
- Validation errors in admin (indicates bypass attempt)
- `skip_validation=True` usage outside migrations

## Troubleshooting

### Issue: ValidationError in admin on valid data

**Cause:** Model validation is stricter than form validation.

**Solution:** Update ModelForm to match model validation rules.

### Issue: Cannot save in migration

**Cause:** Migration using `save()` without `skip_validation=True`.

**Solution:**
```python
# In migration
obj.save(skip_validation=True)
```

### Issue: Readonly fields still editable

**Cause:** `get_readonly_fields()` not returning correct fields.

**Solution:** Check `is_terminal_status` property and readonly field list.

### Issue: StockMove edit button still appears

**Cause:** `has_change_permission()` not blocking access.

**Solution:** Verify admin method returns `False` for StockMove.

## Future Enhancements

### 1. Soft Deletes

Replace hard deletes with soft deletes (is_deleted flag) for terminal objects:

```python
class SoftDeleteMixin(models.Model):
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    
    class Meta:
        abstract = True
```

### 2. Field-Level Audit Trail

Track individual field changes for terminal objects:

```python
class FieldAudit(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    field_name = models.CharField(max_length=100)
    old_value = models.TextField()
    new_value = models.TextField()
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
```

### 3. Custom Admin Messages

Show clear messages when readonly due to terminal status:

```python
def get_readonly_fields(self, request, obj=None):
    if obj and obj.is_terminal_status:
        messages.warning(request, f'This {self.model._meta.verbose_name} is in terminal status and cannot be edited.')
        return [all_fields]
    return readonly
```

### 4. Approval Workflow for Terminal Edits

Require manager approval to edit terminal objects:

```python
class TerminalEditRequest(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    requested_changes = models.JSONField()
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='edit_requests', on_delete=models.CASCADE)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='approvals', null=True, on_delete=models.SET_NULL)
    status = models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')])
```

## References

- Django Admin Documentation: https://docs.djangoproject.com/en/4.2/ref/contrib/admin/
- Model Validation: https://docs.djangoproject.com/en/4.2/ref/models/instances/#validating-objects
- Admin Permissions: https://docs.djangoproject.com/en/4.2/ref/contrib/admin/#django.contrib.admin.ModelAdmin.has_change_permission

## Changelog

### 2024-01-XX - Initial Implementation

**Added:**
- Model-level `save()` overrides with `full_clean()` for Appointment, Encounter, Sale, SaleLine, StockMove
- Admin-level protection for all critical models
- Terminal status properties (Appointment, Sale)
- Immutability enforcement (StockMove)
- Inline permission checks (SaleLineInline)
- Comprehensive test suite (24 test cases)

**Fixed:**
- HIGH priority issue from HARDENING_REPORT.md (Issue 2.1: Admin bypass)

**Security:**
- Multi-layer validation enforcement
- Terminal state protection
- Audit trail immutability
