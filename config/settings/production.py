"""
TON — Production Settings (Railway)
All security headers enabled. Never set DEBUG=True here.
"""

import os
import dj_database_url
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from .base import *

# ─────────────────────────────────────────────
# SECURITY — Non-negotiable in production
# ─────────────────────────────────────────────
DEBUG = False

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# ─────────────────────────────────────────────
# DATABASE — Railway PostgreSQL via URL
# ─────────────────────────────────────────────
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# ─────────────────────────────────────────────
# CORS — Vercel frontend only
# ─────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    os.environ.get('FRONTEND_URL', ''),
]

# ─────────────────────────────────────────────
# CACHE — Redis on Railway
# ─────────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# ─────────────────────────────────────────────
# SENTRY — Error Monitoring
# ─────────────────────────────────────────────
sentry_sdk.init(
    dsn=os.environ.get('SENTRY_DSN', ''),
    integrations=[DjangoIntegration()],
    traces_sample_rate=0.1,
    send_default_pii=False,
)

# ─────────────────────────────────────────────
# CELERY — Background task queue
# ─────────────────────────────────────────────
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
