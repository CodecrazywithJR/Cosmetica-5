# Public API Rate Limiting

## Overview

This document describes the rate limiting (throttling) implementation for public-facing API endpoints in the Cosmetica 5 EMR system. Rate limiting protects the system from abuse, spam, and denial-of-service attacks while ensuring legitimate users can access public content.

## Implementation Summary

- **Framework**: Django REST Framework (DRF) throttling
- **Mechanism**: Per-IP address throttling for anonymous users
- **Storage**: Django cache backend (configurable: Redis, Memcached, or default)
- **Scope**: `/public/` routes only (authenticated endpoints use different limits)

## Rate Limits

### Lead Submission Endpoint

**Endpoint**: `POST /public/leads/`

**Rate Limits**:
- **Hourly Limit**: 10 submissions per hour per IP
- **Burst Protection**: 2 submissions per minute per IP

**Rationale**:
- Prevents spam and automated form submissions
- Allows legitimate users to submit contact forms
- Burst protection stops rapid-fire attacks

**Throttle Classes Applied**:
```python
@throttle_classes([LeadBurstThrottle, LeadHourlyThrottle])
def create_lead(request):
    """Public endpoint for contact form submissions."""
```

**Configuration** (`config/settings.py`):
```python
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_RATES': {
        'lead_submissions': '10/hour',  # Hourly rate limit
        'lead_burst': '2/min',          # Burst protection
    },
}
```

### Read-Only Public Endpoints

**Endpoints**:
- `GET /public/content/pages/`
- `GET /public/content/posts/`
- `GET /public/content/services/`
- `GET /public/content/staff/`
- `GET /public/content/settings/`

**Rate Limits**: **NONE** (no throttling applied)

**Rationale**:
- Read-only operations are low-risk
- Public website content should be freely accessible
- No database modifications possible
- CDN caching handles high traffic (if deployed)

## Throttle Class Definitions

### LeadHourlyThrottle

```python
class LeadHourlyThrottle(AnonRateThrottle):
    """
    Rate limit for lead submissions: 10 per hour per IP.
    
    Prevents spam while allowing legitimate contact form usage.
    """
    scope = 'lead_submissions'
```

### LeadBurstThrottle

```python
class LeadBurstThrottle(AnonRateThrottle):
    """
    Burst protection for lead submissions: 2 per minute per IP.
    
    Prevents rapid-fire spam attacks.
    """
    scope = 'lead_burst'
```

## HTTP 429 Response Format

When a client exceeds the rate limit, they receive:

**Status Code**: `429 Too Many Requests`

**Response Body** (JSON):
```json
{
  "detail": "Request was throttled. Expected available in 58 seconds."
}
```

**Headers** (may include):
```
Retry-After: 58
```

## Authenticated Endpoints

**Scope**: All endpoints under `/api/` (e.g., `/api/stock/`, `/api/patients/`)

**Throttle Scope**: `user` (1000 requests/hour)

**Note**: Authenticated endpoints are NOT affected by public API throttling. They use the `user` throttle scope with much higher limits.

## Testing

### Running Tests

```bash
# Run all throttling tests
pytest apps/api/tests/test_public_throttling.py -v

# With database configuration
DATABASE_HOST=localhost pytest apps/api/tests/test_public_throttling.py -v
```

### Test Coverage

✅ Hourly rate limit enforcement (10/hour)  
✅ Burst protection enforcement (2/min)  
✅ 429 response format and messages  
✅ Lead creation within limits  
✅ Authenticated endpoints isolation  
✅ Read-only endpoints not throttled  

**Test File**: `tests/test_public_throttling.py` (9 tests, all passing)

## Cache Backend Configuration

### Default (Development)

Uses Django's default cache backend (local memory).

**Limitations**:
- Not shared across processes
- Resets on server restart

### Production (Redis Recommended)

```python
# config/settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
```

**Benefits**:
- Shared across multiple processes/servers
- Persistent across restarts
- Accurate rate limiting in load-balanced environments

## Troubleshooting

### Client Reports "Too Many Requests"

1. **Verify Legitimacy**: Check if user is genuinely submitting valid forms
2. **Check IP**: Use `request.META['REMOTE_ADDR']` to identify IP
3. **Wait Period**: Ask client to wait 60 seconds (burst limit) or 1 hour (hourly limit)
4. **Manual Override**: Temporarily clear cache: `python manage.py shell` → `from django.core.cache import cache; cache.clear()`

### Rate Limiting Not Working

1. **Check Settings**: Ensure `DEFAULT_THROTTLE_RATES` is configured
2. **Verify Throttle Classes**: Confirm `@throttle_classes` decorator is applied
3. **Cache Backend**: Verify cache backend is working: `python manage.py shell` → `from django.core.cache import cache; cache.set('test', 123); print(cache.get('test'))`
4. **Test Environment**: In tests, call `cache.clear()` in `setup_method()` to reset state

### Different IPs Being Throttled Together

**Cause**: Behind a proxy/load balancer without proper IP forwarding

**Solution**: Configure trusted proxy headers in Django:
```python
# config/settings.py
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

Then update `ALLOWED_HOSTS` to include proxy IP.

## Security Considerations

### IP Spoofing

- DRF throttling uses `request.META['REMOTE_ADDR']`
- In production, ensure trusted proxy headers are configured
- Validate `X-Forwarded-For` headers if behind a CDN/proxy

### Distributed Attacks

- Single IP throttling won't stop distributed attacks
- Consider adding:
  - WAF (Web Application Firewall)
  - Cloudflare Bot Management
  - CAPTCHA for repeated failed attempts

### Rate Limit Bypass

- Authenticated users can bypass anonymous throttling by logging in
- Monitor for account creation spam
- Consider throttling user registration endpoints

## Monitoring

### Recommended Metrics

1. **429 Response Count**: Track how often throttling is triggered
2. **Unique IPs Throttled**: Identify if attacks are distributed
3. **Time-of-Day Patterns**: Detect automated scripts (uniform distribution)
4. **Lead Conversion Rate**: Ensure throttling isn't blocking legitimate users

### Django Logging

```python
# config/settings.py
LOGGING = {
    'version': 1,
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': '/var/log/django/throttle.log',
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['file'],
            'level': 'WARNING',  # Logs 429 responses
        },
    },
}
```

## Future Enhancements

### Potential Improvements

1. **Dynamic Rate Limits**: Adjust limits based on system load
2. **User-Agent Throttling**: Apply stricter limits to known bots
3. **Geographic Throttling**: Different limits for different regions
4. **CAPTCHA Integration**: Challenge suspicious IPs instead of blocking
5. **Webhook Notifications**: Alert admins when attack detected

### Example: CAPTCHA on Throttle

```python
def create_lead(request):
    if is_throttled(request):
        return Response({
            'error': 'Rate limit exceeded',
            'captcha_required': True,
            'captcha_site_key': settings.RECAPTCHA_SITE_KEY
        }, status=429)
```

## References

- [DRF Throttling Documentation](https://www.django-rest-framework.org/api-guide/throttling/)
- [Django Cache Framework](https://docs.djangoproject.com/en/4.2/topics/cache/)
- [OWASP API Security: Rate Limiting](https://owasp.org/www-project-api-security/)

## Change Log

| Date       | Author | Change                                      |
|------------|--------|---------------------------------------------|
| 2024-12-16 | System | Initial implementation: 10/hour + 2/min     |

---

**Last Updated**: December 16, 2024  
**Maintained By**: Platform Engineering Team  
**Contact**: dev@cosmetica5.com
