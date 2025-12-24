# Cosmetica 5 - Master Architectural Decisions

> **Purpose**: Master document for all architectural, functional, and product decisions in Cosmetica 5 ERP.  
> This is the **single source of truth** for understanding why the system is built the way it is.  
> **Last Updated**: 2025-12-24  
> **Status**: Living document - updated as project evolves

---

## Table of Contents

### Foundation
1. [Product Vision](#1-product-vision)
2. [Guiding Principles](#2-guiding-principles)
3. [Authentication & Authorization](#3-authentication--authorization)

### Architecture
4. [Backend Architecture](#4-backend-architecture)
5. [Clinical/EMR Decisions](#5-clinicalemr-decisions)
6. [Clinical-Sales Integration](#6-clinical-sales-integration)
7. [Frontend Architecture](#7-frontend-architecture)

### Cross-Cutting Concerns
8. [Internationalization (i18n)](#8-internationalization-i18n)
9. [Currency Strategy](#9-currency-strategy)
10. [Clinical Media Strategy](#10-clinical-media-strategy)
11. [Security and Compliance](#11-security-and-compliance)
12. [Infrastructure & DevOps](#12-infrastructure--devops)

### Scope Management
13. [Out of Scope (Explicit)](#13-out-of-scope-explicit)
14. [How to Use This Document](#14-how-to-use-this-document)

---

## 1. Product Vision

### What is Cosmetica 5?

**Cosmetica 5** is an integrated ERP/EMR/POS system designed for aesthetic medicine clinics in France.

**Core Modules**:
- **Agenda** (Appointment Management)
- **Clinical/EMR** (Encounter records, treatments, medical notes)
- **Proposals/POS** (Financial quotations and sales)
- **Stock** (FEFO inventory management)
- **RBAC** (Role-based access control)

### Who is it for?

**Primary Users**:
1. **Practitioners** (Dermatologists, aesthetic doctors)
   - Record clinical encounters
   - Document treatments
   - Review patient history

2. **Reception Staff**
   - Manage appointments
   - Check-in patients
   - Handle basic coordination

3. **Clinical Operations**
   - Manage proposals and sales
   - Track inventory
   - Generate financial reports

**NOT for**:
- Large hospital chains (built for single-clinic or small groups)
- Purely cosmetic retail (clinical focus, not spa/beauty salon)
- International operations (France-first design)

### What problems does it solve?

1. **Fragmented workflows**: Integrates appointments, clinical records, and sales in one system
2. **Paper-based records**: Digital EMR with audit trail
3. **Manual pricing**: Catalog-based treatment pricing with proposals
4. **Inventory chaos**: FEFO-based stock management for products with expiry dates
5. **Access control**: Role-based permissions protecting clinical data

### What it is NOT

- ❌ **NOT a marketing platform** (no landing pages, no patient-facing booking)
- ❌ **NOT a telemedicine platform** (in-clinic focus)
- ❌ **NOT a full accounting system** (basic sales tracking, not full fiscal compliance)
- ❌ **NOT multi-tenant SaaS** (single legal entity per deployment)
- ❌ **NOT a cosmetic e-commerce** (professional medical device, not consumer product)

### Success Criteria

The system succeeds if:
- ✅ Practitioners can record encounters faster than paper
- ✅ Reception can manage appointments without conflicts
- ✅ Clinical data is immutable and auditable
- ✅ Financial flows are transparent and traceable
- ✅ System is stable enough for daily clinical use

---

## 2. Guiding Principles

These principles guide all architectural and product decisions:

### 2.1 Agenda-First

**Principle**: The first screen after login is the Agenda. No landing pages, no videos, no tours.

**Rationale**:
- Clinics operate on schedules - appointments are the heart of operations
- Users want to see "what's happening today" immediately
- Marketing fluff reduces trust in clinical software
- Practitioners value efficiency over aesthetics

**Implementation**:
- `/` redirects to `/agenda` if authenticated
- No splash screens or welcome modals
- Information-dense UI over whitespace

**Example**:
```typescript
// Root page redirects immediately
if (isAuthenticated) {
  router.push('/agenda');
}
```

### 2.2 Explicit Workflows

**Principle**: No automatic transitions or implicit conversions. Every critical action requires explicit user confirmation.

**Rationale**:
- Clinical and financial actions have legal/regulatory implications
- Automatic workflows hide important business logic
- Explicit confirmations create audit trails
- Users must understand consequences before acting

**Implementation**:
- Encounter → Proposal: Explicit "Generate Proposal" button
- Proposal → Sale: Explicit "Convert to Sale" button
- Finalize Encounter: Modal with 4-part warning
- Refunds: Explicit confirmation with reason

**Anti-pattern**:
```javascript
// ❌ WRONG: Auto-convert proposal to sale
if (proposal.status === 'accepted') {
  autoConvertToSale(proposal);
}

// ✅ CORRECT: Explicit user action
<button onClick={() => showConvertModal(proposal)}>
  {t('pos:actions.convertToSale')}
</button>
```

### 2.3 Clinical and Financial Immutability

**Principle**: Once finalized, clinical encounters and paid sales cannot be modified.

**Rationale**:
- **Legal**: Medical records must be tamper-proof
- **Audit**: Historical integrity for regulatory compliance
- **Trust**: Immutability proves data wasn't backdated or altered
- **Safety**: Prevents accidental data loss

**Implementation**:
- `Encounter.status = 'finalized'` → read-only
- `Sale.status = 'paid'` → no edits, only refunds
- Currency and prices captured as snapshots

**Why not soft deletes?**
- Clinical data should never be "deleted" (hidden yes, erased no)
- Audit trail must show what was visible at what time

### 2.4 Traceability > Convenience

**Principle**: When in doubt, choose the option that leaves better audit trail, even if slightly less convenient.

**Rationale**:
- Medical software is audited by regulators
- Disputes require proof of what happened when
- Convenience can be added later; trust is hard to rebuild

**Examples**:
- ✅ Log all status transitions with timestamps
- ✅ Capture idempotency keys for financial operations
- ✅ Store snapshots instead of foreign keys for critical data
- ❌ Don't use soft deletes that hide data
- ❌ Don't allow direct DB modifications in production

### 2.5 YAGNI (You Aren't Gonna Need It)

**Principle**: Don't build features for hypothetical future needs. Build what's needed now, architect for extensibility.

**Rationale**:
- Premature optimization wastes time
- Unused features become maintenance burden
- Requirements change; future-proofing often guesses wrong
- But: Good architecture allows future additions without rewrites

**Examples**:
- ✅ Single currency (EUR) now, multi-currency architecture prepared
- ✅ No fiscal invoicing now, legal entity structure prepared
- ✅ Local file storage now, S3 migration path clear
- ❌ Don't build multi-tenant when single tenant is needed
- ❌ Don't build payment gateway before confirming payment provider

### 2.6 Stability Over Features

**Principle**: A working, stable system with fewer features beats a buggy system with more features.

**Rationale**:
- Clinical software cannot afford downtime during consultations
- Bugs in financial calculations erode trust
- Stability enables confidence to add more features later

**Implementation**:
- See `docs/STABILITY.md` for stability tracking
- Each module marked as STABLE before adding next module
- Regression testing before new features
- Feature flags for risky changes

---

## 3. Authentication & Authorization

### 📅 Decision Date
**2025-12-24**

### 🎯 Problem Statement

The frontend and backend authentication implementations were misaligned, causing login failures:

**Symptoms**:
1. Login returned 404 (endpoint mismatch: `/auth/login/` called but only `/auth/token/` existed)
2. Frontend expected `{ token, user }`, backend returned `{ access, refresh }` (JWT standard)
3. Token storage inconsistent (`auth_token` vs `access_token` in different files)
4. 401 redirects lost user's locale context (`/login` instead of `/{locale}/login`)
5. No way for frontend to get authenticated user profile and roles

**Root Causes**:
- Backend used standard Django SimpleJWT (industry standard)
- Frontend had custom expectations (non-standard contract)
- No `/me/` endpoint to fetch user profile post-authentication
- Duplicate HTTP client files with different configurations
- Hardcoded redirects without locale awareness

---

### 🧠 Architectural Decisions

#### Decision 1: Keep JWT Standard (No Customization)

**Choice**: Maintain Django REST Framework SimpleJWT without customization.

**Rationale**:
- ✅ **Industry Standard**: SimpleJWT is battle-tested, well-documented
- ✅ **Security**: Regular security updates from Django community
- ✅ **Compatibility**: Works with standard JWT libraries and tools
- ✅ **Extensibility**: Easy to add features (token blacklisting, refresh rotation)
- ✅ **Team Knowledge**: Most Django developers know SimpleJWT

**Alternative Rejected**: Custom `/auth/login/` endpoint returning `{ token, user }`
- ❌ Non-standard contract makes future integrations harder
- ❌ Requires custom serializers and maintenance burden
- ❌ Loses refresh token functionality (less secure)
- ❌ Harder to upgrade Django REST Framework

**Endpoint Contract**:
```http
POST /api/auth/token/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secret"
}

→ Response 200 OK:
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

---

#### Decision 2: Create Explicit `/auth/me/` Endpoint

**Choice**: Add dedicated endpoint for authenticated user profile.

**Rationale**:
- ✅ **Separation of Concerns**: Authentication (JWT) separate from profile data
- ✅ **Frontend Needs**: UI requires user ID, email, and roles to render appropriately
- ✅ **Standard Pattern**: `/me/` is RESTful convention (GitHub, Google APIs use it)
- ✅ **Security**: Requires valid JWT (IsAuthenticated permission)
- ✅ **Flexibility**: Can return different data without changing auth flow

**Alternative Rejected**: Custom JWT claims with user data
- ❌ JWT tokens become large (performance impact)
- ❌ User data in token can't be updated until token expires
- ❌ Security risk: more data in token = more exposure if leaked

**Endpoint Contract**:
```http
GET /api/auth/me/
Authorization: Bearer <access_token>

→ Response 200 OK:
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "doctor@clinic.com",
  "is_active": true,
  "roles": ["admin", "practitioner"]
}
```

**Implementation**:
```python
# apps/api/apps/core/views.py
class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        roles = list(user.user_roles.values_list('role__name', flat=True))
        return Response({
            'id': user.id,
            'email': user.email,
            'is_active': user.is_active,
            'roles': roles,
        })
```

---

#### Decision 3: Automatic Token Refresh in Frontend

**Choice**: Implement refresh token logic in axios interceptor.

**Rationale**:
- ✅ **User Experience**: Seamless, no forced re-login every hour
- ✅ **Security**: Short-lived access tokens (60 min) + long-lived refresh (7 days)
- ✅ **Centralized**: All API calls benefit automatically
- ✅ **Prevents Request Duplication**: Queue requests during refresh

**Flow**:
```
1. API request → 401 Unauthorized
2. Check if refresh_token exists
3. POST /api/auth/token/refresh/ { refresh: "..." }
4. Store new access_token
5. Retry original request with new token
6. If refresh fails → redirect to /{locale}/login
```

**Implementation**:
```typescript
// apps/web/src/lib/api-client.ts
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const refreshToken = localStorage.getItem('refresh_token');
      
      if (refreshToken) {
        const response = await axios.post('/api/auth/token/refresh/', {
          refresh: refreshToken,
        });
        const { access } = response.data;
        localStorage.setItem('access_token', access);
        originalRequest.headers.Authorization = `Bearer ${access}`;
        return apiClient(originalRequest);
      }
    }
    
    // Refresh failed or no refresh token → logout
    const locale = getCurrentLocale();
    window.location.href = `/${locale}/login`;
    return Promise.reject(error);
  }
);
```

---

#### Decision 4: Locale-Aware Authentication Redirects

**Choice**: All auth redirects preserve user's current locale.

**Rationale**:
- ✅ **User Experience**: User in `/es/proposals` should go to `/es/login`, not `/en/login`
- ✅ **Consistency**: Respects user's language preference
- ✅ **i18n Compliance**: Follows next-intl routing architecture

**Implementation**:
```typescript
const getCurrentLocale = (): string => {
  if (typeof window === 'undefined') return 'en';
  const pathSegments = window.location.pathname.split('/').filter(Boolean);
  const validLocales = ['en', 'es', 'fr', 'ru', 'uk', 'hy'];
  return validLocales.includes(pathSegments[0]) ? pathSegments[0] : 'en';
};

// On 401:
const locale = getCurrentLocale();
window.location.href = `/${locale}/login`;

// Post-login:
router.push(`/${locale}`); // Redirect to localized dashboard
```

---

#### Decision 5: Frontend as UX Authority, Backend as Security Authority

**Choice**: Frontend uses roles to show/hide UI, backend enforces all permissions.

**Rationale**:
- ✅ **Security**: Backend never trusts frontend (JWT validates on every request)
- ✅ **User Experience**: Frontend hides unavailable options (cleaner UI)
- ✅ **Performance**: Avoid unnecessary API calls for forbidden actions
- ✅ **Trust Boundary**: Clear separation of concerns

**Example**:
```typescript
// Frontend: Hide "Delete Patient" button for non-admins
const { hasRole } = useAuth();

{hasRole(ROLES.ADMIN) && (
  <button onClick={handleDelete}>Delete</button>
)}

// Backend: Enforce permission regardless
class PatientViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]  # 403 if not admin
    
    def destroy(self, request, pk=None):
        # Even if frontend bypassed, backend blocks
        return super().destroy(request, pk)
```

---

### 🔁 Authentication Flow (Complete)

```
┌─────────────┐
│   Browser   │
│  (Frontend) │
└──────┬──────┘
       │
       │ 1) POST /api/auth/token/
       │    { email, password }
       ↓
┌──────────────────┐
│  Django Backend  │
│   (SimpleJWT)    │
└──────┬───────────┘
       │
       │ 2) ← { access, refresh }
       ↓
┌──────────────────┐
│   localStorage   │
│  access_token    │
│  refresh_token   │
└──────┬───────────┘
       │
       │ 3) GET /api/auth/me/
       │    Authorization: Bearer <access>
       ↓
┌──────────────────┐
│  Django Backend  │
│  (IsAuthenticated)│
└──────┬───────────┘
       │
       │ 4) ← { id, email, is_active, roles[] }
       ↓
┌──────────────────┐
│   localStorage   │
│      user        │
└──────┬───────────┘
       │
       │ 5) Redirect to /{locale}
       ↓
┌─────────────┐
│  Dashboard  │
│  (Agenda)   │
└─────────────┘

// Later, when access_token expires:

┌──────────────────┐
│   API Request    │
│     → 401        │
└──────┬───────────┘
       │
       │ Auto: POST /api/auth/token/refresh/
       │       { refresh: "..." }
       ↓
┌──────────────────┐
│  Django Backend  │
└──────┬───────────┘
       │
       │ ← { access: "new_token" }
       ↓
┌──────────────────┐
│   Update token   │
│  Retry request   │
└──────────────────┘
```

---

### 🗂️ API Contract Reference

#### `/api/auth/token/` - Login (POST)

**Request**:
```json
{
  "email": "doctor@clinic.com",
  "password": "SecurePassword123"
}
```

**Response (200 OK)**:
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Errors**:
- `401 Unauthorized`: Invalid credentials
- `400 Bad Request`: Missing email or password

**Token Lifetime**:
- `access`: 60 minutes
- `refresh`: 7 days

---

#### `/api/auth/token/refresh/` - Refresh Access Token (POST)

**Request**:
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Response (200 OK)**:
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Errors**:
- `401 Unauthorized`: Invalid or expired refresh token

**Note**: With `ROTATE_REFRESH_TOKENS=True`, response also includes new refresh token.

---

#### `/api/auth/token/verify/` - Verify Token (POST)

**Request**:
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Response (200 OK)**:
```json
{}
```

**Errors**:
- `401 Unauthorized`: Invalid or expired token

**Use Case**: Verify token validity without making authenticated request.

---

#### `/api/auth/me/` - Current User Profile (GET)

**Request**:
```http
GET /api/auth/me/
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

**Response (200 OK)**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "doctor@clinic.com",
  "is_active": true,
  "roles": ["admin", "practitioner"]
}
```

**Errors**:
- `401 Unauthorized`: No token or invalid token
- `403 Forbidden`: User is inactive

**Use Case**: Frontend calls this after login to get user profile and roles for UI rendering.

---

### 🧩 Authorization Model (Roles)

**Role Definitions** (from `apps.authz.models.RoleChoices`):

| Role | Lowercase | Permissions |
|------|-----------|-------------|
| Admin | `admin` | Full system access, can manage users and practitioners |
| Practitioner | `practitioner` | Clinical operations, can create/finalize encounters |
| Reception | `reception` | Appointment management, patient check-in |
| Marketing | `marketing` | Proposals, social media content |
| Accounting | `accounting` | Financial reports, sales tracking |

**Frontend Usage**:
```typescript
import { useAuth, ROLES } from '@/lib/auth-context';

const { user, hasRole, hasAnyRole } = useAuth();

// Show admin-only features
{hasRole(ROLES.ADMIN) && <AdminPanel />}

// Show if user has ANY of these roles
{hasAnyRole([ROLES.ADMIN, ROLES.PRACTITIONER]) && (
  <EncounterForm />
)}
```

**Backend Enforcement**:
```python
from apps.authz.permissions import IsAdmin, IsPractitioner

class EncounterViewSet(viewsets.ModelViewSet):
    permission_classes = [IsPractitioner]  # Only practitioners can create
    
    def finalize(self, request, pk=None):
        # Backend always verifies, regardless of frontend
        if not request.user.user_roles.filter(
            role__name='practitioner'
        ).exists():
            return Response(status=403)
```

---

### 🚫 Alternatives Considered & Rejected

#### Alternative 1: Custom `/auth/login/` Endpoint

**Rejected**: See Decision 1

**Why Not**:
- Non-standard API contract
- Harder to maintain and upgrade
- No refresh token support
- Team unfamiliar with custom auth

---

#### Alternative 2: NextAuth.js

**Pros**:
- Enterprise-grade session management
- Built-in CSRF protection
- Multiple auth providers (social login ready)

**Cons**:
- ❌ **Migration Effort**: Entire codebase uses `useAuth()`, requires full refactor
- ❌ **Learning Curve**: Team must learn NextAuth.js configuration
- ❌ **Complexity**: Adds callbacks, adapters, database session storage
- ❌ **Over-Engineering**: Current JWT solution works well for requirements

**Decision**: Keep custom auth, revisit NextAuth.js if social login becomes requirement.

---

#### Alternative 3: Embed User Data in JWT Claims

**Rejected**: See Decision 2

**Why Not**:
- Large tokens (performance hit)
- User data becomes stale until token expires
- Security risk (more data in token = more exposure)

---

#### Alternative 4: Session-Based Auth (Cookies)

**Pros**:
- Simpler (no token management)
- HttpOnly cookies (more secure against XSS)

**Cons**:
- ❌ **CORS Complexity**: Requires `credentials: 'include'` and same-site cookies
- ❌ **Mobile Future**: JWT easier for mobile apps (React Native, etc.)
- ❌ **API Design**: RESTful APIs typically use tokens, not sessions
- ❌ **Scaling**: Session storage requires sticky sessions or shared session store

**Decision**: JWT is more suitable for API-first architecture.

---

### 🧪 Validation Checklist

**Before Deploying**:

#### Backend Tests
- [ ] `POST /api/auth/token/` with valid credentials returns tokens
- [ ] `POST /api/auth/token/` with invalid credentials returns 401
- [ ] `POST /api/auth/token/refresh/` with valid refresh token returns new access token
- [ ] `POST /api/auth/token/refresh/` with invalid refresh token returns 401
- [ ] `GET /api/auth/me/` with valid token returns user profile
- [ ] `GET /api/auth/me/` without token returns 401
- [ ] User roles are correctly returned in `/auth/me/` response

#### Frontend Tests
- [ ] Login form submits to correct endpoint (`/api/auth/token/`)
- [ ] Tokens are stored in `localStorage` (`access_token`, `refresh_token`)
- [ ] User profile is fetched after login (`/api/auth/me/`)
- [ ] Dashboard redirects to `/{locale}` after successful login
- [ ] 401 errors trigger token refresh automatically
- [ ] Refresh failure redirects to `/{locale}/login` (preserves locale)
- [ ] Logout clears all tokens and redirects to login
- [ ] Role-based UI rendering works (`hasRole`, `hasAnyRole`)

#### Locale Tests
- [ ] Login from `/es/login` redirects to `/es` (not `/en`)
- [ ] 401 from `/fr/proposals` redirects to `/fr/login` (not `/login`)
- [ ] Token refresh preserves locale context

#### Security Tests
- [ ] Backend blocks unauthorized requests (403/401) regardless of frontend
- [ ] Frontend cannot bypass permissions by manipulating localStorage
- [ ] Expired tokens are automatically refreshed or logged out
- [ ] CORS allows only configured origins

---

### 📦 Files Changed

**Backend**:
- `apps/api/apps/core/serializers.py` - Added `UserProfileSerializer`
- `apps/api/apps/core/views.py` - Added `CurrentUserView`
- `apps/api/apps/core/urls.py` - Registered `/auth/me/` endpoint

**Frontend**:
- `apps/web/src/lib/api-client.ts` - Unified HTTP client, refresh logic, locale-aware redirects
- `apps/web/src/lib/auth-context.tsx` - Updated login flow (JWT + /me/), role management
- `apps/web/src/lib/api.ts` - ⚠️ **DEPRECATED** (should be removed, use `api-client.ts`)

**Documentation**:
- `docs/PROJECT_DECISIONS.md` - This section (authentication architecture)

---

### 🔍 Troubleshooting

**Login returns 404**:
- ✅ Check `NEXT_PUBLIC_API_BASE_URL` in `.env` or docker-compose.yml
- ✅ Verify frontend calls `/api/auth/token/` (not `/auth/login/`)
- ✅ Check Django logs for routing issues

**"Invalid token" on every request**:
- ✅ Verify `access_token` is stored in localStorage
- ✅ Check token format: `Bearer <token>` in Authorization header
- ✅ Verify backend `SIMPLE_JWT` settings in `config/settings.py`

**Refresh token fails immediately**:
- ✅ Check `refresh_token` exists in localStorage
- ✅ Verify `SIMPLE_JWT['ROTATE_REFRESH_TOKENS'] = True`
- ✅ Check if refresh token is blacklisted (database: `token_blacklist`)

**User profile shows no roles**:
- ✅ Verify user has `UserRole` entries in database
- ✅ Check `apps.authz.models.Role` table has roles seeded
- ✅ Confirm `/auth/me/` query joins `user_roles`

**Locale lost after 401**:
- ✅ Check `getCurrentLocale()` function in `api-client.ts`
- ✅ Verify middleware allows `/{locale}/login` routes

---

### 📚 References

- [Django REST Framework SimpleJWT Documentation](https://django-rest-framework-simplejwt.readthedocs.io/)
- [JWT RFC 7519](https://datatracker.ietf.org/doc/html/rfc7519)
- [Next.js App Router](https://nextjs.org/docs/app)
- [next-intl i18n](https://next-intl-docs.vercel.app/)

---

## 4. Backend Architecture

### 3.1 Layered Architecture

**Decision**: Backend organized in 3 layers: Foundation, Domain, Integrations

**Structure**:
```
Foundation Layer (auth, RBAC, base models)
  ↓
Domain Layer (clinical, stock, sales)
  ↓
Integrations Layer (fiscal, external APIs - future)
```

**Rationale**:
- **Separation of Concerns**: Clinical logic separate from sales logic
- **Testability**: Each layer can be tested independently
- **Maintainability**: Changes in one layer don't cascade
- **Team Scalability**: Different developers can work on different layers

**Layer Definitions**:

#### Foundation Layer
- Authentication (Token-based)
- User model with RBAC
- LegalEntity (base for multi-entity future)
- Base permissions and mixins

#### Domain Layer
- **Clinical**: Patients, Encounters, Treatments, Photos
- **Stock**: Products, StockMoves, FEFO allocation
- **Sales**: Proposals, Sales, Refunds
- **Agenda**: Appointments (bridges clinical + operations)

#### Integrations Layer (Prepared, not yet implemented)
- Fiscal invoicing (Chorus Pro - France)
- Payment gateways
- External pharmacy systems

**Anti-pattern Avoided**:
- ❌ Monolithic `apps/core` with everything mixed
- ❌ Circular dependencies between domain apps

### 3.2 Financial Data with Decimal

**Decision**: All monetary values use `DecimalField`, never `FloatField`

**Rationale**:
- **Precision**: Float arithmetic has rounding errors (e.g., 0.1 + 0.2 ≠ 0.3)
- **Legal**: Financial records must be exact
- **Audit**: Rounding discrepancies trigger audit flags

**Implementation**:
```python
class Sale(models.Model):
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    # ✅ CORRECT: Decimal for money

class SaleLine(models.Model):
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()  # Integers for counts
    # ❌ WRONG: FloatField for money
```

**Why max_digits=10, decimal_places=2?**
- Supports up to €99,999,999.99 per line
- 2 decimals = cent precision (EUR standard)
- If needing more precision (e.g., exchange rates), use max_digits=15, decimal_places=6

### 3.3 Atomicity and Idempotency

**Decision**: Critical operations are atomic (all-or-nothing) and idempotent (safe to retry)

**Atomicity**:
```python
from django.db import transaction

@transaction.atomic
def create_refund(sale_id, lines, reason):
    refund = SaleRefund.objects.create(...)
    for line_data in lines:
        SaleRefundLine.objects.create(...)
    # If ANY operation fails, ALL rollback
```

**Why Atomic?**
- No "ghost" records with `status=FAILED`
- Database integrity maintained
- Failures are clean (nothing persisted)

**Idempotency**:
```python
class SaleRefund(models.Model):
    idempotency_key = models.CharField(max_length=255, null=True, blank=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['sale', 'idempotency_key'],
                condition=Q(idempotency_key__isnull=False),
                name='unique_refund_idempotency_per_sale'
            )
        ]
```

**Why Idempotent?**
- Network retries don't create duplicate refunds
- Client can safely retry without checking first
- Audit trail shows retry attempts vs. duplicates

### 3.4 Observability End-to-End

**Decision**: Structured logging with sanitized PHI/PII

**Implementation**:
```python
import structlog

logger = structlog.get_logger(__name__)

# ✅ CORRECT: Structured, sanitized
logger.info(
    "refund_created",
    refund_id=refund.id,
    sale_id=sale.id,
    amount=str(refund.total_refunded),
    # ❌ NO patient_name, NO email
)

# ❌ WRONG: Exposes PHI
logger.info(f"Refund for patient {patient.full_name}")
```

**Why Sanitize?**
- **GDPR**: Logs must not contain unnecessary PII
- **Security**: Logs are often sent to third parties (e.g., Sentry)
- **Compliance**: Regulators audit log access

**What to Log**:
- ✅ IDs (UUIDs are not PHI)
- ✅ Amounts, statuses, timestamps
- ✅ Error types and codes
- ❌ Patient names, emails, addresses
- ❌ Clinical notes or diagnoses

### 3.5 Refunds: Full and Partial

**Decision**: Support both full refunds (entire sale) and partial refunds (specific lines/quantities)

**Data Model**:
```python
class SaleRefund(models.Model):
    sale = models.ForeignKey(Sale)
    refund_type = models.CharField(choices=[('full', 'Full'), ('partial', 'Partial')])
    total_refunded = models.DecimalField()
    
class SaleRefundLine(models.Model):
    refund = models.ForeignKey(SaleRefund)
    sale_line = models.ForeignKey(SaleLine)
    qty_refunded = models.PositiveIntegerField()  # Can be less than original
```

**Business Rules**:
1. Cannot refund more than sold
2. Multiple partial refunds allowed (up to total sold)
3. Refund captures snapshot of original price (no recalculation)
4. Stock is returned to inventory

**Why Partial Refunds?**
- Real scenario: Customer returns 2 of 5 products
- Allows flexibility without voiding entire sale
- Better audit trail (shows what was kept vs. returned)

**See**: `apps/sales/api/serializers.py` for validation logic

---

## 5. Clinical/EMR Decisions

### 4.1 Encounter as Clinical Core

**Decision**: The `Encounter` model is the central clinical entity, not `Patient`

**Model Structure**:
```python
class Patient(models.Model):
    full_name = models.CharField()
    birth_date = models.DateField()
    # Demographics only - NO clinical data here

class Encounter(models.Model):
    patient = models.ForeignKey(Patient)
    practitioner = models.ForeignKey(User)
    occurred_at = models.DateTimeField()
    status = models.CharField(choices=[('draft', 'Draft'), ('finalized', 'Finalized')])
    chief_complaint = models.TextField()
    assessment = models.TextField()
    plan = models.TextField()
```

**Rationale**:
- **Temporal Integrity**: Clinical state changes over time; encounter captures point-in-time
- **Practitioner Accountability**: Each encounter linked to specific practitioner
- **Legal**: Medical record is the encounter, not the patient
- **Auditability**: Encounter cannot be modified after finalization

**Why not store clinical notes in Patient model?**
- ❌ Patient model would become append-only log (messy)
- ❌ No clear "who wrote what when"
- ❌ Hard to finalize (when does patient record become immutable?)

### 4.2 Patient vs. Encounter Separation

**Decision**: Patient stores demographics; Encounter stores clinical interactions

**Patient Responsibilities**:
- Name, contact information, date of birth
- Consent status (documented, not enforced in v1)
- External IDs (for future integrations)

**Encounter Responsibilities**:
- Chief complaint, assessment, plan (medical notes)
- Treatments performed
- Practitioner and datetime
- Finalization status

**Why Separate?**
- **Single Responsibility**: Patient = identity, Encounter = clinical event
- **Privacy**: Easier to anonymize patient while keeping encounters
- **Access Control**: Different roles need different data
  - Reception: Patient demographics ✅, Clinical notes ❌
  - Practitioner: Both ✅

### 4.3 Treatments as Catalog

**Decision**: Treatments are catalog items, not free-text entries

**Model**:
```python
class Treatment(models.Model):
    name = models.CharField()
    category = models.CharField()
    base_price = models.DecimalField()
    is_active = models.BooleanField()

class EncounterTreatment(models.Model):
    encounter = models.ForeignKey(Encounter)
    treatment = models.ForeignKey(Treatment)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField()  # Snapshot of price at time
```

**Rationale**:
- **Pricing Consistency**: Base price ensures consistency
- **Price Override**: Practitioner can adjust per encounter (discount, promo)
- **Reporting**: Aggregation by treatment type
- **Stock Integration**: Treatments can link to products

**Why not free-text treatment names?**
- ❌ Typos and inconsistencies
- ❌ Impossible to aggregate (is "Botox" same as "BOTOX"?)
- ❌ No pricing reference

### 4.4 Encounter → Proposal → Sale Flow

**Decision**: Explicit progression from clinical encounter to financial sale

**Flow**:
```
Encounter (draft) 
  → Add treatments 
  → Finalize encounter (immutable) 
  → Generate Proposal (creates ClinicalChargeProposal) 
  → Present to patient 
  → Convert Proposal to Sale (if accepted)
```

**Why Explicit Steps?**
1. **Clinical Separation**: Medical record (encounter) separate from commercial offer (proposal)
2. **Optionality**: Not all encounters result in sales (patient may decline)
3. **Negotiation**: Proposal can be adjusted before becoming sale
4. **Audit Trail**: Clear record of what was offered vs. what was purchased

**Anti-pattern**:
- ❌ Auto-create sale when encounter finalized (removes negotiation step)
- ❌ Allow modifying encounter after sale created (breaks immutability)

### 4.5 Immutability After Finalize

**Decision**: Finalized encounters cannot be edited

**Why Immutable?**
- **Legal Compliance**: Medical records must be tamper-proof (French regulations)
- **Audit Trail**: Regulators must see original record, not edited version
- **Data Integrity**: Ensures proposal/sale pricing can't change retroactively
- **Trust**: Patients and practitioners trust records aren't backdated

**Implementation**:
```python
class Encounter(models.Model):
    def add_treatment(self, treatment_id):
        if self.status == 'finalized':
            raise ValidationError("Cannot modify finalized encounter")
```

**Frontend Pattern**:
```typescript
// ❌ WRONG: Browser confirm() - not translatable
if (!confirm('Are you sure?')) return;

// ✅ CORRECT: Proper modal with warnings
<Modal>
  <h2>{t('clinical:modals.finalizeTitle')}</h2>
  <p style={{ color: 'var(--warning)' }}>
    {t('clinical:modals.finalizeWarning')}
  </p>
  <p>{t('clinical:modals.finalizeDescription')}</p>
  <p style={{ color: 'var(--error)' }}>
    {t('clinical:modals.finalizeIrreversible')}
  </p>
</Modal>
```

**Why Modal Instead of Confirm?**
- Browser `confirm()` can't be translated (always browser language)
- Can't style warnings (e.g., red text for irreversibility)
- Can't show multi-line explanations
- Better UX for critical actions

### 4.6 What Data is NOT Translated

**Decision**: Clinical notes, patient names, and practitioner names are never translated

**NOT Translated**:
- ❌ `Encounter.chief_complaint` (written by practitioner in their language)
- ❌ `Encounter.assessment`
- ❌ `Encounter.plan`
- ❌ `Patient.full_name`
- ❌ `User.display_name` (practitioner)
- ❌ `Treatment.name` (from catalog)
- ❌ `EncounterTreatment.notes`

**Rationale**:
- These are **user-generated content**, not UI labels
- Medical notes must remain in language they were written
- Patient names are proper nouns (not translatable)
- Translating clinical notes would corrupt medical record

**What IS Translated**:
- ✅ UI labels ("Chief Complaint", "Assessment", "Plan")
- ✅ Status badges ("Draft", "Finalized")
- ✅ Action buttons ("Finalize Encounter", "Add Treatment")
- ✅ Error messages and confirmations

---

## 6. Clinical-Sales Integration

### 5.1 ClinicalChargeProposal Bridge

**Decision**: Use `ClinicalChargeProposal` as bridge between clinical and sales

**Model**:
```python
class ClinicalChargeProposal(models.Model):
    encounter = models.ForeignKey(Encounter)
    proposal = models.ForeignKey(Proposal)
    created_at = models.DateTimeField()
```

**Why a Bridge Table?**
- **Separation**: Keeps `encounters` and `sales` apps decoupled
- **M2M Future**: Could support one proposal from multiple encounters (rare but possible)
- **Audit**: Tracks relationship creation timestamp
- **Reversibility**: Can delete bridge without touching encounter or proposal

**Alternative Considered**:
- ❌ Direct `Encounter.proposal` foreign key: Couples clinical to sales tightly
- ❌ Proposal.encounter JSON field: Not queryable, no referential integrity

### 5.2 Explicit Generation (Not Automatic)

**Decision**: Generating a proposal from an encounter requires explicit user action

**Implementation**:
```typescript
// Practitioner must click button
<button onClick={handleGenerateProposal}>
  {t('clinical:actions.generateProposal')}
</button>
```

**Why Explicit?**
- **Intent**: Not all encounters result in proposals (follow-ups, consultations without purchase)
- **Control**: Practitioner decides when patient is ready to see pricing
- **Audit**: Clear timestamp of when proposal was generated

**Anti-pattern**:
- ❌ Auto-generate proposal on encounter finalization (removes practitioner control)

### 5.3 Proposal Persists After Conversion

**Decision**: Proposal record remains after being converted to Sale

**Data Model**:
```python
class Proposal(models.Model):
    status = models.CharField(choices=[
        ('draft', 'Draft'),
        ('converted', 'Converted'),  # Not deleted!
        ('cancelled', 'Cancelled')
    ])
    
    # Remains queryable after conversion
    sale = models.ForeignKey(Sale, null=True, blank=True)
```

**Why Keep Proposal?**
- **Audit Trail**: Shows what was originally offered
- **Comparisons**: Can compare proposal price vs. final sale price (discounts, adjustments)
- **Reversibility**: If sale is refunded, can reference original proposal

**Why Not Delete?**
- ❌ Loses historical record
- ❌ Breaks audit trail
- ❌ Makes debugging harder ("why was this price used?")

### 5.4 Controlled Reversibility

**Decision**: Refunds create new records; they don't "undo" sales

**Anti-pattern**:
```python
# ❌ WRONG: Editing original sale
sale.status = 'refunded'
sale.total_amount = 0  # Destroys original amount!
```

**Correct Pattern**:
```python
# ✅ CORRECT: Create refund record
refund = SaleRefund.objects.create(
    sale=sale,
    total_refunded=sale.total_amount,
    reason='Patient requested refund'
)
# Original sale remains unchanged (audit trail preserved)
```

**Why No Undo?**
- **Immutability**: Financial records must show what happened, when
- **Audit**: Refund is separate event with its own timestamp and reason
- **Legal**: Tax authorities require both sale and refund records

### 5.5 Complete Audit Trail

**Decision**: Every clinical-to-sales transition is logged

**Tracked Events**:
1. Encounter finalized → Timestamp, practitioner ID
2. Proposal generated → Timestamp, encounter ID, proposal ID
3. Proposal converted to sale → Timestamp, user ID
4. Sale refunded → Timestamp, reason, refund ID

**Implementation**:
- Django model timestamps (`created_at`, `updated_at`)
- Structured logs for state transitions
- Immutable records (no edits after creation)

**Why Complete Audit?**
- **Compliance**: Regulatory audits require complete history
- **Disputes**: Can prove what happened when
- **Debugging**: Trace errors back to source

---

## 7. Frontend Architecture

### 6.1 React + React Query

**Decision**: React for UI, React Query (TanStack Query v5) for server state

**Why React Query?**
- **Caching**: Automatic cache invalidation and refetching
- **Loading States**: Built-in loading/error handling
- **Mutations**: Optimistic updates and rollback
- **DevTools**: Excellent debugging experience

**Pattern**:
```typescript
// Custom hook wraps React Query
export function useAppointments(filters: AppointmentFilters) {
  return useQuery({
    queryKey: ['appointments', filters],
    queryFn: () => fetchAppointments(filters),
    staleTime: 30000, // 30 seconds
  });
}

// Component uses hook
function AgendaPage() {
  const { data, isLoading, error } = useAppointments({ date: today });
  // React Query handles caching, loading, errors
}
```

**Why Not Redux?**
- ✅ React Query handles server state better
- ✅ Less boilerplate
- ✅ Optimistic updates out-of-the-box
- ❌ Redux still valid for complex client state (not needed yet)

### 6.2 Agenda as First Screen

**Decision**: After login, users land directly on `/agenda`

**Implementation**:
```typescript
// Root page redirects
export default function RootPage() {
  const { isAuthenticated } = useAuth();
  useEffect(() => {
    if (isAuthenticated) {
      router.push('/agenda');
    } else {
      router.push('/login');
    }
  }, [isAuthenticated]);
}
```

**Why Agenda First?**
- **Immediate Value**: Users see today's schedule instantly
- **Clinical Focus**: Appointments drive clinic operations
- **No Friction**: No clicks to reach most-used feature

### 6.3 No Landing Pages or Marketing

**Decision**: No splash screens, welcome videos, or tours

**Why Not?**
- **Trust**: Clinical software should feel professional, not "salesy"
- **Efficiency**: Users are practitioners, not consumers browsing
- **Context**: Users are trained before accessing system (no need for tours)

**What We Show Instead**:
- Empty state messages with clear CTAs
- Inline help text where needed
- Links to documentation (not videos)

### 6.4 Information Density Over Whitespace

**Decision**: UI prioritizes showing data over aesthetics

**Examples**:
- Agenda shows full day at a glance (no time picker)
- Proposal lists show all key fields (no "View Details" clicks)
- Tables preferred over cards for dense data

**Why?**
- **Efficiency**: Practitioners need to scan information quickly
- **Context**: Clinical decisions require seeing full picture
- **Professionalism**: Aligns with medical software expectations

**Balance**:
- Still maintain readability (not cluttered)
- Use typography hierarchy (not just cramming text)
- White space used for grouping, not decoration

### 6.5 Explicit Confirmations for Critical Actions

**Decision**: Destructive or irreversible actions require modal confirmations

**Examples**:
- Finalize encounter → Modal with 4-part warning
- Convert proposal to sale → Modal with terms
- Cancel appointment → Modal with reason field
- Refund sale → Modal with partial/full choice

**Pattern**:
```typescript
const [showModal, setShowModal] = useState(false);

<button onClick={() => setShowModal(true)}>
  {t('actions.finalize')}
</button>

{showModal && (
  <Modal onClose={() => setShowModal(false)}>
    <h2>{t('modal.title')}</h2>
    <p>{t('modal.warning')}</p>
    <p style={{ color: 'var(--error)' }}>
      {t('modal.irreversible')}
    </p>
    <button onClick={handleConfirm}>
      {t('modal.confirm')}
    </button>
  </Modal>
)}
```

**Why Modals?**
- **Prevents Accidents**: User must read warning
- **Translatable**: Can show warnings in user's language
- **Styled**: Can use colors (red) to emphasize danger
- **Audit**: User's click is intentional, not accidental

### 6.6 RBAC in UI

**Decision**: Frontend respects backend RBAC (but doesn't enforce it)

**Implementation**:
```typescript
import { useAuth, ROLES } from '@/lib/auth-context';

function ClinicalPage() {
  const { user } = useAuth();
  
  return (
    <>
      {user.role === ROLES.PRACTITIONER && (
        <button>Finalize Encounter</button>
      )}
      {user.role === ROLES.RECEPTION && (
        <p>You don't have access to clinical records</p>
      )}
    </>
  );
}
```

**Key Point**:
- ✅ UI hides unavailable actions (better UX)
- ✅ Backend enforces permissions (security)
- ❌ UI hiding is NOT security (backend always validates)

**Why Show/Hide?**
- **UX**: Don't show buttons that will fail
- **Guidance**: User knows what they can/can't do
- **Trust**: But backend is ultimate authority

---

## 8. Internationalization (i18n)

### 7.1 Supported Languages

**Decision**: Support 6 languages: English (default), Russian, Ukrainian, Armenian, French, Spanish

**Rationale**:
- **English (en)**: Default language, international standard for development
- **Russian (ru)**: Large user base in aesthetic medicine
- **Ukrainian (uk)**: Significant diaspora in France
- **Armenian (hy)**: Large Armenian community in aesthetic medicine
- **French (fr)**: Legal requirement (operating in France)
- **Spanish (es)**: International expansion potential

**Why English as Default?**
- Development standard (code, docs, comments in English)
- Most accessible to international users and developers
- Facilitates onboarding and open-source collaboration

**Change Log**:
- **2025-12-24**: Changed default from Russian (ru) to English (en) for broader accessibility
- Middleware configured with `defaultLocale: 'en'`

### 7.2 Language ≠ Currency

**Decision**: User's language preference does NOT affect currency

**Principle**:
```typescript
// ✅ CORRECT: Fixed currency, variable formatting
const formatter = new Intl.NumberFormat(userLanguage, {
  style: 'currency',
  currency: 'EUR'  // Always EUR
});

// ❌ WRONG: Deriving currency from language
const currency = languageToCurrency[userLanguage]; // NO!
```

**Examples**:
- Russian user in France → UI in Russian, prices in EUR
- French user → UI in French, prices in EUR
- Spanish user → UI in Spanish, prices in EUR

**Why Separate?**
- **Legal**: Invoices must be in EUR (legal entity currency)
- **Clarity**: User language preference is UI concern, not business data
- **Correctness**: Language doesn't determine where business operates

**See**: [Currency Strategy](#8-currency-strategy) for details

### 7.3 Framework: next-intl (Not react-i18next)

**Decision**: Use `next-intl` for App Router i18n, NOT react-i18next

**Migration Timeline**:
- **2025-12-24**: Complete migration from react-i18next to next-intl
- **Archived**: Legacy react-i18next config moved to `apps/web/_legacy/i18n/`

**Why next-intl?**
- ✅ **App Router Native**: Designed for Next.js 14+ App Router
- ✅ **Server Components**: Supports both server/client components
- ✅ **Type Safety**: Full TypeScript inference for translation keys
- ✅ **Route-based i18n**: URL-based locale detection (`/en/dashboard`, `/fr/dashboard`)
- ✅ **Middleware Integration**: Locale resolution happens at edge

**Why NOT react-i18next?**
- ❌ Client-only solution (no SSR integration)
- ❌ Requires complex setup with App Router
- ❌ No native route internationalization
- ❌ Duplicate i18n systems caused conflicts

**Implementation**:
```typescript
// ✅ CORRECT: next-intl hooks
import { useTranslations } from 'next-intl';

export default function Component() {
  const t = useTranslations('clinical');
  return <button>{t('actions.save')}</button>;
}

// ❌ REMOVED: react-i18next imports
import { useTranslation } from 'react-i18next'; // NO LONGER USED
```

**Configuration**:
- Root config: `apps/web/i18n.ts`
- Middleware: `apps/web/src/middleware.ts`
- Route structure: `apps/web/src/app/[locale]/`

### 7.4 Namespaces by Module

**Decision**: Translations organized by feature namespace, not by language file size

**Structure**:
```
messages/
  en/
    common.json      # Shared UI (nav, actions, status)
    agenda.json      # Appointments module
    clinical.json    # Encounter module
    pos.json         # Proposals/Sales module
  ru/
    common.json
    agenda.json
    clinical.json
    pos.json
```

**Why Namespaces?**
- **Scalability**: Each module manages its own translations
- **Lazy Loading**: Can load only needed namespaces
- **Team Workflow**: Developers work on module without conflicts
- **Clarity**: `useTranslations('clinical')` is self-documenting

**Pattern**:
```typescript
// Load specific namespace
const t = useTranslations('clinical');
t('actions.finalize'); // Uses clinical namespace

// Load multiple namespaces
const t = useTranslations('clinical');
const tCommon = useTranslations('common');
t('actions.finalize');  // clinical namespace
tCommon('actions.save'); // common namespace
```

### 7.5 URL-based Locale Routing

**Decision**: All routes include locale prefix (`/[locale]/`)

**Structure**:
```
apps/web/src/app/
  [locale]/
    page.tsx              → /en, /ru, /fr (dashboard/agenda)
    encounters/
      [id]/page.tsx       → /en/encounters/123
    proposals/
      page.tsx            → /en/proposals
    login/
      page.tsx            → /en/login
```

**Why URL Prefix?**
- ✅ **Shareable URLs**: `/en/encounters/123` is explicit
- ✅ **SEO**: Each locale has separate URL for indexing
- ✅ **Browser History**: Back button preserves locale
- ✅ **Static Generation**: Pre-render all locales at build time

**Middleware Behavior**:
```typescript
// User visits: /dashboard
// Middleware detects locale: en (from Accept-Language or cookie)
// Redirects to: /en/dashboard

// User visits: /fr/dashboard
// Serves: /fr/dashboard directly
```

**COMMIT 2 Changes (2025-12-24)**:
- ✅ Moved `encounters/` under `[locale]/`
- ✅ Moved `proposals/` under `[locale]/`
- ✅ Updated all pages to use `next-intl` hooks
- ✅ Removed duplicate `login/` (was in both root and [locale]/)
- ✅ `agenda/` consolidated into `[locale]/page.tsx` (dashboard)

**Remaining**:
- ⏳ COMMIT 3: Create redirects for legacy routes → locale-aware routes
- ⏳ Update navigation links to use locale-aware paths

### 7.6 Safe Fallbacks

**Decision**: Missing translations fall back to key name, not empty string

**Why?**
- **Debugging**: Missing key shows as `actions.missing` (visible bug)
- **No Silent Failures**: Empty strings hide translation gaps
- **Production Safety**: Partial translation doesn't break UI

**Example**:
```typescript
t('actions.newAction'); // Not translated yet
// Shows: "actions.newAction" (developer sees gap)
// NOT: "" (invisible bug)
```

### 7.7 What NOT to Translate

**Decision**: User-generated content is never translated

**NOT Translated**:
- Clinical notes (written by practitioner)
- Patient names (proper nouns)
- Practitioner names
- Treatment names from catalog
- Custom notes on treatments/sales

**Rationale**:
- **Data Integrity**: Medical records must remain in original language
- **Legal**: Translated notes could be considered altered records
- **Correctness**: Names are not translatable

**What IS Translated**:
- UI labels and buttons
- Status values (draft, finalized, paid)
- Error messages and confirmations
- Empty state messages

**Implementation**:
```typescript
// ✅ CORRECT: Label translated, content not
<div>
  <label>{t('labels.chiefComplaint')}</label>
  <p>{encounter.chief_complaint}</p> {/* Original text */}
</div>

// ❌ WRONG: Translating user content
<p>{t(`complaints.${encounter.chief_complaint}`)}</p>
```

**See**: `docs/FRONTEND_I18N.md` for complete i18n guide

### 7.8 Legacy Route Redirects

**Decision**: Provide redirects for legacy non-localized routes

**Implementation (COMMIT 3 + COMMIT 4 - 2025-12-24)**:
```typescript
// Old routes now redirect to default locale (en)
/                   → /en (middleware auto-detect)
/login              → /en/login
/agenda             → /en (dashboard = agenda)
/encounters/:id     → /en/encounters/:id
/proposals          → /en/proposals
```

**Redirect Strategy**:
- **Middleware**: Handles `/` and auto-detects locale from Accept-Language
- **Page Redirects**: Explicit redirects for known legacy routes
- **Matcher**: `['/((?!api|_next|_vercel|.*\\..*).*)']` covers all non-API routes

**Why Redirects?**
- ✅ **Backward Compatibility**: Old bookmarks/links still work
- ✅ **SEO**: Google redirects update index gradually
- ✅ **UX**: Users aren't surprised by 404s
- ✅ **Migration**: Smooth transition from legacy routes

**Routing Helper**:
```typescript
// apps/web/src/lib/routing.ts
import { routes } from '@/lib/routing';
import { useLocale } from 'next-intl';

const locale = useLocale();
router.push(routes.encounters.detail(locale, '123')); // → /en/encounters/123
```

**Navigation Updated (COMMIT 4)**:
- ✅ `AppLayout` sidebar uses `routes` helper for all links
- ✅ All `href` attributes include locale prefix
- ✅ Language switcher preserves current path
- ✅ Auth redirects (login/logout) detect locale from URL
- ✅ No hardcoded routes remain in active code

### 7.9 Technical Debt Resolution (COMMIT 4)

**Date**: 2025-12-24  
**Status**: ✅ COMPLETED

**Debt Closed**:
1. ✅ **Duplicate i18n.ts**: Removed `src/i18n.ts`, kept root `i18n.ts` as single source of truth
2. ✅ **Route Consolidation**: All UI routes now under `[locale]/` (except API)
3. ✅ **Legacy Redirects**: Fixed `/agenda` → `/en` (not `/en/agenda`, since dashboard IS agenda)
4. ✅ **Default Locale**: Corrected `/login` redirect from `/es/login` to `/en/login`
5. ✅ **Dependencies**: Removed `i18next` and `react-i18next` from package.json
6. ✅ **Hardcoded Routes**: Replaced all with locale-aware routing helper
7. ✅ **Middleware Matcher**: Updated to handle all legacy routes

**Architecture Decisions**:
- **Dashboard = Agenda**: `[locale]/page.tsx` IS the appointments view (no separate `/agenda` subfolder)
- **Single Config**: `apps/web/i18n.ts` (not `src/i18n.ts`) for consistency with next-intl conventions
- **Routing Helper**: Centralized `lib/routing.ts` with type-safe route generation
- **Locale Detection**: Auth context detects locale from pathname for login/logout redirects

**Files Changed**:
```
Deleted:
- apps/web/src/i18n.ts (duplicate)

Modified:
- apps/web/package.json (removed react-i18next deps)
- apps/web/src/middleware.ts (updated matcher)
- apps/web/src/lib/routing.ts (expanded routes)
- apps/web/src/components/layout/app-layout.tsx (routes helper)
- apps/web/src/app/login/page.tsx (redirect to /en)
- apps/web/src/app/agenda/page.tsx (clarified dashboard redirect)
- apps/web/src/app/[locale]/login/page.tsx (locale-aware)
- apps/web/src/app/[locale]/encounters/[id]/page.tsx (locale-aware)
- apps/web/src/lib/auth-context.tsx (locale detection)

Created:
- apps/web/I18N_COMMIT4_VERIFICATION.md
```

**Verification Commands**:
```bash
# Single i18n.ts check
find apps/web -name "i18n.ts" -not -path "*/node_modules/*" -not -path "*/_legacy/*"
# Expected: apps/web/i18n.ts (only one)

# No react-i18next imports
grep -r "from 'react-i18next'" apps/web/src/ --exclude-dir=_legacy
# Expected: No matches

# No hardcoded routes
grep -r "router.push('/[a-z]" apps/web/src/ --exclude-dir=_legacy
# Expected: Minimal matches (only locale detection logic)
```

**Risks & Limitations**:
- ⚠️ **Translation Coverage**: Many keys still only in English (content task, not architecture)
- ⚠️ **Missing Pages**: patients, sales, admin not yet created under `[locale]/` (separate tickets)
- ⚠️ **User Profile Locale**: Not persisted to backend (currently URL-based only)
- ✅ **Mitigated**: All above are intentional scope boundaries, not technical debt

---

## 9. Currency Strategy

### 8.1 Single Currency: EUR

**Decision**: System operates exclusively in EUR (Euro)

**Rationale**:
1. **Legal**: Operating in France, EUR is required for invoices and tax reporting
2. **Simplicity**: No currency conversion complexity
3. **Safety**: Eliminates exchange rate exposure and conversion errors
4. **Focus**: Team focuses on clinical workflows, not forex
5. **YAGNI**: No current international clients requiring other currencies

**Implementation**:
```python
class LegalEntity(models.Model):
    currency = models.CharField(max_length=3, default='EUR')

class Sale(models.Model):
    currency = models.CharField(max_length=3, default='EUR')  # Snapshot
```

**Why NOT Multi-Currency Now?**
- ❌ Adds complexity (conversion rates, rounding, reporting)
- ❌ Legal complexity (different tax rules per currency)
- ❌ Low ROI (no confirmed need)
- ✅ Architecture prepared for future multi-currency

### 8.2 Currency as Snapshot

**Decision**: Currency is stored as snapshot in Proposal/Sale/Refund, not as foreign key to LegalEntity

**Why Snapshot?**
1. **Immutability**: Historical records preserve currency at transaction time
2. **Audit Trail**: Cannot be changed retroactively
3. **Data Independence**: LegalEntity currency changes don't affect past transactions
4. **Future-Proofing**: Enables multi-currency without data migration

**Pattern**:
```python
class Sale(models.Model):
    legal_entity = models.ForeignKey(LegalEntity)
    currency = models.CharField(max_length=3)  # Snapshot, not FK
    
    def save(self, *args, **kwargs):
        if not self.currency:
            self.currency = self.legal_entity.currency  # Capture once
        super().save(*args, **kwargs)
```

**Alternative Rejected**:
```python
# ❌ WRONG: No currency field, always resolve from legal_entity
@property
def currency(self):
    return self.legal_entity.currency
# Problem: If legal_entity changes currency, all past sales change too!
```

### 8.3 Frontend Currency Formatting

**Decision**: Use `Intl.NumberFormat` with fixed EUR, variable locale

**Implementation**:
```typescript
const { i18n } = useTranslation();

const formatter = useMemo(
  () => new Intl.NumberFormat(i18n.language, {
    style: 'currency',
    currency: 'EUR'  // Fixed
  }),
  [i18n.language]
);

formatter.format(1234.56);
// Russian: "1 234,56 €"
// French:  "1 234,56 €"
// Spanish: "1.234,56 €"
```

**Why `Intl` API?**
- ✅ Browser-native (no libraries)
- ✅ Handles locale-specific formatting automatically
- ✅ Respects language preferences (symbol position, separators)
- ✅ Future-proof (browsers keep it updated)

### 8.4 Multi-Currency Future Path

**Decision**: Multi-currency is documented but NOT implemented

**What's Prepared**:
- ✅ Currency field exists in all financial models
- ✅ Snapshot pattern allows different currencies per transaction
- ✅ No hardcoded "EUR" strings in calculations
- ✅ Decimal precision for all money fields

**What Would Be Required**:
1. **Backend**: Exchange rate model, conversion logic, base currency reporting
2. **Legal**: Currency-specific tax rules, EUR conversion for French reporting
3. **Frontend**: Currency selector, mixed-currency warnings
4. **Testing**: Currency mismatch scenarios, refund edge cases

**Estimated Effort**: 4-6 weeks

**Why Not Now?**
- No confirmed international clients
- Regulatory complexity (each currency = new tax rules)
- EUR-only is stable and sufficient

**See**: `docs/PROJECT_DECISIONS.md` - Currency Strategy (section 8) for full analysis

---

## 10. Clinical Media Strategy

### 9.1 Media Associated with Encounter

**Decision**: Clinical photos/videos linked to `Encounter`, not to `Patient`

**Model**:
```python
class SkinPhoto(models.Model):
    encounter = models.ForeignKey(Encounter)  # Not Patient!
    image_file = models.FileField()
    captured_at = models.DateTimeField()
    notes = models.TextField()
```

**Why Encounter, Not Patient?**
- **Temporal Context**: Photo taken during specific consultation
- **Clinical Relevance**: Photo documents state at that encounter
- **Immutability**: Once encounter finalized, photos can't be added/removed
- **Access Control**: Access tied to encounter permissions

**Alternative Rejected**:
```python
# ❌ WRONG: Photos on Patient
class SkinPhoto(models.Model):
    patient = models.ForeignKey(Patient)
# Problems:
# - When was photo taken? (no encounter context)
# - Which practitioner took it? (no attribution)
# - Is it finalized? (no immutability)
```

### 9.2 Local/NAS Storage Strategy (Phase 1)

**Decision**: Initial deployment uses **local filesystem or NAS**, NOT cloud storage

**Storage Options** (in order of preference):
1. **NAS (Network Attached Storage)**: Dedicated storage appliance on clinic LAN
   - ✅ Dedicated backup/RAID built-in
   - ✅ Centralized for multi-server setup
   - ✅ Professional-grade reliability
   - ✅ No internet dependency
   
2. **Local Disk with External Backup**: Server's local disk + rsync to external drive
   - ✅ Simple setup (no NAS hardware needed)
   - ✅ Fast access (no network latency)
   - ⚠️ Requires manual backup discipline
   
3. **Cloud Storage (S3/GCS)**: Deferred to Phase 2
   - ❌ Phase 1: Out of scope
   - ⏳ Phase 2: When multi-location or offsite needs arise

**Implementation**:
```python
# settings.py
MEDIA_ROOT = BASE_DIR / 'media'  # Development
# Production options:
# - Local: '/var/cosmetica5/media/'
# - NAS: '/mnt/nas/cosmetica5/media/'
MEDIA_URL = '/media/'

# In production: Nginx serves files with auth check
```

**Why Local/NAS (Not Cloud)?**
- **Data Sovereignty**: Clinical data stays within clinic's physical control
- **Simplicity**: No cloud provider contracts, credentials, or API complexity
- **Privacy**: Files never leave clinic network (GDPR/HIPAA friendly)
- **Latency**: LAN access (1-10ms) vs internet (50-200ms)
- **Cost**: Zero recurring cloud storage fees
- **Compliance**: Easier to audit (files physically accessible)

**Trade-offs**:
| Aspect | Local/NAS | Cloud (S3) |
|--------|-----------|------------|
| Setup Complexity | ✅ Simple | ❌ Complex (IAM, buckets, CDN) |
| Recurring Cost | ✅ Zero | ❌ Monthly fees |
| Scalability | ⚠️ Limited | ✅ Unlimited |
| Multi-Location | ❌ Difficult | ✅ Easy |
| Backup Strategy | ⚠️ Manual | ✅ Automated |
| Physical Security | ✅ Clinic-controlled | ⚠️ Vendor-controlled |

**Limitations (Accepted for Phase 1)**:
- ⚠️ Backup discipline required (mitigated by automated scripts - see Section 9.6)
- ⚠️ No CDN (acceptable: files accessed only within clinic)
- ⚠️ Not scalable to multiple physical locations (future Phase 2 migration)
- ⚠️ Server disk failure = data loss (mitigated by NAS or daily backups)

**Out of Scope (Phase 1)**:
- ❌ Real-time replication to cloud
- ❌ Multi-region redundancy
- ❌ CDN for file delivery
- ❌ Object versioning (S3-style)
- ❌ Lifecycle policies (auto-archive old files)

### 9.3 No Public URLs

**Decision**: Media files are NEVER publicly accessible

**Implementation**:
- Files served behind authentication
- Nginx checks auth token before serving file
- No direct file paths exposed in API

**Pattern**:
```typescript
// ✅ CORRECT: Token in header
fetch('/api/media/skin-photos/abc123/', {
  headers: { 'Authorization': `Token ${token}` }
});

// ❌ WRONG: Public URL
<img src="https://clinic.com/media/photos/patient123.jpg" />
```

**Why No Public URLs?**
- **GDPR**: Clinical photos are sensitive personal data
- **Consent**: Patient may not consent to sharing
- **Security**: Photos must not leak to search engines

### 9.4 RBAC for Media Access

**Decision**: Photo access follows same RBAC as clinical records

**Rules**:
- ✅ Practitioner who created encounter: Full access
- ✅ Admin: Full access
- ❌ Reception: No access to clinical photos
- ❌ Other practitioners: Depends on clinic policy (configurable)

**Implementation**:
```python
class SkinPhotoViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsClinicalStaff]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return SkinPhoto.objects.all()
        else:
            # Only photos from user's own encounters
            return SkinPhoto.objects.filter(
                encounter__practitioner=user
            )
```

### 9.5 Future: S3/Cloud Migration Path

**Decision**: Architecture allows future migration to S3 without code changes

**How?**
- Using Django's `FileField` (storage backend agnostic)
- Swap `FileSystemStorage` → `S3Boto3Storage`
- Update `MEDIA_URL` to CloudFront CDN
- No changes to model fields or API

**When to Migrate?**
- Multiple clinic locations (need centralized storage)
- Automatic backups required
- Mobile app needs remote access

**Estimated Effort**: 1-2 days (mostly DevOps)

### 9.6 Backup & Migration Strategy

**Decision**: Implement **automated daily backups** that serve dual purpose:
1. **Disaster Recovery**: Restore system after failure
2. **Migration Bundle**: Portable package for moving to new ERP versions

**Objectives**:
- ✅ **RPO (Recovery Point Objective)**: Max 24 hours data loss
- ✅ **RTO (Recovery Time Objective)**: < 4 hours to restore
- ✅ **Portability**: Backup can migrate to new server/version
- ✅ **Integrity**: Cryptographic verification of backup contents
- ✅ **Security**: Encrypted backups protecting PHI/PII

**What Gets Backed Up**:
1. **Database**: Full PostgreSQL dump (or SQLite file)
2. **Media Files**: Complete `MEDIA_ROOT` directory (clinical photos)
3. **Manifest**: Metadata file with checksums, version, git commit
4. **Configuration** (optional): Environment variables template (NO SECRETS)
5. **Dependencies** (optional): `requirements.txt`, `package-lock.json`

**Backup Components**:
```json
// backup_manifest.json (example)
{
  "backup_id": "20251222-143052-a3f9c1b",
  "timestamp": "2025-12-22T14:30:52Z",
  "version": "1.2.3",
  "git_commit": "a3f9c1b4e8d2f7c1a9b3e5d7f2c8a4b6",
  "database": {
    "engine": "postgresql",
    "size_bytes": 524288000,
    "checksum_sha256": "abc123..."
  },
  "media": {
    "file_count": 1523,
    "size_bytes": 2147483648,
    "checksum_sha256": "def456..."
  },
  "migrations": {
    "last_applied": "encounters.0002_clinical_media"
  }
}
```

**Storage Locations** (multi-tiered):
1. **Primary**: Local backup directory (`/backups/daily/`)
2. **Secondary**: External drive or NAS (`/mnt/nas/backups/`)
3. **Tertiary** (optional): Offsite location (manual copy weekly/monthly)

**Encryption**:
- **Tool**: `restic` (preferred) or `borg` backup
- **Algorithm**: AES-256-GCM
- **Password**: Stored in secure location (NOT in repo)
- **Why**: Protects PHI/PII if backup drive stolen

**Retention Policy**:
```
Daily backups:   Keep last 7 days
Weekly backups:  Keep last 4 weeks (every Sunday)
Monthly backups: Keep last 12 months (every 1st day)
```

**Backup Verification**:
- Automated verification after each backup (checksum validation)
- Monthly restore test in staging environment
- Integrity check logs preserved for audit

**Migration Bundle** (special backup type):
- Created before major version upgrades
- Includes: DB snapshot + media + manifest + migration checklist
- Tagged with source version and target version
- Tested in staging before production migration

**Implementation**:
- See: `docs/BACKUP_STRATEGY.md` (detailed procedures)
- See: `scripts/backup/` (operational scripts)

**Out of Scope (Phase 1)**:
- ❌ Real-time replication (e.g., PostgreSQL streaming)
- ❌ High availability / failover
- ❌ Cloud-managed backups (AWS Backup, Azure Backup)
- ❌ Continuous data protection (CDP)
- ❌ Point-in-time recovery (PITR) beyond daily snapshots

**Phase 2 Considerations**:
- Cloud backup destination (S3 Glacier for long-term retention)
- Automated restore testing (weekly scheduled tests)
- Incremental backups (reduce storage footprint)

---

## 11. Security and Compliance

### 10.1 PHI/PII Protection

**Decision**: Minimize exposure of Protected Health Information and Personally Identifiable Information

**What is PHI/PII?**
- Patient names, emails, addresses, phone numbers
- Clinical notes, diagnoses, treatment plans
- Photos of patients

**Protection Measures**:
1. **Access Control**: RBAC enforced at API level
2. **Logging**: PHI/PII excluded from logs
3. **APIs**: Only return fields user has permission for
4. **Frontend**: Don't cache sensitive data in localStorage

**Example**:
```python
# ✅ CORRECT: Sanitized logging
logger.info("encounter_finalized", encounter_id=enc.id)

# ❌ WRONG: PHI in logs
logger.info(f"Encounter for {patient.full_name} finalized")
```

### 10.2 Sanitized Logging

**Decision**: Structured logs with PHI/PII stripped

**Implementation**:
```python
import structlog

logger = structlog.get_logger(__name__)

# ✅ Safe: IDs and amounts
logger.info(
    "refund_created",
    refund_id=refund.id,
    sale_id=sale.id,
    amount=str(refund.total_refunded)
)

# ❌ Unsafe: Patient data
logger.info(
    "refund_created",
    patient_name=patient.full_name,  # NO!
    email=patient.email               # NO!
)
```

**Why Sanitize?**
- **GDPR**: Logs are often sent to third parties (e.g., Sentry, Datadog)
- **Retention**: Logs kept longer than necessary violate GDPR
- **Breaches**: If logging service is hacked, PHI is exposed

### 10.3 Role-Based Data Access

**Decision**: API responses vary by user role

**Example**:
```python
class PatientSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        
        # Hide clinical notes from Reception
        if self.context['request'].user.role == 'Reception':
            data.pop('notes', None)
        
        return data
```

**Why Vary Response?**
- **Principle of Least Privilege**: Users see only what they need
- **Compliance**: Reception doesn't need clinical data for their job
- **Audit**: Reduces risk of accidental exposure

### 10.4 No Unnecessary Exposure

**Decision**: Don't expose data "just in case" it might be useful

**Examples**:
- ❌ Don't return full patient list if only searching for one
- ❌ Don't return all encounters if only current encounter needed
- ❌ Don't return all users if only practitioners needed

**Pattern**:
```python
# ✅ CORRECT: Filtered queryset
def get_queryset(self):
    user = self.request.user
    if user.role == 'Practitioner':
        return Encounter.objects.filter(practitioner=user)
    # Don't return all encounters!

# ❌ WRONG: Return everything, filter in frontend
def get_queryset(self):
    return Encounter.objects.all()  # Exposes other practitioners' data!
```

### 10.5 GDPR by Design

**Decision**: Data minimization and purpose limitation built into system

**Principles**:
1. **Collect Only What's Needed**: No "nice to have" fields
2. **Purpose Limitation**: Data used only for clinical/financial purposes
3. **Retention**: Automatic deletion after legal retention period (future)
4. **Right to Access**: Patients can request their data
5. **Right to Erasure**: Patients can request deletion (with exceptions for legal obligations)

**Implementation Status**:
- ✅ Data minimization: Only necessary fields in models
- ✅ Access control: RBAC prevents unauthorized access
- ⏳ Retention policies: Planned for future (legal requirement: 10 years in France)
- ⏳ Data export: Planned for future (GDPR Article 20)
- ⏳ Deletion workflow: Planned for future (GDPR Article 17)

---

## 12. Infrastructure & DevOps

### 12.1 Container Architecture

**Decision**: Dockerized architecture with docker-compose for dev/staging, Kubernetes for production

**Services**:
- `emr-api` (Django REST Framework + Gunicorn)
- `emr-postgres` (PostgreSQL 15)
- `emr-redis` (Cache + Celery broker)
- `emr-minio` (S3-compatible storage)
- `emr-web` (Next.js frontend)

**Key Principles**:
1. **Non-Root Containers**: Security best practice - all containers run as non-root users
2. **Health Checks**: Mandatory for all services (restart on failure)
3. **Fixed Ports**: Documented in [PORTS.md](PORTS.md)
4. **Volume Mounts**: Dev only - production uses immutable images

### 12.2 Static Files Strategy

**Decision**: Django collectstatic during container startup

**Problem (2025-12-24)**:
- Container crashed on startup: `PermissionError: /app/staticfiles/admin`
- Root cause: Non-root user (`django:django`) couldn't create directory

**Solution**:
1. **Pre-create directories in Dockerfile**:
   ```dockerfile
   RUN useradd -m -u 1000 django && \
       mkdir -p /app/staticfiles /app/media && \
       chown -R django:django /app
   ```

2. **Conditional collectstatic**:
   ```yaml
   # docker-compose.yml
   command: >
     if [ "$DJANGO_COLLECTSTATIC" != "0" ]; then 
       python manage.py collectstatic --noinput; 
     fi
   ```

**Rationale**:
- **DEV**: Volume mounts (`../apps/api:/app`) overwrite image directories
  - First run creates `/app/staticfiles` on host (persisted)
  - Subsequent runs reuse existing directory
- **PROD**: No volume mounts - directories baked into image
  - Static files served via nginx (not Django)
  - Or use external storage (S3/MinIO)

**Escape Hatch**:
```bash
# Skip collectstatic in dev (faster startup)
DJANGO_COLLECTSTATIC=0 make dev
```

**Documentation**: [INFRA_API_STARTUP_FIX.md](../INFRA_API_STARTUP_FIX.md)

### 12.3 Environment Variables

**Decision**: `.env` file for local dev, Kubernetes secrets for production

**Critical Variables**:
- `DJANGO_SECRET_KEY` (50+ chars, cryptographically random)
- `DJANGO_DEBUG` (False in production)
- `DJANGO_ALLOWED_HOSTS` (comma-separated, never use `*` in prod)
- `DATABASE_PASSWORD` (strong password, rotated quarterly)
- `JWT_SIGNING_KEY` (HS256, 256+ bits)

**Never Commit**:
- ❌ `.env` files with real secrets
- ❌ `config.py` with hardcoded credentials
- ✅ Use `.env.example` as template (placeholder values only)

### 12.4 Deployment Strategy

**DEV**:
- `make dev` → docker-compose up
- Volume mounts for hot reload
- DEBUG=True, verbose logging

**STAGING**:
- GitHub Actions → Build images → Push to registry
- Deploy to Kubernetes (staging namespace)
- DEBUG=False, production-like setup

**PROD**:
- Manual approval gate (GitHub Actions)
- Blue-green deployment (zero downtime)
- Health checks + rollback automation

**Rollback**:
- Keep last 3 image tags
- `kubectl rollout undo deployment/emr-api`
- Database migrations: Forward-compatible only (never breaking changes)

---

## 13. Out of Scope (Explicit)

These features are **intentionally not implemented** in v1.0:

### 13.1 Multi-Currency Operations

**Status**: ❌ Not Implemented  
**Future**: Documented and architected, but not active

**Why Not Now?**
- No international clients
- Legal complexity (tax rules per currency)
- EUR-only sufficient for France operations

**See**: [Currency Strategy](#9-currency-strategy)

### 13.2 Full Fiscal Invoicing

**Status**: ❌ Not Implemented  
**Future**: Phase 2 (estimated 3-4 weeks)

**What's Missing**:
- Legal invoice numbers (sequential, gap-free)
- TVA (VAT) calculations and breakdown
- French legal invoice template
- Chorus Pro integration (B2G invoicing)

**Why Not Now?**
- Requires accountant input on exemptions
- Legal template needs approval
- Current sales tracking sufficient for Phase 1

**See**: `BUSINESS_RULES_IMPLEMENTATION.md` - Legal Entity section

### 13.3 External Integrations

**Status**: ❌ Not Implemented  
**Future**: As needed per client

**Examples**:
- Payment gateways (Stripe, PayPal)
- Pharmacy systems (drug ordering)
- Lab integrations (test results)
- Chorus Pro (French B2G invoicing)

**Why Not Now?**
- No confirmed integration requirements
- Each integration = maintenance burden
- Internal workflows sufficient for Phase 1

### 13.4 Clinical Automations

**Status**: ❌ Not Implemented  
**Rationale**: Explicit over implicit

**Examples of What We DON'T Auto-Do**:
- ❌ Auto-finalize encounters (practitioner must explicitly finalize)
- ❌ Auto-generate proposals (practitioner decides when)
- ❌ Auto-convert proposals to sales (patient acceptance required)
- ❌ Auto-send appointment reminders (not a marketing platform)

**Why No Automation?**
- Clinical decisions require human judgment
- Explicit workflows create audit trails
- Automation hides business logic
- Reduces errors from unexpected behavior

### 13.5 Patient-Facing Portal

**Status**: ❌ Not Implemented  
**Future**: Depends on clinic demand

**What's Missing**:
- Patient login/accounts
- Online appointment booking
- View medical history
- Pay invoices online

**Why Not Now?**
- Clinics prefer phone/reception booking (personal touch)
- Security complexity (patient authentication)
- GDPR requirements (consent management)
- Reception is sufficient for Phase 1

### 13.6 Multi-Tenant SaaS

**Status**: ❌ Not Implemented  
**Design**: Single legal entity per deployment

**Why Not Multi-Tenant?**
- Simpler architecture
- Better data isolation
- Easier compliance (each clinic = separate DB)
- No risk of data leakage between clinics

**If Multi-Tenant Needed?**
- Would require complete redesign
- Estimated effort: 8-12 weeks
- Not planned for near future

### 13.7 Known Technical Debt

#### 13.7.1 Duplicate i18n Configuration (Frontend)

**Status**: ⚠️ Technical Debt  
**Created**: 2025-12-23  
**Context**: next-intl requirement vs existing architecture

**Issue**:
- next-intl **requires** an `i18n.ts` file at the root of the Next.js app (`apps/web/i18n.ts`)
- Prior to this, configuration existed at `apps/web/src/i18n.ts`
- Both files now coexist with identical logic but different relative paths

**Current State**:
```
apps/web/
├── i18n.ts              # NEW: Required by next-intl (loads ./messages/${locale}.json)
├── src/
│   └── i18n.ts          # EXISTING: Legacy location (loads ../messages/${locale}.json)
└── messages/
    ├── es.json
    ├── fr.json
    ├── en.json
    ├── ru.json
    ├── uk.json
    └── hy.json
```

**Why This Happened**:
- next-intl documentation explicitly requires `i18n.ts` at root for App Router
- Error: "Couldn't find next-intl config file" blocked frontend startup
- Temporary duplication created to unblock development

**Resolution Plan**:
1. ✅ Create `apps/web/i18n.ts` (root) → **DONE** (2025-12-23)
2. ⏳ Audit: Verify no code references `src/i18n.ts` directly
3. ⏳ Remove: Delete `apps/web/src/i18n.ts` once confirmed unused
4. ⏳ Test: Verify all locales load correctly (es, fr, en, ru, uk, hy)

**Risk**: Low  
- Both files have identical logic
- Only difference is relative path to `messages/` folder
- No breaking changes expected on cleanup

**Estimated Cleanup Effort**: 30 minutes (audit + delete + verify)

#### 11.5.2 Global Providers Wiring in App Router (Frontend)

**Status**: ✅ Resolved  
**Created**: 2025-12-23  
**Context**: Next.js 14 App Router client/server component boundaries

**Issue**:
- Error: "useAuth must be used within an AuthProvider" when accessing pages
- App Router layouts are Server Components by default
- Global providers (AuthProvider, QueryClientProvider) must be Client Components
- Mixed i18n setup: react-i18next imported but app uses next-intl

**Root Cause**:
- `apps/web/src/lib/providers.tsx` existed but had conflicting configuration:
  - Imported `I18nextProvider` from react-i18next (wrong i18n library)
  - Attempted to import `@/i18n` which is next-intl config, not i18next instance
  - Had `i18nReady` state check that returned `null` initially
  - This caused AuthProvider to not render, triggering "must be used within" error

**Solution**:
1. ✅ Simplified `apps/web/src/lib/providers.tsx` → **DONE** (2025-12-23)
   - Removed `I18nextProvider` (i18n handled by next-intl at layout level)
   - Removed `i18nReady` state check (no longer needed)
   - Kept only: `QueryClientProvider` → `AuthProvider` → children

2. ✅ Provider hierarchy in `apps/web/src/app/[locale]/layout.tsx`:
   ```tsx
   <Providers>                         // Client Component wrapper
     <NextIntlClientProvider>          // i18n from next-intl
       {children}                      // App content
     </NextIntlClientProvider>
   </Providers>
   ```

3. ✅ Internal structure of `Providers.tsx`:
   ```tsx
   <QueryClientProvider>               // React Query
     <AuthProvider>                    // Auth context
       {children}
     </AuthProvider>
   </QueryClientProvider>
   ```

**Why This Architecture**:
- **Server Component Layout**: Can use `getMessages()` from next-intl/server
- **Client Component Providers**: React context (Auth, Query) requires client-side
- **Separation of Concerns**: i18n (next-intl) vs state (React Query) vs auth (context)
- **Next.js 14 Pattern**: Recommended approach for App Router global providers

**Provider Order Matters**:
1. `Providers` (outer Client Component boundary)
2. `NextIntlClientProvider` (i18n messages)
3. `QueryClientProvider` (API cache)
4. `AuthProvider` (user session)
5. App content (children)

**Future Review**:
- ⏳ Consider adding React Query DevTools in development
- ⏳ Add theme provider if dark mode implemented
- ⏳ Consider moving Providers.tsx to `src/components/providers/` for better organization

**Risk**: None  
- Standard Next.js 14 pattern
- No breaking changes to auth or query logic
- i18n fully handled by next-intl

**References**:
- [Next.js App Router: Client Components](https://nextjs.org/docs/app/building-your-application/rendering/client-components)
- [React Query with Next.js 14](https://tanstack.com/query/latest/docs/framework/react/guides/ssr#using-the-app-directory-in-nextjs-13)
- [next-intl with App Router](https://next-intl-docs.vercel.app/docs/getting-started/app-router)

#### 11.5.3 Login Route Outside [locale] Segment (Frontend)

**Status**: ✅ Resolved  
**Created**: 2025-12-23  
**Context**: App Router route tree and provider hierarchy

**Issue**:
- Error: "useAuth must be used within an AuthProvider" when accessing `/login`
- Login page was at `app/login/page.tsx` (outside `[locale]` segment)
- AuthProvider mounted in `app/[locale]/layout.tsx` only
- Routes outside `[locale]/` don't receive the Providers wrapper

**Root Cause**:
```
app/
├── login/                    # ❌ Outside [locale], no AuthProvider
│   ├── layout.tsx           # ❌ Created duplicate <html> tag
│   └── page.tsx             # ❌ Uses useAuth() but no provider
└── [locale]/                 # ✅ Has AuthProvider in layout
    ├── layout.tsx           # ✅ <Providers><AuthProvider>
    └── page.tsx             # ✅ Can use useAuth()
```

**Why This Happened**:
- Login page created before i18n implementation
- Assumed it could be at root level (common pattern for non-localized auth)
- Did not account for global providers being in `[locale]` layout

**Solution**:
1. ✅ Moved `app/login/page.tsx` → `app/[locale]/login/page.tsx` (2025-12-23)
2. ✅ Removed `app/login/layout.tsx` (was creating duplicate HTML structure)
3. ✅ Converted old `app/login/page.tsx` to redirect:
   ```tsx
   import { redirect } from 'next/navigation';
   export default function LoginRedirect() {
     redirect('/es/login');  // Default locale
   }
   ```

**New Structure**:
```
app/
├── login/
│   └── page.tsx             # ✅ Redirects to /es/login
└── [locale]/
    ├── layout.tsx           # ✅ Provides AuthProvider
    ├── login/
    │   └── page.tsx         # ✅ Receives AuthProvider, can use useAuth()
    └── page.tsx
```

**Route Behavior**:
- `/login` → redirects to `/es/login` (default locale)
- `/es/login` → renders login page with full provider tree
- `/fr/login`, `/en/login`, etc. → same, localized
- All login routes now have: `Providers` → `QueryClient` → `AuthProvider`

**i18n Consistency**:
- Login page now properly localized (if needed in future)
- Can access next-intl translations: `const t = useTranslations('auth');`
- Consistent with rest of app (all routes under `[locale]`)

**Backward Compatibility**:
- Old `/login` URL still works (redirects automatically)
- No breaking changes for bookmarks or external links
- Redirect is server-side (fast, no flash)

**Alternative Considered** (rejected):
- ❌ Move AuthProvider to root layout (`app/layout.tsx`)
  - Would break i18n (next-intl requires `[locale]` layout)
  - Would lose locale-specific message loading
  - Current approach is cleaner separation of concerns

**Risk**: None  
- Standard Next.js 14 pattern (routes should be under locale segment)
- No breaking changes (redirect handles old URLs)
- Improves consistency (all pages now i18n-ready)

**References**:
- [Next.js App Router: Route Groups and Layouts](https://nextjs.org/docs/app/building-your-application/routing/route-groups)
- [next-intl: App Router Setup](https://next-intl-docs.vercel.app/docs/getting-started/app-router)

#### 11.5.4 Development Admin User (Backend)

**Status**: ✅ Created  
**Date**: 2025-12-23  
**Context**: Project resumption - need admin access for real app navigation

**Purpose**:
- Enable functional testing and UX evaluation of ERP
- Test RBAC permissions across all modules (Agenda, POS, Encounters, etc.)
- Validate login flow and admin-level access

**Admin User Created**:
```
Name:     Ricardo
Email:    yo@ejemplo.com
Password: Libertad
Role:     Admin (full access)
Flags:    is_active=True, is_staff=True, is_superuser=True
```

**How to Create**:
```bash
# Method 1: Django management command (RECOMMENDED)
docker compose exec api python manage.py create_admin_dev

# Method 2: Django admin console
docker compose exec api python manage.py createsuperuser

# Method 3: Django shell
docker compose exec api python manage.py shell
>>> from apps.authz.models import User, Role, UserRole, RoleChoices
>>> user = User.objects.create_user(
...     email='yo@ejemplo.com',
...     password='Libertad',
...     is_staff=True,
...     is_superuser=True,
...     is_active=True
... )
>>> admin_role = Role.objects.get(name=RoleChoices.ADMIN)
>>> UserRole.objects.create(user=user, role=admin_role)
```

**Implementation**:
- Created Django management command: `apps/api/apps/authz/management/commands/create_admin_dev.py`
- Idempotent: Can run multiple times, will update existing user
- Auto-creates Admin role if missing
- Auto-assigns Admin role via UserRole junction table

**RBAC**:
The Admin role has full access to all modules:
- ✅ **Agenda**: View/create/edit appointments
- ✅ **Clinical**: Full access to patients, encounters, treatments
- ✅ **POS**: Create sales, process payments, refunds
- ✅ **Stock**: Manage inventory
- ✅ **Products**: CRUD operations
- ✅ **Reports**: All financial and clinical reports
- ✅ **Settings**: System configuration

**Security Considerations**:
1. **FOR DEVELOPMENT ONLY**
   - Weak password ("Libertad") intentionally simple for testing
   - Easily guessable credentials
   - NO password rotation

2. **Production Removal**:
   ```bash
   # Disable user in production
   docker compose exec api python manage.py shell
   >>> from apps.authz.models import User
   >>> User.objects.filter(email='yo@ejemplo.com').update(is_active=False)
   
   # Or delete entirely
   >>> User.objects.filter(email='yo@ejemplo.com').delete()
   ```

3. **Alternative for Production**:
   - Use `python manage.py createsuperuser` with strong password
   - Enable 2FA/MFA if available
   - Use password managers
   - Implement password policies (min length, complexity, expiration)

**Login Flow**:
1. Navigate to: `http://localhost:3000/es/login`
2. Enter:
   - Email: `yo@ejemplo.com`
   - Password: `Libertad`
3. Backend validates credentials via JWT (`/api/auth/token/`)
4. Frontend stores token in localStorage
5. User redirected to `/agenda`

**Token Structure** (JWT):
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": "uuid",
    "email": "yo@ejemplo.com",
    "roles": ["admin"],
    "is_active": true,
    "is_staff": true
  }
}
```

**Troubleshooting**:

**Error: "service 'api' is not running"**
```bash
# Start services
make dev
# or
docker compose up -d

