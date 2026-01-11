# Container Startup Fix - Verification Summary

**Date:** 2025-12-24  
**Issue:** `emr-api` container crash on `collectstatic`  
**Status:** ✅ RESOLVED

---

## Problem Statement

Container failed to start with:
```
PermissionError: [Errno 13] Permission denied: '/app/staticfiles/admin'
```

Container entered infinite restart loop (restart policy: `unless-stopped`).

---

## Root Cause

1. **Dockerfile:** Switched to non-root user (`django:django`) before creating `/app/staticfiles`
2. **Runtime:** `collectstatic` command tried to create directories but lacked permissions
3. **Result:** Container startup failed, restarted infinitely

---

## Solution Implemented

### 1. Dockerfile Fix ([apps/api/Dockerfile](apps/api/Dockerfile))

**Before:**
```dockerfile
RUN useradd -m -u 1000 django && \
    chown -R django:django /app

USER django
```

**After:**
```dockerfile
RUN useradd -m -u 1000 django && \
    mkdir -p /app/staticfiles /app/media && \
    chown -R django:django /app

USER django
```

**Impact:** Directories created with proper ownership BEFORE switching to non-root user.

### 2. Environment Variable Gating ([docker-compose.yml](docker-compose.yml))

Added conditional collectstatic:
```yaml
command: >
  sh -c "
  python manage.py migrate --noinput &&
  if [ \"$DJANGO_COLLECTSTATIC\" != \"0\" ]; then python manage.py collectstatic --noinput; fi &&
  python manage.py ensure_superuser &&
  gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4 --timeout 120 --access-logfile - --error-logfile -
  "
```

Added environment variable:
```yaml
environment:
  DJANGO_COLLECTSTATIC: ${DJANGO_COLLECTSTATIC:-1}  # 1=enabled (default), 0=skip
```

**Impact:** Can disable collectstatic for faster dev startup if needed.

### 3. Path Fixes ([docker-compose.yml](docker-compose.yml))

Fixed all build contexts and volume mounts from `../apps/*` to `./apps/*` (root docker-compose.yml is in project root, not infra/).

**Impact:** Correct paths for building images from root directory.

### 4. Bonus Fix ([ensure_superuser.py](apps/api/apps/core/management/commands/ensure_superuser.py))

Fixed User model field reference:
- **Before:** `User.objects.filter(username=username)`
- **After:** `User.objects.filter(email=email)`

**Impact:** Custom user model uses `email` as `USERNAME_FIELD`, not `username`.

---

## Validation Results

### ✅ Container Status
```
NAMES         STATUS
emr-api       Up (healthy)
emr-postgres  Up (healthy)
emr-redis     Up (healthy)
emr-minio     Up (healthy)
```

### ✅ Logs Verification
```bash
$ docker logs emr-api | grep -E "collectstatic|Superuser|Listening"
172 static files copied to '/app/staticfiles'.
0 static files copied to '/app/staticfiles', 172 unmodified.
Superuser "admin@example.com" created successfully
[2025-12-24 15:07:12 +0000] [10] [INFO] Listening at: http://0.0.0.0:8000 (10)
[2025-12-24 15:07:12 +0000] [11] [INFO] Booting worker with pid: 11
[2025-12-24 15:07:12 +0000] [12] [INFO] Booting worker with pid: 12
[2025-12-24 15:07:12 +0000] [13] [INFO] Booting worker with pid: 13
[2025-12-24 15:07:12 +0000] [14] [INFO] Booting worker with pid: 14
```

### ✅ API Health Check
```bash
$ curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/admin/
302  # Redirect to login (expected - admin is protected)
```

### ✅ No Permission Errors
```bash
$ docker logs emr-api 2>&1 | grep -i "PermissionError"
# (no output = no permission errors)
```

---

## Files Changed

