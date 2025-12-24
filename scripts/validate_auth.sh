#!/usr/bin/env bash
# =============================================================================
# Authentication System Validation Script
# =============================================================================
# Tests all authentication endpoints to verify correct implementation
# 
# Usage:
#   ./scripts/validate_auth.sh
#
# Requirements:
#   - curl
#   - jq (for JSON parsing)
#   - Backend running on http://localhost:8000
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
TEST_EMAIL="${TEST_EMAIL:-yo@ejemplo.com}"
TEST_PASSWORD="${TEST_PASSWORD:-Libertad}"

# Test results
PASSED=0
FAILED=0

# =============================================================================
# Helper Functions
# =============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_test() {
    echo -e "${YELLOW}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
    ((PASSED++))
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
    ((FAILED++))
}

check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}Error: $1 is not installed${NC}"
        exit 1
    fi
}

# =============================================================================
# Tests
# =============================================================================

test_health_check() {
    print_test "Testing health check endpoint..."
    
    response=$(curl -s -w "\n%{http_code}" "$API_BASE_URL/healthz")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" -eq 200 ]; then
        print_success "Health check passed (200 OK)"
        echo "   Response: $body"
    else
        print_error "Health check failed (HTTP $http_code)"
        echo "   Response: $body"
    fi
}

test_login_valid_credentials() {
    print_test "Testing login with valid credentials..."
    
    response=$(curl -s -w "\n%{http_code}" -X POST \
        "$API_BASE_URL/api/auth/token/" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASSWORD\"}")
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" -eq 200 ]; then
        # Check if response contains access and refresh tokens
        access_token=$(echo "$body" | jq -r '.access // empty')
        refresh_token=$(echo "$body" | jq -r '.refresh // empty')
        
        if [ -n "$access_token" ] && [ -n "$refresh_token" ]; then
            print_success "Login successful - tokens received"
            echo "   Access token: ${access_token:0:50}..."
            echo "   Refresh token: ${refresh_token:0:50}..."
            
            # Store tokens for subsequent tests
            export ACCESS_TOKEN="$access_token"
            export REFRESH_TOKEN="$refresh_token"
        else
            print_error "Login returned 200 but tokens missing"
            echo "   Response: $body"
        fi
    else
        print_error "Login failed (HTTP $http_code)"
        echo "   Response: $body"
    fi
}

test_login_invalid_credentials() {
    print_test "Testing login with invalid credentials..."
    
    response=$(curl -s -w "\n%{http_code}" -X POST \
        "$API_BASE_URL/api/auth/token/" \
        -H "Content-Type: application/json" \
        -d '{"email":"wrong@example.com","password":"wrongpass"}')
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" -eq 401 ]; then
        print_success "Invalid credentials correctly rejected (401)"
    else
        print_error "Expected 401 for invalid credentials, got $http_code"
        echo "   Response: $body"
    fi
}

test_get_current_user() {
    print_test "Testing GET /api/auth/me/ (current user profile)..."
    
    if [ -z "$ACCESS_TOKEN" ]; then
        print_error "No access token available (login test must pass first)"
        return
    fi
    
    response=$(curl -s -w "\n%{http_code}" \
        "$API_BASE_URL/api/auth/me/" \
        -H "Authorization: Bearer $ACCESS_TOKEN")
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" -eq 200 ]; then
        # Check if response contains expected fields
        user_id=$(echo "$body" | jq -r '.id // empty')
        user_email=$(echo "$body" | jq -r '.email // empty')
        user_roles=$(echo "$body" | jq -r '.roles // empty')
        
        if [ -n "$user_id" ] && [ -n "$user_email" ] && [ -n "$user_roles" ]; then
            print_success "User profile retrieved successfully"
            echo "   ID: $user_id"
            echo "   Email: $user_email"
            echo "   Roles: $user_roles"
        else
            print_error "User profile returned 200 but missing fields"
            echo "   Response: $body"
        fi
    else
        print_error "Failed to get user profile (HTTP $http_code)"
        echo "   Response: $body"
    fi
}

