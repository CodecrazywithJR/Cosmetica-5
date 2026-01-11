# Backup Scripts - Cosmetica 5

**Purpose**: Operational scripts for backup, restore, and migration procedures.

---

## Scripts Overview

### 1. `run_daily_backup.sh`

**Purpose**: Automated daily backup of database and media files.

**Usage**:
```bash
./run_daily_backup.sh [--verbose] [--label=<label>]
```

**Features**:
- ✅ Backs up PostgreSQL database (custom format)
- ✅ Backs up media files (tar.gz)
- ✅ Generates manifest with checksums
- ✅ Encrypts backups (optional, if password file exists)
- ✅ Copies to NAS (optional, if enabled)
- ✅ Cleans up old backups per retention policy
- ✅ Healthchecks.io integration (optional)

**Environment Variables**:
```bash
BACKUP_BASE_DIR=/backups                          # Base directory for backups
BACKUP_PASSWORD_FILE=/secure/backup_password.txt  # Encryption password
MEDIA_ROOT=/var/cosmetica5/media                  # Media files directory
DB_NAME=cosmetica5                                # Database name
DB_USER=postgres                                  # Database user
APP_DIR=/opt/cosmetica5                           # Application directory
NAS_MOUNT_PATH=/mnt/nas/cosmetica5-backups        # NAS mount point
NAS_ENABLED=false                                 # Enable NAS copy
BACKUP_RETENTION_DAYS=7                           # Daily retention
BACKUP_RETENTION_WEEKS=4                          # Weekly retention
BACKUP_RETENTION_MONTHS=12                        # Monthly retention
HEALTHCHECK_URL=https://hc-ping.com/your-uuid    # Healthchecks.io URL (optional)
```

**Cron Setup** (automated daily backups):
```bash
# Edit crontab
sudo crontab -e

# Add this line (runs at 2:00 AM daily)
0 2 * * * /opt/cosmetica5/scripts/backup/run_daily_backup.sh >> /var/log/cosmetica-backup.log 2>&1
```

**Example**:
```bash
# Manual backup with custom label
./run_daily_backup.sh --label=pre-migration

# Verbose output for debugging
./run_daily_backup.sh --verbose
```

**Output**:
- Backup directory: `/backups/daily/YYYYMMDD-HHMMSS-<git-commit>/`
- Files created:
  - `backup_manifest.json` - Metadata and checksums
  - `database.pgdump` (or `.pgdump.enc` if encrypted)
  - `media.tar.gz` (or `.tar.gz.enc` if encrypted)

---

### 2. `restore_from_backup.sh`

**Purpose**: Restore database and media files from backup.

**Usage**:
```bash
./restore_from_backup.sh --backup-dir=<path> [--target=production|staging]
```

**Features**:
- ✅ Verifies backup integrity (checksums)
- ✅ Decrypts files if encrypted
- ✅ Restores PostgreSQL database
- ✅ Restores media files
- ✅ Runs Django migrations (optional)
- ✅ Performs smoke tests
- ✅ Safety confirmations for production

**Options**:
- `--backup-dir=<path>` - Path to backup directory (required)
- `--target=production|staging` - Target environment (default: staging)

**Example**:
```bash
# Restore to staging (no confirmation required)
./restore_from_backup.sh --backup-dir=/backups/daily/20251222-143052

# Restore to production (requires confirmation)
./restore_from_backup.sh \
  --backup-dir=/backups/daily/20251222-143052 \
  --target=production
```

**Safety Features**:
- ✅ Checksums verified before restore
- ✅ Production requires typing "YES" to confirm
- ✅ Creates safety backup of existing media before overwrite
- ✅ Smoke tests run after restore

**Smoke Tests**:
1. Django system check
2. Database connection test
3. Media files accessible
4. Sample database queries

---

### 3. `make_migration_bundle.sh`

**Purpose**: Create comprehensive backup bundle before major version migrations.

**Usage**:
```bash
./make_migration_bundle.sh \
  --from-version=X.Y.Z \
  --to-version=A.B.C \
  [--reason="..."]
```

**Features**:
- ✅ Creates pre-migration snapshot (full backup)
- ✅ Generates git diff between versions
- ✅ Generates requirements.txt diff
- ✅ Creates migration checklist
- ✅ Creates migration plan template

**Options**:
- `--from-version=X.Y.Z` - Current version (required)
- `--to-version=A.B.C` - Target version (required)
- `--reason="..."` - Migration reason (optional)

**Example**:
```bash
./make_migration_bundle.sh \
  --from-version=1.2.3 \
  --to-version=1.3.0 \
  --reason="Add clinical media support"
```

