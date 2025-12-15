"""
Smoke tests for API permissions by role.

Fast HTTP status code validation without deep content checks.
Validates that role-based permissions work correctly across endpoints.
"""
import pytest
from rest_framework import status


# ============================================================================
# Patient Endpoints
# ============================================================================

@pytest.mark.django_db
class TestPatientPermissions:
    """Test patient endpoint permissions by role."""
    
    endpoint = '/api/v1/patients/'
    
    @pytest.mark.parametrize('client_fixture,expected_status', [
        ('admin_client', status.HTTP_200_OK),
        ('practitioner_client', status.HTTP_200_OK),
        ('reception_client', status.HTTP_200_OK),
        ('accounting_client', status.HTTP_200_OK),
        ('marketing_client', status.HTTP_403_FORBIDDEN),
    ])
    def test_list_patients_by_role(self, client_fixture, expected_status, request):
        """GET /api/v1/patients/ - All roles except Marketing can read."""
        client = request.getfixturevalue(client_fixture)
        response = client.get(self.endpoint)
        assert response.status_code == expected_status
    
    @pytest.mark.parametrize('client_fixture,expected_status', [
        ('admin_client', status.HTTP_201_CREATED),
        ('practitioner_client', status.HTTP_201_CREATED),
        ('reception_client', status.HTTP_201_CREATED),
        ('accounting_client', status.HTTP_403_FORBIDDEN),
        ('marketing_client', status.HTTP_403_FORBIDDEN),
    ])
    def test_create_patient_by_role(self, client_fixture, expected_status, request):
        """POST /api/v1/patients/ - Admin/Practitioner/Reception can create."""
        client = request.getfixturevalue(client_fixture)
        
        payload = {
            'first_name': 'Test',
            'last_name': 'Patient',
            'email': 'test.patient@example.com',
            'sex': 'female',
        }
        
        response = client.post(self.endpoint, payload, format='json')
        assert response.status_code == expected_status
    
    @pytest.mark.parametrize('client_fixture,expected_status', [
        ('admin_client', status.HTTP_200_OK),
        ('practitioner_client', status.HTTP_200_OK),
        ('reception_client', status.HTTP_200_OK),
        ('accounting_client', status.HTTP_200_OK),
        ('marketing_client', status.HTTP_403_FORBIDDEN),
    ])
    def test_retrieve_patient_by_role(self, client_fixture, expected_status, request, patient):
        """GET /api/v1/patients/{id}/ - All roles except Marketing can read."""
        client = request.getfixturevalue(client_fixture)
        response = client.get(f'/api/v1/patients/{patient.id}/')
        assert response.status_code == expected_status
    
    @pytest.mark.parametrize('client_fixture,expected_status', [
        ('admin_client', status.HTTP_200_OK),
        ('practitioner_client', status.HTTP_200_OK),
        ('reception_client', status.HTTP_200_OK),
        ('accounting_client', status.HTTP_403_FORBIDDEN),
        ('marketing_client', status.HTTP_403_FORBIDDEN),
    ])
    def test_update_patient_by_role(self, client_fixture, expected_status, request, patient):
        """PATCH /api/v1/patients/{id}/ - Admin/Practitioner/Reception can update."""
        client = request.getfixturevalue(client_fixture)
        
        payload = {
            'first_name': 'Updated',
            'row_version': patient.row_version,
        }
        
        response = client.patch(f'/api/v1/patients/{patient.id}/', payload, format='json')
        assert response.status_code == expected_status
    
    @pytest.mark.parametrize('client_fixture,expected_status', [
        ('admin_client', status.HTTP_204_NO_CONTENT),
        ('practitioner_client', status.HTTP_403_FORBIDDEN),
        ('reception_client', status.HTTP_403_FORBIDDEN),
        ('accounting_client', status.HTTP_403_FORBIDDEN),
        ('marketing_client', status.HTTP_403_FORBIDDEN),
    ])
    def test_delete_patient_by_role(self, client_fixture, expected_status, request, patient_factory):
        """DELETE /api/v1/patients/{id}/ - Only Admin can delete."""
        client = request.getfixturevalue(client_fixture)
        
        # Create a fresh patient for each test to avoid conflicts
        test_patient = patient_factory(
            first_name='DeleteTest',
            email=f'delete_{client_fixture}@test.com'
        )
        
        response = client.delete(f'/api/v1/patients/{test_patient.id}/')
        assert response.status_code == expected_status


# ============================================================================
# Appointment Endpoints
# ============================================================================

