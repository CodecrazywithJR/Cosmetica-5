# ============================================================================
# EMR Dermatology + POS Cosmetics - Makefile
# ============================================================================
# Single interface for all development commands

.PHONY: help dev down logs logs-follow doctor clean reset-db shell-api shell-db backup-db check lint test

# Default target
.DEFAULT_GOAL := help

# Colors
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m # No Color

##@ General

help: ## Display this help message
	@echo "$(BLUE)EMR Dermatology + POS Cosmetics - Development Commands$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make $(GREEN)<target>$(NC)\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(BLUE)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Development

dev: ## Start all services (docker-compose up)
	@echo "$(BLUE)🚀 Starting development environment...$(NC)"
	@chmod +x scripts/dev.sh
	@./scripts/dev.sh

down: ## Stop all services
	@echo "$(YELLOW)🛑 Stopping services...$(NC)"
	@cd infra && docker compose down

restart: down dev ## Restart all services

##@ Logs & Monitoring

logs: ## View logs (last 100 lines)
	@cd infra && docker compose logs --tail=100

logs-follow: ## View logs in follow mode
	@cd infra && docker compose logs -f

logs-api: ## View backend API logs
	@cd infra && docker compose logs -f api

logs-web: ## View frontend logs
	@cd infra && docker compose logs -f web

logs-celery: ## View Celery worker logs
	@cd infra && docker compose logs -f celery

doctor: ## Run system diagnostics
	@chmod +x scripts/doctor.sh
	@./scripts/doctor.sh

##@ Cleanup & Reset

clean: ## Kill zombie processes, clean Docker, and reset
	@echo "$(YELLOW)🧹 Cleaning up...$(NC)"
	@echo "Step 1: Killing processes on development ports..."
	@chmod +x scripts/kill_ports.sh
	@./scripts/kill_ports.sh || true
	@echo ""
	@echo "Step 2: Stopping Docker containers..."
	@cd infra && docker compose down --remove-orphans || true
	@echo ""
	@echo "Step 3: Pruning Docker networks..."
	@docker network prune -f || true
	@echo ""
	@echo "$(GREEN)✅ Cleanup complete!$(NC)"
	@echo "   Run 'make dev' to start fresh"

clean-all: clean ## Deep clean (remove volumes - DESTRUCTIVE)
	@echo "$(YELLOW)⚠️  WARNING: This will delete all data (database, uploads, etc.)$(NC)"
	@read -p "Are you sure? (type 'yes' to confirm): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		cd infra && docker compose down -v --remove-orphans; \
		echo "$(GREEN)✅ All volumes removed$(NC)"; \
	else \
		echo "$(YELLOW)Cancelled.$(NC)"; \
	fi

##@ Database

reset-db: ## Recreate database and run migrations
	@echo "$(BLUE)🔄 Resetting database...$(NC)"
	@cd infra && docker compose exec api python manage.py migrate --noinput
	@cd infra && docker compose exec api python manage.py ensure_superuser
	@echo "$(GREEN)✅ Database reset complete$(NC)"

migrate: ## Run Django migrations
	@cd infra && docker compose exec api python manage.py migrate

makemigrations: ## Create Django migrations
	@cd infra && docker compose exec api python manage.py makemigrations

shell-api: ## Open Django shell
	@cd infra && docker compose exec api python manage.py shell

shell-db: ## Open PostgreSQL shell
	@cd infra && docker compose exec postgres psql -U emr_user emr_derma_db

backup-db: ## Backup database to backups/ directory
	@mkdir -p backups
	@cd infra && docker compose exec -T postgres pg_dump -U emr_user emr_derma_db > backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)✅ Database backed up to backups/$(NC)"

##@ Code Quality

check: lint ## Run all code quality checks

lint: lint-backend lint-frontend ## Run linters

lint-backend: ## Lint backend code (black, ruff, isort)
	@echo "$(BLUE)🔍 Linting backend...$(NC)"
	@cd infra && docker compose exec api black --check apps/
	@cd infra && docker compose exec api ruff check apps/
	@cd infra && docker compose exec api isort --check-only apps/

lint-frontend: ## Lint frontend code (eslint)
	@echo "$(BLUE)🔍 Linting frontend...$(NC)"
	@cd infra && docker compose exec web npm run lint

