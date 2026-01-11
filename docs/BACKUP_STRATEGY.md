# Backup & Migration Strategy - Cosmetica 5

**Version**: 1.0  
**Last Updated**: 2025-12-22  
**Status**: Production Ready

---

## Table of Contents

1. [Objectives](#objectives)
2. [What Gets Backed Up](#what-gets-backed-up)
3. [Backup Architecture](#backup-architecture)
4. [Security & Encryption](#security--encryption)
5. [Retention Policy](#retention-policy)
6. [Backup Procedures](#backup-procedures)
7. [Restore Procedures](#restore-procedures)
8. [Migration Procedures](#migration-procedures)
9. [Verification & Testing](#verification--testing)
10. [Troubleshooting](#troubleshooting)

---

## Objectives

### Primary Goals

1. **Disaster Recovery**: Restore system after catastrophic failure (hardware, ransomware, corruption)
2. **Migration Enablement**: Create portable bundles for moving to new servers or ERP versions
3. **Audit Trail**: Maintain historical snapshots for compliance/forensics
4. **Data Protection**: Safeguard PHI/PII with encryption and access controls

### Key Metrics

- **RPO (Recovery Point Objective)**: Max 24 hours data loss
- **RTO (Recovery Time Objective)**: < 4 hours to restore production
- **Backup Window**: < 30 minutes for daily backup execution
- **Storage Efficiency**: Compressed backups ~40-60% of raw data size

---

## What Gets Backed Up

### 1. Database (PostgreSQL)

**Contents**:
- All tables (clinical, sales, stock, auth)
- Sequences and indexes
- Views and materialized views (if any)
- Database schema metadata

**Format**:
```bash
# Option A: Custom format (recommended - faster restore, parallelizable)
pg_dump --format=custom --file=db_backup.pgdump cosmetica5

# Option B: Plain SQL (human-readable, larger file)
pg_dump --format=plain --file=db_backup.sql cosmetica5 | gzip > db_backup.sql.gz
```

**Size Estimate**: 
- Empty DB: ~10 MB
- After 1 year (500 patients, 2000 encounters): ~500 MB
- After 5 years: ~2-3 GB

**Excluded**: 
- ❌ Session data (ephemeral)
- ❌ Cache tables (regenerable)

### 2. Media Files (MEDIA_ROOT)

**Contents**:
```
media/
├── clinical_media/
│   ├── encounter_<uuid>/
│   │   ├── media_<uuid>.jpg
│   │   ├── media_<uuid>.png
│   │   └── ...
│   └── ...
├── documents/          # If clinical documents exist
└── avatars/            # User profile pictures (optional)
```

**Method**:
```bash
# Tar + gzip (simple)
tar -czf media_backup.tar.gz media/

# Restic (encrypted, deduplicated)
restic backup media/ --tag=daily
```

**Size Estimate**:
- Per photo: 1-5 MB (average 2.5 MB)
- 100 encounters/month × 3 photos = 300 photos/month = 750 MB/month
- After 1 year: ~9 GB
- After 5 years: ~45 GB

### 3. Backup Manifest

**Purpose**: Metadata for verification and migration

**Contents** (`backup_manifest.json`):
```json
{
  "backup_id": "20251222-143052-a3f9c1b",
  "timestamp": "2025-12-22T14:30:52Z",
  "hostname": "cosmetica-prod-01",
  "version": {
    "app": "1.2.3",
    "git_commit": "a3f9c1b4e8d2f7c1a9b3e5d7f2c8a4b6",
    "git_branch": "main"
  },
  "database": {
    "engine": "postgresql",
    "version": "14.5",
    "name": "cosmetica5",
    "size_bytes": 524288000,
    "checksum_sha256": "abc123...",
    "dump_format": "custom"
  },
  "media": {
    "root_path": "/var/cosmetica5/media",
    "file_count": 1523,
    "size_bytes": 2147483648,
    "checksum_sha256": "def456...",
    "compression": "gzip"
  },
  "migrations": {
    "last_applied": "encounters.0002_clinical_media",
    "all_migrations": [
      "clinical.0001_initial",
      "encounters.0001_initial",
      "encounters.0002_clinical_media",
      "..."
    ]
  },
  "environment": {
    "python_version": "3.9.16",
    "django_version": "4.2.8",
    "drf_version": "3.14.0"
  },
  "checksums": {
    "database_file": "sha256:abc123...",
    "media_archive": "sha256:def456...",
    "manifest": "sha256:self-referential-removed"
  }
}
```

**Generation**:
```bash
python scripts/backup/generate_manifest.py > backup_manifest.json
```

### 4. Configuration Templates (Optional)

**Included** (sanitized):
- `requirements.txt` (Python dependencies)
- `package.json` / `package-lock.json` (Frontend dependencies)
- `.env.example` (configuration template WITHOUT secrets)
- Nginx config snippets (if custom)

**Excluded**:
- ❌ `.env` (contains secrets - NEVER backup)
- ❌ SSL certificates (managed separately)
- ❌ API keys, tokens, passwords

---

## Backup Architecture

### Storage Tiers

```
┌─────────────────────────────────────────────────────────┐
│                    Production Server                     │
│  ┌─────────────┐        ┌──────────────┐               │
│  │  PostgreSQL │        │  MEDIA_ROOT  │               │
│  └──────┬──────┘        └───────┬──────┘               │
│         │                       │                        │
│         └───────────┬───────────┘                        │
│                     ▼                                    │
│         ┌────────────────────────┐                      │
│         │  Backup Script (cron)  │                      │
│         └────────────┬───────────┘                      │
└──────────────────────┼──────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────┐
        │  Tier 1: Local Backup Directory  │
        │  /backups/daily/                 │
        │  Retention: 7 days               │
        └──────────────┬───────────────────┘
                       │ (rsync/copy)
                       ▼
        ┌──────────────────────────────────┐
        │  Tier 2: NAS / External Drive    │
        │  /mnt/nas/backups/               │
        │  Retention: 4 weeks + 12 months  │
        └──────────────┬───────────────────┘
                       │ (manual weekly)
                       ▼
        ┌──────────────────────────────────┐
        │  Tier 3: Offsite (Optional)      │
        │  Physical external drive         │
        │  Stored at owner's home/bank     │
        │  Retention: 12 months            │
        └──────────────────────────────────┘
```

### Directory Structure

```
/backups/
├── daily/
│   ├── 20251222-143052/
│   │   ├── backup_manifest.json
│   │   ├── database.pgdump
│   │   ├── media.tar.gz.enc          # Encrypted
│   │   └── checksums.txt
│   ├── 20251221-143015/
│   └── ...                            # Last 7 days
├── weekly/
│   ├── 2025-W51/                      # ISO week number
│   └── ...                            # Last 4 weeks
├── monthly/
│   ├── 2025-12/
│   └── ...                            # Last 12 months
└── migration-bundles/
    ├── v1.2.3-to-v1.3.0/
    │   ├── pre-migration-snapshot/
    │   └── migration-checklist.md
    └── ...
```

---

## Security & Encryption

### Encryption Strategy

**Tool**: `restic` (preferred) or `borg` backup

**Why Restic?**
- ✅ AES-256-GCM encryption built-in
- ✅ Deduplication (saves space for incremental backups)
- ✅ Cryptographic integrity checks
- ✅ Cross-platform (Linux, macOS, Windows)
- ✅ Supports multiple backends (local, NAS, S3)

**Alternative (if restic unavailable)**:
```bash
# Manual encryption with openssl
tar -czf - media/ | openssl enc -aes-256-cbc -salt -pbkdf2 -out media.tar.gz.enc
```

### Password Management

**DO**:
- ✅ Store backup password in password manager (1Password, Bitwarden)
- ✅ Document password location in runbook (not the password itself)
- ✅ Use strong password (min 20 chars, random)
- ✅ Share password securely with authorized personnel only

**DON'T**:
- ❌ Hardcode password in scripts
- ❌ Store password in git repo
- ❌ Store password in plain text file on server
- ❌ Use same password as database password

**Example**:
```bash
# ✅ CORRECT: Read from secure location
export RESTIC_PASSWORD=$(cat /secure/backup_password.txt)

# ❌ WRONG: Hardcoded
export RESTIC_PASSWORD="MyPassword123"
```

### Access Controls

**Backup Files**:
- Owner: `root` or `backup` user
- Permissions: `600` (owner read/write only)
- Group: No group access

**Backup Scripts**:
- Owner: `root`
- Permissions: `700` (owner execute only)

**NAS/External Drive**:
- Encrypted filesystem (LUKS, FileVault)
- Auto-unmount after backup completes
- Physical security (locked server room)

### GDPR/HIPAA Compliance

**Requirements**:
- ✅ Encryption at rest (AES-256)
- ✅ Encryption in transit (if network transfer)
- ✅ Access logs for backup access
- ✅ Deletion capability (for patient data removal requests)
- ✅ Data retention policy enforced

**Audit Trail**:
```bash
# Log all backup operations
logger -t cosmetica-backup "Backup started by $USER at $(date)"
# Logs go to /var/log/syslog or journalctl
```

---

## Retention Policy

### Schedule

| Type | Frequency | Retention | Storage Location | Notes |
|------|-----------|-----------|------------------|-------|
| **Daily** | Every night at 2 AM | 7 days | Local + NAS | Automated |
| **Weekly** | Every Sunday 2 AM | 4 weeks | NAS | Automated (keep Sunday daily) |
| **Monthly** | 1st of month 2 AM | 12 months | NAS + Offsite | Automated + manual offsite |
| **Migration** | Before major upgrade | Until next migration | NAS | Manual trigger |

### Automated Cleanup

```bash
# Daily backups: Delete older than 7 days
find /backups/daily/ -type d -mtime +7 -exec rm -rf {} \;

# Weekly backups: Delete older than 28 days
find /backups/weekly/ -type d -mtime +28 -exec rm -rf {} \;

# Monthly backups: Delete older than 365 days
find /backups/monthly/ -type d -mtime +365 -exec rm -rf {} \;
```

### Storage Capacity Planning

**Estimated Growth** (assuming 100 encounters/month):
- Year 1: ~15 GB (DB: 500 MB, Media: 9 GB, overhead: 5 GB)
- Year 5: ~50 GB (DB: 3 GB, Media: 45 GB, overhead: 2 GB)

**Recommended Storage**:
- **Local (Tier 1)**: 100 GB SSD (fast for recent backups)
- **NAS (Tier 2)**: 500 GB - 1 TB HDD (capacity for 2-3 years)
- **Offsite (Tier 3)**: 1 TB external drive (annual full backups)

---

## Backup Procedures

### Daily Backup (Automated)

**Trigger**: Cron job at 2:00 AM every night

**Script**: `scripts/backup/run_daily_backup.sh`

**Execution**:
```bash
# Crontab entry
0 2 * * * /opt/cosmetica5/scripts/backup/run_daily_backup.sh >> /var/log/cosmetica-backup.log 2>&1
```

**Steps** (automated):
1. Create timestamped backup directory
2. Dump PostgreSQL database
3. Archive media files
4. Generate manifest with checksums
5. Encrypt archives (if restic/borg available)
6. Copy to NAS/external drive
7. Verify checksums
8. Clean up old backups
9. Send notification (email/Slack if configured)

**Expected Duration**: 10-30 minutes (depends on data size)

**Monitoring**:
- Check `/var/log/cosmetica-backup.log` for errors
- Verify backup directory size is reasonable
- Automated alert if backup fails (optional: healthchecks.io integration)

### Weekly Backup

**Trigger**: Sunday 2:00 AM (keep daily backup as weekly)

**Action**: Copy Sunday's daily backup to `weekly/` directory

```bash
# In cron: Run on Sunday only
0 2 * * 0 cp -r /backups/daily/$(date +\%Y\%m\%d-*)/ /backups/weekly/$(date +\%Y-W\%U)/
```

### Monthly Backup

**Trigger**: 1st of month at 2:00 AM

**Action**: Copy 1st day's backup to `monthly/` directory

```bash
# In cron: Run on 1st day of month
0 2 1 * * cp -r /backups/daily/$(date +\%Y\%m\%d-*)/ /backups/monthly/$(date +\%Y-\%m)/
```

**Manual Offsite Copy** (quarterly):
1. Copy monthly backup to external drive
2. Physically transport to secure offsite location
3. Document in backup log

### Pre-Migration Backup

**Trigger**: Manual, before major version upgrade

**Script**: `scripts/backup/make_migration_bundle.sh`

**Steps**:
1. Tag current version in git
2. Run full backup
3. Export current migration state
4. Create migration checklist
5. Store in `migration-bundles/v{old}-to-v{new}/`

**Example**:
```bash
./scripts/backup/make_migration_bundle.sh --from-version=1.2.3 --to-version=1.3.0
```

---

## Restore Procedures

### Full System Restore (Disaster Recovery)

**Scenario**: Server failed, need to restore everything from backup

**Prerequisites**:
- New server (or repaired server) with OS installed
- PostgreSQL installed
- Python/Django environment setup
- Access to backup files

**Procedure**:

#### Step 1: Prepare Environment
```bash
# 1. Clone codebase
git clone https://github.com/your-org/cosmetica5.git /opt/cosmetica5
cd /opt/cosmetica5

# 2. Checkout correct version (from manifest)
git checkout <commit-hash-from-manifest>

# 3. Install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Create .env file (use backed up template + secrets from password manager)
cp .env.example .env
nano .env  # Fill in DB credentials, SECRET_KEY, etc.
```

#### Step 2: Restore Database
```bash
# 1. Create empty database
sudo -u postgres createdb cosmetica5

# 2. Restore from backup
# Option A: Custom format
pg_restore --dbname=cosmetica5 --username=postgres /path/to/backup/database.pgdump

# Option B: Plain SQL
gunzip < /path/to/backup/database.sql.gz | psql cosmetica5

# 3. Verify restoration
psql cosmetica5 -c "SELECT COUNT(*) FROM clinical_patient;"
psql cosmetica5 -c "SELECT COUNT(*) FROM encounters_encounter;"
```

#### Step 3: Restore Media Files
```bash
# 1. Create media directory
sudo mkdir -p /var/cosmetica5/media
sudo chown www-data:www-data /var/cosmetica5/media

# 2. Extract media archive
# Option A: Plain tar.gz
cd /var/cosmetica5
sudo tar -xzf /path/to/backup/media.tar.gz

# Option B: Encrypted
openssl enc -aes-256-cbc -d -pbkdf2 -in /path/to/backup/media.tar.gz.enc | tar -xz

# Option C: Restic
restic restore <snapshot-id> --target /var/cosmetica5/media/

# 3. Verify files
ls -lh /var/cosmetica5/media/clinical_media/
# Should see encounter directories with photos
```

#### Step 4: Run Migrations (if needed)
```bash
# Check current migration state
python manage.py showmigrations

# Apply any pending migrations (should be none if backup is recent)
python manage.py migrate --no-input
```

#### Step 5: Verify System Health
```bash
# 1. Django system check
python manage.py check --deploy

# 2. Test database connection
python manage.py dbshell
# Try: SELECT 1;

# 3. Test media file access
python manage.py shell
>>> from apps.encounters.models import ClinicalMedia
>>> ClinicalMedia.objects.first().file.path
# Should return valid file path

# 4. Start development server (test)
python manage.py runserver 0.0.0.0:8000
# Visit: http://localhost:8000/api/health/
```

#### Step 6: Smoke Tests
```bash
# 1. API health check
curl http://localhost:8000/api/health/
# Expected: {"status": "ok"}

# 2. Login test
curl -X POST http://localhost:8000/api/auth/login/ \
  -d '{"username":"admin","password":"..."}'
# Expected: {"token":"..."}

# 3. Query test
curl -H "Authorization: Token <token>" \
  http://localhost:8000/api/v1/clinical/patients/?limit=10
# Expected: List of patients

# 4. Media download test
curl -H "Authorization: Token <token>" \
  http://localhost:8000/api/v1/clinical/media/1/download/ \
  --output test_download.jpg
# Expected: Downloaded image file
```

#### Step 7: Production Deployment
```bash
# 1. Configure Nginx/Gunicorn
sudo systemctl start cosmetica5
sudo systemctl start nginx

# 2. Verify production
curl https://clinic.example.com/api/health/

# 3. Notify users
# Send email: "System restored, please login and verify your data"
```

**Expected Duration**: 2-4 hours (depends on data size and team familiarity)

### Partial Restore (Specific Data)

#### Restore Single Patient's Photos

**Scenario**: Accidentally deleted patient's photos, need to restore from backup

```bash
# 1. Find backup containing the photos
restic snapshots | grep "2025-12-20"

# 2. List contents
restic ls <snapshot-id> | grep "encounter_<uuid>"

# 3. Restore specific directory
restic restore <snapshot-id> \
  --target /tmp/restore/ \
  --include="media/clinical_media/encounter_<uuid>/"

# 4. Copy restored files to production
sudo cp -r /tmp/restore/media/clinical_media/encounter_<uuid>/ \
  /var/cosmetica5/media/clinical_media/
```

#### Restore Deleted Patient Record (Database)

**Scenario**: Patient deleted (hard delete), need to restore from backup

```bash
# 1. Dump specific table from backup
pg_restore --dbname=temp_restore /path/to/backup.pgdump \
  --table=clinical_patient

# 2. Export deleted patient
psql temp_restore -c "COPY (SELECT * FROM clinical_patient WHERE id='<uuid>') TO STDOUT CSV HEADER" > patient.csv

# 3. Import to production
psql cosmetica5 -c "COPY clinical_patient FROM STDIN CSV HEADER" < patient.csv
```

---

## Migration Procedures

### Pre-Migration Checklist

**Before upgrading to new version**:

- [ ] Create migration bundle (`make_migration_bundle.sh`)
- [ ] Document current version (git commit, Django migrations)
- [ ] Export production data statistics (patient count, encounter count)
- [ ] Test migration in staging with restored backup
- [ ] Schedule maintenance window (2-4 hours)
- [ ] Notify users of downtime
- [ ] Backup current `.env` file (separately, not in git)

### Migration Bundle Creation

**Script**: `scripts/backup/make_migration_bundle.sh`

```bash
./scripts/backup/make_migration_bundle.sh \
  --from-version=1.2.3 \
  --to-version=1.3.0 \
  --reason="Add clinical media support"
```

**Creates**:
```
/backups/migration-bundles/v1.2.3-to-v1.3.0/
├── pre-migration-snapshot/
│   ├── backup_manifest.json
│   ├── database.pgdump
│   ├── media.tar.gz.enc
│   └── checksums.txt
├── migration-checklist.md
├── git-diff.patch                    # Code changes between versions
├── requirements-diff.txt             # Dependency changes
└── migration-plan.md                 # Step-by-step plan
```

### Migration Staging Test

**Steps**:

1. **Restore backup to staging server**:
   ```bash
   # Follow "Full System Restore" procedure in staging environment
   ./scripts/backup/restore_from_backup.sh \
     --backup-dir=/backups/migration-bundles/v1.2.3-to-v1.3.0/pre-migration-snapshot/ \
     --target=staging
   ```

2. **Checkout new version**:
   ```bash
   git fetch
   git checkout v1.3.0
   ```

3. **Install new dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run migrations**:
   ```bash
   python manage.py migrate --plan  # Dry run
   python manage.py migrate
   ```

5. **Verify data integrity**:
   ```bash
   # Check counts match
   psql cosmetica5 -c "SELECT COUNT(*) FROM clinical_patient;"
   # Compare to pre-migration count from manifest
   
   # Check new tables exist
   psql cosmetica5 -c "\dt encounters_clinicalmedia"
   ```

6. **Run tests**:
   ```bash
   pytest tests/ -v
   ```

7. **Smoke test UI**:
   - Login
   - View patient list
   - View encounter
   - Upload test photo (if new feature)

8. **Document issues and rollback plan**

### Production Migration

**Procedure**:

1. **Maintenance Mode**:
   ```bash
   # Stop application
   sudo systemctl stop cosmetica5
   
   # Put up maintenance page (Nginx)
   sudo cp /etc/nginx/maintenance.html /var/www/html/index.html
   sudo systemctl reload nginx
   ```

2. **Final Backup**:
   ```bash
   ./scripts/backup/run_daily_backup.sh --label=pre-migration
   ```

3. **Deploy New Version**:
   ```bash
   cd /opt/cosmetica5
   git fetch
   git checkout v1.3.0
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Run Migrations**:
   ```bash
   python manage.py migrate --no-input
   ```

5. **Collect Static Files** (if frontend changes):
   ```bash
   python manage.py collectstatic --no-input
   ```

6. **Start Application**:
   ```bash
   sudo systemctl start cosmetica5
   sudo systemctl status cosmetica5
   ```

7. **Smoke Tests** (see Step 6 in Restore Procedures)

8. **Remove Maintenance Page**:
   ```bash
   sudo rm /var/www/html/index.html
   sudo systemctl reload nginx
   ```

9. **Monitor Logs**:
   ```bash
   sudo journalctl -u cosmetica5 -f
   tail -f /var/log/nginx/error.log
   ```

10. **Notify Users**:
    - Send email: "System upgraded to v1.3.0, new features available"

### Rollback Procedure

**If migration fails**:

1. **Stop Application**:
   ```bash
   sudo systemctl stop cosmetica5
   ```

2. **Restore Pre-Migration Backup**:
   ```bash
   ./scripts/backup/restore_from_backup.sh \
     --backup-dir=/backups/migration-bundles/v1.2.3-to-v1.3.0/pre-migration-snapshot/
   ```

3. **Checkout Old Version**:
   ```bash
   git checkout v1.2.3
   pip install -r requirements.txt
   ```

4. **Start Application**:
   ```bash
   sudo systemctl start cosmetica5
   ```

5. **Verify Rollback**:
   ```bash
   curl http://localhost:8000/api/health/
   ```

6. **Document Issue**:
   - Log what went wrong
   - Plan fix for next attempt

---

## Verification & Testing

### Automated Verification (After Each Backup)

**Script**: `scripts/backup/verify_backup.sh`

**Checks**:
1. ✅ Backup directory exists and is not empty
2. ✅ Manifest file present and valid JSON
3. ✅ Database dump file exists and size > 0
4. ✅ Media archive exists and size > 0
5. ✅ Checksums match (SHA-256 validation)
6. ✅ Backup completed within expected time window

**Output**:
```
[✓] Backup directory: /backups/daily/20251222-143052/
[✓] Manifest file: backup_manifest.json (valid JSON)
[✓] Database dump: database.pgdump (524 MB, checksum OK)
[✓] Media archive: media.tar.gz.enc (2.1 GB, checksum OK)
[✓] Backup age: 5 minutes (acceptable)
[✓] All checks passed
```

**Failure Action**:
- Send alert (email/Slack)
- Log detailed error
- Retry backup once (if transient failure)

### Monthly Restore Test

**Frequency**: First Sunday of each month

**Procedure**:

1. **Spin up staging server** (or use existing)
2. **Select random monthly backup** (e.g., 2 months ago)
3. **Run full restore procedure** (see Restore section)
4. **Verify data integrity**:
   - Patient count matches manifest
   - Encounter count matches manifest
   - Random sample of 10 media files download successfully
5. **Smoke test**:
   - Login works
   - Patient list loads
   - Encounter view loads
   - Photo download works
6. **Document results**:
   - Time taken
   - Issues encountered
   - Success/failure status

**Expected Duration**: 1-2 hours

**Success Criteria**:
- ✅ Restore completes without errors
- ✅ Data counts match manifest
- ✅ All smoke tests pass
- ✅ No data corruption detected

### Quarterly Disaster Recovery Drill

**Frequency**: Every 3 months

**Scope**: Full disaster simulation

**Scenario**:
> "Production server suffered hardware failure. Restore from latest backup to new server."

**Steps**:
1. Provision new server (cloud VM or physical)
2. Install OS and dependencies
3. Restore latest daily backup
4. Complete all smoke tests
5. Time the entire process
6. Document lessons learned

**Target**: Complete within 4 hours (RTO compliance)

---

## Troubleshooting

### Backup Script Fails

**Symptom**: Cron job exits with error

**Check**:
```bash
# 1. Check logs
tail -100 /var/log/cosmetica-backup.log

# 2. Check disk space
df -h /backups/

# 3. Check database connection
psql -U postgres -c "SELECT 1;"

# 4. Check permissions
ls -la /backups/

# 5. Run backup manually (verbose)
sudo /opt/cosmetica5/scripts/backup/run_daily_backup.sh --verbose
```

**Common Issues**:
- **Disk full**: Clean up old backups, increase storage
- **Database locked**: Wait for long-running query to finish
- **Permission denied**: Check script has `chmod +x`, user has write access
- **Network timeout**: Check NAS is mounted, network stable

### Restore Fails with Migration Errors

**Symptom**: `python manage.py migrate` fails after restore

**Diagnosis**:
```bash
# Check migration status
python manage.py showmigrations

# Check backup manifest for migration state
cat backup_manifest.json | jq '.migrations'
```

**Fix**:
- If backup is older version: Checkout matching git commit before migrate
- If migration conflict: Manually resolve (fake migrations if needed)
  ```bash
  python manage.py migrate --fake encounters 0001
  python manage.py migrate encounters
  ```

### Media Files Missing After Restore

**Symptom**: API returns 404 for photo downloads

**Check**:
```bash
# 1. Verify media directory exists
ls -la /var/cosmetica5/media/clinical_media/

# 2. Check file permissions
sudo chown -R www-data:www-data /var/cosmetica5/media/

# 3. Verify MEDIA_ROOT in settings
python manage.py shell
>>> from django.conf import settings
>>> settings.MEDIA_ROOT

# 4. Check database references
psql cosmetica5 -c "SELECT file FROM encounters_clinicalmedia LIMIT 5;"
```

**Fix**:
- If files missing: Re-extract media archive
- If permissions wrong: Fix with `chown`
- If path mismatch: Update `.env` file with correct MEDIA_ROOT

### Backup Takes Too Long

**Symptom**: Backup exceeds 30-minute window, impacts production

**Diagnosis**:
```bash
# Time each component
time pg_dump --format=custom --file=/tmp/test.pgdump cosmetica5
time tar -czf /tmp/test.tar.gz media/
```

**Optimizations**:
1. **Database**: Use `--jobs=4` for parallel dump
   ```bash
   pg_dump --format=directory --jobs=4 --file=db_backup/ cosmetica5
   ```
2. **Media**: Use `pigz` (parallel gzip)
   ```bash
   tar -cf - media/ | pigz > media.tar.gz
   ```
3. **Incremental**: Switch to restic/borg (only backup changed files)
4. **Offload**: Run backup on replica/standby server (if available)

### Encryption Password Lost

**Symptom**: Cannot decrypt backup, password not found

**Prevention**:
- ✅ Store password in multiple secure locations (password manager + printed copy in safe)
- ✅ Document password location in runbook
- ✅ Require 2-person knowledge (admin + owner)

**Recovery**:
- If encrypted with restic/borg: Password recovery NOT possible (by design)
- If encrypted with openssl: Attempt password guessing with variations
- **LAST RESORT**: Restore from older unencrypted backup (if exists)

**Lesson**: Regular restore tests verify password works

---

## Appendix

### Environment Variables

**Required**:
```bash
# Backup configuration
BACKUP_REPO_PATH=/backups/restic-repo        # Restic repository path
BACKUP_PASSWORD=<from-password-manager>       # Encryption password (DO NOT COMMIT)
BACKUP_RETENTION_DAYS=7                       # Daily retention
BACKUP_RETENTION_WEEKS=4                      # Weekly retention
BACKUP_RETENTION_MONTHS=12                    # Monthly retention

# Database
DATABASE_URL=postgresql://user:pass@localhost/cosmetica5
DB_NAME=cosmetica5
DB_USER=postgres

# Media
MEDIA_ROOT=/var/cosmetica5/media

# NAS (optional)
NAS_MOUNT_PATH=/mnt/nas/cosmetica5-backups
NAS_ENABLED=true
```

### Backup Script Templates

See:
- `scripts/backup/run_daily_backup.sh` - Main backup script
- `scripts/backup/restore_from_backup.sh` - Restore script
- `scripts/backup/make_migration_bundle.sh` - Migration bundle creator
- `scripts/backup/verify_backup.sh` - Verification script

### Related Documentation

- `docs/PROJECT_DECISIONS.md` - Section 9.6 (Backup Strategy)
- `docs/decisions/ADR-006-clinical-media.md` - Clinical Media decisions
- `CLINICAL_CORE.md` - Clinical Media implementation
- `docs/STABILITY.md` - System stability status

---

**Version History**:
- **v1.0** (2025-12-22): Initial documentation
