# EMR Dermatology + POS Cosmetics - Quick Start Guide

## 🚀 Getting Started (First Time)

```bash
# 1. Install the project
make install

# This will:
# - Create .env from .env.example
# - Build Docker images
# - Start all services
# - Wait for healthchecks
```

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

### Complete Reset (Nuclear Option)
```bash
make clean-all  # ⚠️  Deletes all data!
make dev
```

### Check System Health
```bash
make doctor
```

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
