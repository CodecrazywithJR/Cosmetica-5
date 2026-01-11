#!/bin/bash
#
# Cosmetica 5 - Backup Verification Script
#
# Purpose: Verify integrity and completeness of backup files
# Usage: ./verify_backup.sh --backup-dir=<path> [--verbose]
#
# Version: 1.0
# Last Updated: 2025-12-22

set -euo pipefail

###############################################################################
# Configuration
###############################################################################

VERBOSE=false

###############################################################################
# Helper Functions
###############################################################################

log() {
    local level="$1"
    shift
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*"
}

log_info() {
    if [[ "$VERBOSE" == "true" ]]; then
        log "INFO" "$@"
    fi
}

log_error() {
    log "ERROR" "$@"
}

log_success() {
    log "SUCCESS" "$@"
}

log_check() {
    local status="$1"
    shift
    if [[ "$status" == "ok" ]]; then
        echo "[✓] $*"
    else
        echo "[✗] $*"
    fi
}

###############################################################################
# Verification Functions
###############################################################################

check_directory_exists() {
    local backup_dir="$1"
    
    if [[ ! -d "$backup_dir" ]]; then
        log_check "fail" "Backup directory not found: $backup_dir"
        return 1
    fi
    
    log_check "ok" "Backup directory exists: $backup_dir"
    return 0
}

check_manifest_exists() {
    local backup_dir="$1"
    local manifest_file="$backup_dir/backup_manifest.json"
    
    if [[ ! -f "$manifest_file" ]]; then
        log_check "fail" "Manifest file not found: $manifest_file"
        return 1
    fi
    
    # Validate JSON
    if ! jq empty "$manifest_file" 2>/dev/null; then
        log_check "fail" "Manifest file is not valid JSON: $manifest_file"
        return 1
    fi
    
    log_check "ok" "Manifest file exists and is valid JSON"
    return 0
}

check_database_backup() {
    local backup_dir="$1"
    local manifest_file="$backup_dir/backup_manifest.json"
    
    local db_file=$(jq -r '.database.file' "$manifest_file")
    local expected_checksum=$(jq -r '.database.checksum_sha256' "$manifest_file")
    local expected_size=$(jq -r '.database.size_bytes' "$manifest_file")
    local db_path="$backup_dir/$db_file"
    
    # Check if file exists (may be encrypted)
    if [[ ! -f "$db_path" ]] && [[ ! -f "${db_path}.enc" ]]; then
        log_check "fail" "Database backup file not found: $db_file"
        return 1
    fi
    
    # If encrypted, verify encrypted file
    if [[ -f "${db_path}.enc" ]]; then
        db_path="${db_path}.enc"
        log_info "Database backup is encrypted: $db_file.enc"
    fi
    
    # Check file size
    local actual_size=$(stat -f%z "$db_path" 2>/dev/null || stat -c%s "$db_path" 2>/dev/null)
    
    if [[ "$actual_size" -eq 0 ]]; then
        log_check "fail" "Database backup file is empty: $db_file"
        return 1
    fi
    
    log_check "ok" "Database backup file exists: $(basename "$db_path") ($(numfmt --to=iec $actual_size 2>/dev/null || echo "$actual_size bytes"))"
    
    # Verify checksum (skip if encrypted with .enc extension, as checksum is for unencrypted)
    if [[ "$db_path" != *.enc ]]; then
        log_info "Verifying database checksum..."
        local actual_checksum=$(sha256sum "$db_path" | awk '{print $1}')
        
        if [[ "$actual_checksum" != "$expected_checksum" ]]; then
            log_check "fail" "Database checksum mismatch!"
            log_error "Expected: $expected_checksum"
            log_error "Actual:   $actual_checksum"
            return 1
        fi
        
        log_check "ok" "Database checksum verified"
    else
        log_info "Skipping checksum verification for encrypted file"
    fi
    
    return 0
}

