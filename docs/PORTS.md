# Port Mapping - Fixed Ports Configuration

**CRITICAL: Estos puertos son FIJOS y NO deben cambiar sin actualizar toda la documentación.**

## Service Ports

| Service | Port | URL | Description |
|---------|------|-----|-------------|
| **ERP Frontend (Next.js)** | 3000 | http://localhost:3000 | Admin dashboard & ERP |
| **Public Site (Next.js)** | 3001 | http://localhost:3001 | Public website (dev only) |
| **Backend API (Django)** | 8000 | http://localhost:8000 | REST API & Admin |
| **PostgreSQL** | 5432 | localhost:5432 | Main database |
| **Redis** | 6379 | localhost:6379 | Cache & Celery broker |
| **MinIO (S3)** | 9000 | http://localhost:9000 | Object storage API |
| **MinIO Console** | 9001 | http://localhost:9001 | MinIO web UI |

## Health Check Endpoints

- **Backend**: `http://localhost:8000/api/healthz` - Checks DB + Redis connectivity
- **ERP Frontend**: `http://localhost:3000/api/healthz` - Checks backend connectivity
- **Public Site**: `http://localhost:3001/api/healthz` - Site health status
- **MinIO**: `http://localhost:9000/minio/health/live` - MinIO liveness probe

## Default Credentials (Development Only)

### PostgreSQL
- **User**: `emr_user`
- **Password**: `emr_dev_pass`
- **Database**: `emr_derma_db`

### Redis
- **Password**: (none in dev)

### MinIO
- **Root User**: `minioadmin`
- **Root Password**: `minioadmin`
- **Clinical Bucket**: `derma-photos` (clinical photos ONLY)
- **Marketing Bucket**: `marketing` (public/website assets ONLY)

### Django Admin
- **Username**: `admin`
- **Password**: `admin123dev`

## Firewall Rules

If you need to expose services, ensure these ports are open:
```bash
# macOS
sudo pfctl -e
# Add rules as needed

# Linux (ufw)
sudo ufw allow 3000/tcp
sudo ufw allow 3001/tcp
sudo ufw allow 8000/tcp
```

## Troubleshooting Port Conflicts

If you get "port already in use" errors:

### macOS/Linux
```bash
# Check what's using a port
lsof -i :3000
lsof -i :8000
lsof -i :5432

# Kill process by port
make clean  # Automated cleanup
# or manually:
lsof -ti tcp:3000 | xargs kill -9
```

### Windows
```powershell
# Check port usage
netstat -ano | findstr :3000

# Kill process by PID
taskkill /PID <PID> /F
```

## Port Change Protocol

**If you MUST change a port:**

1. Update `.env.example` and `.env`
2. Update `docker-compose.yml`
3. Update this `PORTS.md` document
4. Update `apps/web/src/config/runtime.ts`
5. Update `RUNBOOK.md` troubleshooting section
6. Notify all developers
7. Run `make clean && make dev` to rebuild

**DO NOT change ports without following this protocol.**