**Output**:
```
/backups/migration-bundles/v1.2.3-to-v1.3.0/
├── pre-migration-snapshot/
│   ├── backup_manifest.json
│   ├── database.pgdump
│   ├── media.tar.gz
│   └── checksums.txt
├── documentation/
│   ├── git-diff.patch
│   └── requirements-diff.txt
├── migration-checklist.md
├── migration-plan.md
└── README.md
```

**Use Cases**:
- Before major version upgrades
- Before schema changes
- Before breaking changes
- Compliance/audit requirements

---

### 4. `verify_backup.sh`

**Purpose**: Verify integrity and completeness of backup files.

**Usage**:
```bash
./verify_backup.sh --backup-dir=<path> [--check-age] [--max-age-hours=<hours>] [--verbose]
```

**Features**:
- ✅ Verifies backup directory exists
- ✅ Validates manifest JSON
- ✅ Checks database backup exists and size > 0
- ✅ Checks media backup exists and size > 0
- ✅ Verifies checksums (SHA-256)
- ✅ Checks backup age (optional)
- ✅ Validates manifest completeness

**Options**:
- `--backup-dir=<path>` - Path to backup directory (required)
- `--check-age` - Verify backup age is acceptable
- `--max-age-hours=<hours>` - Maximum age in hours (default: 48)
- `--verbose` - Enable verbose output

**Example**:
```bash
# Verify specific backup
./verify_backup.sh --backup-dir=/backups/daily/20251222-143052

# Verify latest backup and check age
./verify_backup.sh \
  --backup-dir=/backups/daily/$(ls -t /backups/daily | head -1) \
  --check-age \
  --max-age-hours=24

# Verbose output
./verify_backup.sh \
  --backup-dir=/backups/daily/20251222-143052 \
  --verbose
```

**Exit Codes**:
- `0` - All checks passed
- `1` - One or more checks failed

**Automated Verification**:
```bash
# Add to cron (verify after backup)
0 3 * * * /opt/cosmetica5/scripts/backup/verify_backup.sh --backup-dir=/backups/daily/$(ls -t /backups/daily | head -1) --check-age >> /var/log/cosmetica-backup-verify.log 2>&1
```

---

## Setup Instructions

### Prerequisites

1. **Install Required Tools**:
   ```bash
   # PostgreSQL client (for pg_dump/pg_restore)
   sudo apt-get install postgresql-client
   
   # jq (for JSON parsing)
   sudo apt-get install jq
   
   # Optional: pigz (parallel gzip for faster compression)
   sudo apt-get install pigz
   
   # Optional: restic (for encrypted backups)
   sudo apt-get install restic
   ```

2. **Create Backup Directory**:
   ```bash
   sudo mkdir -p /backups/{daily,weekly,monthly,migration-bundles}
   sudo chown -R backup:backup /backups  # Or your backup user
   sudo chmod 700 /backups
   ```

3. **Create Secure Password File** (if using encryption):
   ```bash
   sudo mkdir -p /secure
   sudo chmod 700 /secure
   
   # Generate strong password
   openssl rand -base64 32 > /tmp/backup_password.txt
   
   # Move to secure location
   sudo mv /tmp/backup_password.txt /secure/backup_password.txt
   sudo chmod 600 /secure/backup_password.txt
   
   # Store password in password manager (1Password, Bitwarden)
   # DO NOT lose this password - cannot decrypt backups without it
   ```

4. **Configure Environment Variables**:
   ```bash
   # Create environment file
   sudo nano /etc/cosmetica5/backup.env
   
   # Add configuration
   export BACKUP_BASE_DIR=/backups
   export BACKUP_PASSWORD_FILE=/secure/backup_password.txt
   export MEDIA_ROOT=/var/cosmetica5/media
   export DB_NAME=cosmetica5
   export DB_USER=postgres
   export APP_DIR=/opt/cosmetica5
   export NAS_ENABLED=false
   
   # Secure the file
   sudo chmod 600 /etc/cosmetica5/backup.env
   ```

