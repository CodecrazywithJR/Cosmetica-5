# Runbook - Operations Guide

## Quick Command Reference

```bash
make dev          # Start all services
make down         # Stop all services
make logs         # View aggregated logs
make doctor       # Run system diagnostics
make clean        # Kill zombies + clean Docker
make reset-db     # Recreate database
make check        # Run linters + tests
make shell-api    # Django shell
make shell-db     # PostgreSQL shell
```

## Common Issues & Solutions

### 🔴 Problem: "Port already in use"

**Symptoms:**
```
Error: bind: address already in use
```

**Solution:**
```bash
# Automated fix
make clean

# Manual fix (macOS/Linux)
lsof -ti tcp:3000 | xargs kill -9
lsof -ti tcp:8000 | xargs kill -9
lsof -ti tcp:5432 | xargs kill -9
lsof -ti tcp:6379 | xargs kill -9
lsof -ti tcp:9000 | xargs kill -9
lsof -ti tcp:9001 | xargs kill -9

# Manual fix (Windows PowerShell)
./scripts/kill_ports.ps1
```

**Prevention:**
- Always use `make down` instead of `Ctrl+C`
- Use `make clean` before `make dev`

---

### 🔴 Problem: Frontend shows "Cannot connect to API"

**Symptoms:**
- Frontend loads but shows connection error
- API requests fail with network errors

**Diagnosis:**
```bash
# 1. Check backend is running
curl http://localhost:8000/api/healthz

# 2. Check environment variable
cat apps/web/.env.local | grep API_BASE_URL

# 3. Check Docker network
docker compose ps
```

**Solution:**
```bash
# 1. Verify .env has correct URL
echo "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000" >> apps/web/.env.local

# 2. Restart frontend
docker compose restart web

# 3. Check browser console for CORS errors
# If CORS error: verify Django CORS_ALLOWED_ORIGINS includes http://localhost:3000
```

---

### 🔴 Problem: Database connection refused

**Symptoms:**
```
django.db.utils.OperationalError: could not connect to server
```

**Diagnosis:**
```bash
# Check if PostgreSQL is running
docker compose ps postgres

# Check logs
docker compose logs postgres

# Test connection manually
docker compose exec postgres pg_isready -U emr_user
```

**Solution:**
```bash
# 1. Restart PostgreSQL
docker compose restart postgres

# 2. Wait for healthcheck (30s)
docker compose ps

# 3. If still failing, recreate
make reset-db
```

---

### 🔴 Problem: Celery tasks not processing

**Symptoms:**
- Photos uploaded but no thumbnails
- Tasks stuck in "PENDING" state

**Diagnosis:**
```bash
# Check Celery worker logs
docker compose logs celery

# Check Redis connection
docker compose exec redis redis-cli ping

# Inspect queue
docker compose exec api python manage.py shell
>>> from celery import current_app
>>> current_app.control.inspect().active()
```

**Solution:**
```bash
# 1. Restart Celery worker
docker compose restart celery

# 2. Check Redis is accessible
docker compose exec api python -c "import redis; r=redis.Redis(host='redis'); print(r.ping())"

# 3. Purge queue if needed
docker compose exec api celery -A config purge -f
```

---

### 🔴 Problem: MinIO uploads failing

**Symptoms:**
```
botocore.exceptions.EndpointConnectionError
```

**Diagnosis:**
```bash
# Check MinIO is running
curl http://localhost:9000/minio/health/live

# Check bucket exists
docker compose exec minio mc ls local/derma-photos

# Check logs
docker compose logs minio
```

**Solution:**
```bash
# 1. Restart MinIO
docker compose restart minio

# 2. Recreate bucket
docker compose exec minio mc mb local/derma-photos --ignore-existing

# 3. Set public policy (dev only)
docker compose exec minio mc anonymous set download local/derma-photos
```

---

### 🔴 Problem: Frontend shows blank page

**Symptoms:**
- Browser loads http://localhost:3000 but shows nothing
- No errors in console

**Diagnosis:**
```bash
# Check Next.js logs
docker compose logs web

# Check if Next.js is running
curl -I http://localhost:3000

# Check Node.js errors
docker compose exec web npm run build
```

**Solution:**
```bash
# 1. Rebuild frontend
docker compose build web
docker compose up -d web

# 2. Check for JavaScript errors
# Open browser console (F12)

# 3. Clear Next.js cache
docker compose exec web rm -rf .next
docker compose restart web
```

---

### 🔴 Problem: Zombie processes after crash

**Symptoms:**
- `make dev` fails even after closing terminal
- Ports still occupied after stopping Docker

**Diagnosis:**
```bash
# List all processes on development ports
lsof -i :3000,:8000,:5432,:6379,:9000,:9001
```

**Solution:**
```bash
# Automated cleanup
make clean

# Manual cleanup (macOS/Linux)
./scripts/kill_ports.sh

# Manual cleanup (Windows)
./scripts/kill_ports.ps1
```

---

### 🔴 Problem: Docker containers marked "unhealthy"

**Symptoms:**
```
docker compose ps
# Shows (unhealthy) status
```

**Diagnosis:**
```bash
# Check health check logs
docker inspect <container_id> | jq '.[0].State.Health'

# View detailed logs
docker compose logs <service_name>
```

**Solution:**
```bash
# 1. Wait for start period to complete (40s)

# 2. Check health endpoint manually
# Backend:
curl http://localhost:8000/api/healthz

# MinIO:
curl http://localhost:9000/minio/health/live

# 3. Restart unhealthy service
docker compose restart <service_name>

# 4. If persists, rebuild
docker compose up -d --build <service_name>
```

---

## Environment Setup Validation

Run this checklist before starting development:

