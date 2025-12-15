# Generated for clinical audit log implementation

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('clinical', '0002_business_rules_appointment_status_and_patient_required'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ClinicalAuditLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('action', models.CharField(
                    choices=[
                        ('create', 'Create'),
                        ('update', 'Update'),
                        ('delete', 'Delete')
                    ],
                    max_length=10
                )),
                ('entity_type', models.CharField(
                    choices=[
                        ('Encounter', 'Encounter'),
                        ('ClinicalPhoto', 'Clinical Photo'),
                        ('Consent', 'Consent'),
                        ('Appointment', 'Appointment')
                    ],
                    help_text='Type of clinical entity (Encounter, ClinicalPhoto, etc.)',
                    max_length=50
                )),
                ('entity_id', models.UUIDField(help_text='UUID of the entity that was changed')),
                ('metadata', models.JSONField(
                    default=dict,
                    help_text='Changed fields, before/after snapshots, request metadata'
                )),
                ('actor_user', models.ForeignKey(
                    blank=True,
                    help_text='User who performed the action (null for system actions)',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='clinical_audit_logs',
                    to=settings.AUTH_USER_MODEL
                )),
                ('appointment', models.ForeignKey(
                    blank=True,
                    help_text='Related appointment (if applicable)',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='audit_logs',
                    to='clinical.appointment'
                )),
                ('patient', models.ForeignKey(
                    blank=True,
                    help_text='Related patient (if applicable)',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='audit_logs',
                    to='clinical.patient'
                )),
            ],
            options={
                'verbose_name': 'Clinical Audit Log',
                'verbose_name_plural': 'Clinical Audit Logs',
                'db_table': 'clinical_audit_log',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='clinicalauditlog',
            index=models.Index(fields=['created_at'], name='idx_audit_created_at'),
        ),
        migrations.AddIndex(
            model_name='clinicalauditlog',
            index=models.Index(fields=['actor_user'], name='idx_audit_actor'),
        ),
        migrations.AddIndex(
            model_name='clinicalauditlog',
            index=models.Index(fields=['entity_type'], name='idx_audit_entity_type'),
        ),
        migrations.AddIndex(
            model_name='clinicalauditlog',
            index=models.Index(fields=['entity_id'], name='idx_audit_entity_id'),
        ),
        migrations.AddIndex(
            model_name='clinicalauditlog',
            index=models.Index(fields=['patient'], name='idx_audit_patient'),
        ),
        migrations.AddIndex(
            model_name='clinicalauditlog',
            index=models.Index(fields=['action'], name='idx_audit_action'),
        ),
    ]
