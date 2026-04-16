---
name: postgresql-pro
description: Use when working with PostgreSQL databases — query optimization, indexing strategy, migration safety, EXPLAIN ANALYZE, connection pooling, JSON fields, constraint design, and multi-tenant query patterns.
license: MIT
metadata:
  author: Cosmetica-5 Team
  version: "1.0.0"
  domain: database
  triggers: PostgreSQL, SQL, query optimization, indexes, EXPLAIN ANALYZE, migration, constraints, CHECK, UNIQUE, exclusion constraint, pg_dump, connection pool, database performance
  role: specialist
  scope: implementation
  output-format: code
  related-skills: django-expert, migration-safety
---

# PostgreSQL Pro

PostgreSQL specialist for production database design, optimization, and maintenance.

## When to Use This Skill

- Designing indexes for query performance
- Analyzing slow queries with EXPLAIN ANALYZE
- Creating database constraints (CHECK, UNIQUE, exclusion)
- Planning safe schema migrations
- Configuring connection pooling
- Multi-tenant data isolation at DB level
- Backup and restore strategies
- JSON/JSONB field design

## Core Workflow

1. **Analyze the query plan** — `EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)` on slow queries
2. **Design indexes** — B-tree for equality/range, GIN for arrays/JSONB/trigram, GiST for exclusion
3. **Add constraints** — Business rules enforced at DB level (CHECK, UNIQUE, exclusion)
4. **Test migration** — Run on staging first, check lock duration
5. **Monitor** — `pg_stat_statements`, `pg_stat_user_tables`, connection count

## Constraints

### MUST DO
- Use `EXPLAIN ANALYZE` before and after adding indexes
- Add indexes on all FK columns (Django does this by default)
- Use partial indexes for filtered queries (`WHERE is_active = true`)
- Use composite indexes for multi-column WHERE/ORDER BY
- Use `CONCURRENTLY` for index creation on production (via Django `AddIndex`)
- Use CHECK constraints for business rule validation
- Use exclusion constraints for time-range overlap prevention
- Set appropriate `work_mem` for complex queries
- Use `pg_dump --format=custom` for backups (supports parallel restore)
- Monitor connection count vs `max_connections`

### MUST NOT DO
- Create indexes on every column "just in case" (write penalty)
- Use `SELECT *` in production queries — specify columns
- Ignore `seq_scan` on large tables — likely missing index
- Use `TRUNCATE` without understanding cascade effects
- Modify `postgresql.conf` without understanding impact
- Use `advisory_lock` without careful design
- Ignore `dead_tuple` count — schedule `VACUUM ANALYZE`

## Index Strategy

```sql
-- FK index (Django auto-creates, verify with \di)
CREATE INDEX idx_patient_legal_entity ON clinical_patient(legal_entity_id);

-- Partial index for common filter
CREATE INDEX idx_appointment_active
ON clinical_appointment(practitioner_id, scheduled_start)
WHERE status NOT IN ('cancelled', 'no_show');

-- Composite index for multi-column queries
CREATE INDEX idx_sale_tenant_status
ON sales_sale(legal_entity_id, status, created_at DESC);

-- Trigram index for fuzzy search (requires pg_trgm)
CREATE INDEX idx_patient_name_trgm
ON clinical_patient USING gin(first_name gin_trgm_ops, last_name gin_trgm_ops);

-- GiST exclusion for time overlap prevention
ALTER TABLE clinical_appointment
ADD CONSTRAINT no_overlap_practitioner
EXCLUDE USING gist (
    practitioner_id WITH =,
    tstzrange(scheduled_start, scheduled_end) WITH &&
) WHERE (status NOT IN ('cancelled', 'no_show'));
```

## EXPLAIN ANALYZE Reading Guide

```
Key metrics to check:
  - Seq Scan on large tables → needs index
  - Nested Loop with many iterations → consider JOIN strategy
  - Sort with external disk → increase work_mem
  - Rows estimated vs actual → run ANALYZE
  - Buffers shared hit vs read → cache efficiency

Good: Index Scan, Index Only Scan, Bitmap Index Scan
Bad:  Seq Scan on >10K rows, Hash Join with huge outer table
```

## Connection Pooling

```
Production setup:
  - Use PgBouncer in transaction mode
  - Django CONN_MAX_AGE = 0 with PgBouncer (let PgBouncer manage)
  - Django CONN_MAX_AGE = 600 without PgBouncer (keep connections alive)
  - Monitor with: SELECT count(*) FROM pg_stat_activity;
```

## Multi-Tenant Patterns

```sql
-- Row-Level Security (RLS) for tenant isolation
ALTER TABLE clinical_patient ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON clinical_patient
    USING (legal_entity_id = current_setting('app.current_tenant')::int);

-- Or via Django Manager (current approach in Cosmetica 5):
-- TenantManager filters by legal_entity automatically
-- CRITICAL: Always verify .filter(legal_entity=...) is applied
-- Test: ensure cross-tenant queries return 0 rows
```

## Project-Specific Notes (Cosmetica 5)

- **PostgreSQL 15** (Alpine) via Docker
- **Multi-tenant**: `LegalEntity` FK on all tenant-scoped models, filtered via `TenantManager`
- **Exclusion constraint**: Used on Appointment for practitioner time slot overlap prevention
- **Trigram search**: Used in POS patient fuzzy search (`pg_trgm`)
- **Stock**: FEFO allocation queries rely on batch expiry ordering
- **Backup**: Manual `pg_dump` via docker-compose exec
- **No RLS** — isolation is at Django ORM level only
