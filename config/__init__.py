"""
TON — Package initialisation.

Loading the Celery app here ensures it is initialised whenever Django starts,
making shared_task decorators work correctly across all apps.
"""
from .celery import app as celery_app

__all__ = ('celery_app',)
