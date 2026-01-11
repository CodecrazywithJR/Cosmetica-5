#!/usr/bin/env python
import os, sys, django, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import logging
logging.disable(logging.CRITICAL)
django.setup()

from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.clinical.models import Patient

User = get_user_model()

# Get admin user
admin = User.objects.filter(email='ricardoparlon@gmail.com').first()
if not admin:
    print("❌ ADMIN USER NOT FOUND")
    sys.exit(1)

print(f"✓ Admin user: {admin.email}")

# Get a patient
patient = Patient.objects.filter(is_deleted=False).first()
if not patient:
    print("❌ NO PATIENT FOUND")
    sys.exit(1)

print(f"✓ Patient ID: {patient.id}")

# Create API client
client = APIClient()
client.force_authenticate(user=admin)
# Set SERVER_NAME to avoid DisallowedHost
import django
from django.conf import settings
settings.ALLOWED_HOSTS.append('testserver')

# STEP 1: GET initial state
print("\n=== STEP 1: GET INITIAL STATE ===")
response = client.get(f'/api/v1/clinical/patients/{patient.id}/')
print(f"Status: {response.status_code}")
if response.status_code != 200:
    print(f"Response content: {response.content.decode()}")
    sys.exit(1)

initial_data = response.json()
print(f"document_type: {initial_data.get('document_type')}")
print(f"document_number: {initial_data.get('document_number')}")
print(f"nationality: {initial_data.get('nationality')}")
print(f"emergency_contact_name: {initial_data.get('emergency_contact_name')}")
print(f"emergency_contact_phone: {initial_data.get('emergency_contact_phone')}")
print(f"privacy_policy_accepted: {initial_data.get('privacy_policy_accepted')}")
print(f"terms_accepted: {initial_data.get('terms_accepted')}")
print(f"row_version: {initial_data.get('row_version')}")

# STEP 2: PATCH all 9 fields
print("\n=== STEP 2: PATCH ALL 9 FIELDS ===")
from django.utils import timezone
now_iso = timezone.now().isoformat()

patch_data = {
    'document_type': 'dni',
    'document_number': 'API_TEST_99999',
    'nationality': 'API_TEST_COUNTRY',
    'emergency_contact_name': 'API_EMERGENCY',
    'emergency_contact_phone': '+34111222333',
    'privacy_policy_accepted': True,
    'privacy_policy_accepted_at': now_iso,
    'terms_accepted': True,
    'terms_accepted_at': now_iso,
    'row_version': initial_data.get('row_version'),  # Required for update
}

response = client.patch(
    f'/api/v1/clinical/patients/{patient.id}/',
    data=json.dumps(patch_data),
    content_type='application/json'
)

print(f"Status: {response.status_code}")
if response.status_code in [200, 201]:
    patch_response = response.json()
    print(f"document_type: {patch_response.get('document_type')}")
    print(f"document_number: {patch_response.get('document_number')}")
    print(f"nationality: {patch_response.get('nationality')}")
    print(f"emergency_contact_name: {patch_response.get('emergency_contact_name')}")
    print(f"emergency_contact_phone: {patch_response.get('emergency_contact_phone')}")
    print(f"privacy_policy_accepted: {patch_response.get('privacy_policy_accepted')}")
    print(f"terms_accepted: {patch_response.get('terms_accepted')}")
else:
    print(f"❌ ERROR: {response.content}")
    sys.exit(1)

