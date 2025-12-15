# System Architecture - EMR Dermatology + POS Cosmetics

## Overview

This is a **Docker-first monorepo** for a dermatology EMR system combined with a cosmetics point-of-sale, designed for maximum stability and cross-platform compatibility (macOS Apple Silicon, Windows, Linux).

## Core Principles

### 1. Stability First
- **Fixed ports**: No random port assignments
- **Health checks**: Every service has liveness/readiness probes
- **Anti-zombie**: Automated cleanup of orphaned processes
- **Restart policies**: Services auto-recover from crashes

### 2. Configuration Management
- **Single source of truth**: `.env` file for all configuration
- **Runtime validation**: Frontend validates API connectivity on startup
- **No hardcoded URLs**: All URLs from environment variables with fallbacks

### 3. Developer Experience
- **One command to rule them all**: `make dev` starts everything
- **Diagnostic tools**: `make doctor` checks system health
- **Clean slate**: `make clean` kills zombies and resets state

## Technology Stack

### Backend
- **Framework**: Django 4.2+ with Django REST Framework
- **Database**: PostgreSQL 15
- **Cache/Queue**: Redis 7
- **Task Queue**: Celery with Redis broker
- **Storage**: MinIO (S3-compatible)
- **API Schema**: OpenAPI 3.0 (drf-spectacular)
- **Auth**: JWT (djangorestframework-simplejwt), prepared for OIDC

### Frontend
- **Framework**: Next.js 14+ (App Router)
- **Language**: TypeScript
- **i18n**: next-intl (RU, FR, EN, UK, HY, ES)
- **State**: React Query for API calls
- **UI**: TailwindCSS + shadcn/ui (optional)
- **API Client**: Auto-generated from OpenAPI schema

### Infrastructure
- **Container**: Docker + Docker Compose
- **Orchestration**: Makefile + bash scripts
- **Monitoring**: Health check endpoints + logs

## Monorepo Structure

```
.
├── apps/
│   ├── api/              # Django backend
│   │   ├── config/       # Django settings
│   │   ├── apps/         # Django apps (patients, encounters, etc.)
│   │   ├── manage.py
│   │   └── requirements.txt
│   └── web/              # Next.js frontend
│       ├── src/
│       │   ├── app/      # Next.js app directory
│       │   ├── config/   # Runtime config (API URLs)
│       │   └── i18n/     # Translations
│       └── package.json
├── infra/
│   ├── docker-compose.yml
│   └── nginx/            # Reverse proxy (optional)
├── scripts/
│   ├── dev.sh            # Development startup script
│   ├── kill_ports.sh     # macOS/Linux port killer
│   ├── kill_ports.ps1    # Windows port killer
│   └── doctor.sh         # System health diagnostic
├── docs/
│   ├── ARCHITECTURE.md   # This file
│   ├── PORTS.md          # Port mapping reference
│   └── RUNBOOK.md        # Operations guide
├── .env.example          # Configuration template
├── Makefile              # Command interface
└── README.md
```

## Application Modules

### Backend Apps

#### 1. **patients**
- Patient CRUD
- Search by name, ID, phone
- Demographics, medical history

#### 2. **encounters**
- Visit/appointment records
- Linked to patients
- SOAP notes, diagnoses

#### 3. **photos**
- Skin photo upload
- Metadata (body part, tags)
- Thumbnail generation (async via Celery)
- Association with patient/encounter

#### 4. **products**
- Product catalog
- SKU, pricing, stock levels
- Categories

#### 5. **stock**
- Stock movements (IN/OUT)
- Inventory adjustments
- Audit trail

#### 6. **sales**
- Sales transactions
- Line items
- Payment tracking

#### 7. **integrations**
- Webhook endpoints
- Calendly integration (placeholder)
- External API connectors

### Frontend Structure