check_media_backup() {
    local backup_dir="$1"
    local manifest_file="$backup_dir/backup_manifest.json"
    
    local media_file=$(jq -r '.media.file' "$manifest_file")
    local expected_checksum=$(jq -r '.media.checksum_sha256' "$manifest_file")
    local expected_size=$(jq -r '.media.size_bytes' "$manifest_file")
    local expected_count=$(jq -r '.media.file_count' "$manifest_file")
    local media_path="$backup_dir/$media_file"
    
    # Check if file exists (may be encrypted)
    if [[ ! -f "$media_path" ]] && [[ ! -f "${media_path}.enc" ]]; then
        log_check "fail" "Media backup file not found: $media_file"
        return 1
    fi
    
    # If encrypted, verify encrypted file
    if [[ -f "${media_path}.enc" ]]; then
        media_path="${media_path}.enc"
        log_info "Media backup is encrypted: $media_file.enc"
    fi
    
    # Check file size
    local actual_size=$(stat -f%z "$media_path" 2>/dev/null || stat -c%s "$media_path" 2>/dev/null)
    
    if [[ "$actual_size" -eq 0 ]]; then
        log_check "fail" "Media backup file is empty: $media_file"
        return 1
    fi
    
    log_check "ok" "Media backup file exists: $(basename "$media_path") ($(numfmt --to=iec $actual_size 2>/dev/null || echo "$actual_size bytes"))"
    
    # Verify checksum (skip if encrypted)
    if [[ "$media_path" != *.enc ]]; then
        log_info "Verifying media checksum..."
        local actual_checksum=$(sha256sum "$media_path" | awk '{print $1}')
        
        if [[ "$actual_checksum" != "$expected_checksum" ]]; then
            log_check "fail" "Media checksum mismatch!"
            log_error "Expected: $expected_checksum"
            log_error "Actual:   $actual_checksum"
            return 1
        fi
        
        log_check "ok" "Media checksum verified"
    else
        log_info "Skipping checksum verification for encrypted file"
    fi
    
    # Verify file count (if not encrypted, can inspect tar)
    if [[ "$media_path" == *.tar.gz ]]; then
        log_info "Verifying media file count..."
        local actual_count=$(tar -tzf "$media_path" 2>/dev/null | wc -l)
        
        # Allow some tolerance (directories vs files)
        if [[ "$actual_count" -lt "$((expected_count - 10))" ]]; then
            log_check "fail" "Media file count mismatch!"
            log_error "Expected: ~$expected_count files"
            log_error "Actual:   $actual_count files"
            return 1
        fi
        
        log_check "ok" "Media file count verified: $actual_count files"
    fi
    
    return 0
}

check_backup_age() {
    local backup_dir="$1"
    local manifest_file="$backup_dir/backup_manifest.json"
    local max_age_hours="${2:-48}"  # Default 48 hours
    
    local backup_timestamp=$(jq -r '.timestamp' "$manifest_file")
    local backup_epoch=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$backup_timestamp" "+%s" 2>/dev/null || date -d "$backup_timestamp" "+%s" 2>/dev/null)
    local current_epoch=$(date "+%s")
    local age_seconds=$((current_epoch - backup_epoch))
    local age_hours=$((age_seconds / 3600))
    
    if [[ "$age_hours" -gt "$max_age_hours" ]]; then
        log_check "fail" "Backup is too old: $age_hours hours (max: $max_age_hours hours)"
        return 1
    fi
    
    log_check "ok" "Backup age: $age_hours hours (acceptable)"
    return 0
}

check_backup_completeness() {
    local backup_dir="$1"
    local manifest_file="$backup_dir/backup_manifest.json"
    
    log_info "Checking backup completeness..."
    
    # Check required fields in manifest
    local required_fields=(
        ".backup_id"
        ".timestamp"
        ".version.app"
        ".version.git_commit"
        ".database.file"
        ".database.size_bytes"
        ".database.checksum_sha256"
        ".media.file"
        ".media.size_bytes"
        ".media.checksum_sha256"
    )
    
    local missing_fields=0
    for field in "${required_fields[@]}"; do
        local value=$(jq -r "$field" "$manifest_file" 2>/dev/null)
        if [[ -z "$value" ]] || [[ "$value" == "null" ]]; then
            log_error "Missing required field in manifest: $field"
            missing_fields=$((missing_fields + 1))
        fi
    done
    
    if [[ "$missing_fields" -gt 0 ]]; then
        log_check "fail" "Backup manifest incomplete: $missing_fields missing fields"
        return 1
    fi
    
    log_check "ok" "Backup manifest is complete"
    return 0
}

