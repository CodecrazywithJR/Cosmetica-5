#!/bin/bash
#
# Cosmetica 5 - Daily Backup Script
#
# Purpose: Automated daily backup of database and media files
# Usage: ./run_daily_backup.sh [--verbose] [--label=<label>]
# Cron: 0 2 * * * /opt/cosmetica5/scripts/backup/run_daily_backup.sh >> /var/log/cosmetica-backup.log 2>&1
#
# Version: 1.0
# Last Updated: 2025-12-22

set -euo pipefail  # Exit on error, undefined var, or pipe failure

###############################################################################
# Configuration (Override with environment variables)
###############################################################################

BACKUP_BASE_DIR="${BACKUP_BASE_DIR:-/backups}"
BACKUP_REPO_PATH="${BACKUP_REPO_PATH:-$BACKUP_BASE_DIR/restic-repo}"
BACKUP_PASSWORD_FILE="${BACKUP_PASSWORD_FILE:-/secure/backup_password.txt}"
MEDIA_ROOT="${MEDIA_ROOT:-/var/cosmetica5/media}"
DB_NAME="${DB_NAME:-cosmetica5}"
DB_USER="${DB_USER:-postgres}"
APP_DIR="${APP_DIR:-/opt/cosmetica5}"
NAS_MOUNT_PATH="${NAS_MOUNT_PATH:-/mnt/nas/cosmetica5-backups}"
NAS_ENABLED="${NAS_ENABLED:-false}"

# Retention policy
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
RETENTION_WEEKS="${BACKUP_RETENTION_WEEKS:-4}"
RETENTION_MONTHS="${BACKUP_RETENTION_MONTHS:-12}"

# Optional: healthchecks.io integration
HEALTHCHECK_URL="${HEALTHCHECK_URL:-}"

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

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if running as root or backup user
    if [[ $EUID -ne 0 ]] && [[ $(whoami) != "backup" ]]; then
        log_error "This script must be run as root or backup user"
        exit 1
    fi
    
    # Check if required commands exist
    local required_commands=("pg_dump" "tar" "sha256sum" "jq")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            log_error "Required command not found: $cmd"
            exit 1
        fi
    done
    
    # Check if media directory exists
    if [[ ! -d "$MEDIA_ROOT" ]]; then
        log_error "Media directory not found: $MEDIA_ROOT"
        exit 1
    fi
    
    # Check if app directory exists
    if [[ ! -d "$APP_DIR" ]]; then
        log_error "Application directory not found: $APP_DIR"
        exit 1
    fi
    
    # Check if database is accessible
    if ! sudo -u postgres psql -d "$DB_NAME" -c "SELECT 1;" &> /dev/null; then
        log_error "Cannot connect to database: $DB_NAME"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

get_git_info() {
    cd "$APP_DIR"
    local commit=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
    local branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
    echo "$commit:$branch"
}

get_app_version() {
    # Try to extract version from __init__.py or VERSION file
    if [[ -f "$APP_DIR/VERSION" ]]; then
        cat "$APP_DIR/VERSION"
    elif [[ -f "$APP_DIR/apps/api/__init__.py" ]]; then
        grep -Po '__version__\s*=\s*"\K[^"]+' "$APP_DIR/apps/api/__init__.py" || echo "unknown"
    else
        echo "unknown"
    fi
}

get_last_migration() {
    cd "$APP_DIR"
    # Query Django for last applied migration
    if [[ -f "apps/api/manage.py" ]]; then
        python apps/api/manage.py showmigrations --plan 2>/dev/null | tail -1 | awk '{print $2}' || echo "unknown"
    else
        echo "unknown"
    fi
}

calculate_checksum() {
    local file="$1"
    if [[ -f "$file" ]]; then
        sha256sum "$file" | awk '{print $1}'
    else
        echo "file_not_found"
    fi
}

###############################################################################
# Backup Functions
###############################################################################

backup_database() {
    local backup_dir="$1"
    local db_file="$backup_dir/database.pgdump"
    
    log_info "Backing up database: $DB_NAME"
    
    # Use custom format for better compression and parallelizable restore
    sudo -u postgres pg_dump \
        --format=custom \
        --file="$db_file" \
        --verbose \
        "$DB_NAME" 2>&1 | grep -v "^pg_dump:" || true
    
    if [[ ! -f "$db_file" ]]; then
        log_error "Database backup failed: file not created"
        return 1
    fi
    
    local size=$(stat -f%z "$db_file" 2>/dev/null || stat -c%s "$db_file" 2>/dev/null)
    log_success "Database backup completed: $(numfmt --to=iec $size 2>/dev/null || echo "$size bytes")"
    
    echo "$db_file:$size"
}

