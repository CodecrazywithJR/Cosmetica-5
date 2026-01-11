#!/bin/bash
# ============================================================================
# Stop All Services
# ============================================================================
# Stops both development and production services
# Usage: ./stop.sh [dev|prod]
# ============================================================================

set -e

MODE=${1:-all}

case $MODE in
    dev)
        echo "🛑 Stopping DEVELOPMENT services..."
        docker compose -f docker-compose.dev.yml down
        echo "✅ Development services stopped"
        ;;
    prod)
        echo "🛑 Stopping PRODUCTION services..."
        docker compose -f docker-compose.prod.yml down
        echo "✅ Production services stopped"
        ;;
    all)
        echo "🛑 Stopping ALL services..."
        docker compose -f docker-compose.dev.yml down 2>/dev/null || true
        docker compose -f docker-compose.prod.yml down 2>/dev/null || true
        echo "✅ All services stopped"
        ;;
    *)
        echo "Usage: ./stop.sh [dev|prod|all]"
        echo "  dev  - Stop development services"
        echo "  prod - Stop production services"
        echo "  all  - Stop all services (default)"
        exit 1
        ;;
esac
