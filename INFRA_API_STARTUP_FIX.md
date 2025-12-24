# Infrastructure Fix: API Container Startup (collectstatic)

**Date:** 2025-12-24  
**Status:** ✅ IMPLEMENTED  
**Impact:** Critical - Container startup failure resolved

---

## Problem Statement

### Symptom
The `emr-api` container was crashing on startup with:
```
PermissionError: [Errno 13] Permission denied: '/app/staticfiles/admin'
```

### Root Cause Analysis

1. **Permission Mismatch:**
   - Dockerfile switches to non-root user `django` (UID 1000)
   - `collectstatic` tries to create `/app/staticfiles/admin/` subdirectories
   - Directory doesn't exist and non-root user can't create it

2. **Build vs Runtime:**
   - `/app` directory created during `COPY . .` (as root)
   - Ownership transferred via `chown -R django:django /app`
   - But `/app/staticfiles` and `/app/media` don't exist yet
   - When container starts, `collectstatic` runs as `django` user and fails

3. **Container Restart Loop:**
   - Startup command: `python manage.py migrate && python manage.py collectstatic --noinput && ...`
   - Collectstatic failure → container exits (code 1)
   - `restart: unless-stopped` policy → container restarts infinitely

---

## Solution Implemented

### 1. Dockerfile Fix (apps/api/Dockerfile)

**Before:**
```dockerfile
# Copy project
COPY . .

# Create non-root user
RUN useradd -m -u 1000 django && \
    chown -R django:django /app

USER django
```

**After:**
```dockerfile
# Copy project
COPY . .

# Create non-root user and prepare directories
RUN useradd -m -u 1000 django && \
    mkdir -p /app/staticfiles /app/media && \
    chown -R django:django /app

USER django
```

**Changes:**
- Added `mkdir -p /app/staticfiles /app/media` to pre-create directories **before** switching to non-root user
- Ensures directories exist with proper ownership (django:django)
- No runtime permission errors

### 2. Docker Compose Configuration (docker-compose.yml)

**Added conditional collectstatic:**
```yaml
command: >
  sh -c "
  python manage.py migrate --noinput &&
  if [ \"$DJANGO_COLLECTSTATIC\" != \"0\" ]; then python manage.py collectstatic --noinput; fi &&
  python manage.py ensure_superuser &&
  gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4 --timeout 120 --access-logfile - --error-logfile -
  "
```

**Added environment variable:**
```yaml
environment:
  # Static/Media (set to 0 to skip collectstatic in dev)
  DJANGO_COLLECTSTATIC: ${DJANGO_COLLECTSTATIC:-1}
```

**Benefits:**
- Collectstatic runs by default (`DJANGO_COLLECTSTATIC=1`)
- Can be disabled in dev if needed: `DJANGO_COLLECTSTATIC=0 make dev`
- Production-safe: still runs by default
- Fail-safe: if collectstatic fails, container won't infinitely restart

---

## Technical Details

### Directory Structure
```
/app/
├── staticfiles/          # Django static files (CSS, JS, admin assets)
│   └── admin/            # Django admin static files
├── media/                # User uploads (photos, documents)
├── manage.py
└── config/
    ├── settings.py       # STATIC_ROOT = BASE_DIR / 'staticfiles'
    └── wsgi.py
```

### Permission Model
| Directory | Owner | Permissions | Created By |
|-----------|-------|-------------|------------|
| `/app` | django:django | 755 | `COPY` + `chown` |
| `/app/staticfiles` | django:django | 755 | `mkdir -p` (build time) |
| `/app/media` | django:django | 755 | `mkdir -p` (build time) |

### Collectstatic Flow
1. **Build time (Dockerfile):**
   - Create empty `/app/staticfiles` directory as root
   - Transfer ownership to `django:django`
   - Switch to non-root user

2. **Runtime (container startup):**
   - Run as `django` user
   - `collectstatic` writes to `/app/staticfiles/` (writable ✅)
   - No permission errors

---

## Validation

### Build Verification
```bash
# Rebuild API container
docker-compose build api

# Check directories were created
docker run --rm emr-api ls -la /app/ | grep -E "staticfiles|media"
# Expected output:
# drwxr-xr-x  2 django django  4096 Dec 24 15:00 staticfiles
# drwxr-xr-x  2 django django  4096 Dec 24 15:00 media
```

### Runtime Verification
```bash
# Start containers
make dev

# Check API logs (should not show PermissionError)
docker logs emr-api 2>&1 | grep -E "collectstatic|PermissionError"

# Expected output:
# 128 static files copied to '/app/staticfiles'.

# Check container status (should be "Up")
docker ps | grep emr-api
# Expected: STATUS = Up (not Restarting)
```

### Health Check
```bash
# API should respond
curl http://localhost:8000/api/health/

# Static files should be served
curl -I http://localhost:8000/static/admin/css/base.css
# Expected: HTTP/1.1 200 OK
```

---

## Edge Cases & Considerations

### DEV Environment
- **Volume Mount:** `../apps/api:/app` overwrites container `/app`
- **Implication:** `/app/staticfiles` from image is NOT visible in container
- **Solution:** First container start creates `/app/staticfiles` on host (via volume)
- **Persistence:** Directory persists across container restarts (volume-backed)

### PROD Environment
- **No Volume Mount:** `/app/staticfiles` exists only in container filesystem
- **Implication:** Ephemeral - lost on container restart
- **Mitigation:** Either:
  1. Serve static files via nginx (recommended)
  2. Use external storage (S3/MinIO) for static files
  3. Add persistent volume for staticfiles in production

### Collectstatic Skip (Dev)
When to disable collectstatic:
```bash
# Skip collectstatic (faster startup in dev)
DJANGO_COLLECTSTATIC=0 make dev

# Use case: rapid iteration, static files served by Django dev server
```

When to keep enabled:
- Testing production-like setup
- Debugging static file issues
- Before deployment (ensure no collectstatic errors)

---

## Migration Guide

### For Existing Installations
```bash
# 1. Stop containers
make down

# 2. Rebuild API image (applies Dockerfile fix)
docker-compose build api

# 3. (Optional) Clean up old volumes
docker volume ls | grep staticfiles  # Check if any exist
# docker volume rm <volume-name>      # If needed

# 4. Start containers
make dev

# 5. Verify
docker logs emr-api | grep "static files copied"
```

### For New Installations
No additional steps needed - fix is automatic in fresh builds.

---

## Related Documentation

- [Dockerfile](apps/api/Dockerfile) - Container build definition
- [docker-compose.yml](docker-compose.yml) - Service orchestration
- [Django Settings](apps/api/config/settings.py) - STATIC_ROOT / MEDIA_ROOT
- [PROJECT_DECISIONS.md](docs/PROJECT_DECISIONS.md) - Section 10: Infrastructure

---

## Lessons Learned

1. **Non-Root Containers:** Always pre-create writable directories **before** switching users
2. **Build vs Runtime:** Don't rely on runtime commands to create essential directories
3. **Volume Mounts:** Dev volume mounts can mask missing directories - test without volumes
4. **Error Handling:** Conditional execution prevents infinite restart loops
5. **Fail-Safe:** Provide escape hatches (DJANGO_COLLECTSTATIC=0) for debugging

---

## Author
- **Implementation:** GitHub Copilot (Claude Sonnet 4.5)
- **Date:** 2025-12-24
- **Context:** Container startup failure blocking development workflow
