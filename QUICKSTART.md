# EMR Dermatology + POS Cosmetics - Quick Start Guide

## ⚙️ Prerequisites

Before starting, ensure you have:

- **Docker Desktop** installed and running (Docker Engine must be active)
- **Make** utility (usually pre-installed on macOS/Linux)

To verify Docker is ready:
```bash
docker info
# Should display system info without errors
```

## 🚀 Getting Started (First Time)

```bash
# 1. Install the project
make install

# This will:
# - Create .env from .env.example
# - Build Docker images
# - Start all services
# - Wait for healthchecks

# 2. Create admin user for login
docker compose exec api python manage.py create_admin_dev

# This creates:
# - Email: yo@ejemplo.com
# - Password: Libertad
# - Role: Admin (full access)
```

## 🔐 Login Credentials (Development)

After running `create_admin_dev`:

- **URL**: http://localhost:3000/es/login (or /en/login, /fr/login, etc.)
- **Email**: yo@ejemplo.com
- **Password**: Libertad
- **Role**: Admin (full access to all modules)

⚠️  **FOR DEVELOPMENT ONLY** - Remove this user in production!

### Authentication Flow (Updated 2025-12-24)

The system uses **JWT-based authentication** with automatic token refresh:

1. **Login**: Enter email + password
2. **Backend**: Returns `access_token` (60 min) + `refresh_token` (7 days)
3. **Profile Fetch**: Frontend automatically fetches your user profile and roles
4. **Redirect**: You're sent to the dashboard (`/{locale}`) based on your locale
5. **Auto-Refresh**: When `access_token` expires, system automatically uses `refresh_token` to get a new one
6. **Logout**: Click logout or refresh token expires → redirected to `/{locale}/login`

**API Endpoints** (for reference):
- `POST /api/auth/token/` - Login
- `POST /api/auth/token/refresh/` - Refresh access token
- `GET /api/auth/me/` - Get current user profile

See `docs/PROJECT_DECISIONS.md` section 3 for full architecture details.

## 📋 Daily Development Workflow

```bash
# Start everything
make dev

# View logs
make logs

# Stop everything
make down

# Check system health
make doctor
```

## 🔧 Common Tasks

### Backend Development
```bash
# Create Django migrations
make makemigrations

# Apply migrations
make migrate

# Open Django shell
make shell-api

# View backend logs
make logs-api
```

### Frontend Development
```bash
# View frontend logs
make logs-web

# Execute npm command
make exec-web CMD="npm install new-package"
```

### Database
```bash
# Reset database
make reset-db

# Backup database
make backup-db

# Open PostgreSQL shell
make shell-db
```

## 🧹 Troubleshooting

### Port Already in Use
```bash
make clean
make dev
```

### npm ci Fails (Missing package-lock.json)
```bash
# If Docker build fails with "npm ci can only install with existing package-lock.json"
# This should not happen anymore, but if it does:
cd apps/web  # or apps/site
docker run --rm -v "$(pwd)":/app -w /app node:20-alpine npm install --package-lock-only
```

### Frontend i18n Issues (next-intl)
```bash
# If you see "Couldn't find next-intl config file" or i18n errors:
rm -rf apps/web/.next
cd apps/web && npm run dev
```

### Docker Build Cache Issues
```bash
# Rebuild without cache if you encounter persistent build errors:
cd infra && docker compose build --no-cache
```

### Complete Reset (Nuclear Option)
```bash
make clean-all  # ⚠️  Deletes all data!
make dev
```

### Check System Health
```bash
make doctor
```

## ℹ️ Docker Build Notes

- All frontend services use `npm ci` for reproducible builds
- Requires `package-lock.json` to be present and committed
- Development Dockerfiles use `npm run dev` (hot reload enabled)
- If adding/updating npm packages, regenerate lockfile and commit it

## 📍 Service URLs

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Django Admin**: http://localhost:8000/admin (admin/admin123dev)
- **API Docs**: http://localhost:8000/api/schema/swagger-ui/
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)

## 📚 Full Documentation

- **Architecture**: `docs/ARCHITECTURE.md`
- **Port Reference**: `docs/PORTS.md`
- **Troubleshooting Guide**: `docs/RUNBOOK.md`

## ⚙️ Configuration

Edit `.env` file to change:
- API base URL
- Database credentials
- MinIO settings
- JWT secrets

**⚠️  Never commit `.env` to Git!**

## 🔒 Security Reminder

Default credentials are **for development only**:
- Django: admin/admin123dev
- MinIO: minioadmin/minioadmin
- PostgreSQL: emr_user/emr_dev_pass

**Change these in production!**

## 📝 Available Make Commands

Run `make help` to see all available commands.

## 🐛 Getting Help

1. Check `make doctor` output
2. Read `docs/RUNBOOK.md`
3. Check logs: `make logs`
4. Open an issue with diagnostic output
