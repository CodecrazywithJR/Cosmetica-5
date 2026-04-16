---
name: celery-worker
description: Use when designing or implementing Celery tasks, periodic jobs, retry strategies, result backends, task routing, and monitoring for Django applications.
license: MIT
metadata:
  author: Cosmetica-5 Team
  version: "1.0.0"
  domain: backend
  triggers: Celery, async task, periodic task, background job, task queue, Redis broker, retry, task routing, celery beat, worker
  role: specialist
  scope: implementation
  output-format: code
  related-skills: django-expert, devops-engineer
---

# Celery Worker

Celery task design specialist for Django applications with Redis broker.

## When to Use This Skill

- Designing background tasks (email, PDF generation, stock calculations)
- Implementing retry strategies for transient failures
- Configuring periodic tasks (celery beat)
- Task routing and priority queues
- Monitoring task execution and failures
- Handling task results and callbacks

## Core Workflow

1. **Identify the operation** — Is it I/O-bound? Takes >500ms? Can be async?
2. **Design the task** — Idempotent, serializable arguments, proper retry
3. **Choose the queue** — Default, priority, or dedicated
4. **Implement** — Task function with proper error handling
5. **Configure** — Routing, retry policy, rate limits
6. **Monitor** — Flower dashboard, logging, dead-letter handling

## Constraints

### MUST DO
- Make tasks **idempotent** — safe to retry/replay
- Pass only **serializable** arguments (IDs, strings, dicts) — never ORM objects
- Set explicit **time limits** (`soft_time_limit`, `time_limit`)
- Use **`autoretry_for`** with exponential backoff for transient errors
- Wrap DB operations in `transaction.atomic()`
- Log task start, completion, and failure with structured data
- Use `task_id` for deduplication when needed
- Handle `SoftTimeLimitExceeded` gracefully (cleanup, partial save)

### MUST NOT DO
- Pass Django model instances as arguments (not serializable across workers)
- Use `delay()` inside `transaction.atomic()` — task may run before commit
  - Use `transaction.on_commit(lambda: task.delay(id))` instead
- Ignore `max_retries` — infinite retries can exhaust resources
- Use `ALWAYS_EAGER = True` in production (testing only)
- Store large results in the result backend — use file storage
- Create tasks that depend on other tasks' completion without proper chaining

## Task Design Pattern

```python
# tasks.py
from celery import shared_task
from django.db import transaction

@shared_task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=5,
    soft_time_limit=300,
    time_limit=360,
)
def generate_patient_report(self, patient_id: int, report_type: str) -> dict:
    """Generate a patient report PDF asynchronously."""
    from apps.clinical.models import Patient

    patient = Patient.objects.get(id=patient_id)
    pdf_url = _build_report_pdf(patient, report_type)

    return {"patient_id": patient_id, "pdf_url": pdf_url}
```

## Safe Task Dispatch

```python
# WRONG — task may fire before DB commit
with transaction.atomic():
    patient = Patient.objects.create(...)
    generate_report.delay(patient.id)  # ❌ patient may not exist yet

# CORRECT — dispatch after commit
with transaction.atomic():
    patient = Patient.objects.create(...)
    transaction.on_commit(lambda: generate_report.delay(patient.id))  # ✅
```

## Periodic Tasks (Celery Beat)

```python
# config/celery.py
app.conf.beat_schedule = {
    'cleanup-expired-sessions': {
        'task': 'apps.clinical.tasks.cleanup_expired_sessions',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'generate-daily-reports': {
        'task': 'apps.sales.tasks.generate_daily_summary',
        'schedule': crontab(hour=6, minute=0),
    },
}
```

## Project-Specific Notes (Cosmetica 5)

- **Broker**: Redis 7 (Alpine) via Docker
- **Celery config**: `config/celery.py` with `os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')`
- **Current usage**: Minimal — mostly placeholder for future async operations
- **Potential tasks**: PDF consent generation, stock recalculation, email notifications, report generation