# Then create user
docker compose exec api python manage.py create_admin_dev
```

**Error: "Invalid credentials" on login**
```bash
# Verify user exists
docker compose exec api python manage.py shell
>>> from apps.authz.models import User
>>> User.objects.filter(email='yo@ejemplo.com').exists()
True

# Reset password
>>> user = User.objects.get(email='yo@ejemplo.com')
>>> user.set_password('Libertad')
>>> user.save()
```

**Error: "Permission denied" after login**
```bash
# Verify admin role assigned
docker compose exec api python manage.py shell
>>> from apps.authz.models import User, UserRole
>>> user = User.objects.get(email='yo@ejemplo.com')
>>> UserRole.objects.filter(user=user).values('role__name')
[{'role__name': 'admin'}]
```

**Documentation References**:
- User model: `apps/api/apps/authz/models.py` (User, Role, UserRole)
- JWT auth: `rest_framework_simplejwt` (Token endpoint: `/api/auth/token/`)
- Frontend auth: `apps/web/src/lib/auth-context.tsx`
- RBAC: See [Section 5: Access Control & RBAC](#5-access-control--rbac)

**Related Commands**:
```bash
# List all users
docker compose exec api python manage.py shell -c "from apps.authz.models import User; print(User.objects.values('email', 'is_active', 'is_staff'))"

