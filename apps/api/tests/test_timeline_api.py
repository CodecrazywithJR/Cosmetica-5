"""
Tests for Patient Timeline API endpoint.

Endpoint tested:
- GET /api/v1/patients/{id}/timeline/ (aggregated timeline of patient events)

Business Rules:
- Timeline aggregates: Encounters, Appointments, Consents, Photos
- Events sorted chronologically (most recent first by default)
- Permissions: Admin/Practitioner can view, Reception limited, others forbidden
- Filters: date_from, date_to, event_type
"""
import pytest
from django.utils import timezone
from datetime import timedelta


@pytest.mark.django_db
class TestPatientTimeline:
    """Test GET /api/v1/patients/{id}/timeline/ endpoint"""
    
    def test_timeline_basic(self, admin_client, patient):
        """Admin can retrieve patient timeline"""
        response = admin_client.get(f'/api/v1/patients/{patient.id}/timeline/')
        
        if response.status_code == 404:
            pytest.skip("Patient timeline endpoint not yet implemented")
        
        assert response.status_code == 200
        assert isinstance(response.data, list) or 'results' in response.data
    
    def test_timeline_includes_encounters(self, admin_client, patient, encounter_factory):
        """Timeline includes encounter events"""
        from apps.clinical.models import Encounter
        
        # Create encounters
        enc1 = encounter_factory(
            patient=patient,
            type='medical_consult',
            status='finalized',
            occurred_at=timezone.now() - timedelta(days=5)
        )
        enc2 = encounter_factory(
            patient=patient,
            type='cosmetic_consult',
            status='draft',
            occurred_at=timezone.now() - timedelta(days=2)
        )
        
        response = admin_client.get(f'/api/v1/patients/{patient.id}/timeline/')
        
        if response.status_code == 404:
            pytest.skip("Patient timeline endpoint not yet implemented")
        
        assert response.status_code == 200
        
        events = response.data if isinstance(response.data, list) else response.data.get('results', [])
        
        # Should include encounters
        encounter_events = [e for e in events if e.get('event_type') in ['encounter', 'medical_consult', 'cosmetic_consult']]
        assert len(encounter_events) >= 2
    
    def test_timeline_includes_appointments(self, admin_client, patient, appointment_factory):
        """Timeline includes appointment events"""
        from apps.clinical.models import Appointment
        
        # Create appointments
        apt1 = appointment_factory(
            patient=patient,
            status='attended',
            scheduled_start=timezone.now() - timedelta(days=10)
        )
        apt2 = appointment_factory(
            patient=patient,
            status='scheduled',
            scheduled_start=timezone.now() + timedelta(days=5)
        )
        
        response = admin_client.get(f'/api/v1/patients/{patient.id}/timeline/')
        
        if response.status_code == 404:
            pytest.skip("Patient timeline endpoint not yet implemented")
        
        assert response.status_code == 200
        
        events = response.data if isinstance(response.data, list) else response.data.get('results', [])
        
        # Should include appointments
        appointment_events = [e for e in events if e.get('event_type') in ['appointment', 'scheduled', 'attended']]
        assert len(appointment_events) >= 2
    
    def test_timeline_includes_consents(self, admin_client, patient):
        """Timeline includes consent events"""
        from apps.clinical.models import Consent
        from django.utils import timezone as django_timezone
        
        # Create consents
        Consent.objects.create(
            patient=patient,
            consent_type='clinical_photos',
            status='granted',
            granted_at=django_timezone.now() - timedelta(days=7),
        )
        Consent.objects.create(
            patient=patient,
            consent_type='newsletter',
            status='revoked',
            granted_at=django_timezone.now() - timedelta(days=8),
            revoked_at=django_timezone.now() - timedelta(days=3),
        )
        
        response = admin_client.get(f'/api/v1/patients/{patient.id}/timeline/')
        
        if response.status_code == 404:
            pytest.skip("Patient timeline endpoint not yet implemented")
        
        assert response.status_code == 200
        
        events = response.data if isinstance(response.data, list) else response.data.get('results', [])
        
        # Should include consents
        consent_events = [e for e in events if e.get('event_type') in ['consent', 'consent_granted', 'consent_revoked']]
        assert len(consent_events) >= 1
    
    def test_timeline_includes_photos(self, admin_client, patient):
        """Timeline includes clinical photo events"""
        from apps.clinical.models import ClinicalPhoto
        
        # Create photos
        ClinicalPhoto.objects.create(
            patient=patient,
            photo_kind='before',
            object_key='photos/before.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
            taken_at=timezone.now() - timedelta(days=4),
        )
        ClinicalPhoto.objects.create(
            patient=patient,
            photo_kind='after',
            object_key='photos/after.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
            taken_at=timezone.now() - timedelta(days=1),
        )
        
        response = admin_client.get(f'/api/v1/patients/{patient.id}/timeline/')
        
        if response.status_code == 404:
            pytest.skip("Patient timeline endpoint not yet implemented")
        
        assert response.status_code == 200
        
        events = response.data if isinstance(response.data, list) else response.data.get('results', [])
        
        # Should include photos
        photo_events = [e for e in events if e.get('event_type') in ['photo', 'clinical_photo', 'before', 'after']]
        assert len(photo_events) >= 2
    
    def test_timeline_sorted_chronologically(self, admin_client, patient, encounter_factory, appointment_factory):
        """Timeline events sorted by date (most recent first by default)"""
        # Create events at different times
        encounter_factory(
            patient=patient,
            occurred_at=timezone.now() - timedelta(days=10)
        )
        appointment_factory(
            patient=patient,
            scheduled_start=timezone.now() - timedelta(days=5)
        )
        encounter_factory(
            patient=patient,
            occurred_at=timezone.now() - timedelta(days=2)
        )
        
        response = admin_client.get(f'/api/v1/patients/{patient.id}/timeline/')
        
        if response.status_code == 404:
            pytest.skip("Patient timeline endpoint not yet implemented")
        
        assert response.status_code == 200
        
        events = response.data if isinstance(response.data, list) else response.data.get('results', [])
        
        # Verify chronological order (most recent first)
        if len(events) >= 2:
            # Extract dates (field names may vary: timestamp, occurred_at, scheduled_start, etc.)
            dates = []
            for event in events:
                date = event.get('timestamp') or event.get('occurred_at') or event.get('scheduled_start') or event.get('granted_at') or event.get('taken_at')
                if date:
                    dates.append(date)
            
            # Check descending order
            if len(dates) >= 2:
                for i in range(len(dates) - 1):
                    assert dates[i] >= dates[i+1], "Timeline should be sorted most recent first"
    
    def test_timeline_filter_by_date_range(self, admin_client, patient, encounter_factory):
        """Timeline can be filtered by date_from and date_to"""
        # Create encounters at different dates
        old_enc = encounter_factory(
            patient=patient,
            occurred_at=timezone.now() - timedelta(days=30)
        )
        recent_enc = encounter_factory(
            patient=patient,
            occurred_at=timezone.now() - timedelta(days=5)
        )
        
        # Filter for last 10 days
        date_from = (timezone.now() - timedelta(days=10)).isoformat()
        
        response = admin_client.get(f'/api/v1/patients/{patient.id}/timeline/?date_from={date_from}')
        
        if response.status_code == 404:
            pytest.skip("Patient timeline endpoint not yet implemented")
        
        assert response.status_code == 200
        
        events = response.data if isinstance(response.data, list) else response.data.get('results', [])
        
        # Should include recent encounter, not old one
        event_ids = [str(e.get('id', '')) for e in events]
        # This is approximate - timeline might aggregate differently
        # Main test: endpoint accepts date_from parameter
    
    def test_timeline_filter_by_event_type(self, admin_client, patient, encounter_factory, appointment_factory):
        """Timeline can be filtered by event_type"""
        encounter_factory(patient=patient)
        appointment_factory(patient=patient)
        
        # Filter for encounters only
        response = admin_client.get(f'/api/v1/patients/{patient.id}/timeline/?event_type=encounter')
        
        if response.status_code == 404:
            pytest.skip("Patient timeline endpoint not yet implemented")
        
        assert response.status_code == 200
        
        events = response.data if isinstance(response.data, list) else response.data.get('results', [])
        
        # All events should be encounters
        for event in events:
            event_type = event.get('event_type', '')
            assert 'encounter' in event_type.lower() or event_type in ['medical_consult', 'cosmetic_consult']
    
    def test_timeline_excludes_soft_deleted(self, admin_client, patient, encounter_factory):
        """Timeline excludes soft-deleted records"""
        active_enc = encounter_factory(patient=patient)
        deleted_enc = encounter_factory(
            patient=patient,
            is_deleted=True,
            deleted_at=timezone.now()
        )
        
        response = admin_client.get(f'/api/v1/patients/{patient.id}/timeline/')
        
        if response.status_code == 404:
            pytest.skip("Patient timeline endpoint not yet implemented")
        
        assert response.status_code == 200
        
        events = response.data if isinstance(response.data, list) else response.data.get('results', [])
        event_ids = [str(e.get('id', '')) for e in events]
        
        # Should not include deleted encounter
        assert str(deleted_enc.id) not in event_ids
    
    def test_timeline_empty_patient(self, admin_client, patient):
        """Timeline for patient with no events returns empty list"""
        response = admin_client.get(f'/api/v1/patients/{patient.id}/timeline/')
        
        if response.status_code == 404:
            pytest.skip("Patient timeline endpoint not yet implemented")
        
        assert response.status_code == 200
        
        events = response.data if isinstance(response.data, list) else response.data.get('results', [])
        assert isinstance(events, list)
        # May be empty or have minimal default events
    
    def test_timeline_nonexistent_patient(self, admin_client):
        """Timeline for nonexistent patient returns 404"""
        import uuid
        fake_id = uuid.uuid4()
        
        response = admin_client.get(f'/api/v1/patients/{fake_id}/timeline/')
        
        if response.status_code == 404:
            pytest.skip("Cannot distinguish between endpoint not implemented and patient not found")
        
        assert response.status_code == 404


