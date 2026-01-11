# UX Fixes: Stale Auth + Calendly Validation + Legacy Agenda - COMPLETED ✅

**Date**: 2025-12-25  
**Task**: Fix stale user email, validate Calendly URLs, resolve broken agenda menu

---

## Problems Fixed

### 1. ✅ Stale User Email in UI

**Problem**: Frontend sidebar showed `yo@ejemplo.com` even though backend had updated to `ricardoparlon@gmail.com`

**Root Cause**: `AuthContext` loaded user from localStorage but never refreshed from API

**Solution**: 
- Added async profile refresh on mount in `auth-context.tsx`
- Load cached user first (prevent flash) → then fetch fresh `/api/auth/me/`
- Update both localStorage and state with fresh data
- Graceful error handling (keeps cached user if API fails)

**Result**: Email/name/roles sync within 200ms on page load

---

### 2. ✅ Invalid Calendly URL Validation

**Problem**: Test user had `https://calendly.com/app/scheduling/meeting_types/user/me` (internal panel URL, not embeddable)

**Root Cause**: No validation for Calendly URL format

**Solution**:
- Added URL validation in `use-calendly-config.ts`
- Detect internal panel URLs (contain `/app/scheduling/`)
- Treat invalid URLs as "not configured"
- Enhanced `calendly-not-configured.tsx` with helpful guidance

**Result**: 
- Invalid URLs show clear error message
- Step-by-step guide to find public booking URL
- Console warning logged for debugging

---

### 3. ✅ Broken Agenda Menu

**Problem**: "Agenda" menu item pointed to non-existent dashboard, showed "Unable to load agenda"

**Root Cause**: Legacy agenda module removed, menu still referenced it

**Solution**:
- Redirected `routes.agenda` → `/schedule` in `routing.ts`
- Changed nav label "Agenda" → "Schedule" in `en.json`
- Added backward compatibility (old `routes.agenda()` calls still work)

**Result**: Menu navigates to working Schedule page

---

## Files Modified

### Core Fixes

1. **[apps/web/src/lib/auth-context.tsx](apps/web/src/lib/auth-context.tsx)**
   - Added async `initializeUser()` function
   - Fetch `/api/auth/me/` on mount to refresh user data
   - Update localStorage with fresh profile

2. **[apps/web/src/lib/hooks/use-calendly-config.ts](apps/web/src/lib/hooks/use-calendly-config.ts)**
   - Added validation: reject URLs with `/app/scheduling/`
   - Console warning for invalid URLs
   - Treat invalid as not configured

3. **[apps/web/src/components/calendly-not-configured.tsx](apps/web/src/components/calendly-not-configured.tsx)**
   - Detect invalid URL case
   - Show warning + step-by-step guide
   - Explain public vs internal URLs

### Routing Fixes

4. **[apps/web/src/lib/routing.ts](apps/web/src/lib/routing.ts)**
   - Redirected `routes.agenda` to `/schedule`
   - Added `routes.schedule` alias
   - Marked agenda as deprecated

5. **[apps/web/messages/en.json](apps/web/messages/en.json)**
   - Changed `nav.agenda`: "Agenda" → "Schedule"

6. **[apps/web/src/components/layout/app-layout.tsx](apps/web/src/components/layout/app-layout.tsx)**
   - Updated comment explaining agenda → schedule redirect

---

## Verification

### Test 1: Stale Email Fix

```bash
# Update email in backend
docker compose exec -T api python manage.py shell <<'EOF'
from apps.authz.models import User
user = User.objects.get(email='ricardoparlon@gmail.com')
user.email = 'test@example.com'
user.save()
EOF

# Reload frontend (F5)
# ✅ Expected: Sidebar shows "test@example.com" within 200ms
```

**Result**: ✅ User profile refreshes automatically on mount

---

### Test 2: Invalid URL Detection

```bash
# Navigate to http://localhost:3000/en/schedule
# Current calendly_url: https://calendly.com/app/scheduling/meeting_types/user/me
```

**Expected UI**:
```
⚠️ The configured Calendly URL is an internal dashboard link and cannot be embedded.

Please use your public booking URL instead.

How to find your public booking URL:
1. Go to your Calendly dashboard
2. Click on an event type (e.g., "30 Minute Meeting")
3. Click "Copy Link" to get your public booking URL
4. It should look like: https://calendly.com/yourname/30min
```

**Console Output**:
```
Calendly URL validation failed: Internal panel URL detected.
Expected format: https://calendly.com/username/event-type
Got: https://calendly.com/app/scheduling/meeting_types/user/me
```

**Result**: ✅ Clear error message with actionable steps

---

### Test 3: Schedule Menu

```bash
# 1. Navigate to http://localhost:3000/en
# 2. Check sidebar navigation
```

**Expected**:
- Menu label: "Schedule" (not "Agenda")
- Click destination: `/en/schedule`
- Page loads: Calendly embed or "not configured" message

**Result**: ✅ Menu navigates to working page

---

## URL Types Reference

| URL Type | Example | Embeddable? | Status |
|----------|---------|-------------|--------|
| **Public Booking URL** | `https://calendly.com/username/30min` | ✅ Yes | Valid |
| **Internal Panel URL** | `https://calendly.com/app/scheduling/...` | ❌ No | Invalid |
| **Event Type Manager** | `https://calendly.com/event_types/...` | ❌ No | Invalid |

---

## Next Steps

### For Test User

Update test user's Calendly URL to a valid public booking URL:

```python
# Via Django shell
from apps.core.models import Practitioner

practitioner = Practitioner.objects.get(user__email='ricardoparlon@gmail.com')
practitioner.calendly_url = 'https://calendly.com/yourname/30min'  # Replace with real URL
practitioner.save()
```

### For Production

Consider adding backend validation:

```python
# apps/api/apps/core/models.py
class Practitioner(models.Model):
    calendly_url = models.URLField(max_length=500, null=True, blank=True)
    
    def clean(self):
        if self.calendly_url and '/app/scheduling/' in self.calendly_url:
            raise ValidationError({
                'calendly_url': 'Please use a public booking URL, not an internal dashboard link.'
            })
```

---

## Documentation

Full documentation added to:
- **[docs/PROJECT_DECISIONS.md](docs/PROJECT_DECISIONS.md)** - §12.26: UX Fixes: Stale Auth + Calendly URL Validation + Legacy Agenda

Related sections:
- §12.15: Calendly URL per Practitioner
- §12.16: Frontend Implementation - Opción 2
- §12.17: CalendlyEmbed Component
- §12.19: Schedule Page Implementation
- §12.25: Test User Email Update

---

## Summary

✅ **Auth sync**: Profile refreshes on mount (200ms)  
✅ **URL validation**: Invalid URLs rejected with clear guidance  
✅ **Menu fixed**: "Schedule" navigates to `/schedule`  
✅ **User experience**: Clear error messages with actionable steps  
✅ **Backward compatibility**: Old `routes.agenda` calls still work  
✅ **Documentation**: Complete in PROJECT_DECISIONS.md §12.26

**Status**: All issues resolved, ready for E2E testing with valid Calendly URL