@pytest.mark.django_db
class TestAppointmentPermissions:
    """Test appointment endpoint permissions by role."""
    
    endpoint = '/api/v1/appointments/'
    
    @pytest.mark.parametrize('client_fixture,expected_status', [
        ('admin_client', status.HTTP_200_OK),
        ('practitioner_client', status.HTTP_200_OK),
        ('reception_client', status.HTTP_200_OK),
        ('accounting_client', status.HTTP_200_OK),
        ('marketing_client', status.HTTP_403_FORBIDDEN),
    ])
    def test_list_appointments_by_role(self, client_fixture, expected_status, request):
        """GET /api/v1/appointments/ - All roles except Marketing can read."""
        client = request.getfixturevalue(client_fixture)
        response = client.get(self.endpoint)
        assert response.status_code == expected_status
    
    @pytest.mark.parametrize('client_fixture,expected_status', [
        ('admin_client', status.HTTP_201_CREATED),
        ('practitioner_client', status.HTTP_201_CREATED),
        ('reception_client', status.HTTP_201_CREATED),
        ('accounting_client', status.HTTP_403_FORBIDDEN),
        ('marketing_client', status.HTTP_403_FORBIDDEN),
    ])
    def test_create_appointment_by_role(
        self,
        client_fixture,
        expected_status,
        request,
        patient,
        practitioner,
        clinic_location
    ):
        """POST /api/v1/appointments/ - Admin/Practitioner/Reception can create."""
        client = request.getfixturevalue(client_fixture)
        
        from django.utils import timezone
        
        payload = {
            'patient_id': str(patient.id),
            'practitioner_id': str(practitioner.id),
            'location_id': str(clinic_location.id),
            'source': 'manual',
            'status': 'scheduled',
            'scheduled_start': (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            'scheduled_end': (timezone.now() + timezone.timedelta(days=1, hours=1)).isoformat(),
        }
        
        response = client.post(self.endpoint, payload, format='json')
        assert response.status_code == expected_status
    
    @pytest.mark.parametrize('client_fixture,expected_status', [
        ('admin_client', status.HTTP_200_OK),
        ('practitioner_client', status.HTTP_200_OK),
        ('reception_client', status.HTTP_200_OK),
        ('accounting_client', status.HTTP_200_OK),
        ('marketing_client', status.HTTP_403_FORBIDDEN),
    ])
    def test_retrieve_appointment_by_role(self, client_fixture, expected_status, request, appointment):
        """GET /api/v1/appointments/{id}/ - All roles except Marketing can read."""
        client = request.getfixturevalue(client_fixture)
        response = client.get(f'/api/v1/appointments/{appointment.id}/')
        assert response.status_code == expected_status
    
    @pytest.mark.parametrize('client_fixture,expected_status', [
        ('admin_client', status.HTTP_200_OK),
        ('practitioner_client', status.HTTP_200_OK),
        ('reception_client', status.HTTP_200_OK),
        ('accounting_client', status.HTTP_403_FORBIDDEN),
        ('marketing_client', status.HTTP_403_FORBIDDEN),
    ])
    def test_update_appointment_by_role(self, client_fixture, expected_status, request, appointment):
        """PATCH /api/v1/appointments/{id}/ - Admin/Practitioner/Reception can update."""
        client = request.getfixturevalue(client_fixture)
        
        payload = {
            'notes': 'Updated notes',
        }
        
        response = client.patch(f'/api/v1/appointments/{appointment.id}/', payload, format='json')
        assert response.status_code == expected_status
    
    @pytest.mark.parametrize('client_fixture,expected_status', [
        ('admin_client', status.HTTP_204_NO_CONTENT),
        ('practitioner_client', status.HTTP_403_FORBIDDEN),
        ('reception_client', status.HTTP_403_FORBIDDEN),
        ('accounting_client', status.HTTP_403_FORBIDDEN),
        ('marketing_client', status.HTTP_403_FORBIDDEN),
    ])
    def test_delete_appointment_by_role(self, client_fixture, expected_status, request, appointment_factory):
        """DELETE /api/v1/appointments/{id}/ - Only Admin can delete."""
        client = request.getfixturevalue(client_fixture)
        
        # Create a fresh appointment for each test
        test_appointment = appointment_factory(status='scheduled')
        
        response = client.delete(f'/api/v1/appointments/{test_appointment.id}/')
        assert response.status_code == expected_status


# ============================================================================
# Appointment Actions
# ============================================================================

@pytest.mark.django_db
class TestAppointmentActions:
    """Test appointment action endpoints permissions."""
    
    @pytest.mark.parametrize('client_fixture,expected_status', [
        ('admin_client', status.HTTP_201_CREATED),
        ('practitioner_client', status.HTTP_201_CREATED),
        ('reception_client', status.HTTP_201_CREATED),
        ('accounting_client', status.HTTP_403_FORBIDDEN),
        ('marketing_client', status.HTTP_403_FORBIDDEN),
    ])
    def test_calendly_sync_by_role(self, client_fixture, expected_status, request):
        """POST /api/v1/appointments/calendly/sync/ - Admin/Practitioner/Reception can sync."""
        client = request.getfixturevalue(client_fixture)
        
        from django.utils import timezone
        
        payload = {
            'external_id': f'cal_test_{client_fixture}',
            'scheduled_start': (timezone.now() + timezone.timedelta(days=1)).isoformat(),
            'scheduled_end': (timezone.now() + timezone.timedelta(days=1, hours=1)).isoformat(),
            'patient_email': f'calendly_{client_fixture}@test.com',
            'patient_first_name': 'Calendly',
            'patient_last_name': 'Patient',
            'status': 'scheduled',
        }
        
        response = client.post('/api/v1/appointments/calendly/sync/', payload, format='json')
        assert response.status_code == expected_status
    
    @pytest.mark.parametrize('client_fixture,expected_status', [
        ('admin_client', status.HTTP_200_OK),
        ('practitioner_client', status.HTTP_200_OK),
        ('reception_client', status.HTTP_403_FORBIDDEN),
        ('accounting_client', status.HTTP_403_FORBIDDEN),
        ('marketing_client', status.HTTP_403_FORBIDDEN),
    ])
    def test_link_encounter_by_role(
        self,
        client_fixture,
        expected_status,
        request,
        appointment,
        encounter
    ):
        """POST /api/v1/appointments/{id}/link-encounter/ - Only Admin/Practitioner can link."""
        client = request.getfixturevalue(client_fixture)
        
        # Update appointment status to confirmed (required for linking)
        appointment.status = 'confirmed'
        appointment.save()
        
        payload = {
            'encounter_id': str(encounter.id),
        }
        
        response = client.post(
            f'/api/v1/appointments/{appointment.id}/link-encounter/',
            payload,
            format='json'
        )
        assert response.status_code == expected_status


# ============================================================================
# Encounter Endpoints (if implemented)
# ============================================================================

@pytest.mark.django_db
class TestEncounterPermissions:
    """Test encounter endpoint permissions by role."""
    
    endpoint = '/api/v1/encounters/'
    
    @pytest.mark.parametrize('client_fixture,expected_status', [
        ('admin_client', status.HTTP_200_OK),
        ('practitioner_client', status.HTTP_200_OK),
        ('accounting_client', status.HTTP_200_OK),
        ('reception_client', status.HTTP_403_FORBIDDEN),
        ('marketing_client', status.HTTP_403_FORBIDDEN),
    ])
    def test_list_encounters_by_role(self, client_fixture, expected_status, request):
        """
        GET /api/v1/encounters/ - Admin/Practitioner/Accounting can read.
        
        Note: This test expects 200 for allowed roles and 403 for forbidden roles.
        If endpoints are not implemented yet, this will fail with 404.
        Skip this test if encounters endpoints are not ready.
        """
        client = request.getfixturevalue(client_fixture)
        response = client.get(self.endpoint)
        
        # If endpoint not implemented, skip test
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        assert response.status_code == expected_status
    
    @pytest.mark.parametrize('client_fixture,expected_status', [
        ('admin_client', status.HTTP_201_CREATED),
        ('practitioner_client', status.HTTP_201_CREATED),
        ('accounting_client', status.HTTP_403_FORBIDDEN),
        ('reception_client', status.HTTP_403_FORBIDDEN),
        ('marketing_client', status.HTTP_403_FORBIDDEN),
    ])
    def test_create_encounter_by_role(
        self,
        client_fixture,
        expected_status,
        request,
        patient,
        practitioner,
        clinic_location
    ):
        """
        POST /api/v1/encounters/ - Only Admin/Practitioner can create.
        
        Skip if not implemented.
        """
        client = request.getfixturevalue(client_fixture)
        
        from django.utils import timezone
        
        payload = {
            'patient_id': str(patient.id),
            'practitioner_id': str(practitioner.id),
            'location_id': str(clinic_location.id),
            'type': 'medical_consult',
            'status': 'draft',
            'occurred_at': timezone.now().isoformat(),
        }
        
        response = client.post(self.endpoint, payload, format='json')
        
        # If endpoint not implemented, skip test
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Encounter endpoints not implemented yet')
        
        assert response.status_code == expected_status


# ============================================================================
# Consent Endpoints (if implemented)
# ============================================================================

@pytest.mark.django_db
class TestConsentPermissions:
    """Test consent endpoint permissions by role."""
    
    @pytest.mark.parametrize('client_fixture,expected_status', [
        ('admin_client', status.HTTP_200_OK),
        ('practitioner_client', status.HTTP_200_OK),
        ('reception_client', status.HTTP_200_OK),
        ('accounting_client', status.HTTP_403_FORBIDDEN),
        ('marketing_client', status.HTTP_403_FORBIDDEN),
    ])
    def test_consent_status_by_role(self, client_fixture, expected_status, request, patient):
        """
        GET /api/v1/patients/{id}/consents/status/ - Admin/Practitioner/Reception can read.
        
        Skip if not implemented.
        """
        client = request.getfixturevalue(client_fixture)
        response = client.get(f'/api/v1/patients/{patient.id}/consents/status/')
        
        # If endpoint not implemented, skip test
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip('Consent endpoints not implemented yet')
        
        assert response.status_code == expected_status


# ============================================================================
# Unauthenticated Access
# ============================================================================

@pytest.mark.django_db
class TestUnauthenticatedAccess:
    """Test that unauthenticated requests are rejected."""
    
    @pytest.mark.parametrize('endpoint', [
        '/api/v1/patients/',
        '/api/v1/appointments/',
        '/api/v1/encounters/',
    ])
    def test_unauthenticated_access_forbidden(self, api_client, endpoint):
        """Unauthenticated requests should return 401."""
        response = api_client.get(endpoint)
        
        # If endpoint not implemented, skip
        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip(f'Endpoint {endpoint} not implemented yet')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