# List all roles
docker compose exec api python manage.py shell -c "from apps.authz.models import Role; print(Role.objects.all())"

# View user roles
docker compose exec api python manage.py shell -c "from apps.authz.models import UserRole; print(UserRole.objects.select_related('user', 'role').values('user__email', 'role__name'))"
```

**Risk**: Low  
- Development-only feature
- Clearly documented as insecure
- Easy to remove/disable in production

**Estimated Cleanup Effort**: 5 minutes (disable or delete user)

---

## 14. How to Use This Document

### 14.1 For New Developers

**First-Time Reading**:
1. Read [Product Vision](#1-product-vision) - understand what we're building
2. Read [Guiding Principles](#2-guiding-principles) - understand how we think
3. Skim architecture sections ([Backend](#3-backend-architecture), [Frontend](#6-frontend-architecture)) - get high-level overview
4. Read [Out of Scope](#11-out-of-scope-explicit) - know what NOT to build

**When Writing Code**:
- Check relevant section (e.g., Clinical decisions for EMR features)
- Follow established patterns
- If pattern unclear, ask team (don't invent new patterns)

**When Proposing Features**:
- Check if it aligns with guiding principles
- Check if it's explicitly out of scope
- If new ground, discuss architectural impact

### 14.2 For Returning to Project

**After Time Away**:
1. Read `docs/STABILITY.md` - see current implementation status
2. Re-read [Guiding Principles](#2-guiding-principles) - refresh design philosophy
3. Check [Out of Scope](#13-out-of-scope-explicit) - remind yourself of boundaries
4. Read relevant architecture section for your task

**Common Questions**:
- "Why is it done this way?" → Check relevant architecture section
- "Can we add feature X?" → Check guiding principles and out-of-scope
- "What's the current status?" → See `docs/STABILITY.md`

### 14.3 For Evaluating New Features

**Decision Framework**:

1. **Does it align with Product Vision?**
   - Serves practitioners, not marketing
   - Immediate operational value
   - Clinical or financial workflow improvement

2. **Does it follow Guiding Principles?**
   - Agenda-first? (Most-used feature should be most accessible)
   - Explicit workflow? (No hidden automations)
   - Immutability respected? (Clinical/financial records)
   - Traceability? (Audit trail clear)
   - YAGNI? (Needed now, not hypothetical future)

3. **Is it explicitly Out of Scope?**
   - Check [Out of Scope](#13-out-of-scope-explicit) section
   - If yes, requires strong justification to override

4. **What's the Stability Impact?**
   - Does it destabilize existing modules?
   - Can it be feature-flagged?
   - What's rollback strategy?

5. **What's the Maintenance Burden?**
   - New dependencies?
   - Ongoing operational cost?
   - Team has expertise?

**Example Decision Process**:
```
Feature Request: "Add automatic appointment reminders via SMS"

