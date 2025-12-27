"""
Tests for Calendly webhook signature verification.

Tests signature validation following Calendly's documented format:
- Header: Calendly-Webhook-Signature
- Format: t=<timestamp>,v1=<signature>
- Signed payload: <timestamp>.<raw_body>
- Algorithm: HMAC-SHA256
"""
import pytest
import hmac
import hashlib
import time
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework import status


pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    """API client for webhook tests."""
    return APIClient()


@pytest.fixture
def webhook_secret():
    """Test webhook secret."""
    return 'test-webhook-secret-12345'


@pytest.fixture
def sample_payload():
    """Sample Calendly webhook payload."""
    return b'{"event":"invitee.created","payload":{"event":"test"}}'


def generate_valid_signature(payload_bytes, secret, timestamp=None):
    """
    Generate valid Calendly signature.
    
    Format: t=<timestamp>,v1=<signature>
    Signed content: <timestamp>.<raw_body>
    """
    if timestamp is None:
        timestamp = str(int(time.time()))
    
    # Build signed payload: timestamp + '.' + raw body
    signed_payload = f"{timestamp}.".encode() + payload_bytes
    
    # Calculate HMAC-SHA256
    signature = hmac.new(
        secret.encode(),
        signed_payload,
        hashlib.sha256
    ).hexdigest()
    
    # Return header value
    return f"t={timestamp},v1={signature}", timestamp


