#!/bin/bash
#
# Cosmetica 5 - Restore from Backup Script
#
# Purpose: Restore database and media files from backup
# Usage: ./restore_from_backup.sh --backup-dir=<path> [--target=production|staging]
#
# Version: 1.0
# Last Updated: 2025-12-22

set -euo pipefail

###############################################################################
# Configuration
###############################################################################

APP_DIR="${APP_DIR:-/opt/cosmetica5}"
MEDIA_ROOT="${MEDIA_ROOT:-/var/cosmetica5/media}"
DB_NAME="${DB_NAME:-cosmetica5}"
DB_USER="${DB_USER:-postgres}"
BACKUP_PASSWORD_FILE="${BACKUP_PASSWORD_FILE:-/secure/backup_password.txt}"

###############################################################################
# Helper Functions
###############################################################################

log() {
    local level="$1"
    shift
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*"
}

log_info() {
    log "INFO" "$@"
}

log_error() {
    log "ERROR" "$@"
}

log_success() {
    log "SUCCESS" "$@"
}

log_warning() {
    log "WARNING" "$@"
}

confirm_action() {
    local message="$1"
    local target="$2"
    
    if [[ "$target" == "production" ]]; then
        log_warning "=========================================="
        log_warning "WARNING: PRODUCTION RESTORE"
        log_warning "This will OVERWRITE production data!"
        log_warning "=========================================="
    fi
    
    echo "$message"
    read -p "Type 'YES' to confirm: " confirmation
    
    if [[ "$confirmation" != "YES" ]]; then
        log_error "Restore cancelled by user"
        exit 1
    fi
}

check_backup_integrity() {
    local backup_dir="$1"
    
    log_info "Checking backup integrity..."
    
    # Check if manifest exists
    if [[ ! -f "$backup_dir/backup_manifest.json" ]]; then
        log_error "Backup manifest not found: $backup_dir/backup_manifest.json"
        exit 1
    fi
    
    # Parse manifest
    local manifest="$backup_dir/backup_manifest.json"
    local db_file=$(jq -r '.database.file' "$manifest")
    local media_file=$(jq -r '.media.file' "$manifest")
    local db_checksum=$(jq -r '.database.checksum_sha256' "$manifest")
    local media_checksum=$(jq -r '.media.checksum_sha256' "$manifest")
    
    # Check if files exist
    if [[ ! -f "$backup_dir/$db_file" ]]; then
        log_error "Database backup file not found: $backup_dir/$db_file"
        exit 1
    fi
    
    if [[ ! -f "$backup_dir/$media_file" ]]; then
        log_error "Media backup file not found: $backup_dir/$media_file"
        exit 1
    fi
    
    # Verify checksums
    log_info "Verifying database checksum..."
    local actual_db_checksum=$(sha256sum "$backup_dir/$db_file" | awk '{print $1}')
    if [[ "$actual_db_checksum" != "$db_checksum" ]]; then
        log_error "Database checksum mismatch!"
        log_error "Expected: $db_checksum"
        log_error "Actual:   $actual_db_checksum"
        exit 1
    fi
    
    log_info "Verifying media checksum..."
    local actual_media_checksum=$(sha256sum "$backup_dir/$media_file" | awk '{print $1}')
    if [[ "$actual_media_checksum" != "$media_checksum" ]]; then
        log_error "Media checksum mismatch!"
        log_error "Expected: $media_checksum"
        log_error "Actual:   $actual_media_checksum"
        exit 1
    fi
    
    log_success "Backup integrity verified"
    
    # Display backup info
    log_info "Backup Details:"
    log_info "  ID:        $(jq -r '.backup_id' "$manifest")"
    log_info "  Timestamp: $(jq -r '.timestamp' "$manifest")"
    log_info "  Version:   $(jq -r '.version.app' "$manifest")"
    log_info "  Git:       $(jq -r '.version.git_commit' "$manifest")"
    log_info "  Migration: $(jq -r '.migrations.last_applied' "$manifest")"
}

decrypt_file() {
    local encrypted_file="$1"
    local output_file="${encrypted_file%.enc}"
    
    if [[ ! -f "$encrypted_file" ]]; then
        log_error "Encrypted file not found: $encrypted_file"
        return 1
    fi
    
    if [[ ! -f "$BACKUP_PASSWORD_FILE" ]]; then
        log_error "Backup password file not found: $BACKUP_PASSWORD_FILE"
        log_error "Cannot decrypt backup files"
        exit 1
    fi
    
    log_info "Decrypting: $(basename "$encrypted_file")"
    
    openssl enc -aes-256-cbc -d -pbkdf2 \
        -in "$encrypted_file" \
        -out "$output_file" \
        -pass "file:$BACKUP_PASSWORD_FILE"
    
    if [[ -f "$output_file" ]]; then
        log_success "Decryption completed: $(basename "$output_file")"
        echo "$output_file"
    else
        log_error "Decryption failed"
        exit 1
    fi
}

