#!/bin/bash
# Build static version of public site

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🔨 Building public site..."
echo ""

# Check if apps/site exists
if [ ! -d "apps/site" ]; then
    echo -e "${RED}❌ apps/site directory not found${NC}"
    exit 1
fi

cd apps/site

# Check package.json
if [ ! -f "package.json" ]; then
    echo -e "${RED}❌ package.json not found${NC}"
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
npm ci

# Check environment variables
if [ -z "$NEXT_PUBLIC_SITE_CONTENT_API_BASE_URL" ]; then
    echo -e "${YELLOW}⚠️  NEXT_PUBLIC_SITE_CONTENT_API_BASE_URL not set, using default${NC}"
    export NEXT_PUBLIC_SITE_CONTENT_API_BASE_URL="http://localhost:8000/public"
fi

# Build
echo "🚀 Building Next.js app..."
npm run build

echo ""
echo -e "${GREEN}✅ Build complete!${NC}"
echo ""
echo "📁 Build output: apps/site/.next"
echo ""
echo "To start production server:"
echo "  cd apps/site && npm start"
