#!/usr/bin/env python
"""
Extraer ejemplos reales de JSON de Encounter LIST y DETAIL
para documentar la auditoría del backend.
"""
import os, sys, django, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import logging
logging.disable(logging.CRITICAL)
django.setup()

from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.clinical.models import Encounter

User = get_user_model()

# Get admin user
admin = User.objects.filter(email='ricardoparlon@gmail.com').first()
if not admin:
    print("❌ ADMIN USER NOT FOUND")
    sys.exit(1)

print(f"✓ Admin user: {admin.email}")

# Create API client
client = APIClient()
client.force_authenticate(user=admin)

from django.conf import settings
settings.ALLOWED_HOSTS.append('testserver')

# Get an encounter
encounter = Encounter.objects.filter(is_deleted=False).first()
if not encounter:
    print("\n⚠️  NO ENCOUNTERS FOUND IN DATABASE")
    print("Cannot provide real JSON examples")
    sys.exit(0)

print(f"✓ Found encounter: {encounter.id}")

# === LIST ENDPOINT ===
print("\n" + "=" * 80)
print("LIST ENDPOINT: GET /api/v1/clinical/encounters/?limit=1")
print("=" * 80)

response = client.get('/api/v1/clinical/encounters/?limit=1')
if response.status_code != 200:
    print(f"❌ ERROR {response.status_code}: {response.content.decode()}")
else:
    data = response.json()
    if data.get('results'):
        print("\n✓ Sample item from LIST (1 encounter):")
        print(json.dumps(data['results'][0], indent=2, default=str))
        
        print(f"\n✓ Fields returned in LIST: {list(data['results'][0].keys())}")

# === DETAIL ENDPOINT ===
print("\n" + "=" * 80)
print(f"DETAIL ENDPOINT: GET /api/v1/clinical/encounters/{encounter.id}/")
print("=" * 80)

response = client.get(f'/api/v1/clinical/encounters/{encounter.id}/')
if response.status_code != 200:
    print(f"❌ ERROR {response.status_code}: {response.content.decode()}")
else:
    data = response.json()
    print("\n✓ Sample DETAIL (full encounter):")
    print(json.dumps(data, indent=2, default=str))
    
    print(f"\n✓ Fields returned in DETAIL: {list(data.keys())}")

# === FILTERS ===
print("\n" + "=" * 80)
print("TESTING FILTERS")
print("=" * 80)

# Filter by status
print("\n1) Filter by status=draft:")
response = client.get('/api/v1/clinical/encounters/?status=draft')
print(f"   Status: {response.status_code}, Count: {response.json().get('count', 0)}")

# Filter by patient
print(f"\n2) Filter by patient_id={encounter.patient_id}:")
response = client.get(f'/api/v1/clinical/encounters/?patient_id={encounter.patient_id}')
print(f"   Status: {response.status_code}, Count: {response.json().get('count', 0)}")

# Filter by date range
print(f"\n3) Filter by date_from=2025-01-01:")
response = client.get('/api/v1/clinical/encounters/?date_from=2025-01-01')
print(f"   Status: {response.status_code}, Count: {response.json().get('count', 0)}")

# Combined filters
print(f"\n4) Combined: patient + status + date_from:")
response = client.get(
    f'/api/v1/clinical/encounters/?patient_id={encounter.patient_id}&status=draft&date_from=2025-01-01'
)
print(f"   Status: {response.status_code}, Count: {response.json().get('count', 0)}")

print("\n" + "=" * 80)
print("✓ AUDIT COMPLETE")
print("=" * 80)
