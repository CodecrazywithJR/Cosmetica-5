# ADR-006: Clinical Media Storage (Phase 1)

**Status**: Accepted  
**Date**: 2025-12-22  
**Deciders**: Clinical Core Team  
**Tags**: clinical, media, storage, rbac, audit

## Context

Clinical practice requires documenting patient treatments visually through photographs taken before, during, and after procedures. These photos:

1. Are essential medical documentation requiring strict access control
2. Must be associated with specific consultations (temporal context)
3. Need audit trails (who uploaded, when, any deletions)
4. Cannot be publicly accessible without authentication
5. Must comply with data protection regulations (no PHI/PII in logs)

**Current State**: No clinical photo management system exists.

**Requirements**:
- Upload photos associated with Encounter (not just Patient)
- Strict RBAC: Practitioner access only to own encounters, ClinicalOps/Admin full access, Reception NO ACCESS
- Soft delete for audit trail (preserve files even when "deleted")
- File validation (type, size limits)
- Cannot upload to cancelled encounters
- Structured logging without PHI/PII leakage
- Local filesystem storage for single-clinic deployment

## Decision

### Architecture

**Model**: `ClinicalMedia`
- **Association**: ForeignKey to `Encounter` (NOT Patient directly)
  - Rationale: Photos document specific consultations, not just patient in general
  - Provides temporal context (date/time via encounter)
  - Enables RBAC filtering by practitioner-encounter relationship

- **Soft Delete**: `deleted_at` timestamp field
  - Rationale: Medical records require audit trail
  - Files preserved on disk even when "deleted" from UI
  - Custom QuerySet methods: `.active()` and `.deleted()`

- **Metadata**:
  - `media_type`: Initially 'photo' only (extensible for future types)
  - `category`: before/after/progress/other (clinical workflow)
  - `uploaded_by`: ForeignKey to User (audit trail)
  - `notes`: Optional clinical notes about the photo

### Storage

**Phase 1: Local Filesystem**
```python
upload_path = f"clinical_media/encounter_{encounter.id}/media_{media.id}.{ext}"
```

- Files stored in `MEDIA_ROOT/clinical_media/`
- Namespaced by encounter ID for organization
- **No public URLs**: Files served via authenticated endpoint only
- Access via `/api/v1/clinical/media/{id}/download/` with token/session auth

**Phase 2 (Future)**: Cloud Storage (S3/GCS)
- Deferred to avoid complexity for single-clinic deployment
- Migration path: Change Django storage backend only (no model changes)

### API Endpoints

```
POST   /api/v1/clinical/encounters/{id}/media/    # Upload
GET    /api/v1/clinical/encounters/{id}/media/    # List for encounter
DELETE /api/v1/clinical/media/{id}/                # Soft delete
GET    /api/v1/clinical/media/{id}/download/      # Serve file (authenticated)
```

### RBAC Implementation

**Permission Class**: `IsClinicalStaff` (blocks Reception)

**QuerySet Filtering**:
```python
if user.role == 'Practitioner':
    queryset.filter(encounter__practitioner=user)  # Own encounters only
elif user.role in ['Admin', 'ClinicalOps']:
    queryset.all()  # Full access
else:
    queryset.none()  # Blocked
```

**Upload Authorization**: Practitioner can only upload to encounters where `encounter.practitioner == request.user`

### Validations

**File Type**: Only `jpg`, `jpeg`, `png`, `webp` allowed
- Django `FileExtensionValidator` at model level
- Additional check in serializer for early rejection

**File Size**: Maximum 10MB per file
- Enforced in serializer `validate_file()` method
- Balance between quality and storage efficiency

**Encounter Status**: Cannot upload to `cancelled` encounters
- Prevents documentation of cancelled consultations
- Enforced in serializer `validate_encounter()` method

### Observability

**Structured Logging**:
```python
logger.info(
    "media_uploaded",
    media_id=media.id,          # ✅ UUID safe
    encounter_id=encounter.id,  # ✅ UUID safe
    user_id=request.user.id,    # ✅ UUID safe
    category=media.category,     # ✅ Enum value
    file_size_mb=media.file_size_mb  # ✅ Number
    # ❌ NO patient_name, NO email, NO file content
)
```

**Events Logged**:
- `media_uploaded`: File upload success
- `media_listed`: Encounter media listing
- `media_deleted`: Soft delete operation
- `media_downloaded`: File download (audit trail)