```
src/
├── app/                  # Next.js routes
│   ├── [locale]/        # i18n wrapper
│   │   ├── page.tsx     # Dashboard
│   │   ├── patients/    # Patient list/detail
│   │   ├── encounters/  # Visit management
│   │   └── pos/         # Point of sale
│   └── api/             # API routes (healthz)
├── components/          # Reusable UI
├── config/
│   └── runtime.ts       # API base URL + validation
├── i18n/                # Translation files
└── lib/
    ├── api/             # API client functions
    └── types/           # TypeScript types (from OpenAPI)
```

## Data Flow

### Patient Photo Upload Flow
1. User uploads photo via frontend
2. Frontend sends multipart/form-data to `/api/photos/`
3. Django saves to MinIO
4. Django creates Photo record in DB
5. Django enqueues Celery task for thumbnail
6. Celery worker generates thumbnail, saves to MinIO
7. Worker updates Photo record with thumbnail URL

### API Request Flow
1. Frontend reads `NEXT_PUBLIC_API_BASE_URL` from `.env`
2. Runtime config validates URL on app start
3. All API calls use `fetch` with base URL prefix
4. Errors trigger reconnect logic + user notification

## Security Considerations

### Development
- Default credentials documented in `PORTS.md`
- CORS enabled for localhost:3000
- Django DEBUG=True

### Production (Future)
- [ ] HTTPS only (Let's Encrypt)
- [ ] Rotate all default credentials
- [ ] CORS whitelist
- [ ] Django DEBUG=False
- [ ] Rate limiting
- [ ] OIDC authentication
- [ ] Encrypted backups

## Scalability Path

Current setup is single-server for development. For production:

1. **Database**: PostgreSQL replication
2. **Storage**: MinIO in distributed mode or AWS S3
3. **Backend**: Multiple Django instances behind nginx
4. **Frontend**: Deploy to Vercel/Netlify or nginx
5. **Celery**: Dedicated worker nodes
6. **Redis**: Redis Sentinel or cluster

## Health Monitoring

### Service Health Matrix

| Service | Endpoint | Expected Response | Checks |
|---------|----------|-------------------|--------|
| Backend | `/api/healthz` | `{"status":"ok","db":"ok","redis":"ok"}` | DB conn, Redis conn |
| Frontend | `/api/healthz` | `{"status":"ok","backend":"ok"}` | Backend reachable |
| MinIO | `/minio/health/live` | 200 OK | MinIO process alive |
| Postgres | `pg_isready` | accepting connections | Process responsive |
| Redis | `redis-cli ping` | PONG | Process responsive |

### Automated Health Checks

Docker Compose runs health checks every 30s:
- **Interval**: 30s
- **Timeout**: 10s
- **Retries**: 3
- **Start period**: 40s (allows slow starts)

## Troubleshooting Guide

See `RUNBOOK.md` for detailed troubleshooting procedures.

### Quick Diagnostics

```bash
# Check all services
make doctor

# View logs
make logs

# Restart everything cleanly
make clean
make dev

# Reset database only
make reset-db
```

## Development Workflow

### First Time Setup
```bash
# 1. Copy environment file
cp .env.example .env

# 2. Start all services
make dev

# 3. Wait for healthchecks to pass (~60s)

# 4. Access applications
open http://localhost:3000  # Frontend
open http://localhost:8000/admin  # Django admin
open http://localhost:9001  # MinIO console
```

### Daily Development
```bash
# Start services
make dev

# View logs in follow mode
make logs

# Stop services
make down

# Clean zombie processes
make clean
```

### Adding New Features
1. Backend: Create Django app, models, serializers, viewsets
2. Frontend: Add routes, components, API client functions
3. Update OpenAPI schema: `make openapi-schema`
4. Regenerate frontend types (if using codegen)
5. Test: `make test`
6. Lint: `make check`

## Future Enhancements

- [ ] GitHub Actions CI/CD
- [ ] Kubernetes manifests
- [ ] Terraform for cloud deployment
- [ ] Monitoring (Prometheus + Grafana)
- [ ] Logging aggregation (ELK stack)
- [ ] Feature flags
- [ ] Multi-tenancy support
- [ ] FHIR compliance for EMR data