# STEP 3: GET again to verify persistence
print("\n=== STEP 3: GET AFTER PATCH (verify persistence) ===")
response = client.get(f'/api/v1/clinical/patients/{patient.id}/')
print(f"Status: {response.status_code}")
if response.status_code == 200:
    final_data = response.json()
    print(f"document_type: {final_data.get('document_type')}")
    print(f"document_number: {final_data.get('document_number')}")
    print(f"nationality: {final_data.get('nationality')}")
    print(f"emergency_contact_name: {final_data.get('emergency_contact_name')}")
    print(f"emergency_contact_phone: {final_data.get('emergency_contact_phone')}")
    print(f"privacy_policy_accepted: {final_data.get('privacy_policy_accepted')}")
    print(f"privacy_policy_accepted_at: {final_data.get('privacy_policy_accepted_at')}")
    print(f"terms_accepted: {final_data.get('terms_accepted')}")
    print(f"terms_accepted_at: {final_data.get('terms_accepted_at')}")
    
    # VERIFY
    print("\n=== VERIFICATION ===")
    errors = []
    if final_data.get('document_type') != 'dni':
        errors.append(f"❌ document_type: expected 'dni', got '{final_data.get('document_type')}'")
    else:
        print("✓ document_type: dni")
        
    if final_data.get('document_number') != 'API_TEST_99999':
        errors.append(f"❌ document_number: expected 'API_TEST_99999', got '{final_data.get('document_number')}'")
    else:
        print("✓ document_number: API_TEST_99999")
        
    if final_data.get('nationality') != 'API_TEST_COUNTRY':
        errors.append(f"❌ nationality: expected 'API_TEST_COUNTRY', got '{final_data.get('nationality')}'")
    else:
        print("✓ nationality: API_TEST_COUNTRY")
        
    if final_data.get('emergency_contact_name') != 'API_EMERGENCY':
        errors.append(f"❌ emergency_contact_name: expected 'API_EMERGENCY', got '{final_data.get('emergency_contact_name')}'")
    else:
        print("✓ emergency_contact_name: API_EMERGENCY")
        
    if final_data.get('emergency_contact_phone') != '+34111222333':
        errors.append(f"❌ emergency_contact_phone: expected '+34111222333', got '{final_data.get('emergency_contact_phone')}'")
    else:
        print("✓ emergency_contact_phone: +34111222333")
        
    if final_data.get('privacy_policy_accepted') != True:
        errors.append(f"❌ privacy_policy_accepted: expected True, got {final_data.get('privacy_policy_accepted')}")
    else:
        print("✓ privacy_policy_accepted: True")
        
    if final_data.get('terms_accepted') != True:
        errors.append(f"❌ terms_accepted: expected True, got {final_data.get('terms_accepted')}")
    else:
        print("✓ terms_accepted: True")
        
    if not final_data.get('privacy_policy_accepted_at'):
        errors.append("❌ privacy_policy_accepted_at: is None")
    else:
        print(f"✓ privacy_policy_accepted_at: {final_data.get('privacy_policy_accepted_at')}")
        
    if not final_data.get('terms_accepted_at'):
        errors.append("❌ terms_accepted_at: is None")
    else:
        print(f"✓ terms_accepted_at: {final_data.get('terms_accepted_at')}")
    
    if errors:
        print("\n❌ ERRORS FOUND:")
        for err in errors:
            print(err)
        sys.exit(1)
    else:
        print("\n✅ ALL 9 FIELDS WORK END-TO-END")
else:
    print(f"❌ ERROR: {response.content}")
    sys.exit(1)

# Restore initial values
print("\n=== RESTORING INITIAL VALUES ===")
restore_data = {
    'document_type': initial_data.get('document_type'),
    'document_number': initial_data.get('document_number'),
    'nationality': initial_data.get('nationality'),
    'emergency_contact_name': initial_data.get('emergency_contact_name'),
    'emergency_contact_phone': initial_data.get('emergency_contact_phone'),
    'privacy_policy_accepted': initial_data.get('privacy_policy_accepted'),
    'privacy_policy_accepted_at': initial_data.get('privacy_policy_accepted_at'),
    'terms_accepted': initial_data.get('terms_accepted'),
    'terms_accepted_at': initial_data.get('terms_accepted_at'),
}
response = client.patch(
    f'/api/v1/clinical/patients/{patient.id}/',
    data=json.dumps(restore_data),
    content_type='application/json'
)
print(f"Restored: {response.status_code}")
