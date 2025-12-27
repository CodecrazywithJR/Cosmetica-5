#!/bin/bash
# ============================================================================
# Start Production Local Environment
# ============================================================================
# Starts all services in production mode (for doctora's machine)
# Usage: ./start-prod.sh
# ============================================================================

set -e

echo "🚀 Starting EMR Dermatology + POS in PRODUCTION LOCAL mode..."
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker Desktop first."
    exit 1
fi

# Check if .env.prod exists
if [ ! -f .env.prod ]; then
    echo "❌ Error: .env.prod file not found!"
    echo "Please create .env.prod and configure it properly"
    exit 1
fi

# Security check: Warn if using default passwords
if grep -q "CHANGE_THIS" .env.prod; then
    echo "⚠️  WARNING: .env.prod contains default passwords marked with CHANGE_THIS"
    echo "   Please update all passwords before deploying to production!"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

echo "📋 Configuration:"
echo "   - Mode: PRODUCTION LOCAL"
echo "   - Hot Reload: DISABLED"
echo "   - DEBUG: False"
echo "   - Env File: .env.prod"
echo ""

# Stop any existing services
echo "🛑 Stopping any existing services..."
docker compose -f docker-compose.prod.yml --env-file .env.prod down

echo ""
echo "🔨 Building and starting services (this may take a few minutes)..."
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check service health
echo ""
echo "🏥 Service Status:"
docker compose -f docker-compose.prod.yml --env-file .env.prod ps

echo ""
echo "✅ Production environment started successfully!"
echo ""
echo "🌐 Access URLs:"
echo "   - Backend API:    http://localhost:8000"
echo "   - Frontend Web:   http://localhost:3000"
echo "   - Public Site:    http://localhost:3001"
echo "   - MinIO Console:  http://localhost:9001"
echo "   - API Docs:       http://localhost:8000/api/schema/swagger-ui/"
echo ""
echo "📊 Useful commands:"
echo "   - View logs:      docker compose -f docker-compose.prod.yml logs -f"
echo "   - Stop services:  docker compose -f docker-compose.prod.yml down"
echo "   - Restart:        ./start-prod.sh"
echo ""
echo "⚠️  IMPORTANT: Make sure to backup the database regularly!"
echo "   Database location: Docker volume 'postgres_data_prod'"
echo ""
