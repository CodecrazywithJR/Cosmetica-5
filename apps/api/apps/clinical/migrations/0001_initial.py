# Generated migration for clinical app - DOMAIN_MODEL.md implementation

import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authz', '0001_initial'),
        ('core', '0001_initial'),
        ('documents', '0001_initial'),
    ]

    operations = [
        # ReferralSource
        migrations.CreateModel(
            name='ReferralSource',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('code', models.CharField(max_length=50, unique=True)),
                ('label', models.CharField(max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Referral Source',
                'verbose_name_plural': 'Referral Sources',
                'db_table': 'referral_source',
            },
        ),
        
        # Patient
        migrations.CreateModel(
            name='Patient',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('first_name', models.CharField(max_length=100)),
                ('last_name', models.CharField(max_length=100)),
                ('full_name_normalized', models.CharField(blank=True, max_length=255, null=True)),
                ('birth_date', models.DateField(blank=True, null=True)),
                ('sex', models.CharField(blank=True, choices=[('female', 'Female'), ('male', 'Male'), ('other', 'Other'), ('unknown', 'Unknown')], max_length=20, null=True)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('phone', models.CharField(blank=True, max_length=50, null=True)),
                ('phone_e164', models.CharField(blank=True, help_text='E.164 format', max_length=20, null=True)),
                ('address_line1', models.CharField(blank=True, max_length=255, null=True)),
                ('city', models.CharField(blank=True, max_length=100, null=True)),
                ('postal_code', models.CharField(blank=True, max_length=20, null=True)),
                ('country_code', models.CharField(blank=True, max_length=2, null=True)),
                ('preferred_language', models.CharField(blank=True, choices=[('ru', 'Russian'), ('fr', 'French'), ('en', 'English'), ('uk', 'Ukrainian'), ('hy', 'Armenian'), ('es', 'Spanish')], max_length=2, null=True)),
                ('preferred_contact_method', models.CharField(blank=True, choices=[('phone_call', 'Phone Call'), ('sms', 'SMS'), ('whatsapp', 'WhatsApp'), ('email', 'Email')], max_length=20, null=True)),
                ('preferred_contact_time', models.CharField(blank=True, max_length=255, null=True)),
                ('contact_opt_out', models.BooleanField(default=False)),
                ('identity_confidence', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], default='low', max_length=10)),
                ('is_merged', models.BooleanField(default=False)),
                ('merge_reason', models.TextField(blank=True, null=True)),
                ('referral_details', models.TextField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('row_version', models.IntegerField(default=1)),
                ('is_deleted', models.BooleanField(default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_patients', to=settings.AUTH_USER_MODEL)),
                ('deleted_by_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deleted_patients', to=settings.AUTH_USER_MODEL)),
                ('merged_into_patient', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='merged_patients', to='clinical.patient')),
                ('referral_source', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='patients', to='clinical.referralsource')),
            ],
            options={
                'verbose_name': 'Patient',
                'verbose_name_plural': 'Patients',
                'db_table': 'patient',
            },
        ),
        
        # PatientGuardian
        migrations.CreateModel(
            name='PatientGuardian',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('full_name', models.CharField(max_length=255)),
                ('relationship', models.CharField(max_length=100)),
                ('phone', models.CharField(blank=True, max_length=50, null=True)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('address_line1', models.CharField(blank=True, max_length=255, null=True)),
                ('city', models.CharField(blank=True, max_length=100, null=True)),
                ('postal_code', models.CharField(blank=True, max_length=20, null=True)),
                ('country_code', models.CharField(blank=True, max_length=2, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='guardians', to='clinical.patient')),
            ],
            options={
                'verbose_name': 'Patient Guardian',
                'verbose_name_plural': 'Patient Guardians',
                'db_table': 'patient_guardian',
            },
        ),
        
        # Encounter
        migrations.CreateModel(
            name='Encounter',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('type', models.CharField(choices=[('medical_consult', 'Medical Consult'), ('cosmetic_consult', 'Cosmetic Consult'), ('aesthetic_procedure', 'Aesthetic Procedure'), ('follow_up', 'Follow-up'), ('sale_only', 'Sale Only')], max_length=30)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('finalized', 'Finalized'), ('cancelled', 'Cancelled')], max_length=20)),
                ('occurred_at', models.DateTimeField()),
                ('chief_complaint', models.TextField(blank=True, null=True)),
                ('assessment', models.TextField(blank=True, null=True)),
                ('plan', models.TextField(blank=True, null=True)),
                ('internal_notes', models.TextField(blank=True, null=True)),
                ('signed_at', models.DateTimeField(blank=True, null=True)),
                ('row_version', models.IntegerField(default=1)),
                ('is_deleted', models.BooleanField(default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_encounters', to=settings.AUTH_USER_MODEL)),
                ('deleted_by_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deleted_encounters', to=settings.AUTH_USER_MODEL)),
                ('location', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='encounters', to='core.cliniclocation')),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='encounters', to='clinical.patient')),
                ('practitioner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='encounters', to='authz.practitioner')),
                ('signed_by_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='signed_encounters', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Encounter',
                'verbose_name_plural': 'Encounters',
                'db_table': 'encounter',
            },
        ),
        
        # Appointment
        migrations.CreateModel(
            name='Appointment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('source', models.CharField(choices=[('calendly', 'Calendly'), ('manual', 'Manual')], max_length=20)),
                ('external_id', models.CharField(blank=True, max_length=255, null=True, unique=True)),
                ('status', models.CharField(choices=[('scheduled', 'Scheduled'), ('confirmed', 'Confirmed'), ('attended', 'Attended'), ('no_show', 'No Show'), ('cancelled', 'Cancelled')], max_length=20)),
                ('scheduled_start', models.DateTimeField()),
                ('scheduled_end', models.DateTimeField()),
                ('notes', models.TextField(blank=True, null=True)),
                ('cancellation_reason', models.TextField(blank=True, null=True)),
                ('no_show_reason', models.TextField(blank=True, null=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('encounter', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='appointments', to='clinical.encounter')),
                ('location', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='appointments', to='core.cliniclocation')),
                ('patient', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='appointments', to='clinical.patient')),
                ('practitioner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='appointments', to='authz.practitioner')),
            ],
            options={
                'verbose_name': 'Appointment',
                'verbose_name_plural': 'Appointments',
                'db_table': 'appointment',
            },
        ),
        
        # Consent
        migrations.CreateModel(
            name='Consent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('consent_type', models.CharField(choices=[('clinical_photos', 'Clinical Photos'), ('marketing_photos', 'Marketing Photos'), ('newsletter', 'Newsletter'), ('marketing_messages', 'Marketing Messages')], max_length=30)),
                ('status', models.CharField(choices=[('granted', 'Granted'), ('revoked', 'Revoked')], max_length=20)),
                ('granted_at', models.DateTimeField()),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('document', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='consents', to='documents.document')),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='consents', to='clinical.patient')),
            ],
            options={
                'verbose_name': 'Consent',
                'verbose_name_plural': 'Consents',
                'db_table': 'consent',
            },
        ),
        
        # ClinicalPhoto
        migrations.CreateModel(
            name='ClinicalPhoto',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('taken_at', models.DateTimeField(blank=True, null=True)),
                ('photo_kind', models.CharField(choices=[('clinical', 'Clinical'), ('before', 'Before'), ('after', 'After')], max_length=20)),
                ('clinical_context', models.CharField(blank=True, choices=[('baseline', 'Baseline'), ('follow_up', 'Follow-up'), ('post_procedure', 'Post-procedure'), ('other', 'Other')], max_length=20, null=True)),
                ('body_area', models.CharField(blank=True, max_length=100, null=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('source_device', models.CharField(blank=True, max_length=255, null=True)),
                ('storage_bucket', models.CharField(default='clinical', editable=False, max_length=64)),
                ('object_key', models.CharField(max_length=512)),
                ('thumbnail_object_key', models.CharField(blank=True, max_length=512, null=True)),
                ('content_type', models.CharField(max_length=128)),
                ('size_bytes', models.BigIntegerField()),
                ('sha256', models.CharField(blank=True, max_length=64, null=True)),
                ('visibility', models.CharField(choices=[('clinical_only', 'Clinical Only')], default='clinical_only', max_length=20)),
                ('is_deleted', models.BooleanField(default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_clinical_photos', to=settings.AUTH_USER_MODEL)),
                ('deleted_by_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deleted_clinical_photos', to=settings.AUTH_USER_MODEL)),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='clinical_photos', to='clinical.patient')),
            ],
            options={
                'verbose_name': 'Clinical Photo',
                'verbose_name_plural': 'Clinical Photos',
                'db_table': 'clinical_photo',
            },
        ),
        
        # EncounterPhoto (M2M)
        migrations.CreateModel(
            name='EncounterPhoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('relation_type', models.CharField(choices=[('attached', 'Attached'), ('comparison', 'Comparison')], max_length=20)),
                ('encounter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='encounter_photos', to='clinical.encounter')),
                ('photo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='encounter_photos', to='clinical.clinicalphoto')),
            ],
            options={
                'verbose_name': 'Encounter Photo',
                'verbose_name_plural': 'Encounter Photos',
                'db_table': 'encounter_photo',
            },
        ),
        
        # EncounterDocument (M2M)
        migrations.CreateModel(
            name='EncounterDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('consent_copy', 'Consent Copy'), ('lab_result', 'Lab Result'), ('instruction', 'Instruction'), ('other', 'Other')], max_length=20)),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='encounter_documents', to='documents.document')),
                ('encounter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='encounter_documents', to='clinical.encounter')),
            ],
            options={
                'verbose_name': 'Encounter Document',
                'verbose_name_plural': 'Encounter Documents',
                'db_table': 'encounter_document',
            },
        ),
        
        # Indexes - ReferralSource
        migrations.AddIndex(
            model_name='referralsource',
            index=models.Index(fields=['is_active'], name='idx_referral_source_active'),
        ),
        
        # Indexes - Patient
        migrations.AddIndex(
            model_name='patient',
            index=models.Index(fields=['last_name', 'first_name'], name='idx_patient_name'),
        ),
        migrations.AddIndex(
            model_name='patient',
            index=models.Index(fields=['email'], name='idx_patient_email'),
        ),
        migrations.AddIndex(
            model_name='patient',
            index=models.Index(fields=['phone_e164'], name='idx_patient_phone_e164'),
        ),
        migrations.AddIndex(
            model_name='patient',
            index=models.Index(fields=['country_code'], name='idx_patient_country'),
        ),
        migrations.AddIndex(
            model_name='patient',
            index=models.Index(fields=['full_name_normalized'], name='idx_patient_full_name_norm'),
        ),
        migrations.AddIndex(
            model_name='patient',
            index=models.Index(fields=['is_deleted'], name='idx_patient_deleted'),
        ),
        
        # Indexes - PatientGuardian
        migrations.AddIndex(
            model_name='patientguardian',
            index=models.Index(fields=['patient'], name='idx_guardian_patient'),
        ),
        
        # Indexes - Encounter
        migrations.AddIndex(
            model_name='encounter',
            index=models.Index(fields=['patient'], name='idx_encounter_patient'),
        ),
        migrations.AddIndex(
            model_name='encounter',
            index=models.Index(fields=['practitioner'], name='idx_encounter_practitioner'),
        ),
        migrations.AddIndex(
            model_name='encounter',
            index=models.Index(fields=['occurred_at'], name='idx_encounter_occurred_at'),
        ),
        migrations.AddIndex(
            model_name='encounter',
            index=models.Index(fields=['status'], name='idx_encounter_status'),
        ),
        migrations.AddIndex(
            model_name='encounter',
            index=models.Index(fields=['is_deleted'], name='idx_encounter_deleted'),
        ),
        
        # Indexes - Appointment
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(fields=['patient'], name='idx_appointment_patient'),
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(fields=['practitioner'], name='idx_appointment_practitioner'),
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(fields=['scheduled_start'], name='idx_appointment_start'),
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(fields=['status'], name='idx_appointment_status'),
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(fields=['external_id'], name='idx_appointment_external_id'),
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(fields=['is_deleted'], name='idx_appointment_deleted'),
        ),
        
        # Indexes - Consent
        migrations.AddIndex(
            model_name='consent',
            index=models.Index(fields=['patient'], name='idx_consent_patient'),
        ),
        migrations.AddIndex(
            model_name='consent',
            index=models.Index(fields=['consent_type'], name='idx_consent_type'),
        ),
        migrations.AddIndex(
            model_name='consent',
            index=models.Index(fields=['status'], name='idx_consent_status'),
        ),
        
        # Indexes - ClinicalPhoto
        migrations.AddIndex(
            model_name='clinicalphoto',
            index=models.Index(fields=['patient'], name='idx_clinical_photo_patient'),
        ),
        migrations.AddIndex(
            model_name='clinicalphoto',
            index=models.Index(fields=['taken_at'], name='idx_clinical_photo_taken_at'),
        ),
        migrations.AddIndex(
            model_name='clinicalphoto',
            index=models.Index(fields=['photo_kind'], name='idx_clinical_photo_kind'),
        ),
        migrations.AddIndex(
            model_name='clinicalphoto',
            index=models.Index(fields=['is_deleted'], name='idx_clinical_photo_deleted'),
        ),
        
        # Indexes - EncounterPhoto
        migrations.AddIndex(
            model_name='encounterphoto',
            index=models.Index(fields=['encounter'], name='idx_encounter_photo_encounter'),
        ),
        migrations.AddIndex(
            model_name='encounterphoto',
            index=models.Index(fields=['photo'], name='idx_encounter_photo_photo'),
        ),
        
        # Indexes - EncounterDocument
        migrations.AddIndex(
            model_name='encounterdocument',
            index=models.Index(fields=['encounter'], name='idx_encounter_doc_encounter'),
        ),
        migrations.AddIndex(
            model_name='encounterdocument',
            index=models.Index(fields=['document'], name='idx_encounter_doc_document'),
        ),
        
        # Unique constraints
        migrations.AlterUniqueTogether(
            name='encounterphoto',
            unique_together={('encounter', 'photo')},
        ),
        migrations.AlterUniqueTogether(
            name='encounterdocument',
            unique_together={('encounter', 'document')},
        ),
    ]
