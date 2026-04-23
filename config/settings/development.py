"""
TON — Development Settings
Local development overrides. Never use in production.
"""

from .base import *

# Dev SECRET_KEY override (never use in production)
SECRET_KEY = 'django-insecure-ton-dev-2024-x7k9p2m5q8r1t4y7u0i3o6p9s2d5f8g1j4k7l0m3n6q9w2e5r8t1y4u7i0o3p6s9d2f5g8j1k4l7m0n3q6w9e2r5t8y1u4i7o0p3s6d9f2g5j8k1l4m7n0q3w6e9r2t5y8u1i4o7p0s3d6f9g2j5k8l1m4n7q0w3e6r9t2y5u8i1o4p7s0d3f6g9j2k5l8m1n4q7w0e3r6t9y2u5i8o1p4s7d0f3g6j9k2l5m8n1q4w7e0r3t6y9u2i5o8p1s4d7f0g3j6k9l2m5n8q1w4e7r0t3y6u9i2o5p8s1d4f7g0j3k6l9m2n5q8w1e4r7t0y3u6i9o2p5s8d1f4g7j0k3l6m9n2q5w8e1r4t7y0u3i6o9p2s5d8f1g4j7k0l3m6n9q2w5e8r1t4y7u0i3o6p9-GENERATED-FOR-DEV'

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# ─────────────────────────────────────────────
# DATABASE — Local PostgreSQL
# ─────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='ton_db'),
        'USER': config('DB_USER', default='ton_user'),
        'PASSWORD': config('DB_PASSWORD', default='ton_pass'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# ─────────────────────────────────────────────
# CORS — Allow all origins locally
# ─────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = True

# ─────────────────────────────────────────────
# AFRICA'S TALKING — Sandbox in dev
# ─────────────────────────────────────────────
AT_USERNAME = 'sandbox'

# ─────────────────────────────────────────────
# EMAIL — Console backend locally
# ─────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ─────────────────────────────────────────────
# CACHE — Local memory cache in dev
# ─────────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# ─────────────────────────────────────────────
# Dev Overrides — Dummy external services
# ─────────────────────────────────────────────
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': 'dummy-dev',
    'API_KEY': 'dummy-dev-key',
    'API_SECRET': 'dummy-dev-secret',
}

AT_API_KEY = 'dummy-at-api-key'

RESEND_API_KEY = 'dummy-resend-key'
