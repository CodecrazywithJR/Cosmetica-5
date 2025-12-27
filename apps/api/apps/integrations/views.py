"""Integration views - Webhooks, external APIs."""
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
import hmac
import hashlib
import time


def verify_calendly_webhook_signature(request) -> tuple[bool, str]:
    """
    Verify Calendly webhook signature.
    
    Follows Calendly's documented signature format:
    - Header: Calendly-Webhook-Signature
    - Format: t=<timestamp>,v1=<signature>
    - Signed payload: <timestamp>.<raw_body>
    - Algorithm: HMAC-SHA256
    
    Returns:
        (is_valid: bool, error_message: str)
    """
    # Get signature header
    signature_header = request.headers.get('Calendly-Webhook-Signature', '')
    
    if not signature_header:
        return False, 'Missing Calendly-Webhook-Signature header'
    
    # Get webhook secret
    secret = settings.CALENDLY_WEBHOOK_SECRET
    if not secret:
        return False, 'Webhook secret not configured'
    
    # Parse signature header: t=<timestamp>,v1=<signature>
    try:
        parts = {}
        for part in signature_header.split(','):
            key, value = part.split('=', 1)
            parts[key.strip()] = value.strip()
        
        timestamp = parts.get('t')
        signature = parts.get('v1')
        
        if not timestamp or not signature:
            return False, 'Invalid signature format (missing t= or v1=)'
    except (ValueError, AttributeError):
        return False, 'Invalid signature format'
    
    # Validate timestamp (reject if older than 5 minutes)
    try:
        timestamp_int = int(timestamp)
        current_time = int(time.time())
        age_seconds = current_time - timestamp_int
        
        if age_seconds > 300:  # 5 minutes
            return False, 'Signature timestamp expired'
        if age_seconds < -60:  # Future timestamp (allow 1 min clock skew)
            return False, 'Signature timestamp is in the future'
    except (ValueError, TypeError):
        return False, 'Invalid timestamp format'
    
    # Build signed payload: <timestamp>.<raw_body>
    raw_body = request.body
    signed_payload = f"{timestamp}.".encode() + raw_body
    
    # Calculate expected signature
    expected_signature = hmac.new(
        secret.encode(),
        signed_payload,
        hashlib.sha256
    ).hexdigest()
    
    # Constant-time comparison
    if not hmac.compare_digest(signature, expected_signature):
        return False, 'Invalid signature'
    
    return True, ''


