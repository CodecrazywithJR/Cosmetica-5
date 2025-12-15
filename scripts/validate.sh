#!/bin/bash
# Validation script - verify all files are in place

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🔍 Validating EMR Dermatology + POS project structure..."
echo ""

ERRORS=0

# Function to check file exists
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✅${NC} $1"
    else
        echo -e "${RED}❌${NC} $1 (missing)"
        ERRORS=$((ERRORS + 1))
    fi
}

# Function to check directory exists
check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✅${NC} $1/"
    else
        echo -e "${RED}❌${NC} $1/ (missing)"
        ERRORS=$((ERRORS + 1))
    fi
}

echo "📁 Root files:"
check_file "Makefile"
check_file ".env"
check_file ".env.example"
check_file ".gitignore"
check_file "README.md"
check_file "QUICKSTART.md"
check_file "BUILD_COMPLETE.md"

echo ""
echo "📁 Documentation:"
check_file "docs/ARCHITECTURE.md"
check_file "docs/PORTS.md"
check_file "docs/RUNBOOK.md"

echo ""
echo "📁 Scripts:"
check_file "scripts/dev.sh"
check_file "scripts/doctor.sh"
check_file "scripts/kill_ports.sh"
check_file "scripts/kill_ports.ps1"

echo ""
echo "📁 Infrastructure:"
check_file "infra/docker-compose.yml"
check_file "infra/postgres/init.sql"

echo ""
echo "📁 Backend (Django):"
check_dir "apps/api"
check_file "apps/api/manage.py"
check_file "apps/api/Dockerfile"
check_file "apps/api/requirements.txt"
check_file "apps/api/pyproject.toml"
check_file "apps/api/config/settings.py"
check_file "apps/api/config/urls.py"
check_file "apps/api/config/celery.py"

echo ""
echo "📁 Backend Apps:"
check_dir "apps/api/apps/core"
check_dir "apps/api/apps/patients"
check_dir "apps/api/apps/encounters"
check_dir "apps/api/apps/photos"
check_dir "apps/api/apps/products"
check_dir "apps/api/apps/stock"
check_dir "apps/api/apps/sales"
check_dir "apps/api/apps/integrations"

echo ""
echo "📁 Frontend (Next.js):"
check_dir "apps/web"
check_file "apps/web/package.json"
check_file "apps/web/Dockerfile"
check_file "apps/web/tsconfig.json"
check_file "apps/web/next.config.js"
check_file "apps/web/tailwind.config.js"
check_file "apps/web/.eslintrc.json"
check_file "apps/web/.prettierrc.json"
check_file "apps/web/src/config/runtime.ts"
check_file "apps/web/src/lib/api.ts"
check_file "apps/web/src/middleware.ts"
check_file "apps/web/src/i18n.ts"

echo ""
echo "📁 Frontend i18n:"
check_file "apps/web/messages/en.json"
check_file "apps/web/messages/ru.json"
check_file "apps/web/messages/fr.json"
check_file "apps/web/messages/es.json"
check_file "apps/web/messages/uk.json"
check_file "apps/web/messages/hy.json"

echo ""
echo "📁 Frontend Pages:"
check_file "apps/web/src/app/[locale]/layout.tsx"
check_file "apps/web/src/app/[locale]/page.tsx"
check_file "apps/web/src/app/[locale]/globals.css"
check_file "apps/web/src/app/api/healthz/route.ts"

echo ""
echo "============================================"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ All files validated successfully!${NC}"
    echo "   Project structure is complete."
    echo ""
    echo "Next step: Run 'make install' to start the project"
else
    echo -e "${RED}❌ Validation failed: $ERRORS file(s) missing${NC}"
    echo "   Please check the errors above."
    exit 1
fi
echo "============================================"