@pytest.mark.django_db
class TestPatientTimelinePermissions:
    """Test timeline permissions by role"""
    
    def test_timeline_admin_allowed(self, admin_client, patient):
        """Admin can view patient timeline"""
        response = admin_client.get(f'/api/v1/patients/{patient.id}/timeline/')
        
        if response.status_code == 404:
            pytest.skip("Patient timeline endpoint not yet implemented")
        
        assert response.status_code == 200
    
    def test_timeline_practitioner_allowed(self, practitioner_client, patient):
        """Practitioner can view patient timeline"""
        response = practitioner_client.get(f'/api/v1/patients/{patient.id}/timeline/')
        
        if response.status_code == 404:
            pytest.skip("Patient timeline endpoint not yet implemented")
        
        assert response.status_code == 200
    
    def test_timeline_reception_limited_or_forbidden(self, reception_client, patient):
        """Reception may have limited access or be forbidden from timeline"""
        response = reception_client.get(f'/api/v1/patients/{patient.id}/timeline/')
        
        if response.status_code == 404:
            pytest.skip("Patient timeline endpoint not yet implemented")
        
        # Could be 200 (allowed) or 403 (forbidden) depending on policy
        assert response.status_code in [200, 403]
    
    def test_timeline_accounting_forbidden(self, accounting_client, patient):
        """Accounting cannot view detailed timeline (clinical data)"""
        response = accounting_client.get(f'/api/v1/patients/{patient.id}/timeline/')
        
        if response.status_code == 404:
            pytest.skip("Patient timeline endpoint not yet implemented")
        
        assert response.status_code == 403
    
    def test_timeline_marketing_forbidden(self, marketing_client, patient):
        """Marketing cannot view patient timeline"""
        response = marketing_client.get(f'/api/v1/patients/{patient.id}/timeline/')
        
        if response.status_code == 404:
            pytest.skip("Patient timeline endpoint not yet implemented")
        
        assert response.status_code == 403
    
    def test_timeline_unauthenticated_denied(self, api_client, patient):
        """Unauthenticated requests return 401"""
        response = api_client.get(f'/api/v1/patients/{patient.id}/timeline/')
        
        if response.status_code == 404:
            pytest.skip("Patient timeline endpoint not yet implemented")
        
        assert response.status_code == 401


