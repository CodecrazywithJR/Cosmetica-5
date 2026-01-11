# Generated migration for core app - DOMAIN_MODEL.md implementation

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AppSettings',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('default_country_code', models.CharField(default='FR', max_length=2)),
                ('default_currency', models.CharField(default='EUR', max_length=3)),
                ('default_language', models.CharField(
                    choices=[('ru', 'Russian'), ('fr', 'French'), ('en', 'English'), ('uk', 'Ukrainian'), ('hy', 'Armenian'), ('es', 'Spanish')],
                    default='fr',
                    max_length=2
                )),
                ('enabled_languages', models.JSONField(default=list, help_text='Array of enabled language codes')),
                ('timezone', models.CharField(default='Europe/Paris', max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'App Settings',
                'verbose_name_plural': 'App Settings',
                'db_table': 'app_settings',
            },
        ),
        migrations.CreateModel(
            name='ClinicLocation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('address_line1', models.CharField(blank=True, max_length=255, null=True)),
                ('city', models.CharField(blank=True, max_length=100, null=True)),
                ('postal_code', models.CharField(blank=True, max_length=20, null=True)),
                ('country_code', models.CharField(blank=True, max_length=2, null=True)),
                ('timezone', models.CharField(default='Europe/Paris', max_length=64)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Clinic Location',
                'verbose_name_plural': 'Clinic Locations',
                'db_table': 'clinic_location',
            },
        ),
        migrations.AddIndex(
            model_name='cliniclocation',
            index=models.Index(fields=['is_active'], name='idx_clinic_location_active'),
        ),
    ]
