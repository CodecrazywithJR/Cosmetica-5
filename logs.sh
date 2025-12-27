#!/bin/bash
# ============================================================================
# View Logs
# ============================================================================
# View logs from development or production services
# Usage: ./logs.sh [dev|prod] [service]
# ============================================================================

set -e

MODE=${1:-dev}
SERVICE=${2:-}

case $MODE in
    dev)
        echo "📋 Viewing DEVELOPMENT logs..."
        if [ -z "$SERVICE" ]; then
            docker compose -f docker-compose.dev.yml logs -f
        else
            docker compose -f docker-compose.dev.yml logs -f "$SERVICE"
        fi
        ;;
    prod)
        echo "📋 Viewing PRODUCTION logs..."
        if [ -z "$SERVICE" ]; then
            docker compose -f docker-compose.prod.yml logs -f
        else
            docker compose -f docker-compose.prod.yml logs -f "$SERVICE"
        fi
        ;;
    *)
        echo "Usage: ./logs.sh [dev|prod] [service]"
        echo ""
        echo "Examples:"
        echo "  ./logs.sh dev          - View all development logs"
        echo "  ./logs.sh dev api      - View development API logs only"
        echo "  ./logs.sh prod         - View all production logs"
        echo "  ./logs.sh prod web     - View production frontend logs only"
        echo ""
        echo "Available services: api, web, site, celery, postgres, redis, minio"
        exit 1
        ;;
esac
