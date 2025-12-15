"""Integration views - Webhooks, external APIs."""
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
import hmac
import hashlib


@api_view(['POST'])
@permission_classes([AllowAny])
def calendly_webhook(request):
    """
    Calendly webhook endpoint.
    Placeholder - add signature verification and event processing.
    """
    # Verify webhook signature
    signature = request.headers.get('Calendly-Webhook-Signature', '')
    secret = settings.CALENDLY_WEBHOOK_SECRET.encode()
    
    # Create expected signature
    body = request.body
    expected_signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(signature, expected_signature):
        return Response({'error': 'Invalid signature'}, status=status.HTTP_401_UNAUTHORIZED)
    
    # Process event
    event_data = request.data
    event_type = event_data.get('event')
    
    # TODO: Process different event types
    # - invitee.created
    # - invitee.canceled
    # etc.
    
    return Response({'status': 'received'}, status=status.HTTP_200_OK)
