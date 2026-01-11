# Cosmetica 5 - Quick Start

EMR/ERP/POS System for aesthetic medicine clinics.

## 🚀 Quick Start

### Development Mode

```bash
./start-dev.sh
```

Access at: http://localhost:3000

### Production Local Mode (Doctora)

```bash
# First time: Edit .env.prod and change ALL passwords
./start-prod.sh
```

Access at: http://localhost:3000

## 📖 Documentation

- **[RUN.md](RUN.md)** - Complete execution guide (DEV vs PROD_LOCAL)
- **[QUICKSTART.md](QUICKSTART.md)** - Setup and installation
- **[docs/PROJECT_DECISIONS.md](docs/PROJECT_DECISIONS.md)** - Architecture decisions
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture

## 🛠️ Commands

```bash
# Start services
./start-dev.sh       # Development mode
./start-prod.sh      # Production local mode

# Stop services
./stop.sh            # Stop all
./stop.sh dev        # Stop development only
./stop.sh prod       # Stop production only

# View logs
./logs.sh dev        # All dev logs
./logs.sh dev api    # Specific service logs
./logs.sh prod web   # Production frontend logs
```

## 🏗️ Architecture

```
┌────────────────────────────────────────┐
│        Docker Compose Stack            │
├────────────────────────────────────────┤
│  Frontend (Next.js)    :3000           │
│  Backend (Django)      :8000           │
│  Public Site           :3001           │
│  PostgreSQL            :5432           │
│  Redis                 :6379           │
│  MinIO                 :9000/9001      │
└────────────────────────────────────────┘
```

## 📦 What's Included

- **Frontend**: Next.js 14 with TypeScript, TailwindCSS, next-intl
- **Backend**: Django REST Framework with PostgreSQL
- **Storage**: MinIO (S3-compatible) for clinical photos
- **Cache**: Redis for session management and Celery
- **Worker**: Celery for background tasks

## 🔐 Default Credentials (DEV)

- Username: `admin`
- Password: `admin123dev`

⚠️ **Change these in production!** (see `.env.prod`)

## ⚙️ Configuration Files

- `.env.dev` - Development environment variables
- `.env.prod` - Production environment variables (EDIT BEFORE USE)
- `docker-compose.dev.yml` - Development Docker configuration
- `docker-compose.prod.yml` - Production Docker configuration

## 🆘 Troubleshooting

### Port already in use

```bash
./stop.sh
./start-dev.sh
```

### Docker not running

```bash
open -a Docker  # macOS
# Wait for Docker to start, then retry
```

### Services not healthy

```bash
./logs.sh dev       # Check logs
docker compose -f docker-compose.dev.yml ps  # Check status
```

## 📱 Access Points

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/schema/swagger-ui/
- **Public Site**: http://localhost:3001
- **MinIO Console**: http://localhost:9001

## 🚫 Deprecated Files

These files are no longer used:

- ❌ `docker-compose.yml` - Use `docker-compose.dev.yml` or `docker-compose.prod.yml`
- ❌ `.env` - Use `.env.dev` or `.env.prod`

## 📚 More Information

For detailed information about system architecture, decisions, and implementation details, see [docs/](docs/).

**Key Documents**:
- [RUN.md](RUN.md) - How to run the system
- [docs/PROJECT_DECISIONS.md](docs/PROJECT_DECISIONS.md#13-execution-modes-dev-vs-prod_local) - Execution modes explained
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design
- [docs/PORTS.md](docs/PORTS.md) - Port assignments

---

**Version**: 1.0.0  
**Docker-First Architecture** - All services run in containers  
**Frontend Access**: Via web browser (not a desktop app)