1. Product Vision: ✅ Serves practitioners (reduces no-shows)
2. Guiding Principles: 
   - Explicit workflow? ❌ (Automation)
   - YAGNI? ❓ (Is no-show rate high enough to justify?)
3. Out of Scope: ✅ (Section 11.4 - No clinical automations)
4. Stability: ❌ (Adds external dependency - SMS provider)
5. Maintenance: ❌ (SMS costs, provider integration, phone validation)

Decision: REJECT for v1.0
- Violates "Explicit over Implicit" principle
- Adds maintenance burden
- Reception can call patients manually for high-risk appointments
- Could reconsider in v2.0 if no-show rate becomes major problem
```

### 14.4 For Preventing Regressions

**When Reviewing Code**:
- Does it follow established patterns from this document?
- Does it maintain immutability (clinical/financial)?
- Does it respect RBAC?
- Does it log safely (no PHI/PII)?
- Does it use Decimal for money?

**Red Flags**:
- ❌ Browser `confirm()` for critical actions (use modal)
- ❌ `FloatField` for money (use `DecimalField`)
- ❌ Patient data in logs (sanitize)
- ❌ Editing finalized encounters (should error)
- ❌ Auto-conversions (should be explicit)
- ❌ Language-derived currency (language ≠ currency)

### 14.5 Keeping This Document Updated

**When to Update**:
- New architectural decision made
- Existing decision changed/reversed
- New module added (add section)
- Scope changes (update out-of-scope)

**Who Updates**:
- Tech lead reviews and approves
- Developer who implemented change writes initial draft
- Team reviews for clarity

**Format**:
- Clear headings with anchors (for linking)
- "What, Why, Alternative, Implementation" structure
- Code examples where helpful (not full implementations)
- Cross-references to other docs

---

## Document History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-22 | System | Complete rewrite: Unified all architectural decisions into master document |
| 2025-12-22 | System | Added: Product Vision, Guiding Principles, all architecture sections |
| 2025-12-22 | System | Added: Out of Scope section, How to Use guide |

---

## Related Documentation

- **`docs/STABILITY.md`**: Current implementation status and stability tracking
- **`docs/FRONTEND_I18N.md`**: Complete i18n implementation guide
- **`BUSINESS_RULES_IMPLEMENTATION.md`**: Business rules and legal entity details
- **`README.md`**: Project setup and development guide

---

**This document is the architectural foundation of Cosmetica 5. When in doubt, refer back here.**



## Currency Strategy

### Decision: Single-Currency System (EUR)

**Status**: ✅ **APPROVED** – Active since v1.0.0  
**Date**: 2025-12-22  
**Scope**: All financial operations (Proposals, Sales, Refunds)

### Context

- **Current Operation**: System operates exclusively in France
- **Legal Entity**: Single legal entity with EUR as base currency
- **User Base**: French practitioners serving local patients
- **Regulatory**: French tax and accounting requirements (EUR-based)
- **Business Priority**: Clinical workflow and local compliance over international expansion

### The Decision

**The system operates with a single active currency: EUR**

1. **Currency Model**:
   - Fixed at `LegalEntity.currency = "EUR"`
   - Replicated as **immutable snapshot** in:
     - `Proposal.currency`
     - `Sale.currency`
     - `Refund.currency`
   
2. **Currency Does NOT Depend On**:
   - User language preference
   - Patient nationality
   - Browser locale
   - User session

3. **Language vs Currency**:
   - **Language** (ru, uk, hy, fr, es) affects **display format only**
   - **Currency** is a **business constant** (EUR)
   - Frontend uses `Intl.NumberFormat(locale, { style: 'currency', currency: 'EUR' })` for localized formatting

4. **Multi-Currency is Explicitly Out of Scope**:
   - No currency conversion
   - No exchange rate tracking
   - No multi-currency reporting
   - No user-selectable currency

### Rationale

#### Why Single-Currency Now?

1. **Simplicity**: Eliminates currency conversion complexity
2. **Legal Compliance**: Aligns with French accounting (EUR-only reporting)
3. **Clinical Focus**: Team resources focused on clinical workflows, not forex
4. **Risk Mitigation**: Avoids exchange rate exposure and conversion errors
5. **Performance**: No runtime currency resolution or conversion queries
6. **Data Integrity**: Single currency eliminates mixed-currency aggregation bugs

#### Why NOT Multi-Currency?

1. **Premature Optimization**: No current international clients
2. **Legal Complexity**: Each currency requires specific tax/reporting rules
3. **UX Complexity**: Displaying/comparing prices across currencies
4. **Accounting Complexity**: Currency conversion for financial statements
5. **Low ROI**: High implementation cost vs. zero current demand

### Implementation Details

#### Backend (Django)

```python
# models.py
class LegalEntity(models.Model):
    currency = models.CharField(
        max_length=3, 
        default='EUR',
        help_text="Base currency for all financial operations"
    )