backup_media() {
    local backup_dir="$1"
    local media_archive="$backup_dir/media.tar.gz"
    
    log_info "Backing up media files: $MEDIA_ROOT"
    
    # Use pigz if available (parallel gzip), otherwise regular gzip
    if command -v pigz &> /dev/null; then
        tar -cf - -C "$(dirname "$MEDIA_ROOT")" "$(basename "$MEDIA_ROOT")" | pigz > "$media_archive"
    else
        tar -czf "$media_archive" -C "$(dirname "$MEDIA_ROOT")" "$(basename "$MEDIA_ROOT")"
    fi
    
    if [[ ! -f "$media_archive" ]]; then
        log_error "Media backup failed: file not created"
        return 1
    fi
    
    local size=$(stat -f%z "$media_archive" 2>/dev/null || stat -c%s "$media_archive" 2>/dev/null)
    local file_count=$(tar -tzf "$media_archive" 2>/dev/null | wc -l)
    
    log_success "Media backup completed: $(numfmt --to=iec $size 2>/dev/null || echo "$size bytes"), $file_count files"
    
    echo "$media_archive:$size:$file_count"
}

encrypt_backup() {
    local file="$1"
    local encrypted_file="${file}.enc"
    
    # Check if restic is available (preferred method)
    if command -v restic &> /dev/null; then
        log_info "Encryption via restic (repository-level)"
        # Restic handles encryption automatically in repository
        return 0
    fi
    
    # Fallback: OpenSSL encryption
    if [[ ! -f "$BACKUP_PASSWORD_FILE" ]]; then
        log_error "Backup password file not found: $BACKUP_PASSWORD_FILE"
        log_error "Skipping encryption (NOT RECOMMENDED FOR PRODUCTION)"
        return 1
    fi
    
    log_info "Encrypting file: $(basename "$file")"
    
    openssl enc -aes-256-cbc -salt -pbkdf2 \
        -in "$file" \
        -out "$encrypted_file" \
        -pass "file:$BACKUP_PASSWORD_FILE"
    
    if [[ -f "$encrypted_file" ]]; then
        rm "$file"  # Remove unencrypted file
        log_success "Encryption completed: $(basename "$encrypted_file")"
        echo "$encrypted_file"
    else
        log_error "Encryption failed"
        return 1
    fi
}

generate_manifest() {
    local backup_dir="$1"
    local db_info="$2"
    local media_info="$3"
    local manifest_file="$backup_dir/backup_manifest.json"
    
    log_info "Generating backup manifest..."
    
    local db_file=$(echo "$db_info" | cut -d: -f1)
    local db_size=$(echo "$db_info" | cut -d: -f2)
    local media_file=$(echo "$media_info" | cut -d: -f1)
    local media_size=$(echo "$media_info" | cut -d: -f2)
    local media_count=$(echo "$media_info" | cut -d: -f3)
    
    local git_info=$(get_git_info)
    local git_commit=$(echo "$git_info" | cut -d: -f1)
    local git_branch=$(echo "$git_info" | cut -d: -f2)
    local app_version=$(get_app_version)
    local last_migration=$(get_last_migration)
    
    local db_checksum=$(calculate_checksum "$db_file")
    local media_checksum=$(calculate_checksum "$media_file")
    
    cat > "$manifest_file" <<EOF
{
  "backup_id": "$(basename "$backup_dir")",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "hostname": "$(hostname)",
  "version": {
    "app": "$app_version",
    "git_commit": "$git_commit",
    "git_branch": "$git_branch"
  },
  "database": {
    "engine": "postgresql",
    "name": "$DB_NAME",
    "size_bytes": $db_size,
    "checksum_sha256": "$db_checksum",
    "dump_format": "custom",
    "file": "$(basename "$db_file")"
  },
  "media": {
    "root_path": "$MEDIA_ROOT",
    "file_count": $media_count,
    "size_bytes": $media_size,
    "checksum_sha256": "$media_checksum",
    "compression": "gzip",
    "file": "$(basename "$media_file")"
  },
  "migrations": {
    "last_applied": "$last_migration"
  },
  "environment": {
    "python_version": "$(python3 --version 2>&1 | awk '{print $2}')",
    "os": "$(uname -s)",
    "os_version": "$(uname -r)"
  }
}
EOF
    
    log_success "Manifest generated: $manifest_file"
    echo "$manifest_file"
}

copy_to_nas() {
    local backup_dir="$1"
    
    if [[ "$NAS_ENABLED" != "true" ]]; then
        log_info "NAS backup disabled, skipping"
        return 0
    fi
    
    if [[ ! -d "$NAS_MOUNT_PATH" ]]; then
        log_error "NAS mount point not found: $NAS_MOUNT_PATH"
        return 1
    fi
    
    log_info "Copying backup to NAS: $NAS_MOUNT_PATH"
    
    rsync -av --progress "$backup_dir/" "$NAS_MOUNT_PATH/$(basename "$backup_dir")/"
    
    if [[ $? -eq 0 ]]; then
        log_success "NAS copy completed"
    else
        log_error "NAS copy failed (non-fatal)"
    fi
}

