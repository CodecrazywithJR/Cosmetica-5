"""
Public Booking API — Security Services

Provides:

1. PublicBookingTokenService — HMAC-signed tokens for public booking access.
   Tokens are generated server-side for embedding in public pages (clinic
   website, doctor landing page, approved Instagram link, etc.).
   Every public booking request must include a valid, non-expired token.

   Why signed tokens?
   Public booking endpoints accept unauthenticated traffic.  A signed token
   ensures the request originates from a trusted channel rather than an
   unauthenticated scraper or bot.  The server generates tokens that encode
   the allowed clinic_id (and optionally practitioner_id / treatment list)
   plus a TTL.

   Settings:
     PUBLIC_BOOKING_TOKEN_KEY      — signing key (defaults to SECRET_KEY)
     PUBLIC_BOOKING_TOKEN_MAX_AGE  — seconds (default 3600 = 1 hour)

2. AntiBotService — Pluggable CAPTCHA / anti-bot verification layer.
   Defaults to 'noop' (always passes).  Production environments set
   PUBLIC_BOOKING_ANTIBOT_BACKEND='require' and wire a real vendor backend
   (reCAPTCHA, hCaptcha, Cloudflare Turnstile, etc.).

   How to plug in a real vendor:
     a) Subclass AntiBotBackend and implement verify(token, remote_ip) → bool.
     b) Register your subclass in the AntiBotService.get_backend() resolver.
     c) Set PUBLIC_BOOKING_ANTIBOT_BACKEND to your key.

3. normalize_email_for_dedup / normalize_phone_for_dedup
   Lightweight normalization to prevent patient duplicates caused by trivial
   formatting differences (extra spaces, uppercase, dashes in phone, etc.).

   Dedup rules:
     • Email: strip whitespace + lowercase.
     • Phone: strip all non-digit characters except leading +.
       Returns None if result is shorter than 7 digits (not a real number).
     • No fuzzy matching — only formatting normalization.
     • Unrelated patients are never merged.
"""
import logging
import re

from django.conf import settings
from django.core import signing

logger = logging.getLogger(__name__)

# ── Signed Token Service ────────────────────────────────────────────

_TOKEN_SALT = 'public-booking-v1'


class PublicBookingTokenService:
    """
    HMAC-signed tokens for public booking access control.

    Token payload:
      cid  — clinic UUID (always present)
      pid  — practitioner UUID (optional, locks form to one practitioner)
      tids — list of treatment UUIDs (optional, restricts allowed treatments)

    Expiration is enforced automatically by django.core.signing.
    """

    @staticmethod
    def _key():
        return getattr(settings, 'PUBLIC_BOOKING_TOKEN_KEY', settings.SECRET_KEY)

    @staticmethod
    def _max_age():
        return getattr(settings, 'PUBLIC_BOOKING_TOKEN_MAX_AGE', 3600)

    @classmethod
    def generate(cls, *, clinic_id, practitioner_id=None, treatment_ids=None):
        """Generate a signed token.  Call server-side when rendering public forms."""
        payload = {'cid': str(clinic_id)}
        if practitioner_id:
            payload['pid'] = str(practitioner_id)
        if treatment_ids:
            payload['tids'] = [str(t) for t in treatment_ids]
        return signing.dumps(payload, key=cls._key(), salt=_TOKEN_SALT)

    @classmethod
    def verify(cls, token):
        """
        Verify signature + expiration.
        Returns (payload_dict, None) on success.
        Returns (None, 'expired'|'invalid') on failure.
        """
        try:
            payload = signing.loads(
                token, key=cls._key(), salt=_TOKEN_SALT,
                max_age=cls._max_age(),
            )
            return payload, None
        except signing.SignatureExpired:
            return None, 'expired'
        except signing.BadSignature:
            return None, 'invalid'

    @classmethod
    def validate_request(cls, token_payload, *, clinic_id,
                         practitioner_id=None, treatment_id=None):
        """
        Cross-check token payload against actual API request params.
        Returns None on match, or a reason string on mismatch.
        """
        if str(token_payload.get('cid', '')) != str(clinic_id):
            return 'clinic_mismatch'
        token_pid = token_payload.get('pid')
        if token_pid and practitioner_id and str(token_pid) != str(practitioner_id):
            return 'practitioner_mismatch'
        token_tids = token_payload.get('tids')
        if token_tids and treatment_id and str(treatment_id) not in token_tids:
            return 'treatment_mismatch'
        return None


# ── Anti-Bot Service ────────────────────────────────────────────────

class AntiBotBackend:
    """Interface for CAPTCHA / anti-bot verification."""
    def verify(self, token, remote_ip):
        raise NotImplementedError


class NoopAntiBotBackend(AntiBotBackend):
    """Always passes — safe for development and tests."""
    def verify(self, token, remote_ip):
        return True


class _RequireTokenBackend(AntiBotBackend):
    """
    Requires a non-empty captcha_token.

    Production deployments should subclass and call the real vendor API
    (reCAPTCHA, hCaptcha, Cloudflare Turnstile, etc.).
    The verify(token, remote_ip) → bool interface stays the same.
    """
    def verify(self, token, remote_ip):
        return bool(token and str(token).strip())


class AntiBotService:
    """
    Pluggable anti-bot verification.

    Settings:
      PUBLIC_BOOKING_ANTIBOT_BACKEND  — 'noop' | 'require' (default: 'noop')
    """

    @classmethod
    def get_backend(cls):
        mode = getattr(settings, 'PUBLIC_BOOKING_ANTIBOT_BACKEND', 'noop')
        if mode == 'require':
            return _RequireTokenBackend()
        return NoopAntiBotBackend()

    @classmethod
    def verify(cls, captcha_token, remote_ip):
        return cls.get_backend().verify(captcha_token, remote_ip)


# ── Normalization Helpers ───────────────────────────────────────────

def normalize_email_for_dedup(email):
    """
    Normalize email for patient deduplication.
    Rule: strip whitespace + lowercase.
    """
    if not email:
        return None
    return email.strip().lower() or None


def normalize_phone_for_dedup(phone):
    """
    Normalize phone for patient deduplication.
    Rule: strip all non-digit characters except leading +.
    Returns None if result is shorter than 7 chars (not a real number).
    """
    if not phone:
        return None
    cleaned = phone.strip()
    cleaned = re.sub(r'[^\d+]', '', cleaned)
    # Ensure + only at the start
    if '+' in cleaned:
        cleaned = '+' + cleaned.replace('+', '')
    if len(cleaned) < 7:
        return None
    return cleaned