| File | Change | Lines |
|------|--------|-------|
| [apps/api/Dockerfile](apps/api/Dockerfile) | Add `mkdir -p /app/staticfiles /app/media` | 1 line |
| [docker-compose.yml](docker-compose.yml) | Add DJANGO_COLLECTSTATIC env var + conditional | 4 lines |
| [docker-compose.yml](docker-compose.yml) | Fix paths: `../apps/*` → `./apps/*` | 4 lines |
| [apps/api/apps/core/management/commands/ensure_superuser.py](apps/api/apps/core/management/commands/ensure_superuser.py) | Fix User field: `username` → `email` | 5 lines |
| [docs/PROJECT_DECISIONS.md](docs/PROJECT_DECISIONS.md) | Add Section 12: Infrastructure & DevOps | +150 lines |
| [INFRA_API_STARTUP_FIX.md](INFRA_API_STARTUP_FIX.md) | New documentation file (detailed guide) | +250 lines |

---

## Testing Steps (Reproducible)

```bash
# 1. Stop all containers
docker-compose down

# 2. Rebuild API image (applies Dockerfile fix)
docker-compose build api

# 3. Start infrastructure
docker-compose up -d postgres redis minio

# 4. Wait for health checks
sleep 10

# 5. Start API
docker-compose up -d api

# 6. Verify startup (wait 10s for container startup)
sleep 10
docker ps | grep emr-api
# Expected: STATUS = Up (healthy)

# 7. Check logs for errors
docker logs emr-api | grep -E "PermissionError|collectstatic|Superuser"
# Expected: 
# - "172 static files copied to '/app/staticfiles'."
# - "Superuser 'admin@example.com' created successfully"
# - NO "PermissionError"

# 8. Test API
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/admin/
# Expected: 302 (redirect to login)
```

---

## Production Considerations

### Static Files Strategy

**DEV (Volume Mount):**
- `/app/staticfiles` created on host (via volume)
- Persists across container restarts
- `collectstatic` runs on each startup (idempotent)

**PROD (No Volume):**
- `/app/staticfiles` baked into image
- Use nginx to serve static files (recommended)
- OR use S3/MinIO for static files
- OR add persistent volume for staticfiles

### Escape Hatch (Dev Only)

Skip collectstatic for faster startup:
```bash
DJANGO_COLLECTSTATIC=0 docker-compose up -d api
```

Use case: Rapid iteration, static files not needed immediately.

---

## Lessons Learned

1. **Non-Root Security:** Always pre-create writable directories BEFORE switching to non-root user
2. **Build vs Runtime:** Don't rely on runtime commands to create essential directories
3. **Volume Mounts:** Dev volume mounts can mask missing directories - test without volumes in CI
4. **Conditional Execution:** Provide env var gates for non-critical startup tasks
5. **Custom User Models:** Django's `USERNAME_FIELD` can be overridden - check model before using `username`

---

## Related Documentation

- [INFRA_API_STARTUP_FIX.md](INFRA_API_STARTUP_FIX.md) - Detailed implementation guide
- [docs/PROJECT_DECISIONS.md](docs/PROJECT_DECISIONS.md) - Section 12: Infrastructure & DevOps
- [apps/api/Dockerfile](apps/api/Dockerfile) - Container definition
- [docker-compose.yml](docker-compose.yml) - Service orchestration
- [QUICKSTART.md](QUICKSTART.md) - Getting started guide

---

## Author

- **Implementation:** GitHub Copilot (Claude Sonnet 4.5)
- **Date:** 2025-12-24
- **Context:** Blocked development workflow - container startup failure
- **Time to Resolution:** ~15 minutes (diagnosis → fix → validation → documentation)

---

## Status: ✅ COMPLETE

Container startup is now robust:
- ✅ No permission errors
- ✅ Collectstatic succeeds
- ✅ Superuser created automatically
- ✅ Gunicorn starts successfully
- ✅ Health checks pass
- ✅ API responds to requests
- ✅ Full documentation provided
- ✅ Production-safe (with considerations documented)