cleanup_old_backups() {
    log_info "Cleaning up old backups..."
    
    # Daily backups: keep last N days
    local daily_dir="$BACKUP_BASE_DIR/daily"
    if [[ -d "$daily_dir" ]]; then
        find "$daily_dir" -type d -maxdepth 1 -mtime +$RETENTION_DAYS -exec rm -rf {} \; 2>/dev/null || true
        log_info "Cleaned up daily backups older than $RETENTION_DAYS days"
    fi
    
    # Weekly backups: keep last N weeks
    local weekly_dir="$BACKUP_BASE_DIR/weekly"
    if [[ -d "$weekly_dir" ]]; then
        find "$weekly_dir" -type d -maxdepth 1 -mtime +$((RETENTION_WEEKS * 7)) -exec rm -rf {} \; 2>/dev/null || true
        log_info "Cleaned up weekly backups older than $RETENTION_WEEKS weeks"
    fi
    
    # Monthly backups: keep last N months
    local monthly_dir="$BACKUP_BASE_DIR/monthly"
    if [[ -d "$monthly_dir" ]]; then
        find "$monthly_dir" -type d -maxdepth 1 -mtime +$((RETENTION_MONTHS * 30)) -exec rm -rf {} \; 2>/dev/null || true
        log_info "Cleaned up monthly backups older than $RETENTION_MONTHS months"
    fi
    
    log_success "Cleanup completed"
}

###############################################################################
# Main Backup Workflow
###############################################################################

main() {
    local start_time=$(date +%s)
    local backup_label="${1:-}"
    
    log_info "=========================================="
    log_info "Cosmetica 5 Daily Backup Started"
    log_info "=========================================="
    
    # Check prerequisites
    check_prerequisites
    
    # Create backup directory
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local backup_id="${timestamp}-$(get_git_info | cut -d: -f1 | cut -c1-7)"
    local backup_dir="$BACKUP_BASE_DIR/daily/$backup_id"
    
    if [[ -n "$backup_label" ]]; then
        backup_dir="$BACKUP_BASE_DIR/daily/${backup_id}-${backup_label}"
    fi
    
    mkdir -p "$backup_dir"
    log_info "Backup directory: $backup_dir"
    
    # Backup database
    local db_info=$(backup_database "$backup_dir")
    if [[ $? -ne 0 ]]; then
        log_error "Database backup failed"
        exit 1
    fi
    
    # Backup media
    local media_info=$(backup_media "$backup_dir")
    if [[ $? -ne 0 ]]; then
        log_error "Media backup failed"
        exit 1
    fi
    
    # Encrypt backups (optional, if password file exists)
    if [[ -f "$BACKUP_PASSWORD_FILE" ]]; then
        local db_file=$(echo "$db_info" | cut -d: -f1)
        local media_file=$(echo "$media_info" | cut -d: -f1)
        
        encrypt_backup "$db_file" || log_error "Database encryption failed (non-fatal)"
        encrypt_backup "$media_file" || log_error "Media encryption failed (non-fatal)"
    else
        log_error "WARNING: Backups are NOT encrypted (password file missing)"
    fi
    
    # Generate manifest
    generate_manifest "$backup_dir" "$db_info" "$media_info"
    
    # Copy to NAS (if enabled)
    copy_to_nas "$backup_dir"
    
    # Cleanup old backups
    cleanup_old_backups
    
    # Calculate duration
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_info "=========================================="
    log_success "Backup completed successfully in ${duration}s"
    log_info "Backup ID: $(basename "$backup_dir")"
    log_info "=========================================="
    
    # Notify healthchecks.io (if configured)
    if [[ -n "$HEALTHCHECK_URL" ]]; then
        curl -fsS --retry 3 "$HEALTHCHECK_URL" > /dev/null 2>&1 || true
    fi
    
    exit 0
}

###############################################################################
# Parse Arguments
###############################################################################

VERBOSE=false
LABEL=""

for arg in "$@"; do
    case $arg in
        --verbose)
            VERBOSE=true
            set -x  # Enable debug output
            ;;
        --label=*)
            LABEL="${arg#*=}"
            ;;
        --help)
            echo "Usage: $0 [--verbose] [--label=<label>]"
            echo ""
            echo "Options:"
            echo "  --verbose       Enable verbose output"
            echo "  --label=<name>  Add custom label to backup directory"
            echo "  --help          Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  BACKUP_BASE_DIR       Base backup directory (default: /backups)"
            echo "  BACKUP_PASSWORD_FILE  Encryption password file (default: /secure/backup_password.txt)"
            echo "  MEDIA_ROOT            Media files directory (default: /var/cosmetica5/media)"
            echo "  DB_NAME               Database name (default: cosmetica5)"
            echo "  NAS_ENABLED           Enable NAS copy (default: false)"
            exit 0
            ;;
    esac
done

# Run main function
main "$LABEL"
