"""
TON — ASGI Application Entry Point

ASGI config for TON project.
Exposes the ASGI callable as a module-level variable named `application`.

At MVP TON uses standard WSGI (gunicorn) — no WebSocket or async views.
This file exists for forward compatibility and for deployment platforms
that prefer ASGI (e.g., Daphne, Uvicorn).

For Railway deployment, use the Procfile which calls gunicorn/wsgi.
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

application = get_asgi_application()
