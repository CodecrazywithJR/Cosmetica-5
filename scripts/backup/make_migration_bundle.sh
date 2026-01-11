#!/bin/bash
#
# Cosmetica 5 - Migration Bundle Creator
#
# Purpose: Create a comprehensive backup bundle before major version migrations
# Usage: ./make_migration_bundle.sh --from-version=X.Y.Z --to-version=A.B.C [--reason="..."]
#
# Version: 1.0
# Last Updated: 2025-12-22

set -euo pipefail

###############################################################################
# Configuration
###############################################################################

BACKUP_BASE_DIR="${BACKUP_BASE_DIR:-/backups}"
APP_DIR="${APP_DIR:-/opt/cosmetica5}"

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

###############################################################################
# Migration Bundle Functions
###############################################################################

create_bundle_directory() {
    local from_version="$1"
    local to_version="$2"
    local bundle_dir="$BACKUP_BASE_DIR/migration-bundles/v${from_version}-to-v${to_version}"
    
    if [[ -d "$bundle_dir" ]]; then
        log_error "Migration bundle already exists: $bundle_dir"
        read -p "Overwrite? (y/N): " overwrite
        if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
            log_error "Bundle creation cancelled"
            exit 1
        fi
        rm -rf "$bundle_dir"
    fi
    
    mkdir -p "$bundle_dir/pre-migration-snapshot"
    mkdir -p "$bundle_dir/documentation"
    
    log_success "Bundle directory created: $bundle_dir"
    echo "$bundle_dir"
}