@api_view(['POST'])
@permission_classes([AllowAny])
def calendly_webhook(request):
    """
    Calendly webhook endpoint.
    
    Validates webhook signature following Calendly's documented format:
    - Header: Calendly-Webhook-Signature
    - Format: t=<timestamp>,v1=<signature>
    
    Processes Calendly events:
    - invitee.created: Creates/updates appointment via _process_calendly_sync()
    - invitee.canceled: Updates appointment status to 'cancelled'
    
    Security:
    - Signature verification (HMAC-SHA256)
    - Timestamp validation (5-minute window)
    - Constant-time comparison
    
    Returns:
    - 401: Invalid or missing signature
    - 200: Event received and processed (even if processing fails internally)
    
    Note: Always returns 200 OK after signature validation to prevent webhook retries.
          Processing errors are logged but don't block the response.
    """
    import logging
    from django.utils.dateparse import parse_datetime
    from apps.clinical.views import _process_calendly_sync
    from apps.clinical.models import Appointment
    
    logger = logging.getLogger(__name__)
    
    # Verify webhook signature
    is_valid, error_message = verify_calendly_webhook_signature(request)
    
    if not is_valid:
        logger.warning(f'[CALENDLY_WEBHOOK] Invalid signature: {error_message}')
        return Response(
            {'error': error_message},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Extract event data
    event_data = request.data
    event_type = event_data.get('event')
    
    logger.info(f'[CALENDLY_WEBHOOK] Event received: {event_type}')
    
    try:
        if event_type == 'invitee.created':
            # Extract data from Calendly payload
            # Calendly API v2 format: { event: "invitee.created", payload: { event: {...}, invitee: {...} } }
            payload = event_data.get('payload', {})
            event_info = payload.get('event', {})
            invitee_info = payload.get('invitee', {})
            
            # Extract external_id from event URI (e.g., "https://api.calendly.com/scheduled_events/ABC123")
            event_uri = event_info.get('uri', '')
            external_id = event_uri.split('/')[-1] if event_uri else None
            
            if not external_id:
                logger.error('[CALENDLY_WEBHOOK] Missing external_id in invitee.created event')
                return Response({'status': 'received', 'error': 'Missing external_id'}, status=status.HTTP_200_OK)
            
            # Parse datetime fields
            scheduled_start_raw = event_info.get('start_time')
            scheduled_end_raw = event_info.get('end_time')
            
            if not scheduled_start_raw or not scheduled_end_raw:
                logger.error(f'[CALENDLY_WEBHOOK] Missing datetime fields for event {external_id}')
                return Response({'status': 'received', 'error': 'Missing datetime fields'}, status=status.HTTP_200_OK)
            
            scheduled_start = parse_datetime(scheduled_start_raw)
            scheduled_end = parse_datetime(scheduled_end_raw)
            
            if not scheduled_start or not scheduled_end:
                logger.error(f'[CALENDLY_WEBHOOK] Invalid datetime format for event {external_id}')
                return Response({'status': 'received', 'error': 'Invalid datetime format'}, status=status.HTTP_200_OK)
            
            # Extract patient data from invitee
            patient_email = invitee_info.get('email')
            patient_name = invitee_info.get('name', '')
            patient_first_name = invitee_info.get('first_name', '')
            patient_last_name = invitee_info.get('last_name', '')
            
            # Fallback: if first/last not provided, split name
            if not patient_first_name and patient_name:
                name_parts = patient_name.split(' ', 1)
                patient_first_name = name_parts[0]
                patient_last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            patient_phone = invitee_info.get('text_reminder_number')
            
            # Build sync_data dict
            sync_data = {
                'external_id': external_id,
                'scheduled_start': scheduled_start,
                'scheduled_end': scheduled_end,
                'patient_email': patient_email,
                'patient_phone': patient_phone,
                'patient_first_name': patient_first_name,
                'patient_last_name': patient_last_name,
                'status': 'scheduled',
                'notes': f'Created via Calendly webhook: {event_info.get("name", "Appointment")}'
            }
            
            # Call shared sync logic
            appointment, created = _process_calendly_sync(sync_data, created_by_user=None)
            
            action = 'created' if created else 'updated'
            logger.info(f'[CALENDLY_WEBHOOK] Appointment {action}: {appointment.id} (external_id={external_id})')
            
            return Response({
                'status': 'received',
                'action': action,
                'appointment_id': str(appointment.id)
            }, status=status.HTTP_200_OK)
        
        elif event_type == 'invitee.canceled':
            # Extract external_id from event
            payload = event_data.get('payload', {})
            event_info = payload.get('event', {})
            event_uri = event_info.get('uri', '')
            external_id = event_uri.split('/')[-1] if event_uri else None
            
            if not external_id:
                logger.error('[CALENDLY_WEBHOOK] Missing external_id in invitee.canceled event')
                return Response({'status': 'received', 'error': 'Missing external_id'}, status=status.HTTP_200_OK)
            
            # Find and cancel appointment
            try:
                appointment = Appointment.objects.get(external_id=external_id)
                appointment.status = 'cancelled'
                appointment.cancellation_reason = 'Cancelled via Calendly webhook'
                appointment.save()
                
                logger.info(f'[CALENDLY_WEBHOOK] Appointment cancelled: {appointment.id} (external_id={external_id})')
                
                return Response({
                    'status': 'received',
                    'action': 'cancelled',
                    'appointment_id': str(appointment.id)
                }, status=status.HTTP_200_OK)
            
            except Appointment.DoesNotExist:
                logger.warning(f'[CALENDLY_WEBHOOK] Appointment not found for cancellation: external_id={external_id}')
                return Response({
                    'status': 'received',
                    'warning': 'Appointment not found'
                }, status=status.HTTP_200_OK)
        
        else:
            # Unknown event type - log and return 200 OK (don't trigger retries)
            logger.info(f'[CALENDLY_WEBHOOK] Unknown event type: {event_type}')
            return Response({
                'status': 'received',
                'info': f'Event type {event_type} not processed'
            }, status=status.HTTP_200_OK)
    
    except Exception as e:
        # CRITICAL: Return 200 OK even on error to prevent Calendly retries
        # The error is logged for monitoring, but we acknowledge receipt
        logger.error(f'[CALENDLY_WEBHOOK] Error processing event {event_type}: {str(e)}', exc_info=True)
        return Response({
            'status': 'received',
            'error': 'Internal processing error (logged)'
        }, status=status.HTTP_200_OK)

