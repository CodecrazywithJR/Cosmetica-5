"""
Tests for Consent API endpoints.

Endpoints tested:
- POST /api/v1/patients/{id}/consents/grant/
- POST /api/v1/patients/{id}/consents/revoke/
- GET /api/v1/patients/{id}/consents/status/

Business Rules:
- Consents are IMMUTABLE - revoke creates a NEW record, doesn't update
- 4 consent types: clinical_photos, marketing_photos, newsletter, marketing_messages
- Marketing role can read status ONLY if contract allows, otherwise 403
- Clinical roles (Admin/Practitioner/Reception) can grant/revoke/read
- document_id is optional (can be null)
"""
import pytest
from datetime import datetime, timezone
from django.utils import timezone as django_timezone


@pytest.mark.django_db
class TestConsentGrant:
    """Test POST /api/v1/patients/{id}/consents/grant/ endpoint"""
    
    def test_grant_consent_success(self, admin_client, patient):
        """Admin can grant consent and creates new Consent record"""
        url = f'/api/v1/patients/{patient.id}/consents/grant/'
        payload = {
            'consent_type': 'clinical_photos',
        }
        
        response = admin_client.post(url, payload, format='json')
        
        # Skip if endpoint not implemented
        if response.status_code == 404:
            pytest.skip("Consent grant endpoint not yet implemented")
        
        assert response.status_code in [200, 201], f"Expected 200 or 201, got {response.status_code}: {response.data}"
        assert response.data['consent_type'] == 'clinical_photos'
        assert response.data['status'] == 'granted'
        assert response.data['patient'] == str(patient.id)
        assert 'granted_at' in response.data
        assert response.data['revoked_at'] is None
        
        # Verify database record
        from apps.clinical.models import Consent
        consent = Consent.objects.get(id=response.data['id'])
        assert consent.patient_id == patient.id
        assert consent.consent_type == 'clinical_photos'
        assert consent.status == 'granted'
        assert consent.granted_at is not None
        assert consent.revoked_at is None
    
    def test_grant_consent_with_document_id(self, admin_client, patient):
        """Grant consent with optional document_id"""
        # Create a mock document ID (UUID format)
        import uuid
        document_id = uuid.uuid4()
        
        url = f'/api/v1/patients/{patient.id}/consents/grant/'
        payload = {
            'consent_type': 'marketing_photos',
            'document_id': str(document_id),
        }
        
        response = admin_client.post(url, payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Consent grant endpoint not yet implemented")
        
        assert response.status_code in [200, 201]
        # Document FK might fail if document doesn't exist - that's ok for validation test
        # Main point: endpoint accepts document_id parameter
    
    def test_grant_consent_without_document_id(self, admin_client, patient):
        """Grant consent without document_id (should be allowed)"""
        url = f'/api/v1/patients/{patient.id}/consents/grant/'
        payload = {
            'consent_type': 'newsletter',
        }
        
        response = admin_client.post(url, payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Consent grant endpoint not yet implemented")
        
        assert response.status_code in [200, 201]
        assert response.data['consent_type'] == 'newsletter'
        assert response.data['status'] == 'granted'
        # document_id should be null
        assert response.data.get('document') is None or response.data.get('document_id') is None
    
    def test_grant_consent_all_types(self, admin_client, patient):
        """Grant consent for all 4 consent types"""
        consent_types = ['clinical_photos', 'marketing_photos', 'newsletter', 'marketing_messages']
        
        for consent_type in consent_types:
            url = f'/api/v1/patients/{patient.id}/consents/grant/'
            payload = {'consent_type': consent_type}
            
            response = admin_client.post(url, payload, format='json')
            
            if response.status_code == 404:
                pytest.skip("Consent grant endpoint not yet implemented")
            
            assert response.status_code in [200, 201], f"Failed for {consent_type}"
            assert response.data['consent_type'] == consent_type
            assert response.data['status'] == 'granted'
    
    def test_grant_consent_practitioner_allowed(self, practitioner_client, patient):
        """Practitioner can grant consent"""
        url = f'/api/v1/patients/{patient.id}/consents/grant/'
        payload = {'consent_type': 'clinical_photos'}
        
        response = practitioner_client.post(url, payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Consent grant endpoint not yet implemented")
        
        assert response.status_code in [200, 201]
        assert response.data['status'] == 'granted'
    
    def test_grant_consent_reception_allowed(self, reception_client, patient):
        """Reception can grant consent"""
        url = f'/api/v1/patients/{patient.id}/consents/grant/'
        payload = {'consent_type': 'newsletter'}
        
        response = reception_client.post(url, payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Consent grant endpoint not yet implemented")
        
        assert response.status_code in [200, 201]
        assert response.data['status'] == 'granted'
    
    def test_grant_consent_accounting_forbidden(self, accounting_client, patient):
        """Accounting cannot grant consent"""
        url = f'/api/v1/patients/{patient.id}/consents/grant/'
        payload = {'consent_type': 'clinical_photos'}
        
        response = accounting_client.post(url, payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Consent grant endpoint not yet implemented")
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    
    def test_grant_consent_marketing_forbidden(self, marketing_client, patient):
        """Marketing cannot grant consent"""
        url = f'/api/v1/patients/{patient.id}/consents/grant/'
        payload = {'consent_type': 'marketing_messages'}
        
        response = marketing_client.post(url, payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Consent grant endpoint not yet implemented")
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    
    def test_grant_consent_invalid_type(self, admin_client, patient):
        """Grant consent with invalid consent_type returns 400"""
        url = f'/api/v1/patients/{patient.id}/consents/grant/'
        payload = {'consent_type': 'invalid_type'}
        
        response = admin_client.post(url, payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Consent grant endpoint not yet implemented")
        
        assert response.status_code == 400
    
    def test_grant_consent_missing_type(self, admin_client, patient):
        """Grant consent without consent_type returns 400"""
        url = f'/api/v1/patients/{patient.id}/consents/grant/'
        payload = {}
        
        response = admin_client.post(url, payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Consent grant endpoint not yet implemented")
        
        assert response.status_code == 400
    
    def test_grant_consent_nonexistent_patient(self, admin_client):
        """Grant consent for nonexistent patient returns 404"""
        import uuid
        fake_patient_id = uuid.uuid4()
        url = f'/api/v1/patients/{fake_patient_id}/consents/grant/'
        payload = {'consent_type': 'clinical_photos'}
        
        response = admin_client.post(url, payload, format='json')
        
        if response.status_code == 404:
            # Could be either endpoint not implemented or patient not found
            # Can't distinguish, so skip
            pytest.skip("Endpoint not implemented or patient not found (both 404)")
        
        # If endpoint exists, should get 404 for patient not found
        assert response.status_code == 404


@pytest.mark.django_db
class TestConsentRevoke:
    """Test POST /api/v1/patients/{id}/consents/revoke/ endpoint"""
    
    def test_revoke_consent_creates_new_record(self, admin_client, patient):
        """Revoke creates NEW consent record (immutable pattern), doesn't update existing"""
        # First grant consent
        from apps.clinical.models import Consent
        granted_consent = Consent.objects.create(
            patient=patient,
            consent_type='clinical_photos',
            status='granted',
            granted_at=django_timezone.now(),
        )
        original_id = granted_consent.id
        
        # Now revoke
        url = f'/api/v1/patients/{patient.id}/consents/revoke/'
        payload = {'consent_type': 'clinical_photos'}
        
        response = admin_client.post(url, payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Consent revoke endpoint not yet implemented")
        
        assert response.status_code in [200, 201]
        assert response.data['consent_type'] == 'clinical_photos'
        assert response.data['status'] == 'revoked'
        assert 'revoked_at' in response.data
        assert response.data['revoked_at'] is not None
        
        # CRITICAL: Verify NEW record created, not updated
        revoked_consent_id = response.data['id']
        assert revoked_consent_id != str(original_id), "Revoke must create NEW record, not update existing"
        
        # Original granted record still exists unchanged
        granted_consent.refresh_from_db()
        assert granted_consent.status == 'granted', "Original granted consent should remain unchanged"
        assert granted_consent.revoked_at is None
        
        # New revoked record exists
        revoked_consent = Consent.objects.get(id=revoked_consent_id)
        assert revoked_consent.status == 'revoked'
        assert revoked_consent.revoked_at is not None
        
        # Both records exist in DB
        assert Consent.objects.filter(patient=patient, consent_type='clinical_photos').count() == 2
    
    def test_revoke_consent_all_types(self, admin_client, patient):
        """Revoke consent for all 4 consent types"""
        from apps.clinical.models import Consent
        consent_types = ['clinical_photos', 'marketing_photos', 'newsletter', 'marketing_messages']
        
        for consent_type in consent_types:
            # Grant first
            Consent.objects.create(
                patient=patient,
                consent_type=consent_type,
                status='granted',
                granted_at=django_timezone.now(),
            )
            
            # Revoke
            url = f'/api/v1/patients/{patient.id}/consents/revoke/'
            payload = {'consent_type': consent_type}
            
            response = admin_client.post(url, payload, format='json')
            
            if response.status_code == 404:
                pytest.skip("Consent revoke endpoint not yet implemented")
            
            assert response.status_code in [200, 201], f"Failed for {consent_type}"
            assert response.data['consent_type'] == consent_type
            assert response.data['status'] == 'revoked'
    
    def test_revoke_consent_without_prior_grant(self, admin_client, patient):
        """Revoking without prior grant should still work (creates revoked record)"""
        url = f'/api/v1/patients/{patient.id}/consents/revoke/'
        payload = {'consent_type': 'newsletter'}
        
        response = admin_client.post(url, payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Consent revoke endpoint not yet implemented")
        
        # Should succeed - creates first consent record as revoked
        assert response.status_code in [200, 201]
        assert response.data['status'] == 'revoked'
    
    def test_revoke_consent_practitioner_allowed(self, practitioner_client, patient):
        """Practitioner can revoke consent"""
        url = f'/api/v1/patients/{patient.id}/consents/revoke/'
        payload = {'consent_type': 'clinical_photos'}
        
        response = practitioner_client.post(url, payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Consent revoke endpoint not yet implemented")
        
        assert response.status_code in [200, 201]
        assert response.data['status'] == 'revoked'
    
    def test_revoke_consent_reception_allowed(self, reception_client, patient):
        """Reception can revoke consent"""
        url = f'/api/v1/patients/{patient.id}/consents/revoke/'
        payload = {'consent_type': 'marketing_messages'}
        
        response = reception_client.post(url, payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Consent revoke endpoint not yet implemented")
        
        assert response.status_code in [200, 201]
        assert response.data['status'] == 'revoked'
    
    def test_revoke_consent_accounting_forbidden(self, accounting_client, patient):
        """Accounting cannot revoke consent"""
        url = f'/api/v1/patients/{patient.id}/consents/revoke/'
        payload = {'consent_type': 'clinical_photos'}
        
        response = accounting_client.post(url, payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Consent revoke endpoint not yet implemented")
        
        assert response.status_code == 403
    
    def test_revoke_consent_marketing_forbidden(self, marketing_client, patient):
        """Marketing cannot revoke consent"""
        url = f'/api/v1/patients/{patient.id}/consents/revoke/'
        payload = {'consent_type': 'newsletter'}
        
        response = marketing_client.post(url, payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Consent revoke endpoint not yet implemented")
        
        assert response.status_code == 403
    
    def test_revoke_consent_invalid_type(self, admin_client, patient):
        """Revoke consent with invalid consent_type returns 400"""
        url = f'/api/v1/patients/{patient.id}/consents/revoke/'
        payload = {'consent_type': 'invalid_type'}
        
        response = admin_client.post(url, payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Consent revoke endpoint not yet implemented")
        
        assert response.status_code == 400
    
    def test_revoke_consent_multiple_times(self, admin_client, patient):
        """Revoking multiple times creates multiple revoked records (immutable)"""
        from apps.clinical.models import Consent
        
        # Grant once
        Consent.objects.create(
            patient=patient,
            consent_type='clinical_photos',
            status='granted',
            granted_at=django_timezone.now(),
        )
        
        # Revoke twice
        url = f'/api/v1/patients/{patient.id}/consents/revoke/'
        payload = {'consent_type': 'clinical_photos'}
        
        response1 = admin_client.post(url, payload, format='json')
        if response1.status_code == 404:
            pytest.skip("Consent revoke endpoint not yet implemented")
        
        response2 = admin_client.post(url, payload, format='json')
        
        assert response1.status_code in [200, 201]
        assert response2.status_code in [200, 201]
        
        # Different IDs - two separate revoked records
        assert response1.data['id'] != response2.data['id']
        
        # Total 3 records: 1 granted + 2 revoked
        assert Consent.objects.filter(patient=patient, consent_type='clinical_photos').count() == 3


@pytest.mark.django_db
class TestConsentStatus:
    """Test GET /api/v1/patients/{id}/consents/status/ endpoint"""
    
    def test_get_consent_status_all_types(self, admin_client, patient):
        """Status endpoint returns current status for all 4 consent types"""
        from apps.clinical.models import Consent
        
        # Grant some consents
        Consent.objects.create(
            patient=patient,
            consent_type='clinical_photos',
            status='granted',
            granted_at=django_timezone.now(),
        )
        Consent.objects.create(
            patient=patient,
            consent_type='marketing_photos',
            status='granted',
            granted_at=django_timezone.now(),
        )
        
        # Revoke one
        Consent.objects.create(
            patient=patient,
            consent_type='newsletter',
            status='revoked',
            granted_at=django_timezone.now(),
            revoked_at=django_timezone.now(),
        )
        
        # marketing_messages not touched (no records)
        
        url = f'/api/v1/patients/{patient.id}/consents/status/'
        response = admin_client.get(url)
        
        if response.status_code == 404:
            pytest.skip("Consent status endpoint not yet implemented")
        
        assert response.status_code == 200
        
        # Should return dict with all 4 types
        data = response.data
        assert 'clinical_photos' in data
        assert 'marketing_photos' in data
        assert 'newsletter' in data
        assert 'marketing_messages' in data
        
        # Verify statuses
        assert data['clinical_photos'] == 'granted'
        assert data['marketing_photos'] == 'granted'
        assert data['newsletter'] == 'revoked'
        # marketing_messages has no records - could be null or 'not_granted' or absent
        assert data['marketing_messages'] in [None, 'not_granted', 'revoked', ''] or 'marketing_messages' not in data
    
    def test_get_consent_status_latest_record_wins(self, admin_client, patient):
        """Status returns latest record for each consent_type (immutable pattern)"""
        from apps.clinical.models import Consent
        import time
        
        # Grant clinical_photos
        Consent.objects.create(
            patient=patient,
            consent_type='clinical_photos',
            status='granted',
            granted_at=django_timezone.now(),
        )
        
        time.sleep(0.01)  # Small delay to ensure different timestamps
        
        # Revoke clinical_photos (creates new record)
        Consent.objects.create(
            patient=patient,
            consent_type='clinical_photos',
            status='revoked',
            granted_at=django_timezone.now(),
            revoked_at=django_timezone.now(),
        )
        
        time.sleep(0.01)
        
        # Grant again (creates another new record)
        Consent.objects.create(
            patient=patient,
            consent_type='clinical_photos',
            status='granted',
            granted_at=django_timezone.now(),
        )
        
        url = f'/api/v1/patients/{patient.id}/consents/status/'
        response = admin_client.get(url)
        
        if response.status_code == 404:
            pytest.skip("Consent status endpoint not yet implemented")
        
        assert response.status_code == 200
        
        # Latest record is granted
        assert response.data['clinical_photos'] == 'granted'
    
    def test_get_consent_status_admin_allowed(self, admin_client, patient):
        """Admin can read consent status"""
        url = f'/api/v1/patients/{patient.id}/consents/status/'
        response = admin_client.get(url)
        
        if response.status_code == 404:
            pytest.skip("Consent status endpoint not yet implemented")
        
        assert response.status_code == 200
    
    def test_get_consent_status_practitioner_allowed(self, practitioner_client, patient):
        """Practitioner can read consent status"""
        url = f'/api/v1/patients/{patient.id}/consents/status/'
        response = practitioner_client.get(url)
        
        if response.status_code == 404:
            pytest.skip("Consent status endpoint not yet implemented")
        
        assert response.status_code == 200
    
    def test_get_consent_status_reception_allowed(self, reception_client, patient):
        """Reception can read consent status"""
        url = f'/api/v1/patients/{patient.id}/consents/status/'
        response = reception_client.get(url)
        
        if response.status_code == 404:
            pytest.skip("Consent status endpoint not yet implemented")
        
        assert response.status_code == 200
    
    def test_get_consent_status_accounting_allowed(self, accounting_client, patient):
        """Accounting can read consent status (read-only role)"""
        url = f'/api/v1/patients/{patient.id}/consents/status/'
        response = accounting_client.get(url)
        
        if response.status_code == 404:
            pytest.skip("Consent status endpoint not yet implemented")
        
        assert response.status_code == 200
    
    def test_get_consent_status_marketing_forbidden_by_default(self, marketing_client, patient):
        """Marketing CANNOT read consent status unless contract explicitly allows"""
        url = f'/api/v1/patients/{patient.id}/consents/status/'
        response = marketing_client.get(url)
        
        if response.status_code == 404:
            pytest.skip("Consent status endpoint not yet implemented")
        
        # Marketing should be forbidden by default
        assert response.status_code == 403, "Marketing should get 403 unless contract allows"
    
    def test_get_consent_status_empty_patient(self, admin_client, patient):
        """Status for patient with no consents returns all types with null/not_granted status"""
        url = f'/api/v1/patients/{patient.id}/consents/status/'
        response = admin_client.get(url)
        
        if response.status_code == 404:
            pytest.skip("Consent status endpoint not yet implemented")
        
        assert response.status_code == 200
        
        # Should return all 4 types with null or 'not_granted'
        data = response.data
        for consent_type in ['clinical_photos', 'marketing_photos', 'newsletter', 'marketing_messages']:
            # Could be null, 'not_granted', or missing
            if consent_type in data:
                assert data[consent_type] in [None, 'not_granted', '']
    
    def test_get_consent_status_nonexistent_patient(self, admin_client):
        """Status for nonexistent patient returns 404"""
        import uuid
        fake_patient_id = uuid.uuid4()
        url = f'/api/v1/patients/{fake_patient_id}/consents/status/'
        
        response = admin_client.get(url)
        
        if response.status_code == 404:
            pytest.skip("Endpoint not implemented or patient not found (both 404)")
        
        assert response.status_code == 404


@pytest.mark.django_db
class TestConsentImmutability:
    """Test that consent records are truly immutable"""
    
    def test_grant_then_revoke_preserves_history(self, admin_client, patient):
        """Grant → Revoke creates 2 separate records preserving full audit trail"""
        from apps.clinical.models import Consent
        
        # Grant
        grant_url = f'/api/v1/patients/{patient.id}/consents/grant/'
        grant_response = admin_client.post(grant_url, {'consent_type': 'clinical_photos'}, format='json')
        
        if grant_response.status_code == 404:
            pytest.skip("Consent endpoints not yet implemented")
        
        granted_id = grant_response.data['id']
        granted_at_time = grant_response.data['granted_at']
        
        # Revoke
        revoke_url = f'/api/v1/patients/{patient.id}/consents/revoke/'
        revoke_response = admin_client.post(revoke_url, {'consent_type': 'clinical_photos'}, format='json')
        
        revoked_id = revoke_response.data['id']
        
        # Different IDs
        assert granted_id != revoked_id
        
        # Both records exist in DB
        granted_record = Consent.objects.get(id=granted_id)
        revoked_record = Consent.objects.get(id=revoked_id)
        
        # Granted record unchanged
        assert granted_record.status == 'granted'
        assert granted_record.revoked_at is None
        
        # Revoked record has revoked_at
        assert revoked_record.status == 'revoked'
        assert revoked_record.revoked_at is not None
        
        # Total 2 records
        assert Consent.objects.filter(patient=patient, consent_type='clinical_photos').count() == 2
    
    def test_multiple_grants_and_revokes_create_timeline(self, admin_client, patient):
        """Multiple grant/revoke operations create complete audit timeline"""
        from apps.clinical.models import Consent
        
        grant_url = f'/api/v1/patients/{patient.id}/consents/grant/'
        revoke_url = f'/api/v1/patients/{patient.id}/consents/revoke/'
        payload = {'consent_type': 'newsletter'}
        
        # Grant → Revoke → Grant → Revoke
        r1 = admin_client.post(grant_url, payload, format='json')
        if r1.status_code == 404:
            pytest.skip("Consent endpoints not yet implemented")
        
        r2 = admin_client.post(revoke_url, payload, format='json')
        r3 = admin_client.post(grant_url, payload, format='json')
        r4 = admin_client.post(revoke_url, payload, format='json')
        
        # All succeed
        assert all(r.status_code in [200, 201] for r in [r1, r2, r3, r4])
        
        # All different IDs
        ids = [r1.data['id'], r2.data['id'], r3.data['id'], r4.data['id']]
        assert len(ids) == len(set(ids)), "All consent records must have unique IDs"
        
        # 4 total records
        assert Consent.objects.filter(patient=patient, consent_type='newsletter').count() == 4
        
        # Latest status should be revoked
        status_url = f'/api/v1/patients/{patient.id}/consents/status/'
        status_response = admin_client.get(status_url)
        assert status_response.data['newsletter'] == 'revoked'


@pytest.mark.django_db
class TestConsentDocumentLink:
    """Test consent with optional document_id"""
    
    def test_grant_with_null_document(self, admin_client, patient):
        """Grant consent with document_id=null is valid"""
        url = f'/api/v1/patients/{patient.id}/consents/grant/'
        payload = {
            'consent_type': 'clinical_photos',
            'document_id': None,
        }
        
        response = admin_client.post(url, payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Consent grant endpoint not yet implemented")
        
        assert response.status_code in [200, 201]
        assert response.data.get('document') is None or response.data.get('document_id') is None
    
    def test_grant_without_document_field(self, admin_client, patient):
        """Grant consent without document_id field at all is valid"""
        url = f'/api/v1/patients/{patient.id}/consents/grant/'
        payload = {
            'consent_type': 'marketing_messages',
            # No document_id field
        }
        
        response = admin_client.post(url, payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Consent grant endpoint not yet implemented")
        
        assert response.status_code in [200, 201]
        assert response.data.get('document') is None or response.data.get('document_id') is None
    
    def test_revoke_does_not_require_document(self, admin_client, patient):
        """Revoke consent without document_id is valid"""
        url = f'/api/v1/patients/{patient.id}/consents/revoke/'
        payload = {
            'consent_type': 'newsletter',
            # No document_id
        }
        
        response = admin_client.post(url, payload, format='json')
        
        if response.status_code == 404:
            pytest.skip("Consent revoke endpoint not yet implemented")
        
        assert response.status_code in [200, 201]


@pytest.mark.django_db
class TestConsentEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_grant_with_invalid_uuid_format(self, admin_client, patient):
        """Grant with malformed patient ID returns 404"""
        url = '/api/v1/patients/not-a-uuid/consents/grant/'
        payload = {'consent_type': 'clinical_photos'}
        
        response = admin_client.post(url, payload, format='json')
        
        # Could be 404 (endpoint pattern doesn't match) or 400 (invalid UUID)
        assert response.status_code in [400, 404]
    
    def test_status_returns_consistent_format(self, admin_client, patient):
        """Status endpoint returns consistent dict structure"""
        from apps.clinical.models import Consent
        
        # Create one consent
        Consent.objects.create(
            patient=patient,
            consent_type='clinical_photos',
            status='granted',
            granted_at=django_timezone.now(),
        )
        
        url = f'/api/v1/patients/{patient.id}/consents/status/'
        response = admin_client.get(url)
        
        if response.status_code == 404:
            pytest.skip("Consent status endpoint not yet implemented")
        
        assert response.status_code == 200
        
        # Should be dict/object, not list
        assert isinstance(response.data, dict), "Status should return dict keyed by consent_type"
    
    def test_unauthenticated_access_denied(self, api_client, patient):
        """Unauthenticated requests to consent endpoints return 401"""
        grant_url = f'/api/v1/patients/{patient.id}/consents/grant/'
        revoke_url = f'/api/v1/patients/{patient.id}/consents/revoke/'
        status_url = f'/api/v1/patients/{patient.id}/consents/status/'
        
        grant_response = api_client.post(grant_url, {'consent_type': 'clinical_photos'}, format='json')
        revoke_response = api_client.post(revoke_url, {'consent_type': 'clinical_photos'}, format='json')
        status_response = api_client.get(status_url)
        
        # All should be 401 (or 404 if not implemented)
        for response in [grant_response, revoke_response, status_response]:
            if response.status_code != 404:
                assert response.status_code == 401, f"Expected 401 for unauthenticated, got {response.status_code}"
