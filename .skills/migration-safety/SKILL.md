---
name: migration-safety
description: Use when creating, modifying, or reviewing Django migrations. Covers zero-downtime migration patterns, backward-compatible schema changes, data migration safety, migration squashing, and rollback strategies.
license: MIT
metadata:
  author: Cosmetica-5 Team
  version: "1.0.0"
  domain: database
  triggers: Django migration, makemigrations, migrate, schema change, data migration, zero-downtime, backward compatible, RunPython, AddField, AlterField, RemoveField
  role: specialist
  scope: implementation
  output-format: code
  related-skills: django-expert, postgresql-pro
---

# Migration Safety

Django migration safety specialist — zero-downtime patterns for production databases.

## When to Use This Skill

- Creating new migrations for model changes
- Reviewing existing migrations for safety
- Planning data migrations (RunPython)
- Adding NOT NULL fields to tables with data
- Renaming fields or models
- Removing fields or models safely
- Squashing migrations

## Core Workflow

1. **Plan the change** — What models change? What's the current table size?
2. **Classify safety** — SAFE / CAUTION / DANGEROUS (see table below)
3. **Write migration** — Use safe patterns, split if needed
4. **Test locally** — `makemigrations --check`, `sqlmigrate`, run on dev DB
5. **Review SQL** — `python manage.py sqlmigrate app_label migration_name`
6. **Deploy** — Apply on staging first, check lock time

## Safety Classification

```
SAFE (no table lock, instant):
  ✅ CreateModel
  ✅ AddField(null=True)
  ✅ AddField(default=...) — Django 4.x fills in Python, no DB default
  ✅ AddIndex (CONCURRENTLY on PostgreSQL)
  ✅ AlterField(null=True → null=True) — no-op at DB level
  ✅ RunSQL / RunPython (depends on content)

CAUTION (brief lock or full scan):
  ⚠️ AddField(null=False, default=...) — rewrite on old Django, Python-fill on 4.x
  ⚠️ AddConstraint(CheckConstraint) — validates all existing rows
  ⚠️ RemoveField — brief ACCESS EXCLUSIVE lock
  ⚠️ AlterField(null=True → null=False) — validates all rows
  ⚠️ RenameField — brief lock, but breaks code referencing old name

DANGEROUS (long lock, possible downtime):
  ❌ AlterField changing column type (e.g., varchar→int) — full rewrite
  ❌ AddField NOT NULL without default on old Django — full rewrite
  ❌ AddIndex (non-CONCURRENTLY) on large table — blocks writes
```

## Safe Patterns

### Adding a NOT NULL field to an existing table

```python
# Migration 1: Add nullable field
operations = [
    migrations.AddField(
        model_name='patient',
        name='country_code',
        field=models.CharField(max_length=2, null=True),
    ),
]

# Migration 2: Backfill data
def backfill_country(apps, schema_editor):
    Patient = apps.get_model('clinical', 'Patient')
    Patient.objects.filter(country_code__isnull=True).update(country_code='FR')

def reverse_backfill(apps, schema_editor):
    pass  # Cannot un-backfill

operations = [
    migrations.RunPython(backfill_country, reverse_backfill),
]

# Migration 3: Make NOT NULL
operations = [
    migrations.AlterField(
        model_name='patient',
        name='country_code',
        field=models.CharField(max_length=2, default='FR'),
    ),
]
```

### Renaming a field safely

```python
# Step 1: Add new field, copy data
# Step 2: Update code to use new field
# Step 3: Deploy code change
# Step 4: Drop old field in next release

# NEVER use RenameField in production — it renames the column instantly
# breaking any running old code instances during deploy
```

### Removing a field safely

```python
# Step 1: Stop writing to the field in code
# Step 2: Deploy code change
# Step 3: Remove field in next migration
# Step 4: Deploy migration

# The field must be unused before removal
```

## Data Migration Rules

```python
# ALWAYS provide reverse_code
migrations.RunPython(forward_func, reverse_func)

# ALWAYS use apps.get_model() — never import models directly
def forward_func(apps, schema_editor):
    Patient = apps.get_model('clinical', 'Patient')  # ✅
    # from apps.clinical.models import Patient  # ❌ NEVER

# ALWAYS batch large updates
def backfill_large_table(apps, schema_editor):
    Model = apps.get_model('app', 'Model')
    batch_size = 1000
    while Model.objects.filter(new_field__isnull=True).exists():
        ids = list(Model.objects.filter(new_field__isnull=True).values_list('id', flat=True)[:batch_size])
        Model.objects.filter(id__in=ids).update(new_field='default')
```

## Squashing Migrations

```bash
# Only squash when migration count becomes unwieldy (>20 per app)
python manage.py squashmigrations app_label 0001 0020

# After squashing:
# 1. Test the squashed migration on a fresh DB
# 2. Remove RunPython operations that are no longer relevant
# 3. Replace squashed migration on ALL environments before removing originals
```

## Project-Specific Notes (Cosmetica 5)

- **Django 4.2.8** — AddField with default is handled in Python (no table rewrite)
- **PostgreSQL 15** — supports CONCURRENTLY index creation
- **Multi-tenant**: Migrations apply to all tenants (shared schema)
- **Current state**: ~7 migrations per major app, no squashing needed yet
- **5 remaining SonarQube issues**: `null=True` on CharField in clinical/models.py — requires data migration to convert NULL→'' before removing `null=True`
