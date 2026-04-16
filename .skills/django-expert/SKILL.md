---
name: django-expert
description: Use when building or maintaining Django 4.x applications with Django REST Framework, custom User models, multi-tenant patterns, and PostgreSQL. Covers ORM optimization, migration safety, middleware, signals, management commands, admin customization, and production hardening.
license: MIT
metadata:
  author: Cosmetica-5 Team
  version: "1.0.0"
  domain: backend
  triggers: Django, DRF, ORM, migrations, middleware, signals, admin, management commands, queryset optimization, select_related, prefetch_related, Django views, serializers, permissions
  role: specialist
  scope: implementation
  output-format: code
  related-skills: drf-specialist, postgresql-pro, test-master
---

# Django Expert

Django 4.x specialist for production-grade applications with DRF, PostgreSQL, and multi-tenant patterns.

## When to Use This Skill

- Writing Django models, views, serializers, or middleware
- Optimizing ORM queries (N+1, select_related, prefetch_related)
- Creating or modifying migrations safely
- Implementing custom User models, managers, or querysets
- Building management commands
- Configuring Django admin for custom models
- Multi-tenant data isolation patterns
- Django signal design and pitfalls

## Core Workflow

1. **Understand the model layer** — Review models.py, managers, constraints, indexes
2. **Check migration safety** — Will this migration lock tables? Is it backward-compatible?
3. **Implement with ORM best practices** — Avoid N+1, use proper managers, respect tenant isolation
4. **Test with pytest-django** — Use `@pytest.mark.django_db`, fixtures, `APIClient`
5. **Validate** — `python manage.py check`, `python manage.py makemigrations --check`, `pytest`

## Constraints

### MUST DO
- Use `select_related()` for FK/OneToOne, `prefetch_related()` for M2M/reverse FK
- Always add `db_index=True` on fields used in WHERE/ORDER BY
- Use `Meta.constraints` for business rule enforcement at DB level
- Use `transaction.atomic()` for multi-model writes
- Use `F()` and `Q()` expressions instead of Python-side filtering
- Validate at model level (`clean()`, `full_clean()`) not just serializer level
- Use `get_user_model()` instead of importing User directly
- Use `reverse()` or `reverse_lazy()` for URL references
- Test with `@pytest.mark.django_db(transaction=True)` when testing constraints
- Always set `on_delete` explicitly on ForeignKey fields
- Use `TimeBasedModel` or equivalent for `created_at`/`updated_at` patterns

### MUST NOT DO
- Use `objects.all()` without filtering in views (performance + tenant leaks)
- Create circular imports between apps (use string references for FK)
- Put business logic in views — use model methods or services
- Use `migrate` in production without reviewing the SQL (`sqlmigrate`)
- Use `RunPython` migrations without a `reverse_code`
- Mix `filter()` chains when a single `Q()` expression is clearer
- Use `signals` for critical business logic (prefer explicit calls)
- Access `request.user` in model methods — pass user explicitly
- Use `null=True` on CharField/TextField (use `blank=True, default=""`)
- Ignore `related_name` on ForeignKey fields

## Migration Safety Rules

```
SAFE (no lock, no downtime):
  ✅ AddField with null=True
  ✅ AddField with default (Django 4.x handles in Python)
  ✅ CreateModel
  ✅ AddIndex (CONCURRENTLY on PostgreSQL)
  ✅ RunSQL for data backfill

UNSAFE (may lock table):
  ⚠️ AddField NOT NULL without default → full table rewrite
  ⚠️ AlterField changing type → full table rewrite
  ⚠️ RemoveField on large tables → brief lock
  ⚠️ AddConstraint with CHECK → full table scan

PATTERN for safe NOT NULL addition:
  1. AddField(null=True)
  2. RunPython(backfill data)
  3. AlterField(null=False, default=...)
```

## ORM Optimization Patterns

```python
# BAD: N+1 query
for patient in Patient.objects.all():
    print(patient.legal_entity.trade_name)  # 1 query per patient

# GOOD: select_related for FK
for patient in Patient.objects.select_related('legal_entity'):
    print(patient.legal_entity.trade_name)  # 1 query total

# GOOD: prefetch_related for reverse FK / M2M
encounters = Encounter.objects.prefetch_related('clinicalphoto_set')

# GOOD: Only fetch needed fields
Patient.objects.only('id', 'first_name', 'last_name', 'email')

# GOOD: Exists check without loading
if Patient.objects.filter(email=email).exists():
    raise ValidationError("Email already exists")

# GOOD: Bulk operations
Patient.objects.bulk_create([Patient(...), Patient(...)])
Patient.objects.filter(is_active=False).update(is_active=True)

# GOOD: Subquery instead of Python loop
from django.db.models import Subquery, OuterRef
latest_encounter = Encounter.objects.filter(
    patient=OuterRef('pk')
).order_by('-created_at').values('id')[:1]
patients = Patient.objects.annotate(last_encounter_id=Subquery(latest_encounter))
```

## Custom Manager Pattern

```python
class TenantManager(models.Manager):
    """Filter queryset by tenant (legal_entity)."""

    def get_queryset(self):
        return super().get_queryset().filter(
            legal_entity=get_current_tenant()
        )

    def for_tenant(self, legal_entity):
        return super().get_queryset().filter(legal_entity=legal_entity)
```

## Settings Best Practices

```python
# Use environment variables with sensible defaults
SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-production')
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1')
DATABASE_HOST = os.environ.get('DATABASE_HOST', 'localhost')

# Separate INSTALLED_APPS into sections
DJANGO_APPS = ['django.contrib.admin', ...]
THIRD_PARTY_APPS = ['rest_framework', 'corsheaders', ...]
LOCAL_APPS = ['apps.authz', 'apps.clinical', ...]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS
```

## Project-Specific Notes (Cosmetica 5)

- **Python 3.9** runtime — use `Optional[str]` not `str | None`, `from __future__ import annotations` or string literals for forward refs
- **Custom User**: `apps.authz.models.User` (email-based, no username)
- **Tenant model**: `apps.legal.models.LegalEntity` — every tenant-scoped model has `legal_entity` FK
- **TenantManager**: auto-filters by `legal_entity` — always be aware of tenant context
- **Settings**: single `config/settings.py` file (no env split)
- **Test runner**: `pytest` with `conftest.py` at root and `apps/api/tests/conftest.py`