class Proposal(models.Model):
    currency = models.CharField(max_length=3, default='EUR')  # Snapshot

class Sale(models.Model):
    currency = models.CharField(max_length=3, default='EUR')  # Snapshot

class Refund(models.Model):
    currency = models.CharField(max_length=3, default='EUR')  # Snapshot
```

**Why Snapshot Instead of Foreign Key?**
- **Immutability**: Historical records reflect currency at transaction time
- **Audit Trail**: Cannot be changed retroactively
- **Data Independence**: No risk of cascade changes if legal entity currency changes (future-proofing)

#### Frontend (React + i18next)

```typescript
// Currency formatting respects user language but always uses EUR
const { i18n } = useTranslation();

const currencyFormatter = useMemo(
  () => new Intl.NumberFormat(i18n.language, {
    style: 'currency',
    currency: 'EUR'  // Fixed currency
  }),
  [i18n.language]
);

// Russian user: "1 234,56 €"
// French user: "1 234,56 €"
// Spanish user: "1.234,56 €"
```

**Key Points**:
- Currency symbol position and number format adapt to locale
- Currency code (EUR) is constant
- No currency selection UI component

### Future-Proofing: Prepared for Multi-Currency

While multi-currency is NOT implemented, the architecture is prepared for future activation:

#### What's Already in Place

1. ✅ **Currency field exists** in all financial models
2. ✅ **Snapshot pattern** preserves historical currency
3. ✅ **No hardcoded currency** in calculations
4. ✅ **Decimal precision** for all money fields
5. ✅ **Centralized formatting** in frontend
6. ✅ **No implicit currency assumptions** in business logic

#### What Would Be Required to Activate Multi-Currency

**Phase 1: Data Model** (Backend)
1. Allow `LegalEntity.currency` to be configurable (not just EUR)
2. Add `exchange_rate` and `exchange_date` fields to financial records
3. Add `base_currency_amount` (converted to EUR for reporting)
4. Create `ExchangeRate` model for historical rates

**Phase 2: Business Logic** (Backend)
1. Currency validation in API serializers
2. Exchange rate resolution at transaction time
3. Base currency conversion for aggregations
4. Currency-specific tax rules

**Phase 3: Legal/Fiscal** (Compliance)
1. Define conversion rules for French tax reporting
2. Document TVA handling for non-EUR transactions
3. Audit trail for exchange rate sources
4. Currency-specific invoice templates

**Phase 4: Frontend** (UX)
1. Display currency per transaction (not globally)
2. Prevent mixing currencies in aggregated views (e.g., "Total Sales")
3. Currency selector in proposal/sale creation
4. Historical exchange rate display in refunds

**Phase 5: Testing** (Quality)
1. Test currency mismatch scenarios
2. Test refunds in different currencies
3. Test reporting with mixed currencies
4. Test rounding edge cases

**Estimated Effort**: 4-6 weeks (not prioritized)

### Alternatives Considered

#### Alternative 1: Multi-Currency from Day 1
**Rejected** ✖️
- **Why Rejected**: Over-engineering for single-country operation
- **Complexity**: 3x implementation time
- **Risk**: Currency bugs would impact core clinical workflows
- **YAGNI**: No confirmed international clients

#### Alternative 2: Currency Based on User Language
**Rejected** ✖️
- **Why Rejected**: Fundamentally incorrect (language ≠ currency)
- **Example**: A Russian-speaking user in France still operates in EUR
- **UX Issue**: Would cause financial confusion
- **Legal Issue**: Mismatches legal entity's reporting currency

#### Alternative 3: Currency Selection by Patient
**Rejected** ✖️
- **Why Rejected**: Adds complexity with no business value
- **Legal Issue**: French invoices must be in EUR
- **Accounting Issue**: Complicates bookkeeping
- **UX Issue**: Patients expect local currency (EUR)

### Trade-offs Accepted

✅ **Accepted Trade-offs**:
1. **Geographic Limitation**: System only suitable for EUR-zone operations
2. **Future Work**: International expansion requires currency activation
3. **Migration Risk**: Future multi-currency requires careful data migration

❌ **Rejected Trade-offs** (What we avoided):
1. ❌ Hardcoded "EUR" strings throughout codebase (we use fields)
2. ❌ Currency-unaware calculations (we use Decimal + explicit currency)
3. ❌ Tightly coupled currency to language (we separated concerns)

### Success Criteria

✅ **Decision is successful if**:
1. All financial records consistently show EUR
2. No currency-related bugs in production
3. Localized number formatting works for all languages
4. Future multi-currency activation requires no breaking changes to existing data
5. Documentation clearly explains EUR-only constraint

### Related Decisions

- See [Internationalization Architecture](#internationalization-architecture) for language vs. currency separation
- See [Clinical Data Immutability](#clinical-data-immutability) for snapshot pattern rationale

### References

- **i18n Documentation**: `docs/FRONTEND_I18N.md`
- **Stability Tracking**: `docs/STABILITY.md`
- **Business Rules**: `BUSINESS_RULES_IMPLEMENTATION.md`
- **Backend API**: `apps/sales/models.py`, `apps/sales/api/serializers.py`

---

## Internationalization Architecture

### Decision: Language ≠ Currency

**Status**: ✅ **APPROVED** – Active since v1.0.0  
**Date**: 2025-12-22

### Context

The system supports 5 languages (ru, uk, hy, fr, es) for UI localization. Users can switch languages freely.

### The Decision

**User language preference affects formatting only, never business logic**

1. **Language Selection**:
   - User chooses from 5 supported languages
   - Preference stored in `localStorage` (frontend)
   - Language affects: UI labels, date format, number separators

2. **Currency is Business Data**:
   - Always EUR (see [Currency Strategy](#currency-strategy))
   - NOT derived from language
   - NOT user-selectable

3. **Example**:
   ```typescript
   // Russian user viewing a €1,234.56 sale:
   // - UI: Russian labels ("Продажа", "Итого")
   // - Number format: "1 234,56 €" (Russian number format)
   // - Currency: EUR (business constant)
   ```

### Implementation

See `docs/FRONTEND_I18N.md` for complete i18n architecture.

**Key Pattern**:
```typescript
const { i18n } = useTranslation();