class TestCalendlyWebhookSignatureVerification:
    """Test Calendly webhook signature verification."""
    
    @override_settings(CALENDLY_WEBHOOK_SECRET='test-webhook-secret-12345')
    def test_webhook_without_signature_header_rejected(self, api_client, sample_payload):
        """Webhook request without signature header should be rejected with 401."""
        response = api_client.post(
            '/api/integrations/calendly/webhook/',
            data=sample_payload,
            content_type='application/json'
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'signature' in response.data.get('error', '').lower()
    
    @override_settings(CALENDLY_WEBHOOK_SECRET='test-webhook-secret-12345')
    def test_webhook_with_empty_signature_rejected(self, api_client, sample_payload):
        """Webhook with empty signature header should be rejected."""
        response = api_client.post(
            '/api/integrations/calendly/webhook/',
            data=sample_payload,
            content_type='application/json',
            HTTP_CALENDLY_WEBHOOK_SIGNATURE=''
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @override_settings(CALENDLY_WEBHOOK_SECRET='test-webhook-secret-12345')
    def test_webhook_with_invalid_format_rejected(self, api_client, sample_payload):
        """Webhook with invalid signature format (no t= or v1=) should be rejected."""
        # Missing t= timestamp
        response = api_client.post(
            '/api/integrations/calendly/webhook/',
            data=sample_payload,
            content_type='application/json',
            HTTP_CALENDLY_WEBHOOK_SIGNATURE='v1=abc123'
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Missing v1= signature
        response = api_client.post(
            '/api/integrations/calendly/webhook/',
            data=sample_payload,
            content_type='application/json',
            HTTP_CALENDLY_WEBHOOK_SIGNATURE='t=1234567890'
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Wrong format (plain signature)
        response = api_client.post(
            '/api/integrations/calendly/webhook/',
            data=sample_payload,
            content_type='application/json',
            HTTP_CALENDLY_WEBHOOK_SIGNATURE='abc123def456'
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @override_settings(CALENDLY_WEBHOOK_SECRET='test-webhook-secret-12345')
    def test_webhook_with_wrong_signature_rejected(self, api_client, sample_payload, webhook_secret):
        """Webhook with incorrect signature should be rejected."""
        timestamp = str(int(time.time()))
        wrong_signature = 'wrong_signature_value_' + 'a' * 40
        
        response = api_client.post(
            '/api/integrations/calendly/webhook/',
            data=sample_payload,
            content_type='application/json',
            HTTP_CALENDLY_WEBHOOK_SIGNATURE=f't={timestamp},v1={wrong_signature}'
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'invalid' in response.data.get('error', '').lower()
    
    @override_settings(CALENDLY_WEBHOOK_SECRET='test-webhook-secret-12345')
    def test_webhook_with_valid_signature_accepted(self, api_client, sample_payload, webhook_secret):
        """Webhook with valid signature should be accepted."""
        signature_header, timestamp = generate_valid_signature(sample_payload, webhook_secret)
        
        response = api_client.post(
            '/api/integrations/calendly/webhook/',
            data=sample_payload,
            content_type='application/json',
            HTTP_CALENDLY_WEBHOOK_SIGNATURE=signature_header
        )
        
        # Should accept (200 or 204)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT]
    
    @override_settings(CALENDLY_WEBHOOK_SECRET='test-webhook-secret-12345')
    def test_webhook_signature_uses_raw_body(self, api_client, webhook_secret):
        """Signature verification should use raw body bytes, not re-serialized JSON."""
        # Payload with specific formatting (spaces, order)
        payload_bytes = b'{"event": "invitee.created",  "payload": {"test": true}}'
        
        signature_header, timestamp = generate_valid_signature(payload_bytes, webhook_secret)
        
        response = api_client.post(
            '/api/integrations/calendly/webhook/',
            data=payload_bytes,
            content_type='application/json',
            HTTP_CALENDLY_WEBHOOK_SIGNATURE=signature_header
        )
        
        # Should work because we use raw body
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT]
    
    @override_settings(CALENDLY_WEBHOOK_SECRET='test-webhook-secret-12345')
    def test_webhook_signature_with_different_payload_rejected(self, api_client, webhook_secret):
        """Signature valid for different payload should be rejected."""
        original_payload = b'{"event":"invitee.created"}'
        tampered_payload = b'{"event":"invitee.canceled"}'
        
        # Generate signature for original payload
        signature_header, timestamp = generate_valid_signature(original_payload, webhook_secret)
        
        # Try to use it with tampered payload
        response = api_client.post(
            '/api/integrations/calendly/webhook/',
            data=tampered_payload,
            content_type='application/json',
            HTTP_CALENDLY_WEBHOOK_SIGNATURE=signature_header
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @override_settings(CALENDLY_WEBHOOK_SECRET='')
    def test_webhook_without_configured_secret_rejected(self, api_client, sample_payload):
        """Webhook without configured secret should reject all requests."""
        signature_header, timestamp = generate_valid_signature(sample_payload, 'any-secret')
        
        response = api_client.post(
            '/api/integrations/calendly/webhook/',
            data=sample_payload,
            content_type='application/json',
            HTTP_CALENDLY_WEBHOOK_SIGNATURE=signature_header
        )
        
        # Should reject - no secret configured
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @override_settings(CALENDLY_WEBHOOK_SECRET='test-webhook-secret-12345')
    def test_webhook_with_old_timestamp_rejected(self, api_client, sample_payload, webhook_secret):
        """Webhook with timestamp older than 5 minutes should be rejected."""
        # Timestamp from 10 minutes ago
        old_timestamp = str(int(time.time()) - 600)
        
        signature_header, _ = generate_valid_signature(sample_payload, webhook_secret, timestamp=old_timestamp)
        
        response = api_client.post(
            '/api/integrations/calendly/webhook/',
            data=sample_payload,
            content_type='application/json',
            HTTP_CALENDLY_WEBHOOK_SIGNATURE=signature_header
        )
        
        # Should reject due to old timestamp
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'timestamp' in response.data.get('error', '').lower() or 'expired' in response.data.get('error', '').lower()
    
    @override_settings(CALENDLY_WEBHOOK_SECRET='test-webhook-secret-12345')
    def test_webhook_rejects_x_calendly_signature_header(self, api_client, sample_payload, webhook_secret):
        """Legacy X-Calendly-Signature header should NOT be accepted."""
        # Try with old header name (should not work)
        signature_header, timestamp = generate_valid_signature(sample_payload, webhook_secret)
        
        response = api_client.post(
            '/api/integrations/calendly/webhook/',
            data=sample_payload,
            content_type='application/json',
            HTTP_X_CALENDLY_SIGNATURE=signature_header  # Wrong header
        )
        
        # Should reject - wrong header name
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
