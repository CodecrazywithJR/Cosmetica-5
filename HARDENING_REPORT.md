# Production Hardening Report - Cosmetica 5 EMR/POS

**Date:** December 16, 2025  
**Auditor:** Senior Engineer  
**Scope:** Django 4.2 + DRF API (apps/api/)  
**Purpose:** Pre-production security, integrity, and quality audit before implementing Sale→Stock integration

---

## Executive Summary

This report documents a comprehensive audit of the Cosmetica 5 Django/DRF application, covering migrations, domain integrity, security, privacy, data consistency, and API quality. The audit identified **1 CRITICAL**, **4 HIGH**, **6 MEDIUM**, and **5 LOW** severity issues.

**Overall Status:** ⚠️ **NOT PRODUCTION READY**  
**Critical Blocker:** Migration dependency error (FIXED during audit)  
**High Priority Fixes:** 4 issues require immediate attention before production deployment

---

## Table of Contents

1. [Migrations Audit](#1-migrations-audit)
2. [Domain Integrity Audit](#2-domain-integrity-audit)
3. [Security & Permissions Audit](#3-security--permissions-audit)
4. [Privacy & Audit Log Audit](#4-privacy--audit-log-audit)
5. [Data Consistency Audit](#5-data-consistency-audit)
6. [API Quality Audit](#6-api-quality-audit)
7. [Implementation Checklist](#7-implementation-checklist)
8. [Testing Instructions](#8-testing-instructions)

---

## 1. Migrations Audit

### 1.1 CRITICAL: AUTH_USER_MODEL Dependency Error ✅ FIXED

**Severity:** CRITICAL  
**Status:** ✅ **FIXED during audit**  
**File:** `apps/api/apps/stock/migrations/0001_layer2_a3_stock_batch_expiry.py`

**Issue:**
```python
# WRONG - String literal instead of settings
migrations.swappable_dependency('AUTH_USER_MODEL')
to='AUTH_USER_MODEL'
```

**Impact:**
- Migration fails to run: `ValueError: Dependency on unknown app: AUTH_USER_MODEL`
- Stock app cannot be initialized
- Database cannot be created from migrations
- **BLOCKS ALL PRODUCTION DEPLOYMENT**

**Root Cause:**
Used string literal `'AUTH_USER_MODEL'` instead of `settings.AUTH_USER_MODEL` in migration file. Django expects swappable dependencies to reference the settings module.

**Fix Applied:**
```python
# CORRECT
from django.conf import settings

dependencies = [
    migrations.swappable_dependency(settings.AUTH_USER_MODEL),
]

# And in field definition:
to=settings.AUTH_USER_MODEL
```

**Verification:**
```bash
python manage.py makemigrations --check --dry-run
# Output: No changes detected ✓
```

**Recommendation:**
- ✅ **COMPLETED:** Fix has been applied
- Add pre-commit hook to check for `'AUTH_USER_MODEL'` string literals in migrations
- All future migrations must use `settings.AUTH_USER_MODEL`

---

### 1.2 HIGH: Migration Dependency Order

**Severity:** HIGH  
**Status:** ⚠️ **NEEDS REVIEW**

**Current Migration Order:**

```
1. authz.0001_initial (creates User model)
2. authz.0002_bootstrap_reception_role (data migration)
3. core.0001_initial (ClinicLocation)
4. clinical.0001_initial (Patient, Encounter, Appointment, etc.)
5. clinical.0002_business_rules_appointment_status_and_patient_required
6. clinical.0003_clinical_audit_log
7. clinical.0004_layer2_a1_clinical_domain_integrity (data migration)
8. clinical.0005_fix_clinicalphoto_index_name
9. documents.0001_initial
10. sales.0001_layer2_a2_sales_integrity
11. stock.0001_layer2_a3_stock_batch_expiry (data migration)
```

**Issues Identified:**

**A. Fragile Cross-App Dependencies:**
- `sales.0001` depends on `patients.Patient` and `clinical.Appointment`
- `stock.0001` depends on `products.Product`
- No explicit dependency declarations between sales/clinical, stock/products

**Potential Failure Scenarios:**
1. If `patients` app migrations run after `sales`, FK constraints fail
2. If `products` app has no migrations, `stock.0001` fails
3. Order is implicit, not enforced

**Recommendation:**
```python
# In sales/migrations/0001_*.py
dependencies = [
    ('sales', []),
    ('patients', '__first__'),  # ADD THIS
    ('clinical', '0001_initial'),  # ADD THIS
    ...
]

# In stock/migrations/0001_*.py  
dependencies = [
    ('products', '__first__'),  # ALREADY PRESENT ✓
    ...
]
```

**Impact:** MEDIUM (migrations work now, but fragile to refactoring)

---

### 1.3 MEDIUM: Data Migration Idempotency

**Severity:** MEDIUM  
**Status:** ⚠️ **NEEDS IMPROVEMENT**

**Migrations with Data Changes:**

1. **`authz/0002_bootstrap_reception_role.py`**
   - Creates Reception role if not exists ✓
   - **Idempotent:** ✓ (uses get_or_create)

2. **`clinical/0004_layer2_a1_clinical_domain_integrity.py`**
   - Function: `clean_inconsistent_encounter_appointments`
   - Sets `encounter.appointment = NULL` where patients don't match
   - **Idempotent:** ⚠️ PARTIAL
   - **Issue:** Re-running migration will audit same changes again (duplicate logs)
   - **Recommendation:** Check if audit log already exists before creating

3. **`sales/0001_layer2_a2_sales_integrity.py`**
   - Function: `clean_invalid_sales`
   - Deletes sales with quantity ≤ 0 or negative prices
   - **Idempotent:** ⚠️ PARTIAL
   - **Issue:** Destructive operation, no reverse migration
   - **Recommendation:** Add reverse migration to restore deleted sales from backup

4. **`stock/0001_layer2_a3_stock_batch_expiry.py`**
   - Function: `migrate_existing_stock_to_batches`
   - Creates UNKNOWN-INITIAL batches for existing stock
   - **Idempotent:** ⚠️ PARTIAL
   - **Issue:** Re-running creates duplicate batches (batch_number not unique across runs)
   - **Recommendation:** Check if batch already exists before creating

**Recommended Pattern for Idempotent Data Migrations:**
```python
def migrate_data(apps, schema_editor):
    Model = apps.get_model('app', 'Model')
    
    # Check if migration already ran
    if Model.objects.filter(metadata__contains={'migration': 'identifier'}).exists():
        print("Migration already applied, skipping...")
        return
    
    # Perform migration
    # ... changes ...
    
    # Mark as completed
    Model.objects.create(metadata={'migration': 'identifier', 'completed_at': timezone.now()})
```

---

### 1.4 LOW: Index Name Length

**Severity:** LOW  
**Status:** ✅ **ALREADY FIXED**

**Issue:**
PostgreSQL has a 63-character limit for index names. Long table/column names can cause truncation and conflicts.

**Analysis:**
Checked all index names in migrations:
- ✅ `idx_patient_name` (16 chars)
- ✅ `idx_appointment_start` (21 chars)
- ✅ `idx_clin_photo_timeline` (23 chars)
- ✅ All index names < 50 characters

**Previous Issue (FIXED):**
- Migration `0005_fix_clinicalphoto_index_name.py` already fixed a long index name
- Original: `idx_clinical_photo_patient_timeline` (35 chars) → ✅ OK
- Changed to: `idx_clin_photo_timeline` (23 chars) → ✅ BETTER

**Recommendation:** No action needed. Continue using concise index names.

---

## 2. Domain Integrity Audit

### 2.1 HIGH: Admin Bypass of Business Rules

**Severity:** HIGH  
**Status:** ⚠️ **VULNERABLE**

**Issue:**
Django Admin allows direct model editing, which bypasses:
- Model `clean()` validation (unless explicitly called)
- Serializer validation
- Custom business logic in views

**Vulnerable Models:**

1. **Appointment:**
   - Rule: Patient required
   - Rule: No overlapping appointments
   - Rule: Status transitions via endpoint only
   - **Admin Bypass:** Admin can set any status directly, create overlapping appointments

2. **Sale:**
   - Rule: Once paid/cancelled, lines are immutable
   - Rule: Total must equal sum of lines
   - **Admin Bypass:** Admin can modify closed sales, break total consistency

3. **StockMove:**
   - Rule: Quantity != 0
   - Rule: IN > 0, OUT < 0
   - Rule: Cannot consume from expired batch
   - **Admin Bypass:** Admin can create invalid moves

**Impact:**
- Data corruption
- Business rule violations
- Audit trail bypassed
- Financial inconsistencies (sales totals incorrect)

**Recommendation:**

**Option 1: Read-Only Admin for Critical Models** (RECOMMENDED)
```python
# apps/api/apps/clinical/admin.py
class AppointmentAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False  # Create via API only
    
    def has_change_permission(self, request, obj=None):
        return False  # Update via API transition endpoint only
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superuser can delete

# apps/api/apps/sales/admin.py
class SaleAdmin(admin.ModelAdmin):
    def has_change_permission(self, request, obj=None):
        if obj and obj.status in ['paid', 'cancelled', 'refunded']:
            return False  # Cannot modify closed sales
        return True
```

**Option 2: Override save_model to Enforce Validation**
```python
class AppointmentAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        # Force full_clean() to run model validations
        obj.full_clean()
        super().save_model(request, obj, form, change)
```

**Option 3: Separate Admin Site for Superusers**
```python
# config/admin.py
from django.contrib.admin import AdminSite

class SuperAdminSite(AdminSite):
    site_header = 'Cosmetica 5 - Superuser Admin'

superadmin_site = SuperAdminSite(name='superadmin')

# Register critical models only on superadmin_site
# Regular admin gets read-only or no access
```

**Priority:** HIGH - Implement Option 1 before production

---

### 2.2 MEDIUM: Encounter-Appointment Coherence Validation Missing in Admin

**Severity:** MEDIUM  
**Status:** ⚠️ **PARTIAL**

**Issue:**
`Encounter.clean()` validates that `encounter.patient == appointment.patient`, but this validation:
- ✅ Runs in API (serializers call `full_clean()`)
- ⚠️ **MAY NOT RUN in Admin** (Django admin doesn't always call `full_clean()`)

**Test Required:**
```python
# Manual test in Django admin:
1. Create encounter with patient A, appointment with patient B
2. Save in admin
3. Check if validation error appears

# If validation doesn't run → HIGH severity
# If validation runs → Close this issue
```

**Recommendation:**
```python
# apps/api/apps/clinical/admin.py
class EncounterAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        obj.full_clean()  # Force validation
        super().save_model(request, obj, form, change)
```

---

### 2.3 MEDIUM: Stock Permissions Too Permissive

**Severity:** MEDIUM  
**Status:** ⚠️ **NEEDS RESTRICTION**

**Issue:**
Stock endpoints use `IsAuthenticated` only, no role-based restrictions:

```python
# apps/api/apps/stock/views.py
class StockLocationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]  # ⚠️ TOO PERMISSIVE
```

**Impact:**
- **Reception** can view/modify stock (should be read-only or no access)
- **Accounting** can modify stock (should be read-only)
- **Marketing** has no business need for stock access

**Expected Permissions:**

| Role | Stock Locations | Stock Batches | Stock Moves | Stock On Hand |
|------|----------------|---------------|-------------|---------------|
| Admin | Full | Full | Full | Full |
| Practitioner | Read | Read | Create (consume for treatments) | Read |
| Reception | No Access | No Access | No Access | No Access |
| Accounting | Read | Read | Read | Read |
| Marketing | No Access | No Access | No Access | No Access |

**Recommendation:**
```python
# Create apps/api/apps/stock/permissions.py
class StockPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        user_roles = set(request.user.user_roles.values_list('role__name', flat=True))
        
        # Marketing and Reception: No access
        if user_roles & {'Marketing', 'Reception'}:
            return False
        
        # Admin: Full access
        if 'Admin' in user_roles:
            return True
        
        # Accounting: Read-only
        if 'Accounting' in user_roles:
            return request.method in permissions.SAFE_METHODS
        
        # Practitioner: Read + Create OUT moves only
        if 'Practitioner' in user_roles:
            if request.method in permissions.SAFE_METHODS:
                return True
            if view.action == 'consume_fefo':  # OUT moves only
                return True
            return False
        
        return False

# Apply to all stock ViewSets
class StockLocationViewSet(viewsets.ModelViewSet):
    permission_classes = [StockPermission]
```

**Priority:** HIGH - Implement before stock goes live

---

### 2.4 LOW: Product.stock_quantity Deprecated but Still Used

**Severity:** LOW  
**Status:** ⚠️ **TECHNICAL DEBT**

**Issue:**
After Layer 2 A3 (stock batch system), `Product.stock_quantity` is deprecated but:
- Still exists in model
- Still updated by some code paths (?)
- Creates confusion about "source of truth"

**Source of Truth:**
- ✅ **NEW:** `StockOnHand` (aggregated by product/location/batch)
- ⚠️ **DEPRECATED:** `Product.stock_quantity` (simple integer, no batch tracking)

**Recommendation:**
1. **Short-term:** Document in `Product` model that `stock_quantity` is deprecated
   ```python
   class Product(models.Model):
       stock_quantity = models.IntegerField(
           _('Stock Quantity (DEPRECATED)'),
           default=0,
           help_text=_('DEPRECATED: Use StockOnHand for batch-tracked stock. This field is legacy.')
       )
   ```

2. **Medium-term:** Add computed property:
   ```python
   @property
   def total_stock(self):
       """Get total stock across all locations/batches from StockOnHand."""
       from apps.stock.models import StockOnHand
       return StockOnHand.objects.filter(product=self).aggregate(
           total=Sum('quantity_on_hand')
       )['total'] or 0
   ```

3. **Long-term:** Create migration to drop `stock_quantity` column (after Sale→Stock integration)

---

## 3. Security & Permissions Audit

### 3.1 HIGH: Public Endpoints Without Rate Limiting

**Severity:** HIGH  
**Status:** ⚠️ **VULNERABLE**

**Publicly Accessible Endpoints (No Authentication):**

```python
# apps/api/apps/website/views.py
permission_classes = []  # ⚠️ COMPLETELY OPEN

# Endpoints:
POST /public/leads/                    # Create marketing lead
GET  /public/website-settings/         # Get clinic settings
GET  /public/cms-pages/{slug}/         # Get CMS pages
POST /public/blog-posts/               # Create blog post (!)
GET  /public/marketing-media-assets/   # List marketing photos
```

**Issues:**

1. **No Rate Limiting:**
   - Vulnerable to spam attacks on `/public/leads/`
   - Can create unlimited leads → database bloat
   - Can scrape all CMS content

2. **Suspicious Endpoint:**
   ```python
   POST /public/blog-posts/  # ⚠️ Why is POST public?
   ```
   - Should require authentication for content creation
   - Likely a security bug

**Recommendation:**

**A. Add Rate Limiting (DRF Throttling):**
```python
# config/settings.py
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',  # Anonymous users
        'user': '1000/hour',  # Authenticated users
        'lead_creation': '10/hour',  # Lead-specific
    }
}

# apps/api/apps/website/views.py
from rest_framework.throttling import AnonRateThrottle

class LeadCreationThrottle(AnonRateThrottle):
    rate = '10/hour'

class PublicLeadViewSet(viewsets.ModelViewSet):
    throttle_classes = [LeadCreationThrottle]
```

**B. Restrict Public Write Operations:**
```python
# POST /public/blog-posts/ should require auth
class BlogPostViewSet(viewsets.ModelViewSet):
    def get_permissions(self):
        if self.action in ['create', 'update', 'destroy']:
            return [IsAuthenticated(), IsAdminUser()]
        return []  # Public read
```

**C. Add CAPTCHA to Lead Form:**
```python
# config/settings.py
INSTALLED_APPS += ['django_recaptcha']

# Use reCAPTCHA v3 for /public/leads/ endpoint
```

**Priority:** HIGH - Add before public launch

---

### 3.2 MEDIUM: Webhook Endpoint Security

**Severity:** MEDIUM  
**Status:** ⚠️ **NEEDS VERIFICATION**

**Webhook Endpoint:**
```python
# apps/api/apps/integrations/views.py
@api_view(['POST'])
@permission_classes([AllowAny])  # ⚠️ COMPLETELY OPEN
def calendly_webhook(request):
    # Handles Calendly appointment webhooks
```

**Issues:**
1. No signature verification (CRITICAL for webhooks)
2. Anyone can POST to this endpoint
3. Could create fake appointments

**Recommendation:**
```python
import hmac
import hashlib
from django.conf import settings

@api_view(['POST'])
@permission_classes([AllowAny])
def calendly_webhook(request):
    # Verify signature
    signature = request.headers.get('X-Calendly-Signature', '')
    payload = request.body
    
    expected_signature = hmac.new(
        settings.CALENDLY_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_signature):
        return Response(
            {'error': 'Invalid signature'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Process webhook
    ...
```

**Verification Required:**
- Check if signature verification is implemented elsewhere
- Check Calendly documentation for signature header name

**Priority:** MEDIUM (if webhook is used) / LOW (if webhook is disabled)

---

### 3.3 MEDIUM: Missing CORS Configuration Details

**Severity:** MEDIUM  
**Status:** ⚠️ **NEEDS REVIEW**

**Current Configuration:**
```python
# config/settings.py
CORS_ALLOWED_ORIGINS = os.environ.get(
    'DJANGO_CORS_ALLOWED_ORIGINS',
    'http://localhost:3000'  # ⚠️ Dev default
).split(',')
```

**Issues:**
1. **Dev default in production:** If env var not set, allows `localhost:3000` → security issue
2. **No wildcard detection:** Could accidentally allow `*`
3. **No CORS headers logged:** Hard to debug in production

**Recommendation:**
```python
# config/settings.py
if DEBUG:
    CORS_ALLOWED_ORIGINS = ['http://localhost:3000', 'http://127.0.0.1:3000']
    CORS_ALLOW_CREDENTIALS = True
else:
    # Production: MUST set DJANGO_CORS_ALLOWED_ORIGINS
    cors_origins = os.environ.get('DJANGO_CORS_ALLOWED_ORIGINS', '')
    if not cors_origins:
        raise ImproperlyConfigured(
            'DJANGO_CORS_ALLOWED_ORIGINS must be set in production'
        )
    
    CORS_ALLOWED_ORIGINS = cors_origins.split(',')
    
    # Validate no wildcards
    if '*' in CORS_ALLOWED_ORIGINS or 'http://*' in str(CORS_ALLOWED_ORIGINS):
        raise ImproperlyConfigured(
            'CORS wildcards not allowed in production'
        )
    
    CORS_ALLOW_CREDENTIALS = True

# Log CORS headers in debug mode
if DEBUG:
    LOGGING['loggers']['corsheaders'] = {
        'handlers': ['console'],
        'level': 'DEBUG',
    }
```

**Priority:** MEDIUM - Review before production

---

### 3.4 LOW: DEBUG=True in Production

**Severity:** LOW (already documented, but critical)  
**Status:** ⚠️ **DOCUMENTED WARNING**

**Current Configuration:**
```python
# config/settings.py
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'  # ⚠️ Defaults to True
```

**Issue:**
- **EXTREMELY DANGEROUS** if `DJANGO_DEBUG` not set in production
- Exposes stack traces with sensitive data (DB credentials, SECRET_KEY, file paths)
- Enables debug toolbar (if installed)

**Recommendation:**
```python
# config/settings.py
DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'  # ✓ Default to False

# Fail loudly if critical settings are default
if not DEBUG and SECRET_KEY == 'dev-secret-key-change-in-production':
    raise ImproperlyConfigured(
        'SECRET_KEY must be changed in production'
    )

if not DEBUG and 'localhost' in ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        'ALLOWED_HOSTS must not include localhost in production'
    )
```

**Priority:** LOW (already known, add fail-safe checks)

---

## 4. Privacy & Audit Log Audit

### 4.1 MEDIUM: Audit Log Stores Full Notes/Complaints

**Severity:** MEDIUM  
**Status:** ⚠️ **PHI EXPOSURE**

**Issue:**
`ClinicalAuditLog.metadata` stores before/after snapshots of encounter changes, including:
- `chief_complaint` (full text)
- `assessment` (full diagnosis)
- `plan` (treatment details)
- `internal_notes` (sensitive clinical notes)

**Example:**
```python
# From audit log function
metadata = {
    'before': {
        'chief_complaint': 'Patient reports severe acne on forehead and cheeks...',  # ⚠️ PHI
        'assessment': 'Diagnosed with cystic acne, possible hormonal imbalance...',  # ⚠️ PHI
        'internal_notes': 'Patient mentioned past trauma, sensitive situation...'   # ⚠️ VERY SENSITIVE
    },
    'after': { ... }
}
```

**Privacy Concerns:**
1. **Retention:** Audit logs stored indefinitely → GDPR/HIPAA issues
2. **Access:** Anyone with DB access can read full PHI
3. **Backup:** Audit logs backed up separately → hard to purge patient data
4. **Purpose:** Do we need full text for audit, or just field names?

**Recommendation:**

**Option 1: Store Field Names Only** (RECOMMENDED)
```python
def log_clinical_audit(...):
    metadata = {
        'changed_fields': ['chief_complaint', 'assessment'],  # ✓ No content
        'change_summary': f"Updated {len(changed_fields)} clinical fields"
    }
```

**Option 2: Anonymize Text Content**
```python
def log_clinical_audit(...):
    metadata = {
        'before': {
            'chief_complaint': f'[{len(before["chief_complaint"])} chars]',  # Length only
            'assessment': f'[{len(before["assessment"])} chars]'
        },
        'changed_fields': ['chief_complaint', 'assessment']
    }
```

**Option 3: Separate PHI Audit from General Audit**
```python
# General audit (current ClinicalAuditLog): Field names only
# PHI audit (new PHIAuditLog): Full content, encrypted at rest, auto-purged after 90 days
```

**Priority:** MEDIUM - Change before HIPAA/GDPR compliance audit

---

### 4.2 LOW: IP Anonymization Insufficient

**Severity:** LOW  
**Status:** ⚠️ **PARTIAL ANONYMIZATION**

**Current Implementation:**
```python
# apps/api/apps/clinical/models.py (log_clinical_audit function)
ip = request.META.get('REMOTE_ADDR', '')
if ip and '.' in ip:
    parts = ip.split('.')
    if len(parts) == 4:
        ip = f"{parts[0]}.{parts[1]}.{parts[2]}.xxx"  # ⚠️ IPv4 only
```

**Issues:**
1. **IPv6 Not Handled:** IPv6 addresses not anonymized (e.g., `2001:0db8:85a3::8a2e:0370:7334`)
2. **Insufficient Anonymization:** Last octet masked, but first 3 octets can still identify location/ISP
3. **GDPR Compliance:** EU requires more aggressive anonymization

**Recommendation:**
```python
import ipaddress

def anonymize_ip(ip_str):
    """
    Anonymize IP address for GDPR compliance.
    IPv4: Keep first 2 octets (e.g., 192.168.x.x)
    IPv6: Keep first 32 bits (e.g., 2001:0db8::)
    """
    if not ip_str:
        return ''
    
    try:
        ip = ipaddress.ip_address(ip_str)
        
        if isinstance(ip, ipaddress.IPv4Address):
            # Keep first 2 octets
            parts = str(ip).split('.')
            return f"{parts[0]}.{parts[1]}.x.x"
        
        elif isinstance(ip, ipaddress.IPv6Address):
            # Keep first 32 bits (4 groups)
            parts = ip.exploded.split(':')
            return ':'.join(parts[:2]) + '::x'
    
    except ValueError:
        return '[invalid]'

# Usage in audit log
metadata['request'] = {
    'ip': anonymize_ip(request.META.get('REMOTE_ADDR', '')),
    'user_agent': request.META.get('HTTP_USER_AGENT', '')[:100]
}
```

**Priority:** LOW (current anonymization is OK for non-EU, improve for GDPR)

---

### 4.3 LOW: Audit Log Retention Policy Missing

**Severity:** LOW  
**Status:** ⚠️ **POLICY NEEDED**

**Issue:**
`ClinicalAuditLog` has no retention policy:
- Logs stored indefinitely
- No automatic purging
- Database grows unbounded

**Recommendation:**

**Policy Options:**
1. **HIPAA Minimum:** 6 years after patient last visit
2. **GDPR Right to Erasure:** Purge when patient requests deletion
3. **Operational:** 2 years for recent audit, 6 years archived

**Implementation** (document only, don't implement yet):
```python
# Future: Add to ops/management/commands/purge_old_audit_logs.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.clinical.models import ClinicalAuditLog

class Command(BaseCommand):
    help = 'Purge audit logs older than retention period'
    
    def handle(self, *args, **options):
        cutoff_date = timezone.now() - timedelta(days=365*6)  # 6 years
        
        deleted_count = ClinicalAuditLog.objects.filter(
            created_at__lt=cutoff_date
        ).delete()[0]
        
        self.stdout.write(f"Purged {deleted_count} old audit logs")

# Run via cron: python manage.py purge_old_audit_logs
```

**Priority:** LOW - Document policy, implement in v2

---

## 5. Data Consistency Audit

### 5.1 HIGH: Patient Model Duplicated

**Severity:** HIGH  
**Status:** ⚠️ **DUPLICATE MODELS**

**Issue:**
Two `Patient` models exist:
1. `apps.clinical.models.Patient` (full EMR patient with 30+ fields)
2. `apps.patients.models.Patient` (legacy stub model?)

**Current State:**
```python
# apps/api/apps/sales/models.py
patient = models.ForeignKey(
    'patients.Patient',  # ⚠️ Uses legacy model
    ...
)

# apps/api/apps/clinical/models.py
class Patient(models.Model):
    # Full implementation with 30+ fields
    ...
```

**Impact:**
- **Data Fragmentation:** Patient data split between two models
- **FK Inconsistency:** Sales point to `patients.Patient`, Encounters to `clinical.Patient`
- **Migration Complexity:** Can't merge patients across models
- **Confusion:** Which model is source of truth?

**Recommendation:**

**Phase 1: Investigate** (IMMEDIATE)
```bash
# Check if apps.patients.Patient has any data
python manage.py shell
>>> from apps.patients.models import Patient as LegacyPatient
>>> LegacyPatient.objects.count()

# Check FK references
>>> from apps.sales.models import Sale
>>> Sale.objects.filter(patient__isnull=False).count()
```

**Phase 2: Consolidate** (if legacy model empty)
```python
# Option A: If apps.patients.Patient is empty → delete app
INSTALLED_APPS.remove('apps.patients')

# Update FK in sales
patient = models.ForeignKey(
    'clinical.Patient',  # ✓ Use canonical model
    ...
)

# Create migration to change FK
python manage.py makemigrations sales --name migrate_patient_fk
```

**Phase 3: Migrate Data** (if legacy model has data)
```python
# Create data migration to copy patients.Patient → clinical.Patient
# Update all FKs to point to new model
# Soft-delete legacy model
```

**Priority:** HIGH - Resolve before Sale→Stock integration

---

### 5.2 MEDIUM: Product.sku Not Unique Across Apps

**Severity:** MEDIUM  
**Status:** ⚠️ **POTENTIAL DUPLICATION**

**Issue:**
`Product.sku` is unique within `products` app, but:
- No validation prevents duplicate SKUs if multiple product tables exist
- Commerce app might create separate product model

**Current State:**
```python
# apps/api/apps/products/models.py
class Product(models.Model):
    sku = models.CharField(max_length=100, unique=True)  # ✓ Unique in this table
```

**Potential Issue:**
```python
# If apps.commerce creates its own Product model:
class Product(models.Model):
    sku = models.CharField(max_length=100, unique=True)  # ⚠️ Duplicate SKU possible
```

**Recommendation:**
1. **Single Product Model:** Use `apps.products.Product` as canonical source
2. **No Commerce Product:** If commerce needs different fields, extend via OneToOne:
   ```python
   class CommerceMeta(models.Model):
       product = models.OneToOneField('products.Product', on_delete=models.CASCADE)
       wholesale_price = models.DecimalField(...)
       supplier_sku = models.CharField(...)
   ```

**Priority:** MEDIUM - Document product model ownership

---

### 5.3 MEDIUM: Sale.patient vs Appointment.patient Coherence

**Severity:** MEDIUM  
**Status:** ⚠️ **NO VALIDATION**

**Issue:**
`Sale` has optional FKs to both `patient` and `appointment`, but no validation ensures:
```python
if sale.appointment and sale.patient:
    assert sale.appointment.patient == sale.patient  # ⚠️ Not enforced
```

**Impact:**
- Can create sale with `patient=A, appointment=B` where `B.patient=C` (C != A)
- Data inconsistency

**Recommendation:**
```python
# apps/api/apps/sales/models.py
class Sale(models.Model):
    def clean(self):
        super().clean()
        
        # If both patient and appointment exist, they must match
        if self.patient and self.appointment:
            if self.appointment.patient_id != self.patient_id:
                raise ValidationError({
                    'appointment': (
                        f'Appointment patient mismatch: '
                        f'sale.patient={self.patient_id} but '
                        f'appointment.patient={self.appointment.patient_id}'
                    )
                })
```

**Priority:** MEDIUM - Add before Sale→Stock integration

---

### 5.4 LOW: SaleLine Missing product FK

**Severity:** LOW  
**Status:** ⚠️ **TECHNICAL DEBT**

**Issue:**
```python
# apps/api/apps/sales/models.py
class SaleLine(models.Model):
    product_name = models.CharField(...)  # ⚠️ String field
    product_code = models.CharField(...)  # ⚠️ String field
    # Missing: product = FK to Product
```

**Impact:**
- Can't link sales to products programmatically
- Can't calculate product revenue
- Can't commit stock automatically (Sale→Stock integration blocked)

**Recommendation:**
```python
class SaleLine(models.Model):
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Product (if product sale, null for service)'
    )
    product_name = models.CharField(...)  # Keep for services
    product_code = models.CharField(..., blank=True)  # Legacy
```

**Priority:** LOW (needed for Sale→Stock integration, but not a bug now)

---

## 6. API Quality Audit

### 6.1 MEDIUM: No API Versioning

**Severity:** MEDIUM  
**Status:** ⚠️ **MISSING**

**Issue:**
API endpoints use `/api/` prefix, but no version:
```python
# Current
GET /api/patients/
GET /api/stock/moves/

# Should be
GET /api/v1/patients/
GET /api/v1/stock/moves/
```

**Impact:**
- Can't introduce breaking changes without breaking existing clients
- Can't deprecate endpoints gracefully
- Mobile apps hard-coded to `/api/` will break if API changes

**Recommendation:**

**Option 1: Add /v1/ to URLs** (RECOMMENDED)
```python
# config/urls.py
urlpatterns = [
    path('api/v1/patients/', include('apps.patients.urls')),
    path('api/v1/encounters/', include('apps.encounters.urls')),
    path('api/v1/stock/', include('apps.stock.urls')),
    path('api/v1/sales/', include('apps.sales.urls')),
    ...
]

# Keep /api/ as alias to /api/v1/ for backward compatibility
urlpatterns += [
    path('api/', include('api.v1.urls')),  # Redirects to v1
]
```

**Option 2: Header-Based Versioning**
```python
# config/settings.py
REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.AcceptHeaderVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1'],
}

# Client sends: Accept: application/json; version=v1
```

**Priority:** MEDIUM - Add before mobile app release

---

### 6.2 LOW: Inconsistent Error Response Format

**Severity:** LOW  
**Status:** ⚠️ **INCONSISTENT**

**Issue:**
Error responses have different formats:

```python
# Format 1: DRF default
{
    "detail": "Not found."
}

# Format 2: Custom validation errors
{
    "patient": ["This field is required."],
    "email": ["Enter a valid email address."]
}

# Format 3: Custom business logic errors
{
    "error": "Invalid transition",
    "current_status": "paid",
    "new_status": "draft"
}

# Format 4: Sale transition errors
{
    "error": {
        "code": "CONFLICT",
        "message": "Patient data modified by another user",
        "details": {...}
    }
}
```

**Impact:**
- Hard to parse errors consistently in frontend
- No standard error codes

**Recommendation:**
```python
# Standardize on RFC 7807 Problem Details
# https://tools.ietf.org/html/rfc7807

{
    "type": "https://api.cosmetica5.com/errors/validation-error",
    "title": "Validation Error",
    "status": 400,
    "detail": "One or more fields are invalid",
    "errors": {
        "patient": ["This field is required"],
        "email": ["Enter a valid email address"]
    },
    "instance": "/api/v1/patients/123"
}

# Implement custom exception handler
def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    
    if response is not None:
        response.data = {
            'type': f'https://api.cosmetica5.com/errors/{exc.__class__.__name__}',
            'title': exc.default_detail,
            'status': response.status_code,
            'detail': str(exc),
            'instance': context['request'].path
        }
    
    return response
```

**Priority:** LOW - Improve in v2, document current formats for now

---

### 6.3 LOW: OpenAPI Schema Not Validated

**Severity:** LOW  
**Status:** ⚠️ **UNKNOWN**

**Issue:**
DRF Spectacular configured for OpenAPI, but:
- Not tested if schema generates without errors
- No validation that all endpoints documented
- No versioning in schema

**Recommendation:**
```bash
# Test schema generation
python manage.py spectacular --file schema.yml --validate

# Check for errors
# If errors found → Fix serializers/views
# If OK → Add to CI/CD pipeline
```

**Priority:** LOW - Test before API documentation release

---

## 7. Implementation Checklist

### Critical Fixes (Before Production)

- [x] **1.1 CRITICAL: AUTH_USER_MODEL Migration** ✅ FIXED
  - File: `apps/api/apps/stock/migrations/0001_layer2_a3_stock_batch_expiry.py`
  - Change: `'AUTH_USER_MODEL'` → `settings.AUTH_USER_MODEL`
  - Verified: `python manage.py makemigrations --check` → No changes detected

### High Priority Fixes (Before Production)

- [ ] **2.1 HIGH: Admin Bypass Protection**
  - Implement read-only admin for Appointment, Sale (closed), StockMove
  - Add `full_clean()` calls in admin `save_model()`
  - Test: Create invalid appointment in admin → should fail

- [ ] **2.3 HIGH: Stock Permissions**
  - Create `apps/stock/permissions.py` with `StockPermission` class
  - Apply to all stock ViewSets
  - Test: Reception user tries to access `/api/stock/moves/` → 403

- [ ] **3.1 HIGH: Rate Limiting on Public Endpoints**
  - Add throttling to `/public/leads/` (10/hour)
  - Require auth for `POST /public/blog-posts/`
  - Test: Create 11 leads in 1 hour → 11th should fail

- [ ] **5.1 HIGH: Resolve Patient Model Duplication**
  - Investigate if `apps.patients.Patient` has data
  - Migrate FKs to `clinical.Patient` or consolidate models
  - Update `Sale.patient` FK

### Medium Priority Fixes (Before v2)

- [ ] **1.2 MEDIUM: Migration Dependencies**
  - Add explicit dependencies in `sales/migrations/0001_*.py`
  - Add explicit dependencies in `stock/migrations/0001_*.py`

- [ ] **1.3 MEDIUM: Data Migration Idempotency**
  - Add idempotency checks to all data migrations
  - Prevent duplicate audit logs on re-run

- [ ] **2.2 MEDIUM: Encounter Admin Validation**
  - Test if admin calls `full_clean()` on Encounter
  - Add explicit validation if needed

- [ ] **3.2 MEDIUM: Webhook Signature Verification**
  - Verify Calendly webhook has signature check
  - Implement if missing

- [ ] **3.3 MEDIUM: CORS Configuration**
  - Add production validation (no wildcards, no localhost)
  - Add logging for CORS headers

- [ ] **4.1 MEDIUM: Audit Log PHI Reduction**
  - Change audit log to store field names only (not full content)
  - Test: Update encounter → audit log has changed_fields, not full text

- [ ] **5.3 MEDIUM: Sale-Appointment Patient Validation**
  - Add `clean()` validation in Sale model
  - Test: Create sale with mismatched patient/appointment → should fail

- [ ] **6.1 MEDIUM: API Versioning**
  - Add `/api/v1/` prefix to all endpoints
  - Keep `/api/` as alias for backward compatibility

### Low Priority Fixes (Future)

- [ ] **2.4 LOW: Product.stock_quantity Deprecation**
  - Document field as deprecated
  - Add `total_stock` computed property

- [ ] **3.4 LOW: DEBUG Default**
  - Change default to `DEBUG = False`
  - Add fail-safe checks for production

- [ ] **4.2 LOW: IP Anonymization**
  - Implement IPv6 anonymization
  - Use more aggressive masking (first 2 octets only)

- [ ] **4.3 LOW: Audit Retention Policy**
  - Document retention policy (6 years)
  - Create purge command (don't run yet)

- [ ] **5.2 LOW: Product SKU Ownership**
  - Document `apps.products.Product` as canonical
  - Prevent commerce from creating duplicate

- [ ] **5.4 LOW: SaleLine product FK**
  - Add FK to Product (needed for Sale→Stock)
  - Make nullable for services

- [ ] **6.2 LOW: Error Format Standardization**
  - Document current formats
  - Plan RFC 7807 adoption in v2

- [ ] **6.3 LOW: OpenAPI Validation**
  - Test schema generation
  - Add to CI/CD

---

## 8. Testing Instructions

### Test Migration Fix

```bash
cd apps/api

# Clean migrations (if in dev)
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
find . -path "*/migrations/*.pyc" -delete

# Recreate migrations
python manage.py makemigrations

# Check no pending migrations
python manage.py makemigrations --check --dry-run
# Expected: "No changes detected"

# Test migrate (requires DB)
python manage.py migrate
# Expected: All migrations apply without errors
```

### Test Admin Bypass Protection

```python
# After implementing 2.1 fix
# Login to admin: http://localhost:8000/admin/

# Test 1: Try to create appointment with overlapping time
# Expected: Validation error

# Test 2: Try to change status of paid sale
# Expected: Form is read-only

# Test 3: Try to create StockMove with quantity=0
# Expected: Validation error
```

### Test Stock Permissions

```bash
# Create test users with different roles
python manage.py shell

from apps.authz.models import User, Role
from apps.clinical.models import UserRole

# Create Reception user
reception_user = User.objects.create_user(email='reception@test.com', password='test123')
reception_role = Role.objects.get(name='Reception')
UserRole.objects.create(user=reception_user, role=reception_role)

# Test API access
curl -X GET http://localhost:8000/api/stock/moves/ \
  -H "Authorization: Bearer <reception_token>"
# Expected: 403 Forbidden
```

### Test Rate Limiting

```bash
# Test lead creation throttle
for i in {1..12}; do
  curl -X POST http://localhost:8000/public/leads/ \
    -H "Content-Type: application/json" \
    -d '{"email":"test'$i'@example.com","name":"Test User"}'
  echo "Request $i"
done

# Expected: First 10 succeed, 11th and 12th return 429 Too Many Requests
```

### Test Patient Model Consolidation

```python
# Before migration
from apps.patients.models import Patient as LegacyPatient
from apps.clinical.models import Patient as ClinicalPatient

legacy_count = LegacyPatient.objects.count()
clinical_count = ClinicalPatient.objects.count()

print(f"Legacy patients: {legacy_count}")
print(f"Clinical patients: {clinical_count}")

# Run consolidation migration
# python manage.py migrate

# After migration
# Verify all FKs point to clinical.Patient
from apps.sales.models import Sale
sale_patient_model = Sale._meta.get_field('patient').related_model
print(f"Sale.patient points to: {sale_patient_model}")
# Expected: <class 'apps.clinical.models.Patient'>
```

---

## 9. Summary

**Total Issues Found:** 16

| Severity | Count | Status |
|----------|-------|--------|
| CRITICAL | 1 | ✅ FIXED |
| HIGH | 4 | ⚠️ OPEN |
| MEDIUM | 6 | ⚠️ OPEN |
| LOW | 5 | ⚠️ OPEN |

**Production Blockers (Must Fix):**
1. ✅ AUTH_USER_MODEL migration (FIXED)
2. ⚠️ Admin bypass protection
3. ⚠️ Stock permissions
4. ⚠️ Public endpoint rate limiting
5. ⚠️ Patient model duplication

**Estimated Fix Time:**
- Critical: ✅ 0 hours (completed)
- High Priority: ~8 hours (admin protection, permissions, rate limiting, patient consolidation)
- Medium Priority: ~12 hours (validation, idempotency, PHI reduction)
- Low Priority: ~6 hours (documentation, minor improvements)

**Total: ~26 hours of engineering work** before production-ready.

---

## Appendix A: Files Modified

```
apps/api/apps/stock/migrations/0001_layer2_a3_stock_batch_expiry.py  [FIXED]
apps/api/apps/clinical/admin.py  [TO FIX]
apps/api/apps/sales/admin.py  [TO FIX]
apps/api/apps/stock/admin.py  [TO FIX]
apps/api/apps/stock/permissions.py  [TO CREATE]
apps/api/apps/stock/views.py  [TO UPDATE]
apps/api/apps/website/views.py  [TO UPDATE]
apps/api/apps/clinical/models.py  [TO UPDATE - audit log]
apps/api/apps/sales/models.py  [TO UPDATE - clean validation]
apps/api/config/settings.py  [TO UPDATE - throttling, CORS]
apps/api/config/urls.py  [TO UPDATE - versioning]
```

---

## Appendix B: Recommended Reading

- Django Security Checklist: https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/
- DRF Permissions: https://www.django-rest-framework.org/api-guide/permissions/
- DRF Throttling: https://www.django-rest-framework.org/api-guide/throttling/
- HIPAA Compliance: https://www.hhs.gov/hipaa/for-professionals/security/index.html
- GDPR Right to Erasure: https://gdpr.eu/right-to-be-forgotten/

---

**End of Report**