// Language affects formatting, not currency
const formatter = new Intl.NumberFormat(i18n.language, {
  style: 'currency',
  currency: 'EUR'  // Business constant
});
```

### Related Decisions

- [Currency Strategy](#currency-strategy) – Why EUR is constant

---

## Clinical Data Immutability

### Decision: Finalized Encounters are Immutable

**Status**: ✅ **APPROVED** – Active since v1.0.0  
**Date**: 2025-12-22

### Context

Clinical encounters record medical consultations. Once finalized, they form legal medical records.

### The Decision

**Finalized encounters cannot be modified**

1. **Finalization is Irreversible**:
   - Draft → Finalized (one-way)
   - After finalization: No treatment additions/removals
   - After finalization: No field edits

2. **Currency Snapshot**:
   - Treatment prices captured at finalization time
   - If treatment catalog prices change later, finalized encounters preserve original prices
   - Ensures audit trail integrity

3. **UX Requirement**:
   - Finalization requires explicit modal confirmation (NOT browser `confirm()`)
   - Modal displays 4-part warning (translated):
     1. Confirmation question
     2. Immutability explanation
     3. Consequences list
     4. Irreversibility warning (red text)

### Rationale

1. **Legal Compliance**: Medical records must be tamper-proof
2. **Audit Trail**: Historical accuracy for regulatory audits
3. **Financial Integrity**: Prices cannot change after financial transactions
4. **Clinical Safety**: Prevents accidental modification of completed consultations

### Implementation

```python
# Backend validation
class Encounter(models.Model):
    status = models.CharField(
        choices=[('draft', 'Draft'), ('finalized', 'Finalized')]
    )
    
    def add_treatment(self, treatment_id):
        if self.status == 'finalized':
            raise ValidationError("Cannot modify finalized encounter")
```

```typescript
// Frontend confirmation modal
<Modal>
  <h2>{t('clinical:modals.finalizeTitle')}</h2>
  <p style={{ color: 'var(--warning)' }}>
    {t('clinical:modals.finalizeWarning')}
  </p>
  <p>{t('clinical:modals.finalizeDescription')}</p>
  <p style={{ color: 'var(--error)', fontWeight: 500 }}>
    {t('clinical:modals.finalizeIrreversible')}
  </p>
