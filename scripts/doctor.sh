#!/bin/bash
# System health diagnostic script

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "============================================"
echo "  EMR Dermatology - System Diagnostics"
echo "============================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Docker status
echo "🐳 Docker Status:"
if docker info > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Docker is running${NC}"
else
    echo -e "${RED}❌ Docker is not running${NC}"
fi
echo ""

# Docker Compose status
echo "📦 Docker Compose Services:"
cd "$PROJECT_ROOT/infra"
docker compose ps
echo ""

# Port availability
echo "🔌 Port Status:"
PORTS=(3000 3001 8000 5432 6379 9000 9001)
PORT_NAMES=("ERP Frontend" "Public Site" "Backend API" "PostgreSQL" "Redis" "MinIO API" "MinIO Console")

for i in "${!PORTS[@]}"; do
    PORT=${PORTS[$i]}
    NAME=${PORT_NAMES[$i]}
    
    if lsof -ti tcp:$PORT &> /dev/null; then
        PID=$(lsof -ti tcp:$PORT)
        PROCESS=$(ps -p $PID -o comm= 2>/dev/null || echo "unknown")
        echo -e "${YELLOW}⚠️  Port $PORT ($NAME) - OCCUPIED by PID $PID ($PROCESS)${NC}"
    else
        echo -e "${GREEN}✅ Port $PORT ($NAME) - FREE${NC}"
    fi
done
echo ""

# Health checks
echo "🏥 Service Health Checks:"

# Backend
if curl -sf http://localhost:8000/api/healthz > /dev/null 2>&1; then
    HEALTH=$(curl -s http://localhost:8000/api/healthz)
    echo -e "${GREEN}✅ Backend API - HEALTHY${NC}"
    echo "   $HEALTH"
else
    echo -e "${RED}❌ Backend API - UNREACHABLE${NC}"
fi

# ERP Frontend
if curl -sf http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ ERP Frontend - HEALTHY${NC}"
else
    echo -e "${RED}❌ ERP Frontend - UNREACHABLE${NC}"
fi

# Public Site
if curl -sf http://localhost:3001/api/healthz > /dev/null 2>&1; then
    SITE_HEALTH=$(curl -s http://localhost:3001/api/healthz)
    echo -e "${GREEN}✅ Public Site - HEALTHY${NC}"
    echo "   $SITE_HEALTH"
else
    echo -e "${RED}❌ Public Site - UNREACHABLE${NC}"
fi

# MinIO
if curl -sf http://localhost:9000/minio/health/live > /dev/null 2>&1; then
    echo -e "${GREEN}✅ MinIO - HEALTHY${NC}"
else
    echo -e "${RED}❌ MinIO - UNREACHABLE${NC}"
fi

echo ""

# Disk space
echo "💾 Disk Space:"
df -h . | tail -1
echo ""

# Docker resources
echo "📊 Docker Resource Usage:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" 2>/dev/null || echo "No containers running"
echo ""

# Environment file
echo "⚙️  Environment Configuration:"
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${GREEN}✅ .env file exists${NC}"
    echo "   API URL: $(grep NEXT_PUBLIC_API_BASE_URL $PROJECT_ROOT/.env || echo 'Not set')"
else
    echo -e "${RED}❌ .env file not found${NC}"
fi
echo ""

echo "============================================"
echo "  Diagnostic complete"
echo "============================================"
