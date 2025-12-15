#!/bin/bash
# Publish static site to CDN/S3 (controlled deployment)

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "🚀 Publishing public site..."
echo ""

# Check if export exists
if [ ! -d "apps/site/out" ]; then
    echo -e "${RED}❌ Static export not found. Run ./scripts/site_export.sh first${NC}"
    exit 1
fi

# Verify content
echo "📋 Verifying content..."
FILE_COUNT=$(find apps/site/out -type f | wc -l | tr -d ' ')
echo "   Files to publish: $FILE_COUNT"

# Check for required environment variables
if [ -z "$S3_BUCKET" ]; then
    echo -e "${YELLOW}⚠️  S3_BUCKET not set. Using default: website-derma-public${NC}"
    S3_BUCKET="website-derma-public"
fi

if [ -z "$CDN_DISTRIBUTION_ID" ]; then
    echo -e "${YELLOW}⚠️  CDN_DISTRIBUTION_ID not set (CloudFront cache invalidation will be skipped)${NC}"
fi

# Confirmation prompt
echo ""
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${YELLOW}⚠️  PRODUCTION DEPLOYMENT${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo "  Target: s3://$S3_BUCKET"
echo "  Files: $FILE_COUNT"
echo ""
read -p "Are you sure you want to publish? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${RED}❌ Deployment cancelled${NC}"
    exit 1
fi

# Upload to S3
echo ""
echo "☁️  Uploading to S3..."
aws s3 sync apps/site/out s3://$S3_BUCKET/ \
    --delete \
    --cache-control "public,max-age=31536000,immutable" \
    --exclude "*.html" \
    --exclude "*.json"

# Upload HTML with shorter cache
aws s3 sync apps/site/out s3://$S3_BUCKET/ \
    --cache-control "public,max-age=3600" \
    --include "*.html" \
    --include "*.json"

# Invalidate CloudFront cache (if configured)
if [ -n "$CDN_DISTRIBUTION_ID" ]; then
    echo ""
    echo "🔄 Invalidating CloudFront cache..."
    aws cloudfront create-invalidation \
        --distribution-id $CDN_DISTRIBUTION_ID \
        --paths "/*"
fi

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo "🌐 Your site should be live shortly"
echo ""
echo "Next steps:"
echo "  1. Verify deployment: curl https://yoursite.com"
echo "  2. Test contact form"
echo "  3. Check analytics"