format: format-backend format-frontend ## Auto-format all code

format-backend: ## Format backend code
	@echo "$(BLUE)✨ Formatting backend...$(NC)"
	@cd infra && docker compose exec api black apps/
	@cd infra && docker compose exec api isort apps/

format-frontend: ## Format frontend code
	@echo "$(BLUE)✨ Formatting frontend...$(NC)"
	@cd infra && docker compose exec web npm run lint -- --fix

##@ Testing

test: test-backend ## Run all tests

test-backend: ## Run backend tests
	@cd infra && docker compose exec api pytest

test-frontend: ## Run frontend tests
	@cd infra && docker compose exec web npm run test

##@ Build

build: ## Build Docker images
	@cd infra && docker compose build

rebuild: ## Rebuild Docker images (no cache)
	@cd infra && docker compose build --no-cache

##@ Security Scanning

security: security-bandit security-audit security-semgrep security-secrets ## Run all security scans

security-bandit: ## Run Bandit SAST scanner
	@echo "$(BLUE)🔒 Running Bandit (Python SAST)...$(NC)"
	@cd infra && docker compose exec api bandit -r apps/ -c /app/../.bandit 2>/dev/null || \
		bandit -r apps/api -c .bandit
	@echo "$(GREEN)✅ Bandit scan complete$(NC)"

security-audit: ## Run pip-audit dependency scan
	@echo "$(BLUE)🔒 Running pip-audit (dependency vulnerabilities)...$(NC)"
	@cd infra && docker compose exec api pip-audit -r requirements.txt 2>/dev/null || \
		pip-audit -r apps/api/requirements.txt
	@echo "$(GREEN)✅ pip-audit scan complete$(NC)"

security-semgrep: ## Run Semgrep static analysis
	@echo "$(BLUE)🔒 Running Semgrep (advanced SAST)...$(NC)"
	@semgrep scan --config .semgrep.yml
	@echo "$(GREEN)✅ Semgrep scan complete$(NC)"

security-secrets: ## Run detect-secrets scan
	@echo "$(BLUE)🔒 Running detect-secrets...$(NC)"
	@detect-secrets scan --baseline .secrets.baseline
	@echo "$(GREEN)✅ detect-secrets scan complete$(NC)"

security-trivy: ## Run Trivy filesystem scan
	@echo "$(BLUE)🔒 Running Trivy (filesystem vulnerabilities)...$(NC)"
	@trivy fs . --severity HIGH,CRITICAL
	@echo "$(GREEN)✅ Trivy scan complete$(NC)"

security-gate: test-backend security ## Full security gate (tests + all scans)
	@echo "$(GREEN)✅ All security gates passed$(NC)"

##@ Utilities

ps: ## Show running containers
	@cd infra && docker compose ps

exec-api: ## Execute command in API container (usage: make exec-api CMD="ls -la")
	@cd infra && docker compose exec api $(CMD)

exec-web: ## Execute command in web container (usage: make exec-web CMD="npm install")
	@cd infra && docker compose exec web $(CMD)

openapi-schema: ## Generate OpenAPI schema
	@cd infra && docker compose exec api python manage.py spectacular --file openapi-schema.yml
	@echo "$(GREEN)✅ OpenAPI schema generated: infra/openapi-schema.yml$(NC)"

##@ Installation

install: ## First-time setup
	@echo "$(BLUE)📦 Setting up EMR Dermatology + POS...$(NC)"
	@echo ""
	@echo "Step 1: Creating .env file..."
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(GREEN)✅ Created .env file$(NC)"; \
	else \
		echo "$(YELLOW)⚠️  .env already exists, skipping$(NC)"; \
	fi
	@echo ""
	@echo "Step 2: Building Docker images..."
	@cd infra && docker compose build
	@echo ""
	@echo "Step 3: Starting services..."
	@make dev
	@echo ""
	@echo "$(GREEN)✅ Installation complete!$(NC)"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Access frontend: http://localhost:3000"
	@echo "  2. Access Django admin: http://localhost:8000/admin"
	@echo "  3. Read docs: cat docs/ARCHITECTURE.md"
