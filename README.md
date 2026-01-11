# EMR Dermatology + POS Cosmetics

**A stable, Docker-first monorepo for dermatology practice management with integrated cosmetics point-of-sale.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-ready-blue.svg)](https://www.docker.com/)
[![Django](https://img.shields.io/badge/Django-4.2+-green.svg)](https://www.djangoproject.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14+-black.svg)](https://nextjs.org/)

---

## ⚡ Quick Start

```bash
# 1. Clone and navigate
git clone <your-repo-url>
cd "Cosmetica 5"

# 2. Copy environment file
cp .env.example .env

# 3. Start everything
make dev

# 4. Wait ~60 seconds for healthchecks, then access:
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# Django Admin: http://localhost:8000/admin (admin/admin123dev)
# MinIO Console: http://localhost:9001 (minioadmin/minioadmin)
```

---

## 🎯 Key Features

- **💚 Stability First**: Fixed ports, health checks, anti-zombie scripts
- **🐳 Docker-First**: One command to run everything
- **🌍 Multilingual**: UI in RU, FR, EN, UK, HY, ES
- **📸 Media Management**: S3-compatible storage with async thumbnail generation
- **🔐 Secure**: JWT auth, prepared for OIDC
- **📊 Modern Stack**: Django REST + Next.js + PostgreSQL + Redis + MinIO

---

## 📁 Project Structure

```
.
├── apps/
│   ├── api/              # Django backend
│   └── web/              # Next.js frontend
├── infra/                # Docker Compose
├── scripts/              # Dev automation
├── docs/                 # Documentation
│   ├── PORTS.md         # Port reference
│   ├── ARCHITECTURE.md  # System design
│   └── RUNBOOK.md       # Operations guide
├── .env.example         # Config template
├── Makefile             # Command interface
└── README.md            # You are here
```

---

## 🛠️ Technology Stack

### Backend
- Django 4.2+ with Django REST Framework
- PostgreSQL 15
- Redis 7 (cache + Celery broker)
- Celery (async tasks)
- MinIO (S3-compatible storage)
- OpenAPI 3.0 schema (drf-spectacular)

### Frontend
- Next.js 14+ (App Router)
- TypeScript
- TailwindCSS
- next-intl (i18n)
- React Query

### Infrastructure
- Docker + Docker Compose
- Makefile automation
- Shell scripts (macOS/Linux/Windows)

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, tech stack, data flow |
| [PORTS.md](docs/PORTS.md) | Fixed port mapping reference |
| [RUNBOOK.md](docs/RUNBOOK.md) | Operations guide, troubleshooting |

---

## 🚀 Development Commands

```bash
make dev          # Start all services
make down         # Stop all services
make logs         # View aggregated logs
make doctor       # System health diagnostics
make clean        # Kill zombies + reset Docker
make reset-db     # Recreate database
make check        # Run linters + tests
make shell-api    # Django shell
make shell-db     # PostgreSQL shell
```

---

## 🔌 Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | - |
| Backend API | http://localhost:8000 | - |
| Django Admin | http://localhost:8000/admin | admin/admin123dev |
| MinIO Console | http://localhost:9001 | minioadmin/minioadmin |
| API Docs | http://localhost:8000/api/schema/swagger-ui/ | - |

---

## 🏥 Application Modules

1. **Patients**: Patient records, demographics, search
2. **Encounters**: Visit tracking, SOAP notes
3. **Photos**: Skin photo upload with async thumbnails
4. **Products**: Catalog, pricing, stock levels
5. **Stock**: Inventory movements, audit trail
6. **Sales**: Transactions, payments
7. **Integrations**: Calendly webhooks, external APIs

---

## 🩺 Health Checks

All services have automated health monitoring:

```bash
# Backend health
curl http://localhost:8000/api/healthz
# {"status":"ok","database":"ok","redis":"ok"}

# Frontend health
curl http://localhost:3000/api/healthz
# {"status":"ok","backend":"connected"}

# System diagnostics
make doctor
```

---

## 🐛 Troubleshooting

### Port Already in Use
```bash
make clean  # Automated fix
```

### Cannot Connect to API
```bash
# Check backend is running
curl http://localhost:8000/api/healthz

# Verify environment variable
cat apps/web/.env.local | grep API_BASE_URL
```

### Database Connection Refused
```bash
make reset-db  # Recreate database
```

**See [RUNBOOK.md](docs/RUNBOOK.md) for comprehensive troubleshooting.**

---

## 🔒 Security Notes

⚠️ **Development credentials are PUBLIC. Change them in production!**

- PostgreSQL: `emr_user` / `emr_dev_pass`
- Django Admin: `admin` / `admin123dev`
- MinIO: `minioadmin` / `minioadmin`

**Production checklist:**
- [ ] Change all default passwords
- [ ] Set `DJANGO_DEBUG=False`
- [ ] Enable HTTPS
- [ ] Configure CORS whitelist
- [ ] Use secrets manager
- [ ] Enable firewall rules

---

## 📦 Requirements

- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **Disk Space**: 5GB minimum
- **RAM**: 8GB recommended
- **OS**: macOS (Apple Silicon/Intel), Windows 10+, Linux

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

**Before submitting:**
```bash
make check  # Run linters + tests
```

---

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file.

---

## 🙏 Acknowledgments

- Django REST Framework
- Next.js Team
- MinIO Project
- Open Source Community

---

## 📞 Support

For issues and questions:
1. Check [RUNBOOK.md](docs/RUNBOOK.md)
2. Run `make doctor` and share output
3. Open GitHub issue with:
   - Steps to reproduce
   - Expected vs actual behavior
   - Logs from `docker compose logs`

---

**Built with ❤️ for dermatology practices**