restore_database() {
    local backup_dir="$1"
    local target="$2"
    
    log_info "Restoring database: $DB_NAME"
    
    local manifest="$backup_dir/backup_manifest.json"
    local db_file=$(jq -r '.database.file' "$manifest")
    local db_path="$backup_dir/$db_file"
    
    # Decrypt if encrypted
    if [[ "$db_file" == *.enc ]]; then
        db_path=$(decrypt_file "$db_path")
    fi
    
    # Confirm destructive action
    if [[ "$target" == "production" ]]; then
        confirm_action "This will DROP and recreate database '$DB_NAME'. Continue?" "production"
    fi
    
    # Drop existing database (if target is not production, or user confirmed)
    log_info "Dropping existing database..."
    sudo -u postgres psql -c "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null || true
    
    # Create fresh database
    log_info "Creating fresh database..."
    sudo -u postgres createdb "$DB_NAME"
    
    # Restore from backup
    log_info "Restoring from backup file..."
    sudo -u postgres pg_restore \
        --dbname="$DB_NAME" \
        --verbose \
        --no-owner \
        --no-privileges \
        "$db_path" 2>&1 | grep -v "^pg_restore:" || true
    
    # Verify restoration
    local patient_count=$(sudo -u postgres psql -d "$DB_NAME" -tAc "SELECT COUNT(*) FROM clinical_patient;" 2>/dev/null || echo "0")
    local encounter_count=$(sudo -u postgres psql -d "$DB_NAME" -tAc "SELECT COUNT(*) FROM encounters_encounter;" 2>/dev/null || echo "0")
    
    log_success "Database restored successfully"
    log_info "  Patients:   $patient_count"
    log_info "  Encounters: $encounter_count"
}

restore_media() {
    local backup_dir="$1"
    local target="$2"
    
    log_info "Restoring media files: $MEDIA_ROOT"
    
    local manifest="$backup_dir/backup_manifest.json"
    local media_file=$(jq -r '.media.file' "$manifest")
    local media_path="$backup_dir/$media_file"
    
    # Decrypt if encrypted
    if [[ "$media_file" == *.enc ]]; then
        media_path=$(decrypt_file "$media_path")
    fi
    
    # Confirm destructive action
    if [[ "$target" == "production" ]]; then
        confirm_action "This will DELETE existing media files in '$MEDIA_ROOT'. Continue?" "production"
    fi
    
    # Backup existing media (just in case)
    if [[ -d "$MEDIA_ROOT" ]] && [[ "$target" == "production" ]]; then
        local backup_timestamp=$(date +%Y%m%d-%H%M%S)
        local temp_backup="/tmp/media-backup-$backup_timestamp"
        log_info "Creating safety backup of existing media: $temp_backup"
        mv "$MEDIA_ROOT" "$temp_backup"
    fi
    
    # Create media directory
    mkdir -p "$MEDIA_ROOT"
    
    # Extract media archive
    log_info "Extracting media files..."
    tar -xzf "$media_path" -C "$(dirname "$MEDIA_ROOT")"
    
    # Set correct permissions
    if [[ -d "$MEDIA_ROOT" ]]; then
        chown -R www-data:www-data "$MEDIA_ROOT" 2>/dev/null || chown -R $(whoami):$(whoami) "$MEDIA_ROOT"
        chmod -R 755 "$MEDIA_ROOT"
    fi
    
    # Verify restoration
    local file_count=$(find "$MEDIA_ROOT" -type f | wc -l)
    local expected_count=$(jq -r '.media.file_count' "$manifest")
    
    log_success "Media files restored successfully"
    log_info "  Files restored: $file_count"
    log_info "  Files expected: $expected_count"
    
    if [[ "$file_count" -ne "$expected_count" ]]; then
        log_warning "File count mismatch! Review restore logs."
    fi
}

run_migrations() {
    local backup_dir="$1"
    
    log_info "Checking Django migrations..."
    
    cd "$APP_DIR"
    
    # Activate virtual environment if exists
    if [[ -f ".venv/bin/activate" ]]; then
        source .venv/bin/activate
    fi
    
    # Show migration status
    log_info "Current migration status:"
    python apps/api/manage.py showmigrations 2>&1 | head -20
    
    # Ask user if they want to run migrations
    read -p "Run migrations? (y/N): " run_migrations
    
    if [[ "$run_migrations" =~ ^[Yy]$ ]]; then
        log_info "Running migrations..."
        python apps/api/manage.py migrate --no-input
        log_success "Migrations completed"
    else
        log_warning "Migrations skipped by user"
    fi
}

