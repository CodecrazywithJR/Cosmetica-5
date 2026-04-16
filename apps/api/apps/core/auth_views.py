"""
Cookie-based JWT authentication views.

Architecture:
  LOGIN  → returns {access} in JSON, sets refresh_token as HttpOnly cookie
  REFRESH → reads refresh_token from cookie, returns {access} in JSON
  LOGOUT → blacklists refresh_token, deletes cookie

The refresh token is NEVER returned in JSON.
The browser manages the cookie; JavaScript cannot read it.
"""

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView


class AuthTokenThrottle(AnonRateThrottle):
    """Strict throttle for login attempts — 5 per minute."""
    rate = '5/min'


class AuthRefreshThrottle(AnonRateThrottle):
    """Throttle for token refresh — 30 per minute."""
    rate = '30/min'


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REFRESH_COOKIE_NAME = 'refresh_token'
REFRESH_COOKIE_PATH = '/api/auth/'


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------
def _set_refresh_cookie(response, token_value):
    """Set HttpOnly refresh-token cookie on the response."""
    max_age = int(
        settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()
    )
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token_value,
        max_age=max_age,
        httponly=True,
        secure=not settings.DEBUG,  # True in production (HTTPS only)
        samesite='Lax',
        path=REFRESH_COOKIE_PATH,
    )


def _delete_refresh_cookie(response):
    """Delete the refresh-token cookie."""
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        samesite='Lax',
    )


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


class CookieTokenObtainView(TokenObtainPairView):
    """
    POST /api/auth/token/

    Accepts { email, password }.
    Returns { access } in JSON.
    Sets refresh token as HttpOnly cookie.

    The refresh token is NEVER included in the JSON response.
    """
    throttle_classes = [AuthTokenThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            refresh_token = response.data.pop('refresh', None)
            if refresh_token:
                _set_refresh_cookie(response, refresh_token)

        return response


class CookieTokenRefreshView(APIView):
    """
    POST /api/auth/token/refresh/

    Reads refresh token from HttpOnly cookie (NOT from request body).
    Returns { access } in JSON.
    If ROTATE_REFRESH_TOKENS is True, sets a new refresh cookie.

    Returns 401 if cookie is missing or token is invalid/expired.
    """

    permission_classes = []
    authentication_classes = []
    throttle_classes = [AuthRefreshThrottle]

    def post(self, request, *args, **kwargs):
        raw_token = request.COOKIES.get(REFRESH_COOKIE_NAME)

        if not raw_token:
            return Response(
                {'detail': 'Refresh token cookie not found.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = TokenRefreshSerializer(data={'refresh': raw_token})

        try:
            serializer.is_valid(raise_exception=True)
        except (TokenError, InvalidToken, Exception):
            response = Response(
                {'detail': 'Invalid or expired refresh token.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            _delete_refresh_cookie(response)
            return response

        # Build response — never expose refresh token in JSON
        response = Response({'access': serializer.validated_data['access']})

        # If rotation is enabled, simplejwt produces a new refresh token
        new_refresh = serializer.validated_data.get('refresh')
        if new_refresh:
            _set_refresh_cookie(response, new_refresh)

        return response


class LogoutView(APIView):
    """
    POST /api/auth/logout/

    Blacklists the refresh token (if token_blacklist app is active)
    and deletes the cookie.
    Always returns 204.
    """

    permission_classes = []
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        raw_token = request.COOKIES.get(REFRESH_COOKIE_NAME)

        # Best-effort: blacklist so the token can't be reused
        if raw_token:
            try:
                token = RefreshToken(raw_token)
                token.blacklist()
            except Exception:
                pass  # already blacklisted, expired, or invalid

        response = Response(status=status.HTTP_204_NO_CONTENT)
        _delete_refresh_cookie(response)
        return response
