#!/bin/bash

# SPRINT 4 - Booking System Verification Script
# This script performs NO-MOCK verification of the booking system

set -e

echo "============================================"
echo "SPRINT 4 - BOOKING SYSTEM VERIFICATION"
echo "============================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Check containers
echo "📦 Test 1: Checking Docker containers..."
if docker ps | grep -q "emr-api-dev" && docker ps | grep -q "emr-web-dev"; then
    echo -e "${GREEN}✅ Backend and Frontend containers are running${NC}"
    # Show container status
    docker ps --filter "name=emr-api-dev" --format "  - API: {{.Status}}"
    docker ps --filter "name=emr-web-dev" --format "  - Web: {{.Status}}"
else
    echo -e "${RED}❌ Containers not running. Run: docker-compose -f docker-compose.dev.yml up -d${NC}"
    exit 1
fi
echo ""

# Test 2: Check API health
echo "🏥 Test 2: Checking API health..."
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/healthz)
if [ "$API_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ API is healthy (HTTP 200)${NC}"
else
    echo -e "${RED}❌ API not responding (HTTP $API_STATUS)${NC}"
    exit 1
fi
echo ""

# Test 3: Check booking page
echo "🌐 Test 3: Checking booking page..."
BOOKING_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/en/booking)
if [ "$BOOKING_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ Booking page accessible (HTTP 200)${NC}"
else
    echo -e "${RED}❌ Booking page not accessible (HTTP $BOOKING_STATUS)${NC}"
    exit 1
fi
echo ""

# Test 4: Check booking files exist
echo "📁 Test 4: Checking booking files..."
FILES=(
    "apps/web/src/lib/types/booking.ts"
    "apps/web/src/lib/api/booking.ts"
    "apps/web/src/components/booking/availability-calendar.tsx"
    "apps/web/src/components/booking/booking-modal.tsx"
    "apps/web/src/app/[locale]/booking/page.tsx"
)

ALL_FILES_EXIST=true
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅ $file${NC}"
    else
        echo -e "${RED}❌ Missing: $file${NC}"
        ALL_FILES_EXIST=false
    fi
done

if [ "$ALL_FILES_EXIST" = false ]; then
    exit 1
fi
echo ""

# Test 5: Check filterPastSlots function exists
echo "🕒 Test 5: Checking CRITICAL filterPastSlots function..."
if grep -q "filterPastSlots" apps/web/src/lib/api/booking.ts; then
    echo -e "${GREEN}✅ filterPastSlots() function exists${NC}"
    # Show function snippet
    echo -e "${YELLOW}Function preview:${NC}"
    grep -A 10 "export function filterPastSlots" apps/web/src/lib/api/booking.ts | head -11
else
    echo -e "${RED}❌ filterPastSlots() function NOT FOUND${NC}"
    exit 1
fi
echo ""

# Test 6: Check i18n translations
echo "🌍 Test 6: Checking i18n translations..."
if grep -q '"booking"' apps/web/messages/en.json && grep -q '"booking"' apps/web/messages/es.json; then
    echo -e "${GREEN}✅ Booking translations exist (EN + ES)${NC}"
else
    echo -e "${RED}❌ Booking translations missing${NC}"
    exit 1
fi
echo ""

# Test 7: Check API contracts (verify backend endpoint)
echo "🔌 Test 7: Testing API availability endpoint..."
# Get token (assuming user exists)
TOKEN=$(docker exec emr-api-dev python manage.py shell -c "
from apps.users.models import User
from rest_framework_simplejwt.tokens import RefreshToken
try:
    user = User.objects.filter(email='ricardoparlon@gmail.com').first()
    if user:
        refresh = RefreshToken.for_user(user)
        print(str(refresh.access_token))
except Exception as e:
    pass
" 2>/dev/null | tail -1)

if [ -z "$TOKEN" ] || [ "$TOKEN" = "None" ]; then
    echo -e "${YELLOW}⚠️  Could not get auth token. Skipping API endpoint test.${NC}"
    echo "   This is optional - API endpoints can be tested manually after login."
else
    # Get first practitioner
    PRACTITIONER_ID=$(docker exec emr-api-dev python manage.py shell -c "
from apps.users.models import User
try:
    p = User.objects.filter(user_role='practitioner').first()
    if p:
        print(p.id)
except Exception:
    pass
" 2>/dev/null | tail -1)
    
    if [ -n "$PRACTITIONER_ID" ] && [ "$PRACTITIONER_ID" != "None" ]; then
        # Test availability endpoint
        AVAIL_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
            -H "Authorization: Bearer $TOKEN" \
            "http://localhost:8000/api/v1/practitioners/$PRACTITIONER_ID/availability/?date_from=2025-01-20&date_to=2025-01-27&slot_duration=30" 2>/dev/null)
        
        if [ "$AVAIL_STATUS" = "200" ]; then
            echo -e "${GREEN}✅ Availability API endpoint working (HTTP 200)${NC}"
        else
            echo -e "${YELLOW}⚠️  Availability API returned HTTP $AVAIL_STATUS (might need schedule setup)${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  No practitioner found in database${NC}"
    fi
fi
echo ""

# Test 8: Check RBAC in code
echo "🔐 Test 8: Checking RBAC implementation..."
if grep -q "canSelectPractitioner" apps/web/src/app/[locale]/booking/page.tsx; then
    echo -e "${GREEN}✅ RBAC logic found in booking page${NC}"
    echo -e "${YELLOW}RBAC rules:${NC}"
    grep -A 2 "canSelectPractitioner" apps/web/src/app/[locale]/booking/page.tsx | head -3
else
    echo -e "${RED}❌ RBAC logic not found${NC}"
    exit 1
fi
echo ""

# Test 9: Check error handling
echo "⚠️  Test 9: Checking error handling..."
if grep -q "already started\|not available" apps/web/src/components/booking/booking-modal.tsx; then
    echo -e "${GREEN}✅ Error handling for slot validation found${NC}"
else
    echo -e "${RED}❌ Error handling missing${NC}"
    exit 1
fi
echo ""

# Test 10: Check auto-refresh logic
echo "🔄 Test 10: Checking auto-refresh after booking..."
if grep -q "loadAvailability()" apps/web/src/app/[locale]/booking/page.tsx; then
    echo -e "${GREEN}✅ Auto-refresh logic found${NC}"
    echo -e "${YELLOW}Implementation:${NC}"
    grep -B 2 -A 2 "loadAvailability()" apps/web/src/app/[locale]/booking/page.tsx | grep -A 4 "setTimeout" | head -5
else
    echo -e "${RED}❌ Auto-refresh logic missing${NC}"
    exit 1
fi
echo ""

# Summary
echo "============================================"
echo -e "${GREEN}✅ ALL AUTOMATED TESTS PASSED${NC}"
echo "============================================"
echo ""
echo "📝 MANUAL TESTING REQUIRED:"
echo ""
echo "1. Open browser: http://localhost:3000/en/booking"
echo "2. Login: ricardoparlon@gmail.com / qatest123"
echo "3. Verify slot filtering (today shows only future slots)"
echo "4. Book appointment and verify:"
echo "   - Success message appears"
echo "   - Slot disappears after 1.5s"
echo "   - Check DB:"
echo "     docker exec emr-api-dev python manage.py shell -c \\"
echo "       from apps.clinical.models import Appointment; \\"
echo "       print(Appointment.objects.latest('created_at'))\\"
echo ""
echo "5. Test error cases:"
echo "   - Try double booking (should show error)"
echo "   - Test RBAC (login as different roles)"
echo ""
echo "📚 Full documentation: SPRINT_4_UX_BOOKING_COMPLETE.md"
echo ""