```bash
# 1. Docker installed and running
docker --version
docker compose version

# 2. Ports are free
make doctor

# 3. Environment file exists
test -f .env && echo "✓ .env exists" || echo "✗ Copy .env.example to .env"

# 4. Sufficient disk space
df -h .

# 5. Docker has enough resources
# macOS: Docker Desktop > Settings > Resources
# - CPUs: 4+
# - Memory: 8GB+
# - Swap: 2GB+
```

---

## System Health Check Commands

### Backend Health
```bash
# Django
curl http://localhost:8000/api/healthz
# Expected: {"status":"ok","database":"ok","redis":"ok"}

# Database
docker compose exec postgres pg_isready -U emr_user
# Expected: accepting connections

# Redis
docker compose exec redis redis-cli ping
# Expected: PONG

# Celery
docker compose exec api celery -A config inspect ping
# Expected: pong from workers
```

### Frontend Health
```bash
# Next.js
curl http://localhost:3000/api/healthz
# Expected: {"status":"ok","backend":"connected"}

# Build check
docker compose exec web npm run build
# Expected: No errors
```

### Storage Health
```bash
# MinIO
curl http://localhost:9000/minio/health/live
# Expected: 200 OK

# List buckets
docker compose exec minio mc ls local
# Expected: derma-photos bucket listed
```

---

## Database Operations

### Backup Database
```bash
docker compose exec postgres pg_dump -U emr_user emr_derma_db > backup_$(date +%Y%m%d).sql
```

### Restore Database
```bash
# 1. Stop backend
docker compose stop api celery

# 2. Drop and recreate DB
docker compose exec postgres psql -U emr_user -c "DROP DATABASE emr_derma_db;"
docker compose exec postgres psql -U emr_user -c "CREATE DATABASE emr_derma_db;"

# 3. Restore
cat backup_20231215.sql | docker compose exec -T postgres psql -U emr_user emr_derma_db

# 4. Restart backend
docker compose up -d api celery
```

### Reset Database (Development)
```bash
make reset-db
# This will:
# 1. Drop all tables
# 2. Run migrations
# 3. Create superuser (admin/admin123dev)
# 4. Load fixtures (if any)
```

### Run Migrations
```bash
# Create migration
docker compose exec api python manage.py makemigrations

# Apply migrations
docker compose exec api python manage.py migrate

# Show migration status
docker compose exec api python manage.py showmigrations
```

---

## Debugging

### Access Django Shell
```bash
make shell-api
# or
docker compose exec api python manage.py shell
```

### Access PostgreSQL Shell
```bash
make shell-db
# or
docker compose exec postgres psql -U emr_user emr_derma_db
```

### Access Redis CLI
```bash
docker compose exec redis redis-cli
```

### View Live Logs
```bash
# All services
make logs

# Specific service
docker compose logs -f api
docker compose logs -f web
docker compose logs -f celery

# Last 100 lines
docker compose logs --tail=100 api
```

### Inspect Container
```bash
docker compose exec api bash
docker compose exec web sh
```

---

## Performance Tuning

### Backend Too Slow
```bash
# Enable Django Debug Toolbar (dev only)
# Add to apps/api/config/settings/dev.py

# Profile slow queries
docker compose exec api python manage.py shell
>>> from django.db import connection
>>> print(connection.queries)

# Check database indexes
docker compose exec postgres psql -U emr_user emr_derma_db -c "\d+ patients_patient"
```

### Frontend Too Slow
```bash
# Analyze bundle size
docker compose exec web npm run build
# Look for large chunks

# Use Next.js production mode locally
docker compose exec web npm run build
docker compose exec web npm run start
```

### High Memory Usage
```bash
# Check Docker stats
docker stats

# Restart service with memory limit
docker compose up -d --scale api=1 --memory="2g" api
```

---

## Security Reminders

### Development Only Credentials
⚠️ **NEVER use these in production:**
- PostgreSQL: `emr_user` / `emr_dev_pass`
- Django Admin: `admin` / `admin123dev`
- MinIO: `minioadmin` / `minioadmin`

### Production Checklist
- [ ] Change all default passwords
- [ ] Set `DEBUG=False` in Django
- [ ] Use environment variables for secrets
- [ ] Enable HTTPS
- [ ] Configure CORS whitelist
- [ ] Set up database backups
- [ ] Enable firewall rules
- [ ] Use secrets manager (AWS Secrets Manager, Vault)

---

## Getting Help

### Log Files
All logs are available via `docker compose logs <service>`:
- Backend: `api`
- Frontend: `web`
- Worker: `celery`
- Database: `postgres`
- Cache: `redis`
- Storage: `minio`

### Diagnostic Report
```bash
# Generate full diagnostic report
make doctor > diagnostic_report.txt
```

### Reporting Issues
Include this information:
1. Output of `make doctor`
2. Relevant logs from `docker compose logs`
3. Steps to reproduce
4. Expected vs actual behavior
5. OS and Docker version

---

## Maintenance Tasks

### Weekly
```bash
# Clean up old Docker images
docker image prune -a --filter "until=168h"

# Check disk usage
docker system df

# Backup database
make backup-db
```

### Monthly
```bash
# Update dependencies
# Backend:
docker compose exec api pip list --outdated

# Frontend:
docker compose exec web npm outdated

# Rebuild with latest images
docker compose build --no-cache
```

---

## Emergency Procedures

### Complete System Reset
```bash
# ⚠️ This will DELETE all data!

# 1. Stop all services
make down

# 2. Remove all containers and volumes
docker compose down -v --remove-orphans

# 3. Clean zombie processes
make clean

# 4. Remove Docker networks
docker network prune -f

# 5. Start fresh
make dev

# 6. Reset database
make reset-db
```

### Rollback to Previous State
```bash
# If you have a backup
make down
# Restore backup (see Database Operations)
make dev
```
