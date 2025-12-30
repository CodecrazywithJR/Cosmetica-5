#!/usr/bin/env python
"""
Crear encounter de ejemplo y obtener JSON para auditoría
"""
import os, sys, django, json
from datetime import datetime, timezone
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import logging
logging.disable(logging.CRITICAL)
django.setup()

from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.clinical.models import Encounter, Patient, EncounterTypeChoices, EncounterStatusChoices

User = get_user_model()

# Get admin user
admin = User.objects.filter(email='ricardoparlon@gmail.com').first()
if not admin:
    print("❌ ADMIN USER NOT FOUND")
    sys.exit(1)

# Get or create a patient
patient = Patient.objects.filter(is_deleted=False).first()
if not patient:
    print("❌ NO PATIENT FOUND")
    sys.exit(1)

# Create sample encounter
encounter = Encounter.objects.create(
    patient=patient,
    type=EncounterTypeChoices.COSMETIC_CONSULT,
    status=EncounterStatusChoices.DRAFT,
    occurred_at=datetime.now(timezone.utc),
    chief_complaint="Patient wants to improve skin texture",
    assessment="Mild photoaging, some hyperpigmentation",
    plan="Recommend chemical peel series",
    internal_notes="Patient is interested in packages",
    created_by_user=admin
)

print(f"✓ Created encounter: {encounter.id}")

# Create API client
client = APIClient()
client.force_authenticate(user=admin)

from django.conf import settings
settings.ALLOWED_HOSTS.append('testserver')

# === LIST ENDPOINT ===
print("\n" + "=" * 80)
print("LIST ENDPOINT: GET /api/v1/clinical/encounters/")
print("=" * 80)

response = client.get('/api/v1/clinical/encounters/?limit=1')
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    if data.get('results'):
        print("\n✓ Sample item from LIST:")
        print(json.dumps(data['results'][0], indent=2, default=str))

# === DETAIL ENDPOINT ===
print("\n" + "=" * 80)
print(f"DETAIL ENDPOINT: GET /api/v1/clinical/encounters/{encounter.id}/")
print("=" * 80)

response = client.get(f'/api/v1/clinical/encounters/{encounter.id}/')
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print("\n✓ Full DETAIL:")
    print(json.dumps(data, indent=2, default=str))

# Clean up
encounter.delete()
print(f"\n✓ Cleaned up test encounter")