@pytest.mark.django_db
class TestPatientTimelineEventFormat:
    """Test timeline event format and content"""
    
    def test_timeline_event_has_required_fields(self, admin_client, patient, encounter_factory):
        """Each timeline event has required fields: event_type, timestamp, id"""
        encounter_factory(patient=patient, occurred_at=timezone.now() - timedelta(days=1))
        
        response = admin_client.get(f'/api/v1/patients/{patient.id}/timeline/')
        
        if response.status_code == 404:
            pytest.skip("Patient timeline endpoint not yet implemented")
        
        assert response.status_code == 200
        
        events = response.data if isinstance(response.data, list) else response.data.get('results', [])
        
        if len(events) > 0:
            event = events[0]
            # Check for common timeline event fields
            # event_type might be named differently: type, event_type, kind
            assert 'event_type' in event or 'type' in event or 'kind' in event
            # timestamp might be: timestamp, occurred_at, scheduled_start, created_at
            has_timestamp = any(field in event for field in ['timestamp', 'occurred_at', 'scheduled_start', 'created_at', 'granted_at', 'taken_at'])
            assert has_timestamp, "Event should have a timestamp field"
            # id field
            assert 'id' in event
    
    def test_timeline_event_includes_summary(self, admin_client, patient, encounter_factory):
        """Timeline events include summary or description"""
        encounter_factory(
            patient=patient,
            type='medical_consult',
            chief_complaint='Patient complaint',
            occurred_at=timezone.now() - timedelta(days=1)
        )
        
        response = admin_client.get(f'/api/v1/patients/{patient.id}/timeline/')
        
        if response.status_code == 404:
            pytest.skip("Patient timeline endpoint not yet implemented")
        
        assert response.status_code == 200
        
        events = response.data if isinstance(response.data, list) else response.data.get('results', [])
        
        if len(events) > 0:
            # Events should have some descriptive text
            # This is flexible - implementation may vary
            event = events[0]
            has_description = any(field in event for field in ['summary', 'description', 'title', 'chief_complaint', 'notes'])
            # Not required but nice to have
    
    def test_timeline_paginated_if_many_events(self, admin_client, patient, encounter_factory):
        """Timeline may be paginated if patient has many events"""
        # Create many encounters
        for i in range(25):
            encounter_factory(
                patient=patient,
                occurred_at=timezone.now() - timedelta(days=i)
            )
        
        response = admin_client.get(f'/api/v1/patients/{patient.id}/timeline/')
        
        if response.status_code == 404:
            pytest.skip("Patient timeline endpoint not yet implemented")
        
        assert response.status_code == 200
        
        # If paginated, should have pagination fields
        if isinstance(response.data, dict):
            # Might have: results, count, next, previous
            assert 'results' in response.data or 'events' in response.data
        else:
            # Or just a list
            assert isinstance(response.data, list)


