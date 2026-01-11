#!/bin/bash
# Export static HTML for public site (for CDN/static hosting)

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "📦 Exporting public site to static HTML..."
echo ""

# Check if apps/site exists
if [ ! -d "apps/site" ]; then
    echo -e "${RED}❌ apps/site directory not found${NC}"
    exit 1
fi

cd apps/site

# Check if build exists
if [ ! -d ".next" ]; then
    echo -e "${YELLOW}⚠️  No build found. Running build first...${NC}"
    npm run build
fi

# Export
echo "🚀 Exporting to static HTML..."
npm run export

echo ""
echo -e "${GREEN}✅ Export complete!${NC}"
echo ""
echo "📁 Static files: apps/site/out"
echo "📊 Total size: $(du -sh out | cut -f1)"
echo ""
echo "To test static export locally:"
echo "  npx serve out"
echo ""
echo "To publish to CDN:"
echo "  ./scripts/site_publish.sh"
