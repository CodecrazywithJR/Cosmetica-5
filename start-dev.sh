#!/bin/bash
# ============================================================================
# Start Development Environment
# ============================================================================
# Starts all services in development mode with hot reload enabled
# Usage: ./start-dev.sh
# ============================================================================

set -e

echo "🚀 Starting EMR Dermatology + POS in DEVELOPMENT mode..."
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker Desktop first."
    exit 1
fi

# Check if .env.dev exists
if [ ! -f .env.dev ]; then
    echo "❌ Error: .env.dev file not found!"
    echo "Please create .env.dev from .env.example"
    exit 1
fi

echo "📋 Configuration:"
echo "   - Mode: DEVELOPMENT"
echo "   - Hot Reload: ENABLED"
echo "   - DEBUG: True"
echo "   - Env File: .env.dev"
echo ""

# Stop any existing services
echo "🛑 Stopping any existing services..."
docker compose -f docker-compose.dev.yml --env-file .env.dev down

echo ""
echo "🔨 Building and starting services..."
docker compose -f docker-compose.dev.yml --env-file .env.dev up -d --build

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 5

# Check service health
echo ""
echo "🏥 Service Status:"
docker compose -f docker-compose.dev.yml --env-file .env.dev ps

echo ""
echo "✅ Development environment started successfully!"
echo ""
echo "🌐 Access URLs:"
echo "   - Backend API:    http://localhost:8000"
echo "   - Frontend Web:   http://localhost:3000"
echo "   - Public Site:    http://localhost:3001"
echo "   - MinIO Console:  http://localhost:9001"
echo "   - API Docs:       http://localhost:8000/api/schema/swagger-ui/"
echo ""
echo "📊 Useful commands:"
echo "   - View logs:      docker compose -f docker-compose.dev.yml logs -f"
echo "   - Stop services:  docker compose -f docker-compose.dev.yml down"
echo "   - Restart:        ./start-dev.sh"
echo ""