display_backup_summary() {
    local backup_dir="$1"
    local manifest_file="$backup_dir/backup_manifest.json"
    
    echo ""
    echo "=========================================="
    echo "Backup Summary"
    echo "=========================================="
    echo "Backup ID:     $(jq -r '.backup_id' "$manifest_file")"
    echo "Timestamp:     $(jq -r '.timestamp' "$manifest_file")"
    echo "Hostname:      $(jq -r '.hostname' "$manifest_file")"
    echo "App Version:   $(jq -r '.version.app' "$manifest_file")"
    echo "Git Commit:    $(jq -r '.version.git_commit' "$manifest_file" | cut -c1-7)"
    echo "Last Migration: $(jq -r '.migrations.last_applied' "$manifest_file")"
    echo ""
    echo "Database:"
    echo "  Engine:      $(jq -r '.database.engine' "$manifest_file")"
    echo "  Size:        $(jq -r '.database.size_bytes' "$manifest_file" | numfmt --to=iec 2>/dev/null || jq -r '.database.size_bytes' "$manifest_file")"
    echo "  Format:      $(jq -r '.database.dump_format' "$manifest_file")"
    echo ""
    echo "Media:"
    echo "  File Count:  $(jq -r '.media.file_count' "$manifest_file")"
    echo "  Size:        $(jq -r '.media.size_bytes' "$manifest_file" | numfmt --to=iec 2>/dev/null || jq -r '.media.size_bytes' "$manifest_file")"
    echo "  Compression: $(jq -r '.media.compression' "$manifest_file")"
    echo "=========================================="
    echo ""
}

###############################################################################
# Main Verification Workflow
###############################################################################

main() {
    local backup_dir=""
    local check_age=false
    local max_age_hours=48
    
    # Parse arguments
    for arg in "$@"; do
        case $arg in
            --backup-dir=*)
                backup_dir="${arg#*=}"
                ;;
            --check-age)
                check_age=true
                ;;
            --max-age-hours=*)
                max_age_hours="${arg#*=}"
                check_age=true
                ;;
            --verbose)
                VERBOSE=true
                ;;
            --help)
                echo "Usage: $0 --backup-dir=<path> [options]"
                echo ""
                echo "Options:"
                echo "  --backup-dir=<path>      Path to backup directory (required)"
                echo "  --check-age              Verify backup age is acceptable"
                echo "  --max-age-hours=<hours>  Maximum age in hours (default: 48)"
                echo "  --verbose                Enable verbose output"
                echo "  --help                   Show this help message"
                echo ""
                echo "Examples:"
                echo "  # Verify specific backup"
                echo "  $0 --backup-dir=/backups/daily/20251222-143052"
                echo ""
                echo "  # Verify latest backup and check age"
                echo "  $0 --backup-dir=/backups/daily/\$(ls -t /backups/daily | head -1) --check-age"
                echo ""
                echo "Exit codes:"
                echo "  0 - All checks passed"
                echo "  1 - One or more checks failed"
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
    
    echo "=========================================="
    echo "Cosmetica 5 Backup Verification"
    echo "=========================================="
    echo "Backup Dir: $backup_dir"
    echo "=========================================="
    echo ""
    
    local all_checks_passed=true
    
    # Run all checks
    if ! check_directory_exists "$backup_dir"; then
        exit 1  # Fatal error
    fi
    
    if ! check_manifest_exists "$backup_dir"; then
        exit 1  # Fatal error
    fi
    
    if ! check_backup_completeness "$backup_dir"; then
        all_checks_passed=false
    fi
    
    if ! check_database_backup "$backup_dir"; then
        all_checks_passed=false
    fi
    
    if ! check_media_backup "$backup_dir"; then
        all_checks_passed=false
    fi
    
    if [[ "$check_age" == "true" ]]; then
        if ! check_backup_age "$backup_dir" "$max_age_hours"; then
            all_checks_passed=false
        fi
    fi
    
    # Display summary
    display_backup_summary "$backup_dir"
    
    # Final result
    echo "=========================================="
    if [[ "$all_checks_passed" == "true" ]]; then
        log_success "All verification checks passed ✓"
        echo "=========================================="
        exit 0
    else
        log_error "Some verification checks failed ✗"
        echo "=========================================="
        exit 1
    fi
}

# Run main function
main "$@"
