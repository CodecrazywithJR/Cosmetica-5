#!/bin/bash
# Development startup script with validation

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "============================================"
echo "  EMR Dermatology + POS - Dev Startup"
echo "============================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo "📋 Checking prerequisites..."

# Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker found${NC}"

# Docker Compose
if ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose is not installed or too old${NC}"
    echo "   Please install Docker Compose v2+"
    exit 1
fi
echo -e "${GREEN}✅ Docker Compose found${NC}"

# Check .env file
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Copying from .env.example...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✅ Created .env file${NC}"
fi

echo ""
echo "🔍 Checking ports..."

# Check if ports are free
PORTS=(3000 3001 8000 5432 6379 9000 9001)
OCCUPIED=()

for PORT in "${PORTS[@]}"; do
  if lsof -ti tcp:$PORT &> /dev/null; then
    OCCUPIED+=($PORT)
  fi
done

if [ ${#OCCUPIED[@]} -gt 0 ]; then
    echo -e "${YELLOW}⚠️  The following ports are occupied: ${OCCUPIED[*]}${NC}"
    echo ""
    read -p "Kill processes on these ports? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ./scripts/kill_ports.sh
    else
        echo -e "${RED}❌ Cannot start with occupied ports. Exiting.${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✅ All ports are free${NC}"
echo ""

# Start services
echo "🚀 Starting services..."
cd infra
docker compose up --build -d

echo ""
echo "⏳ Waiting for services to become healthy (this may take up to 60 seconds)..."
echo ""

# Wait for services
TIMEOUT=60
ELAPSED=0
INTERVAL=5

while [ $ELAPSED -lt $TIMEOUT ]; do
    # Check backend health
    if curl -sf http://localhost:8000/api/healthz > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend is healthy${NC}"
        break
    fi
    
    echo "   Waiting for backend... ($ELAPSED/$TIMEOUT seconds)"
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

if [ $ELAPSED -ge $TIMEOUT ]; then
    echo -e "${RED}❌ Timeout waiting for backend to become healthy${NC}"
    echo "   Check logs with: docker compose -f infra/docker-compose.yml logs api"
    exit 1
fi

# Check frontend
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT ]; do
    if curl -sf http://localhost:3000 > /dev/null 2>&1; then
        echo -e "${GREEN}✅ ERP Frontend is healthy${NC}"
        break
    fi
    
    echo "   Waiting for ERP frontend... ($ELAPSED/$TIMEOUT seconds)"
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

# Check public site
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT ]; do
    if curl -sf http://localhost:3001/api/healthz > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Public Site is healthy${NC}"
        break
    fi
    
    echo "   Waiting for public site... ($ELAPSED/$TIMEOUT seconds)"
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

echo ""
echo "============================================"
echo -e "${GREEN}✅ All services are up and running!${NC}"
echo "============================================"
echo ""
echo "📍 Access your applications:"
echo "   ERP Frontend:  http://localhost:3000"
echo "   Public Site:   http://localhost:3001"
echo "   Backend API:   http://localhost:8000"
echo "   Django Admin:  http://localhost:8000/admin"
echo "   API Docs:      http://localhost:8000/api/schema/swagger-ui/"
echo "   MinIO Console: http://localhost:9001"
echo ""
echo "📊 Credentials (development only):"
echo "   Django Admin:  admin / admin123dev"
echo "   MinIO:         minioadmin / minioadmin"
echo ""
echo "📝 Useful commands:"
echo "   View logs:     make logs"
echo "   Stop services: make down"
echo "   Clean reset:   make clean"
echo ""