5. **Setup Cron Jobs**:
   ```bash
   sudo crontab -e
   
   # Add these lines:
   
   # Daily backup at 2:00 AM
   0 2 * * * source /etc/cosmetica5/backup.env && /opt/cosmetica5/scripts/backup/run_daily_backup.sh >> /var/log/cosmetica-backup.log 2>&1
   
   # Verify backup at 3:00 AM (1 hour after backup)
   0 3 * * * source /etc/cosmetica5/backup.env && /opt/cosmetica5/scripts/backup/verify_backup.sh --backup-dir=/backups/daily/$(ls -t /backups/daily | head -1) --check-age >> /var/log/cosmetica-backup-verify.log 2>&1
   
   # Weekly backup (keep Sunday's daily as weekly)
   0 4 * * 0 cp -r /backups/daily/$(ls -t /backups/daily | head -1) /backups/weekly/$(date +\%Y-W\%U)/
   
   # Monthly backup (keep 1st day's backup as monthly)
   0 4 1 * * cp -r /backups/daily/$(ls -t /backups/daily | head -1) /backups/monthly/$(date +\%Y-\%m)/
   ```

---

## NAS Configuration (Optional)

### Setup NAS Mount

1. **Mount NAS**:
   ```bash
   # Create mount point
   sudo mkdir -p /mnt/nas/cosmetica5-backups
   
   # Mount NAS (example: NFS)
   sudo mount -t nfs nas.local:/backups /mnt/nas/cosmetica5-backups
   
   # Add to /etc/fstab for auto-mount
   echo "nas.local:/backups /mnt/nas/cosmetica5-backups nfs defaults 0 0" | sudo tee -a /etc/fstab
   ```

2. **Enable NAS in Environment**:
   ```bash
   # Edit backup.env
   sudo nano /etc/cosmetica5/backup.env
   
   # Change:
   export NAS_ENABLED=true
   export NAS_MOUNT_PATH=/mnt/nas/cosmetica5-backups
   ```

3. **Test NAS Backup**:
   ```bash
   ./run_daily_backup.sh --verbose
   # Should see "Copying backup to NAS" in output
   
   # Verify files copied
   ls -lh /mnt/nas/cosmetica5-backups/
   ```

---

## Monitoring & Alerts

### Healthchecks.io Integration

1. **Create Account**: https://healthchecks.io
2. **Create Check**: "Cosmetica 5 Daily Backup"
3. **Copy Ping URL**
4. **Add to Environment**:
   ```bash
   export HEALTHCHECK_URL=https://hc-ping.com/your-uuid-here
   ```
5. **Test**:
   ```bash
   ./run_daily_backup.sh
   # Should ping healthchecks.io on success
   ```

### Log Monitoring

**View backup logs**:
```bash
# Backup execution log
sudo tail -f /var/log/cosmetica-backup.log

# Verification log
sudo tail -f /var/log/cosmetica-backup-verify.log

# System log (cron jobs)
sudo journalctl -u cron -f
```

**Alert on failures**:
```bash
# Install logwatch or similar tool
sudo apt-get install logwatch

# Configure email alerts for backup failures
```

---

## Troubleshooting

### Backup Fails with "Permission Denied"

**Solution**:
```bash
# Ensure backup user has correct permissions
sudo chown -R backup:backup /backups
sudo chmod 700 /backups

# Ensure backup script is executable
chmod +x /opt/cosmetica5/scripts/backup/*.sh
```

### Database Backup Fails

**Check**:
```bash
# Test database connection
sudo -u postgres psql -d cosmetica5 -c "SELECT 1;"

# Check if database exists
sudo -u postgres psql -l | grep cosmetica5

# Check disk space
df -h /backups
```

### Restore Checksum Mismatch

**Cause**: Corrupted backup file

**Solution**:
1. Use older backup
2. Restore from NAS copy
3. Check disk integrity: `fsck`

### Cannot Decrypt Backup

**Cause**: Password file missing or incorrect

**Solution**:
1. Retrieve password from password manager
2. Recreate `/secure/backup_password.txt`
3. Ensure file permissions: `chmod 600`

---

## Testing Procedures

### Monthly Restore Test

**Schedule**: First Sunday of each month

**Procedure**:
1. Select backup from 2 months ago
2. Restore to staging server
3. Run smoke tests
4. Document results

**Script**:
```bash
#!/bin/bash
# Monthly restore test

BACKUP_DIR=/backups/monthly/$(ls -t /backups/monthly | head -3 | tail -1)

echo "Testing restore from: $BACKUP_DIR"

./restore_from_backup.sh \
  --backup-dir="$BACKUP_DIR" \
  --target=staging

# Document results
echo "Test completed at $(date)" >> /var/log/restore-tests.log
```

---

## Related Documentation

- `docs/BACKUP_STRATEGY.md` - Comprehensive backup strategy
- `docs/PROJECT_DECISIONS.md` - Section 9.6 (Backup & Migration Strategy)
- `docs/decisions/ADR-006-clinical-media.md` - Clinical Media decisions

---

**Version**: 1.0  
**Last Updated**: 2025-12-22
