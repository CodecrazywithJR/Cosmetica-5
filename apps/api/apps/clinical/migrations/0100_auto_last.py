# Stub migration to repair chain after missing 0100_auto_last
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('clinical', '0014_add_patient_identity_emergency_legal_fields'),
    ]

    operations = []