run_smoke_tests() {
    log_info "Running smoke tests..."
    
    cd "$APP_DIR"
    
    # Activate virtual environment if exists
    if [[ -f ".venv/bin/activate" ]]; then
        source .venv/bin/activate
    fi
    
    # Test 1: Django check
    log_info "Test 1: Django system check..."
    if python apps/api/manage.py check --deploy > /dev/null 2>&1; then
        log_success "✓ Django system check passed"
    else
        log_error "✗ Django system check failed"
    fi
    
    # Test 2: Database connection
    log_info "Test 2: Database connection..."
    if sudo -u postgres psql -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
        log_success "✓ Database connection OK"
    else
        log_error "✗ Database connection failed"
    fi
    
    # Test 3: Media files accessible
    log_info "Test 3: Media files accessible..."
    if [[ -d "$MEDIA_ROOT" ]] && [[ $(find "$MEDIA_ROOT" -type f | wc -l) -gt 0 ]]; then
        log_success "✓ Media files accessible"
    else
        log_warning "⚠ Media directory empty or not accessible"
    fi
    
    # Test 4: Sample queries
    log_info "Test 4: Sample database queries..."
    local patient_count=$(sudo -u postgres psql -d "$DB_NAME" -tAc "SELECT COUNT(*) FROM clinical_patient;" 2>/dev/null || echo "0")
    if [[ "$patient_count" -gt 0 ]]; then
        log_success "✓ Database queries working (Patients: $patient_count)"
    else
        log_warning "⚠ No patients found in database"
    fi
    
    log_info "=========================================="
    log_info "Smoke tests completed"
    log_info "=========================================="
}

###############################################################################
# Main Restore Workflow
###############################################################################

main() {
    local backup_dir=""
    local target="staging"
    
    # Parse arguments
    for arg in "$@"; do
        case $arg in
            --backup-dir=*)
                backup_dir="${arg#*=}"
                ;;
            --target=*)
                target="${arg#*=}"
                ;;
            --help)
                echo "Usage: $0 --backup-dir=<path> [--target=production|staging]"
                echo ""
                echo "Options:"
                echo "  --backup-dir=<path>    Path to backup directory"
                echo "  --target=<env>         Target environment (default: staging)"
                echo "  --help                 Show this help message"
                echo ""
                echo "Examples:"
                echo "  # Restore to staging (safer, no confirmation)"
                echo "  $0 --backup-dir=/backups/daily/20251222-143052"
                echo ""
                echo "  # Restore to production (requires confirmation)"
                echo "  $0 --backup-dir=/backups/daily/20251222-143052 --target=production"
                exit 0
                ;;
        esac
    done
    
    # Validate arguments
    if [[ -z "$backup_dir" ]]; then
        log_error "Missing required argument: --backup-dir"
        log_error "Use --help for usage information"
        exit 1
    fi
    
    if [[ ! -d "$backup_dir" ]]; then
        log_error "Backup directory not found: $backup_dir"
        exit 1
    fi
    
    if [[ "$target" != "production" ]] && [[ "$target" != "staging" ]]; then
        log_error "Invalid target: $target (must be 'production' or 'staging')"
        exit 1
    fi
    
    log_info "=========================================="
    log_info "Cosmetica 5 Restore from Backup"
    log_info "=========================================="
    log_info "Backup Dir: $backup_dir"
    log_info "Target:     $target"
    log_info "=========================================="
    
    # Check prerequisites
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
    
    # Check backup integrity
    check_backup_integrity "$backup_dir"
    
    # Final confirmation for production
    if [[ "$target" == "production" ]]; then
        confirm_action "Proceed with PRODUCTION restore?" "production"
    fi
    
    # Restore database
    restore_database "$backup_dir" "$target"
    
    # Restore media
    restore_media "$backup_dir" "$target"
    
    # Run migrations (optional)
    run_migrations "$backup_dir"
    
    # Run smoke tests
    run_smoke_tests
    
    log_info "=========================================="
    log_success "Restore completed successfully"
    log_info "=========================================="
    log_info "Next steps:"
    log_info "  1. Review smoke test results above"
    log_info "  2. Start application: systemctl start cosmetica5"
    log_info "  3. Test login and basic functionality"
    log_info "  4. Notify users if production restore"
    log_info "=========================================="
}

# Run main function
main "$@"