test_get_current_user_no_token() {
    print_test "Testing GET /api/auth/me/ without token..."
    
    response=$(curl -s -w "\n%{http_code}" "$API_BASE_URL/api/auth/me/")
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" -eq 401 ]; then
        print_success "Correctly rejected request without token (401)"
    else
        print_error "Expected 401 for missing token, got $http_code"
        echo "   Response: $body"
    fi
}

test_refresh_token() {
    print_test "Testing token refresh..."
    
    if [ -z "$REFRESH_TOKEN" ]; then
        print_error "No refresh token available (login test must pass first)"
        return
    fi
    
    response=$(curl -s -w "\n%{http_code}" -X POST \
        "$API_BASE_URL/api/auth/token/refresh/" \
        -H "Content-Type: application/json" \
        -d "{\"refresh\":\"$REFRESH_TOKEN\"}")
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" -eq 200 ]; then
        new_access_token=$(echo "$body" | jq -r '.access // empty')
        
        if [ -n "$new_access_token" ]; then
            print_success "Token refresh successful"
            echo "   New access token: ${new_access_token:0:50}..."
        else
            print_error "Token refresh returned 200 but no access token"
            echo "   Response: $body"
        fi
    else
        print_error "Token refresh failed (HTTP $http_code)"
        echo "   Response: $body"
    fi
}

test_refresh_token_invalid() {
    print_test "Testing token refresh with invalid token..."
    
    response=$(curl -s -w "\n%{http_code}" -X POST \
        "$API_BASE_URL/api/auth/token/refresh/" \
        -H "Content-Type: application/json" \
        -d '{"refresh":"invalid_token_here"}')
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" -eq 401 ]; then
        print_success "Invalid refresh token correctly rejected (401)"
    else
        print_error "Expected 401 for invalid refresh token, got $http_code"
        echo "   Response: $body"
    fi
}

test_verify_token() {
    print_test "Testing token verification..."
    
    if [ -z "$ACCESS_TOKEN" ]; then
        print_error "No access token available (login test must pass first)"
        return
    fi
    
    response=$(curl -s -w "\n%{http_code}" -X POST \
        "$API_BASE_URL/api/auth/token/verify/" \
        -H "Content-Type: application/json" \
        -d "{\"token\":\"$ACCESS_TOKEN\"}")
    
    http_code=$(echo "$response" | tail -n1)
    
    if [ "$http_code" -eq 200 ]; then
        print_success "Token verification passed (200 OK)"
    else
        print_error "Token verification failed (HTTP $http_code)"
    fi
}

# =============================================================================
# Main Execution
# =============================================================================

main() {
    print_header "Authentication System Validation"
    
    # Check prerequisites
    echo "Checking prerequisites..."
    check_command curl
    check_command jq
    
    echo -e "${GREEN}✓ All prerequisites met${NC}"
    echo ""
    echo "API Base URL: $API_BASE_URL"
    echo "Test Email: $TEST_EMAIL"
    echo ""
    
    # Run tests
    test_health_check
    test_login_valid_credentials
    test_login_invalid_credentials
    test_get_current_user
    test_get_current_user_no_token
    test_refresh_token
    test_refresh_token_invalid
    test_verify_token
    
    # Summary
    print_header "Test Summary"
    echo ""
    echo -e "${GREEN}Passed: $PASSED${NC}"
    echo -e "${RED}Failed: $FAILED${NC}"
    echo ""
    
    if [ "$FAILED" -eq 0 ]; then
        echo -e "${GREEN}✓ All tests passed!${NC}"
        echo -e "${GREEN}Authentication system is working correctly.${NC}"
        exit 0
    else
        echo -e "${RED}✗ Some tests failed${NC}"
        echo -e "${RED}Please review the errors above.${NC}"
        exit 1
    fi
}

# Run main function
main