## Consequences

### Positive

✅ **Temporal Context**: Photos associated with specific consultations, not just patients  
✅ **Audit Trail**: Soft delete preserves all records and files  
✅ **Security**: No public URLs, authentication required for all access  
✅ **RBAC**: Strict practitioner boundaries enforced at QuerySet level  
✅ **Compliance**: No PHI/PII in logs, structured logging for audit  
✅ **Simplicity**: Local storage avoids S3 complexity for single-clinic  
✅ **Extensibility**: Easy migration to cloud storage later (change storage backend only)

### Negative

⚠️ **Storage Cost**: Files stored on application server (disk usage grows)  
⚠️ **Scalability**: Not suitable for multi-region deployment (local filesystem)  
⚠️ **Backup**: Server backup must include `MEDIA_ROOT` directory  
⚠️ **Performance**: File serving via Django (slower than CDN, but acceptable for single clinic)

### Risks

**Risk 1**: Disk space exhaustion  
**Mitigation**: Monitor disk usage, implement cleanup policy for old deleted files (future)

**Risk 2**: File corruption or loss  
**Mitigation**: Include `MEDIA_ROOT` in backup strategy, verify backups regularly

**Risk 3**: Download performance at scale  
**Mitigation**: Phase 2 migration to S3/CDN when clinic grows

## Implementation Notes

### Model Changes

**New Model**: `apps.encounters.models_media.ClinicalMedia`
- Located in separate file for maintainability
- Imported in `models.py` via `__all__`

**Modified Model**: `apps.encounters.models.Encounter`
- Added `practitioner` ForeignKey (nullable for backward compatibility)
- Required for RBAC filtering

### Migration Strategy

**Migration 1**: `0002_clinical_media.py`
- Add `practitioner` field to Encounter (nullable)
- Create ClinicalMedia table
- Create indexes: encounter+created_at, uploaded_by+created_at, deleted_at

**Data Migration** (if needed): Populate `encounter.practitioner` from existing data

### Testing Requirements

✅ **Model Tests**: Soft delete, QuerySet methods, file_size_mb property  
✅ **API Tests**: Upload, list, delete, download endpoints  
✅ **RBAC Tests**: Practitioner boundaries, Reception blocked, Admin full access  
✅ **Validation Tests**: File type rejection, size limit, cancelled encounter block  
✅ **Error Handling**: File not found, permission denied

### Documentation Updates

- ✅ ADR-006-clinical-media.md (this document)
- ⏳ Update `CLINICAL_CORE.md` with Clinical Media section
- ⏳ Update `STABILITY.md` with implementation status

## Alternatives Considered

### Alternative 1: Associate Media with Patient (Not Encounter)

**Rejected**:
- Loses temporal context (when was photo taken?)
- Requires separate date field (duplicates encounter scheduled_at)
- RBAC more complex (practitioner-patient relationship less clear)

### Alternative 2: Cloud Storage (S3) from Day 1

**Rejected for Phase 1**:
- Adds complexity (AWS credentials, bucket management)
- Cost for single-clinic deployment not justified
- Local storage sufficient for MVP
- Can migrate later without model changes

### Alternative 3: Hard Delete

**Rejected**:
- Medical records require audit trail
- Cannot prove compliance if records disappear
- Recovery impossible if accidental deletion

### Alternative 4: Public Media URLs with Signed Tokens

**Rejected**:
- More complex than authenticated endpoint
- Token expiration management adds complexity
- Authenticated endpoint simpler for Phase 1

## References

- [Django ImageField Documentation](https://docs.djangoproject.com/en/4.2/ref/models/fields/#imagefield)
- [DRF File Upload](https://www.django-rest-framework.org/api-guide/parsers/#fileuploadparser)
- [GDPR Technical Measures](https://gdpr-info.eu/art-32-gdpr/)
- Medical Records Retention Guidelines (varies by jurisdiction)

## Related Decisions

- **ADR-001**: Django + DRF stack selection
- **ADR-002**: PostgreSQL as primary database
- **ADR-003**: RBAC implementation with User.role field
- **PROJECT_DECISIONS.md Section 9**: Clinical Core Architecture

## Review Schedule

**Next Review**: 2026-03-22 (3 months)  
**Triggers for Review**:
- Multi-clinic deployment planned
- Storage costs exceed threshold
- Performance issues reported
- Cloud migration considered
