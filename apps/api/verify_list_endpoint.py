#!/usr/bin/env python
"""
Verify what fields are returned by the patients LIST endpoint
vs the DETAIL endpoint to diagnose the consent badge issue.
"""
import os, sys, django, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import logging
logging.disable(logging.CRITICAL)
django.setup()

from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()

# Get admin user
admin = User.objects.filter(email='ricardoparlon@gmail.com').first()
if not admin:
    print("❌ ADMIN USER NOT FOUND")
    sys.exit(1)

# Create API client
client = APIClient()
client.force_authenticate(user=admin)

from django.conf import settings
settings.ALLOWED_HOSTS.append('testserver')

print("=" * 80)
print("LIST ENDPOINT: /api/v1/clinical/patients/?limit=1")
print("=" * 80)

response = client.get('/api/v1/clinical/patients/?limit=1')
if response.status_code != 200:
    print(f"❌ ERROR {response.status_code}: {response.content.decode()}")
    sys.exit(1)

list_data = response.json()
if list_data['results']:
    patient_from_list = list_data['results'][0]
    patient_id = patient_from_list['id']
    
    print(f"\n✓ Patient from LIST endpoint (ID: {patient_id}):")
    print(f"  - first_name: {patient_from_list.get('first_name')}")
    print(f"  - last_name: {patient_from_list.get('last_name')}")
    print(f"  - email: {patient_from_list.get('email')}")
    print(f"  - privacy_policy_accepted: {patient_from_list.get('privacy_policy_accepted')}")
    print(f"  - privacy_policy_accepted_at: {patient_from_list.get('privacy_policy_accepted_at')}")
    print(f"  - terms_accepted: {patient_from_list.get('terms_accepted')}")
    print(f"  - terms_accepted_at: {patient_from_list.get('terms_accepted_at')}")
    
    print(f"\n  Full keys returned: {list(patient_from_list.keys())}")
    
    print("\n" + "=" * 80)
    print(f"DETAIL ENDPOINT: /api/v1/clinical/patients/{patient_id}/")
    print("=" * 80)
    
    response = client.get(f'/api/v1/clinical/patients/{patient_id}/')
    if response.status_code != 200:
        print(f"❌ ERROR {response.status_code}: {response.content.decode()}")
        sys.exit(1)
    
    patient_from_detail = response.json()
    
    print(f"\n✓ Patient from DETAIL endpoint (ID: {patient_id}):")
    print(f"  - first_name: {patient_from_detail.get('first_name')}")
    print(f"  - last_name: {patient_from_detail.get('last_name')}")
    print(f"  - email: {patient_from_detail.get('email')}")
    print(f"  - privacy_policy_accepted: {patient_from_detail.get('privacy_policy_accepted')}")
    print(f"  - privacy_policy_accepted_at: {patient_from_detail.get('privacy_policy_accepted_at')}")
    print(f"  - terms_accepted: {patient_from_detail.get('terms_accepted')}")
    print(f"  - terms_accepted_at: {patient_from_detail.get('terms_accepted_at')}")
    
    print(f"\n  Full keys returned: {list(patient_from_detail.keys())}")
    
    # Compare
    print("\n" + "=" * 80)
    print("COMPARISON")
    print("=" * 80)
    
    list_keys = set(patient_from_list.keys())
    detail_keys = set(patient_from_detail.keys())
    
    missing_in_list = detail_keys - list_keys
    if missing_in_list:
        print(f"\n⚠️  Fields in DETAIL but NOT in LIST: {sorted(missing_in_list)}")
    else:
        print("\n✓ LIST contains all DETAIL fields")
    
    # Check consent fields specifically
    consent_fields = ['privacy_policy_accepted', 'privacy_policy_accepted_at', 'terms_accepted', 'terms_accepted_at']
    print(f"\n✓ Consent fields in LIST:")
    for field in consent_fields:
        present = field in patient_from_list
        print(f"  - {field}: {'YES' if present else 'NO'}")
    
else:
    print("❌ No patients found in database")
