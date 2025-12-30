"""
Manual verification script: PATCH Patient with 9 new fields and verify persistence.
This script provides CONCRETE EVIDENCE of end-to-end functionality.
"""
import requests
import json
from datetime import datetime, timezone

# API configuration
BASE_URL = "http://localhost:8001/api/v1/clinical"
# Use a real auth token or skip if API allows test access
HEADERS = {
    "Content-Type": "application/json",
}

def create_patient():
    """Step 1: Create a new patient (POST)"""
    print("\n" + "="*80)
    print("STEP 1: CREATE PATIENT (POST)")
    print("="*80)
    
    payload = {
        "first_name": "Manual",
        "last_name": "Verification",
        "email": f"manual.verification.{datetime.now().timestamp()}@test.com",
        "birth_date": "1990-05-15",
        "sex": "male",
    }
    
    response = requests.post(f"{BASE_URL}/patients/", json=payload, headers=HEADERS)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 201:
        data = response.json()
        patient_id = data['id']
        row_version = data['row_version']
        print(f"✅ Patient created: {patient_id}")
        print(f"Row version: {row_version}")
        
        # Verify initial values of 9 fields (should be default/null)
        print("\nInitial values of 9 new fields:")
        print(f"  document_type: {data.get('document_type')}")
        print(f"  document_number: {data.get('document_number')}")
        print(f"  nationality: {data.get('nationality')}")
        print(f"  emergency_contact_name: {data.get('emergency_contact_name')}")
        print(f"  emergency_contact_phone: {data.get('emergency_contact_phone')}")
        print(f"  privacy_policy_accepted: {data.get('privacy_policy_accepted')}")
        print(f"  privacy_policy_accepted_at: {data.get('privacy_policy_accepted_at')}")
        print(f"  terms_accepted: {data.get('terms_accepted')}")
        print(f"  terms_accepted_at: {data.get('terms_accepted_at')}")
        
        return patient_id, row_version
    else:
        print(f"❌ Failed: {response.text}")
        return None, None


def patch_patient(patient_id, row_version):
    """Step 2: PATCH patient with all 9 new fields"""
    print("\n" + "="*80)
    print(f"STEP 2: PATCH PATIENT {patient_id} WITH 9 NEW FIELDS")
    print("="*80)
    
    now_iso = datetime.now(timezone.utc).isoformat()
    
    payload = {
        "row_version": row_version,
        "document_type": "passport",
        "document_number": "MANUAL123456",
        "nationality": "Spanish",
        "emergency_contact_name": "Emergency Contact Test",
        "emergency_contact_phone": "+34611223344",
        "privacy_policy_accepted": True,
        "privacy_policy_accepted_at": now_iso,
        "terms_accepted": True,
        "terms_accepted_at": now_iso,
    }
    
    print("\nPATCH payload:")
    print(json.dumps(payload, indent=2))
    
    response = requests.patch(
        f"{BASE_URL}/patients/{patient_id}/",
        json=payload,
        headers=HEADERS
    )
    
    print(f"\nStatus: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("✅ PATCH successful")
        print("\nResponse values of 9 fields:")
        print(f"  document_type: {data.get('document_type')}")
        print(f"  document_number: {data.get('document_number')}")
        print(f"  nationality: {data.get('nationality')}")
        print(f"  emergency_contact_name: {data.get('emergency_contact_name')}")
        print(f"  emergency_contact_phone: {data.get('emergency_contact_phone')}")
        print(f"  privacy_policy_accepted: {data.get('privacy_policy_accepted')}")
        print(f"  privacy_policy_accepted_at: {data.get('privacy_policy_accepted_at')}")
        print(f"  terms_accepted: {data.get('terms_accepted')}")
        print(f"  terms_accepted_at: {data.get('terms_accepted_at')}")
        
        return True
    else:
        print(f"❌ PATCH failed: {response.text}")
        return False


def get_patient(patient_id):
    """Step 3: GET patient to verify persistence"""
    print("\n" + "="*80)
    print(f"STEP 3: GET PATIENT {patient_id} TO VERIFY PERSISTENCE")
    print("="*80)
    
    response = requests.get(f"{BASE_URL}/patients/{patient_id}/", headers=HEADERS)
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("✅ GET successful")
        print("\nFinal persisted values of 9 fields:")
        print(f"  document_type: {data.get('document_type')}")
        print(f"  document_number: {data.get('document_number')}")
        print(f"  nationality: {data.get('nationality')}")
        print(f"  emergency_contact_name: {data.get('emergency_contact_name')}")
        print(f"  emergency_contact_phone: {data.get('emergency_contact_phone')}")
        print(f"  privacy_policy_accepted: {data.get('privacy_policy_accepted')}")
        print(f"  privacy_policy_accepted_at: {data.get('privacy_policy_accepted_at')}")
        print(f"  terms_accepted: {data.get('terms_accepted')}")
        print(f"  terms_accepted_at: {data.get('terms_accepted_at')}")
        
        # Verify all fields match expectations
        assert data.get('document_type') == 'passport', "❌ document_type NOT persisted!"
        assert data.get('document_number') == 'MANUAL123456', "❌ document_number NOT persisted!"
        assert data.get('nationality') == 'Spanish', "❌ nationality NOT persisted!"
        assert data.get('emergency_contact_name') == 'Emergency Contact Test', "❌ emergency_contact_name NOT persisted!"
        assert data.get('emergency_contact_phone') == '+34611223344', "❌ emergency_contact_phone NOT persisted!"
        assert data.get('privacy_policy_accepted') is True, "❌ privacy_policy_accepted NOT persisted!"
        assert data.get('privacy_policy_accepted_at') is not None, "❌ privacy_policy_accepted_at NOT persisted!"
        assert data.get('terms_accepted') is True, "❌ terms_accepted NOT persisted!"
        assert data.get('terms_accepted_at') is not None, "❌ terms_accepted_at NOT persisted!"
        
        print("\n" + "="*80)
        print("🎉 SUCCESS: ALL 9 FIELDS PERSISTED CORRECTLY!")
        print("="*80)
        return True
    else:
        print(f"❌ GET failed: {response.text}")
        return False


if __name__ == "__main__":
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*15 + "MANUAL VERIFICATION: 9 NEW PATIENT FIELDS" + " "*22 + "║")
    print("╚" + "="*78 + "╝")
    
    # Run the verification flow
    patient_id, row_version = create_patient()
    
    if patient_id:
        patch_success = patch_patient(patient_id, row_version)
        
        if patch_success:
            get_patient(patient_id)
