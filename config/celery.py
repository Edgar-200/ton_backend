"""
TON — Celery Application

Configures Celery for background task processing.
Used for asynchronous NikoScore recalculation and notification delivery
when the platform scales beyond Railway's free tier concurrency limits.

At MVP the Django signals fire synchronously (inline with the request).
When request latency becomes a problem under load, move signal handlers
to Celery tasks by changing the signal receivers to call .delay() instead.

Usage in manage.py / wsgi.py:
  The DJANGO_SETTINGS_MODULE env var must be set before this module loads.

Starting the worker (local):
  celery -A config.celery worker --loglevel=info

Starting the worker (Railway):
  Add a new service: celery -A config.celery worker --loglevel=warning --concurrency=2
"""

import os
from celery import Celery

# Set default Django settings module for Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

app = Celery('ton')

# Use Django settings with CELERY_ namespace prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps (looks for tasks.py in each app)
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Utility task for verifying the worker is running correctly."""
    print(f'Request: {self.request!r}')