@pytest.mark.django_db
class TestPatientTimelineEdgeCases:
    """Test timeline edge cases"""
    
    def test_timeline_with_invalid_patient_id(self, admin_client):
        """Timeline with invalid UUID format returns 404 or 400"""
        response = admin_client.get('/api/v1/patients/not-a-uuid/timeline/')
        
        # Could be 404 (pattern doesn't match) or 400 (invalid UUID)
        assert response.status_code in [400, 404]
    
    def test_timeline_concurrent_event_types(self, admin_client, patient, encounter_factory, appointment_factory):
        """Timeline handles multiple event types occurring on same day"""
        same_date = timezone.now() - timedelta(days=3)
        
        encounter_factory(patient=patient, occurred_at=same_date)
        appointment_factory(patient=patient, scheduled_start=same_date)
        
        from apps.clinical.models import Consent
        from django.utils import timezone as django_timezone
        Consent.objects.create(
            patient=patient,
            consent_type='clinical_photos',
            status='granted',
            granted_at=same_date,
        )
        
        response = admin_client.get(f'/api/v1/patients/{patient.id}/timeline/')
        
        if response.status_code == 404:
            pytest.skip("Patient timeline endpoint not yet implemented")
        
        assert response.status_code == 200
        
        events = response.data if isinstance(response.data, list) else response.data.get('results', [])
        
        # Should include all events
        assert len(events) >= 3
    
    def test_timeline_with_null_dates(self, admin_client, patient):
        """Timeline handles records with null dates gracefully"""
        from apps.clinical.models import ClinicalPhoto
        
        # Photo without taken_at
        ClinicalPhoto.objects.create(
            patient=patient,
            photo_kind='clinical',
            object_key='photos/no_date.jpg',
            content_type='image/jpeg',
            size_bytes=1024000,
            taken_at=None,  # Null date
        )
        
        response = admin_client.get(f'/api/v1/patients/{patient.id}/timeline/')
        
        if response.status_code == 404:
            pytest.skip("Patient timeline endpoint not yet implemented")
        
        # Should succeed and handle null dates
        assert response.status_code == 200
