"""
TON — Talent Observable Network
Base settings shared across all environments.
"""

import os
from pathlib import Path
from datetime import timedelta
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ─────────────────────────────────────────────
# SECURITY
# ─────────────────────────────────────────────
SECRET_KEY = config('SECRET_KEY', default='django-insecure-ton-base-fallback-K9p2m5q8r1t4y7u0i3o6p9s2d5f8g1j4k7-DO-NOT-USE-IN-PRODUCTION')

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='').split(',')

# ─────────────────────────────────────────────
# APPLICATIONS
# ─────────────────────────────────────────────
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'cloudinary',
    'cloudinary_storage',
]

LOCAL_APPS = [
    'apps.authentication',
    'apps.students',
    'apps.companies',
    'apps.tasks',
    'apps.nikoscore',
    'apps.invitations',
    'apps.notifications',
    'apps.admin_panel',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ─────────────────────────────────────────────
# MIDDLEWARE
# ─────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

# ─────────────────────────────────────────────
# CUSTOM AUTH USER MODEL
# ─────────────────────────────────────────────
AUTH_USER_MODEL = 'authentication.User'

# ─────────────────────────────────────────────
# INTERNATIONALIZATION
# ─────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Dar_es_Salaam'
USE_I18N = True
USE_TZ = True

# ─────────────────────────────────────────────
# STATIC & MEDIA FILES
# ─────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─────────────────────────────────────────────
# CLOUDINARY — File storage (URLs only in DB)
# ─────────────────────────────────────────────
CLOUDINARY_STORAGE = {
'CLOUD_NAME': config('CLOUDINARY_CLOUD_NAME', default='dummy-dev'),
    'API_KEY': config('CLOUDINARY_API_KEY', default='dummy-dev-key'),
    'API_SECRET': config('CLOUDINARY_API_SECRET', default='dummy-dev-secret'),
}
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# ─────────────────────────────────────────────
# DJANGO REST FRAMEWORK
# ─────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '100/min',
        # Custom throttle scopes (applied per view)
        'register': '5/hour',
        'login': '10/15min',
        'otp_verify': '5/hour',
        'task_submit': '3/hour',
        'invitation_send': '20/day',
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# ─────────────────────────────────────────────
# SIMPLE JWT — Token Configuration
# ─────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    # Embed role in JWT payload — avoids DB query on every request
    'TOKEN_OBTAIN_SERIALIZER': 'apps.authentication.serializers.TONTokenObtainPairSerializer',
}

# ─────────────────────────────────────────────
# AFRICA'S TALKING — SMS / OTP
# ─────────────────────────────────────────────
AT_USERNAME = config('AT_USERNAME', default='sandbox')
AT_API_KEY = config('AT_API_KEY', default='dummy-at-key')
AT_SENDER_ID = 'TON'

# ─────────────────────────────────────────────
# RESEND — Transactional Email
# ─────────────────────────────────────────────
RESEND_API_KEY = config('RESEND_API_KEY', default='dummy-resend-key')
RESEND_FROM_EMAIL = config('RESEND_FROM_EMAIL', default='noreply@ton.co.tz')

# ─────────────────────────────────────────────
# OTP CONFIGURATION
# ─────────────────────────────────────────────
OTP_EXPIRY_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_LENGTH = 6

# ─────────────────────────────────────────────
# NIKOSCORE ENGINE CONSTANTS
# ─────────────────────────────────────────────
NIKOSCORE_MAX = 100
NIKOSCORE_COMPONENT_MAX = 25
NIKOSCORE_INACTIVITY_DAYS = 30
NIKOSCORE_INACTIVITY_DECAY_PER_WEEK = 1
NIKOSCORE_QUALITY_MIN_REVIEWS = 3
NIKOSCORE_OUTLIER_WEIGHT = 0.3
NIKOSCORE_OUTLIER_STD_THRESHOLD = 2

# ─────────────────────────────────────────────
# INVITATION CONFIGURATION
# ─────────────────────────────────────────────
INVITATION_EXPIRY_DAYS = 14

# ─────────────────────────────────────────────
# FILE UPLOAD LIMITS
# ─────────────────────────────────────────────
MAX_SUBMISSION_FILE_SIZE_MB = 5
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {module}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'admin_audit': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        # Django core
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        # TON application logs
        'apps': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        # Admin audit trail — every admin action logged here
        'ton.admin_audit': {
            'handlers': ['admin_audit'],
            'level': 'INFO',
            'propagate': False,
        },
        # Notification delivery logs (email + SMS)
        'apps.notifications': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        # NikoScore engine logs
        'apps.nikoscore': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
}

# ─────────────────────────────────────────────
# PASSWORD RESET TOKEN TTL (minutes)
# ─────────────────────────────────────────────
PASSWORD_RESET_EXPIRY_MINUTES = 30

# ─────────────────────────────────────────────
# AUTHENTICATION BACKENDS
# Required for django.contrib.auth.authenticate() to work with email field
# ─────────────────────────────────────────────
AUTHENTICATION_BACKENDS = [
    'apps.authentication.backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',  # fallback for admin
]

# ─────────────────────────────────────────────
# FRONTEND URL — used in email links
# ─────────────────────────────────────────────
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:3000')
