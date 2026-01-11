import os, django, sys, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import logging
logging.disable(logging.CRITICAL)
django.setup()

from apps.clinical.models import Patient
from apps.clinical.serializers import PatientDetailSerializer

# Get an existing patient
patient = Patient.objects.filter(is_deleted=False).first()
if not patient:
    print("NO PATIENT FOUND")
    sys.exit(1)

print(f"=== TESTING PATIENT {patient.id} ===")
print(f"Name: {patient.first_name} {patient.last_name}")

# Store original values
original_values = {
    'document_type': patient.document_type,
    'document_number': patient.document_number,
    'nationality': patient.nationality,
    'emergency_contact_name': patient.emergency_contact_name,
    'emergency_contact_phone': patient.emergency_contact_phone,
    'privacy_policy_accepted': patient.privacy_policy_accepted,
    'privacy_policy_accepted_at': patient.privacy_policy_accepted_at,
    'terms_accepted': patient.terms_accepted,
    'terms_accepted_at': patient.terms_accepted_at,
}

# STEP 1: UPDATE via model
from datetime import datetime
from django.utils import timezone

print("\n=== STEP 1: UPDATE ALL 9 FIELDS ===")
patient.document_type = 'passport'
patient.document_number = 'VERIFY123456'
patient.nationality = 'TEST_NATIONALITY'
patient.emergency_contact_name = 'VERIFY_CONTACT'
patient.emergency_contact_phone = '+34999888777'
patient.privacy_policy_accepted = True
patient.privacy_policy_accepted_at = timezone.now()
patient.terms_accepted = True
patient.terms_accepted_at = timezone.now()
patient.save()

# STEP 2: RELOAD from database
print("\n=== STEP 2: RELOAD FROM DB ===")
patient.refresh_from_db()
print(f"document_type: {patient.document_type}")
print(f"document_number: {patient.document_number}")
print(f"nationality: {patient.nationality}")
print(f"emergency_contact_name: {patient.emergency_contact_name}")
print(f"emergency_contact_phone: {patient.emergency_contact_phone}")
print(f"privacy_policy_accepted: {patient.privacy_policy_accepted}")
print(f"privacy_policy_accepted_at: {patient.privacy_policy_accepted_at}")
print(f"terms_accepted: {patient.terms_accepted}")
print(f"terms_accepted_at: {patient.terms_accepted_at}")

# STEP 3: SERIALIZE (simulate GET)
print("\n=== STEP 3: SERIALIZER OUTPUT (GET) ===")
serializer = PatientDetailSerializer(patient)
data = serializer.data

print(f"document_type: {data.get('document_type')}")
print(f"document_number: {data.get('document_number')}")
print(f"nationality: {data.get('nationality')}")
print(f"emergency_contact_name: {data.get('emergency_contact_name')}")
print(f"emergency_contact_phone: {data.get('emergency_contact_phone')}")
print(f"privacy_policy_accepted: {data.get('privacy_policy_accepted')}")
print(f"privacy_policy_accepted_at: {data.get('privacy_policy_accepted_at')}")
print(f"terms_accepted: {data.get('terms_accepted')}")
print(f"terms_accepted_at: {data.get('terms_accepted_at')}")

# STEP 4: VERIFY serializer has fields (not read_only)
print("\n=== STEP 4: SERIALIZER CONFIGURATION ===")
read_only = PatientDetailSerializer.Meta.read_only_fields
all_fields = PatientDetailSerializer.Meta.fields
new_fields = [
    'document_type', 'document_number', 'nationality',
    'emergency_contact_name', 'emergency_contact_phone',
    'privacy_policy_accepted', 'privacy_policy_accepted_at',
    'terms_accepted', 'terms_accepted_at'
]
for field in new_fields:
    in_fields = field in all_fields
    is_read_only = field in read_only
    print(f"{field}: in_fields={in_fields} read_only={is_read_only}")

# Restore original values
print("\n=== RESTORING ORIGINAL VALUES ===")
for key, value in original_values.items():
    setattr(patient, key, value)
patient.save()
print("RESTORED")
