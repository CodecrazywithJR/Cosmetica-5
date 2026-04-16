"""
Data migration: transition existing proposals to new status system.

- status == 'converted' → 'accepted'
- accepted_at = converted_at  (if converted_at is set)
- valid_until = created_at + 30 days  (for all rows)
"""
from datetime import timedelta
from django.db import migrations


def migrate_statuses_forward(apps, schema_editor):
    Proposal = apps.get_model('proposals', 'Proposal')

    for proposal in Proposal.objects.all():
        changed = False

        # 1. converted → accepted
        if proposal.status == 'converted':
            proposal.status = 'accepted'
            proposal.accepted_at = proposal.converted_at
            changed = True

        # 2. Set valid_until = created_at + 30 days (if not already set)
        if not proposal.valid_until and proposal.created_at:
            proposal.valid_until = proposal.created_at + timedelta(days=30)
            changed = True

        if changed:
            proposal.save(update_fields=[
                f for f in ['status', 'accepted_at', 'valid_until']
                if getattr(proposal, f, None) is not None or f == 'status'
            ])


def migrate_statuses_backward(apps, schema_editor):
    """Reverse: accepted → converted, clear accepted_at/valid_until."""
    Proposal = apps.get_model('proposals', 'Proposal')

    for proposal in Proposal.objects.filter(status='accepted'):
        proposal.status = 'converted'
        proposal.accepted_at = None
        proposal.save(update_fields=['status', 'accepted_at'])


class Migration(migrations.Migration):
    dependencies = [
        ('proposals', '0002_add_lifecycle_fields'),
    ]

    operations = [
        migrations.RunPython(
            migrate_statuses_forward,
            migrate_statuses_backward,
        ),
    ]