create_pre_migration_snapshot() {
    local bundle_dir="$1"
    local snapshot_dir="$bundle_dir/pre-migration-snapshot"
    
    log_info "Creating pre-migration snapshot..."
    
    # Run daily backup script
    if [[ -f "$APP_DIR/scripts/backup/run_daily_backup.sh" ]]; then
        export BACKUP_BASE_DIR="$snapshot_dir"
        bash "$APP_DIR/scripts/backup/run_daily_backup.sh" --label=pre-migration
        
        # Move backup from daily subdirectory to snapshot root
        local backup_subdir=$(ls -t "$snapshot_dir/daily" | head -1)
        if [[ -n "$backup_subdir" ]]; then
            mv "$snapshot_dir/daily/$backup_subdir"/* "$snapshot_dir/"
            rm -rf "$snapshot_dir/daily"
        fi
    else
        log_error "Backup script not found: $APP_DIR/scripts/backup/run_daily_backup.sh"
        exit 1
    fi
    
    log_success "Pre-migration snapshot created"
}

generate_git_diff() {
    local bundle_dir="$1"
    local from_version="$2"
    local to_version="$3"
    local diff_file="$bundle_dir/documentation/git-diff.patch"
    
    log_info "Generating git diff between versions..."
    
    cd "$APP_DIR"
    
    # Try to generate diff between tags/branches
    if git diff "v${from_version}...v${to_version}" > "$diff_file" 2>/dev/null; then
        log_success "Git diff generated: $(wc -l < "$diff_file") lines"
    else
        log_error "Could not generate git diff (tags may not exist yet)"
        echo "# Git diff not available" > "$diff_file"
        echo "# Run: git diff v${from_version}...v${to_version}" >> "$diff_file"
    fi
}

generate_requirements_diff() {
    local bundle_dir="$1"
    local from_version="$2"
    local to_version="$3"
    local diff_file="$bundle_dir/documentation/requirements-diff.txt"
    
    log_info "Generating requirements diff..."
    
    cd "$APP_DIR"
    
    # Try to get requirements.txt from both versions
    if git show "v${from_version}:requirements.txt" > "/tmp/req_old.txt" 2>/dev/null; then
        if git show "v${to_version}:requirements.txt" > "/tmp/req_new.txt" 2>/dev/null; then
            diff -u /tmp/req_old.txt /tmp/req_new.txt > "$diff_file" || true
            log_success "Requirements diff generated"
        else
            echo "# New version requirements.txt not available" > "$diff_file"
        fi
    else
        echo "# Old version requirements.txt not available" > "$diff_file"
        log_error "Could not generate requirements diff (version tags may not exist)"
    fi
    
    rm -f /tmp/req_old.txt /tmp/req_new.txt
}

generate_migration_checklist() {
    local bundle_dir="$1"
    local from_version="$2"
    local to_version="$3"
    local reason="$4"
    local checklist_file="$bundle_dir/migration-checklist.md"
    
    log_info "Generating migration checklist..."
    
    cat > "$checklist_file" <<EOF
# Migration Checklist: v${from_version} → v${to_version}

**Created**: $(date '+%Y-%m-%d %H:%M:%S')  
**Reason**: ${reason}

---

## Pre-Migration

### Planning
- [ ] Review release notes for v${to_version}
- [ ] Read \`migration-plan.md\` (if exists)
- [ ] Review \`git-diff.patch\` for code changes
- [ ] Review \`requirements-diff.txt\` for dependency changes
- [ ] Identify breaking changes
- [ ] Schedule maintenance window (recommended: 2-4 hours)

### Communication
- [ ] Notify all users of planned downtime
- [ ] Notify users 48 hours in advance
- [ ] Send reminder 24 hours before
- [ ] Send final notice 1 hour before

### Testing
- [ ] Restore pre-migration snapshot to staging
- [ ] Test migration procedure in staging
- [ ] Run full test suite in staging
- [ ] Perform manual smoke tests in staging
- [ ] Document any issues encountered
- [ ] Verify rollback procedure works

### Backups
- [ ] Verify pre-migration snapshot exists: \`pre-migration-snapshot/\`
- [ ] Verify backup integrity (checksums)
- [ ] Copy backup to external drive (offsite)
- [ ] Test restore from backup (in staging)

---

## Migration Day

### Preparation
- [ ] Backup \`.env\` file separately (contains secrets)
- [ ] Stop monitoring/alerts temporarily
- [ ] Put up maintenance page
- [ ] Final communication to users

### Execution
- [ ] **STOP APPLICATION**: \`systemctl stop cosmetica5\`
- [ ] **BACKUP DATABASE**: Run final backup before migration
- [ ] **CHECKOUT NEW VERSION**: \`git checkout v${to_version}\`
- [ ] **INSTALL DEPENDENCIES**: \`pip install -r requirements.txt\`
- [ ] **RUN MIGRATIONS**: \`python manage.py migrate\`
- [ ] **COLLECT STATIC**: \`python manage.py collectstatic --no-input\`
- [ ] **START APPLICATION**: \`systemctl start cosmetica5\`

### Verification
- [ ] Check application logs: \`journalctl -u cosmetica5 -f\`
- [ ] Check Nginx logs: \`tail -f /var/log/nginx/error.log\`
- [ ] Run smoke tests (see checklist below)
- [ ] Verify database migration status: \`python manage.py showmigrations\`
- [ ] Test critical workflows (see below)

---

## Smoke Tests

### System Health
- [ ] API health endpoint: \`curl http://localhost:8000/api/health/\`
- [ ] Django system check: \`python manage.py check --deploy\`
- [ ] Database connection: \`psql cosmetica5 -c "SELECT 1;"\`

### Authentication
- [ ] Login as Admin
- [ ] Login as Practitioner
- [ ] Login as Reception

### Core Workflows
- [ ] View patient list
- [ ] View patient detail
- [ ] View encounter list
- [ ] View encounter detail
- [ ] Create new appointment
- [ ] Upload clinical photo (if new feature)

### Data Integrity
- [ ] Patient count matches pre-migration
- [ ] Encounter count matches pre-migration
- [ ] Media files accessible
- [ ] Random sample of 10 records checked

---

## Post-Migration

### Monitoring
- [ ] Monitor application logs for 24 hours
- [ ] Monitor error rates
- [ ] Monitor performance metrics
- [ ] Re-enable monitoring/alerts

### Communication
- [ ] Notify users migration completed
- [ ] Provide release notes / what's new
- [ ] Set up support channel for issues

### Documentation
- [ ] Document any issues encountered
- [ ] Document any manual fixes required
- [ ] Update runbook with lessons learned
- [ ] Archive this checklist with results

---

## Rollback Procedure

**If migration fails, follow these steps:**

1. **STOP APPLICATION**:
   \`\`\`bash
   systemctl stop cosmetica5
   \`\`\`

2. **RESTORE PRE-MIGRATION BACKUP**:
   \`\`\`bash
   ./scripts/backup/restore_from_backup.sh \\
     --backup-dir=$bundle_dir/pre-migration-snapshot/ \\
     --target=production
   \`\`\`

3. **CHECKOUT OLD VERSION**:
   \`\`\`bash
   cd /opt/cosmetica5
   git checkout v${from_version}
   pip install -r requirements.txt
   \`\`\`

4. **START APPLICATION**:
   \`\`\`bash
   systemctl start cosmetica5
   \`\`\`

5. **VERIFY ROLLBACK**:
   \`\`\`bash
   curl http://localhost:8000/api/health/
   \`\`\`

6. **NOTIFY USERS**:
   - Send email: "Migration rolled back, system restored to v${from_version}"

7. **DOCUMENT FAILURE**:
   - Log what went wrong
   - Plan fix for next attempt

---

## Migration Metadata

**Pre-Migration State**:
- Version: v${from_version}
- Git Commit: $(cd "$APP_DIR" && git rev-parse HEAD 2>/dev/null || echo "unknown")
- Database: $(cd "$APP_DIR" && python apps/api/manage.py showmigrations 2>/dev/null | tail -1 || echo "unknown")
- Backup Created: $(date '+%Y-%m-%d %H:%M:%S')

**Target State**:
- Version: v${to_version}
- Expected Duration: 2-4 hours
- Estimated Downtime: 1-2 hours

**Team Contacts**:
- Primary: [Name] - [Phone] - [Email]
- Backup: [Name] - [Phone] - [Email]
- Emergency: [Name] - [Phone]

---

## Notes

(Add any migration-specific notes here)

EOF
    
    log_success "Migration checklist created: $checklist_file"
}

generate_migration_plan() {
    local bundle_dir="$1"
    local from_version="$2"
    local to_version="$3"
    local reason="$4"
    local plan_file="$bundle_dir/documentation/migration-plan.md"
    
    log_info "Generating migration plan..."
    
    cat > "$plan_file" <<EOF
# Migration Plan: v${from_version} → v${to_version}

**Created**: $(date '+%Y-%m-%d %H:%M:%S')  
**Reason**: ${reason}  
**Target Date**: [TBD]

---

## Overview

This migration upgrades Cosmetica 5 from version ${from_version} to ${to_version}.

**Key Changes**:
- [List major changes here]
- [Example: New ClinicalMedia module for photo management]
- [Example: Database schema changes in encounters table]

**Risks**:
- [Identify potential risks]
- [Example: Migration may take longer if large dataset]
- [Example: Downtime required for schema changes]

**Mitigation**:
- [How to mitigate each risk]
- [Example: Test migration in staging with production data clone]
- [Example: Schedule migration during low-usage hours]

---

## Technical Details

### Database Migrations

**New Migrations**:
\`\`\`bash
# Run in staging first to see what migrations will apply
python manage.py migrate --plan
\`\`\`

**Expected Migrations** (based on git diff):
- [List expected migrations]
- [Example: encounters.0002_clinical_media - Add ClinicalMedia table]
- [Example: encounters.0003_encounter_practitioner - Add practitioner FK to Encounter]

### Dependency Changes

**New Packages**:
\`\`\`bash
# See requirements-diff.txt for details
diff requirements.txt
\`\`\`

**Breaking Changes**:
- [List any breaking changes in dependencies]
- [Example: Django upgraded from 4.2.7 to 4.2.8]

### Configuration Changes

**Environment Variables**:
- [List any new or changed env vars]
- [Example: MEDIA_ROOT must be set if not using default]

**Settings Changes**:
- [List any settings.py changes]
- [Example: INSTALLED_APPS includes new encounters app]

---

## Staging Test Results

**Test Date**: [TBD]  
**Test Environment**: [Staging server details]

**Test Procedure**:
1. Restore pre-migration snapshot to staging
2. Checkout v${to_version}
3. Install dependencies
4. Run migrations
5. Run test suite
6. Manual smoke tests

**Results**:
- [ ] Migrations completed successfully
- [ ] All tests passed
- [ ] Smoke tests passed
- [ ] Performance acceptable

**Issues Encountered**:
- [Document any issues found in staging]
- [Include workarounds/fixes]

---

## Production Migration Schedule

**Maintenance Window**: [Date/Time] to [Date/Time]  
**Expected Duration**: 2-4 hours  
**Expected Downtime**: 1-2 hours

**Timeline**:
- **T-0:00**: Stop application, put up maintenance page
- **T-0:15**: Run final backup
- **T-0:30**: Start migration (checkout, install, migrate)
- **T-1:00**: Start application, run smoke tests
- **T-1:30**: Remove maintenance page, notify users
- **T-2:00**: Monitor logs, ready for rollback if needed

**Team Availability**:
- [List team members and contact info]

---

## Communication Plan

**Pre-Migration** (48 hours before):
- Email to all users
- In-app notification (if available)
- Slack/Teams announcement

**During Migration**:
- Status page updates every 30 minutes
- Slack/Teams updates

**Post-Migration**:
- Email announcement: "Migration complete"
- Release notes sent to users
- Support channel open for questions

---

## Success Criteria

Migration is considered successful if:
- ✅ Application starts without errors
- ✅ All smoke tests pass
- ✅ Data counts match pre-migration
- ✅ No critical errors in logs for 2 hours
- ✅ Users can login and perform basic operations

---

## Rollback Criteria

Rollback is triggered if:
- ❌ Migration fails (error during \`migrate\` command)
- ❌ Application won't start after migration
- ❌ Critical smoke test failures
- ❌ Data corruption detected
- ❌ Critical errors in logs

**Rollback Procedure**: See \`migration-checklist.md\`

---

## Post-Migration Monitoring

**Monitor for 24-48 hours**:
- Application logs (\`journalctl -u cosmetica5 -f\`)
- Error rates (check for spikes)
- Performance metrics (response times)
- User reports (support tickets)

**Known Issues** (if any):
- [Document any known issues and workarounds]

---

## Lessons Learned

(Fill out after migration)

**What went well**:
-

**What could be improved**:
-

**Action items for next migration**:
-

EOF
    
    log_success "Migration plan created: $plan_file"
}

###############################################################################
# Main Workflow
###############################################################################

main() {
    local from_version=""
    local to_version=""
    local reason="Version upgrade"
    
    # Parse arguments
    for arg in "$@"; do
        case $arg in
            --from-version=*)
                from_version="${arg#*=}"
                ;;
            --to-version=*)
                to_version="${arg#*=}"
                ;;
            --reason=*)
                reason="${arg#*=}"
                ;;
            --help)
                echo "Usage: $0 --from-version=X.Y.Z --to-version=A.B.C [--reason=\"...\"]"
                echo ""
                echo "Options:"
                echo "  --from-version=X.Y.Z   Current version"
                echo "  --to-version=A.B.C     Target version"
                echo "  --reason=\"...\"         Migration reason (optional)"
                echo "  --help                 Show this help message"
                echo ""
                echo "Example:"
                echo "  $0 --from-version=1.2.3 --to-version=1.3.0 --reason=\"Add clinical media support\""
                exit 0
                ;;
        esac
    done
    
    # Validate arguments
    if [[ -z "$from_version" ]] || [[ -z "$to_version" ]]; then
        log_error "Missing required arguments: --from-version and --to-version"
        log_error "Use --help for usage information"
        exit 1
    fi
    
    log_info "=========================================="
    log_info "Migration Bundle Creator"
    log_info "=========================================="
    log_info "From: v${from_version}"
    log_info "To:   v${to_version}"
    log_info "Reason: ${reason}"
    log_info "=========================================="
    
    # Create bundle directory
    local bundle_dir=$(create_bundle_directory "$from_version" "$to_version")
    
    # Create pre-migration snapshot
    create_pre_migration_snapshot "$bundle_dir"
    
    # Generate documentation
    generate_git_diff "$bundle_dir" "$from_version" "$to_version"
    generate_requirements_diff "$bundle_dir" "$from_version" "$to_version"
    generate_migration_checklist "$bundle_dir" "$from_version" "$to_version" "$reason"
    generate_migration_plan "$bundle_dir" "$from_version" "$to_version" "$reason"
    
    # Create README
    cat > "$bundle_dir/README.md" <<EOF
# Migration Bundle: v${from_version} → v${to_version}

**Created**: $(date '+%Y-%m-%d %H:%M:%S')

## Contents

- \`pre-migration-snapshot/\` - Full backup taken before migration
  - \`backup_manifest.json\` - Backup metadata
  - \`database.pgdump\` - Database dump
  - \`media.tar.gz\` - Media files archive
  - \`checksums.txt\` - File checksums

- \`documentation/\` - Migration documentation
  - \`git-diff.patch\` - Code changes between versions
  - \`requirements-diff.txt\` - Dependency changes

- \`migration-checklist.md\` - Step-by-step checklist
- \`migration-plan.md\` - Detailed migration plan

## Usage

### Before Migration

1. Read \`migration-plan.md\`
2. Test migration in staging using \`pre-migration-snapshot/\`
3. Follow \`migration-checklist.md\`

### Rollback

If migration fails:

\`\`\`bash
./scripts/backup/restore_from_backup.sh \\
  --backup-dir=$bundle_dir/pre-migration-snapshot/ \\
  --target=production
\`\`\`

## Support

For questions or issues, contact: [Your team contact info]
EOF
    
    log_info "=========================================="
    log_success "Migration bundle created successfully!"
    log_info "=========================================="
    log_info "Location: $bundle_dir"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Review migration-checklist.md"
    log_info "  2. Review migration-plan.md"
    log_info "  3. Test migration in staging"
    log_info "  4. Schedule production migration"
    log_info "=========================================="
}

# Run main function
main "$@"