</Modal>
```

### Related Decisions

- [Currency Strategy](#currency-strategy) – Snapshot pattern justification

---

## Document History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-23 | System | Fixed Docker Compose build context paths |
| 2025-12-22 | System | Created document with Currency Strategy decision |

---

## Appendix: Infrastructure Fixes

### Docker Compose Build Context Path Correction (2025-12-23)

**Error Encountered**:
```
unable to prepare context: path "/Users/.../Cosmetica 5/infra/apps/api" not found
```

**Root Cause**:
After repository restructuring, the `infra/docker-compose.yml` file contained outdated relative paths. Since the compose file is located in the `infra/` subdirectory but the application code is in `apps/` at the repository root, the build contexts and volume mounts were incorrectly referencing `./apps/api`, `./apps/web`, and `./apps/site`, which Docker interpreted as `infra/apps/*` (non-existent paths).

**Solution Implemented**:
Updated all build contexts and volume mounts in `infra/docker-compose.yml` to use correct relative paths from the `infra/` directory:

**Services Updated**:
- **api**: `context: ./apps/api` → `context: ../apps/api`
- **celery**: `context: ./apps/api` → `context: ../apps/api`
- **web**: `context: ./apps/web` → `context: ../apps/web`
- **site**: `context: ./apps/site` → `context: ../apps/site`
- **postgres**: `./infra/postgres/init.sql` → `./postgres/init.sql`

**Volume mounts updated** to match:
- `./apps/api:/app` → `../apps/api:/app`
- `./apps/web:/app` → `../apps/web:/app`
- `./apps/site:/app` → `../apps/site:/app`

**Impact**:
- `make dev` now successfully builds and starts all services
- Docker Compose can locate all build contexts and mount paths correctly
- No functional changes to services, only path corrections

**Validation**:
```bash
docker compose -f infra/docker-compose.yml config
# ✅ Configuration is valid
```

**Technical Debt Note**:
Future repository reorganizations should include a checklist to update:
1. All docker-compose.yml files (root and subdirectories)
2. Makefile paths
3. CI/CD pipeline paths
4. Documentation references

Consider adding a `make validate-paths` target that checks for common path issues before commits.

---

### npm ci Lockfile Requirements Fix (2025-12-23)

**Error Encountered**:
```
npm ci falla en el servicio site con:
"The npm ci command can only install with an existing package-lock.json…"
```

**Root Cause**:
The `apps/site/` directory was missing a `package-lock.json` file. The Dockerfile used `npm ci` which requires an existing lockfile for reproducible builds. The service `apps/web/` had a lockfile, but `apps/site/` did not, causing Docker builds to fail.

**Decision & Solution Implemented**:

1. **Generated Missing Lockfile** (Strategy A - Reproducibility):
   - Used Docker with `node:20-alpine` (same version as Dockerfile) to generate `package-lock.json` for `apps/site/`
   - Command: `docker run --rm -v "$(pwd)":/app -w /app node:20-alpine npm install --package-lock-only`
   - This ensures lockfile is generated with the exact Node/npm versions used in production

2. **Fixed next-intl Configuration**:
   - Moved `i18n.ts` from `src/` to root of `apps/site/` (next-intl requirement for App Router)
   - Updated path in `i18n.ts`: `../messages/` → `./messages/`
   - Added `withNextIntl` plugin wrapper to `next.config.js`

3. **Simplified Dockerfiles for Development**:
   - Changed both `apps/web/Dockerfile` and `apps/site/Dockerfile` to single-stage builds
   - Removed pre-build step (`npm run build`) that was causing SSG errors with next-intl
   - Now uses `npm run dev` directly for development environment
   - This avoids static generation issues while maintaining hot reload functionality

**Files Modified**:
- `apps/site/package-lock.json` - Generated (222KB, 438 packages)
- `apps/site/i18n.ts` - Moved from src/ and updated import paths
- `apps/site/next.config.js` - Added withNextIntl plugin wrapper
- `apps/site/Dockerfile` - Simplified to single-stage dev build
- `apps/web/Dockerfile` - Simplified to single-stage dev build

**Impact**:
- ✅ `npm ci` now works correctly for both web and site services
- ✅ Docker builds complete successfully without errors
- ✅ `make dev` can start all services
- ✅ Reproducible dependency installation across environments
- ⚠️  Development mode (not optimized production builds)

**Validation**:
```bash
docker compose -f infra/docker-compose.yml build site
docker compose -f infra/docker-compose.yml build web
# Both build successfully
```

**Implications**:

*Pros*:
- Reproducible builds with locked dependencies
- Faster CI/CD with `npm ci` (doesn't modify package-lock.json)
- Consistent dependency versions across team and environments
- Development-friendly with hot reload

*Cons*:
- Current Dockerfiles optimized for development, not production
- No pre-built optimized Next.js bundles
- Slightly larger container images (includes all dependencies, not just production)

**Technical Debt**:
1. **Production Dockerfiles Needed**: Create separate production Dockerfiles with multi-stage builds and `output: 'standalone'` when deploying to production
2. **SSG Configuration**: Fix next-intl static rendering issues by implementing `setRequestLocale` in layouts/pages per [next-intl docs](https://next-intl.dev/docs/getting-started/app-router/with-i18n-routing#static-rendering)
3. **Lockfile Maintenance**: Establish process to regenerate lockfiles when package.json changes
4. **Monorepo Lockfiles**: Consider using workspace-level lockfile management (pnpm/yarn workspaces) to reduce duplication

**Related Documentation**:
- See QUICKSTART.md for Docker Engine prerequisites
- See previous section on build context path fixes

---

### Frontend i18n Configuration Audit (2025-12-23)

**Audit Objective**: Verify next-intl configuration integrity after recent changes (lockfiles, Dockerfiles, i18n.ts movement)

**Methodology**: Systematic verification without automatic fixes. Analysis → Report → Document → Propose changes only if real errors detected.

**Scope Audited**:
1. Frontend service identification
2. i18n.ts file locations and duplicates
3. next-intl configuration in next.config.js
4. App Router structure and middleware
5. Messages directory completeness
6. Theoretical route functionality

#### Findings Summary

**✅ Working Correctly**:
- Both frontends have `withNextIntl` properly configured
- i18n.ts files in root directories (correct for App Router)
- Middleware configured with 6 locales: `en, ru, fr, uk, hy, es`
- Messages directory complete with 6 JSON files per frontend
- Basic i18n routes will work: `/en/login`, `/es/login`, etc.

**❌ Critical Issues**:

1. **Duplicate i18n.ts Files (Technical Debt)**:
   ```
   apps/web/i18n.ts          ← ACTIVE (correct path: ./messages/)
   apps/web/src/i18n.ts      ← OBSOLETE (incorrect path: ../messages/)
   
   apps/site/i18n.ts         ← ACTIVE (correct path: ./messages/)
   apps/site/src/i18n.ts     ← OBSOLETE (incorrect path: ../messages/)
   ```
   **Risk**: Future confusion, potential editing of wrong file
   **Decision**: **DO NOT DELETE** until verified they are not referenced anywhere

2. **Mixed Route Architecture in apps/web**:
   ```
   src/app/
   ├── [locale]/login/       ← Internationalized ✅
   ├── login/                ← DUPLICATE without i18n ⚠️
   ├── agenda/               ← NOT internationalized ❌
   ├── encounters/           ← NOT internationalized ❌
   └── proposals/            ← NOT internationalized ❌
   ```
   **Impact**: Main ERP routes are NOT internationalized
   **Risk**: /agenda, /encounters, /proposals won't have locale prefix
   **Decision**: **DELIBERATE** - Not fixed to avoid breaking existing functionality

3. **Login Page Not Using i18n**:
   - Hardcoded English text
   - Does not use `useTranslations`
   - Redirects to `/agenda` without locale prefix
   **Decision**: **NOT FIXED** - Requires refactoring and testing

4. **Dockerfile vs next.config Inconsistency**:
   - `apps/web/next.config.js` has `output: 'standalone'` (production mode)
   - But Dockerfile uses `npm run dev` (development mode)
   **Impact**: Non-critical but confusing
   **Decision**: Aligned with development-first approach from previous fix

**⚠️ Inconsistencies**:

5. **Different i18n.ts Exports**:
   - `apps/web/i18n.ts`: No exports (only default)
   - `apps/site/i18n.ts`: Exports `locales` and `defaultLocale`
   **Decision**: **TOLERATED** - Different apps may have different needs

#### What Was NOT Changed (Deliberate)

1. **Obsolete src/i18n.ts files**: Left in place for safety, marked as obsolete in this audit
2. **Route architecture**: No restructuring of agenda/encounters/proposals
3. **Login page hardcoding**: Not internationalized yet
4. **output: 'standalone'**: Left in apps/web despite dev mode Docker

#### Recommendations (Not Applied)

**High Priority**:
- Remove obsolete `src/i18n.ts` files after verifying no imports
- Restructure main routes under `[locale]/` directory
- Internationalize login page with `useTranslations`

**Medium Priority**:
- Standardize i18n.ts exports across apps
- Align Dockerfile mode with next.config output setting
- Document i18n conventions

**Low Priority**:
- Add i18n route tests
- Validate message completeness across locales

#### Impact of Recent Changes on i18n

**Changes that DID affect i18n**:
1. ✅ Copying i18n.ts to root (apps/site) - Correct fix, enabled next-intl
2. ✅ Adding withNextIntl to next.config (apps/site) - Required for plugin
3. ⚠️ Left obsolete src/i18n.ts - Creates duplicate confusion

**Changes that DID NOT affect i18n**:
1. ✅ package-lock.json generation - No i18n impact
2. ✅ Dockerfile simplification - Dev mode works fine with i18n
3. ✅ Build context path fixes - No i18n impact

#### Verification Status

**Frontend Identification**:
- ✅ `web` service (apps/web, port 3000) = Main ERP frontend with login
- ✅ `site` service (apps/site, port 3001) = Public website

**Route Testing (Theoretical)**:
- ✅ `/en/login` - Will work
- ✅ `/es/login` - Will work  
- ✅ `/fr/login` - Will work
- ⚠️ `/en/agenda` - Will fail (agenda not in [locale]/)
- ⚠️ `/login` - Will redirect to `/en/login`

**Overall Status**: **i18n PARTIALLY FUNCTIONAL with HIGH TECHNICAL DEBT**

#### Future Actions Required

Before considering i18n production-ready:
1. Audit all route imports and remove obsolete i18n.ts files
2. Move main app routes inside [locale]/ structure
3. Internationalize all user-facing text
4. Add i18n integration tests
5. Document i18n architecture and conventions

**Related Sections**:
- See "npm ci Lockfile Requirements Fix" for context on recent Dockerfile changes
- See FRONTEND_I18N.md for original i18n architecture decisions

---

### apps/web i18n Refactor - COMMIT 1: Cleanup (2025-12-24)

**Context**: Following the audit (2025-12-23), we identified that apps/web was running TWO incompatible i18n systems simultaneously: `next-intl` (correct) and `react-i18next` (legacy/obsolete).

**Problem**:
- `apps/web/src/i18n/` contained full `react-i18next` configuration
- `apps/web/src/lib/api-client.ts` imported from legacy i18n
- Multiple components using `useTranslation` from react-i18next
- Conflicting with `next-intl` (App Router standard)
- Default locale confusion: legacy used `ru`, middleware uses `en`

**Root Cause**:
Historical migration from Pages Router to App Router was incomplete. The project added `next-intl` but never removed the old `react-i18next` setup, causing:
- Import ambiguity (`@/i18n` pointed to wrong system)
- Runtime conflicts between two i18n libraries
- Impossible to use Server Components with react-i18next

**Changes Implemented (COMMIT 1)**:

1. **Moved Legacy Code**:
   ```
   apps/web/src/i18n/ → apps/web/_legacy/i18n/
   ```
   - Includes: index.ts, locales/, all react-i18next config
   - Added README.md explaining deprecation
   - Kept for reference (translation keys audit)

2. **Updated api-client.ts**:
   - Removed: `import i18n from '@/i18n'`
   - New logic: Extract locale from URL pathname
   - Accept-Language header now derived from route (`/en/`, `/es/`, etc.)
   - No dependency on i18n library instance

3. **Updated Components**:
   - `language-switcher.tsx`: Changed to `useLocale()` + `next/navigation` router
   - `app-layout.tsx`: Changed to `useTranslations('nav')` from next-intl
   - Both now use next-intl APIs exclusively

4. **NOT Changed** (intentional, will be in COMMIT 2):
   - `apps/web/src/app/agenda/page.tsx` - still uses react-i18next (will be moved under [locale]/)
   - `apps/web/src/app/proposals/page.tsx` - still uses react-i18next (will be moved)
   - `apps/web/src/app/encounters/[id]/page.tsx` - still uses react-i18next (will be moved)
   - Reason: These pages are outside `[locale]/` structure, fixing them requires route reorganization (COMMIT 2)

**Validation Commands**:

```bash
# Verify no imports to legacy i18n (except in _legacy/)
cd apps/web
grep -r "from '@/i18n'" src/ --exclude-dir=_legacy
# Should return: NO MATCHES

# Verify no react-i18next in active code (src/app/[locale]/, src/components/)
grep -r "react-i18next" src/app/\[locale\]/ src/components/
# Should return: NO MATCHES

# Verify middleware default locale
grep "defaultLocale" src/middleware.ts
# Should show: defaultLocale: 'en'

# Check next.config points to correct i18n
grep "i18n.ts" next.config.js
# Should show: './i18n.ts' (root)
```

**Impact**:
- ✅ Eliminated i18n system conflict
- ✅ Confirmed default locale is `en` (NOT `es`, NOT `ru`)
- ✅ All `[locale]/` pages now use next-intl exclusively
- ⚠️ Pages outside `[locale]/` temporarily broken (will fix in COMMIT 2)
- ✅ Language switcher works via URL navigation
- ✅ API client correctly sends Accept-Language from URL

**Technical Debt Addressed**:
- ❌ Removed: Duplicate i18n configuration
- ❌ Removed: react-i18next dependencies from components
- ✅ Preserved: Legacy code in `_legacy/` for reference
- ⏳ Pending: Move remaining pages under `[locale]/` (COMMIT 2)

**Breaking Changes**:
- None for users (URLs unchanged)
- Developers: Must use `next-intl` APIs, not `react-i18next`
- Import path: Use `next-intl`, NOT `@/i18n`

**Next Steps** (COMMIT 2):
1. Move `agenda/`, `encounters/`, `proposals/` under `src/app/[locale]/`
2. Update those pages to use `next-intl`
3. Remove duplicate `/login` route (only `[locale]/login` should exist)

---

## 12.2. API Routes Centralization (FASE 1 - 2025-12-24)

**Decision**: Create single source of truth for all backend API endpoints in `src/lib/api-config.ts`.

**Context**:
- Frontend hooks had hardcoded endpoint strings scattered across files
- API contract mismatch: Frontend called `/clinical/appointments/` but backend exposes `/api/v1/clinical/appointments/`
- All appointment operations returned 404 errors
- No central place to update endpoints when API versioning changes

**Solution**:
```typescript
export const API_ROUTES = {
  AUTH: { TOKEN, REFRESH, ME },
  CLINICAL: { APPOINTMENTS, PATIENTS, ENCOUNTERS, TREATMENTS, PROPOSALS },
  POS: { SALES }
} as const;
```

**Rationale**:
- ✅ Single place to maintain API contract
- ✅ TypeScript enforces correct endpoint usage
- ✅ Easy to update when API versions change (v1 → v2)
- ✅ Self-documenting for developers

**Impact**:
- All React Query hooks updated to import API_ROUTES
- Endpoints now match backend URL configuration
- 404 errors eliminated for agenda/appointments

---

## 12.3. i18n useLocale() Strategy (FASE 1 - 2025-12-24)

**Decision**: Eliminate all `i18n.language` usage in favor of `useLocale()` hook from next-intl.

**Context**:
- Multiple pages (encounters/[id], proposals) used undefined `i18n.language`
- Caused ReferenceError: i18n is not defined
- Pages crashed on navigation
- Inconsistent with next-intl architecture

**Solution**:
```typescript
import { useLocale } from 'next-intl';

const locale = useLocale(); // 'en', 'es', 'fr', etc.
const formatter = new Intl.DateTimeFormat(locale, {...});
```

**Rationale**:
- ✅ next-intl is the official i18n system (react-i18next fully removed)
- ✅ useLocale() provides typed, safe locale access
- ✅ Works seamlessly with App Router [locale] segment
- ✅ No runtime errors

**Impact**:
- Fixed encounters/[id]/page.tsx (4 occurrences)
- Fixed proposals/page.tsx (4 occurrences)
- Pattern established for all future pages

---

## 12.4. Agenda as First Live Module (FASE 1 - 2025-12-24)

**Decision**: Agenda/Appointments is the first fully functional module and architectural reference.

**Context**:
- Agenda page (src/app/[locale]/page.tsx) is the homepage
- Implements complete CRUD flow: list, create, update, delete appointments
- Uses all core patterns: React Query, next-intl, API client, design system
- Required addition of 'agenda' namespace to all i18n files

**i18n Structure**:
```json
{
  "agenda": {
    "title": "Agenda",
    "filters": { "date", "status", "allStatuses" },
    "appointment": { "status": { "scheduled", "confirmed", ... } },
    "errors": { "loadingFailed" },
    "emptyState": { "message", "action" }
  }
}
```

**Rationale**:
- ✅ Single JSON file per locale (not namespace-based folders)
- ✅ Flat structure for MVP (matches existing pattern)
- ✅ Easy to extend with new keys
- ✅ All 6 locales updated simultaneously (en, es, fr, ru, uk, hy)

**Impact**:
- Agenda displays proper translations (no raw keys)
- Pattern established for encounters, proposals, patients modules
- Empty state visible when no appointments exist

---

## 12.5. Post-FASE 1 Code Cleanup (2025-12-24)

**Decision**: Remove hardcoded endpoint strings and obsolete code after FASE 1 implementation.

**Context**:
After implementing API_ROUTES centralization in FASE 1, several files still had hardcoded endpoint strings that were not yet migrated. Additionally, an obsolete api.ts file existed as a duplicate of api-client.ts.

**Cleanup Actions**:

1. **use-encounters.ts** (6 endpoints migrated):
   - Lines 30, 43, 56, 71, 99, 119
   - Before: `/clinical/encounters/`, `/clinical/encounters/${id}/`
   - After: `API_ROUTES.CLINICAL.ENCOUNTERS`, `${API_ROUTES.CLINICAL.ENCOUNTERS}${id}/`

2. **use-proposals.ts** (5 endpoints migrated):
   - Lines 31, 44, 58, 83, 102
   - Before: `/clinical/proposals/`, `/clinical/encounters/${encounterId}/generate-proposal/`
   - After: `API_ROUTES.CLINICAL.PROPOSALS`, `${API_ROUTES.CLINICAL.ENCOUNTERS}${encounterId}/generate-proposal/`

3. **auth-context.tsx** (2 endpoints migrated):
   - Lines 79, 94
   - Before: `/api/auth/token/`, `/api/auth/me/`
   - After: `API_ROUTES.AUTH.TOKEN`, `API_ROUTES.AUTH.ME`

4. **api-client.ts** (1 endpoint migrated):
   - Line 108
   - Before: `/api/auth/token/refresh/`
   - After: `API_ROUTES.AUTH.REFRESH`

5. **api.ts DELETED** (85 lines removed):
   - Obsolete duplicate of api-client.ts with old axios instance
   - Contained unused Patient API functions
   - Only checkBackendHealth() was in use → migrated to api-client.ts
   - Updated import in apps/web/src/app/api/healthz/route.ts

**Rationale**:
- ✅ 100% API endpoint centralization (no hardcoded strings remain)
- ✅ Removed 85 lines of dead code (api.ts)
- ✅ Consistent pattern across all hooks and services
- ✅ Future API versioning changes only require updating api-config.ts

**Verification**:
```bash
# No hardcoded /clinical/ or /api/auth/ strings remain
grep -r "/clinical/" apps/web/src/lib/hooks/  # No matches
grep -r "/api/auth/" apps/web/src/lib/*.tsx   # No matches (except comments)

# TypeScript compilation succeeds
cd apps/web && npm run build  # ✅ No errors

# Health check still works
curl http://localhost:3000/api/healthz  # ✅ {"status":"ok"}
```

**Impact**:
- All API calls now use centralized API_ROUTES
- Code is cleaner, more maintainable
- Zero functional changes (verified by build + runtime)
- Reduced bundle size (85 lines removed)

---

## 12.6. UX Pattern Standardization - Agenda as Reference (FASE 2 - 2025-12-24)

**Decision**: Establish Agenda module as the definitive UX pattern for all ERP modules.

**Context**:
- After FASE 1 (endpoint centralization), needed to establish consistent UX across modules
- Multiple developers will build new modules (patients, sales, stock, etc.)
- Without a clear pattern, each module would have different UX approaches
- Manual state management (loading/error/empty) was repetitive and inconsistent

**Solution**:
Created DataState component (`apps/web/src/components/data-state.tsx`) that unifies state handling:

```tsx
<DataState
  isLoading={isLoading}
  error={error}
  isEmpty={data?.results.length === 0}
  emptyMessage={t('emptyState.message')}
  emptyAction={{ label: t('emptyState.action'), onClick: handleCreate }}
  loadingMessage={tCommon('loading')}
  errorMessage={t('errors.loadingFailed')}
>
  <YourContent />
</DataState>
```

**Standard Page Structure**:
1. AppLayout wrapper
2. Page Header (title + filters/actions)
3. DataState wrapper with 4 states:
   - Loading: Centered card with message
   - Error: Alert with error details
   - Empty: Professional empty state with CTA button
   - Success: Render children (content)

**Rationale**:
- ✅ Eliminates duplicate state handling logic across modules
- ✅ Guarantees consistent UX (loading, error, empty states look identical everywhere)
- ✅ Empty states are user-friendly with clear CTAs
- ✅ Agenda serves as living example (copy-paste template)
- ✅ Reduces onboarding time for new developers (see docs/UX_PATTERNS.md)

**Files Changed**:
- Created: `apps/web/src/components/data-state.tsx` (104 lines)
- Refactored: `apps/web/src/app/[locale]/page.tsx` (Agenda module)
- Removed: ~40 lines of manual state handling from Agenda
- Added: i18n keys for table headers, actions, summary

**Impact**:
- Agenda now uses DataState (no more manual if/else chains)
- Empty state shows icon + message + "Create New Appointment" button (no functionality yet)
- Loading state is centered and professional
- Error state uses alert-error class with clear messaging
- Pattern is fully documented in docs/UX_PATTERNS.md

**Verification**:
```bash
# Build succeeds
npm run build  # ✓ Compiled successfully

# Frontend renders correctly
curl http://localhost:3000/es | grep "Agenda"  # ✓ Found

# TypeScript errors: 0
# No errors in apps/web/src/app/[locale]/page.tsx
# No errors in apps/web/src/components/data-state.tsx
```

---

## 12.7. Empty State Strategy (FASE 2 - 2025-12-24)

**Decision**: All empty states must have clear user-friendly messaging and actionable CTAs.

**Context**:
- Technical users understand "No data found"
- Non-technical users need context and next steps
- Empty states are common in ERP (no appointments, no patients, no stock, etc.)
- Need consistent pattern across all modules

**Empty State Requirements**:

1. **Icon**: Visual indicator (📋 emoji, 48px, opacity 0.3)
2. **Message**: Clear, non-technical explanation
   - ❌ "No results"
   - ✅ "No appointments scheduled"
3. **Description** (optional): Additional context
   - "Date: December 24, 2025"
   - "Try adjusting your filters"
4. **CTA Button**: Always present, can be disabled
   - Label: "Create New [Resource]"
   - onClick: undefined if not implemented yet

**Examples**:
```tsx
// Agenda empty state
emptyMessage: "No appointments scheduled"
emptyDescription: `Date: ${dateFormatter.format(new Date(selectedDate))}`
emptyAction: { label: "Create New Appointment", onClick: undefined }

// Future: Patients empty state
emptyMessage: "No patients found"
emptyDescription: "Start by adding your first patient"
emptyAction: { label: "Add Patient", onClick: handleAddPatient }
```

**Rationale**:
- ✅ Users understand what's empty and why
- ✅ Users know what action to take next
- ✅ Reduces support requests ("Why is this page blank?")
- ✅ Consistent UX across all modules
- ✅ CTA can be disabled if feature not ready (no broken buttons)

**Impact**:
- Improved user experience for non-technical users
- Reduced confusion during initial setup/empty database
- Clear path forward for users

---

## 12.8. CSS Class Discipline (FASE 2 - 2025-12-24)

**Decision**: No new global CSS classes. Use existing classes from globals.css only.

**Context**:
- `apps/web/src/app/[locale]/globals.css` has 539 lines of comprehensive styles
- Classes exist for: buttons, cards, tables, badges, alerts, forms, utilities
- Risk of CSS bloat if every developer adds new classes
- Risk of inconsistent styling across modules

**Existing Class Categories**:
1. Layout: `.app-layout`, `.page-header`, `.card`, `.card-body`
2. Buttons: `.btn-primary`, `.btn-secondary`, `.btn-destructive`, `.btn-sm`
3. Tables: `.table`, `.table thead`, `.table th`, `.table td`
4. Badges: `.badge`, `.badge-{status}`
5. Alerts: `.alert-error`, `.alert-success`, `.alert-info`
6. Forms: `.form-group`, `.form-label`, `.form-error`
7. Utilities: `.flex`, `.gap-2`, `.items-center`, `.w-full`, etc.

**Rules**:
- ❌ DO NOT add new classes to globals.css
- ✅ DO use existing classes
- ✅ DO use inline styles if truly unique styling needed
- ✅ DO document any deviations in PR

**Rationale**:
- ✅ Prevents CSS bloat
- ✅ Enforces consistency
- ✅ Existing classes cover 95% of use cases
- ✅ Easier to maintain (one source of truth)

**Impact**:
- Agenda module uses ONLY existing classes
- All future modules follow same discipline
- CSS size remains stable (~539 lines)

---

## 12.9. Documentation Strategy (FASE 2 - 2025-12-24)

**Decision**: Create UX_PATTERNS.md as living documentation for module development.

**Context**:
- PROJECT_DECISIONS.md documents architectural decisions (why)
- Needed practical guide for developers (how)
- Copy-paste templates reduce errors and speed up development
- Consistency requires clear examples

**UX_PATTERNS.md Sections**:
1. Standard Page Structure (code template)
2. Data State Management (DataState usage)
3. Component Reusability (available components + hooks)
4. CSS Classes Reference (complete list from globals.css)
5. Real Example: Agenda Module (living reference)
6. What NOT to Do (anti-patterns with examples)

**Content Style**:
- Code examples (copy-pasteable)
- Side-by-side comparisons (❌ BAD vs ✅ GOOD)
- Real code from Agenda (not theoretical)
- Checklist for new modules

**Rationale**:
- ✅ Developers can copy Agenda structure directly
- ✅ Reduces onboarding time (don't need to read all code)
- ✅ Anti-patterns prevent common mistakes
- ✅ Checklist ensures nothing is forgotten
- ✅ Living document (updates as patterns evolve)

**Impact**:
- New modules can be built faster
- Consistency enforced through documentation
- Agenda changes automatically update reference
- Reduced code review time (pattern is pre-approved)

---

## 12.10. UI Localization Completion - FASE 2.5 (2025-12-24)

**Decision**: Complete all missing i18n keys for navigation and eliminate hardcoded strings in UI.

**Context**:
- After FASE 2 (UX patterns), UI showed raw i18n keys (nav.app.name, nav.nav.admin, etc.)
- "Language" label was hardcoded in English
- App name should be fixed brand name "Cosmetica 5" (not translated)
- User display showed email; better UX would show name (but backend only provides email)
- Logout button showed key instead of translated text
- Agenda had no data for visual verification of layout

**Problems Found (Screenshots)**:
1. ❌ `nav.app.name` visible in sidebar header
2. ❌ `nav.actions.logout` visible in logout button
3. ❌ `nav.nav.admin` malformed key (should be nav.admin)
4. ❌ `nav.proposals` missing translation
5. ❌ "Language" label not translated (hardcoded English)
6. ❌ Empty agenda prevented visual verification of table layout

**Solution**:

### A) i18n Keys Completion
Added/corrected keys in ALL locales (en, es, ru, fr, hy, uk):
```json
"nav": {
  "agenda": "Agenda / Расписание / ...",
  "patients": "...",
  "encounters": "...",
  "proposals": "Proposals / Propuestas / ...",
  "sales": "...",
  "admin": "Administration / Administración / ...",  // Fixed from nav.nav.admin
  "actions": {
    "logout": "Sign Out / Cerrar Sesión / Выйти / ..."
  }
},
"common": {
  "languageLabel": "Language / Idioma / Язык / ..."
}
```

### B) App Name as Constant
- Created `apps/web/src/lib/constants.ts`:
  ```ts
  export const APP_NAME = 'Cosmetica 5';  // Fixed, not translated
  ```
- Updated `app-layout.tsx` to use `APP_NAME` instead of `t('app.name')`

### C) Language Label Translation
- Updated `language-switcher.tsx` to use `t('languageLabel')` instead of hardcoded "Language"
- Verified translations in ES (Idioma), RU (Язык), FR (Langue), etc.

### D) User Display Strategy
- Backend `/api/auth/me/` returns: `{ id, email, is_active, roles }`
- NO first_name/last_name available
- Decision: Display `user.email` (no fabricated data)
- Future: If backend adds name fields, easy to update

### E) Navigation Keys Cleanup
- Fixed malformed key `nav.nav.admin` → `nav.admin`
- Removed non-existent `ROLES.CLINICAL_OPS` from permission checks
- Kept only existing roles: ADMIN, PRACTITIONER, RECEPTION, MARKETING, ACCOUNTING

### F) DEV-Only Mock Data
- Created `apps/web/src/lib/mock/agenda-mock.ts`
- Purpose: Visual verification of Agenda layout without real backend data
- Activation: Only when `NODE_ENV === 'development'` AND backend returns empty array
- Data: 5 mock appointments with varied statuses (scheduled, confirmed, checked_in, completed, cancelled)
- Clearly marked with ⚠️ TEMPORAL warnings
- Updated `page.tsx` to use mock when empty in dev

**Files Changed**:
1. ✅ `apps/web/messages/*.json` (6 locales) - Added nav keys
2. ✅ `apps/web/src/lib/constants.ts` (NEW) - APP_NAME constant
3. ✅ `apps/web/src/components/layout/app-layout.tsx` - Use APP_NAME, fix nav.admin
4. ✅ `apps/web/src/components/language-switcher.tsx` - Translate label
5. ✅ `apps/web/src/lib/mock/agenda-mock.ts` (NEW) - DEV mock data
6. ✅ `apps/web/src/app/[locale]/page.tsx` - Integrate mock data

**Verification**:
```bash
# Build succeeds
cd apps/web && npm run build  # ✓ Compiled successfully

# TypeScript errors: 0
# No errors in modified files

# Frontend loads correctly
docker restart emr-web
curl http://localhost:3000/es | grep "Cosmetica 5"  # ✓ Found
curl http://localhost:3000/es | grep "Idioma"  # ✓ Found (not "Language")
curl http://localhost:3000/ru | grep "Язык"   # ✓ Found

# Visual verification in browser:
# - Sidebar header: "Cosmetica 5" (not nav.app.name)
# - Language label: "Idioma" in ES, "Язык" in RU (translated)
# - Logout button: "Cerrar Sesión" in ES (not nav.actions.logout)
# - Agenda: Shows 5 mock appointments with proper layout
# - No raw i18n keys visible in ES, RU, FR, HY, UK
```

**Rationale**:
- ✅ Professional UI: No developer keys visible to end users
- ✅ Consistent translations: All 6 locales have same structure
- ✅ Brand identity: "Cosmetica 5" is fixed name (like "Slack" or "Stripe")
- ✅ No data fabrication: Display what backend provides (email)
- ✅ DEV workflow: Mock allows visual verification without seeding database
- ✅ Production safe: Mock code is DEV-only (process.env.NODE_ENV check)

**Cleanup Strategy**:
- Mock data is isolated in `agenda-mock.ts`
- Marked as ⚠️ TEMPORAL with clear removal instructions
- When backend provides real data, simply delete `agenda-mock.ts` and remove import from `page.tsx`
- No contamination of production builds (NODE_ENV check prevents activation)

**Impact**:
- UI is now production-ready in all supported languages
- No "dev smell" (raw keys) visible to users
- Mock data allows designers/PMs to review layout without backend setup
- Clear path to remove mock when no longer needed

---

## 12.11. FASE 2.5 Cleanup Summary (2025-12-24)

**What Was Cleaned**:
1. ✅ All malformed nav keys (nav.nav.* → nav.*)
2. ✅ Removed non-existent ROLES.CLINICAL_OPS from RBAC checks
3. ✅ Eliminated hardcoded "Language" string
4. ✅ Removed hardcoded nav.app.name key usage

**What Is Temporary (DEV-Only)**:
1. 🔶 `apps/web/src/lib/mock/agenda-mock.ts` - Mock appointment data
   - When to remove: When backend provides real appointments
   - How to remove: Delete file, remove import from page.tsx
   - Safe to keep: Only activates in NODE_ENV=development

**What Is Production-Ready**:
- All i18n translations (6 locales)
- APP_NAME constant (brand identity)
- Language switcher with translated labels
- Sidebar navigation with correct permissions
- DataState component (FASE 2)
- UX_PATTERNS.md documentation (FASE 2)

**Verification Checklist**:
- ✅ No raw i18n keys in UI (tested ES, RU, FR)
- ✅ "Cosmetica 5" shows in sidebar header
- ✅ Language label translates correctly
- ✅ Logout button shows translated text
- ✅ Build compiles successfully (0 TS errors)
- ✅ Frontend loads without console errors
- ✅ Agenda shows mock data in development
- ✅ Mock does not activate in production

**Next Steps**:
1. User acceptance testing in all locales
2. Backend: Add name fields to UserProfile if desired
3. Backend: Provide real appointment data (remove mock)
4. Apply i18n pattern to other modules (Patients, Proposals, Sales)

---

## 12.12. Backend User Identity Model - Tech Debt (Phase 3.0 - 2025-12-24)

**Current Situation**: UI only displays email for user identity, no human-friendly name available.

### Backend Current State

**Endpoint**: `GET /api/auth/me/`  
**Serializer**: `UserProfileSerializer` (apps/api/apps/core/serializers.py)  
**Fields Returned**:
```python
{
  "id": "uuid",
  "email": "user@example.com",
  "is_active": true,
  "roles": ["admin", "practitioner", ...]
}
```

**What's Missing**:
- ❌ No `first_name` / `last_name`
- ❌ No `display_name` / `full_name`
- ❌ No `username` alternative
- ❌ No user preferences (timezone, language, avatar)

### UX Impact

**Problem**: Header displays "yo@ejemplo.com" instead of "Dr. García" or "María López"
- ❌ Not user-friendly (technical identifier visible)
- ❌ Poor audit trail (emails are not unique identifiers in legal contexts)
- ❌ GDPR concerns (email is PII, unnecessarily exposed in UI header)
- ❌ Internationalization issues (no localized name formatting)

**Current Workaround** (Phase 3.0):
```tsx
// apps/web/src/components/layout/app-layout.tsx
const getUserLabel = (user: { email: string }): string => {
  return user.email || tCommon('user');  // Fallback to translated "User"
};
```

### Proposed Backend Enhancement (Not Implemented)

**Goal**: Add human-friendly identity fields to UserProfile without breaking existing clients.

#### Phase 1: Schema Evolution (Backend)

**1. Update Django User Model** (apps/api/apps/authz/models.py or custom User):
```python
class User(AbstractBaseUser):
    # Existing
    email = EmailField(unique=True)
    
    # NEW - Add with defaults for backward compatibility
    first_name = CharField(max_length=50, blank=True, default='')
    last_name = CharField(max_length=50, blank=True, default='')
    
    @property
    def display_name(self) -> str:
        """
        Get user-friendly display name with fallback strategy.
        Priority: full_name → email username → email
        """
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        if self.first_name:
            return self.first_name
        if self.last_name:
            return self.last_name
        # Fallback: extract username from email
        return self.email.split('@')[0]
    
    @property
    def full_name(self) -> str:
        """Get full name or email as fallback."""
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.email
```

**2. Database Migration**:
```bash
# Create migration with defaults (no data loss)
python manage.py makemigrations authz --name add_user_names
python manage.py migrate authz

# Optional: Backfill names from existing data
# UPDATE users SET first_name = ... WHERE ...
```

**3. Update Serializer** (apps/api/apps/core/serializers.py):
```python
class UserProfileSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    roles = serializers.ListField(child=serializers.CharField(), read_only=True)
    
    # NEW - Add with source to use model property
    display_name = serializers.CharField(read_only=True)
    full_name = serializers.CharField(read_only=True)
```

**4. Update View** (apps/api/apps/core/views.py):
```python
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    user = request.user
    data = {
        'id': str(user.id),
        'email': user.email,
        'is_active': user.is_active,
        'roles': get_user_roles(user),
        'display_name': user.display_name,  # NEW
        'full_name': user.full_name,        # NEW
    }
    serializer = UserProfileSerializer(data)
    return Response(serializer.data)
```

#### Phase 2: Frontend Adaptation (Automatic)

**Frontend already prepared** (Phase 3.0):
```tsx
const getUserLabel = (user: { 
  email: string;
  display_name?: string;  // Will be used when available
  full_name?: string;     // Alternative
}): string => {
  // Priority order (no changes needed when backend is ready):
  return user.display_name || user.full_name || user.email || tCommon('user');
};
```

**TypeScript Type Update** (apps/web/src/lib/auth-context.tsx):
```tsx
export interface User {
  id: string;
  email: string;
  is_active: boolean;
  roles: string[];
  display_name?: string;  // NEW - optional for backward compatibility
  full_name?: string;     // NEW - optional
}
```

### Migration Strategy

**Compatibility Strategy**: Additive, non-breaking
1. ✅ New fields are optional (nullable/default)
2. ✅ Frontend uses fallback chain (display_name → email)
3. ✅ Old clients (mobile, scripts) won't break (ignore new fields)
4. ✅ New clients benefit immediately when backend updated

**Rollout Steps**:
1. Backend: Add fields with migrations (no downtime)
2. Backend: Deploy new serializer (backward compatible)
3. Frontend: Already prepared (getUserLabel handles optional fields)
4. Admin: Populate names via Django Admin or import script
5. Users: Can update their own names via future profile page

**Rollback Safety**:
- Backend can remove fields (frontend falls back to email)
- No data corruption risk (fields are optional)
- TypeScript errors caught at compile time

### GDPR & Legal Considerations

**Current (Problematic)**:
- ❌ Email (PII) exposed in every UI header
- ❌ Email in browser localStorage (XSS risk)
- ❌ Email in logs/metrics (GDPR Article 5)

**Proposed (Better)**:
- ✅ Display name (non-PII) in UI header
- ✅ Email only in profile page / admin panel
- ✅ Pseudonymization option: use `user_${id}` instead of email
- ✅ Audit logs reference user.id (UUID), not email

**GDPR Compliance Notes**:
- Names are PII but less sensitive than email
- Users should consent to name display (ToS / onboarding)
- Admin panel should allow "Delete Account" (right to erasure)
- Consider "display_name" as user-chosen pseudonym option

### Risks & Mitigation

**Risk 1: Name Collisions**
- Problem: Multiple "Dr. García" in dropdown selectors
- Mitigation: Show `{display_name} ({email})` in disambiguation contexts

**Risk 2: Empty Names**
- Problem: User doesn't provide name, header shows "yo@ejemplo.com"
- Mitigation: Onboarding flow requests name (optional but encouraged)

**Risk 3: Unicode / RTL Names**
- Problem: Names like "محمد" or "Владимир" may render poorly
- Mitigation: Ensure UTF-8 everywhere, test with diverse locales

**Risk 4: Breaking Changes**
- Problem: Old mobile app expects only 4 fields
- Mitigation: New fields are optional, old clients ignore them

### Acceptance Criteria

**Backend Ready When**:
- ✅ UserProfile returns `display_name` and `full_name`
- ✅ Fields are optional (null/empty allowed)
- ✅ Migration tested on staging with 10k+ users
- ✅ API docs updated (Swagger / DRF browsable API)

**Frontend Ready When** (Already Done):
- ✅ getUserLabel() uses display_name if available
- ✅ Falls back to email gracefully
- ✅ TypeScript types allow optional fields
- ✅ No errors if backend doesn't send new fields

**UX Verified When**:
- ✅ Header shows "Dr. García" instead of "garcia@example.com"
- ✅ Audit logs reference "Dr. García performed action X"
- ✅ Users can update their name in profile page (future)

### Timeline & Priorities

**Priority**: P1 (High) - Significant UX improvement, GDPR compliance

**Estimated Effort**:
- Backend: 4-6 hours (model, migration, serializer, tests)
- Frontend: 1 hour (type update, already implemented)
- Testing: 2 hours (e2e, migration testing)
- Total: ~8 hours (1 developer-day)

**Dependencies**:
- None (can be done independently)
- Nice-to-have: Profile edit page (separate ticket)

**Blocking Issues**:
- None - frontend already prepared for this change

### Decision Record

**Date**: 2025-12-24  
**Decided By**: Tech Lead  
**Status**: Approved for backend implementation (not yet scheduled)

**Rationale**:
- ✅ Improves UX significantly
- ✅ GDPR compliance improvement
- ✅ Low risk (additive change, backward compatible)
- ✅ Frontend already prepared (Phase 3.0)
- ✅ Aligns with industry best practices (all modern apps show names)

**Alternatives Considered**:
1. ❌ Keep email forever: Bad UX, GDPR concerns
2. ❌ Generate random usernames: Confusing for users
3. ❌ Use first name only: Ambiguous in large organizations
4. ✅ **Chosen**: display_name property with fallback chain

**No Hacks Policy**:
- ❌ Frontend will NOT fake names from email (e.g., "garcia@" → "Garcia")
- ❌ Frontend will NOT use localStorage to store custom names
- ❌ Frontend will NOT parse email to extract names
- ✅ Frontend will ONLY use what backend provides

**Next Action**: Create backend ticket "Add display_name to UserProfile"

---

## 12.13. Empty State vs Error State - UX Semantics (Phase 3.1 - 2025-12-24)

**Context**: Frontend debe diferenciar claramente entre "no hay datos" (EMPTY) y "error de sistema" (ERROR).

### The Problem

**Anti-pattern observado en muchos sistemas**:
```tsx
// ❌ WRONG: Backend devuelve 200 + [] pero UI muestra "Error al cargar"
if (data.length === 0) {
  return <ErrorBanner>Error al cargar citas</ErrorBanner>;
}
```

**Consecuencias**:
- Usuario piensa que el sistema está roto (cuando simplemente no hay datos)
- Confusión: ¿es un fallo técnico o ausencia legítima de datos?
- Copy técnico ("Failed to load") no es útil para usuario final
- No hay guía sobre qué hacer (crear dato, cambiar filtros, etc.)

### Decision: EMPTY ≠ ERROR

**Principio UX**:
> Una lista vacía devuelta exitosamente por el backend (HTTP 200 + `[]`) NO es un error de sistema.

**Implementación en DataState**:
```tsx
// ✅ CORRECT: Separar semánticamente empty vs error
<DataState
  isLoading={isLoading}
  error={error}           // Solo cuando HTTP >= 400 o excepción
  isEmpty={data.length === 0}  // Cuando HTTP 200 + []
  emptyMessage="No hay citas para este día"
  errorTitle="No se pudo cargar la agenda"
/>
```

### Behavior Matrix

| Condición Backend | Estado Frontend | Componente Mostrado | Copy UX |
|-------------------|-----------------|---------------------|---------|
| `isLoading=true` | Loading | LoadingState | "Cargando..." |
| `HTTP 200 + []` | Success + Empty | EmptyState | "No hay citas para este día" |
| `HTTP 200 + [...]` | Success | SuccessState (children) | N/A (se muestra la tabla) |
| `HTTP >= 400` | Error | ErrorState | "No se pudo cargar la agenda" |
| `Network error` | Error | ErrorState | "Problemas de conexión" |
| `Exception` | Error | ErrorState | "Error del sistema" |

**Regla clave**:
```typescript
// Si backend responde exitosamente, NO es error (aunque esté vacío)
const isEmpty = !error && !isLoading && data?.results?.length === 0;
```

### UX Copy Guidelines

**EMPTY STATE** (200 + []):
- ✅ Título claro: "No hay citas para este día"
- ✅ Descripción contextual: "No hay citas programadas para la fecha seleccionada"
- ✅ CTA orientado a acción: "Crear Nueva Cita"
- ✅ Tono neutral (no alarmante)
- ❌ Evitar: "Error", "Failed", "No se pudo"

**ERROR STATE** (HTTP >= 400 | Exception):
- ✅ Título claro: "No se pudo cargar la agenda"
- ✅ Descripción útil: "Problemas de conexión. Verifica tu internet e intenta nuevamente"
- ✅ Guía de solución: qué puede hacer el usuario
- ✅ Tono calmado (no técnico)
- ❌ Evitar: "HTTP 500", "Failed to fetch", stack traces

**Ejemplos reales** (Agenda):
```json
// ES
"emptyState": {
  "title": "No hay citas para este día",
  "description": "No hay citas programadas para la fecha seleccionada...",
  "action": "Crear Nueva Cita"
},
"errors": {
  "title": "No se pudo cargar la agenda",
  "description": "Problemas de conexión. Verifica tu internet..."
}

// EN
"emptyState": {
  "title": "No appointments for this day",
  "description": "There are no scheduled appointments...",
  "action": "Create New Appointment"
},
"errors": {
  "title": "Unable to load agenda",
  "description": "We're having trouble connecting to the server..."
}
```

### Implementation Details

**DataState Component** ([data-state.tsx](../apps/web/src/components/data-state.tsx)):
```tsx
interface DataStateProps {
  isLoading: boolean;
  error?: Error | null;
  isEmpty?: boolean;
  emptyMessage?: string;      // → "No hay citas para este día"
  emptyDescription?: string;  // → "No hay citas programadas..."
  emptyAction?: EmptyAction;  // → "Crear Nueva Cita"
  errorTitle?: string;        // → "No se pudo cargar la agenda"
  errorDescription?: string;  // → "Problemas de conexión..."
}

// Orden de evaluación:
// 1. isLoading → LoadingState
// 2. error → ErrorState (con errorTitle + errorDescription)
// 3. isEmpty → EmptyState (con emptyMessage + emptyDescription)
// 4. default → SuccessState (render children)
```

**Agenda Page** ([page.tsx](../apps/web/src/app/[locale]/page.tsx)):
```tsx
const { data, isLoading, error } = useAppointments({ date, status });
const appointments = data?.results || [];
const isEmpty = appointments.length === 0;

<DataState
  isLoading={isLoading}
  error={error}                          // Solo cuando falla el fetch
  isEmpty={isEmpty}                      // 200 + [] → empty, NO error
  emptyMessage={t('emptyState.title')}
  emptyDescription={t('emptyState.description')}
  errorTitle={t('errors.title')}
  errorDescription={t('errors.description')}
>
  {/* Tabla de citas (solo se muestra en success state) */}
