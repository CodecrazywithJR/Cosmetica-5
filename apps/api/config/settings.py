"""
Django settings for EMR Dermatology + POS Cosmetics project.
"""

import os
from datetime import timedelta
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Application version
VERSION = os.environ.get('APP_VERSION', '1.0.0')
COMMIT_HASH = os.environ.get('COMMIT_HASH', None)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-secret-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'drf_spectacular',
    
    # Local apps - DOMAIN_MODEL.md structure
    'apps.core',        # app_settings, clinic_location
    'apps.authz',       # auth_user, auth_role, auth_user_role, practitioner
    'apps.clinical',    # patient, guardian, encounter, appointment, consent, clinical_photo, etc.
    'apps.documents',   # document (unified)
    'apps.commerce',    # products, inventory, sales, invoices, payments
    'apps.website',     # cms_*, website_settings, marketing_media_asset, public_lead
    # 'apps.social',      # social_* (Instagram Manual Pack) - DISABLED: AUTH_USER_MODEL issue
    'apps.ops',         # audit_log, diagnostics
    'apps.legal',       # legal_entity (minimal, no fiscal logic) - See ADR-002
    
    # Legacy apps (to be migrated)
    'apps.encounters',
    'apps.photos',
    'apps.products',
    'apps.stock',
    'apps.sales',
    'apps.pos',  # Point of Sale with fuzzy patient search
    'apps.integrations',
]

# Add debug toolbar in development
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar', 'django_extensions']

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # CORS before CommonMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.core.observability.correlation.RequestCorrelationMiddleware',  # Request correlation
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Add debug toolbar middleware in development
if DEBUG:
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DATABASE_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.environ.get('DATABASE_NAME', 'emr_derma_db'),
        'USER': os.environ.get('DATABASE_USER', 'emr_user'),
        'PASSWORD': os.environ.get('DATABASE_PASSWORD', 'emr_dev_pass'),
        'HOST': os.environ.get('DATABASE_HOST', 'postgres'),
        'PORT': os.environ.get('DATABASE_PORT', '5432'),
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files (user uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Custom User Model
AUTH_USER_MODEL = 'authz.User'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==============================================================================
# REST FRAMEWORK
# ==============================================================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    # Throttling configuration for public endpoints
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',  # Generic anonymous users (fallback)
        'user': '1000/hour',  # Authenticated users (not typically throttled)
        'lead_submissions': '10/hour',  # Public lead form submissions
        'lead_burst': '2/min',  # Burst protection for lead submissions
    },
}

# ==============================================================================
# SIMPLE JWT
# ==============================================================================
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(
        minutes=int(os.environ.get('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', 60))
    ),
    'REFRESH_TOKEN_LIFETIME': timedelta(
        days=int(os.environ.get('JWT_REFRESH_TOKEN_LIFETIME_DAYS', 7))
    ),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': os.environ.get('JWT_SIGNING_KEY', SECRET_KEY),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ==============================================================================
# CORS
# ==============================================================================
CORS_ALLOWED_ORIGINS = os.environ.get(
    'DJANGO_CORS_ALLOWED_ORIGINS',
    'http://localhost:3000'
).split(',')

CORS_ALLOW_CREDENTIALS = True

# ==============================================================================
# DRF SPECTACULAR (OpenAPI Schema)
# ==============================================================================
SPECTACULAR_SETTINGS = {
    'TITLE': 'EMR Dermatology + POS Cosmetics API',
    'DESCRIPTION': 'RESTful API for dermatology practice management with integrated POS',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
}

# ==============================================================================
# CELERY
# ==============================================================================
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes

# ==============================================================================
# MINIO / S3 STORAGE
# ==============================================================================
MINIO_ENDPOINT = os.environ.get('MINIO_ENDPOINT', 'minio:9000')
MINIO_ACCESS_KEY = os.environ.get('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.environ.get('MINIO_SECRET_KEY', 'minioadmin')
MINIO_USE_SSL = os.environ.get('MINIO_USE_SSL', 'False') == 'True'
MINIO_PUBLIC_URL = os.environ.get('MINIO_PUBLIC_URL', 'http://localhost:9000')

# MinIO buckets - CRITICAL: Separate clinical from marketing data
MINIO_CLINICAL_BUCKET = os.environ.get('MINIO_CLINICAL_BUCKET', 'derma-photos')
MINIO_MARKETING_BUCKET = os.environ.get('MINIO_MARKETING_BUCKET', 'marketing')
MINIO_DOCUMENTS_BUCKET = os.environ.get('MINIO_DOCUMENTS_BUCKET', 'documents')

# Legacy variable for backward compatibility
MINIO_BUCKET_NAME = MINIO_CLINICAL_BUCKET

# Configure Django storage backends
if not DEBUG:
    # In production, use MinIO for static and media
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    
    AWS_ACCESS_KEY_ID = MINIO_ACCESS_KEY
    AWS_SECRET_ACCESS_KEY = MINIO_SECRET_KEY
    AWS_STORAGE_BUCKET_NAME = MINIO_CLINICAL_BUCKET  # Default to clinical bucket
    AWS_S3_ENDPOINT_URL = f"{'https' if MINIO_USE_SSL else 'http'}://{MINIO_ENDPOINT}"
    AWS_S3_USE_SSL = MINIO_USE_SSL
    AWS_DEFAULT_ACL = 'public-read'
    AWS_QUERYSTRING_AUTH = False

# ==============================================================================
# LOGGING
# ==============================================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'correlation': {
            '()': 'apps.core.observability.logging.CorrelationFilter',
        },
    },
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'json': {
            '()': 'apps.core.observability.logging.SanitizedJSONFormatter',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json' if not DEBUG else 'verbose',
            'filters': ['correlation'],
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.environ.get('LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

# ==============================================================================
# DEBUG TOOLBAR (Development Only)
# ==============================================================================
if DEBUG:
    import socket
    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS = [ip[: ip.rfind(".")] + ".1" for ip in ips] + ["127.0.0.1", "10.0.2.2"]

# ==============================================================================
# EMAIL
# ==============================================================================
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend'
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')

# ==============================================================================
# INTEGRATIONS
# ==============================================================================
CALENDLY_WEBHOOK_SECRET = os.environ.get('CALENDLY_WEBHOOK_SECRET', 'dev-webhook-secret')
CALENDLY_API_TOKEN = os.environ.get('CALENDLY_API_TOKEN', '')