</DataState>
```

### Why This Matters

**Impacto en UX**:
- ✅ Usuario entiende claramente la situación
- ✅ Sabe qué hacer (crear cita vs reportar error)
- ✅ No se alarma innecesariamente
- ✅ Copy profesional y orientado a acción

**Impacto en soporte**:
- ✅ Menos tickets de "el sistema no funciona" (cuando solo estaba vacío)
- ✅ Reportes de error más precisos (solo errores reales)
- ✅ Usuarios saben cuándo contactar soporte (solo en error real)

**Impacto en desarrollo**:
- ✅ Patrón reutilizable (DataState en todos los módulos)
- ✅ Copy i18n bien estructurado (emptyState vs errors)
- ✅ Testing más claro (estados distintos = tests distintos)

### Tech Debt

**Current Limitations**:
- Empty state action (`onClick`) actualmente es `undefined` (placeholder)
- Falta implementar flujo de "Crear Nueva Cita"
- Falta backend mutation para crear appointment

**Future Work** (P2):
1. Implementar modal "Crear Cita" (frontend)
2. Conectar con backend mutation `POST /api/clinical/appointments/`
3. Actualizar `emptyAction.onClick` para abrir modal
4. Invalidar query cache después de crear cita

### Acceptance Criteria

✅ Backend devuelve `200 + []` → UI muestra EmptyState (NO ErrorState)  
✅ Backend devuelve `400/500` → UI muestra ErrorState  
✅ EmptyState tiene copy UX-friendly en 6 idiomas (EN, ES, FR, RU, UK, HY)  
✅ ErrorState tiene copy UX-friendly sin jerga técnica  
✅ DataState component es reutilizable en otros módulos  
✅ TypeScript 0 errores  
✅ Build exitoso  

**Decision Record**:
- **Date**: 2025-12-24
- **Phase**: 3.1
- **Status**: ✅ IMPLEMENTED
- **Pattern**: DataState con separación semántica EMPTY ≠ ERROR
- **Applies to**: Todos los módulos del ERP (Agenda, Patients, Encounters, etc.)

---
